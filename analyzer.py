import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Tuple
from dotenv import load_dotenv
from google import genai

load_dotenv()


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY in .env file.")
    return genai.Client(api_key=api_key)


def _extract_json(raw_text: str) -> Dict[str, Any]:
    """Strip markdown code fences if present and parse JSON."""
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    return json.loads(cleaned)


def _run_gemini4_json(prompt: str, preferred_model: str = "gemini-4-neon") -> Tuple[Dict[str, Any], str]:
    """Call Gemini 4 via the Interactions API, falling back to Hydrogen if needed."""
    client = get_client()
    models_to_try = [preferred_model]
    if preferred_model != "gemini-4-hydrogen":
        models_to_try.append("gemini-4-hydrogen")

    last_error = None
    for model_id in models_to_try:
        try:
            interaction = client.interactions.create(
                model=model_id,
                input=prompt,
            )
            parsed = _extract_json(interaction.output_text)
            return parsed, model_id
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Gemini 4 call failed: {last_error}")


def analyze_hearing_records(scrubbed_text: str, model: str = "gemini-4-neon") -> Tuple[Dict[str, Any], str]:
    """Reconcile IEP mandates vs. delivery logs, build chronology, and map UPL-safe prep items."""
    prompt = f"""
You are a Special Education Impartial Hearing Record Organizer helping a pro se parent
prepare for an NYC DOE Impartial Hearing.

STRICT RULES:
1. Ground EVERY claim in an exact citation from the text headers (e.g., "DOC_001 | PAGE 4").
2. Never invent dates, missed minutes, or diagnoses. If records are incomplete or unclear, state "Insufficient record data".
3. Do NOT give formal legal advice or tell the parent what legal strategy to choose. Frame issues as factual discrepancies, procedural timeline checks, and neutral IDEA/NYC prep items.
4. Return ONLY valid JSON matching the exact schema below.

JSON SCHEMA:
{{
  "documents_detected": [
    {{
      "doc_id": "DOC_001",
      "doc_type": "IEP | Evaluation | FBA/BIP | Service Log | PWN | Transcript/FOFD | Correspondence | Other",
      "date_range": "string",
      "summary": "1-2 sentence factual summary"
    }}
  ],
  "service_gaps": [
    {{
      "service_name": "e.g., Speech Therapy, OT, BCBA Supervision, SETSS, Paraprofessional",
      "mandated_on_iep": "exact frequency/duration/group size or 'Not specified in uploaded docs'",
      "delivered_or_observed": "what logs/progress reports actually show",
      "gap_assessment": "quantified gap or discrepancy, or 'Needs service logs to verify'",
      "severity": "High | Medium | Low | Needs Verification",
      "citation": "DOC_XXX | PAGE Y"
    }}
  ],
  "chronology": [
    {{
      "date": "YYYY-MM-DD or text date",
      "event": "factual description",
      "category": "IEP Meeting | Evaluation | Service Delivery | PWN/Notice | Procedural Milestone",
      "citation": "DOC_XXX | PAGE Y"
    }}
  ],
  "procedural_and_fape_checks": [
    {{
      "issue_area": "e.g., Unimplemented Mandate / Compensatory Ed, Missing Evaluation/FBA, Progress Stagnation, PWN/Notice Gap",
      "factual_basis": "specific discrepancy observed in records",
      "citation": "DOC_XXX | PAGE Y"
    }}
  ],
  "upl_safe_prep_prompts": [
    {{
      "topic": "short label",
      "fact_question_or_exhibit_note": "neutral question to clarify the record or exhibit to include",
      "citation": "DOC_XXX | PAGE Y"
    }}
  ]
}}

SCRUBBED RECORDS:
{scrubbed_text}
"""
    return _run_gemini4_json(prompt, preferred_model=model)


def reverse_engineer_fofd(scrubbed_transcript_and_fofd: str, model: str = "gemini-4-neon") -> Tuple[Dict[str, Any], str]:
    """Reverse-engineer what the IHO relied upon in a past Transcript/FOFD and draft a teaching storyboard."""
    prompt = f"""
You are a Special Education Advocacy Educator. Analyze this scrubbed past Impartial Hearing
Transcript and/or Findings of Fact and Decision (FOFD). Reverse-engineer what actually
persuaded (or concerned) the Impartial Hearing Officer (IHO), and create a 3-scene teaching
storyboard for a short parent explainer video.

STRICT RULES:
1. Ground every finding in an exact citation ("DOC_XXX | PAGE Y").
2. Keep all anonymized tags like [STUDENT] or [PERSON_1] intact—never attempt to guess names.
3. Return ONLY valid JSON matching the exact schema below.

JSON SCHEMA:
{{
  "case_outcome_summary": "2-3 sentence plain-English summary of what happened and why",
  "what_the_iho_found_decisive": [
    {{
      "factor": "short title",
      "why_it_mattered": "how the IHO weighed this testimony, log, or exhibit",
      "citation": "DOC_XXX | PAGE Y"
    }}
  ],
  "video_storyboard": [
    {{
      "scene_number": 1,
      "slide_title": "max 8 words",
      "key_takeaway": "max 20 words for on-screen slide card",
      "evidence_citation": "DOC_XXX | PAGE Y",
      "narration_script": "25-35 words of clear, spoken narration (approx 10-12 seconds)",
      "visual_prompt": "clean editorial motion-graphics scene matching the slide card, calm courtroom/education theme, no garbled text"
    }}
  ]
}}

SCRUBBED TRANSCRIPT / FOFD:
{scrubbed_transcript_and_fofd}
"""
    return _run_gemini4_json(prompt, preferred_model=model)


if __name__ == "__main__":
    redacted_dir = Path("redacted_output")
    txt_files = sorted(redacted_dir.glob("*_REDACTED.txt"))
    if not txt_files:
        print("No *_REDACTED.txt files found in redacted_output/. Run redact_local.py first.")
    else:
        sample_file = txt_files[0]
        content = sample_file.read_text(encoding="utf-8")
        print(f"Testing Gemini 4 on {sample_file.name} ({len(content):,} chars)...")
        result, used_model = analyze_hearing_records(content)
        print(f"Success! Responded using model: {used_model}")
        print(json.dumps(result, indent=2)[:2000])