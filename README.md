# `cda2pdf`

Convert **HL7 CDA R2 XML** clinical documents, **IHE XDM** folders, or **XDM `.zip` archives** into a single unabridged, bookmarked, page-numbered PDF on macOS.

> **Licensing:** `cda2pdf` is licensed under the **GNU AGPL v3.0** for open-source and non-commercial use. For proprietary commercial use without the AGPL's source-disclosure obligations, a commercial license must be purchased. Contact **hello@minthealthvt.com** for pricing. See [Licensing](#licensing) below.

> **No warranty.** This software is provided "as is", without warranty of any kind, express or implied. It is **not** a medical device and is **not** certified for clinical decision-making. You are responsible for validating its output before relying on it. See sections 15–17 of the [LICENSE](LICENSE).

---

## Features

- **Zero summarization (full-fidelity extraction):**
  - Renders the complete human-readable clinical narrative of each CDA document via XSLT.
  - Appends an **XML Header & Coded Clinical Entries Metadata** section to each document containing machine-readable codes (RxNorm, NDC, First DataBank NDDF, SNOMED CT, ICD-10-CM, ICD-9-CM, LOINC, CPT), quantities and doses, narrative references, and author provenance timestamps.
  - Extracts and renders `INDEX.HTM`, `IHE_XDM/.../METADATA.XML` (`RegistryPackage`, `ExtrinsicObject` entries, HL7 PID fields, SHA-1 hashes, byte sizes, `HasMember` associations), and `README.TXT` when converting an XDM package.
- **Dynamic patient and encounter parsing:** extracts patient name, date of birth, gender, patient IDs, authoring organization/device, and encounter dates and locations directly from the CDA XML.
- **Native macOS rendering, stamping and bookmarks:** uses macOS `WebKit` + `PDFKit` to paginate each document onto US Letter pages, stamp every page with per-document and global page counters, and build clickable PDF sidebar bookmarks (`PDFOutline`).

---

## Requirements

| Requirement | Notes |
|---|---|
| **macOS** | Required. Rendering uses the system `WebKit` and `PDFKit` frameworks. |
| **Xcode Command Line Tools** | Provides `clang`, used to compile the native renderer on first run. Install with `xcode-select --install`. |
| **Python 3.9+** | |
| **`xsltproc`** | Ships with macOS by default. |

The native renderer (`src/cda2pdf/native/mac_pdf_renderer.m`) is **compiled on your machine on first use** and is not distributed as a binary. If the package directory is read-only, the compiled binary is cached in `~/.cache/cda2pdf/` instead.

---

## Installation

```bash
git clone https://github.com/<your-org>/cda2pdf.git
cd cda2pdf
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The only runtime dependency is `beautifulsoup4`.

Verify the install:

```bash
cda2pdf --version
python -m unittest discover -s tests
```

The test suite runs against a synthetic CDA fixture and requires no patient data.

---

## Command-line usage

### Convert an IHE XDM package folder

```bash
cda2pdf /path/to/XDM-YYMMDD-HHMMSS -o patient_record.pdf
```

If `-o` is omitted, the output PDF is named `<Patient_Name>_<Folder_Name>.pdf` in the current working directory.

### Convert an XDM `.zip` archive directly

```bash
cda2pdf /path/to/XDM-YYMMDD-HHMMSS.zip
```

### Convert standalone CDA `.xml` files

```bash
# Single CDA XML file
cda2pdf DOC00001.XML -o health_summary.pdf

# Multiple CDA XML files merged into one bookmarked PDF
cda2pdf DOC00001.XML DOC00002.XML DOC00003.XML -o combined_docs.pdf
```

### Narrative only, without the index and code appendix

```bash
cda2pdf /path/to/XDM-YYMMDD-HHMMSS --no-cover --no-coded-entries -o essentials.pdf
```

### Options

```text
usage: cda2pdf [-h] [-o OUTPUT_PDF] [--xsl XSL_PATH] [--no-coded-entries]
               [--no-cover] [--keep-html KEEP_HTML_DIR] [-v]
               inputs [inputs ...]

  -o, --output OUTPUT_PDF   Output PDF file path (defaults to <Patient_Name>_<Source>.pdf)
  --xsl XSL_PATH            Custom XSLT stylesheet path
  --no-coded-entries        Omit appended XML Header & Coded Clinical Entries tables
  --no-cover                Omit Package Index / METADATA.XML / README.TXT cover section
  --keep-html KEEP_HTML_DIR Directory to keep intermediate HTML and per-part PDFs
  -v, --version             Show version number
