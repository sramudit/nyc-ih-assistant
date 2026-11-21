# ⚖️ NYC Impartial Hearing Assistant

**A privacy-first, multi-model Gemini 4 record organizer, service-gap auditor, and parent briefing tool for *pro se* families navigating NYC DOE Special Education Impartial Hearings.**

> **Hackathon Track:** Gemini 4 NYC Hackathon — **Problem Statement One: 5 Sigma**  
> Built by a biomedical engineer and 7-year *pro se* NYC special education parent so families—and the advocates and law clinics supporting them—can audit messy school records without risking minor PII or hallucinated citations.

---

## Why This Matters
*Pro se* parents entering NYC Office of Administrative Trials and Hearings (OATH) special education disputes face hundreds of pages of SESIS IEPs, Prior Written Notices (PWNs), neuropsychological evaluations, and scanned therapy logs—while arguing against experienced district representatives. Generic AI chatbots fail on this task in three ways:
1. **Privacy Risk:** Uploading unredacted minor medical/educational records (FERPA/PHI) to cloud LLMs is unsafe for families and violates clinic confidentiality.
2. **Layout Blindness:** Text-only extraction scrambles multi-column IEP service grids and drops visual checkboxes (e.g., an IEP marking `Yes` for a Behavioral Intervention Plan on page 12 and `No` on page 22).
3. **Citation Hallucinations:** Misquoting a service gap or page number destroys a parent's credibility in front of an Impartial Hearing Officer (IHO).

---

## Multi-Model Architecture (Each Model Has a Clear Job)

| Stage / Model | Role in Pipeline | Input → Output |
| :--- | :--- | :--- |
| **Local Privacy Shield** (`PyMuPDF` + `spaCy` + `RapidOCR`) | Runs **100% locally** before any cloud API call. Scrubs names, OSIS IDs, DOBs, addresses, and filenames (`DOC_001`), runs offline OCR on scanned PDFs, and burns permanent black redaction boxes into a downloadable PDF copy. | Raw PDFs → Blacked-out PDF previews + anonymized text |
| **`gemini-4-hydrogen`** | **Multimodal Visual Inspector & Video Verifier.** Reads blacked-out PDF page images directly to catch visual checkbox contradictions and table columns, and watches generated briefing clips to verify legibility and alignment. | Redacted PNG pages / MP4 video → Visual findings & verification check |
| **`gemini-4-neon`** | **NYC DOE SOPM / Part 200 Audit & Parent Coach.** Reconciles IEP mandates against delivery logs and evaluations (grounded in IDEA *Endrew F.*, NYSED `8 NYCRR Part 200`, and NYC OATH rules) into calm, plain-English Action Cards, arguments to document, and video scripts. | Scrubbed text + visual findings → Parent Action Cards, OATH checklist & 3-min script |
| **`gemini-4-carbon`** | **5-Sigma Citation Auditor.** Independently cross-checks every Neon claim, score, and missed-session count against the source text and scores citation accuracy (`0–100%`). | Draft findings + source text → Verification score & discrepancy flags |
| **`gemini-omni-1.2-flash`** (`v1beta`) + `Pillow` + `edge-tts` + `moviepy` | **3-Minute Parent Briefing Video Studio.** Combines an animated Omni 1.2 Flash opener (guided by a Pillow reference card) with 3 comprehensive 1-minute narrated explainer segments (*Gaps Found → NYC Rules → Arguments to Document*). | Verified findings → Complete ~3-min MP4 guide + 1-min segment clips |

---

## 5-Sigma Engineering: Real-World Failures Caught & Fixed
When tested against real unseen NYC OATH transcripts, SESIS IEPs, and scanned evaluations (processed locally and never committed to GitHub), our initial single-pass scrubber and parser exposed real edge-case failures that we engineered out:

1. **Phonetic Transcript Spelling (`R-A-M as in Mary, U-D as in dog`):** Court reporters record parents spelling names aloud across `"as in"` cues, splitting the name from single-token matching. *Fix:* Added a dedicated phonetic-spelling regex rule before NER runs.
2. **Line-Number-Split Case IDs (`case\n 7 number 311994`):** OATH transcripts insert line numbers at the start of every line, breaking `"case number"` regexes. *Fix:* Allowed line-number/whitespace gaps between ID labels and numbers.
3. **Spaced & Unlabeled NYC OSIS IDs (`901 442 817`):** NYC DOE forms frequently space 9-digit OSIS numbers across table columns. *Fix:* Added standalone `3-3-3` digit-group detection with boundary guards (preserving 10-digit phones and dates).
4. **ALL-CAPS Court Signatures & Scanned Image PDFs:** Standard `spaCy` NER missed ALL-CAPS names (e.g., `EFRATH LEVY`) and scanned PDFs rendered blank text. *Fix:* Added ALL-CAPS signature-line handling + offline `RapidOCR` bounding-box blackouts on forced white-background RGB renders.
5. **Baseline vs. System Evaluation (`eval_5sigma.py`):** Compares a single-model text-only baseline (`gemini-4-hydrogen`) against our full 3-model verified pipeline across adversarial PII cases and messy visual/contradictory PDFs (runnable live inside **Tab 5** or via `python eval_5sigma.py`).

