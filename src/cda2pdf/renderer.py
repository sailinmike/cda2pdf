# Copyright (C) 2026 Mint Medical PLLC
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

"""Native macOS WebKit + PDFKit rendering wrapper for cda2pdf."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
NATIVE_DIR = os.path.join(PACKAGE_DIR, "native")
OBJC_SOURCE = os.path.join(NATIVE_DIR, "mac_pdf_renderer.m")
DEFAULT_BIN_PATH = os.path.join(NATIVE_DIR, "cda2pdf_mac_renderer")


def ensure_native_renderer() -> str:
    """Ensure the macOS WebKit + PDFKit Objective-C binary is compiled and return its path."""
    bin_path = DEFAULT_BIN_PATH
    need_compile = False

    if not os.path.exists(bin_path) or not os.access(bin_path, os.X_OK):
        need_compile = True
    elif os.path.exists(OBJC_SOURCE) and os.path.getmtime(OBJC_SOURCE) > os.path.getmtime(bin_path):
        need_compile = True

    if not need_compile:
        return bin_path

    # Try compiling inside package native directory; fall back to ~/.cache/cda2pdf if read-only
    target_bin = bin_path
    if not os.access(NATIVE_DIR, os.W_OK):
        cache_dir = os.path.expanduser("~/.cache/cda2pdf")
        os.makedirs(cache_dir, exist_ok=True)
        target_bin = os.path.join(cache_dir, "cda2pdf_mac_renderer")
        if (
            os.path.exists(target_bin)
            and os.access(target_bin, os.X_OK)
            and os.path.getmtime(target_bin) >= os.path.getmtime(OBJC_SOURCE)
        ):
            return target_bin

    cmd = [
        "clang",
        "-fobjc-arc",
        # macOS 11 is the floor: WKWebView's paginated print support
        # (-printOperationWithPrintInfo:) was introduced there.
        "-mmacosx-version-min=11.0",
        "-framework",
        "Cocoa",
        "-framework",
        "WebKit",
        "-framework",
        "PDFKit",
        OBJC_SOURCE,
        "-o",
        target_bin,
    ]
    subprocess.run(cmd, check=True)
    return target_bin


def render_pdf_manifest(
    output_pdf: str,
    parts: List[Dict[str, str]],
    footer_prefix: str,
    title: str,
    author: str,
    subject: str,
    work_dir: str,
) -> Dict[str, Any]:
    """Render HTML parts to PDF, stamp footers, add PDFOutline bookmarks, and return summary dict."""
    bin_path = ensure_native_renderer()
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)

    temp_merged_pdf = os.path.join(work_dir, "_merged_stamped.pdf")
    manifest_path = os.path.join(work_dir, "_render_manifest.json")
    result_path = os.path.join(work_dir, "_render_result.json")

    manifest_data = {
        "output_pdf": os.path.abspath(output_pdf),
        "temp_merged_pdf": os.path.abspath(temp_merged_pdf),
        "footer_prefix": footer_prefix,
        "title": title,
        "author": author,
        "subject": subject,
        "parts": parts,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    subprocess.run([bin_path, manifest_path, result_path], check=True)

    if os.path.exists(result_path):
        with open(result_path, encoding="utf-8") as f:
            return json.load(f)

    return {
        "output_pdf": os.path.abspath(output_pdf),
        "total_pages": 0,
        "parts": [],
    }
