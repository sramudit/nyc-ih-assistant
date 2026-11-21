import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
import pymupdf  # Modern import for PyMuPDF (runs 100% locally)
import spacy

# Clinical tests, special-ed acronyms, and terms spaCy sometimes mis-tags as PERSON/ORG
SAFE_ALLOWLIST = {
    "idea", "fape", "iep", "pwn", "fba", "bip", "iho", "cse", "cpse", "mdr",
    "setss", "ict", "ot", "pt", "slp", "aba", "lre", "esy", "rti", "mtss",
    "wisc", "wisc-v", "wiat", "wiat-4", "woodcock", "johnson", "woodcock-johnson",
    "vineland", "basc", "basc-3", "conners", "ados", "ados-2", "kaufman",
    "celf", "celf-5", "gort", "towre", "berry", "vmi", "bot-2", "pdms",
    "ferpa", "hipaa", "section 504", "sesis", "sped", "adhd", "asd"
}

# Only these safe document-type words may appear in anonymized output filenames
SAFE_DOC_TYPE_TOKENS = {
    "iep", "pwn", "fba", "bip", "eval", "evaluation", "psych", "neuropsych",
    "speech", "therapy", "bcba", "aba", "progress", "attendance", "log",
    "logs", "notes", "notice", "ihr", "complaint", "dpc", "decision", "order",
    "sesis", "amendment", "report", "transcript", "exhibit", "fofd"
}

TITLE_SKIP = {"mr", "mrs", "ms", "miss", "dr", "prof", "jr", "sr", "ii", "iii", "iv"}


def load_spacy_model():
    for model_name in ("en_core_web_md", "en_core_web_sm"):
        try:
            return spacy.load(model_name)
        except OSError:
            continue
    raise RuntimeError(
        "No spaCy English model found. Run: python -m spacy download en_core_web_md"
    )


def build_safe_doc_stem(doc_id: str, original_filename: str) -> str:
    """Create a leak-proof filename like DOC_001_TRANSCRIPT using only safe keywords."""
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

        # Layer 1: Exact blocklist + auto-split & spelled-out transcript catchers
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
        }

        for key, tag in category_tags.items():
            entries = list(self.config.get(key, []))

            # For student & parent names, also add standalone first/last tokens
            expanded_entries = list(entries)
            if key in ("student_names", "parent_names"):
                for item in entries:
                    for part in re.split(r"[\s\-]+", item.strip()):
                        clean_part = re.sub(r"[^A-Za-z]", "", part)
                        if len(clean_part) >= 3 and clean_part.lower() not in TITLE_SKIP:
                            expanded_entries.append(clean_part)

            # Deduplicate preserving longest-first order
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

                # Catch spelled-out letters in transcripts (e.g., S-M-I-T-H or S M I T H)
                if key in ("student_names", "parent_names") and item.isalpha() and len(item) >= 3:
                    spelled = r"[\s\-.,/]+".join(re.escape(ch) for ch in item)
                    spelled_pattern = re.compile(
                        rf"(?<![A-Za-z0-9]){spelled}(?![A-Za-z0-9])",
                        re.IGNORECASE,
                    )
                    self.blocklist_rules.append((spelled_pattern, tag, f"{key}_spelled"))

        # Layer 2: Special-Ed & PII Regexes (preserves service/IEP dates!)
        self.regex_rules = [
            (
                re.compile(
                    r"(?i)\b(d\.?o\.?b\.?|date\s+of\s+birth|birth\s*date)\s*[:#\-]?\s*"
                    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})"
                ),
                r"\1: [REDACTED_DOB]",
                "regex_dob",
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
            ),
           # Catch standalone 9-digit NYC OSIS / NYC IDs (123456789, 123 456 789, or 123-456-789)
            (
                re.compile(r"(?<!\d)\d{3}[ \t\-]?\d{3}[ \t\-]?\d{3}(?!\d)"),
                "[REDACTED_ID]",
                "regex_nyc_9digit_id",
            ),
            
            (
                re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
                "[REDACTED_SSN]",
                "regex_ssn",
            ),
            (
                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
                "[REDACTED_EMAIL]",
                "regex_email",
            ),
            (
                re.compile(
                    r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
                ),
                "[REDACTED_PHONE]",
                "regex_phone",
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

    def redact_text(self, text: str) -> str:
        for pattern, tag, cat in self.blocklist_rules:
            text, n = pattern.subn(tag, text)
            self._record(cat, n)

        for pattern, repl, cat in self.regex_rules:
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

            tag = self._get_person_tag(clean_ent)
            replacements.append((ent.start_char, ent.end_char, tag))

        for start, end, tag in sorted(replacements, key=lambda x: x[0], reverse=True):
            text = text[:start] + tag + text[end:]
            self._record("ner_person", 1)

        return text


def redact_pymupdf_doc(
    doc: pymupdf.Document, doc_id: str, redactor: LocalRedactor
) -> Tuple[str, int, int]:
    """Reusable helper for both CLI batch runs and Streamlit in-memory uploads."""
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

    scanned_warnings = []
    document_map = {}

    for idx, pdf_path in enumerate(pdf_files, start=1):
        doc_id = f"DOC_{idx:03d}"
        safe_stem = build_safe_doc_stem(doc_id, pdf_path.name)
        out_file = output_dir / f"{safe_stem}_REDACTED.txt"

        doc = pymupdf.open(pdf_path)
        full_text, page_count, empty_pages = redact_pymupdf_doc(doc, doc_id, redactor)
        out_file.write_text(full_text, encoding="utf-8")

        document_map[doc_id] = {
            "original_filename_kept_local": pdf_path.name,
            "redacted_output_file": out_file.name,
            "page_count": page_count,
        }

        print(f"Processed: {pdf_path.name} ({page_count} pages) -> {out_file.name}")

        if empty_pages > 0:
            scanned_warnings.append((doc_id, pdf_path.name, empty_pages, page_count))

    audit_path = output_dir / "_LOCAL_AUDIT_DO_NOT_SHARE.json"
    audit_data = {
        "document_map_kept_local": document_map,
        "redaction_counts": redactor.audit_counts,
        "pseudonym_map_kept_local": redactor.person_map,
    }
    audit_path.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")

    print("\n--- Redaction Summary ---")
    for k, v in sorted(redactor.audit_counts.items()):
        print(f"  {k}: {v}")

    if scanned_warnings:
        print("\n[!] WARNING: Possible scanned/image pages detected (no selectable text):")
        for doc_id, fname, empty, total in scanned_warnings:
            print(f"  - {doc_id} ({fname}): {empty}/{total} pages had <40 chars.")
        print("  Run local OCR first with: ocrmypdf input.pdf output_ocr.pdf")


if __name__ == "__main__":
    process_pdfs(
        input_dir=Path("raw_pdfs"),
        output_dir=Path("redacted_output"),
        config_path=Path("pii_config.json"),
    )