```

---

## Python API

```python
from cda2pdf import convert_cda_to_pdf

result = convert_cda_to_pdf(
    inputs="/path/to/XDM-YYMMDD-HHMMSS",
    output_pdf="patient_record.pdf",
    include_coded_entries=True,
    include_cover=True,
)

print(f"Generated {result.output_pdf} ({result.total_pages} pages) for {result.patient_name}")
for part in result.parts:
    print(f"  Pages {part['start_page']}-{part['end_page']}: {part['bookmark_label']}")
```

---

## Stylesheets

CDA documents carry a human-readable narrative that must be rendered through an XSLT stylesheet. `cda2pdf` resolves one in this order:

1. The path given with `--xsl`.
2. A stylesheet shipped inside the source XDM package itself, at `HTML/STYLE/*.xsl`. **This is preferred for XDM packages**, because it is the stylesheet the originating health system intended for those documents.
3. The bundled default, `src/cda2pdf/assets/STYLE/cda-default.xsl`.

The bundled `cda-default.xsl` is an **original, clean-room implementation** written against the published HL7 CDA R2 specification and the CDA `NarrativeBlock` schema. It renders the CDA header (demographics, document metadata, encounter) and every `structuredBody` section's narrative, including tables, lists, `styleCode` formatting, footnotes and revision marks.

No vendor-supplied stylesheet, logo or other branded asset is redistributed with this package. When you convert an XDM export that contains its own stylesheet and images, those files are read from **your copy** of the package at runtime and are never vendored into this repository.

### Writing a replacement stylesheet

If you pass your own stylesheet with `--xsl`, emit these two container IDs so the per-document banner and the coded-entries appendix are injected correctly:

```html
<div id="DocWrapper">      <!-- banner is inserted at the top of this element -->
  <div id="DocBody">       <!-- coded-entries table is appended to this element -->
    ...                    <!-- your rendered sections -->
  </div>
</div>
```

---

## Handling patient data

This tool processes protected health information. A few notes:

- **Nothing is transmitted.** All parsing and rendering happen locally. The package makes no network calls.
- **Output is unredacted by design.** The generated PDF contains the complete record, including identifiers. Treat it with the same care as the source export.
- **Intermediate files.** `--keep-html` writes unencrypted intermediate HTML and per-document PDFs to the directory you specify. Without that flag, intermediates go to a temporary directory that is deleted when conversion finishes.
- **Do not commit patient data to this repository.** The test suite uses a synthetic fixture. To test against a real export, set `CDA2PDF_TEST_XDM` to a path outside the repo:

  ```bash
  CDA2PDF_TEST_XDM=/path/to/XDM-export python -m unittest discover -s tests
  ```

---

## Licensing

`cda2pdf` is dual-licensed.

**Open-source / non-commercial — GNU AGPL v3.0.** You may use, modify and redistribute this software under the terms of the [GNU Affero General Public License v3.0](LICENSE). Note that the AGPL's network clause (section 13) applies: if you run a modified version as a network service, you must offer its source to users of that service.

**Commercial.** For proprietary commercial use without the AGPL's source-disclosure obligations, a separate commercial license is required. Contact **hello@minthealthvt.com** for pricing.

Contributions are accepted under the terms described in [CONTRIBUTING.md](CONTRIBUTING.md), which includes a contributor license agreement enabling the dual-licensing model above.

### Disclaimer of warranty

As stated in sections 15 and 16 of the [LICENSE](LICENSE), this program is provided without warranty of any kind, express or implied, including the implied warranties of merchantability and fitness for a particular purpose. The entire risk as to the quality and performance of the program is with you. In no event will any copyright holder or other party be liable for damages arising out of the use or inability to use the program.

This software is not a medical device, has not been reviewed or cleared by any regulatory authority, and must not be used as the sole basis for clinical decisions.
