# Contributing to `cda2pdf`

Thanks for your interest in contributing.

---

## Contributor License Agreement (please read before opening a pull request)

`cda2pdf` is **dual-licensed**: under the GNU AGPL v3.0 for open-source and non-commercial use, and under a separate commercial license for proprietary use. For that model to work, the project maintainer must hold sufficient rights in all contributed code to relicense it commercially.

**By submitting a pull request, issue patch, or any other contribution to this project, you agree to the following:**

1. **Grant of copyright license.** You grant the project maintainer a perpetual, worldwide, non-exclusive, royalty-free, irrevocable copyright license to reproduce, prepare derivative works of, publicly display, publicly perform, sublicense and distribute your contribution and such derivative works, **under any license terms, including proprietary commercial terms**.

2. **Grant of patent license.** You grant the project maintainer and recipients of software distributed by the project a perpetual, worldwide, non-exclusive, royalty-free, irrevocable patent license to make, use, sell, offer to sell, import and otherwise transfer your contribution, covering those patent claims licensable by you that are necessarily infringed by your contribution alone or by its combination with the project.

3. **You retain your copyright.** This agreement does not transfer ownership. You keep the copyright in your contribution and remain free to use it however you wish elsewhere.

4. **You have the right to grant this license.** You represent that each contribution is your original work, and that you are legally entitled to grant the above licenses. If your employer has rights to intellectual property you create, you represent that you have received permission to make the contribution on their behalf, or that your employer has waived such rights.

5. **No PHI or third-party material.** You represent that your contribution contains no protected health information, no personal data of any real individual, and no code or assets copied from a third party whose license is incompatible with the above grants.

6. **Provided as is.** Unless required by applicable law or agreed in writing, you provide your contribution on an "as is" basis, without warranties or conditions of any kind.

If you are not willing to agree to these terms, please open an issue describing the change rather than submitting code, and it can be implemented independently.

---

## Protected health information: a hard rule

**Never commit real patient data to this repository.** That includes CDA XML files, XDM exports, generated PDFs, intermediate HTML from `--keep-html`, screenshots showing real records, and log output containing identifiers.

Pull requests containing PHI will be closed without merge, and the data will need to be purged from Git history — which is disruptive for everyone. Please check your diffs carefully.

Use the synthetic fixture at `tests/fixtures/sample_cda.xml` for anything that needs sample data. If you need a new scenario covered, extend that fixture or add another synthetic one. Keep invented data clearly fake:

- Telephone numbers in the `555-01xx` range reserved for fictional use.
- Identifier OIDs under `2.16.840.1.113883.19`, the arc HL7 reserves for examples.
- Email addresses on the `.invalid` TLD.
- Obviously fictional names, organizations and addresses.

---

## Do not vendor vendor assets

This project deliberately ships **no** third-party stylesheets, logos or branded images. Health-system CDA exports typically include a vendor stylesheet under `HTML/STYLE/` that is copyrighted and not redistributable.

`cda2pdf` reads those files from the user's own copy of their export at runtime. **Do not add them to this repository**, even for convenience or testing. If you need a stylesheet for development, point `--xsl` at your local copy.

The bundled `src/cda2pdf/assets/STYLE/cda-default.xsl` is original, clean-room work written from the published HL7 CDA R2 specification. Keep it that way: do not copy markup, CSS, class names or template logic out of a vendor stylesheet when extending it.

---

## Development setup

```bash
git clone https://github.com/<your-org>/cda2pdf.git
cd cda2pdf
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires macOS, Python 3.9+, `xsltproc`, and Xcode Command Line Tools (`xcode-select --install`) for `clang`.

### Running tests

```bash
python -m unittest discover -s tests -v
```

The suite runs against the synthetic fixture and needs no patient data. Parser tests run on any platform; conversion tests skip automatically off macOS or without `xsltproc`.

To additionally exercise the XDM package path against a real export (kept outside the repo):

```bash
CDA2PDF_TEST_XDM=/path/to/XDM-export python -m unittest discover -s tests -v
```

Those tests assert only on structure — page counts, part ordering, bookmark ranges — never on patient identifiers, so they stay valid for any export.

### The native renderer

`src/cda2pdf/native/mac_pdf_renderer.m` is compiled on demand by `renderer.py`. It rebuilds automatically when the `.m` file is newer than the compiled binary. To force a rebuild:

```bash
rm -f src/cda2pdf/native/cda2pdf_mac_renderer
python -c "from cda2pdf.renderer import ensure_native_renderer; print(ensure_native_renderer())"
```

**Compiled binaries must not be committed.** They are machine- and architecture-specific, and `.gitignore` excludes them.

---

## Pull request guidelines

- Keep changes focused; one concern per PR.
- Add or update tests for behavior changes.
- Run the full suite before submitting.
- Match the existing style: type hints on public functions, docstrings on modules and public classes, and comments that explain *why* rather than restating the code.
- If you change rendering output, say so in the PR description and include before/after page counts. Verify no content was dropped — the project's core promise is that nothing is summarized or truncated.

## Reporting security or privacy issues

Please do **not** open a public issue for a vulnerability, or for a bug that could expose patient data. Email **hello@minthealthvt.com** instead.
