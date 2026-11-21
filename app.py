import json
from pathlib import Path
import streamlit as st
from analyzer import analyze_hearing_records, reverse_engineer_fofd
from demo_packet import build_synthetic_demo_packet
from eval_5sigma import run_full_evaluation
from redact_local import (
    LocalRedactor,
    build_safe_doc_stem,
    discover_pii_candidates,
    redact_pdf_with_visuals,
    render_pdf_page_png,
)
from video_gen import generate_teaching_clip, render_slide_card_png, verify_video_with_gemini4

st.set_page_config(
    page_title="NYC Impartial Hearing Assistant",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ NYC Impartial Hearing Assistant")
st.caption(
    "Privacy-first record organizer & parent coaching tool for NYC DOE Special Education Impartial Hearings. "
    "Real PDFs are scrubbed 100% locally before Gemini 4 (Hydrogen + Neon + Carbon) analyzes anonymized records."
)

defaults = {
    "redacted_docs": [],
    "audit_counts": {},
    "discovered": {},
    "demo_loaded_files": [],
    "verified_safe": False,
    "pipeline_output": None,
    "fofd_override": None,
    "generated_videos": {},
    "video_checks": {},
    "eval_summary": None,
    "student_names": "",
    "parent_names": "",
    "school_names": "",
    "district_names": "NYC DOE",
    "provider_names": "",
    "ids": "",
    "dobs": "",
    "addresses": "",
    "extra_terms": "",
}
for key, default in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default


def split_csv(val: str):
    return [x.strip() for x in val.split(",") if x.strip()]


def build_prep_markdown(pipeline_out: dict) -> str:
    a = pipeline_out.get("analysis", {})
    lines = ["# NYC Impartial Hearing — Parent Prep Guide\n"]
    lines.append(f"**Overview:** {a.get('case_snapshot', '')}\n")
    lines.append("## 1. Priority Gaps Found\n")
    for idx, f in enumerate(a.get("priority_findings", []), start=1):
        lines.append(f"### {idx}. [{f.get('priority')}] {f.get('title')} ({f.get('citation')})")
        lines.append(f"- **What DOE promised/assumed:** {f.get('what_doe_promised_or_assumed')}")
        lines.append(f"- **What records show:** {f.get('what_records_actually_show')}")
        lines.append(f"- **Why it matters (NYC/IDEA rules):** {f.get('why_it_matters_nyc_rules')}\n")
    lines.append("## 2. Arguments to Document & Share\n")
    for idx, arg in enumerate(a.get("arguments_to_document", []), start=1):
        lines.append(f"### {idx}. {arg.get('argument_title')} ({arg.get('citation')})")
        lines.append(f"- **How to explain it:** {arg.get('plain_english_explanation')}")
        lines.append(f"- **What to document next:** {arg.get('what_to_document_and_share')}\n")
    oath = a.get("oath_readiness", {})
    lines.append("## 3. NYC OATH Hearing Readiness\n")
    lines.append(f"- **Deadlines & Notes:** {oath.get('hearing_and_disclosure_notes', '')}")
    lines.append(f"- **Burden of Proof Reminder:** {oath.get('burden_of_proof_reminder', '')}\n")
    for ex in oath.get("exhibit_checklist", []):
        lines.append(f"- **{ex.get('suggested_label')}** ({ex.get('document_id')}): {ex.get('why_include')}")
    return "\n".join(lines)


# Sidebar: Local PII Intake Form
with st.sidebar:
    st.header("🛡️ Local Privacy Config")
    st.caption("Stays strictly on your computer. Separate multiple items with commas.")

    if Path("pii_config.json").exists():
        if st.button("📂 Load My Local pii_config.json", width="stretch"):
            cfg = json.loads(Path("pii_config.json").read_text(encoding="utf-8"))
            for field in (
                "student_names", "parent_names", "school_names",
                "district_names", "provider_names", "ids", "dobs", "addresses",
            ):
                st.session_state[field] = ", ".join(cfg.get(field, []))
            st.rerun()

    st.session_state["student_names"] = st.text_input("Student Name(s)", value=st.session_state["student_names"], placeholder="e.g., Maya Chen")
    st.session_state["parent_names"] = st.text_input("Parent / Guardian Name(s)", value=st.session_state["parent_names"], placeholder="e.g., Grace Chen")
    st.session_state["school_names"] = st.text_input("School Name(s)", value=st.session_state["school_names"], placeholder="e.g., Tech High School")
    st.session_state["district_names"] = st.text_input("District / Agency", value=st.session_state["district_names"])
    st.session_state["provider_names"] = st.text_input("Provider / Evaluator Name(s)", value=st.session_state["provider_names"], placeholder="e.g., Dr. Avery Patel")
    st.session_state["ids"] = st.text_input("Student / OSIS / Case IDs", value=st.session_state["ids"], placeholder="e.g., 901 442 817")
    st.session_state["dobs"] = st.text_input("Date(s) of Birth", value=st.session_state["dobs"], placeholder="e.g., 04/12/2012")
    st.session_state["addresses"] = st.text_input("Street Address(es)", value=st.session_state["addresses"], placeholder="e.g., 100 Example Avenue")
    st.session_state["extra_terms"] = st.text_area(
        "Extra Words to Black Out",
        value=st.session_state["extra_terms"],
        placeholder="Caught a typo, sibling name, or employer in preview? Add here...",
    )

    def build_config_dict():
        return {
            "student_names": split_csv(st.session_state["student_names"]),
            "parent_names": split_csv(st.session_state["parent_names"]),
            "school_names": split_csv(st.session_state["school_names"]),
            "district_names": split_csv(st.session_state["district_names"]),
            "provider_names": split_csv(st.session_state["provider_names"]),
            "ids": split_csv(st.session_state["ids"]),
            "dobs": split_csv(st.session_state["dobs"]),
            "addresses": split_csv(st.session_state["addresses"]),
            "extra_terms": split_csv(st.session_state["extra_terms"]),
        }


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Local Privacy Shield",
    "2️⃣ What We Found (Parent View)",
    "3️⃣ Arguments & OATH Prep",
    "4️⃣ Parent Briefing Video",
    "5️⃣ 5-Sigma Reliability & Eval",
])

