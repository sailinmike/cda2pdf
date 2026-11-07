/*
 * Copyright (C) 2026 Mint Medical PLLC
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

/*
 * Receives the completion callback from an asynchronous print operation.
 *
 * WKWebView's synchronous -[NSPrintOperation runOperation] deadlocks here:
 * pagination needs replies from the web content process, which arrive on the
 * main run loop that runOperation is blocking. Driving the operation through
 * runOperationModalForWindow: and spinning the run loop ourselves keeps the
 * main loop live so those replies can be delivered.
 */
@interface PrintCompletion : NSObject
@property (nonatomic, assign) BOOL done;
@property (nonatomic, assign) BOOL success;
@end

@implementation PrintCompletion
- (void)printOperationDidRun:(NSPrintOperation *)printOperation
                     success:(BOOL)success
                 contextInfo:(void *)contextInfo {
    self.success = success;
    self.done = YES;
}
@end

/*
 * Navigation delegate: signals load completion and refuses any navigation
 * that is not to a local file.
 */
@interface LoadDelegate : NSObject <WKNavigationDelegate>
@property (nonatomic, assign) BOOL done;
@property (nonatomic, assign) BOOL failed;
@end

@implementation LoadDelegate

- (void)webView:(WKWebView *)webView didFinishNavigation:(WKNavigation *)navigation {
    self.done = YES;
}

- (void)webView:(WKWebView *)webView
        didFailNavigation:(WKNavigation *)navigation
                withError:(NSError *)error {
    fprintf(stderr, "cda2pdf: navigation failed: %s\n",
            [[error localizedDescription] UTF8String]);
    self.failed = YES;
    self.done = YES;
}

- (void)webView:(WKWebView *)webView
        didFailProvisionalNavigation:(WKNavigation *)navigation
                           withError:(NSError *)error {
    fprintf(stderr, "cda2pdf: provisional navigation failed: %s\n",
            [[error localizedDescription] UTF8String]);
    self.failed = YES;
    self.done = YES;
}

/*
 * Second line of defense. The content rule list (below) blocks subresource
 * loads; this blocks frame navigations, including anything an iframe in a
 * clinical document might attempt.
 */
- (void)webView:(WKWebView *)webView
        decidePolicyForNavigationAction:(WKNavigationAction *)navigationAction
                        decisionHandler:(void (^)(WKNavigationActionPolicy))decisionHandler {
    NSString *scheme = [[[[navigationAction request] URL] scheme] lowercaseString];
    if (scheme == nil
        || [scheme isEqualToString:@"file"]
        || [scheme isEqualToString:@"about"]
        || [scheme isEqualToString:@"data"]) {
        decisionHandler(WKNavigationActionPolicyAllow);
        return;
    }
    fprintf(stderr, "cda2pdf: blocked non-local navigation during render: %s\n",
            [[[[navigationAction request] URL] absoluteString] UTF8String]);
    decisionHandler(WKNavigationActionPolicyCancel);
}

@end

/*
 * Builds the content rule list that prevents rendering from reaching the
 * network.
 *
 * Clinical documents are untrusted input. A CDA narrative, a vendor
 * stylesheet, or a user-supplied stylesheet can reference a remote resource --
 * for example <img src="https://example.com/x.gif?mrn=...">. WebKit would
 * otherwise fetch it, transmitting patient identifiers to a third party as a
 * side effect of rendering a PDF.
 *
 * WKWebView, unlike the legacy WebView it replaced, offers no delegate
 * callback for subresource loads, so blocking is expressed declaratively: deny
 * everything, then re-allow only the local schemes. Rules are evaluated in
 * order and "ignore-previous-rules" undoes the preceding block.
 *
 * Returns nil on failure, which the caller treats as fatal -- rendering
 * without the guard in place is not an acceptable fallback.
 */
