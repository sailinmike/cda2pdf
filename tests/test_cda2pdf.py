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

"""Automated tests for the cda2pdf package.

These tests run against a synthetic CDA fixture (tests/fixtures/sample_cda.xml)
that contains no protected health information. No real patient data is required
to run the suite.

To additionally exercise the full IHE XDM package path against a real export,
set CDA2PDF_TEST_XDM to the path of an XDM directory or .zip. Those tests are
skipped when the variable is unset, and they assert only on structure -- never
on patient identifiers.
"""

import os
import shutil
import sys
import tempfile
import unittest

from cda2pdf import convert_cda_to_pdf, is_cda_xml, parse_cda_xml

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SAMPLE_CDA = os.path.join(FIXTURE_DIR, "sample_cda.xml")

# Optional: point at a real XDM export to exercise the package code path.
SAMPLE_XDM = os.environ.get("CDA2PDF_TEST_XDM", "")

requires_macos = unittest.skipUnless(
    sys.platform == "darwin", "PDF rendering requires macOS (WebKit + PDFKit)"
)
requires_xsltproc = unittest.skipUnless(
    shutil.which("xsltproc") is not None, "xsltproc not available on PATH"
)


class TestCDAParsing(unittest.TestCase):
    """Parser tests -- no PDF rendering, so these run on any platform."""

    def test_fixture_is_recognized_as_cda(self):
        self.assertTrue(is_cda_xml(SAMPLE_CDA))

    def test_non_cda_xml_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "not_cda.xml")
            with open(path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0"?><foo><bar>hi</bar></foo>')
            self.assertFalse(is_cda_xml(path))

    def test_parse_demographics(self):
        parsed = parse_cda_xml(SAMPLE_CDA, base_dir=FIXTURE_DIR)
        self.assertEqual(parsed.demographics.name, "Test Q Patient")
        self.assertEqual(parsed.demographics.dob, "07/04/1980")
        self.assertEqual(parsed.title, "Patient Health Summary")

    def test_parse_coded_entries(self):
        parsed = parse_cda_xml(SAMPLE_CDA, base_dir=FIXTURE_DIR)
        # The fixture declares 6 <entry> elements across 4 sections:
        # 1 allergy, 2 medications, 2 problems, 1 vital-signs organizer.
        self.assertEqual(len(parsed.entry_rows), 6)
        all_codes = " ".join(str(r["codes"]) for r in parsed.entry_rows)
        self.assertIn("RxNorm", all_codes)
        self.assertIn("314076", all_codes)  # Lisinopril

    def test_parse_header_rows(self):
        parsed = parse_cda_xml(SAMPLE_CDA, base_dir=FIXTURE_DIR)
        self.assertTrue(parsed.header_rows)


@requires_macos
@requires_xsltproc
class TestConversion(unittest.TestCase):
    """End-to-end conversion tests. Require macOS for WebKit/PDFKit rendering."""

    def test_convert_single_cda_to_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_pdf = os.path.join(tmp, "out.pdf")
            res = convert_cda_to_pdf(SAMPLE_CDA, output_pdf=out_pdf)
            self.assertTrue(os.path.isfile(res.output_pdf))
            self.assertEqual(res.documents_count, 1)
            self.assertGreater(res.total_pages, 0)
            self.assertEqual(res.patient_name, "Test Q Patient")
            with open(res.output_pdf, "rb") as f:
                self.assertEqual(f.read(5), b"%PDF-")

    def test_coded_entries_flag_changes_page_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            with_entries = convert_cda_to_pdf(
                SAMPLE_CDA,
                output_pdf=os.path.join(tmp, "with.pdf"),
                include_coded_entries=True,
            )
            without_entries = convert_cda_to_pdf(
                SAMPLE_CDA,
                output_pdf=os.path.join(tmp, "without.pdf"),
                include_coded_entries=False,
            )
            self.assertGreaterEqual(with_entries.total_pages, without_entries.total_pages)

    def test_multiple_inputs_are_merged_and_bookmarked(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_a = os.path.join(tmp, "doc_a.xml")
            copy_b = os.path.join(tmp, "doc_b.xml")
            shutil.copyfile(SAMPLE_CDA, copy_a)
            shutil.copyfile(SAMPLE_CDA, copy_b)
            out_pdf = os.path.join(tmp, "merged.pdf")
            res = convert_cda_to_pdf([copy_a, copy_b], output_pdf=out_pdf)
            self.assertTrue(os.path.isfile(res.output_pdf))
            self.assertEqual(res.documents_count, 2)
            # One part per document, plus the package index cover part.
            self.assertGreaterEqual(len(res.parts), 2)

    def test_missing_input_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                convert_cda_to_pdf(
                    os.path.join(tmp, "does_not_exist.xml"),
                    output_pdf=os.path.join(tmp, "out.pdf"),
                )


@unittest.skipUnless(SAMPLE_XDM, "Set CDA2PDF_TEST_XDM to run XDM package tests")
@requires_macos
@requires_xsltproc
class TestXDMPackage(unittest.TestCase):
    """Optional tests against a real XDM export. Structure assertions only."""

    def test_convert_xdm_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_pdf = os.path.join(tmp, "xdm.pdf")
            res = convert_cda_to_pdf(SAMPLE_XDM, output_pdf=out_pdf)
            self.assertTrue(os.path.isfile(res.output_pdf))
            self.assertGreater(res.documents_count, 0)
            self.assertGreater(res.total_pages, 0)
            self.assertTrue(res.patient_name)
            # Every document should contribute a bookmarked part.
            self.assertGreaterEqual(len(res.parts), res.documents_count)
            for part in res.parts:
                self.assertLessEqual(part["start_page"], part["end_page"])


if __name__ == "__main__":
    unittest.main()