# ==================== TAB 1: LOCAL PRIVACY SHIELD ====================
with tab1:
    st.subheader("Step 1: Load PDFs & Scrub Locally")

    demo_col, up_col = st.columns([1, 2])
    with demo_col:
        st.markdown("**Testing / Judge Demo?**")
        if st.button("🧪 Load Realistic NYC Demo Packet", width="stretch"):
            st.session_state["demo_loaded_files"] = build_synthetic_demo_packet()
            st.session_state["student_names"] = "Maya Chen"
            st.session_state["parent_names"] = "Grace Chen"
            st.session_state["school_names"] = "Tech High School"
            st.session_state["district_names"] = "District 99, NYC DOE"
            st.session_state["provider_names"] = "Dr. Avery Patel"
            st.session_state["ids"] = "901 442 817, 901442817, 311994"
            st.session_state["dobs"] = "04/12/2012"
            st.session_state["addresses"] = "100 Example Avenue"
            st.session_state["redacted_docs"] = []
            st.session_state["pipeline_output"] = None
            st.session_state["generated_videos"] = {}
            st.rerun()

    with up_col:
        uploaded_files = st.file_uploader(
            "Or upload your own IEP, Neuropsych, Service Logs, or Transcript PDFs",
            type=["pdf"],
            accept_multiple_files=True,
        )

    if uploaded_files:
        active_files = [(f.name, f.getvalue()) for f in uploaded_files]
    else:
        active_files = st.session_state["demo_loaded_files"]
        if active_files:
            st.info(f"🧪 Synthetic NYC Demo Packet loaded ({len(active_files)} realistic fake PDFs ready to scrub).")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔍 Auto-Discover Names / Schools / OSIS Locally", disabled=not active_files, width="stretch"):
            with st.spinner("Scanning first pages locally with spaCy + OCR..."):
                st.session_state["discovered"] = discover_pii_candidates([b for _, b in active_files])

    if st.session_state["discovered"]:
        disc = st.session_state["discovered"]
        with st.expander("📋 Locally Detected PII Candidates", expanded=True):
            st.write("**People detected:**", ", ".join(disc.get("people", [])) or "None")
            st.write("**Schools detected:**", ", ".join(disc.get("schools", [])) or "None")
            st.write("**9-digit IDs detected:**", ", ".join(disc.get("ids", [])) or "None")
            if st.button("➕ Add All Detected Candidates to 'Extra Words to Black Out'"):
                all_found = disc.get("people", []) + disc.get("schools", []) + disc.get("ids", [])
                existing = split_csv(st.session_state["extra_terms"])
                merged = list(dict.fromkeys(existing + all_found))
                st.session_state["extra_terms"] = ", ".join(merged)
                st.rerun()

    with col_b:
        if st.button("🛡️ Run Local Scrubber & Black Out PDFs", type="primary", disabled=not active_files, width="stretch"):
            with st.spinner("Scrubbing text (with RapidOCR for scans) and burning permanent black boxes..."):
                redactor = LocalRedactor(config_dict=build_config_dict())
                docs_out = []
                for idx, (fname, fbytes) in enumerate(active_files, start=1):
                    doc_id = f"DOC_{idx:03d}"
                    safe_name = build_safe_doc_stem(doc_id, fname)
                    scrubbed_text, blacked_pdf, page_cnt, ocr_cnt = redact_pdf_with_visuals(
                        fbytes, doc_id, redactor
                    )
                    docs_out.append({
                        "doc_id": doc_id,
                        "safe_name": safe_name,
                        "scrubbed_text": scrubbed_text,
                        "blacked_pdf": blacked_pdf,
                        "page_count": page_cnt,
                        "ocr_pages": ocr_cnt,
                    })
                st.session_state["redacted_docs"] = docs_out
                st.session_state["audit_counts"] = redactor.audit_counts
                st.session_state["verified_safe"] = False

    if st.session_state["redacted_docs"]:
        st.success(
            f"Scrubbed {len(st.session_state['redacted_docs'])} document(s) locally! "
            f"Total redactions applied: {sum(st.session_state['audit_counts'].values())}"
        )

        doc_choices = [f"{d['safe_name']} ({d['page_count']} pages)" for d in st.session_state["redacted_docs"]]
        selected_idx = st.selectbox("Inspect Document", range(len(doc_choices)), format_func=lambda i: doc_choices[i])
        selected_doc = st.session_state["redacted_docs"][selected_idx]

        if selected_doc["ocr_pages"] > 0:
            st.info(f"🔍 Local RapidOCR processed {selected_doc['ocr_pages']} scanned page(s) in this document.")

        st.download_button(
            "⬇️ Download Blacked-Out PDF",
            data=selected_doc["blacked_pdf"],
            file_name=f"{selected_doc['safe_name']}_BLACKED_OUT.pdf",
            mime="application/pdf",
        )

        page_num = st.number_input("Page to inspect", min_value=1, max_value=selected_doc["page_count"], value=1)

        left_col, right_col = st.columns(2)
        with left_col:
            st.markdown("**Blacked-Out PDF View**")
            png_bytes = render_pdf_page_png(selected_doc["blacked_pdf"], page_num - 1)
            st.image(png_bytes, width="stretch")

        with right_col:
            st.markdown("**Anonymized Text Sent to Gemini 4**")
            pages_split = selected_doc["scrubbed_text"].split(f"=== {selected_doc['doc_id']} | PAGE ")
            matching_page = next(
                (p for p in pages_split if p.startswith(f"{page_num}")),
                selected_doc["scrubbed_text"][:4000],
            )
            st.text_area("Scrubbed page text", value=matching_page, height=580, label_visibility="collapsed")

        st.divider()
        st.session_state["verified_safe"] = st.checkbox(
            "✅ I verified the blacked-out PDF and scrubbed text contain no personal identifiers.",
            value=st.session_state["verified_safe"],
        )

        if st.button(
            "🚀 Analyze with 3-Model Gemini 4 Pipeline (Hydrogen + Neon + Carbon)",
            type="primary",
            disabled=not st.session_state["verified_safe"],
        ):
            combined_text = "\n\n".join(d["scrubbed_text"] for d in st.session_state["redacted_docs"])
            # Send key blacked-out PDF page images directly to Gemini 4 Hydrogen for visual checkbox/table inspection
            key_images = []
            for d in st.session_state["redacted_docs"]:
                for p_idx in range(min(d["page_count"], 2)):
                    if len(key_images) < 6:
                        key_images.append((
                            f"{d['doc_id']} | PAGE {p_idx + 1}",
                            render_pdf_page_png(d["blacked_pdf"], p_idx),
                        ))
            with st.spinner("Running Hydrogen (Visual PDF) -> Neon (NYC DOE Coach) -> Carbon (5-Sigma Audit)..."):
                out = analyze_hearing_records(combined_text, page_images=key_images)
                st.session_state["pipeline_output"] = out
                st.session_state["generated_videos"] = {}
            st.success("Analysis & 5-Sigma Citation Audit complete! Open Tabs 2, 3, and 4.")


