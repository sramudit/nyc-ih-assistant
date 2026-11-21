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