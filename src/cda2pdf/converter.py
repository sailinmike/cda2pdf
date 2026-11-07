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

"""Core conversion pipeline for turning HL7 CDA R2 files and IHE XDM packages into PDF."""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
from bs4 import BeautifulSoup

from .parser import (
    CDADocumentParsed,
    IndexHtmParsed,
    PatientDemographics,
    fmt_hl7_date_us,
    fmt_hl7_ts,
    is_cda_xml,
    parse_cda_xml,
    parse_index_htm,
    parse_metadata_xml,
)
from .renderer import render_pdf_manifest

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# Default CDA R2 stylesheet shipped with cda2pdf. This is an original,
# clean-room implementation (AGPL-3.0-or-later); no vendor stylesheet is
# redistributed with this package. When a source XDM package supplies its own
# stylesheet under HTML/STYLE/, that one is preferred -- see _discover_inputs().
BUNDLED_XSL = os.path.join(PACKAGE_DIR, "assets", "STYLE", "cda-default.xsl")

# Vendor-supplied images (logos, banners) are never bundled; they are resolved
# only from the user's own XDM package when present.
BUNDLED_IMAGES_DIR = os.path.join(PACKAGE_DIR, "assets", "IMAGES")

CUSTOM_CSS = """
<style type="text/css">
  html, body, #document {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    height: auto !important;
    -webkit-print-color-adjust: exact !important;
    font-family: 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  }
  #DocBody {
    overflow: visible !important;
    height: auto !important;
  }
  .Section {
    position: relative !important;
    page-break-inside: auto !important;
    padding: 0px 4px 8px 4px !important;
    margin-bottom: 4px !important;
  }
  .sectionHead {
    page-break-after: avoid !important;
    page-break-inside: avoid !important;
  }
  tr, .Item, .ListRow {
    page-break-inside: avoid !important;
  }
  thead {
    display: table-header-group !important;
  }
  .CE-Default .HeadCard, .CE-Default .sectionBody, .CE-Default .ShowAll {
    box-shadow: none !important;
    -webkit-box-shadow: none !important;
    border-top: 1px solid #D0D7DE !important;
    border-right: 1px solid #D0D7DE !important;
    border-bottom: 1px solid #D0D7DE !important;
  }
  .CE-Default .HeadCard {
    border-left: 1px solid #D0D7DE !important;
    padding: 8px 12px !important;
    margin-bottom: 6px !important;
  }
  /* Remove dashed hover-tooltip underlines that look like artifacts in PDF */
  table.provenanceTooltip > tbody span,
  tr.provenanceTooltip > td span,
  span.provenanceTooltip,
  .provenanceTooltip:not(table):not(tr) span,
  .provenanceTooltip {
    text-decoration: none !important;
    border-bottom: none !important;
  }
  /* Ensure nothing is truncated or hidden */
  .truncated {
    overflow: visible !important;
    max-height: none !important;
  }
  .truncatedHidden {
    display: block !important;
  }
  .loadSectionButton, .gradient, #tocHead, .screenOnly {
    display: none !important;
  }
  /* Hide duplicate screen-reader-only text */
  .SRonly, .SRonlyCaption, tr.SRonly {
    display: none !important;
  }
  img.logo {
    max-height: 55px !important;
    width: auto !important;
  }
  .docBanner {
    background: #1B365D;
    color: #FFFFFF;
    padding: 10px 14px;
    margin: 0 4px 8px 4px;
    border-radius: 4px;
  }
  .docBanner h1 {
    font-size: 13pt !important;
    line-height: 16pt !important;
    font-weight: bold !important;
    color: #FFFFFF !important;
    margin: 0 0 4px 0 !important;
  }
  .docBanner .docSub {
    font-size: 9pt !important;
    line-height: 13pt !important;
    color: #E2E8F0 !important;
  }
  .metaTable {
    width: 100%;
    border-collapse: collapse;
    font-size: 8.5pt !important;
    line-height: 11.5pt !important;
    margin: 4px 0 8px 0;
  }
  .metaTable th {
    background: #F1F5F9;
    color: #1E293B !important;
    font-weight: bold !important;
    padding: 4px 6px !important;
    border: 1px solid #CBD5E1 !important;
    text-align: left;
  }
  .metaTable td {
    padding: 4px 6px !important;
    border: 1px solid #CBD5E1 !important;
    vertical-align: top;
    word-break: break-word;
    color: #0F172A;
  }
  .metaTable tr:nth-child(even) td {
    background: #F8FAFC;
  }
  pre.readmePre {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 8.5pt;
    line-height: 12pt;
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    padding: 10px;
    white-space: pre-wrap;
    word-wrap: break-word;
    margin: 6px 0;
  }
</style>
"""