static WKContentRuleList *BuildBlockAllNetworkRuleList(void) {
    NSString *rules = @"["
        "{\"trigger\":{\"url-filter\":\".*\"},\"action\":{\"type\":\"block\"}},"
        "{\"trigger\":{\"url-filter\":\"^file:\"},\"action\":{\"type\":\"ignore-previous-rules\"}},"
        "{\"trigger\":{\"url-filter\":\"^data:\"},\"action\":{\"type\":\"ignore-previous-rules\"}},"
        "{\"trigger\":{\"url-filter\":\"^about:\"},\"action\":{\"type\":\"ignore-previous-rules\"}}"
        "]";

    __block WKContentRuleList *compiled = nil;
    __block BOOL finished = NO;

    [[WKContentRuleListStore defaultStore]
        compileContentRuleListForIdentifier:@"cda2pdf-block-all-network"
                     encodedContentRuleList:rules
                          completionHandler:^(WKContentRuleList *list, NSError *error) {
        if (error) {
            fprintf(stderr, "cda2pdf: failed to compile network block rules: %s\n",
                    [[error localizedDescription] UTF8String]);
        }
        compiled = list;
        finished = YES;
    }];

    NSDate *limit = [NSDate dateWithTimeIntervalSinceNow:20.0];
    while (!finished && [[NSDate date] compare:limit] == NSOrderedAscending) {
        [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode
                                 beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.02]];
    }
    return compiled;
}

/*
 * Reports non-local resource references found in the HTML about to be
 * rendered.
 *
 * The content rule list blocks these silently, so this scan exists purely for
 * visibility: an operator should be able to see that a document asked to
 * reach the network, even though the request never left the machine.
 */
static void WarnAboutRemoteReferences(NSString *htmlPath) {
    NSString *html = [NSString stringWithContentsOfFile:htmlPath
                                               encoding:NSUTF8StringEncoding
                                                  error:nil];
    if (!html) {
        return;
    }
    NSRegularExpression *re =
        [NSRegularExpression regularExpressionWithPattern:
            @"(?:src|href)\\s*=\\s*[\"']\\s*((?:https?:|ftp:)//[^\"']+)"
                                                  options:NSRegularExpressionCaseInsensitive
                                                    error:nil];
    if (!re) {
        return;
    }
    NSMutableSet<NSString *> *seen = [NSMutableSet set];
    [re enumerateMatchesInString:html
                         options:0
                           range:NSMakeRange(0, [html length])
                      usingBlock:^(NSTextCheckingResult *m, NSMatchingFlags flags, BOOL *stop) {
        if ([m numberOfRanges] < 2) {
            return;
        }
        NSString *url = [html substringWithRange:[m rangeAtIndex:1]];
        if ([seen containsObject:url]) {
            return;
        }
        [seen addObject:url];
        fprintf(stderr,
                "cda2pdf: blocked non-local resource reference in document: %s\n",
                [url UTF8String]);
    }];
}

