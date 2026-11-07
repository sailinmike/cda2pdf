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

"""XML and HTML parsing utilities for HL7 CDA R2 documents and IHE XDM packages."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

NS = {
    "hl7": "urn:hl7-org:v3",
    "sdtc": "urn:hl7-org:sdtc",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "lcm": "urn:oasis:names:tc:ebxml-regrep:xsd:lcm:3.0",
    "rim": "urn:oasis:names:tc:ebxml-regrep:xsd:rim:3.0",
}


@dataclass
class PatientDemographics:
    """Extracted patient and authoring metadata from CDA XML / XDM package."""

    name: str = "Unknown Patient"
    dob: str = ""
    gender: str = ""
    patient_ids: List[str] = field(default_factory=list)
    organization: str = ""
    author_device: str = ""
    created_by: str = ""
    current_as_of: str = ""


@dataclass
class CDADocumentParsed:
    """Parsed metadata and coded clinical entries from a single CDA R2 XML file."""

    xml_path: str
    xml_name: str
    rel_path: str
    title: str
    effective_time_raw: str
    effective_time_fmt: str
    encounter_summary: str
    demographics: PatientDemographics
    header_rows: List[Tuple[str, str]]
    entry_rows: List[Dict[str, object]]


@dataclass
class IndexHtmParsed:
    """Extracted fields from an IHE XDM INDEX.HTM file."""

    title: str = ""
    created_by: str = ""
    current_as_of: str = ""
    patient_heading: str = ""
    intro_text: str = ""
    package_path: str = ""
    copyright_text: str = ""


def fmt_hl7_ts(val: Optional[str]) -> str:
    """Format an HL7 timestamp string (e.g. 20261103103757-0800) into human-readable + raw."""
    if not val:
        return ""
    val = val.strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2})(\d{2})?)?([+-]\d{4})?$", val)
    if not m:
        return val
    y, mo, d, hh, mm, ss, tz = m.groups()
    res = f"{y}-{mo}-{d}"
    if hh and mm:
        res += f" {hh}:{mm}"
        if ss:
            res += f":{ss}"
    if tz:
        res += f" ({tz})"
    return f"{res} [raw: {val}]"


def fmt_hl7_date_us(val: Optional[str]) -> str:
    """Format YYYYMMDD into MM/DD/YYYY."""
    if not val:
        return ""
    val = val.strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", val)
    if not m:
        return val
    y, mo, d = m.groups()
    return f"{mo}/{d}/{y}"


def is_cda_xml(xml_path: str) -> bool:
    """Return True if xml_path is an HL7 CDA R2 ClinicalDocument XML file."""
    try:
        for _, elem in ET.iterparse(xml_path, events=("start",)):
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            return tag == "ClinicalDocument"
    except Exception:
        return False
    return False


def extract_patient_demographics(root: ET.Element) -> PatientDemographics:
    """Extract patient demographics and authoring system details from a ClinicalDocument root."""
    demo = PatientDemographics()

    # Patient Name (prefer Legal 'L' name if multiple exist)
    name_els = root.findall("hl7:recordTarget/hl7:patientRole/hl7:patient/hl7:name", NS)
    chosen_name = None
    for nel in name_els:
        if nel.get("use") == "L":
            chosen_name = nel
            break
    if chosen_name is None and name_els:
        chosen_name = name_els[0]

    if chosen_name is not None:
        givens = [g.text.strip() for g in chosen_name.findall("hl7:given", NS) if g.text and g.text.strip()]
        fam_el = chosen_name.find("hl7:family", NS)
        family = fam_el.text.strip() if fam_el is not None and fam_el.text else ""
        full_name = " ".join(givens + ([family] if family else [])).strip()
        if full_name:
            demo.name = full_name

    # Birth Time
    bt_el = root.find("hl7:recordTarget/hl7:patientRole/hl7:patient/hl7:birthTime", NS)
    if bt_el is not None and bt_el.get("value"):
        demo.dob = fmt_hl7_date_us(bt_el.get("value"))

    # Gender
    gen_el = root.find("hl7:recordTarget/hl7:patientRole/hl7:patient/hl7:administrativeGenderCode", NS)
    if gen_el is not None:
        demo.gender = gen_el.get("displayName") or gen_el.get("code") or ""

    # Patient IDs
    demo.patient_ids = [
        f"{e.get('extension', '')} (root={e.get('root', '')})"
        for e in root.findall("hl7:recordTarget/hl7:patientRole/hl7:id", NS)
        if e.get("extension") or e.get("root")
    ]

    # Organization & Device
    auth_org = root.findtext(
        "hl7:author/hl7:assignedAuthor/hl7:representedOrganization/hl7:name",
        default="",
        namespaces=NS,
    ).strip()
    prov_org = root.findtext(
        "hl7:recordTarget/hl7:patientRole/hl7:providerOrganization/hl7:name",
        default="",
        namespaces=NS,
    ).strip()
    cust_org = root.findtext(
        "hl7:custodian/hl7:assignedCustodian/hl7:representedCustodianOrganization/hl7:name",
        default="",
        namespaces=NS,
    ).strip()
    demo.organization = auth_org or prov_org or cust_org

    # Check if there is a "Note from <Organization>" section title
    for sec in root.findall(".//hl7:structuredBody/hl7:component/hl7:section", NS):
        sec_code = sec.find("hl7:code", NS)
        if sec_code is not None and sec_code.get("code") == "X-CE-PFD":
            disp = sec_code.get("displayName", "")
            if disp.lower().startswith("note from "):
                demo.created_by = disp[len("note from ") :].strip()
                break

    dev_name = root.findtext(
        "hl7:author/hl7:assignedAuthor/hl7:assignedAuthoringDevice/hl7:manufacturerModelName",
        default="",
        namespaces=NS,
    ).strip()
    demo.author_device = dev_name

    eff_el = root.find("hl7:effectiveTime", NS)
    if eff_el is not None and eff_el.get("value"):
        demo.current_as_of = fmt_hl7_date_us(eff_el.get("value"))

    return demo


def parse_cda_xml(xml_path: str, base_dir: Optional[str] = None) -> CDADocumentParsed:
    """Parse an HL7 CDA R2 XML file and extract header attributes and all structured entries."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    xml_name = os.path.basename(xml_path)
    rel_path = os.path.relpath(xml_path, base_dir) if base_dir else xml_name

    demographics = extract_patient_demographics(root)

    # Build ID -> text lookup from narrative <text> blocks
    id_map: Dict[str, str] = {}
    for el in root.findall(".//*[@ID]"):
        el_id = el.attrib.get("ID")
        txt = " ".join(el.itertext()).strip()
        if el_id and txt:
            id_map[f"#{el_id}"] = txt
            id_map[el_id] = txt

    # Header fields
    header_rows: List[Tuple[str, str]] = []
    doc_id = root.find("hl7:id", NS)
    if doc_id is not None:
        header_rows.append(
            (
                "Document ID",
                f"root={doc_id.get('root', '')} | assigningAuthorityName={doc_id.get('assigningAuthorityName', '')} | extension={doc_id.get('extension', '')}",
            )
        )

    code_el = root.find("hl7:code", NS)
    if code_el is not None:
        header_rows.append(
            (
                "Document Code",
                f"{code_el.get('code', '')} ({code_el.get('codeSystemName', '')} {code_el.get('codeSystem', '')}) — {code_el.get('displayName', '')}",
            )
        )

    title_txt = root.findtext("hl7:title", default="Clinical Document", namespaces=NS).strip()
    eff_el = root.find("hl7:effectiveTime", NS)
    eff_val = eff_el.get("value", "") if eff_el is not None else ""
    header_rows.append(("Title / Effective Time", f"{title_txt} | {fmt_hl7_ts(eff_val)}"))

    conf_el = root.find("hl7:confidentialityCode", NS)
    lang_el = root.find("hl7:languageCode", NS)
    set_el = root.find("hl7:setId", NS)
    ver_el = root.find("hl7:versionNumber", NS)
    header_rows.append(
        (
            "Set ID / Version / Confidentiality / Language",
            f"setId={set_el.get('extension', '') if set_el is not None else ''} (root={set_el.get('root', '') if set_el is not None else ''}) | "
            f"version={ver_el.get('value', '') if ver_el is not None else ''} | "
            f"confidentiality={conf_el.get('code', '') if conf_el is not None else ''} ({conf_el.get('displayName', '') if conf_el is not None else ''}) | "
            f"language={lang_el.get('code', '') if lang_el is not None else ''}",
        )
    )

    header_rows.append(("Record Target Patient ID(s)", "; ".join(demographics.patient_ids)))

    auth_time = root.find("hl7:author/hl7:time", NS)
    header_rows.append(
        (
            "Document Author / System",
            f"Device: {demographics.author_device} | Org: {demographics.organization} | Time: {fmt_hl7_ts(auth_time.get('value', '') if auth_time is not None else '')}",
        )
    )

    la_time = root.find("hl7:legalAuthenticator/hl7:time", NS)
    la_sig = root.find("hl7:legalAuthenticator/hl7:signatureCode", NS)
    la_id = root.find("hl7:legalAuthenticator/hl7:assignedEntity/hl7:id", NS)
    la_given = root.findtext(
        "hl7:legalAuthenticator/hl7:assignedEntity/hl7:assignedPerson/hl7:name/hl7:given",
        default="",
        namespaces=NS,
    )
    la_fam = root.findtext(
        "hl7:legalAuthenticator/hl7:assignedEntity/hl7:assignedPerson/hl7:name/hl7:family",
        default="",
        namespaces=NS,
    )
    if la_time is not None or la_given or la_fam:
        header_rows.append(
            (
                "Legal Authenticator",
                f"{la_given} {la_fam} (ID={la_id.get('extension', '').strip() if la_id is not None else ''}, root={la_id.get('root', '') if la_id is not None else ''}) | "
                f"signatureCode={la_sig.get('code', '') if la_sig is not None else ''} | time={fmt_hl7_ts(la_time.get('value', '') if la_time is not None else '')}",
            )
        )

    # Encompassing Encounter if present
    enc = root.find("hl7:componentOf/hl7:encompassingEncounter", NS)
    enc_summary = "None (Summary Document)"
    if enc is not None:
        enc_ids = [f"{e.get('extension', '')} (root={e.get('root', '')})" for e in enc.findall("hl7:id", NS)]
        enc_code = enc.find("hl7:code", NS)
        enc_code_str = ""
        orig = ""
        if enc_code is not None:
            orig = enc_code.findtext("hl7:originalText", default="", namespaces=NS).strip()
            trans = [
                f"{t.get('code', '')} {t.get('displayName', '')}".strip()
                for t in enc_code.findall("hl7:translation", NS)
            ]
            enc_code_str = f"code={enc_code.get('code', '')} ({enc_code.get('displayName', '')}) | originalText={orig} | translations={', '.join(trans)}"
        low_el = enc.find("hl7:effectiveTime/hl7:low", NS)
        high_el = enc.find("hl7:effectiveTime/hl7:high", NS)
        et_val = enc.find("hl7:effectiveTime", NS)
        time_str = ""
        date_short = ""
        if low_el is not None or high_el is not None:
            low_v = low_el.get("value", "") if low_el is not None else ""
            high_v = high_el.get("value", "") if high_el is not None else ""
            time_str = f"low={fmt_hl7_ts(low_v)} — high={fmt_hl7_ts(high_v)}"
            date_short = fmt_hl7_date_us(low_v) or fmt_hl7_date_us(high_v)
        elif et_val is not None and et_val.get("value"):
            time_str = fmt_hl7_ts(et_val.get("value", ""))
            date_short = fmt_hl7_date_us(et_val.get("value", ""))
        loc_names = [n.text.strip() for n in enc.findall(".//hl7:healthCareFacility//hl7:name", NS) if n.text and n.text.strip()]
        header_rows.append(
            (
                "Encompassing Encounter",
                f"ID: {', '.join(enc_ids)} | {enc_code_str} | Time: {time_str} | Facility: {' / '.join(loc_names)}",
            )
        )
        summary_parts = [p for p in [orig, " / ".join(loc_names[:2]), date_short] if p]
        if summary_parts:
            enc_summary = " | ".join(summary_parts)

    # Extract coded entries per section
    entry_rows: List[Dict[str, object]] = []
    for sec in root.findall(".//hl7:structuredBody/hl7:component/hl7:section", NS):
        sec_title = sec.findtext("hl7:title", default="Section", namespaces=NS).strip()
        sec_code_el = sec.find("hl7:code", NS)
        sec_code_str = (
            f"{sec_code_el.get('code', '')} ({sec_code_el.get('displayName', '')})"
            if sec_code_el is not None
            else ""
        )
        entries = sec.findall("hl7:entry", NS)
        for idx, entry in enumerate(entries, 1):
            ids = []
            for i_el in entry.findall(".//hl7:id", NS):
                ext = i_el.get("extension", "")
                rt = i_el.get("root", "")
                if ext and ext not in [x[0] for x in ids]:
                    ids.append((ext, rt))
            id_str = "; ".join([f"{ext}" for ext, _ in ids[:4]])

            raw_refs = []
            for r_el in entry.findall(".//hl7:reference", NS):
                rv = r_el.get("value", "")
                resolved = id_map.get(rv, "")
                if rv:
                    raw_refs.append((rv, resolved))

            filtered_refs = []
            for rv, resolved in raw_refs:
                if resolved and any(
                    other_res and other_rv != rv and other_res in resolved and len(other_res) < len(resolved)
                    for other_rv, other_res in raw_refs
                ):
                    filtered_refs.append(f"{rv}")
                elif resolved and len(resolved) > 400:
                    filtered_refs.append(f"{rv} (Full note text rendered in section above)")
                elif resolved:
                    filtered_refs.append(f"{rv}: {resolved}")
                else:
                    filtered_refs.append(rv)

            for orig_el in entry.findall(".//hl7:originalText", NS):
                if orig_el.find(".//hl7:reference", NS) is None:
                    ot = " ".join(orig_el.itertext()).strip()
                    if ot and ot not in filtered_refs:
                        filtered_refs.append(ot)
            ref_str = " | ".join(dict.fromkeys(filtered_refs))

            codes = []
            for c_el in entry.findall(".//hl7:code", NS) + entry.findall(".//hl7:translation", NS):
                c_code = c_el.get("code", "")
                c_sys = c_el.get("codeSystemName", "") or c_el.get("codeSystem", "")
                c_disp = c_el.get("displayName", "")
                if c_code and c_code not in ("CONC", "33999-4", "76662-6", "311401005", "48767-8"):
                    item = f"{c_sys}: {c_code}" + (f" ({c_disp})" if c_disp else "")
                    if item not in codes:
                        codes.append(item)

            vals = []
            for v_el in entry.findall(".//hl7:value", NS):
                v_code = v_el.get("code", "")
                v_disp = v_el.get("displayName", "")
                v_val = v_el.get("value", "")
                v_unit = v_el.get("unit", "")
                v_txt = " ".join(v_el.itertext()).strip()
                if v_code:
                    s = f"{v_code}" + (f" ({v_disp})" if v_disp else "")
                    if s not in vals:
                        vals.append(s)
                elif v_val:
                    s = f"{v_val} {v_unit}".strip()
                    if s not in vals:
                        vals.append(s)
                elif v_txt and v_el.find(".//hl7:reference", NS) is None:
                    if v_txt not in vals:
                        vals.append(v_txt)
            for dq in entry.findall(".//hl7:doseQuantity", NS):
                if dq.get("value"):
                    vals.append(f"Dose: {dq.get('value')} {dq.get('unit', '')}".strip())
            for sq in entry.findall(".//hl7:quantity", NS):
                if sq.get("value"):
                    vals.append(f"Supply Qty: {sq.get('value')} {sq.get('unit', '')}".strip())

            times = []
            for et in entry.findall(".//hl7:effectiveTime", NS):
                if et.get("value"):
                    times.append(et.get("value"))
                low = et.find("hl7:low", NS)
                high = et.find("hl7:high", NS)
                if low is not None and low.get("value"):
                    times.append(f"Start: {low.get('value')}")
                if high is not None and high.get("value"):
                    times.append(f"End: {high.get('value')}")
            authors = []
            for au in entry.findall(".//hl7:author", NS):
                tm = au.find("hl7:time", NS)
                tm_v = tm.get("value", "") if tm is not None else ""
                p_g = au.findtext(".//hl7:assignedPerson/hl7:name/hl7:given", default="", namespaces=NS)
                p_f = au.findtext(".//hl7:assignedPerson/hl7:name/hl7:family", default="", namespaces=NS)
                org_n = au.findtext(".//hl7:representedOrganization/hl7:name", default="", namespaces=NS)
                au_s = " ".join(
                    filter(
                        None,
                        [
                            f"{p_g} {p_f}".strip(),
                            f"({org_n})" if org_n else "",
                            f"@{tm_v}" if tm_v else "",
                        ],
                    )
                )
                if au_s and au_s not in authors:
                    authors.append(au_s)

            entry_rows.append(
                {
                    "section": f"{sec_title}" + (f" [{sec_code_str}]" if sec_code_str else ""),
                    "idx": idx,
                    "id": id_str,
                    "ref": ref_str,
                    "codes": "; ".join(codes),
                    "vals": "; ".join(vals),
                    "times_authors": " | ".join(list(dict.fromkeys(times)) + authors),
                }
            )

    return CDADocumentParsed(
        xml_path=xml_path,
        xml_name=xml_name,
        rel_path=rel_path,
        title=title_txt,
        effective_time_raw=eff_val,
        effective_time_fmt=fmt_hl7_ts(eff_val),
        encounter_summary=enc_summary,
        demographics=demographics,
        header_rows=header_rows,
        entry_rows=entry_rows,
    )