# ==================== TAB 2: WHAT WE FOUND (PARENT VIEW) ====================
with tab2:
    out = st.session_state.get("pipeline_output")
    if not out:
        st.info("Scrub and analyze records in Tab 1 first.")
    else:
        analysis = out["analysis"]
        carbon = out["carbon_audit"]
        tel = out["telemetry"]
        visual = out["visual_findings"]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Priority Gaps Found", len(analysis.get("priority_findings", [])))
        m2.metric("Visual Checks (Hydrogen)", f"{tel.get('hydrogen_visual_s', 0)}s")
        m3.metric("NYC DOE Coach (Neon)", f"{tel.get('neon_reasoning_s', 0)}s")
        m4.metric("5-Sigma Citation Score (Carbon)", f"{carbon.get('verification_score_pct', 0)}%")

        st.info(f"**Plain-English Overview:** {analysis.get('case_snapshot', '')}")

        with st.expander(f"🔎 Carbon 5-Sigma Auditor Verdict: {carbon.get('auditor_summary', '')}"):
            if carbon.get("flagged_discrepancies"):
                for flag in carbon["flagged_discrepancies"]:
                    st.warning(f"**{flag.get('claim_title')}:** {flag.get('issue')}")
            else:
                st.success("All claims and page citations verified cleanly against source records.")

        if visual.get("checkbox_contradictions"):
            with st.expander("👁️ Visual Contradictions Caught on Page Images (Gemini 4 Hydrogen)", expanded=True):
                for vc in visual["checkbox_contradictions"]:
                    st.warning(f"**{vc.get('citation')}:** {vc.get('description')}")

        st.subheader("What We Found in Your Records")
        for item in analysis.get("priority_findings", []):
            badge = "🔴 HIGH PRIORITY" if item.get("priority") == "High" else "🟡 WATCHOUT"
            with st.container(border=True):
                st.markdown(f"### {badge} — {item.get('title')}")
                st.caption(f"Source Citation: `{item.get('citation')}`")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**What the DOE promised / assumed:**\n\n{item.get('what_doe_promised_or_assumed')}")
                with c2:
                    st.markdown(f"**What the records actually show:**\n\n{item.get('what_records_actually_show')}")
                st.markdown(f"**Why this matters under NYC DOE / IDEA rules:** {item.get('why_it_matters_nyc_rules')}")


