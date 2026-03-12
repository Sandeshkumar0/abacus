from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, ListFlowable, ListItem

OUTPUT_PATH = r"docs/EMESYS_Portal_Workflow_Guide.pdf"


def bullet_list(items, style):
    return ListFlowable(
        [ListItem(Paragraph(i, style), leftIndent=10) for i in items],
        bulletType="bullet",
        leftIndent=14,
        bulletFontName="Helvetica",
        bulletFontSize=9,
    )


def heading(text, style):
    return Paragraph(text, style)


def section_title(num, text, style):
    return Paragraph(f"<b>{num}. {text}</b>", style)


def build_pdf(path: str):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="EMESYS Portal Working Guide",
        author="Codex (for project handover)",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0B4DBA"),
        spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=16,
    )
    h_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=8,
        spaceAfter=6,
    )
    sh_style = ParagraphStyle(
        "SubHeadingStyle",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=6,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=6,
        textColor=colors.HexColor("#1F2937"),
    )
    small = ParagraphStyle(
        "Small",
        parent=body,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    # Cover
    story.append(Paragraph("EMESYS Portal - Complete Working Guide", title_style))
    story.append(Paragraph("Admin + Teacher + Student + Parent workflows for demo/presentation", subtitle_style))
    story.append(Paragraph(f"Generated on: <b>{datetime.now().strftime('%d %b %Y, %I:%M %p')}</b>", body))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Purpose</b>", h_style))
    story.append(Paragraph(
        "This document explains how the full portal works in practical sequence: setup by Admin, day-to-day operations by Teacher, learning actions by Student, and monitoring by Parent. It is prepared for senior-level walkthrough and handover.",
        body,
    ))

    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Quick System Flow</b>", h_style))
    story.append(Paragraph(
        "Admin Setup -> Teacher Operations -> Student Actions -> Parent Visibility -> Notifications & Analytics",
        body,
    ))

    story.append(PageBreak())

    # Role matrix
    story.append(section_title(1, "Role Matrix and Responsibilities", h_style))
    role_data = [
        ["Role", "Primary Responsibility", "Where it is controlled"],
        ["Admin / Principal", "Create sections, assign teachers, create section subjects", "Django Admin + restricted teacher subject pages"],
        ["Teacher / Class Teacher", "Assignments, exams, attendance, notes, student management", "Teacher dashboard pages"],
        ["Student", "View subjects, attempt assignments/exams, raise query, track progress", "Student dashboard pages"],
        ["Parent", "Monitor child performance, assignments, attendance, messages", "Parent dashboard pages"],
    ]
    role_table = Table(role_data, colWidths=[3.2 * cm, 7.6 * cm, 6.0 * cm])
    role_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4DBA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(role_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Access control is role-driven and section-aware. Teachers and students only see data mapped to their sections/subjects. Parents see only linked child data.",
        body,
    ))

    # Admin setup
    story.append(section_title(2, "Admin / Principal Setup Workflow", h_style))
    story.append(Paragraph("<b>2.1 Create base masters</b>", sh_style))
    story.append(bullet_list([
        "Create users with correct role: Admin/Principal/Teacher/Class Teacher/Student/Parent.",
        "Create TeacherProfile, StudentProfile, ParentProfile records.",
        "Create ParentStudentRelation to link each parent with one or more children.",
    ], body))

    story.append(Paragraph("<b>2.2 Create sections (single or bulk)</b>", sh_style))
    story.append(bullet_list([
        "Section master stores class level and section (example: UKG-A, 5-B).",
        "Bulk section creation is supported in admin (example input: A,B,C for same class level).",
        "Class teacher can be set while creating/editing section.",
    ], body))

    story.append(Paragraph("<b>2.3 Assign teacher to section and subjects</b>", sh_style))
    story.append(bullet_list([
        "TeacherSectionAssignment maps teacher to section (with option Is Class Teacher).",
        "Admin can map one teacher to multiple sections in one action.",
        "Optional subject mapping in same flow creates SubjectTeacherAssignment records.",
        "Validation ensures subject class level matches section class level.",
        "Validation also ensures one section-subject has only one active subject teacher.",
    ], body))

    story.append(Paragraph("<b>2.4 Create section-wise subjects</b>", sh_style))
    story.append(bullet_list([
        "Subject creation page is restricted to Admin/Principal only.",
        "Subject is created with section context and assigned subject teacher.",
        "Duplicate section+subject assignment is blocked with clear message.",
    ], body))

    story.append(PageBreak())

    # Teacher workflows
    story.append(section_title(3, "Teacher Portal - Daily Working", h_style))
    story.append(Paragraph("<b>3.1 Dashboard and class data scope</b>", sh_style))
    story.append(bullet_list([
        "Teacher dashboard metrics are dynamic (students, active assignments, pending queries, upcoming tests).",
        "All views are filtered by accessible sections and student mappings.",
    ], body))

    story.append(Paragraph("<b>3.2 Assign homework / class test</b>", sh_style))
    story.append(bullet_list([
        "Teacher opens Assign Questions page and selects a valid section.",
        "Teacher enters description, marks, due date, optional file/LaTeX.",
        "System creates Question record mapped to selected section.",
        "Section-specific students get notifications (no cross-section broadcast).",
        "Linked parents also receive assignment notification.",
    ], body))

    story.append(Paragraph("<b>3.3 Create exam and questions</b>", sh_style))
    story.append(bullet_list([
        "Teacher creates exam with title, due date, total marks, timer/duration (optional), section, subject, chapter.",
        "Multiple exam questions can be attached with marks and files.",
        "Exam is visible only to students of target section.",
    ], body))

    story.append(Paragraph("<b>3.4 Upload notes and subject resources</b>", sh_style))
    story.append(bullet_list([
        "Teacher Notes: title, message, optional file, section and subject scope.",
        "Subject Resources: Books, Notes, Video, Quiz, Worksheet under subject.",
        "Only assigned subject teacher can upload for that section-subject.",
        "Students see only published resources for their section/class visibility.",
    ], body))

    story.append(Paragraph("<b>3.5 Attendance, remarks, and communication</b>", sh_style))
    story.append(bullet_list([
        "Attendance can be marked by date and section (Present/Absent/Late).",
        "Upsert logic prevents duplicate attendance row for same student/date.",
        "Teacher reviews submissions and gives marks + remarks.",
        "Teacher can respond to student queries and post class messages/announcements.",
    ], body))

    # Student workflows
    story.append(section_title(4, "Student Portal - Learning Journey", h_style))
    story.append(Paragraph("<b>4.1 What student sees on login</b>", sh_style))
    story.append(bullet_list([
        "Dashboard cards: pending assignments, queries, upcoming exams, graded count.",
        "Subject cards with assigned teacher and resource counters (book/note/video/quiz/worksheet).",
        "Recent subject notes and notification stream.",
    ], body))

    story.append(Paragraph("<b>4.2 Assignment and exam flow</b>", sh_style))
    story.append(bullet_list([
        "Student opens pending assignment list (section-filtered).",
        "Student submits text/file answer before due date.",
        "Teacher evaluates and publishes marks/remarks.",
        "Student can attempt section-specific exams and submit per-question answers.",
        "Submission and grading events trigger notifications.",
    ], body))

    story.append(Paragraph("<b>4.3 Notes, resources, and performance</b>", sh_style))
    story.append(bullet_list([
        "Class Notes page shows teacher notes for student section.",
        "My Subjects page shows resource availability per subject.",
        "Attendance and performance pages show student-level analytics.",
        "Practice with AI and chapter learning pages support extra revision.",
    ], body))

    story.append(PageBreak())

    # Parent workflows
    story.append(section_title(5, "Parent Portal - Monitoring and Feedback", h_style))
    story.append(Paragraph("<b>5.1 Child-based dashboard</b>", sh_style))
    story.append(bullet_list([
        "Parent selects linked child (if multiple children).",
        "Dashboard shows attendance %, pending assignments, upcoming exams, and recent notifications.",
        "All cards are scoped to selected child section.",
    ], body))

    story.append(Paragraph("<b>5.2 Assignments and parent-friendly review</b>", sh_style))
    story.append(bullet_list([
        "Parent can open assignments with marks and teacher remarks.",
        "AI tools provide simplified and parent-friendly feedback language.",
        "Feedback format can be made actionable (what went well, support area, this week action).",
    ], body))

    story.append(Paragraph("<b>5.3 Messages, notes, holidays, exam portion</b>", sh_style))
    story.append(bullet_list([
        "Parent receives class messages/announcements relevant to child section.",
        "Class notes and upcoming exam portion are section-filtered.",
        "Holiday calendar combines global + class + section scope.",
    ], body))

    # E2E scenarios
    story.append(section_title(6, "End-to-End Scenarios (Presentation Friendly)", h_style))
    scenario_data = [
        ["Scenario", "Action Chain", "Visible To"],
        [
            "Section Subject Setup",
            "Admin creates section -> assigns teacher -> creates subject -> maps subject teacher",
            "Teacher sees subject; Student sees subject card",
        ],
        [
            "Assignment Lifecycle",
            "Teacher assigns question to section -> student submits -> teacher remarks -> notifications",
            "Teacher, Student, Parent",
        ],
        [
            "Exam Lifecycle",
            "Teacher creates exam/questions -> student attempts -> teacher evaluates",
            "Teacher, Student, Parent",
        ],
        [
            "Notes Distribution",
            "Teacher uploads notes/resource in section-subject -> student class notes/my subjects updates",
            "Teacher, Student, Parent (class notes view)",
        ],
        [
            "Attendance Lifecycle",
            "Teacher marks attendance -> student attendance page updates -> parent dashboard reflects summary",
            "Teacher, Student, Parent",
        ],
    ]
    sc_table = Table(scenario_data, colWidths=[3.8 * cm, 8.2 * cm, 4.8 * cm])
    sc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.6),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(sc_table)

    story.append(Spacer(1, 8))
    story.append(section_title(7, "Key Controls and Validations", h_style))
    story.append(bullet_list([
        "Strict section-based targeting for assignment/exam notifications.",
        "SubjectTeacherAssignment checks class-level compatibility.",
        "Single section-subject cannot have multiple active subject teachers.",
        "Attendance unique constraint: one record per student per day.",
        "Role-based access methods ensure users only access allowed records.",
    ], body))

    story.append(section_title(8, "10-Minute Demo Script for Senior Presentation", h_style))
    story.append(bullet_list([
        "Minute 1-2: Show Admin setup (Section creation + Teacher assignment).",
        "Minute 3-4: Show Admin/Principal creating section subject and assigning subject teacher.",
        "Minute 5-6: Login as Teacher and assign one homework + one exam to a section.",
        "Minute 7: Login as Student and show assignment/exam visibility and submission.",
        "Minute 8: Teacher checks submission and gives marks + remark.",
        "Minute 9: Login as Parent and show performance card + parent-friendly feedback.",
        "Minute 10: Show notification trail and section-specific visibility proof.",
    ], body))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Appendix: Important URL Prefixes</b>", sh_style))
    story.append(Paragraph(
        "Admin: /admin/ | Teacher: /portal/dashboard/teacher/... | Student: /portal/dashboard/student/... | Parent: /portal/dashboard/parent/...",
        small,
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Prepared for internal review and operational handover. This guide is based on implemented Django views, models, access-control rules, and signal-driven notifications.",
        small,
    ))

    doc.build(story)


if __name__ == "__main__":
    build_pdf(OUTPUT_PATH)
    print(f"PDF generated: {OUTPUT_PATH}")
