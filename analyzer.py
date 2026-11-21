import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY in .env file.")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=90_000),
    )


def _extract_json(raw_text: str) -> Dict[str, Any]:
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    return json.loads(cleaned)


def _call_gemini4_json(model_id: str, contents: Any) -> Tuple[Dict[str, Any], float]:
    client = get_client()
    t0 = time.time()
    print(f"  -> Calling {model_id} (thinking_level=low, JSON mode)...", flush=True)
    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )
    elapsed = time.time() - t0
    print(f"  -> {model_id} finished in {elapsed:.1f}s", flush=True)
    return _extract_json(response.text), elapsed


def run_hydrogen_visual_pass(page_images: List[Tuple[str, bytes]]) -> Dict[str, Any]:
    """Job 1 (gemini-4-hydrogen): Inspect blacked-out PDF page images directly for checkboxes, tables, and contradictions."""
    if not page_images:
        return {"visual_observations": [], "checkbox_contradictions": [], "elapsed_s": 0.0}

    prompt = """
You are inspecting redacted special education PDF page images directly.
Look closely at visual checkboxes ([X], Yes/No circled/marked), multi-column IEP service grids,
and score tables that plain text extraction often scrambles.

Return ONLY JSON:
{
  "visual_observations": [
    {"page_label": "DOC_XXX | PAGE Y", "finding": "what is visually shown in table/checkboxes"}
  ],
  "checkbox_contradictions": [
    {"description": "e.g., Special Factors marks Yes for BIP while Summary marks No", "citation": "DOC_XXX | PAGE Y"}
  ]
}
"""
    parts: List[Any] = [prompt]
    for label, png_bytes in page_images[:6]:
        parts.append(f"Image label: {label}")
        parts.append(types.Part.from_bytes(data=png_bytes, mime_type="image/png"))

    data, elapsed = _call_gemini4_json("gemini-4-hydrogen", parts)
    data["elapsed_s"] = round(elapsed, 1)
    return data


def run_neon_parent_coaching_pass(
    scrubbed_text: str, visual_findings: Dict[str, Any]
) -> Tuple[Dict[str, Any], float]:
    """Job 2 (gemini-4-neon): Reconcile records against NYC DOE SOPM / NYSED Part 200 & write parent-friendly guidance."""
    prompt = f"""
You are a calm, deeply knowledgeable NYC Special Education Parent Coach helping an exhausted pro se
parent understand their records and prepare for an NYC OATH Impartial Hearing.

GROUNDING REFERENCES (cite accurately where relevant, never invent rules):
- IDEA FAPE & Endrew F. (educational progress appropriate in light of the child's circumstances; high grades/IQ do NOT disqualify behavioral/executive functioning or related services).
- NYSED 8 NYCRR § 200.4 & NYC DOE Standard Operating Procedures Manual (SOPM): CSE must address all documented evaluation needs (including executive functioning, adaptive deficits, DCD/OT, dyslexia/structured literacy), maintain mandatory triennial evaluations (every 3 years), and issue clear Prior Written Notice (PWN) explaining why parent-requested services were refused.
- NYSED 8 NYCRR § 200.22: FBA & BIP required when behavior (including non-aggressive task avoidance, freezing, or emotional shutdowns) impedes learning.
- NYC OATH Special Education Hearings Division: 30-day resolution period, 5-business-day evidence disclosure deadline, Exhibit labeling (Parent: A-1, B-1; District: 1-1, 2-1), District bears burden on FAPE, Parent bears burden on appropriateness/rate of requested private provider, and Pendency / Compensatory Education remedies for missed mandated sessions.

STRICT RULES:
1. Write in warm, clear, parent-level plain English (avoid dense legal jargon; explain any rule simply).
2. Ground EVERY claim in exact citations from the headers ("DOC_XXX | PAGE Y").
3. Never invent numbers, missed sessions, or dates.
4. Keep UPL-safe framing: organize facts, gaps, rules, and "arguments/points to document and share" (not formal legal representation).
5. Return ONLY valid JSON matching the exact schema below.

JSON SCHEMA:
{{
  "case_snapshot": "2-3 warm, plain-English sentences summarizing the child's profile and the main issue.",
  "priority_findings": [
    {{
      "priority": "High | Medium",
      "title": "short, clear parent-friendly headline",
      "what_doe_promised_or_said": "plain English summary of IEP mandate or DOE refusal",
      "what_records_actually_show": "exact contradiction, missed minutes, or clinical score gap",
      "why_it_matters_nyc_rules": "simple explanation referencing IDEA / Part 200 / NYC DOE SOPM",
      "citation": "DOC_XXX | PAGE Y"
    }}
  ],
  "arguments_to_document": [
    {{
      "argument_title": "clear point for parent to make",
      "plain_english_explanation": "how to explain this clearly to an IHO without legal jargon",
      "what_to_document_and_share": "concrete records, emails, homework logs, or exhibits to gather next",
      "citation": "DOC_XXX | PAGE Y"
    }}
  ],
  "oath_readiness": {{
    "hearing_and_disclosure_notes": "deadlines, resolution period status, triennial status, or 'Not specified in records'",
    "burden_of_proof_reminder": "what DOE must prove vs. what parent must document (e.g. provider rate/appropriateness)",
    "exhibit_checklist": [
      {{"suggested_label": "Exhibit A", "document_id": "DOC_001", "why_include": "1-sentence reason"}}
    ]
  }},
  "parent_briefing_storyboard": [
    {{
      "scene_number": 1,
      "slide_title": "max 8 words (Scene 1: Key Gaps Found; Scene 2: Why NYC Rules Matter; Scene 3: What to Document & Argue)",
      "key_takeaway": "max 20 words in warm parent-friendly English",
      "evidence_citation": "DOC_XXX | PAGE Y",
      "narration_script": "25-35 words of warm, empowering spoken narration explaining the gap or argument at a parent level",
      "visual_prompt": "clean editorial motion-graphics card, calm civic navy and warm paper tones, no garbled text"
    }}
  ]
}}

VISUAL CHECKBOX/TABLE OBSERVATIONS (from Gemini 4 Hydrogen):
{json.dumps(visual_findings, indent=2)}

SCRUBBED RECORDS TEXT:
{scrubbed_text}
"""
    return _call_gemini4_json("gemini-4-neon", prompt)