---

# Quick Start Guide — NYC Impartial Hearing Assistant

Follow these steps to run the app on your computer. Your real student PDFs stay **100% local** on your machine during redaction.

---

## 1. Install Prerequisites (One-Time Setup)
* **Python 3.12** (recommended for `spacy` and `rapidocr-onnxruntime` compatibility). On Windows, check **"Add python.exe to PATH"** during installation.
* **VS Code** (or any terminal).

---

## 2. Download & Set Up the Project

Open a terminal in the project folder and create a virtual environment:

**Windows (PowerShell):**
```powershell
git clone https://github.com/YOUR_USERNAME/nyc-ih-assistant.git
cd nyc-ih-assistant
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m spacy download en_core_web_md
```

**Mac / Linux:**
```bash
git clone https://github.com/YOUR_USERNAME/nyc-ih-assistant.git
cd nyc-ih-assistant
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_md
```

---

## 3. Add Your Gemini API Key
1. Create a file named **`.env`** in the main `nyc-ih-assistant` folder (already ignored by `.gitignore`).
2. Paste your Google AI Studio API key inside:

```text
GEMINI_API_KEY=your_api_key_here
```

*(Note: `gemini-4-neon`, `gemini-4-carbon`, and `gemini-omni-1.2-flash` require a billing-enabled Gemini API project under `v1beta`.)*

---

## 4. Launch the App

**Windows:**
```powershell
.venv\Scripts\streamlit run app.py
```

**Mac / Linux:**
```bash
.venv/bin/streamlit run app.py
```

Your browser will open automatically at **`http://localhost:8501`**.

---

## 5. Two Ways to Use It

### Option A: 1-Click Judge / Advocate Demo (Fake NYC Case)
1. In **Tab 1 (`Local Privacy Shield`)**, click **🧪 Load Realistic NYC Demo Packet** (loads 4 synthetic NYC DOE PDFs—IEP, Neuropsych Eval, Service Logs/PWN, and OATH Transcript).
2. Click **🛡️ Run Local Scrubber & Black Out PDFs** to inspect the blacked-out PDF pages side-by-side with anonymized text.
3. Check the verification box and click **🚀 Analyze with 3-Model Gemini 4 Pipeline**.
4. Explore **Tab 2 (`What We Found`)**, **Tab 3 (`Arguments & OATH Prep`)**, **Tab 4 (`Parent Briefing Video`)**, and **Tab 5 (`5-Sigma Reliability & Eval`)**.

### Option B: Your Real Hearing Records (Private Local Mode)
1. In the left sidebar, type your **Student Name, Parent Name, School, OSIS/NYC ID, DOB, and Address** (or copy `pii_config.example.json` to `pii_config.json` and click **📂 Load My Local pii_config.json**).
2. Upload your PDFs in **Tab 1** (both digital PDFs and scanned image PDFs are supported via offline `RapidOCR`).
3. Click **🔍 Auto-Discover Names / Schools / OSIS Locally** to catch extra evaluators/clinics, then click **🛡️ Run Local Scrubber & Black Out PDFs**.
4. Inspect every page in the side-by-side viewer. If anything slipped through, add it to **Extra Words to Black Out** and re-scrub.
5. Check the human verification gate and run the **3-Model Gemini 4 Analysis**, download your plain-English **Parent Prep Guide (`.md`)** in Tab 3, or generate your **3-Minute Briefing Video** in Tab 4.

---

## Privacy & Self-Help Notice
* **Never commit private files:** `.gitignore` automatically excludes `.env`, `pii_config.json`, `raw_pdfs/`, `redacted_output/`, `generated_videos/`, and `*.pdf`.
* **Not legal advice:** This tool helps organize records and explain IDEA / NYSED Part 200 / NYC OATH rules in plain English. Always verify citations against your original exhibits.