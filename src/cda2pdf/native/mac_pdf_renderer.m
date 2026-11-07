/*
 * Copyright (C) 2026 cda2pdf contributors
 *
 * This file is part of cda2pdf.
 *
 * cda2pdf is free software: you can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * cda2pdf is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 *
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#import <PDFKit/PDFKit.h>

@interface LoadDelegate : NSObject <WebFrameLoadDelegate>
@property (nonatomic, assign) BOOL done;
@end

@implementation LoadDelegate
- (void)webView:(WebView *)sender didFinishLoadForFrame:(WebFrame *)frame {
    if (frame == [sender mainFrame]) {
        self.done = YES;
    }
}
- (void)webView:(WebView *)sender didFailLoadWithError:(NSError *)error forFrame:(WebFrame *)frame {
    NSLog(@"Failed load: %@", error);
    self.done = YES;
}
@end

BOOL renderHTMLToPDF(NSString *htmlPath, NSString *pdfPath) {
    NSRect rect = NSMakeRect(0, 0, 820, 1050);
    WebView *webView = [[WebView alloc] initWithFrame:rect frameName:nil groupName:nil];
    LoadDelegate *del = [[LoadDelegate alloc] init];
    [webView setFrameLoadDelegate:del];
    [[webView preferences] setShouldPrintBackgrounds:YES];
    [[webView preferences] setLoadsImagesAutomatically:YES];

    NSURL *url = [NSURL fileURLWithPath:htmlPath];
    [[webView mainFrame] loadRequest:[NSURLRequest requestWithURL:url]];

    NSDate *timeout = [NSDate dateWithTimeIntervalSinceNow:25.0];
    while (!del.done && [[NSDate date] compare:timeout] == NSOrderedAscending) {
        [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    }
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.15]];

    NSMutableDictionary *dict = [NSMutableDictionary dictionaryWithDictionary:[[NSPrintInfo sharedPrintInfo] dictionary]];
    dict[NSPrintJobDisposition] = NSPrintSaveJob;
    dict[NSPrintJobSavingURL] = [NSURL fileURLWithPath:pdfPath];

    NSPrintInfo *printInfo = [[NSPrintInfo alloc] initWithDictionary:dict];
    [printInfo setPaperSize:NSMakeSize(612, 792)]; // US Letter
    [printInfo setTopMargin:28];
    [printInfo setBottomMargin:34];
    [printInfo setLeftMargin:28];
    [printInfo setRightMargin:28];
    [printInfo setHorizontalPagination:NSFitPagination];
    [printInfo setVerticalPagination:NSAutoPagination];
    [printInfo setVerticallyCentered:NO];

    NSView *docView = [[[webView mainFrame] frameView] documentView];
    NSPrintOperation *op = [NSPrintOperation printOperationWithView:docView printInfo:printInfo];
    [op setShowsPrintPanel:NO];
    [op setShowsProgressPanel:NO];
    return [op runOperation];
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) {
            fprintf(stderr, "Usage: cda2pdf_mac_renderer <manifest.json> [result.json]\n");
            return 1;
        }
        [NSApplication sharedApplication];

        NSString *manifestPath = [NSString stringWithUTF8String:argv[1]];
        NSData *jsonData = [NSData dataWithContentsOfFile:manifestPath];
        if (!jsonData) {
            fprintf(stderr, "Error: Could not read manifest at %s\n", argv[1]);
            return 1;
        }
        NSError *jsonErr = nil;
        NSDictionary *manifest = [NSJSONSerialization JSONObjectWithData:jsonData options:0 error:&jsonErr];
        if (!manifest || jsonErr) {
            fprintf(stderr, "Error parsing JSON manifest: %s\n", [[jsonErr localizedDescription] UTF8String]);
            return 1;
        }

        NSString *tempMergedPath = manifest[@"temp_merged_pdf"];
        NSString *finalPdfPath = manifest[@"output_pdf"];
        NSString *footerPrefix = manifest[@"footer_prefix"] ?: @"Clinical Document Record";
        NSString *docTitle = manifest[@"title"] ?: @"CDA Clinical Document Record";
        NSString *docAuthor = manifest[@"author"] ?: @"cda2pdf";
        NSString *docSubject = manifest[@"subject"] ?: @"HL7 CDA / IHE XDM Clinical Document Extraction";
        NSArray<NSDictionary *> *parts = manifest[@"parts"];

        NSMutableArray<PDFDocument *> *subDocs = [NSMutableArray array];
        NSMutableArray<NSNumber *> *startPages = [NSMutableArray array];
        NSMutableArray<NSString *> *pageSectionLabels = [NSMutableArray array];
        NSMutableArray<NSDictionary *> *partSummaries = [NSMutableArray array];
        NSUInteger totalPages = 0;

        for (NSDictionary *part in parts) {
            NSString *hPath = part[@"html"];
            NSString *pPath = part[@"pdf"];
            NSString *shortLabel = part[@"short_label"] ?: @"Document";
            NSString *bookmarkLabel = part[@"bookmark_label"] ?: shortLabel;

            if (!renderHTMLToPDF(hPath, pPath)) {
                fprintf(stderr, "Failed rendering HTML file: %s\n", [hPath UTF8String]);
                return 2;
            }
            PDFDocument *subDoc = [[PDFDocument alloc] initWithURL:[NSURL fileURLWithPath:pPath]];
            if (!subDoc) {
                fprintf(stderr, "Failed loading rendered PDF: %s\n", [pPath UTF8String]);
                return 2;
            }
            [subDocs addObject:subDoc];
            [startPages addObject:@(totalPages)];
            NSUInteger subCount = [subDoc pageCount];
            for (NSUInteger i = 0; i < subCount; i++) {
                [pageSectionLabels addObject:[NSString stringWithFormat:@"%@ (Doc Page %lu of %lu)", shortLabel, (unsigned long)(i + 1), (unsigned long)subCount]];
            }
            [partSummaries addObject:@{
                @"short_label": shortLabel,
                @"bookmark_label": bookmarkLabel,
                @"start_page": @(totalPages + 1),
                @"end_page": @(totalPages + subCount),
                @"page_count": @(subCount)
            }];
            totalPages += subCount;
        }

        // Draw all pages into a CGPDFContext and stamp page numbers in the bottom margin
        NSURL *tempURL = [NSURL fileURLWithPath:tempMergedPath];
        CGRect mediaBox = CGRectMake(0, 0, 612, 792);
        CGContextRef pdfCtx = CGPDFContextCreateWithURL((__bridge CFURLRef)tempURL, &mediaBox, NULL);

        NSDictionary *footerAttrs = @{
            NSFontAttributeName: [NSFont fontWithName:@"Helvetica" size:7.5],
            NSForegroundColorAttributeName: [NSColor colorWithCalibratedWhite:0.35 alpha:1.0]
        };

        NSUInteger globalPageIdx = 0;
        for (PDFDocument *subDoc in subDocs) {
            NSUInteger subCount = [subDoc pageCount];
            for (NSUInteger i = 0; i < subCount; i++) {
                PDFPage *page = [subDoc pageAtIndex:i];
                CGRect pageBox = [page boundsForBox:kPDFDisplayBoxMediaBox];
                CGContextBeginPage(pdfCtx, &pageBox);
                CGContextSaveGState(pdfCtx);
                [page drawWithBox:kPDFDisplayBoxMediaBox toContext:pdfCtx];
                CGContextRestoreGState(pdfCtx);

                // Draw footer line and text
                NSGraphicsContext *nsCtx = [NSGraphicsContext graphicsContextWithCGContext:pdfCtx flipped:NO];
                [NSGraphicsContext saveGraphicsState];
                [NSGraphicsContext setCurrentContext:nsCtx];

                CGContextSetStrokeColorWithColor(pdfCtx, [[NSColor colorWithCalibratedWhite:0.82 alpha:1.0] CGColor]);
                CGContextSetLineWidth(pdfCtx, 0.5);
                CGContextMoveToPoint(pdfCtx, 28, 24);
                CGContextAddLineToPoint(pdfCtx, 612 - 28, 24);
                CGContextStrokePath(pdfCtx);

                NSString *leftText = [NSString stringWithFormat:@"%@   |   %@", footerPrefix, pageSectionLabels[globalPageIdx]];
                NSString *rightText = [NSString stringWithFormat:@"Page %lu of %lu", (unsigned long)(globalPageIdx + 1), (unsigned long)totalPages];

                [leftText drawAtPoint:NSMakePoint(28, 12) withAttributes:footerAttrs];
                NSSize rightSize = [rightText sizeWithAttributes:footerAttrs];
                [rightText drawAtPoint:NSMakePoint(612 - 28 - rightSize.width, 12) withAttributes:footerAttrs];

                [NSGraphicsContext restoreGraphicsState];
                CGContextEndPage(pdfCtx);
                globalPageIdx++;
            }
        }
        CGPDFContextClose(pdfCtx);
        CGContextRelease(pdfCtx);

        // Load stamped PDF and attach PDFOutline bookmarks + document metadata
        PDFDocument *masterDoc = [[PDFDocument alloc] initWithURL:tempURL];
        PDFOutline *rootOutline = [[PDFOutline alloc] init];
        for (NSUInteger pIdx = 0; pIdx < [parts count]; pIdx++) {
            NSUInteger startPageIdx = [startPages[pIdx] unsignedIntegerValue];
            if (startPageIdx < [masterDoc pageCount]) {
                PDFPage *firstPage = [masterDoc pageAtIndex:startPageIdx];
                NSRect bounds = [firstPage boundsForBox:kPDFDisplayBoxMediaBox];
                PDFDestination *dest = [[PDFDestination alloc] initWithPage:firstPage atPoint:NSMakePoint(0, NSMaxY(bounds))];
                PDFOutline *item = [[PDFOutline alloc] init];
                [item setLabel:parts[pIdx][@"bookmark_label"] ?: parts[pIdx][@"short_label"]];
                [item setDestination:dest];
                [rootOutline insertChild:item atIndex:[rootOutline numberOfChildren]];
            }
        }
        [masterDoc setOutlineRoot:rootOutline];

        NSMutableDictionary *attrs = [NSMutableDictionary dictionaryWithDictionary:[masterDoc documentAttributes]];
        attrs[PDFDocumentTitleAttribute] = docTitle;
        attrs[PDFDocumentAuthorAttribute] = docAuthor;
        attrs[PDFDocumentSubjectAttribute] = docSubject;
        [masterDoc setDocumentAttributes:attrs];

        BOOL wrote = [masterDoc writeToFile:finalPdfPath];
        if (!wrote) {
            fprintf(stderr, "Failed writing final PDF to %s\n", [finalPdfPath UTF8String]);
            return 3;
        }

        if (argc >= 3) {
            NSString *resultPath = [NSString stringWithUTF8String:argv[2]];
            NSDictionary *resDict = @{
                @"output_pdf": finalPdfPath,
                @"total_pages": @(totalPages),
                @"parts": partSummaries
            };
            NSData *resData = [NSJSONSerialization dataWithJSONObject:resDict options:NSJSONWritingPrettyPrinted error:nil];
            [resData writeToFile:resultPath atomically:YES];
        }
    }
    return 0;
}