def run_carbon_citation_audit(
    scrubbed_text: str, neon_output: Dict[str, Any]
) -> Tuple[Dict[str, Any], float]:
    """Job 3 (gemini-4-carbon): 5-Sigma independent auditor verifying every Neon claim & citation against source text."""
    claims_to_check = {
        "priority_findings": neon_output.get("priority_findings", []),
        "arguments_to_document": neon_output.get("arguments_to_document", []),
    }
    prompt = f"""
You are a strict 5-Sigma Fact & Citation Auditor. Compare the draft findings below against the
SCRUBBED RECORDS TEXT. Check whether every quoted number, score, missed session count, and
"DOC_XXX | PAGE Y" citation actually exists in the text.

Return ONLY valid JSON:
{{
  "total_claims_checked": 0,
  "verified_claims_count": 0,
  "verification_score_pct": 100,
  "flagged_discrepancies": [
    {{"claim_title": "string", "issue": "what could not be verified or wrong page number"}}
  ],
  "auditor_summary": "1-2 sentence reliability verdict"
}}

DRAFT FINDINGS TO AUDIT:
{json.dumps(claims_to_check, indent=2)}

SCRUBBED RECORDS TEXT:
{scrubbed_text}
"""
    return _call_gemini4_json("gemini-4-carbon", prompt)


def analyze_hearing_records(
    scrubbed_text: str, page_images: Optional[List[Tuple[str, bytes]]] = None
) -> Dict[str, Any]:
    """Full 3-Model Gemini 4 Pipeline: Hydrogen (Visual) -> Neon (NYC DOE Coaching) -> Carbon (5-Sigma Audit)."""
    visual_data = run_hydrogen_visual_pass(page_images or [])
    neon_data, neon_s = run_neon_parent_coaching_pass(scrubbed_text, visual_data)

    try:
        carbon_audit, carbon_s = run_carbon_citation_audit(scrubbed_text, neon_data)
    except Exception as exc:
        carbon_audit = {
            "total_claims_checked": len(neon_data.get("priority_findings", [])),
            "verified_claims_count": len(neon_data.get("priority_findings", [])),
            "verification_score_pct": 0,
            "flagged_discrepancies": [{"claim_title": "Carbon Audit", "issue": str(exc)}],
            "auditor_summary": f"Carbon audit skipped: {exc}",
        }
        carbon_s = 0.0

    return {
        "analysis": neon_data,
        "visual_findings": visual_data,
        "carbon_audit": carbon_audit,
        "telemetry": {
            "hydrogen_visual_s": visual_data.get("elapsed_s", 0.0),
            "neon_reasoning_s": round(neon_s, 1),
            "carbon_audit_s": round(carbon_s, 1),
        },
    }


def reverse_engineer_fofd(scrubbed_transcript_and_fofd: str) -> Tuple[Dict[str, Any], str]:
    """Optional mode: Reverse-engineer what an IHO relied upon in a past Transcript/FOFD."""
    prompt = f"""
Analyze this scrubbed Impartial Hearing Transcript / FOFD. Reverse-engineer what swayed the IHO
and create a 3-scene parent-friendly teaching storyboard. Return ONLY JSON:
{{
  "case_outcome_summary": "2-3 plain-English sentences",
  "what_the_iho_found_decisive": [
    {{"factor": "short title", "why_it_mattered": "plain English explanation", "citation": "DOC_XXX | PAGE Y"}}
  ],
  "video_storyboard": [
    {{
      "scene_number": 1,
      "slide_title": "max 8 words",
      "key_takeaway": "max 20 words",
      "evidence_citation": "DOC_XXX | PAGE Y",
      "narration_script": "25-35 words warm parent narration",
      "visual_prompt": "clean editorial motion-graphics card, calm civic navy theme"
    }}
  ]
}}

SCRUBBED TRANSCRIPT / FOFD:
{scrubbed_transcript_and_fofd}
"""
    data, _ = _call_gemini4_json("gemini-4-neon", prompt)
    return data, "gemini-4-neon"