# ==================== TAB 3: ARGUMENTS & OATH PREP ====================
with tab3:
    out = st.session_state.get("pipeline_output")
    if not out:
        st.info("Scrub and analyze records in Tab 1 first.")
    else:
        analysis = out["analysis"]
        st.warning(
            "⚖️ **Self-Help Preparation Tool (Not Legal Advice):** Organized to help you, an advocate, "
            "or a clinic see the factual points and gather the exact supporting proof."
        )

        st.download_button(
            "⬇️ Download Plain-English Parent Prep Guide (.md)",
            data=build_prep_markdown(out),
            file_name="parent_hearing_prep_guide.md",
            mime="text/markdown",
            type="primary",
        )

        st.subheader("Arguments & Points to Document and Share")
        for idx, arg in enumerate(analysis.get("arguments_to_document", []), start=1):
            with st.container(border=True):
                st.markdown(f"### {idx}. {arg.get('argument_title')}")
                st.caption(f"Source Citation: `{arg.get('citation')}`")
                st.markdown(f"**How to explain this simply:** {arg.get('plain_english_explanation')}")
                st.success(f"📋 **What to document & gather next:** {arg.get('what_to_document_and_share')}")

        st.subheader("NYC OATH Pre-Hearing Readiness Checklist")
        oath = analysis.get("oath_readiness", {})
        with st.container(border=True):
            st.markdown(f"**Deadlines & Procedural Notes:** {oath.get('hearing_and_disclosure_notes', '')}")
            st.markdown(f"**Burden of Proof Reminder:** {oath.get('burden_of_proof_reminder', '')}")
            st.markdown("**Suggested Exhibit Binder Order:**")
            for ex in oath.get("exhibit_checklist", []):
                st.checkbox(
                    f"**{ex.get('suggested_label')}** (`{ex.get('document_id')}`) — {ex.get('why_include')}",
                    key=f"ex_chk_{ex.get('suggested_label')}_{ex.get('document_id')}",
                )