def parse_metadata_xml(meta_path: str) -> Tuple[List[Tuple[str, str]], List[Dict[str, object]], List[str]]:
    """Parse an IHE XDM METADATA.XML ebXML SubmitObjectsRequest file."""
    tree = ET.parse(meta_path)
    root = tree.getroot()

    pkg = root.find(".//rim:RegistryPackage", NS)
    pkg_info: List[Tuple[str, str]] = []
    if pkg is not None:
        pkg_info.append(("RegistryPackage ID", pkg.get("id", "")))
        pkg_info.append(("Status", pkg.get("status", "")))
        name_el = pkg.find("rim:Name/rim:LocalizedString", NS)
        desc_el = pkg.find("rim:Description/rim:LocalizedString", NS)
        if name_el is not None:
            pkg_info.append(("SubmissionSet Name", name_el.get("value", "")))
        if desc_el is not None:
            pkg_info.append(("Description", desc_el.get("value", "")))
        for slot in pkg.findall("rim:Slot", NS):
            s_name = slot.get("name", "")
            vals = [v.text for v in slot.findall(".//rim:Value", NS) if v.text]
            pkg_info.append((f"Slot: {s_name}", " | ".join(vals)))
        for cl in pkg.findall("rim:Classification", NS):
            nr = cl.get("nodeRepresentation", "")
            c_name = cl.find("rim:Name/rim:LocalizedString", NS)
            c_name_v = c_name.get("value", "") if c_name is not None else ""
            s_parts = []
            for slot in cl.findall("rim:Slot", NS):
                vals = [v.text for v in slot.findall(".//rim:Value", NS) if v.text]
                s_parts.append(f"{slot.get('name', '')}={' ; '.join(vals)}")
            pkg_info.append(
                (
                    f"Classification ({c_name_v or nr or 'Author'})",
                    " | ".join(filter(None, [f"nodeRepresentation={nr}" if nr else "", *s_parts])),
                )
            )
        for ei in pkg.findall("rim:ExternalIdentifier", NS):
            ei_name = ei.find("rim:Name/rim:LocalizedString", NS)
            ei_name_v = ei_name.get("value", "") if ei_name is not None else ei.get("identificationScheme", "")
            pkg_info.append((f"ExternalIdentifier: {ei_name_v}", ei.get("value", "")))

    ext_objs: List[Dict[str, object]] = []
    for eo in root.findall(".//rim:ExtrinsicObject", NS):
        eo_data: Dict[str, object] = {
            "id": eo.get("id", ""),
            "mimeType": eo.get("mimeType", ""),
            "status": eo.get("status", ""),
            "name": "",
            "slots": {},
            "classifications": [],
            "external_ids": [],
        }
        n_el = eo.find("rim:Name/rim:LocalizedString", NS)
        if n_el is not None:
            eo_data["name"] = n_el.get("value", "")
        slots_dict: Dict[str, List[str]] = {}
        for slot in eo.findall("rim:Slot", NS):
            vals = [v.text for v in slot.findall(".//rim:Value", NS) if v.text]
            slots_dict[slot.get("name", "")] = vals
        eo_data["slots"] = slots_dict

        cls_list: List[str] = []
        for cl in eo.findall("rim:Classification", NS):
            nr = cl.get("nodeRepresentation", "")
            cn = cl.find("rim:Name/rim:LocalizedString", NS)
            cn_v = cn.get("value", "") if cn is not None else ""
            s_parts = []
            for slot in cl.findall("rim:Slot", NS):
                vals = [v.text for v in slot.findall(".//rim:Value", NS) if v.text]
                s_parts.append(f"{slot.get('name', '')}={', '.join(vals)}")
            cls_list.append(
                f"{cn_v or 'Classification'}"
                + (f" [{nr}]" if nr else "")
                + (f" ({'; '.join(s_parts)})" if s_parts else "")
            )
        eo_data["classifications"] = cls_list

        eids_list: List[str] = []
        for ei in eo.findall("rim:ExternalIdentifier", NS):
            en = ei.find("rim:Name/rim:LocalizedString", NS)
            en_v = en.get("value", "") if en is not None else ""
            eids_list.append(f"{en_v}: {ei.get('value', '')}")
        eo_data["external_ids"] = eids_list
        ext_objs.append(eo_data)

    assocs: List[str] = []
    for a in root.findall(".//rim:Association", NS):
        slot_vals = [v.text for v in a.findall(".//rim:Value", NS) if v.text]
        assocs.append(
            f"{a.get('sourceObject', '')} -> {a.get('targetObject', '')} ({a.get('associationType', '').split(':')[-1]}: {', '.join(slot_vals)})"
        )

    return pkg_info, ext_objs, assocs


