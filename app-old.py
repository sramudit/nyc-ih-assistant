import json
import streamlit as st
from analyzer import analyze_hearing_records, reverse_engineer_fofd
from redact_local import (
    LocalRedactor,
    build_safe_doc_stem,
    discover_pii_candidates,
    redact_pdf_with_visuals,
    render_pdf_page_png,
)

st.set_page_config(
    page_title="NYC Impartial Hearing Assistant",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ NYC Impartial Hearing Assistant")
st.caption(
    "Privacy-first record organizer & hearing prep assistant for pro se NYC parents. "
    "Real PDFs are scrubbed 100% locally before Gemini 4 ever sees anonymized text."
)

# Initialize session state
for key, default in {
    "redacted_docs": [],
    "audit_counts": {},
    "discovered": {},
    "extra_terms": "",
    "verified_safe": False,
    "analysis_result": None,
    "analysis_model": "",
    "fofd_result": None,
    "fofd_model": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def split_csv(val: str):
    return [x.strip() for x in val.split(",") if x.strip()]


# Sidebar: Local PII Intake Form
with st.sidebar:
    st.header("🛡️ Local Privacy Config")
    st.caption("Stays strictly on your computer. Separate multiple items with commas.")

    student_names = st.text_input("Student Name(s)", placeholder="e.g., Jordan Sample")
    parent_names = st.text_input("Parent / Guardian Name(s)", placeholder="e.g., Alex Sample")
    school_names = st.text_input("School Name(s)", placeholder="e.g., P.S. 123")
    district_names = st.text_input("District / Agency", value="NYC DOE")
    provider_names = st.text_input("Provider / Evaluator Name(s)", placeholder="e.g., Dr. Taylor Reed")
    ids = st.text_input("Student / OSIS / Case IDs", placeholder="e.g., 123456789")
    dobs = st.text_input("Date(s) of Birth", placeholder="e.g., 04/12/2017")
    addresses = st.text_input("Street Address(es)", placeholder="e.g., 100 Main St")

    extra_terms = st.text_area(
        "Extra Words to Black Out",
        value=st.session_state["extra_terms"],
        placeholder="Caught something in preview? Add it here, separated by commas...",
    )
    st.session_state["extra_terms"] = extra_terms

    def build_config_dict():
        return {
            "student_names": split_csv(student_names),
            "parent_names": split_csv(parent_names),
            "school_names": split_csv(school_names),
            "district_names": split_csv(district_names),
            "provider_names": split_csv(provider_names),
            "ids": split_csv(ids),
            "dobs": split_csv(dobs),
            "addresses": split_csv(addresses),
            "extra_terms": split_csv(extra_terms),
        }


tab1, tab2, tab3, tab4 = st.tabs([
    "1️⃣ Local Privacy Shield",
    "2️⃣ Service Gaps & Timeline",
    "3️⃣ Prep & Exhibit Binder",
    "4️⃣ FOFD Lessons & Video",
])

# ==================== TAB 1: LOCAL PRIVACY SHIELD ====================
with tab1:
    st.subheader("Step 1: Upload PDFs & Scrub Locally")
    uploaded_files = st.file_uploader(
        "Upload IEP, Evaluation, Service Logs, or Transcript PDFs (processed locally in memory)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔍 Auto-Discover Names / Schools / OSIS Locally", disabled=not uploaded_files):
            with st.spinner("Scanning first pages locally with spaCy..."):
                raw_bytes_list = [f.getvalue() for f in uploaded_files]
                st.session_state["discovered"] = discover_pii_candidates(raw_bytes_list)

    if st.session_state["discovered"]:
        disc = st.session_state["discovered"]
        with st.expander("📋 Locally Detected PII Candidates (Confirm & Add to Sidebar)", expanded=True):
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
        if st.button("🖤 Run Local Scrubber & Black Out PDFs", type="primary", disabled=not uploaded_files):
            with st.spinner("Scrubbing text and burning permanent black boxes into PDFs..."):
                redactor = LocalRedactor(config_dict=build_config_dict())
                docs_out = []
                for idx, uf in enumerate(uploaded_files, start=1):
                    doc_id = f"DOC_{idx:03d}"
                    safe_name = build_safe_doc_stem(doc_id, uf.name)
                    scrubbed_text, blacked_pdf, page_cnt, empty_cnt = redact_pdf_with_visuals(
                        uf.getvalue(), doc_id, redactor
                    )
                    docs_out.append({
                        "doc_id": doc_id,
                        "safe_name": safe_name,
                        "scrubbed_text": scrubbed_text,
                        "blacked_pdf": blacked_pdf,
                        "page_count": page_cnt,
                        "empty_pages": empty_cnt,
                    })
                st.session_state["redacted_docs"] = docs_out
                st.session_state["audit_counts"] = redactor.audit_counts
                st.session_state["verified_safe"] = False

    if st.session_state["redacted_docs"]:
        st.success(
            f"Scrubbed {len(st.session_state['redacted_docs'])} document(s) locally! "
            f"Redactions applied: {sum(st.session_state['audit_counts'].values())}"
        )

        # Quick side-by-side verification viewer
        doc_choices = [f"{d['safe_name']} ({d['page_count']} pages)" for d in st.session_state["redacted_docs"]]
        selected_idx = st.selectbox("Inspect Document", range(len(doc_choices)), format_func=lambda i: doc_choices[i])
        selected_doc = st.session_state["redacted_docs"][selected_idx]

        if selected_doc["empty_pages"] > 0:
            st.warning(f"⚠️ {selected_doc['empty_pages']} page(s) appear to be scanned images with minimal selectable text.")

        st.download_button(
            "⬇️ Download Blacked-Out PDF",
            data=selected_doc["blacked_pdf"],
            file_name=f"{selected_doc['safe_name']}_BLACKED_OUT.pdf",
            mime="application/pdf",
        )

        page_num = st.number_input(
            "Page to inspect",
            min_value=1,
            max_value=selected_doc["page_count"],
            value=1,
        )

        left_col, right_col = st.columns(2)
        with left_col:
            st.markdown("**Blacked-Out PDF View**")
            png_bytes = render_pdf_page_png(selected_doc["blacked_pdf"], page_num - 1)
            st.image(png_bytes, width="stretch")

        with right_col:
            st.markdown("**Anonymized Text Sent to Gemini 4**")
            pages_split = selected_doc["scrubbed_text"].split(f"=== {selected_doc['doc_id']} | PAGE ")
            matching_page = next(
                (p for p in pages_split if p.startswith(f"{page_num} ===")),
                selected_doc["scrubbed_text"][:4000],
            )
            st.text_area("Scrubbed page text", value=matching_page, height=580, label_visibility="collapsed")

        st.divider()
        st.session_state["verified_safe"] = st.checkbox(
            "✅ I verified the blacked-out PDF and scrubbed text contain no personal identifiers.",
            value=st.session_state["verified_safe"],
        )

        if st.button(
            "🚀 Analyze Scrubbed Records with Gemini 4",
            type="primary",
            disabled=not st.session_state["verified_safe"],
        ):
            combined_text = "\n\n".join(d["scrubbed_text"] for d in st.session_state["redacted_docs"])
            with st.spinner("Running Gemini 4 Neon analysis on scrubbed text..."):
                res, used_model = analyze_hearing_records(combined_text)
                st.session_state["analysis_result"] = res
                st.session_state["analysis_model"] = used_model
            st.success(f"Analysis complete using `{used_model}`! Open Tabs 2 & 3 to review.")


# ==================== TAB 2: SERVICE GAPS & TIMELINE ====================
with tab2:
    res = st.session_state.get("analysis_result")
    if not res:
        st.info("Scrub and analyze records in Tab 1 first.")
    else:
        st.caption(f"Analyzed with `{st.session_state['analysis_model']}` • Every item grounded in PDF page citations.")
        gaps = res.get("service_gaps", [])
        high_gaps = sum(1 for g in gaps if g.get("severity") == "High")

        m1, m2, m3 = st.columns(3)
        m1.metric("Documents Triaged", len(res.get("documents_detected", [])))
        m2.metric("Services Audited", len(gaps))
        m3.metric("High-Severity Gaps", high_gaps)

        st.subheader("Mandate vs. Delivery Audit")
        st.dataframe(gaps, width="stretch")

        st.subheader("Record Chronology")
        st.dataframe(res.get("chronology", []), width="stretch")

        st.subheader("Procedural & FAPE Checks")
        st.dataframe(res.get("procedural_and_fape_checks", []), width="stretch")


# ==================== TAB 3: PREP & EXHIBIT BINDER ====================
with tab3:
    res = st.session_state.get("analysis_result")
    if not res:
        st.info("Scrub and analyze records in Tab 1 first.")
    else:
        st.warning(
            "⚖️ **Self-Help Organization Only (Not Legal Advice):** These factual checklists and "
            "clarifying questions help organize records for a parent, advocate, or attorney."
        )
        st.subheader("Documents & Suggested Exhibit Index")
        st.dataframe(res.get("documents_detected", []), width="stretch")

        st.subheader("Fact-Clarifying Questions & Prep Prompts")
        st.dataframe(res.get("upl_safe_prep_prompts", []), width="stretch")

        st.download_button(
            "⬇️ Download Full Prep Report (JSON)",
            data=json.dumps(res, indent=2),
            file_name="hearing_prep_report.json",
            mime="application/json",
        )


# ==================== TAB 4: FOFD LESSONS & VIDEO ====================
with tab4:
    st.subheader("Reverse-Engineer a Past Transcript / FOFD into a Teaching Video")
    st.caption(
        "Uses Gemini 4 to identify what actually swayed the Impartial Hearing Officer, "
        "and Gemini Omni 1.2 Flash to generate a parent explainer clip."
    )

    fofd_source = ""
    if st.session_state["redacted_docs"]:
        fofd_source = "\n\n".join(d["scrubbed_text"] for d in st.session_state["redacted_docs"])
        st.info(f"Using {len(st.session_state['redacted_docs'])} scrubbed document(s) currently loaded from Tab 1.")
    else:
        fofd_source = st.text_area("Or paste ALREADY-SCRUBBED Transcript / FOFD text here", height=200)

    if st.button("🧠 Extract IHO Insights & Video Storyboard (Gemini 4)", disabled=not fofd_source.strip()):
        with st.spinner("Reverse-engineering what the IHO relied upon..."):
            fofd_res, used_model = reverse_engineer_fofd(fofd_source)
            st.session_state["fofd_result"] = fofd_res
            st.session_state["fofd_model"] = used_model

    if st.session_state.get("fofd_result"):
        fofd = st.session_state["fofd_result"]
        st.success(f"Storyboard generated with `{st.session_state['fofd_model']}`")
        st.markdown(f"**Outcome Summary:** {fofd.get('case_outcome_summary', '')}")

        st.markdown("### What the IHO Found Decisive")
        st.dataframe(fofd.get("what_the_iho_found_decisive", []), width="stretch")

        st.markdown("### 3-Scene Teaching Video Storyboard")
        for scene in fofd.get("video_storyboard", []):
            with st.expander(f"Scene {scene.get('scene_number')}: {scene.get('slide_title')}", expanded=True):
                st.write(f"**On-Screen Card:** {scene.get('key_takeaway')}")
                st.write(f"**Narration:** {scene.get('narration_script')}")
                st.caption(f"Citation: {scene.get('evidence_citation')}")