# ==================== TAB 4: PARENT BRIEFING VIDEO ====================
with tab4:
    st.subheader("Parent Briefing Video: Your Case Gaps & Arguments to Document")
    st.caption(
        "Turns your actual gaps and prep points into a calm, parent-level 3-scene explainer video "
        "using Gemini Omni 1.2 Flash (v1beta), then optionally verifies accuracy with Gemini 4 Hydrogen."
    )

    out = st.session_state.get("pipeline_output")
    storyboard = out["analysis"].get("parent_briefing_storyboard", []) if out else []

    if not storyboard:
        st.info("Run the 3-Model Analysis in Tab 1 first to automatically build your case briefing storyboard.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            vid_res = st.selectbox("Video Resolution (use 360p for fast drafts)", ["360p", "720p"], index=0)
        with c2:
            vid_dur = st.slider("Clip Duration (seconds)", min_value=5, max_value=15, value=8)

        for scene in storyboard:
            s_num = scene.get("scene_number", 1)
            with st.expander(f"Scene {s_num}: {scene.get('slide_title')}", expanded=True):
                left, right = st.columns([1, 1])
                with left:
                    slide_preview = render_slide_card_png(scene)
                    st.image(slide_preview, caption="Reference Slide Card sent to Omni 1.2 Flash", width="stretch")
                with right:
                    st.write(f"**Key Point:** {scene.get('key_takeaway')}")
                    st.write(f"**Parent Narration:** {scene.get('narration_script')}")
                    st.caption(f"Citation: {scene.get('evidence_citation')}")

                    if st.button(f"🎬 Generate Scene {s_num} Video (Omni 1.2 Flash)", key=f"gen_vid_{s_num}", type="primary"):
                        with st.spinner(f"Rendering Scene {s_num} via gemini-omni-1.2-flash ({vid_res}, {vid_dur}s)..."):
                            try:
                                vid_bytes, _inter_id, _ = generate_teaching_clip(
                                    scene, resolution=vid_res, duration_seconds=vid_dur
                                )
                                st.session_state["generated_videos"][s_num] = vid_bytes
                            except Exception as exc:
                                st.error(f"Video generation error: {exc}")

                    if s_num in st.session_state["generated_videos"]:
                        vid_bytes = st.session_state["generated_videos"][s_num]
                        st.video(vid_bytes)
                        st.download_button(
                            f"⬇️ Download Scene {s_num} (.mp4)",
                            data=vid_bytes,
                            file_name=f"parent_briefing_scene_{s_num}.mp4",
                            mime="video/mp4",
                            key=f"dl_vid_{s_num}",
                        )
                        if st.button(f"🔎 Verify Clip Accuracy with Gemini 4 Hydrogen", key=f"chk_vid_{s_num}"):
                            with st.spinner("Gemini 4 Hydrogen watching clip..."):
                                check_text = verify_video_with_gemini4(
                                    vid_bytes, scene.get("key_takeaway", "")
                                )
                                st.session_state["video_checks"][s_num] = check_text

                        if s_num in st.session_state["video_checks"]:
                            st.info(st.session_state["video_checks"][s_num])

    with st.expander("Optional: Reverse-Engineer a Separate Past FOFD / Transcript"):
        fofd_txt = st.text_area("Paste ALREADY-SCRUBBED past FOFD text here", height=150)
        if st.button("Extract IHO Lessons from Past FOFD", disabled=not fofd_txt.strip()):
            with st.spinner("Analyzing past FOFD with Gemini 4 Neon..."):
                fofd_res, _ = reverse_engineer_fofd(fofd_txt)
                st.session_state["fofd_override"] = fofd_res
        if st.session_state.get("fofd_override"):
            st.write(st.session_state["fofd_override"].get("case_outcome_summary", ""))
            st.json(st.session_state["fofd_override"].get("what_the_iho_found_decisive", []))


# ==================== TAB 5: 5-SIGMA RELIABILITY & EVAL ====================
with tab5:
    st.subheader("5-Sigma Engineering: Real-World Failures Caught & Baseline Benchmark")
    st.markdown(
        """
**Multi-Model Architecture (Each Gemini 4 Model Has a Clear Job):**
1. **Local Privacy Layer (`PyMuPDF` + `spaCy` + `RapidOCR`):** Strips minor PII, spaced OSIS IDs (`xxx xxx xxx`), court line-split case numbers, and phonetic spellings (`R-A-M as in...`) *before* cloud calls.
2. **`gemini-4-hydrogen` (Multimodal PDF & Video Inspector):** Reads blacked-out PDF page images directly to spot visual checkbox contradictions (e.g., `BIP: Yes` vs `No`) and audits generated video clips.
3. **`gemini-4-neon` (NYC DOE SOPM / Part 200 Coach):** Reconciles mandates vs. logs and translates findings into parent-level explanations and arguments to document.
4. **`gemini-4-carbon` (5-Sigma Citation Auditor):** Cross-checks every claim against source pages to catch hallucinations.
5. **`gemini-omni-1.2-flash` (`v1beta`):** Generates narrated parent-briefing video clips from reference slide cards.
"""
    )

    if st.button("📊 Run Live 5-Sigma Evaluation (Baseline vs. Multi-Model System)", type="primary"):
        with st.spinner("Running adversarial PII suite, single-model baseline, and 3-model pipeline..."):
            st.session_state["eval_summary"] = run_full_evaluation(include_local_unseen=True)

    eval_res = st.session_state.get("eval_summary")
    if not eval_res and Path("eval_results.json").exists():
        eval_res = json.loads(Path("eval_results.json").read_text(encoding="utf-8"))

    if eval_res:
        st.success(f"Evaluated on: **{eval_res.get('evaluated_on')}**")
        st.table(eval_res.get("comparison", []))
        st.caption(f"Carbon Auditor Verdict: {eval_res.get('carbon_auditor_verdict', '')}")

        with st.expander("Adversarial Scrubber Stress-Test Details (Real Transcript/IEP Edge Cases)"):
            st.table(eval_res.get("scrubber_stress_test", {}).get("details", []))