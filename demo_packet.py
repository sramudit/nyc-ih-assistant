from typing import List, Tuple
import pymupdf


SYNTHETIC_DOCUMENTS: List[Tuple[str, List[str]]] = [
    (
        "01_Maya_Chen_SESIS_IEP_2025.pdf",
        [
            (
                "3/25/26, 9:15 AM          Individualized Education Program (IEP) for Maya Chen (901 442 817)\n\n"
                "                          INDIVIDUALIZED EDUCATION PROGRAM (IEP)\n"
                "STUDENT NAME: Maya Chen                     DISABILITY CLASSIFICATION: Autism\n"
                "DATE OF BIRTH: 04/12/2012                   LOCAL ID #: 901 442 817\n"
                "SCHOOL: Tech High School (District 99)      PARENT: Grace Chen\n"
                "ADDRESS: 100 Example Avenue, Bronx, NY      NYC ID: 901 442 817\n"
                "PROJECTED DATE IEP TO BE IMPLEMENTED: 04/04/2026   ANNUAL REVIEW: 03/21/2027\n\n"
                "PRESENT LEVELS OF PERFORMANCE AND INDIVIDUAL NEEDS\n"
                "ACADEMIC ACHIEVEMENT & LEARNING CHARACTERISTICS:\n"
                "Maya Chen is a 14-year-old 9th grade student with Autism Spectrum Disorder (ASD),\n"
                "ADHD Combined Presentation, Developmental Coordination Disorder (F82), and\n"
                "phonological dyslexia. She is placed in Integrated Co-Teaching (ICT) classes.\n"
                "Teacher Reports: Geometry grade 90, Chemistry grade 92 ('excels conceptually').\n"
                "Teachers state: 'Maya is quiet and performs well on content exams, so behavioral\n"
                "supports do not appear warranted.' However, Chemistry teacher notes Maya shuts down\n"
                "during multi-step lab procedures and turns in incomplete handwritten labs. ELA teacher\n"
                "notes reading decoding fluency lags significantly on timed passages despite strong\n"
                "oral comprehension, and homework takes 3+ hours nightly with heavy parent prompting.\n"
            ),
            (
                "STUDENT NEEDS RELATING TO SPECIAL FACTORS (IEP PAGE 12 EQUIVALENT)\n\n"
                "Does the student need strategies, including positive behavioral interventions,\n"
                "supports and other strategies to address behaviors that impede the student's\n"
                "learning or that of others?   [X] Yes   [ ] No\n"
                "Does the student need a behavioral intervention plan (BIP)?   [X] Yes   [ ] No\n"
                "Note: Student requires structured executive-functioning prompting, visual task\n"
                "breakdowns, and anxiety de-escalation before shutting down during transitions.\n\n"
                "RECOMMENDED SPECIAL EDUCATION PROGRAMS AND SERVICES (MANDATES):\n"
                "1. Integrated Co-Teaching (ICT): ELA, Math, Science, Social Studies (5x/wk)\n"
                "2. SETSS (Specialized Reading - Orton-Gillingham): 5x45 min/wk, Small Group (3:1)\n"
                "3. Counseling Services: 1x40 min/wk, Group of 3\n"
                "4. Parent Counseling and Training: 2x per year, 30 min (Virtual/Phone)\n"
                "5. Occupational Therapy (OT): DISCONTINUED at 03/21/2026 review despite F82 DCD\n"
                "6. Licensed Behavior Analyst (LBA / BCBA) Services: OMITTED from IEP mandates\n"
                "   (Prior 08/20/2024 IHO Order awarded 180 hrs LBA expiring 08/20/2026).\n"
            ),
            (
                "IEP SUMMARY & OTHER OPTIONS CONSIDERED (IEP PAGE 22 EQUIVALENT)\n\n"
                "Classification of Disability: Autism\n"
                "Does Maya Chen have a Behavioral Intervention Plan?   No\n"
                "(CONTRADICTION: Special Factors marked YES for BIP, Summary marked NO.)\n\n"
                "Parent Concerns: Parent Grace Chen formally objected that discontinuing OT,\n"
                "reducing Parent Training to 2x/year, failing to mandate LBA/BCBA support across\n"
                "new 9th grade teachers, and failing to conduct a triennial evaluation since 5th\n"
                "grade leaves Maya regressing in executive functioning and self-advocacy.\n"
                "Reason(s) for Rejection of LBA/BCBA: 'CSE declined mandated LBA services because\n"
                "student earns high grades in math/science and exhibits no classroom aggression.'\n"
            ),
        ],
    ),
    (
        "02_Neuropsych_Eval_Summary.pdf",
        [
            (
                "NEUROPSYCHOLOGICAL EVALUATION REPORT\n"
                "Examinee: Maya Chen | DOB: 04/12/2012 | OSIS: 901442817\n"
                "Dates of Eval: 04/02/2026, 04/20/2026 | Report Date: 05/06/2026\n"
                "Clinician: Dr. Avery Patel, Psy.D., ABPP/CN | Grey Matter Neuropsychology\n\n"
                "COGNITIVE & ACHIEVEMENT PROFILE (TWICE-EXCEPTIONAL / 2E SPLIT):\n"
                "WISC-V: FSIQ = 125 (95th %ile, Superior) | Fluid Reasoning = 138 (>99th %ile)\n"
                "TOWRE-2 Phonemic Decoding: SS = 74 (4th %ile, Well Below Average — unchanged from 2024)\n"
                "WJ-IV Reading Recall: SS = 81 (10th %ile) | Spelling: SS = 78 (7th %ile)\n"
                "Beery VMI-6: Visual-Motor Integration SS = 82 (12th %ile) | Motor Coord SS = 79\n\n"
                "ADAPTIVE & EXECUTIVE FUNCTIONING SCALES:\n"
                "ABAS-3 General Adaptive Composite: SS = 74 (4th %ile, Well Below Average)\n"
                "  - Self-Direction: ss = 3 (1st %ile, Extremely Low)\n"
                "  - Activities of Daily Living (BASC-3): T = 29 (Clinically Significant deficit)\n"
                "BRIEF-2 Parent Form: Global Executive Composite (GEC) T = 76 (98th %ile, Severely Elevated)\n"
                "  - Initiate T = 78 (>99th %ile) | Plan/Organize T = 81 (>99th %ile) | Shift T = 79\n"
                "Conners-4: Inattention/Exec Dysfunction T = 75 | Anxious Thoughts T = 84 (Very Elevated)\n"
            ),
            (
                "CLINICAL RECOMMENDATIONS (DR. AVERY PATEL, PSY.D.):\n\n"
                "1. Licensed Behavior Analyst (LBA / BCBA): Minimum 5 hours/week direct school-based\n"
                "   support for task initiation, assignment breakdown, and generalization across\n"
                "   9th grade teachers, PLUS 4 hours/month LBA Parent Training and 2 hours/month\n"
                "   LBA Team Coordination. Note: Cognitive ability masks severe executive dysfunction.\n"
                "2. Structured Literacy (Dyslexia): 5x45 min/week 1:1 or 2:1 Orton-Gillingham\n"
                "   intervention; current 3:1 group SETSS has yielded flat TOWRE-2 scores.\n"
                "3. Occupational Therapy: Reinstate 2x30 min/week 1:1 OT for DCD (F82) & lab/motor needs.\n"
                "4. Immediate Functional Behavioral Assessment (FBA) & updated BIP targeting shutdowns.\n"
            ),
        ],
    ),
    (
        "03_SESIS_Service_Logs_and_PWN.pdf",
        [
            (
                "NYC DOE SESIS RELATED SERVICE & SETSS DELIVERY AUDIT (JAN 2026 - APR 2026)\n"
                "Student: Maya Chen | NYC ID: 901 442 817 | School: Tech High School\n\n"
                "1. SETSS SPECIALIZED READING (Mandated: 5x45 min/week = 60 sessions over 12 wks):\n"
                "   - Jan 2026: 15 delivered / 20 mandated (5 MISSED — provider reassigned)\n"
                "   - Feb 2026: 14 delivered / 20 mandated (6 MISSED — regents proctoring / absent)\n"
                "   - Mar 2026: 17 delivered / 20 mandated (3 MISSED — scheduling conflict)\n"
                "   TOTAL: 46 delivered / 60 mandated = 14 MISSED SESSIONS (630 missed minutes).\n"
                "   Make-up sessions documented in SESIS: 0.\n\n"
                "2. OCCUPATIONAL THERAPY: Discontinued 03/21/2026; prior Jan-Feb logs show\n"
                "   6 MISSED SESSIONS (180 missed minutes) due to no assigned OT provider.\n\n"
                "3. PRIOR WRITTEN NOTICE (PWN) DATED 04/10/2026:\n"
                "   DOE refused LBA/BCBA mandate, FBA, and OT reinstatement stating: 'Student earns\n"
                "   87-92 grades in core classes and exhibits no externalizing classroom disruptions.'\n"
                "   PWN omitted any discussion of BRIEF-2 (98th %ile), ABAS-3 (4th %ile), or TOWRE-2.\n"
            ),
        ],
    ),
    (
        "04_OATH_Transcript_and_Prior_FOFD.pdf",
        [
            (
                "NYC OFFICE OF ADMINISTRATIVE TRIALS AND HEARINGS (OATH)\n"
                "In the Matter of Maya Chen | Case\n 7 number 311994 | District #99\n"
                "BEFORE: SAMUEL MERCER, Impartial Hearing Officer | Date: July 16, 2026\n\n"
                " 8  PARENT: I am Grace Chen, spelled C-H-E-N as in Charles, H-E-N, pro se.\n"
                " 9  IHO MERCER: Confirmed. Parent filed Due Process Complaint in Jan 2026;\n"
                "10  case number 311994 was assigned June 15, 2026 after DOE backlog.\n"
                "11  MS. WINTERS (DOE): No resolution meeting was held within 30 days.\n"
                "12  IHO MERCER: Hearing is set for August 6, 2026. Five-business-day disclosures\n"
                "13  are due July 30, 2026 by 11:59 PM. Parent exhibits must be labeled A-1, B-1;\n"
                "14  District exhibits 1-1, 2-1. DOE bears burden of proof on FAPE; Parent bears\n"
                "15  burden on appropriateness and $360/hr rate of Manhattan Behavioral Group.\n"
                "16  Triennial evaluation has not been conducted by DOE since 5th grade.\n"
            ),
            (
                "EXCERPT FROM PRIOR 2024 FOFD (CASE NO. 288401, IHO R. GLASSER):\n"
                "1. 'Academic grades do not negate an IDEA FAPE denial where executive dysfunction\n"
                "   and adaptive deficits (ABAS-3 4th %ile) prevent independent access.'\n"
                "2. 'No other methodology, save for LBA/ABA training across teachers, enabled\n"
                "   Maya Chen to generalize self-advocacy and avoid regression.'\n"
                "3. 'Unrebutted SESIS logs proving 14 missed SETSS sessions entitle the student\n"
                "   to compensatory 1:1 Orton-Gillingham instruction.'\n"
            ),
        ],
    ),
]


def build_synthetic_demo_packet() -> List[Tuple[str, bytes]]:
    results: List[Tuple[str, bytes]] = []
    for filename, pages in SYNTHETIC_DOCUMENTS:
        doc = pymupdf.open()
        for page_text in pages:
            page = doc.new_page(width=612, height=792)
            rect = pymupdf.Rect(45, 45, 567, 747)
            page.insert_textbox(rect, page_text, fontsize=9.8, fontname="helv")
        results.append((filename, doc.tobytes()))
    return results


if __name__ == "__main__":
    from pathlib import Path
    out_dir = Path("demo_data")
    out_dir.mkdir(exist_ok=True)
    for fname, pdf_bytes in build_synthetic_demo_packet():
        (out_dir / fname).write_bytes(pdf_bytes)
        print(f"Generated: demo_data/{fname}")