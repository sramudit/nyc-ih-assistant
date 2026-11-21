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


def run_decisions_api_triage(scrubbed_text: str) -> Dict[str, Any]:
    """Job 0 (Decisions API + gemini-decision-1 on v1alpha): Calibrated triage & FAPE severity scoring."""
    api_key = os.getenv("GEMINI_API_KEY")
    v1alpha_client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1alpha", timeout=60_000),
    )
    t0 = time.time()
    print("  -> Calling Decisions API (gemini-decision-1, v1alpha)...", flush=True)

    packet_res = v1alpha_client.decisions.create(
        model="gemini-decision-1",
        api_version="v1alpha",
        input=scrubbed_text[:18000],
        questions={
            "escalation_track": {
                "type": "choice",
                "instructions": "Select the primary NYC DOE OATH impartial hearing escalation track supported by these records.",
                "criteria": {
                    "COMP_ED_AND_LBA_ESCALATION": "Missed mandated services (e.g. SETSS/OT/Speech) and/or denied BCBA/LBA support despite clinical need.",
                    "PROCEDURAL_EVAL_OR_PWN_GAP": "Overdue triennial evaluation, missing PWN rationale, or unaddressed private neuropsych report.",
                    "ROUTINE_IEP_MONITORING": "All mandated services delivered and evaluations current with no material FAPE gap.",
                },
            },
            "part_200_trigger": {
                "type": "choice",
                "instructions": "Check whether NYSED 8 NYCRR 200.22 (FBA/BIP) or 200.4 (Triennial Eval) statutory triggers appear.",
                "criteria": {
                    "FBA_BIP_CONTRADICTION_OR_MISSING": "IEP marks Yes/needs behavior/executive support yet omits BIP, marks No, or lacks FBA.",
                    "OVERDUE_TRIENNIAL_EVAL": "Records state mandatory 3-year DOE re-evaluation has not been completed on time.",
                    "NO_STATUTORY_TRIGGER": "No FBA/BIP contradiction or overdue triennial evaluation documented.",
                },
            },
            "fape_risk_score": {
                "type": "score",
                "instructions": "Score overall FAPE denial / compensatory education risk from 0 (none) to 3 (severe).",
                "criteria": [
                    "0 - No documented service gap or procedural violation",
                    "1 - Minor documentation gap without clear service loss",
                    "2 - Moderate gap: missed sessions or unaddressed evaluation recommendations",
                    "3 - Severe FAPE risk: significant missed mandated hours, IEP contradictions, or denied core supports",
                ],
            },
        },
    )

    ans = packet_res.answers
    esc = ans["escalation_track"]
    trig = ans["part_200_trigger"]
    sev = ans["fape_risk_score"]

    doc_chunks = re.split(r"(?==== DOC_\d+ \| PAGE 1 )", scrubbed_text)
    doc_routes = []
    for chunk in [c for c in doc_chunks if c.strip()][:6]:
        doc_match = re.search(r"===\s*(DOC_\d+)", chunk)
        doc_id = doc_match.group(1) if doc_match else "DOC"
        d_res = v1alpha_client.decisions.create(
            model="gemini-decision-1",
            api_version="v1alpha",
            input=chunk[:4000],
            questions={
                "doc_type": {
                    "type": "choice",
                    "instructions": "Classify this NYC special education document.",
                    "criteria": {
                        "IEP_MANDATE_RECORD": "Individualized Education Program listing present levels, goals, or service mandates.",
                        "NEUROPSYCH_OR_CLINICAL_EVAL": "Psychological, neuropsychological, or educational testing evaluation report.",
                        "SERVICE_LOG_OR_PWN": "Related-service/SETSS attendance delivery audit or Prior Written Notice (PWN).",
                        "OATH_TRANSCRIPT_OR_FOFD": "Impartial Hearing transcript, conference order, or Findings of Fact and Decision (FOFD).",
                    },
                },
                "doc_urgency": {
                    "type": "score",
                    "instructions": "Rate how critical this document is as a primary hearing exhibit (0=background, 3=decisive).",
                    "criteria": ["0 Background", "1 Supporting", "2 Important", "3 Decisive Exhibit"],
                },
            },
        )
        d_ans = d_res.answers
        doc_routes.append({
            "doc_id": doc_id,
            "route": d_ans["doc_type"].choice,
            "route_confidence": round(d_ans["doc_type"].confidence * 100, 1),
            "exhibit_priority_score": round(d_ans["doc_urgency"].score, 2),
        })

    elapsed = round(time.time() - t0, 2)
    print(f"  -> Decisions API finished in {elapsed}s", flush=True)
    return {
        "escalation_track": esc.choice,
        "escalation_confidence_pct": round(esc.confidence * 100, 1),
        "escalation_probabilities": {k: round(v * 100, 1) for k, v in esc.probabilities.items()},
        "part_200_trigger": trig.choice,
        "part_200_confidence_pct": round(trig.confidence * 100, 1),
        "fape_risk_score": round(sev.score, 2),
        "fape_risk_confidence_pct": round(sev.confidence * 100, 1),
        "document_routes": doc_routes,
        "elapsed_s": elapsed,
    }


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
      "slide_title": "max 6 words",
      "key_takeaway": "max 10 words in warm parent-friendly English",
      "evidence_citation": "DOC_XXX | PAGE Y",
      "narration_script": "18-24 words of warm spoken narration explaining the gap or argument cleanly",
      "visual_prompt": "minimalist deep blue and warm cream legal education graphics, bold large headings, school and scales icons only, NO ear or medical icons, zero small body text"
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
    """Full Pipeline: Decisions API (gemini-decision-1) -> Hydrogen (Visual) -> Neon (Coach) -> Carbon (Audit)."""
    decisions_triage = run_decisions_api_triage(scrubbed_text)
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
        "decisions_triage": decisions_triage,
        "analysis": neon_data,
        "visual_findings": visual_data,
        "carbon_audit": carbon_audit,
        "telemetry": {
            "decisions_api_s": decisions_triage.get("elapsed_s", 0.0),
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
      "slide_title": "max 6 words",
      "key_takeaway": "max 10 words",
      "evidence_citation": "DOC_XXX | PAGE Y",
      "narration_script": "18-24 words warm parent narration",
      "visual_prompt": "minimalist deep blue and warm cream legal education graphics, bold large headings, school and scales icons only, NO ear or medical icons, zero small body text"
    }}
  ]
}}

