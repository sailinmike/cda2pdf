# Healthcare Data & Clinical Use Disclaimer

This Python package is a data processing and formatting utility designed to convert Clinical Document Architecture (CDA) XML patient data into PDF format. By using this software, you explicitly acknowledge and agree to the following terms, which supplement the main repository license (AGPLv3 / Commercial).

---

### 1. No Medical or Clinical Advice

* This software is **not a medical device** and has not been cleared or approved by the U.S. Food and Drug Administration (FDA), the European Medicines Agency (EMA), or any other regulatory body for clinical diagnostic use.
* This software does not provide medical advice, diagnosis, treatment recommendations, or clinical decision support.
* The visual rendering of data in the generated PDF is for informational and administrative purposes only. It should not be relied upon as the primary source for making critical clinical decisions.

### 2. Clinical Accuracy and Validation Warning

* Automated parsing and rendering of CDA XML structures (including CCD, Continuity of Care Documents) are inherently complex. Variations in XML schemas, custom extensions, or malformed source data may result in missing, misaligned, truncated, or incorrectly formatted text in the final PDF output.
* **Critical Risk:** Errors in parsing can lead to the misrepresentation of vital clinical data, including but not limited to: medication dosages, patient allergies, laboratory results, and active problem lists.
* It is the sole responsibility of the end user, implementation clinical team, and healthcare institution to thoroughly validate the PDF output against the raw source data before integrating this package into any active clinical workflow.

#### 2a. Known rendering behaviors that affect fidelity

The following are specific, known characteristics of how this software renders documents. They are disclosed so that your validation can account for them.

* **Rendering depends on an external stylesheet.** CDA narrative is rendered through an XSLT stylesheet. By default the software uses a stylesheet found inside your own source package (`HTML/STYLE/*.xsl`) when one is present, and otherwise falls back to the bundled `cda-default.xsl`. **Different stylesheets produce materially different output,** including different page counts, section ordering, and visual emphasis. Validate against the stylesheet you actually deploy.
* **The bundled stylesheet is an independent implementation.** `cda-default.xsl` was written against the published HL7 CDA R2 specification. It is not the stylesheet your source health system authored, and it may present the same document differently than that system's own viewer does.
* **Only the attested narrative is rendered as clinical content.** Per CDA R2, the `<text>` NarrativeBlock is the human-readable, attested portion of a document. Coded entries are reproduced in a separate metadata appendix, not merged into the narrative. Where a coded entry and the narrative disagree, this software does not reconcile them.
* **No cross-document reconciliation is performed — by design.** When converting a multi-document package, each document is rendered independently as the point-in-time record it is. Medication lists, allergy lists, and problem lists are deliberately **not** merged, deduplicated, reconciled, or summarized across documents, and a later document may differ from an earlier one.

  This is an intentional design decision, not a limitation to be corrected. Each document is part of the clinical history, and the differences between them carry clinical meaning. Reconciling them automatically would require the software to make clinical judgments about which record supersedes which — exactly the kind of inference this tool refuses to make. Medication reconciliation is a clinical act performed by a qualified clinician, and nothing in this output substitutes for it. **Accordingly, the output is a chronological record, not a current medication list.**
* **Unsupported content is omitted rather than approximated.** Documents using `nonXMLBody` (for example, an embedded PDF or scanned image) are noted but their content is not rendered. Referenced external media is identified by reference only. Image references that cannot be resolved locally are dropped.
* **Resolution of embedded references.** Narrative text may reference identifiers resolved elsewhere in the document. Where a reference cannot be resolved, the raw reference may appear in place of a resolved value.

### 3. Limitation of Liability for Clinical Outcomes

* To the maximum extent permitted by applicable law, the author(s) and copyright holders shall not be held liable for any medical malpractice claims, misdiagnoses, patient injury, adverse clinical events, or wrongful death resulting from the use, misuse, or failure of this software.
* The end user assumes all clinical risks associated with relying on the generated PDF documents.
* This section supplements, and does not replace, the disclaimer of warranty and limitation of liability in sections 15 through 17 of the [LICENSE](LICENSE).

