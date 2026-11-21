from typing import Dict, List, Tuple
import pymupdf


SYNTHETIC_DOCUMENTS: List[Tuple[str, List[str]]] = [
    (
        "01_Jordan_Rivera_IEP_2025.pdf",
        [
            (
                "NYC DEPARTMENT OF EDUCATION - INDIVIDUALIZED EDUCATION PROGRAM (IEP)\n"
                "CONFIDENTIAL STUDENT RECORD\n\n"
                "Student Name: Jordan Rivera          DOB: 04/12/2017\n"
                "NYC ID / OSIS: 900 123 456           School: P.S. 999 (District 99)\n"
                "Parent/Guardian: Elena Rivera        Address: 100 Example Avenue, New York, NY\n"
                "IEP Meeting Date: 09/15/2025         Disability Classification: Autism / OHI\n\n"
                "PRESENT LEVELS OF PERFORMANCE & NEEDS:\n"
                "- Executive Functioning: Jordan demonstrates significant deficits in task initiation,\n"
                "  multi-step sequencing, transition flexibility, and self-monitoring. Private\n"
                "  evaluation notes Jordan freezes for 15-20 minutes during non-preferred transitions\n"
                "  without structured behavioral prompting and visual reinforcement schedules.\n"
                "- Reading / Literacy: Diagnosed with specific phonological dyslexia. Decoding at\n"
                "  early 1st-grade level despite 3rd-grade placement. Requires explicit, systematic\n"
                "  multisensory structured literacy (Orton-Gillingham / Wilson) instruction.\n"
            ),
            (
                "RECOMMENDED SPECIAL EDUCATION PROGRAMS AND SERVICES (MANDATES):\n\n"
                "1. Integrated Co-Teaching (ICT): 5 periods/week (Full Day, General Ed + Special Ed)\n"
                "2. Special Education Teacher Support Services (SETSS - Specialized Reading):\n"
                "   5x45 minutes/week, Small Group (3:1), Orton-Gillingham trained provider.\n"
                "   Projected Start: 09/16/2025\n"
                "3. Speech-Language Therapy: 2x30 minutes/week, Group (3:1). Projected Start: 09/16/2025\n"
                "4. Occupational Therapy: 2x30 minutes/week, Individual (1:1). Projected Start: 09/16/2025\n"
                "5. BCBA Consultation & Direct Behavioral Support: [NOT RECOMMENDED BY CSE]\n"
                "6. Parent Counseling & Training: [NOT RECOMMENDED BY CSE]\n\n"
                "ANNUAL GOALS EXCERPT (READING):\n"
                "Goal 1 (2025-2026): Given CVCe and vowel-team words, Jordan will decode with 80% accuracy.\n"
                "Note: Identical wording carried over from 2024-2025 IEP Goal 1 (baseline remained 42%).\n"
            ),
        ],
    ),
    (
        "02_Neuropsych_Eval_Summary.pdf",
        [
            (
                "COMPREHENSIVE NEUROPSYCHOLOGICAL & EDUCATIONAL EVALUATION\n\n"
                "Examinee: Jordan Rivera              DOB: 04/12/2017\n"
                "OSIS #: 900123456                    Evaluator: Dr. Taylor Reed, Ph.D.\n"
                "Evaluation Date: 08/22/2025          School: P.S. 999\n\n"
                "STANDARDIZED TEST SCORES (YEAR-OVER-YEAR COMPARISON):\n"
                "- WIAT-4 Word Reading: SS 72 (3rd percentile) — unchanged from 2024 (SS 73)\n"
                "- TOWRE-2 Phonemic Decoding: SS 69 (2nd percentile) — no measurable growth\n"
                "- BRIEF-2 Executive Function Global Composite: T-score 78 (Clinically Elevated)\n"
                "  Subscales: Initiate (79), Working Memory (76), Shift/Transitions (81).\n\n"
                "CLINICAL RECOMMENDATIONS:\n"
                "1. BCBA Services for Executive Functioning: Recommend 4 hours/month direct BCBA\n"
                "   supervision/consultation to design antecedent transition supports, task-initiation\n"
                "   prompts, and self-monitoring protocols across classroom routines, PLUS 2 hours/month\n"
                "   BCBA-led Parent Training to generalize executive functioning strategies at home.\n"
                "   Executive dysfunction—not physical aggression—is the primary barrier to access.\n"
                "2. Structured Literacy: 5x45 min/week 1:1 or 2:1 Orton-Gillingham intervention.\n"
                "3. Conduct a Functional Behavioral Assessment (FBA) targeting work-avoidance freezes.\n"
            ),
        ],
    ),
    (
        "03_Service_Delivery_Logs_and_PWN.pdf",
        [
            (
                "RELATED SERVICE & SETSS DELIVERY LOG (OCT 2025 - DEC 2025)\n\n"
                "Student: Jordan Rivera | NYC ID: 900 123 456 | School: P.S. 999\n"
                "Mandated SETSS Reading: 5x45 min/week (60 sessions expected over 12-week period).\n\n"
                "DELIVERY AUDIT SUMMARY BY WEEK:\n"
                "- Oct 2025 (4 weeks, 20 expected): 14 delivered, 6 MISSED (Provider Absent / Testing)\n"
                "- Nov 2025 (4 weeks, 20 expected): 15 delivered, 5 MISSED (Provider Reassigned)\n"
                "- Dec 2025 (4 weeks, 20 expected): 17 delivered, 3 MISSED (Scheduling Conflict)\n"
                "TOTAL SETSS READING: 46 delivered / 60 mandated = 14 MISSED SESSIONS (630 minutes).\n"
                "Make-up sessions provided to date: 0.\n\n"
                "SPEECH-LANGUAGE THERAPY (2x30 min/week, 24 expected): 20 delivered, 4 MISSED (120 min).\n"
                "Note: 10/14/2025 progress note confirms group size was 5:1 instead of mandated 3:1.\n"
            ),
            (
                "NYC DOE PRIOR WRITTEN NOTICE (PWN) - DATED 09/25/2025\n\n"
                "Student: Jordan Rivera | OSIS: 900 123 456 | Parent: Elena Rivera\n\n"
                "ACTION REFUSED: Parent request for 4 hrs/month BCBA consultation, 2 hrs/month BCBA\n"
                "parent training, and updated FBA/BIP based on Dr. Taylor Reed's 08/22/2025 report.\n\n"
                "DOE EXPLANATION FOR REFUSAL:\n"
                "'The CSE declined BCBA services and an FBA because Jordan does not exhibit severe\n"
                "physical aggression or elopement in the classroom. Staff report Jordan is quiet.'\n\n"
                "NOTICE NOTE: PWN does not address the BRIEF-2 executive functioning freezing behaviors\n"
                "documented in Dr. Taylor Reed's evaluation, nor explain why 2024 reading goals were\n"
                "repeated verbatim despite flat WIAT-4 / TOWRE-2 scores.\n"
            ),
        ],
    ),
    (
        "04_Past_Hearing_Transcript_and_FOFD.pdf",
        [
            (
                "OFFICE OF ADMINISTRATIVE TRIALS AND HEARINGS (OATH)\n"
                "SPECIAL EDUCATION HEARINGS DIVISION - EXCERPT OF HEARING TRANSCRIPT\n\n"
                "Matter of Jordan Rivera (OSIS 900 123 456) v. NYC Department of Education\n"
                "Parent Representative: Elena Rivera (Pro Se), spelled R-I-V-E-R-A\n\n"
                "Q (Parent): Can you confirm from Exhibit C whether any FBA was conducted after\n"
                "Dr. Taylor Reed documented 20-minute task-initiation freezes?\n"
                "A (District Witness): No FBA was conducted because the student was not disruptive.\n"
                "Q (Parent): Did the DOE provide make-up sessions for the 14 missed SETSS sessions?\n"
                "A (District Witness): Not yet; our SESIS log confirms 14 sessions were missed.\n"
            ),
            (
                "FINDINGS OF FACT AND DECISION (FOFD) - IMPARTIAL HEARING OFFICER RULING\n\n"
                "FINDINGS OF FACT:\n"
                "1. The record establishes that the DOE denied Jordan Rivera a FAPE by failing to\n"
                "   address executive functioning deficits solely because the student was 'quiet' and\n"
                "   non-aggressive. Behavioral/BCBA support under IDEA is not limited to aggression.\n"
                "2. Unrebutted SESIS logs prove 14 missed SETSS reading sessions (630 minutes) and\n"
                "   stagnant WIAT-4/TOWRE-2 decoding scores alongside copy-pasted annual goals.\n\n"
                "ORDER / REMEDY AWARDED:\n"
                "- DOE shall fund 4 hrs/month BCBA consultation + 2 hrs/month BCBA parent training.\n"
                "- DOE shall provide 15 hours of compensatory 1:1 Orton-Gillingham reading instruction.\n"
            ),
        ],
    ),
]


def build_synthetic_demo_packet() -> List[Tuple[str, bytes]]:
    """Build 4 synthetic NYC DOE PDFs entirely in memory (returns list of (filename, pdf_bytes))."""
    results: List[Tuple[str, bytes]] = []
    for filename, pages in SYNTHETIC_DOCUMENTS:
        doc = pymupdf.open()
        for page_text in pages:
            page = doc.new_page(width=612, height=792)  # US Letter
            rect = pymupdf.Rect(50, 50, 562, 742)
            page.insert_textbox(rect, page_text, fontsize=10.5, fontname="helv")
        results.append((filename, doc.tobytes()))
    return results


if __name__ == "__main__":
    from pathlib import Path
    out_dir = Path("demo_data")
    out_dir.mkdir(exist_ok=True)
    for fname, pdf_bytes in build_synthetic_demo_packet():
        (out_dir / fname).write_bytes(pdf_bytes)
        print(f"Generated: demo_data/{fname}")