@dataclass
class ConversionResult:
    """Result summary returned after converting CDA files / XDM package to PDF."""

    output_pdf: str
    total_pages: int
    patient_name: str
    patient_dob: str
    source_label: str
    documents_count: int
    parts: List[Dict[str, Any]] = field(default_factory=list)


def _find_case_insensitive(directory: str, target_name: str) -> Optional[str]:
    """Find a file in directory matching target_name case-insensitively."""
    target_lower = target_name.lower()
    try:
        for entry in os.listdir(directory):
            if entry.lower() == target_lower:
                full = os.path.join(directory, entry)
                if os.path.isfile(full):
                    return full
    except OSError:
        pass
    return None


def _natural_sort_key(path: str) -> List[Any]:
    name = os.path.basename(path)
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", name)]


class CDAPackageConverter:
    """Converts an IHE XDM directory, ZIP archive, or standalone CDA XML files into a single PDF."""

    def __init__(
        self,
        inputs: Union[str, Path, Sequence[Union[str, Path]]],
        output_pdf: Optional[Union[str, Path]] = None,
        xsl_path: Optional[Union[str, Path]] = None,
        include_coded_entries: bool = True,
        include_cover: bool = True,
        keep_html_dir: Optional[Union[str, Path]] = None,
    ):
        if isinstance(inputs, (str, Path)):
            self.inputs = [str(inputs)]
        else:
            self.inputs = [str(x) for x in inputs]
        self.output_pdf = str(output_pdf) if output_pdf else None
        self.custom_xsl_path = str(xsl_path) if xsl_path else None
        self.include_coded_entries = include_coded_entries
        self.include_cover = include_cover
        self.keep_html_dir = str(keep_html_dir) if keep_html_dir else None

    def _discover_inputs(self, temp_extract_root: str):
        """Resolve inputs (directories, .zip archives, or .xml files) into package structure."""
        base_dir: Optional[str] = None
        source_label = "CDA_Package"
        index_htm_path: Optional[str] = None
        readme_txt_path: Optional[str] = None
        metadata_xml_path: Optional[str] = None
        package_images_dir: Optional[str] = None
        discovered_xsl: Optional[str] = self.custom_xsl_path
        cda_files: List[str] = []

        # Single input that is a .zip or a directory
        if len(self.inputs) == 1 and os.path.isfile(self.inputs[0]) and self.inputs[0].lower().endswith(".zip"):
            zip_path = os.path.abspath(self.inputs[0])
            source_label = os.path.splitext(os.path.basename(zip_path))[0]
            extract_dir = os.path.join(temp_extract_root, "unzipped")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            # If the zip had a single top-level directory, descend into it
            entries = [e for e in os.listdir(extract_dir) if not e.startswith(".")]
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                base_dir = os.path.join(extract_dir, entries[0])
            else:
                base_dir = extract_dir
        elif len(self.inputs) == 1 and os.path.isdir(self.inputs[0]):
            base_dir = os.path.abspath(self.inputs[0].rstrip("/\\"))
            source_label = os.path.basename(base_dir)

        if base_dir:
            index_htm_path = _find_case_insensitive(base_dir, "INDEX.HTM") or _find_case_insensitive(
                base_dir, "INDEX.HTML"
            )
            readme_txt_path = _find_case_insensitive(base_dir, "README.TXT")

            # Check for HTML/STYLE and HTML/IMAGES
            html_dir = _find_case_insensitive(base_dir, "HTML")
            if html_dir is None and os.path.isdir(os.path.join(base_dir, "HTML")):
                html_dir = os.path.join(base_dir, "HTML")
            if html_dir and os.path.isdir(html_dir):
                style_dir = os.path.join(html_dir, "STYLE")
                if os.path.isdir(style_dir) and not discovered_xsl:
                    xsl_candidate = _find_case_insensitive(style_dir, "CECDocDisplay.xsl")
                    if not xsl_candidate:
                        for f in os.listdir(style_dir):
                            if f.lower().endswith(".xsl"):
                                xsl_candidate = os.path.join(style_dir, f)
                                break
                    discovered_xsl = xsl_candidate
                img_dir = os.path.join(html_dir, "IMAGES")
                if os.path.isdir(img_dir):
                    package_images_dir = img_dir

            # Walk base_dir for METADATA.XML and CDA XML files
            all_xmls: List[str] = []
            for root_dir, _, files in os.walk(base_dir):
                for fn in files:
                    full_p = os.path.join(root_dir, fn)
                    if fn.upper() == "METADATA.XML":
                        if metadata_xml_path is None:
                            metadata_xml_path = full_p
                    elif fn.lower().endswith(".xml"):
                        if is_cda_xml(full_p):
                            all_xmls.append(full_p)
            cda_files = sorted(all_xmls, key=_natural_sort_key)
        else:
            # Multiple inputs or standalone XML file(s)
            for inp in self.inputs:
                abs_inp = os.path.abspath(inp)
                if os.path.isdir(abs_inp):
                    for root_dir, _, files in os.walk(abs_inp):
                        for fn in files:
                            full_p = os.path.join(root_dir, fn)
                            if fn.lower().endswith(".xml") and is_cda_xml(full_p):
                                cda_files.append(full_p)
                elif os.path.isfile(abs_inp) and is_cda_xml(abs_inp):
                    cda_files.append(abs_inp)
            if len(cda_files) == 1:
                source_label = os.path.splitext(os.path.basename(cda_files[0]))[0]
                parent_dir = os.path.dirname(cda_files[0])
                # Check if parent or grandparent has HTML/STYLE/CECDocDisplay.xsl
                for cand_base in (parent_dir, os.path.dirname(parent_dir), os.path.dirname(os.path.dirname(parent_dir))):
                    cand_xsl = os.path.join(cand_base, "HTML", "STYLE", "CECDocDisplay.xsl")
                    if os.path.isfile(cand_xsl) and not discovered_xsl:
                        discovered_xsl = cand_xsl
                    cand_img = os.path.join(cand_base, "HTML", "IMAGES")
                    if os.path.isdir(cand_img) and not package_images_dir:
                        package_images_dir = cand_img

        if not cda_files:
            raise ValueError(f"No HL7 CDA R2 (<ClinicalDocument>) XML files found in {self.inputs}")

        if not discovered_xsl or not os.path.isfile(discovered_xsl):
            discovered_xsl = BUNDLED_XSL

        return (
            base_dir,
            source_label,
            index_htm_path,
            readme_txt_path,
            metadata_xml_path,
            package_images_dir,
            discovered_xsl,
            cda_files,
        )

    def _resolve_image_url(self, img_filename: str, package_images_dir: Optional[str]) -> Optional[str]:
        """Return file:// URL for an image in package_images_dir or bundled assets, or None if unavailable."""
        if package_images_dir:
            cand = os.path.join(package_images_dir, img_filename)
            if os.path.isfile(cand):
                return Path(cand).as_uri()
        bundled_cand = os.path.join(BUNDLED_IMAGES_DIR, img_filename)
        if os.path.isfile(bundled_cand):
            return Path(bundled_cand).as_uri()
        return None

    def convert(self) -> ConversionResult:
        """Execute the full CDA/XDM to PDF conversion pipeline."""
        with tempfile.TemporaryDirectory(prefix="cda2pdf_") as temp_root:
            work_dir = os.path.abspath(self.keep_html_dir) if self.keep_html_dir else os.path.join(temp_root, "work")
            os.makedirs(work_dir, exist_ok=True)

            (
                base_dir,
                source_label,
                index_htm_path,
                readme_txt_path,
                metadata_xml_path,
                package_images_dir,
                xsl_path,
                cda_files,
            ) = self._discover_inputs(temp_root)

            # Parse optional METADATA.XML, INDEX.HTM, README.TXT
            pkg_info, ext_objs, assocs = ([], [], [])
            if metadata_xml_path and os.path.isfile(metadata_xml_path):
                pkg_info, ext_objs, assocs = parse_metadata_xml(metadata_xml_path)

            index_info = parse_index_htm(index_htm_path) if index_htm_path else IndexHtmParsed()
            readme_text = ""
            if readme_txt_path and os.path.isfile(readme_txt_path):
                with open(readme_txt_path, encoding="utf-8", errors="replace") as rf:
                    readme_text = rf.read()

            # Parse and transform each CDA XML file
            parsed_docs: List[CDADocumentParsed] = []
            manifest_parts: List[Dict[str, str]] = []
            total_docs = len(cda_files)

            for idx, xml_path in enumerate(cda_files, 1):
                parsed = parse_cda_xml(xml_path, base_dir=base_dir)
                parsed_docs.append(parsed)

                raw_html_path = os.path.join(work_dir, f"raw_doc{idx}.html")
                full_html_path = os.path.join(work_dir, f"doc{idx}_full.html")
                part_pdf_path = os.path.join(work_dir, f"part{idx}.pdf")

                with open(raw_html_path, "w", encoding="utf-8") as out_f:
                    subprocess.run(["xsltproc", xsl_path, xml_path], stdout=out_f, check=True)

                with open(raw_html_path, encoding="utf-8", errors="replace") as in_f:
                    soup = BeautifulSoup(in_f.read(), "html.parser")

                # Remove duplicate screen-reader-only elements
                for sr in soup.select(".SRonly, .SRonlyCaption, tr.SRonly"):
                    sr.decompose()

                # Fix or remove image paths
                for img in soup.find_all("img"):
                    src = img.get("src", "")
                    if "HTML/IMAGES/" in src:
                        img_file = src.split("HTML/IMAGES/")[-1]
                        resolved_uri = self._resolve_image_url(img_file, package_images_dir)
                        if resolved_uri:
                            img["src"] = resolved_uri
                        else:
                            img.decompose()

                if soup.head:
                    soup.head.append(BeautifulSoup(CUSTOM_CSS, "html.parser"))

                # Build top document banner
                pat_name = parsed.demographics.name
                pat_dob = parsed.demographics.dob
                pat_display = f"{pat_name} (DOB: {pat_dob})" if pat_dob else pat_name

                wrapper = soup.find(id="DocWrapper")
                banner_html = f"""
                <div class="docBanner">
                  <h1>Document {idx} of {total_docs}: {html.escape(parsed.rel_path)} — {html.escape(parsed.title)}</h1>
                  <div class="docSub">
                    <b>Patient:</b> {html.escape(pat_display)} &nbsp;|&nbsp;
                    <b>Generated:</b> {html.escape(parsed.effective_time_fmt)} &nbsp;|&nbsp;
                    <b>Context:</b> {html.escape(parsed.encounter_summary)}
                  </div>
                </div>
                """
                if wrapper:
                    wrapper.insert(0, BeautifulSoup(banner_html, "html.parser"))

                # Append Structured XML Header & Coded Entry Metadata section
                doc_body = soup.find(id="DocBody")
                if doc_body and self.include_coded_entries:
                    hdr_trs = "".join(
                        f"<tr><td style='width:28%;font-weight:bold;'>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>"
                        for k, v in parsed.header_rows
                    )
                    entry_trs = "".join(
                        f"<tr>"
                        f"<td>{html.escape(str(r['section']))} (#{r['idx']})</td>"
                        f"<td>{html.escape(str(r['id']))}</td>"
                        f"<td>{html.escape(str(r['ref']))}</td>"
                        f"<td>{html.escape(str(r['codes']))}</td>"
                        f"<td>{html.escape(str(r['vals']))}</td>"
                        f"<td>{html.escape(str(r['times_authors']))}</td>"
                        f"</tr>"
                        for r in parsed.entry_rows
                    )
                    extra_sec_html = f"""
                    <div class="Section XSLadded">
                      <div class="sectionBody pgContent bodyE E">
                        <div class="sectionHead headE">
                          <h2>XML Header &amp; Coded Clinical Entries Metadata ({html.escape(parsed.xml_name)})</h2>
                        </div>
                        <div style="padding: 6px;">
                          <div style="font-weight:bold; margin-bottom:4px;">CDA XML Header Attributes</div>
                          <table class="metaTable">
                            <thead><tr><th>Header Field</th><th>Value</th></tr></thead>
                            <tbody>{hdr_trs}</tbody>
                          </table>
                          <div style="font-weight:bold; margin:8px 0 4px 0;">Structured Section Entries ({len(parsed.entry_rows)} Coded Entries in {html.escape(parsed.xml_name)})</div>
                          <table class="metaTable">
                            <thead>
                              <tr>
                                <th style="width:16%;">Section</th>
                                <th style="width:11%;">Entry ID</th>
                                <th style="width:23%;">Narrative Reference / Text</th>
                                <th style="width:22%;">Clinical Codes (RxNorm / NDC / SNOMED / LOINC / CPT)</th>
                                <th style="width:12%;">Value / Qty</th>
                                <th style="width:16%;">Effective Time &amp; Author Provenance</th>
                              </tr>
                            </thead>
                            <tbody>{entry_trs}</tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                    """
                    doc_body.append(BeautifulSoup(extra_sec_html, "html.parser"))

                with open(full_html_path, "w", encoding="utf-8") as out_f:
                    out_f.write(str(soup))

                # Build concise footer & bookmark labels
                eff_date_us = fmt_hl7_date_us(parsed.effective_time_raw)
                short_label = f"Doc {idx}: {parsed.xml_name} ({parsed.title})"
                if parsed.encounter_summary != "None (Summary Document)":
                    bookmark_label = f"Document {idx} ({parsed.xml_name}) — {parsed.title}: {parsed.encounter_summary}"
                elif eff_date_us:
                    bookmark_label = f"Document {idx} ({parsed.xml_name}) — {parsed.title} ({eff_date_us})"
                else:
                    bookmark_label = f"Document {idx} ({parsed.xml_name}) — {parsed.title}"

                manifest_parts.append(
                    {
                        "html": full_html_path,
                        "pdf": part_pdf_path,
                        "short_label": short_label,
                        "bookmark_label": bookmark_label,
                    }
                )

            # Determine overall patient demographics from first document
            primary_demo = parsed_docs[0].demographics if parsed_docs else PatientDemographics()
            patient_name = primary_demo.name
            patient_dob = primary_demo.dob
            patient_display = f"{patient_name} (DOB: {patient_dob})" if patient_dob else patient_name

            created_by_org = (
                index_info.created_by.replace("Created by ", "").strip()
                or primary_demo.created_by
                or primary_demo.organization
                or "Clinical Document Source"
            )
            org_and_device = created_by_org
            if primary_demo.organization and primary_demo.organization not in org_and_device:
                org_and_device += f" ({primary_demo.organization}"
                if primary_demo.author_device:
                    org_and_device += f" / {primary_demo.author_device}"
                org_and_device += ")"
            elif primary_demo.author_device:
                org_and_device += f" ({primary_demo.author_device})"

            current_as_of = (
                index_info.current_as_of.replace("Current as of ", "").strip()
                or primary_demo.current_as_of
            )

            # Build Cover / Package Index & Metadata part0.html if requested
            if self.include_cover and (index_htm_path or metadata_xml_path or readme_txt_path or len(parsed_docs) > 1):
                part0_html_path = os.path.join(work_dir, "part0.html")
                part0_pdf_path = os.path.join(work_dir, "part0.pdf")
                self._build_cover_html(
                    part0_html_path=part0_html_path,
                    source_label=source_label,
                    patient_display=patient_display,
                    patient_name=patient_name,
                    created_by_org=created_by_org,
                    org_and_device=org_and_device,
                    current_as_of=current_as_of,
                    index_info=index_info,
                    parsed_docs=parsed_docs,
                    pkg_info=pkg_info,
                    ext_objs=ext_objs,
                    assocs=assocs,
                    readme_text=readme_text,
                    package_images_dir=package_images_dir,
                )
                cover_short = (
                    "Package Index, METADATA.XML & README.TXT"
                    if metadata_xml_path
                    else "Clinical Document Package Index & Summary"
                )
                cover_bookmark = (
                    "Package Index (INDEX.HTM), Registry Metadata (METADATA.XML) & README.TXT"
                    if metadata_xml_path
                    else "Clinical Document Package Index & Summary"
                )
                manifest_parts.insert(
                    0,
                    {
                        "html": part0_html_path,
                        "pdf": part0_pdf_path,
                        "short_label": cover_short,
                        "bookmark_label": cover_bookmark,
                    },
                )

            # Determine default output PDF path if not explicitly specified
            if not self.output_pdf:
                safe_pat = re.sub(r"[^A-Za-z0-9]+", "_", patient_name).strip("_")
                safe_src = re.sub(r"[^A-Za-z0-9_-]+", "_", source_label).strip("_")
                self.output_pdf = os.path.abspath(f"{safe_pat}_{safe_src}.pdf")
            else:
                self.output_pdf = os.path.abspath(self.output_pdf)

            footer_prefix = f"{patient_display} — {source_label}"
            pdf_title = f"Clinical Documents For {patient_name} ({source_label})"
            pdf_author = org_and_device
            pdf_subject = f"Complete HL7 CDA / IHE XDM Clinical Document Extraction ({len(parsed_docs)} Document(s))"

            render_res = render_pdf_manifest(
                output_pdf=self.output_pdf,
                parts=manifest_parts,
                footer_prefix=footer_prefix,
                title=pdf_title,
                author=pdf_author,
                subject=pdf_subject,
                work_dir=work_dir,
            )

            return ConversionResult(
                output_pdf=self.output_pdf,
                total_pages=int(render_res.get("total_pages", 0)),
                patient_name=patient_name,
                patient_dob=patient_dob,
                source_label=source_label,
                documents_count=len(parsed_docs),
                parts=render_res.get("parts", []),
            )

    def _build_cover_html(
        self,
        part0_html_path: str,
        source_label: str,
        patient_display: str,
        patient_name: str,
        created_by_org: str,
        org_and_device: str,
        current_as_of: str,
        index_info: IndexHtmParsed,
        parsed_docs: List[CDADocumentParsed],
        pkg_info: List[Tuple[str, str]],
        ext_objs: List[Dict[str, object]],
        assocs: List[str],
        readme_text: str,
        package_images_dir: Optional[str],
    ) -> None:
        # These logos are resolved only from the user's own XDM package;
        # none are bundled with cda2pdf. Each resolves to None when absent.
        cec_logo = self._resolve_image_url("CEC_logo.gif", package_images_dir)
        docs_icon = self._resolve_image_url("Docs.png", package_images_dir)
        org_logo = self._resolve_image_url("org.png", package_images_dir)

        # Match ExtrinsicObject by URI suffix if present
        eo_by_name: Dict[str, Dict[str, object]] = {}
        for eo in ext_objs:
            slots = eo.get("slots", {})
            if isinstance(slots, dict):
                uris = slots.get("URI", [])
                for u in uris:
                    bn = os.path.basename(u.replace("\\", "/"))
                    eo_by_name[bn.upper()] = eo

        toc_rows = ""
        for idx, d in enumerate(parsed_docs, 1):
            eo = eo_by_name.get(d.xml_name.upper())
            if eo is None and idx - 1 < len(ext_objs):
                eo = ext_objs[idx - 1]
            slots = eo.get("slots", {}) if isinstance(eo, dict) else {}
            eo_name = str(eo.get("name", "")) if isinstance(eo, dict) else ""
            size_v = ", ".join(slots.get("size", [])) if isinstance(slots, dict) else ""
            hash_v = ", ".join(slots.get("hash", [])) if isinstance(slots, dict) else ""
            ctime_v = ", ".join(slots.get("creationTime", [])) if isinstance(slots, dict) else ""

            if not size_v and os.path.isfile(d.xml_path):
                size_v = str(os.path.getsize(d.xml_path))

            meta_name_html = (
                f"<br/><span style='color:#475569;'>Metadata Name: {html.escape(eo_name)}</span>"
                if eo_name
                else ""
            )
            ctime_html = (
                f"<br/><span style='color:#475569;'>UTC Creation: {html.escape(ctime_v)}</span>"
                if ctime_v
                else ""
            )
            hash_html = f"<br/><code>SHA1: {html.escape(hash_v)}</code>" if hash_v else ""

            toc_rows += f"""
            <tr>
              <td style="font-weight:bold;">Document {idx}<br/><code>{html.escape(d.rel_path)}</code></td>
              <td><b>{html.escape(d.title)}</b>{meta_name_html}</td>
              <td>{html.escape(d.encounter_summary)}</td>
              <td>{html.escape(d.effective_time_fmt)}{ctime_html}</td>
              <td>{html.escape(size_v)} bytes{hash_html}<br/>{len(d.entry_rows)} coded entries</td>
            </tr>
            """

        logos_html = ""
        if cec_logo:
            logos_html += f'<img src="{cec_logo}" alt="Source package logo" style="vertical-align:middle; max-height:40px; margin-right:12px;" />'
        if org_logo:
            logos_html += f'<img src="{org_logo}" alt="{html.escape(created_by_org)}" style="vertical-align:middle; max-height:42px;" />'

        docs_icon_html = (
            f'<img src="{docs_icon}" alt="Clinical Document Library" style="vertical-align:middle; width:24px; height:24px; margin-right:6px;" />'
            if docs_icon
            else ""
        )

        intro_p = (
            index_info.intro_text
            or "These files are a portable copy of the clinical information created by clinicians and organizations that provide the patient with medical care."
        )
        pkg_path_line = ""
        if index_info.package_path or index_info.copyright_text:
            parts_line = []
            if index_info.package_path:
                parts_line.append(f"<b>Package Path:</b> <code>{html.escape(index_info.package_path)}</code>")
            if index_info.copyright_text:
                parts_line.append(f"<b>Copyright:</b> {html.escape(index_info.copyright_text)}")
            pkg_path_line = "<br/>" + " &nbsp;|&nbsp; ".join(parts_line)

        metadata_section_html = ""
        if pkg_info or ext_objs:
            pkg_rows = "".join(
                f"<tr><td style='width:28%;font-weight:bold;'>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>"
                for k, v in pkg_info
            )
            eo_rows = ""
            for eo in ext_objs:
                slots = eo.get("slots", {}) if isinstance(eo, dict) else {}
                uri_v = ", ".join(slots.get("URI", []))
                pinfo_v = " | ".join(slots.get("sourcePatientInfo", []))
                slots_str = "; ".join(
                    f"{k}={', '.join(v)}" for k, v in slots.items() if k not in ("sourcePatientInfo",)
                )
                cls_str = " | ".join(eo.get("classifications", []))
                eids_str = " | ".join(eo.get("external_ids", []))
                eo_rows += f"""
                <tr>
                  <td style="font-weight:bold;">{html.escape(uri_v)}<br/><code>{html.escape(str(eo.get('id', '')))}</code></td>
                  <td>{html.escape(slots_str)}<br/><b>Patient Info (PID):</b> {html.escape(pinfo_v)}</td>
                  <td>{html.escape(cls_str)}</td>
                  <td>{html.escape(eids_str)}</td>
                </tr>
                """
            assoc_rows = "".join(f"<li><code>{html.escape(a)}</code></li>" for a in assocs)
            metadata_section_html = f"""
            <div style="border:1px solid #CBD5E1; border-radius:4px; padding:12px; margin: 0 4px 10px 4px; background:#FFFFFF;">
              <h2 style="font-size:12pt; font-weight:bold; color:#1B365D; margin:0 0 6px 0; border-bottom:1px solid #CBD5E1; padding-bottom:4px;">
                IHE XDM SubmissionSet &amp; Registry Metadata (METADATA.XML)
              </h2>
              <div style="font-weight:bold; font-size:9pt; margin:4px 0;">SubmissionSet (RegistryPackage) Attributes</div>
              <table class="metaTable">
                <thead><tr><th>Metadata Attribute</th><th>Value</th></tr></thead>
                <tbody>{pkg_rows}</tbody>
              </table>

              <div style="font-weight:bold; font-size:9pt; margin:8px 0 4px 0;">Document Registry Entries (ExtrinsicObjects)</div>
              <table class="metaTable">
                <thead>
                  <tr>
                    <th style="width:16%;">Document URI &amp; Entry ID</th>
                    <th style="width:34%;">Slots &amp; Source Patient Info (HL7 PID)</th>
                    <th style="width:32%;">Classifications (Author, Class, Confidentiality, Format, Facility, Practice Setting, Type)</th>
                    <th style="width:18%;">External Identifiers</th>
                  </tr>
                </thead>
                <tbody>{eo_rows}</tbody>
              </table>

              <div style="font-weight:bold; font-size:9pt; margin:8px 0 4px 0;">Registry Package HasMember Associations</div>
              <ul style="font-size:8pt; line-height:11pt; margin:0 0 0 18px; padding:0;">
                {assoc_rows}
              </ul>
            </div>
            """

        readme_section_html = ""
        if readme_text.strip():
            readme_section_html = f"""
            <div style="border:1px solid #CBD5E1; border-radius:4px; padding:12px; margin: 0 4px 10px 4px; background:#FFFFFF;">
              <h2 style="font-size:12pt; font-weight:bold; color:#1B365D; margin:0 0 6px 0; border-bottom:1px solid #CBD5E1; padding-bottom:4px;">
                Package Instructions &amp; Manifest (README.TXT)
              </h2>
              <pre class="readmePre">{html.escape(readme_text)}</pre>
            </div>
            """

        part0_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Clinical Documents For {html.escape(patient_name)} — Complete Record</title>
{CUSTOM_CSS}
</head>
<body id="document">
<div id="DocWrapper" class="CE-Default" style="padding: 6px;">
  <div class="docBanner">
    <h1>XDM / CDA Clinical Document Package — Complete Extracted Record</h1>
    <div class="docSub">
      <b>Source:</b> {html.escape(source_label)} &nbsp;|&nbsp;
      <b>Patient:</b> {html.escape(patient_display)} &nbsp;|&nbsp;
      <b>Created By:</b> {html.escape(org_and_device)} &nbsp;|&nbsp;
      <b>Current As Of:</b> {html.escape(current_as_of)}
    </div>
  </div>

  <div style="border:1px solid #CBD5E1; border-radius:4px; padding:12px; margin: 0 4px 10px 4px; background:#FFFFFF;">
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0CA99D; padding-bottom:8px; margin-bottom:10px;">
      <div>{logos_html}</div>
      <div style="text-align:right; font-size:10pt; font-weight:bold; color:#0E766E;">
        Created by {html.escape(created_by_org)}<br/>
        <span style="font-size:9pt; font-weight:normal; color:#334155;">Current as of {html.escape(current_as_of)}</span>
      </div>
    </div>

    <div style="margin-bottom:8px;">
      {docs_icon_html}
      <span style="font-size:13pt; font-weight:bold; color:#0E766E; vertical-align:middle;">Clinical Document Library — Documents for {html.escape(patient_name)}</span>
    </div>
    <p style="font-size:9pt; line-height:13pt; color:#1E293B; margin: 4px 0 8px 0;">
      {html.escape(intro_p)}
      {pkg_path_line}
    </p>

    <table class="metaTable">
      <thead>
        <tr>
          <th style="width:17%;">Document File</th>
          <th style="width:20%;">Document Title</th>
          <th style="width:25%;">Encounter / Clinical Context</th>
          <th style="width:18%;">Effective / Creation Time</th>
          <th style="width:20%;">Size, SHA-1 Hash &amp; Entries</th>
        </tr>
      </thead>
      <tbody>
        {toc_rows}
      </tbody>
    </table>
  </div>

  {metadata_section_html}
  {readme_section_html}
</div>
</body>
</html>
"""
        with open(part0_html_path, "w", encoding="utf-8") as f:
            f.write(part0_html)


def convert_cda_to_pdf(
    inputs: Union[str, Path, Sequence[Union[str, Path]]],
    output_pdf: Optional[Union[str, Path]] = None,
    xsl_path: Optional[Union[str, Path]] = None,
    include_coded_entries: bool = True,
    include_cover: bool = True,
    keep_html_dir: Optional[Union[str, Path]] = None,
) -> ConversionResult:
    """Convenience function to convert an XDM directory, .zip archive, or CDA XML file(s) to PDF."""
    converter = CDAPackageConverter(
        inputs=inputs,
        output_pdf=output_pdf,
        xsl_path=xsl_path,
        include_coded_entries=include_coded_entries,
        include_cover=include_cover,
        keep_html_dir=keep_html_dir,
    )
    return converter.convert()
