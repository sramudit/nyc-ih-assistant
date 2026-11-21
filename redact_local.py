import io
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from PIL import Image, ImageDraw
import pymupdf  # Modern import for PyMuPDF (runs 100% locally)
import spacy

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None

SAFE_ALLOWLIST = {
    "idea", "fape", "iep", "pwn", "fba", "bip", "iho", "cse", "cpse", "mdr",
    "setss", "ict", "ot", "pt", "slp", "aba", "lre", "esy", "rti", "mtss",
    "wisc", "wisc-v", "wiat", "wiat-4", "woodcock", "johnson", "woodcock-johnson",
    "vineland", "basc", "basc-3", "conners", "ados", "ados-2", "kaufman",
    "celf", "celf-5", "gort", "towre", "berry", "vmi", "bot-2", "pdms",
    "ferpa", "hipaa", "section 504", "sesis", "sped", "adhd", "asd",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "new york", "nyc", "doe", "oath", "hearing", "officer", "district",
    "parent", "student", "school", "counsel", "exhibit", "page", "record"
}

SAFE_DOC_TYPE_TOKENS = {
    "iep", "pwn", "fba", "bip", "eval", "evaluation", "psych", "neuropsych",
    "speech", "therapy", "bcba", "aba", "progress", "attendance", "log",
    "logs", "notes", "notice", "ihr", "complaint", "dpc", "decision", "order",
    "sesis", "amendment", "report", "transcript", "exhibit", "fofd"
}

TITLE_SKIP = {"mr", "mrs", "ms", "miss", "dr", "prof", "jr", "sr", "ii", "iii", "iv"}

_NLP_CACHE = None
_OCR_CACHE = None


def load_spacy_model():
    global _NLP_CACHE
    if _NLP_CACHE is not None:
        return _NLP_CACHE
    for model_name in ("en_core_web_md", "en_core_web_sm"):
        try:
            _NLP_CACHE = spacy.load(model_name)
            return _NLP_CACHE
        except OSError:
            continue
    raise RuntimeError(
        "No spaCy English model found. Run: python -m spacy download en_core_web_md"
    )


def load_ocr_engine():
    global _OCR_CACHE
    if _OCR_CACHE is None and RapidOCR is not None:
        _OCR_CACHE = RapidOCR()
    return _OCR_CACHE


def build_safe_doc_stem(doc_id: str, original_filename: str) -> str:
    stem = Path(original_filename).stem.lower()
    tokens = re.split(r"[^a-z0-9]+", stem)
    safe_hits = []
    for tok in tokens:
        if tok in SAFE_DOC_TYPE_TOKENS and tok.upper() not in safe_hits:
            safe_hits.append(tok.upper())
        if len(safe_hits) >= 3:
            break
    if safe_hits:
        return f"{doc_id}_{'_'.join(safe_hits)}"
    return doc_id