def parse_index_htm(index_path: str) -> IndexHtmParsed:
    """Extract metadata text from an IHE XDM INDEX.HTM file."""
    res = IndexHtmParsed()
    try:
        with open(index_path, encoding="utf-8", errors="replace") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        if soup.title and soup.title.string:
            res.title = soup.title.string.strip()
        nav_msg = soup.select_one(".Navigation .WelcomeMessageText")
        if nav_msg:
            res.created_by = nav_msg.get_text(" ", strip=True)
        cur_el = soup.select_one(".SectionHeaderTextSmall")
        if cur_el:
            res.current_as_of = cur_el.get_text(" ", strip=True)
        sub_msg = soup.select_one(".Subsection .WelcomeMessageText")
        if sub_msg:
            res.patient_heading = sub_msg.get_text(" ", strip=True)
        sub_span = soup.select_one(".Subsection > span")
        if sub_span:
            res.intro_text = " ".join(sub_span.get_text(" ", strip=True).split())
        fp_el = soup.select_one(".FilePath")
        if fp_el:
            res.package_path = " ".join(fp_el.get_text(" ", strip=True).split())
        cp_el = soup.select_one(".CopyrightText")
        if cp_el:
            res.copyright_text = " ".join(cp_el.get_text(" ", strip=True).split())
    except Exception:
        pass
    return res