SCRUBBED TRANSCRIPT / FOFD:
{scrubbed_transcript_and_fofd}
"""
    data, _ = _call_gemini4_json("gemini-4-neon", prompt)
    return data, "gemini-4-neon"


def generate_omni_storyboard_beats(analysis_dict: Dict[str, Any], num_clips: int = 6) -> List[Dict[str, Any]]:
    """Create N cohesive 14-second Omni 1.2 Flash beats covering gaps, NYC rules, and parent arguments."""
    prompt = f"""
Turn these verified NYC special education case findings into {num_clips} sequential
14-second explainer video scenes for a stressed pro se parent.

Cover the full arc across the {num_clips} scenes:
- Early scenes: Key Gaps Found (include bold concrete numbers like missed minutes or contradictions)
- Middle scenes: Why NYC DOE / IDEA / Part 200 Rules Protect Your Child
- Final scenes: Exact Arguments & Exhibits to Document Before Hearing

CRITICAL RULES FOR GENERATIVE VIDEO QUALITY:
1. slide_title: MAX 5 words (short bold headline).
2. key_takeaway: MAX 9 words (short bold phrase; NO tiny paragraphs that warp in AI video).
3. narration_script: STRICTLY 18-24 words of warm, parent-level spoken English so it finishes cleanly inside 14 seconds.
4. visual_prompt: "minimalist deep blue and warm cream legal education graphics, bold large headings, school and scales icons only, NO ear or medical icons, zero small body text"

Return ONLY valid JSON:
{{
  "beats": [
    {{
      "scene_number": 1,
      "slide_title": "max 5 words",
      "key_takeaway": "max 9 words",
      "evidence_citation": "DOC_XXX | PAGE Y",
      "narration_script": "18-24 words warm spoken narration",
      "visual_prompt": "minimalist deep blue and warm cream legal education graphics, bold large headings, school and scales icons only, NO ear or medical icons, zero small body text"
    }}
  ]
}}

VERIFIED CASE FINDINGS:
{json.dumps(analysis_dict, indent=2)}
"""
    data, _ = _call_gemini4_json("gemini-4-neon", prompt)
    return data.get("beats", [])


def generate_3min_guide_script(analysis_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Expand Tab 2 & 3 findings into a comprehensive 3-minute (3 x 1-min) parent briefing script."""
    prompt = f"""
You are creating a warm, clear, comprehensive 3-minute spoken Parent Briefing Video
based on the verified case findings below.

Create:
1. One 12-second animated intro prompt for Gemini Omni 1.2 Flash.
2. Exactly 3 comprehensive 1-minute segments:
   - Segment 1: Key Service & Support Gaps Found in Your Records
   - Segment 2: Why NYC DOE & IDEA Rules Protect Your Child Here
   - Segment 3: Arguments to Document and Gather Before Your Hearing

Each segment MUST contain 3 slide cards (~45 words of narration per slide = ~135 words / ~55-60 seconds per segment).
Return ONLY valid JSON:
{{
  "intro_hook": {{
    "slide_title": "NYC Special Ed Briefing",
    "key_takeaway": "Your IEP gaps, NYC rules, and next steps.",
    "evidence_citation": "Case Overview",
    "narration_script": "14-18 words max welcoming the parent to their NYC Special Education hearing briefing.",
    "visual_prompt": "minimalist deep blue and warm cream legal education graphics, bold large headings, school and scales icons only, NO ear or medical icons, zero small body text"
  }},
  "segments": [
    {{
      "segment_number": 1,
      "segment_title": "Key Gaps Found in Your Records",
      "slides": [
        {{
          "slide_title": "max 8 words",
          "bullets": ["short bullet 1 (max 12 words)", "short bullet 2 (max 12 words)", "short bullet 3 (max 12 words)"],
          "citation": "DOC_XXX | PAGE Y",
          "narration": "40-50 words of warm, clear parent-level explanation covering the details on this slide."
        }}
      ]
    }}
  ]
}}

VERIFIED CASE FINDINGS:
{json.dumps(analysis_dict, indent=2)}
"""
    data, _ = _call_gemini4_json("gemini-4-neon", prompt)
    return data