class LocalRedactor:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        config_dict: Optional[Dict] = None,
    ):
        self.nlp = load_spacy_model()
        if config_dict is not None:
            self.config = config_dict
        elif config_path is not None:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}

        self.person_map = {}
        self.audit_counts = {}
        self.blocklist_rules = []

        category_tags = {
            "student_names": "[STUDENT]",
            "parent_names": "[PARENT]",
            "school_names": "[SCHOOL]",
            "district_names": "[DISTRICT]",
            "provider_names": "[PROVIDER]",
            "ids": "[REDACTED_ID]",
            "dobs": "[REDACTED_DOB]",
            "addresses": "[REDACTED_ADDRESS]",
            "extra_terms": "[REDACTED]",
        }

        for key, tag in category_tags.items():
            entries = list(self.config.get(key, []))
            expanded_entries = list(entries)
            if key in ("student_names", "parent_names"):
                for item in entries:
                    for part in re.split(r"[\s\-]+", item.strip()):
                        clean_part = re.sub(r"[^A-Za-z]", "", part)
                        if len(clean_part) >= 3 and clean_part.lower() not in TITLE_SKIP:
                            expanded_entries.append(clean_part)

            seen = set()
            unique_entries = []
            for item in sorted(expanded_entries, key=len, reverse=True):
                norm = item.strip().lower()
                if norm and norm not in seen:
                    seen.add(norm)
                    unique_entries.append(item.strip())

            for item in unique_entries:
                if len(item) >= 2:
                    parts = item.split()
                    joined = r"[\s_]+".join(re.escape(p) for p in parts)
                    pattern = re.compile(
                        rf"(?<![A-Za-z0-9]){joined}(?![A-Za-z0-9])",
                        re.IGNORECASE,
                    )
                    self.blocklist_rules.append((pattern, tag, key))

                if key in ("student_names", "parent_names") and item.isalpha() and len(item) >= 3:
                    spelled = r"[\s\-.,/]+".join(re.escape(ch) for ch in item)
                    spelled_pattern = re.compile(
                        rf"(?<![A-Za-z0-9]){spelled}(?![A-Za-z0-9])",
                        re.IGNORECASE,
                    )
                    self.blocklist_rules.append((spelled_pattern, tag, f"{key}_spelled"))

        self.regex_rules = [
            (
                re.compile(
                    r"(?i)\b(d\.?o\.?b\.?|date\s+of\s+birth|birth\s*date)\s*[:#\-]?\s*"
                    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})"
                ),
                r"\1: [REDACTED_DOB]",
                "regex_dob",
                2,
            ),
            (
                re.compile(
                    r"(?i)\b(osis|nyc\s*(?:student\s*)?id(?:\s*(?:no\.?|number|#))?|"
                    r"nysed\s*id|sesis\s*id|student\s*id|id\s*(?:no\.?|number|#)|"
                    r"oath\s*(?:case|index|docket)?\s*(?:no\.?|number|#)?|"
                    r"case\s*(?:no\.?|number|#)|ih\s*(?:case\s*)?#?|"
                    r"docket\s*(?:no\.?|number|#)|file\s*(?:no\.?|number|#)|"
                    r"medicaid\s*(?:id|#|no\.?)?|cin)\s*[:#\-]?\s*([A-Z0-9\-]{5,20})"
                ),
                r"\1: [REDACTED_ID]",
                "regex_id",
                2,
            ),
            (
                re.compile(r"(?<!\d)\d{3}[ \t\-]{0,2}\d{3}[ \t\-]{0,2}\d{3}(?!\d)"),
                "[REDACTED_ID]",
                "regex_nyc_9digit_id",
                0,
            ),
            (
                re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
                "[REDACTED_SSN]",
                "regex_ssn",
                0,
            ),
            (
                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
                "[REDACTED_EMAIL]",
                "regex_email",
                0,
            ),
            (
                re.compile(
                    r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
                ),
                "[REDACTED_PHONE]",
                "regex_phone",
                0,
            ),
            (
                re.compile(
                    r"\b\d{1,5}\s+[A-Za-z0-9.\s]{2,30}\s+"
                    r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|"
                    r"Drive|Dr\.?|Lane|Ln\.?|Court|Ct\.?|Place|Pl\.?|Terrace|Way)\b",
                    re.IGNORECASE,
                ),
                "[REDACTED_ADDRESS]",
                "regex_address",
                0,
            ),
        ]

    def _record(self, category: str, count: int = 1):
        if count > 0:
            self.audit_counts[category] = self.audit_counts.get(category, 0) + count

    def _get_person_tag(self, raw_name: str) -> str:
        norm = re.sub(r"\s+", " ", raw_name.strip()).lower()
        if norm not in self.person_map:
            idx = len(self.person_map) + 1
            self.person_map[norm] = f"[PERSON_{idx}]"
        return self.person_map[norm]

    def redact_text_with_matches(self, text: str) -> Tuple[str, Set[str]]:
        matched_strings: Set[str] = set()

        for pattern, tag, cat in self.blocklist_rules:
            for m in pattern.finditer(text):
                matched_strings.add(m.group(0))
            text, n = pattern.subn(tag, text)
            self._record(cat, n)

        for pattern, repl, cat, grp_idx in self.regex_rules:
            for m in pattern.finditer(text):
                matched_strings.add(m.group(grp_idx))
            text, n = pattern.subn(repl, text)
            self._record(cat, n)

        protected_spans = [
            (m.start(), m.end()) for m in re.finditer(r"\[[A-Z0-9_]+\]", text)
        ]

        doc = self.nlp(text)
        replacements = []

        for ent in doc.ents:
            if ent.label_ != "PERSON":
                continue
            if any(not (ent.end_char <= s or ent.start_char >= e) for s, e in protected_spans):
                continue

            clean_ent = ent.text.strip()
            if len(clean_ent) < 3 or any(ch.isdigit() for ch in clean_ent):
                continue
            if clean_ent.lower() in SAFE_ALLOWLIST:
                continue
            if any(tok.lower() in SAFE_ALLOWLIST for tok in re.split(r"[\s\-/]+", clean_ent)):
                continue

            matched_strings.add(clean_ent)
            tag = self._get_person_tag(clean_ent)
            replacements.append((ent.start_char, ent.end_char, tag))

        for start, end, tag in sorted(replacements, key=lambda x: x[0], reverse=True):
            text = text[:start] + tag + text[end:]
            self._record("ner_person", 1)

        return text, matched_strings

    def redact_text(self, text: str) -> str:
        clean, _ = self.redact_text_with_matches(text)
        return clean


