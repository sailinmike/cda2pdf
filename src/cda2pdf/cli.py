# Copyright (C) 2026 cda2pdf contributors
#
# This file is part of cda2pdf.
#
# cda2pdf is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# cda2pdf is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Command-line interface for cda2pdf."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .converter import CDAPackageConverter


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cda2pdf",
        description=(
            "Convert HL7 CDA R2 XML files, IHE XDM clinical directories, or XDM .zip archives "
            "into a single unabridged, bookmarked, page-numbered PDF document."
        ),
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Path(s) to an IHE XDM directory, a .zip archive, or one or more CDA .xml files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_pdf",
        default=None,
        help="Output PDF file path (defaults to <Patient_Name>_<Source>.pdf in the current directory).",
    )
    parser.add_argument(
        "--xsl",
        dest="xsl_path",
        default=None,
        help="Optional custom XSLT stylesheet path. By default, a stylesheet "
        "shipped inside the source XDM package (HTML/STYLE/*.xsl) is used when "
        "present; otherwise the bundled cda-default.xsl is used.",
    )
    parser.add_argument(
        "--no-coded-entries",
        action="store_true",
        help="Omit the appended XML Header & Coded Clinical Entries Metadata tables at the end of each document.",
    )
    parser.add_argument(
        "--no-cover",
        action="store_true",
        help="Omit the Package Index / METADATA.XML / README.TXT cover section.",
    )
    parser.add_argument(
        "--keep-html",
        dest="keep_html_dir",
        default=None,
        help="Optional directory path to save intermediate generated HTML and per-part PDF files.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        converter = CDAPackageConverter(
            inputs=args.inputs,
            output_pdf=args.output_pdf,
            xsl_path=args.xsl_path,
            include_coded_entries=not args.no_coded_entries,
            include_cover=not args.no_cover,
            keep_html_dir=args.keep_html_dir,
        )
        result = converter.convert()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    size_kb = os.path.getsize(result.output_pdf) / 1024.0 if os.path.exists(result.output_pdf) else 0.0
    dob_str = f" (DOB: {result.patient_dob})" if result.patient_dob else ""
    print(f"Patient:    {result.patient_name}{dob_str}")
    print(f"Source:     {result.source_label} ({result.documents_count} CDA document(s))")
    print(f"Output PDF: {result.output_pdf} ({result.total_pages} pages, {size_kb:.1f} KB)")
    if result.parts:
        print("\nPage Breakdown:")
        for part in result.parts:
            s_pg = part.get("start_page")
            e_pg = part.get("end_page")
            cnt = part.get("page_count")
            lbl = part.get("bookmark_label") or part.get("short_label")
            print(f"  Pages {s_pg:>3} - {e_pg:<3} ({cnt:>2} pp): {lbl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