BOOL renderHTMLToPDF(NSString *htmlPath, NSString *pdfPath, WKContentRuleList *blockList) {
    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];

    // Ephemeral data store: WebKit keeps no cache, cookies or local storage on
    // disk, so no fragment of a clinical document outlives the process here.
    config.websiteDataStore = [WKWebsiteDataStore nonPersistentDataStore];

    if (blockList) {
        [[config userContentController] addContentRuleList:blockList];
    }

    // Clinical documents are untrusted input; no scripting.
    config.defaultWebpagePreferences.allowsContentJavaScript = NO;
    config.preferences.javaScriptCanOpenWindowsAutomatically = NO;
    config.suppressesIncrementalRendering = YES;

    NSRect rect = NSMakeRect(0, 0, 820, 1050);
    WKWebView *webView = [[WKWebView alloc] initWithFrame:rect configuration:config];
    LoadDelegate *del = [[LoadDelegate alloc] init];
    [webView setNavigationDelegate:del];

    /*
     * WKWebView renders in a separate content process, which stays idle while
     * the view is detached. Its print operation then blocks forever waiting
     * for content that is never drawn. Hosting the view in an off-screen
     * window gets it into a window hierarchy so rendering actually proceeds.
     * The window is positioned far off-screen and never ordered front, so
     * nothing appears on the user's display.
     */
    NSWindow *offscreen =
        [[NSWindow alloc] initWithContentRect:rect
                                    styleMask:NSWindowStyleMaskBorderless
                                      backing:NSBackingStoreBuffered
                                        defer:NO];
    /*
     * NSWindow defaults to releasedWhenClosed for programmatically created
     * windows. Under ARC that double-frees: -close releases the window while
     * ARC still holds its own reference, which crashes on the second document
     * in a multi-document run. Opt out and let ARC own the lifetime.
     */
    [offscreen setReleasedWhenClosed:NO];
    [offscreen setFrameOrigin:NSMakePoint(-20000, -20000)];
    [offscreen setContentView:webView];
    [offscreen orderBack:nil];

    WarnAboutRemoteReferences(htmlPath);

    NSURL *url = [NSURL fileURLWithPath:htmlPath];
    /*
     * Read access is granted from the filesystem root because a package's
     * stylesheet and images routinely live outside the temporary directory
     * holding the generated HTML -- typically in the user's own XDM export.
     * This is a local CLI tool already running with the user's permissions, so
     * it grants no authority the invoking user lacks. It is safe in
     * combination with the two controls above: scripting is disabled, so a
     * document cannot read a local file programmatically, and all network
     * egress is blocked, so nothing it does load can be exfiltrated.
     */
    [webView loadFileURL:url allowingReadAccessToURL:[NSURL fileURLWithPath:@"/"]];

    NSDate *timeout = [NSDate dateWithTimeIntervalSinceNow:25.0];
    while (!del.done && [[NSDate date] compare:timeout] == NSOrderedAscending) {
        [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode
                                 beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    }
    if (!del.done) {
        fprintf(stderr, "cda2pdf: timed out loading %s\n", [htmlPath UTF8String]);
        return NO;
    }
    if (del.failed) {
        return NO;
    }
    // Let layout and image decoding settle before paginating.
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.35]];

    NSMutableDictionary *dict = [NSMutableDictionary dictionaryWithDictionary:[[NSPrintInfo sharedPrintInfo] dictionary]];
    dict[NSPrintJobDisposition] = NSPrintSaveJob;
    dict[NSPrintJobSavingURL] = [NSURL fileURLWithPath:pdfPath];

    NSPrintInfo *printInfo = [[NSPrintInfo alloc] initWithDictionary:dict];
    [printInfo setPaperSize:NSMakeSize(612, 792)]; // US Letter
    [printInfo setTopMargin:28];
    [printInfo setBottomMargin:34];
    [printInfo setLeftMargin:28];
    [printInfo setRightMargin:28];
    [printInfo setHorizontalPagination:NSPrintingPaginationModeFit];
    [printInfo setVerticalPagination:NSPrintingPaginationModeAutomatic];
    [printInfo setVerticallyCentered:NO];

    /*
     * WKWebView paginates itself through its own print operation; the legacy
     * approach of printing the frame's document view does not apply, because
     * the page content lives in a separate process.
     */
    NSPrintOperation *op = [webView printOperationWithPrintInfo:printInfo];
    [op setShowsPrintPanel:NO];
    [op setShowsProgressPanel:NO];
    // The operation's view must be sized to the printable area or WebKit
    // paginates against the on-screen frame and clips the right edge.
    [[op view] setFrame:NSMakeRect(0, 0,
                                   612 - 28 - 28,
                                   792 - 28 - 34)];

    PrintCompletion *completion = [[PrintCompletion alloc] init];
    [op runOperationModalForWindow:offscreen
                          delegate:completion
                    didRunSelector:@selector(printOperationDidRun:success:contextInfo:)
                       contextInfo:NULL];

    NSDate *printLimit = [NSDate dateWithTimeIntervalSinceNow:120.0];
    while (!completion.done && [[NSDate date] compare:printLimit] == NSOrderedAscending) {
        [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode
                                 beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.02]];
    }
    if (!completion.done) {
        fprintf(stderr, "cda2pdf: timed out paginating %s\n", [htmlPath UTF8String]);
    }
    BOOL ok = completion.done && completion.success;

    // Tear down the off-screen host window and its content process.
    [webView setNavigationDelegate:nil];
    [offscreen setContentView:nil];
    [offscreen close];

    return ok;
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

        /*
         * Compile the network block list once, up front. If it cannot be
         * built we abort rather than render: producing a PDF without the
         * guard in place could silently transmit patient data.
         */
        WKContentRuleList *blockList = BuildBlockAllNetworkRuleList();
        if (!blockList) {
            fprintf(stderr,
                    "cda2pdf: refusing to render without the network block list\n");
            return 4;
        }

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

            if (!renderHTMLToPDF(hPath, pPath, blockList)) {
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