def _ocr_and_redact_scanned_page(
    page: pymupdf.Page, redactor: LocalRedactor
) -> Tuple[str, bytes]:
    """Render a scanned page to crisp white-background RGB, run RapidOCR, and draw black boxes."""
    pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csRGB, alpha=False)
    png_bytes = pix.tobytes("png")
    pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

    ocr = load_ocr_engine()
    if ocr is None:
        return "[OCR unavailable: install rapidocr-onnxruntime]", png_bytes

    ocr_result, _ = ocr(png_bytes)
    if not ocr_result:
        return "", png_bytes

    draw = ImageDraw.Draw(pil_img)
    clean_lines = []

    for item in ocr_result:
        box, line_text, _score = item
        clean_line, matched = redactor.redact_text_with_matches(line_text)
        clean_lines.append(clean_line)

        if matched:
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            draw.rectangle([min(xs) - 2, min(ys) - 2, max(xs) + 2, max(ys) + 2], fill=(0, 0, 0))

    out_buf = io.BytesIO()
    pil_img.save(out_buf, format="PNG")
    return "\n".join(clean_lines), out_buf.getvalue()


def discover_pii_candidates(pdf_bytes_list: List[bytes]) -> Dict[str, List[str]]:
    """Locally scan first 2 pages of uploaded PDFs (with OCR fallback) to suggest PII."""
    nlp = load_spacy_model()
    ocr = load_ocr_engine()
    people, schools, ids = set(), set(), set()

    for pdf_bytes in pdf_bytes_list:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        chunks = []
        for page in doc[:2]:
            txt = page.get_text("text", sort=True)
            if len(txt.strip()) < 40 and ocr is not None:
                pix = page.get_pixmap(dpi=130, colorspace=pymupdf.csRGB, alpha=False)
                ocr_res, _ = ocr(pix.tobytes("png"))
                if ocr_res:
                    txt = "\n".join(item[1] for item in ocr_res)
            chunks.append(txt)
        sample_text = "\n".join(chunks)

        for m in re.finditer(r"\b(?:P\.?S\.?|I\.?S\.?|M\.?S\.?|H\.?S\.?)\s*\d{1,4}[A-Za-z]?\b", sample_text):
            schools.add(m.group(0).strip())

        for m in re.finditer(r"(?<!\d)\d{3}[ \t\-]{0,2}\d{3}[ \t\-]{0,2}\d{3}(?!\d)", sample_text):
            ids.add(m.group(0).strip())

        spacy_doc = nlp(sample_text[:15000])
        for ent in spacy_doc.ents:
            val = re.sub(r"\s+", " ", ent.text.strip())
            if len(val) < 3 or val.lower() in SAFE_ALLOWLIST:
                continue
            if ent.label_ == "PERSON" and not any(c.isdigit() for c in val):
                people.add(val)
            elif ent.label_ == "ORG" and any(w in val.lower() for w in ("school", "academy", "district", "center")):
                schools.add(val)

    return {
        "people": sorted(people)[:25],
        "schools": sorted(schools)[:15],
        "ids": sorted(ids)[:10],
    }