### 4. HIPAA, GDPR, and Data Privacy Compliance

* This Python package operates **entirely locally** on the infrastructure provided by the end user.
* The software does not collect, transmit, or upload Protected Health Information (PHI), Personally Identifiable Information (PII), or any patient data to external servers or third parties. It contains no telemetry, analytics, update check, or other outbound network call.
* **Rendering is network-isolated.** Clinical documents are treated as untrusted input. Because a document or a third-party stylesheet could reference a remote resource — and fetching it would transmit data to its host as a side effect — the renderer blocks all non-local resource requests. Only `file:`, `data:`, and `about:` URLs are permitted; anything else is refused and reported on standard error. JavaScript, plugins, and Java are disabled during rendering.
* Compliance with regional healthcare data privacy regulations (such as HIPAA in the United States, GDPR in the European Union, or equivalent local statutes) remains entirely the responsibility of the entity deploying the software. The author(s) assume no liability for data breaches, unencrypted data storage, or regulatory compliance failures occurring on the user's systems.

#### 4a. Run only on systems certified to handle PHI

**This software writes unencrypted Protected Health Information to local disk as a normal part of its operation. It must only be run on a machine that your organization has certified, authorized, and secured for handling PHI.**

Do not run it on a personal, shared, loaner, or otherwise uncontrolled computer; on removable media; or on any system outside the scope of your organization's HIPAA security risk analysis. At minimum, the machine should have full-disk encryption enabled, enforced access controls and screen lock, current security patches, and whatever endpoint monitoring, backup exclusion, and device management policies your organization requires. Where the machine is covered by a Business Associate Agreement or equivalent contractual control, that agreement governs.

Determining whether a given system meets these requirements is the responsibility of the deploying entity, not of this software or its author. The software performs no check of the environment it runs in and will write PHI to whatever location it is pointed at.

#### 4b. What is written to disk

Subject to the requirement above, you are responsible for securing and disposing of the following:

* **The output PDF.** It contains the complete, unredacted record, including patient identifiers. It is not encrypted or password-protected, and it inherits the permissions of the directory you write it to.
* **Temporary working files.** During conversion, intermediate HTML and per-document PDFs are written to a temporary directory. This directory is deleted when conversion completes normally. **If the process is interrupted — by a crash, a kill signal, or a power loss — these files may remain on disk** in your system's temporary directory.
* **`--keep-html` output.** This flag intentionally preserves intermediate HTML and per-document PDFs in a directory you specify, and does not delete them. These files contain the full record in plain text. Use the flag only for debugging, and remove the output afterward.
* **Input handling.** When given a `.zip` archive, the software extracts it to a temporary directory in order to read it. The original archive is not modified.

Nothing written by this software is encrypted at rest. If your threat model or regulatory obligations require encryption at rest, place the working directory and the output directory on an encrypted volume (for example, a FileVault-protected disk).

### 5. No Professional Relationship

* Use of this software does not create a physician-patient relationship, a business associate relationship, or any professional or fiduciary duty between the user and the author(s) or copyright holders.
* If you are a HIPAA covered entity or business associate, note that the author(s) are **not** acting as your business associate by virtue of your use of this software. No Business Associate Agreement (BAA) is offered or implied, and none is required, because the software operates locally and the author(s) receive no patient data.

### 6. Your Responsibilities

Before deploying this software in any environment that handles real patient data, you should at minimum:

1. Confirm the machine is certified and authorized by your organization to process PHI, with full-disk encryption enabled (see 4a).
2. Validate output against source data for a representative sample of your own documents, including edge cases such as long medication lists, nested tables, and documents from each source system you ingest.
3. Confirm that the stylesheet you deploy renders every section type your documents contain.
4. Establish access controls, encryption at rest, and a retention and disposal policy for generated PDFs.
5. Conduct your own privacy and security review against your regulatory obligations.
6. Keep a human in the loop for any clinical use of the output. Medication, allergy and problem reconciliation across documents remains a clinical task for a qualified clinician.

---

*This disclaimer is provided for transparency about how the software behaves. It is not legal advice. Consult qualified counsel regarding your own regulatory obligations.*