def redact_pdf_with_visuals(
    pdf_bytes: bytes, doc_id: str, redactor: LocalRedactor
) -> Tuple[str, bytes, int, int]:
    """Scrub text (with local OCR fallback for scans) and burn black boxes into a PDF copy."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    redacted_pages = []
    ocr_pages_count = 0
    scanned_replacements = []

    for idx in range(len(doc)):
        page_num = idx + 1
        page = doc[idx]
        raw_text = page.get_text("text", sort=True)

        if len(raw_text.strip()) < 40:
            ocr_pages_count += 1
            clean_text, redacted_png = _ocr_and_redact_scanned_page(page, redactor)
            redacted_pages.append(f"=== {doc_id} | PAGE {page_num} (OCR) ===\n{clean_text}")
            scanned_replacements.append((idx, redacted_png, page.rect))
        else:
            clean_text, matched_strings = redactor.redact_text_with_matches(raw_text)
            redacted_pages.append(f"=== {doc_id} | PAGE {page_num} ===\n{clean_text}")
            for target in matched_strings:
                t = target.strip()
                if len(t) < 3:
                    continue
                for rect in page.search_for(t):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

    for idx, img_bytes, orig_rect in scanned_replacements:
        doc.delete_page(idx)
        new_page = doc.new_page(pno=idx, width=orig_rect.width, height=orig_rect.height)
        new_page.insert_image(new_page.rect, stream=img_bytes)

    blacked_out_pdf_bytes = doc.tobytes()
    return "\n\n".join(redacted_pages), blacked_out_pdf_bytes, len(doc), ocr_pages_count


def render_pdf_page_png(pdf_bytes: bytes, page_index: int) -> bytes:
    """Render a single PDF page on a guaranteed white RGB background."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    pix = page.get_pixmap(dpi=140, colorspace=pymupdf.csRGB, alpha=False)
    return pix.tobytes("png")


def redact_pymupdf_doc(
    doc: pymupdf.Document, doc_id: str, redactor: LocalRedactor
) -> Tuple[str, int, int]:
    redacted_pages = []
    empty_pages = 0
    for page_num, page in enumerate(doc, start=1):
        raw_text = page.get_text("text", sort=True)
        if len(raw_text.strip()) < 40:
            empty_pages += 1
        clean_text = redactor.redact_text(raw_text)
        redacted_pages.append(f"=== {doc_id} | PAGE {page_num} ===\n{clean_text}")
    return "\n\n".join(redacted_pages), len(doc), empty_pages


def process_pdfs(input_dir: Path, output_dir: Path, config_path: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    redactor = LocalRedactor(config_path=config_path)
    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {input_dir.resolve()}")
        return
    document_map = {}
    for idx, pdf_path in enumerate(pdf_files, start=1):
        doc_id = f"DOC_{idx:03d}"
        safe_stem = build_safe_doc_stem(doc_id, pdf_path.name)
        out_file = output_dir / f"{safe_stem}_REDACTED.txt"
        doc = pymupdf.open(pdf_path)
        full_text, page_count, _ = redact_pymupdf_doc(doc, doc_id, redactor)
        out_file.write_text(full_text, encoding="utf-8")
        document_map[doc_id] = {
            "original_filename_kept_local": pdf_path.name,
            "redacted_output_file": out_file.name,
            "page_count": page_count,
        }
        print(f"Processed: {pdf_path.name} ({page_count} pages) -> {out_file.name}")

    audit_path = output_dir / "_LOCAL_AUDIT_DO_NOT_SHARE.json"
    audit_data = {
        "document_map_kept_local": document_map,
        "redaction_counts": redactor.audit_counts,
        "pseudonym_map_kept_local": redactor.person_map,
    }
    audit_path.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    process_pdfs(
        input_dir=Path("raw_pdfs"),
        output_dir=Path("redacted_output"),
        config_path=Path("pii_config.json"),
    )