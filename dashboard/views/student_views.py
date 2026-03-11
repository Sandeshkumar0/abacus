"""
Student-related views for the dashboard app.
Handles student dashboard, assignments, queries, remarks, and exams.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from django.utils.timezone import now, timedelta
from datetime import datetime
import json
import io
import urllib.parse
import requests
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from django.views.decorators.csrf import csrf_exempt
from accounts.models import StudentProfile, TeacherProfile, TeacherSectionAssignment
from ..access_control import get_accessible_subjects
from ..models import (
    StudentAnswer, Question, Query, Exam, ExamQuestion, ExamAnswer,
    Course, Enrollment, Notification, Subject, Chapter, GroupCompetition,
    SubtopicPerformance, ChapterPerformance, SubjectTeacherAssignment,
    SubjectIntroCache, TeacherNote, AttendanceRecord, SubjectResource,
    StudentSubjectPerformance, SchoolExamResult, Holiday,
)
from ..services.dashboard_metrics import get_student_metrics


def _normalize_class_level(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    for token in ("class", "grade", "std"):
        text = text.replace(token, "")
    return text.replace(" ", "").replace("-", "")


def _teacher_display_name(teacher_profile):
    if not teacher_profile or not getattr(teacher_profile, "user", None):
        return ""
    full_name = (teacher_profile.user.get_full_name() or "").strip()
    if full_name:
        return full_name
    return (teacher_profile.user.email or "").strip()


def _section_teacher_names_by_subject(section, subject_ids):
    if not section or not subject_ids:
        return {}
    mapping = {}
    section_level = _normalize_class_level(section.class_level)
    assignments = SubjectTeacherAssignment.objects.filter(
        section=section,
        subject_id__in=subject_ids,
    ).select_related("teacher__user", "subject", "section")
    for assignment in assignments:
        subject_level = _normalize_class_level(assignment.subject.class_level if assignment.subject else "")
        if section_level and subject_level and section_level != subject_level:
            continue
        teacher_name = _teacher_display_name(assignment.teacher)
        if not teacher_name:
            continue
        names = mapping.setdefault(assignment.subject_id, [])
        if teacher_name not in names:
            names.append(teacher_name)
    return mapping


@login_required(login_url='student_login')
def student_dashboard(request):
    """Main dashboard view for students with real statistics."""
    
    # Get the student's profile
    student_profile, _ = StudentProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'roll_number': f'STU{request.user.id}',
            'student_class': 'Unknown',
            'dob': timezone.now().date(),
            'phone': '0000000000'
        }
    )
    # New profile might not have teacher assigned, handle that gracefully if needed later
    
    # Production-oriented metric aggregation (cached; same UI keys retained)
    metrics = get_student_metrics(request.user)
    total_assignments = metrics["total_assignments"]
    pending_assignments = metrics["pending_assignments"]
    pending_queries = metrics["pending_queries"]
    upcoming_exams = metrics["upcoming_exams"]
    
    # Recent graded answers (last 5)
    recent_graded = StudentAnswer.objects.filter(
        student=student_profile,
        remarks__isnull=False
    ).select_related('question').order_by('-id')[:5]
    
    # Recent query responses (last 5)
    recent_responses = Query.objects.filter(
        student=student_profile,
        response__isnull=False
    ).select_related('responded_by').order_by('-id')[:5]
    
    # Count of recently graded (cached metric)
    recent_graded_count = metrics["recent_graded_count"]
    
    # My Enrolled Courses
    enrollments = (
        Enrollment.objects.filter(student=student_profile)
        .select_related('course')
        .prefetch_related('course__resources')
    )

    # Subject cards for student section/class
    accessible_subjects_qs = get_accessible_subjects(request.user).order_by("name")
    subjects = list(accessible_subjects_qs[:8])
    section = student_profile.section
    language = getattr(request, "LANGUAGE_CODE", "en")
    section_teacher_map = _section_teacher_names_by_subject(section, [subject.id for subject in subjects])
    subject_cards = []
    for subject in subjects:
        teacher_names = section_teacher_map.get(subject.id, [])
        teacher_name = ", ".join(teacher_names) if teacher_names else "Not Assigned"

        notes_qs = TeacherNote.objects.filter(subject=subject, is_published=True)
        if section:
            notes_qs = notes_qs.filter(Q(section=section) | Q(section__isnull=True))
        notes_count = notes_qs.count()

        assignment_qs = Question.objects.filter(subject=subject, is_exam=False)
        if section:
            section_teacher_ids = list(
                SubjectTeacherAssignment.objects.filter(
                    section=section,
                    subject=subject,
                ).values_list("teacher_id", flat=True)
            )
            if student_profile.assigned_teacher_id:
                section_teacher_ids.append(student_profile.assigned_teacher_id)
            assignment_qs = assignment_qs.filter(teacher_id__in=set(section_teacher_ids))
        elif student_profile.assigned_teacher_id:
            assignment_qs = assignment_qs.filter(teacher=student_profile.assigned_teacher)
        assignments_count = assignment_qs.count()

        intro_text = (
            f"{subject.name} helps build strong conceptual understanding with guided practice and section-aligned activities."
        )
        if section:
            intro_cache, _ = SubjectIntroCache.objects.get_or_create(
                subject=subject,
                section=section,
                language=language,
                defaults={"intro_text": intro_text},
            )
            intro_text = intro_cache.intro_text

        subject_cards.append(
            {
                "subject": subject,
                "teacher_name": teacher_name,
                "notes_count": notes_count,
                "assignments_count": assignments_count,
                "intro_text": intro_text,
            }
        )

    # Pending assignments list (for dashboard panel)
    pending_assignment_items = (
        Question.objects.exclude(
            id__in=StudentAnswer.objects.filter(student=student_profile).values_list("question_id", flat=True)
        )
        .filter(section=student_profile.section)
        .order_by("due_date")[:6]
    )

    # Class notes from course resources
    class_notes = []
    for enrollment in enrollments:
        for resource in enrollment.course.resources.all():
            class_notes.append(
                {
                    "title": resource.title,
                    "course_title": enrollment.course.title,
                    "file_url": resource.file.url,
                    "uploaded_at": resource.uploaded_at,
                }
            )
    class_notes = sorted(class_notes, key=lambda x: x["uploaded_at"], reverse=True)[:8]

    # Messages feed from notifications
    messages_feed = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:8]

    # Holiday calendar (lightweight placeholder data)
    holiday_calendar = [
        {"name": "Republic Day", "date": "2026-01-26"},
        {"name": "Holi", "date": "2026-03-04"},
        {"name": "Independence Day", "date": "2026-08-15"},
        {"name": "Gandhi Jayanti", "date": "2026-10-02"},
        {"name": "Diwali", "date": "2026-11-08"},
        {"name": "Christmas", "date": "2026-12-25"},
    ]

    # Upcoming exam portion
    upcoming_exam_portion = (
        Exam.objects.filter(section=student_profile.section).exclude(answers__student=student_profile)
        .filter(due_date__gte=timezone.now())
        .select_related("subject", "chapter")
        .order_by("due_date")[:8]
    )

    # Performance Analysis
    # Fetch all graded answers (Assignments + Exams)
    # We need to link Questions (Assignment) -> Chapter and Exam -> Chapter
    
    from collections import defaultdict
    
    # Structure: { chapter_id: { 'name': str, 'total_obtained': int, 'total_max': int, 'ncert': str } }
    performance_map = defaultdict(lambda: {'name': '', 'total_obtained': 0, 'total_max': 0, 'ncert': ''})

    # 1. Assignment Performance
    graded_assignments = StudentAnswer.objects.filter(
        student=student_profile,
        remarks__isnull=False
    ).select_related('question__chapter')

    for ans in graded_assignments:
        chapter = ans.question.chapter
        if chapter:
            performance_map[chapter.id]['name'] = chapter.name
            performance_map[chapter.id]['ncert'] = chapter.ncert_reference
            if ans.marks_obtained is not None:
                performance_map[chapter.id]['total_obtained'] += ans.marks_obtained
            # Assuming question.max_marks is the total for this assignment
            performance_map[chapter.id]['total_max'] += ans.question.max_marks

    # 2. Exam Performance
    # Exams might be linked to a chapter directly, or we might need to look at questions?
    # The requirement says "teacher creates exam... select Subject/Chapter". 
    # So the Exam object itself has a 'chapter' field.
    
    graded_exams = Exam.objects.filter(
        answers__student=student_profile,
        answers__marks_obtained__isnull=False
    ).distinct().select_related('chapter')

    # We need to sum up marks for each exam attempt. 
    # Logic: For each exam, get total obtained and total max. 
    # If exam has a chapter, add to that chapter's stats.
    
    for exam in graded_exams:
        if exam.chapter:
            # Calculate total obtained by student in this exam
            obtained = ExamAnswer.objects.filter(
                exam=exam, 
                student=student_profile
            ).aggregate(sum_marks=Sum('marks_obtained'))['sum_marks'] or 0
            
            # Total marks for the exam
            max_marks = exam.total_marks
            
            performance_map[exam.chapter.id]['name'] = exam.chapter.name
            performance_map[exam.chapter.id]['ncert'] = exam.chapter.ncert_reference
            performance_map[exam.chapter.id]['total_obtained'] += obtained
            performance_map[exam.chapter.id]['total_max'] += max_marks

    # Calculate Status
    performance_data = []
    for chat_id, data in performance_map.items():
        if data['total_max'] > 0:
            percentage = (data['total_obtained'] / data['total_max']) * 100
        else:
            percentage = 0
            
        if percentage >= 75:
            status = 'Strong'
            color = 'green'
        elif percentage >= 50:
            status = 'Moderate'
            color = 'yellow'
        else:
            status = 'Weak'
            color = 'red'
            
        performance_data.append({
            'chapter_name': data['name'],
            'ncert_link': data['ncert'],
            'percentage': round(percentage, 1),
            'status': status,
            'color': color
        })

    # Subject-level performance built from manual school result uploads.
    subject_performance_qs = StudentSubjectPerformance.objects.filter(
        student=student_profile
    ).select_related("subject").order_by("subject__name")

    subject_performance_rows = []
    total_obtained_all = 0.0
    total_marks_all = 0.0
    strong_count = 0
    weak_count = 0
    top_subject_name = ""
    top_subject_percentage = -1.0

    for row in subject_performance_qs:
        percentage = round(float(row.percentage or 0), 1)
        if percentage >= 75:
            color = "green"
            strong_count += 1
        elif percentage >= 40:
            color = "yellow"
        else:
            color = "red"
            weak_count += 1

        subject_performance_rows.append(
            {
                "subject_name": row.subject.name,
                "percentage": percentage,
                "marks_obtained": row.marks_obtained,
                "total_marks": row.total_marks,
                "ai_remark": row.ai_remark,
                "color": color,
            }
        )

        total_obtained_all += float(row.marks_obtained or 0)
        total_marks_all += float(row.total_marks or 0)
        if percentage > top_subject_percentage:
            top_subject_percentage = percentage
            top_subject_name = row.subject.name

    overall_percentage = round((total_obtained_all / total_marks_all) * 100, 1) if total_marks_all > 0 else 0
    subject_performance_summary = {
        "overall_percentage": overall_percentage,
        "total_subjects": len(subject_performance_rows),
        "strong_count": strong_count,
        "weak_count": weak_count,
        "top_subject_name": top_subject_name,
        "top_subject_percentage": round(top_subject_percentage, 1) if top_subject_percentage >= 0 else 0,
    }

    # Subject-wise graph data from 3 sources:
    # 1) Assignments (StudentAnswer)
    # 2) Tests/Exams (ExamAnswer)
    # 3) Teacher uploaded school results (SchoolExamResult)
    selected_perf_subject = (request.GET.get("perf_subject") or "").strip()
    selected_perf_days = (request.GET.get("perf_days") or "all").strip().lower()
    if selected_perf_days not in {"all", "30", "90"}:
        selected_perf_days = "all"
    cutoff_dt = None
    cutoff_date = None
    if selected_perf_days != "all":
        cutoff_dt = timezone.now() - timedelta(days=int(selected_perf_days))
        cutoff_date = cutoff_dt.date()

    selected_subject_id = None
    if selected_perf_subject.isdigit():
        selected_subject_id = int(selected_perf_subject)

    subject_metrics_map = {}
    for sub in accessible_subjects_qs:
        if selected_subject_id and sub.id != selected_subject_id:
            continue
        subject_metrics_map[sub.id] = {
            "subject_name": sub.name,
            "assignment_count": 0,
            "assignment_obtained": 0.0,
            "assignment_total": 0.0,
            "test_count": 0,
            "test_obtained": 0.0,
            "test_total": 0.0,
            "result_count": 0,
            "result_obtained": 0.0,
            "result_total": 0.0,
        }

    assignment_answers = StudentAnswer.objects.filter(
        student=student_profile,
        question__subject__isnull=False,
    ).select_related("question__subject", "question")
    if cutoff_dt:
        assignment_answers = assignment_answers.filter(submitted_at__gte=cutoff_dt)
    if selected_subject_id:
        assignment_answers = assignment_answers.filter(question__subject_id=selected_subject_id)
    for ans in assignment_answers:
        sid = ans.question.subject_id
        if not sid:
            continue
        row = subject_metrics_map.setdefault(
            sid,
            {
                "subject_name": ans.question.subject.name,
                "assignment_count": 0,
                "assignment_obtained": 0.0,
                "assignment_total": 0.0,
                "test_count": 0,
                "test_obtained": 0.0,
                "test_total": 0.0,
                "result_count": 0,
                "result_obtained": 0.0,
                "result_total": 0.0,
            },
        )
        row["assignment_count"] += 1
        max_marks = float(ans.question.max_marks or 0)
        if max_marks > 0 and ans.marks_obtained is not None:
            row["assignment_obtained"] += float(ans.marks_obtained or 0)
            row["assignment_total"] += max_marks

    exam_subject_rows = (
        ExamAnswer.objects.filter(
            student=student_profile,
            exam__subject__isnull=False,
        )
        .filter(**({"submitted_at__gte": cutoff_dt} if cutoff_dt else {}))
        .filter(**({"exam__subject_id": selected_subject_id} if selected_subject_id else {}))
        .values("exam_id", "exam__subject_id", "exam__subject__name", "exam__total_marks")
        .annotate(obtained=Sum("marks_obtained"))
    )
    for item in exam_subject_rows:
        sid = item.get("exam__subject_id")
        if not sid:
            continue
        row = subject_metrics_map.setdefault(
            sid,
            {
                "subject_name": item.get("exam__subject__name") or f"Subject {sid}",
                "assignment_count": 0,
                "assignment_obtained": 0.0,
                "assignment_total": 0.0,
                "test_count": 0,
                "test_obtained": 0.0,
                "test_total": 0.0,
                "result_count": 0,
                "result_obtained": 0.0,
                "result_total": 0.0,
            },
        )
        row["test_count"] += 1
        total_marks = float(item.get("exam__total_marks") or 0)
        if total_marks > 0:
            row["test_obtained"] += float(item.get("obtained") or 0)
            row["test_total"] += total_marks

    teacher_result_rows = (
        SchoolExamResult.objects.filter(
            student=student_profile,
            subject__isnull=False,
        )
        .filter(**({"subject_id": selected_subject_id} if selected_subject_id else {}))
        .filter(
            Q(exam_date__gte=cutoff_date)
            | Q(exam_date__isnull=True, created_at__gte=cutoff_dt)
            if cutoff_dt
            else Q()
        )
        .values("subject_id", "subject__name")
        .annotate(
            result_count=Count("id"),
            obtained=Sum("marks_obtained"),
            total=Sum("total_marks"),
        )
    )
    for item in teacher_result_rows:
        sid = item.get("subject_id")
        if not sid:
            continue
        row = subject_metrics_map.setdefault(
            sid,
            {
                "subject_name": item.get("subject__name") or f"Subject {sid}",
                "assignment_count": 0,
                "assignment_obtained": 0.0,
                "assignment_total": 0.0,
                "test_count": 0,
                "test_obtained": 0.0,
                "test_total": 0.0,
                "result_count": 0,
                "result_obtained": 0.0,
                "result_total": 0.0,
            },
        )
        row["result_count"] = int(item.get("result_count") or 0)
        row["result_obtained"] += float(item.get("obtained") or 0)
        row["result_total"] += float(item.get("total") or 0)

    subject_metrics_rows = []
    subject_graph_labels = []
    assignment_pct_series = []
    test_pct_series = []
    teacher_result_pct_series = []
    for row in sorted(subject_metrics_map.values(), key=lambda x: x["subject_name"].lower()):
        if (
            row["assignment_count"] == 0
            and row["test_count"] == 0
            and row["result_count"] == 0
        ):
            continue

        assignment_pct = round((row["assignment_obtained"] / row["assignment_total"]) * 100, 1) if row["assignment_total"] > 0 else 0
        test_pct = round((row["test_obtained"] / row["test_total"]) * 100, 1) if row["test_total"] > 0 else 0
        teacher_result_pct = round((row["result_obtained"] / row["result_total"]) * 100, 1) if row["result_total"] > 0 else 0

        subject_metrics_rows.append(
            {
                "subject_name": row["subject_name"],
                "assignment_count": row["assignment_count"],
                "test_count": row["test_count"],
                "result_count": row["result_count"],
                "assignment_percentage": assignment_pct,
                "test_percentage": test_pct,
                "result_percentage": teacher_result_pct,
            }
        )
        subject_graph_labels.append(row["subject_name"])
        assignment_pct_series.append(assignment_pct)
        test_pct_series.append(test_pct)
        teacher_result_pct_series.append(teacher_result_pct)

    performance_subject_options = [
        {"id": sub.id, "name": sub.name}
        for sub in accessible_subjects_qs
    ]

    context = {
        'total_assignments': total_assignments,
        'pending_assignments': pending_assignments,
        'pending_queries': pending_queries,
        'upcoming_exams': upcoming_exams,
        'subjects': subjects,
        'subject_cards': subject_cards,
        'pending_assignment_items': pending_assignment_items,
        'class_notes': class_notes,
        'messages_feed': messages_feed,
        'holiday_calendar': holiday_calendar,
        'upcoming_exam_portion': upcoming_exam_portion,
        'recent_graded': recent_graded,
        'recent_responses': recent_responses,
        'recent_graded_count': recent_graded_count,
        'enrollments': enrollments,
        'performance_data': performance_data,
        'subject_performance_rows': subject_performance_rows,
        'subject_performance_summary': subject_performance_summary,
        'subject_metrics_rows': subject_metrics_rows,
        'subject_graph_labels': subject_graph_labels,
        'assignment_pct_series': assignment_pct_series,
        'test_pct_series': test_pct_series,
        'teacher_result_pct_series': teacher_result_pct_series,
        'performance_subject_options': performance_subject_options,
        'selected_perf_subject': selected_perf_subject,
        'selected_perf_days': selected_perf_days,
    }
    
    return render(request, 'student/student_dashboard.html', context)


@login_required
def submit_answer(request):
    """Handle student answer submission for assignments."""
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        answer_text = request.POST.get('answer')
        answer_file = request.FILES.get('answer_file')

        try:
            student_profile = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Student profile not found'}, status=403)

        question_qs = Question.objects.filter(id=question_id)
        if student_profile.assigned_teacher_id:
            question_qs = question_qs.filter(teacher=student_profile.assigned_teacher)

        question = question_qs.first()
        if not question:
            return JsonResponse(
                {'status': 'error', 'message': 'Question not found for your assigned teacher'},
                status=404
            )

        StudentAnswer.objects.update_or_create(
            student=student_profile,
            student_name=request.user,
            student_roll=student_profile,
            question=question,
            defaults={
                'answer_text': answer_text,
                'answer_file': answer_file
            }
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def download_answer_pdf(request, question_id):
    """Generate and download PDF of student's answer for a specific question."""
    question = get_object_or_404(Question, id=question_id)
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        raise Http404("Student profile not found")
    answer = StudentAnswer.objects.filter(student=student_profile, question=question).first()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    # Header
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, f"Question {question.id}")
    y -= 30

    # Question text
    p.setFont("Helvetica", 12)
    text = question.description.split("LaTeX Equation:")[0].strip()
    for line in text.split('\n'):
        p.drawString(50, y, line)
        y -= 20

    # If equation present
    if "LaTeX Equation:" in question.description:
        latex = question.description.split("LaTeX Equation:")[1].strip()
        latex_url = f"https://latex.codecogs.com/png.image?\\dpi{{150}} {urllib.parse.quote(latex)}"
        img_data = requests.get(latex_url).content

        with open("temp_eq.png", "wb") as f:
            f.write(img_data)

        img = Image.open("temp_eq.png")
        img_width, img_height = img.size

        max_width = 60
        scale = max_width / img_width
        new_width = max_width
        new_height = img_height * scale

        y -= new_height + 10
        p.drawInlineImage("temp_eq.png", 50, y, width=new_width, height=new_height)
        y -= 20

    # Answer Section
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Answer:")
    y -= 30

    if answer and answer.answer_text:
        p.setFont("Helvetica", 12)
        for line in answer.answer_text.split('\n'):
            if y < 100:  # new page if space low
                p.showPage()
                y = height - 50
            p.drawString(50, y, line)
            y -= 20
    else:
        p.setFont("Helvetica-Oblique", 12)
        p.drawString(50, y, "No answer submitted.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Answer_Q{question.id}.pdf")


@login_required
def student_assign(request):
    """View assigned questions for the student."""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/view_assigned_questions.html', {
            'questions': [],
            'completed_count': 0,
            'pending_count': 0,
            'error_message': 'No student profile found. Please contact administrator.'
        })
    all_questions = Question.objects.all()
    if student_profile.section_id:
        all_questions = all_questions.filter(section=student_profile.section)
    else:
        all_questions = all_questions.none()
    if student_profile.assigned_teacher_id:
        all_questions = all_questions.filter(teacher=student_profile.assigned_teacher)
    all_questions = all_questions.order_by('created_at')
    answered_q_ids = StudentAnswer.objects.filter(student=student_profile).values_list('question_id', flat=True)
    unanswered_questions = all_questions.exclude(id__in=answered_q_ids)

    questions = []
    for q in unanswered_questions:
        desc = q.description
        if "LaTeX Equation:" in desc:
            parts = desc.split("LaTeX Equation:")
            question_text = parts[0].strip()
            latex = parts[1].strip()
        else:
            question_text = desc.strip()
            latex = ""
        questions.append({
            'id': q.id,
            'question_text': question_text,
            'latex': latex,
            'due_date': q.due_date,
            'max_marks': q.max_marks,
            'is_exam': q.is_exam,
            'file': q.image.url if q.image else None
        })

    completed_count = StudentAnswer.objects.filter(student=student_profile).count()
    pending_count = unanswered_questions.count()

    return render(request, 'student/view_assigned_questions.html', {
        'questions': questions,
        'completed_count': completed_count,
        'pending_count': pending_count,
    })


@login_required
def student_competitions(request):
    """List group competitions for the logged-in student and allow direct participation."""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete. Please contact an administrator.'
        })

    competitions = GroupCompetition.objects.filter(
        is_active=True,
        group__students=student_profile
    ).select_related('group', 'question').order_by('-created_at')

    items = []
    for comp in competitions:
        ans = StudentAnswer.objects.filter(student=student_profile, question=comp.question).first()
        items.append({
            'competition_id': comp.id,
            'group_name': comp.group.name,
            'question': comp.question,
            'submitted': bool(ans),
            'submitted_at': ans.submitted_at if ans else None,
            'answer_text': ans.answer_text if ans else "",
        })

    return render(request, 'student/competitions.html', {'competition_items': items})


@login_required
def student_profile(request):
    """Display student profile."""
    student, _ = StudentProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'roll_number': f'STU{request.user.id}',
            'student_class': 'Unknown',
            'dob': timezone.now().date(),
            'phone': '0000000000',
            'assigned_teacher': TeacherProfile.objects.first(),
        }
    )
    return render(request, 'student/profile.html', {'student': student})


@login_required
def student_profile_edit(request):
    """Edit student profile - update profile picture."""
    try:
        student = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete. Please contact an administrator.'
        })
    
    if request.method == 'POST':
        # Update profile picture if uploaded
        if 'profile_picture' in request.FILES:
            student.profile_picture = request.FILES['profile_picture']
            student.save()
        
        return redirect('student_profile')
    
    return render(request, 'student/profile_edit.html', {'student': student})


@login_required
def raise_query(request):
    """Allow students to raise queries with statistics."""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete. Please contact an administrator.'
        })

    if request.method == 'POST':
        query_text = request.POST.get('query_text')
        query_file = request.FILES.get('query_file')

        Query.objects.create(
            student=student_profile,
            student_name=request.user,
            student_roll=student_profile,
            query_text=query_text,
            query_image=query_file
        )
        return redirect('raise_query')

    # Stats calculation
    total_queries = Query.objects.filter(student=student_profile).count()
    resolved_queries = Query.objects.filter(student=student_profile).exclude(response="").count()
    unresolved_queries = total_queries - resolved_queries

    # Resolution rate
    resolution_rate = int((resolved_queries / total_queries) * 100) if total_queries > 0 else 0

    # Team utilization
    one_week_ago = now() - timedelta(days=7)
    utilization = Query.objects.filter(submitted_at__gte=one_week_ago).values('responded_by').annotate(total=Count('id'))
    total_teachers = TeacherProfile.objects.count()
    total_assignments = sum(entry['total'] for entry in utilization)
    team_utilization = int((total_assignments / (total_teachers or 1)) * 100)

    # Avg. response time
    avg_response_qs = Query.objects.filter(response__isnull=False).annotate(
        response_time=ExpressionWrapper(F('responded_by__user__date_joined') - F('submitted_at'), output_field=DurationField())
    ).aggregate(avg_time=Avg('response_time'))

    avg_response_days = round(avg_response_qs['avg_time'].days if avg_response_qs['avg_time'] else 0)

    context = {
        'active_queries': unresolved_queries,
        'resolution_rate': resolution_rate,
        'team_utilization': team_utilization,
        'avg_response_days': avg_response_days,
    }

    return render(request, 'student/raise_query.html', context)


@login_required
def view_remarks(request):
    """View remarks/feedback on submitted answers."""
    try:
        student = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete. Please contact an administrator.'
        })
    student_answers_raw = StudentAnswer.objects.filter(student=student).select_related('question')

    student_answers = []
    for ans in student_answers_raw:
        desc = ans.question.description
        if "LaTeX Equation:" in desc:
            parts = desc.split("LaTeX Equation:")
            question_text = parts[0].strip()
            latex = parts[1].strip()
        else:
            question_text = desc.strip()
            latex = ""
        student_answers.append({
            'question_number': ans.question.id,
            'question_text': question_text,
            'latex': latex,
            'answer_text': ans.answer_text,
            'answer_file': ans.answer_file.url if ans.answer_file else None,
            'question_file': ans.question.image.url if ans.question.image else None,
            'remarks': ans.remarks,
            'teacher_name': ans.question.teacher_name.get_full_name() if ans.question.teacher_name else None
        })

    total_answers = len(student_answers)
    graded_count = sum(1 for ans in student_answers if ans['remarks'])
    pending_review = total_answers - graded_count

    context = {
        'student_answers': student_answers,
        'total_answers': total_answers,
        'graded_count': graded_count,
        'pending_review': pending_review,
    }

    return render(request, 'student/view_remarks.html', context)


@login_required
def get_exam_questions(request, exam_id):
    """Get exam questions for a student (API endpoint)."""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Profile missing"}, status=403)
    exam = get_object_or_404(Exam, id=exam_id)
    if not student_profile.section_id or exam.section_id != student_profile.section_id:
        return JsonResponse({"status": "error", "message": "Exam not assigned to your section."}, status=403)

    # Prevent showing if already attempted
    if ExamAnswer.objects.filter(exam=exam, student=student_profile).exists():
        return JsonResponse({"status": "completed"})

    questions = []
    for q in exam.questions.all():
        questions.append({
            "id": q.id,
            "question_text": q.text,
            "latex": q.latex,
            "marks": q.marks,
        })

    return JsonResponse({
        "status": "ok",
        "exam": exam.title,
        "questions": questions,
        "timer_enabled": exam.timer_enabled,
        "duration_minutes": exam.duration_minutes,
    })


@login_required
def attempt_exam(request, exam_id):
    """Handle exam attempt by student."""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete. Please contact an administrator.'
        })
    exam = get_object_or_404(Exam, id=exam_id)
    if not student_profile.section_id or exam.section_id != student_profile.section_id:
        return render(request, 'student/profile_missing.html', {
            'message': 'This exam is not assigned to your section.'
        })

    if ExamAnswer.objects.filter(exam=exam, student=student_profile).exists():
        return redirect("give_test")

    attempt_start_key = f"exam_attempt_{exam.id}_student_{student_profile.user_id}_start"
    now = timezone.now()
    attempt_start = request.session.get(attempt_start_key)
    attempt_start_dt = None
    if attempt_start:
        try:
            attempt_start_dt = datetime.fromisoformat(attempt_start)
            if timezone.is_naive(attempt_start_dt):
                attempt_start_dt = timezone.make_aware(attempt_start_dt)
        except Exception:
            attempt_start_dt = None
    if exam.timer_enabled and not attempt_start_dt:
        attempt_start_dt = now
        request.session[attempt_start_key] = attempt_start_dt.isoformat()

    if request.method == "POST":
        elapsed_seconds = 0
        if exam.timer_enabled and attempt_start_dt:
            elapsed_seconds = max(0, int((now - attempt_start_dt).total_seconds()))
        elif exam.timer_enabled and not attempt_start_dt:
            messages.error(request, "Exam timer session missing. Please restart exam attempt.")
            return redirect("give_test")

        for q in exam.questions.all():
            answer_text = request.POST.get(f"answer_{q.id}", "").strip()
            answer_file = request.FILES.get(f"answer_file_{q.id}")

            ExamAnswer.objects.create(
                exam=exam,
                student=student_profile,
                student_name=request.user,
                student_roll=student_profile,
                question=q,
                answer_text=answer_text,
                answer_file=answer_file,
                marks_obtained=0,
                time_taken_seconds=elapsed_seconds,
            )
        if attempt_start_key in request.session:
            request.session.pop(attempt_start_key, None)
        return redirect("give_test")

    remaining_seconds = None
    if exam.timer_enabled and exam.duration_minutes and attempt_start_dt:
        total_seconds = int(exam.duration_minutes) * 60
        elapsed = max(0, int((now - attempt_start_dt).total_seconds()))
        remaining_seconds = max(0, total_seconds - elapsed)
        if remaining_seconds <= 0:
            messages.error(request, "Time is over for this exam.")
            return redirect("give_test")

    context = {
        "exam": exam,
        "questions": exam.questions.all(),
        "timer_enabled": exam.timer_enabled,
        "duration_minutes": exam.duration_minutes,
        "remaining_seconds": remaining_seconds,
    }
    return render(request, "student/attempt_exam.html", context)


@login_required
def download_exam_answer_pdf(request, exam_id):
    """Generate PDF for all exam answers of the logged-in student."""
    exam = get_object_or_404(Exam, id=exam_id)
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        raise Http404("Student profile not found")
    answers = ExamAnswer.objects.filter(exam=exam, student=student_profile)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    # Exam Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"Exam: {exam.title}")
    y -= 40

    for idx, ans in enumerate(answers, start=1):
        q = ans.question

        # Question Heading
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, f"Q{idx}. {q.text}")
        y -= 25

        # Render LaTeX if present
        if q.latex:
            latex_url = f"https://latex.codecogs.com/png.image?\\dpi{{150}} {urllib.parse.quote(q.latex)}"
            img_data = requests.get(latex_url).content
            with open("temp_eq.png", "wb") as f:
                f.write(img_data)

            img = Image.open("temp_eq.png")
            img_width, img_height = img.size
            max_width = 200
            scale = max_width / img_width
            new_width = max_width
            new_height = img_height * scale

            y -= new_height + 10
            p.drawInlineImage("temp_eq.png", 50, y, width=new_width, height=new_height)
            y -= 20

        # Answer text
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "Answer:")
        y -= 20

        if ans.answer_text:
            p.setFont("Helvetica", 11)
            for line in ans.answer_text.split("\n"):
                if y < 100:
                    p.showPage()
                    y = height - 50
                p.drawString(60, y, line)
                y -= 18
        else:
            p.setFont("Helvetica-Oblique", 11)
            p.drawString(60, y, "No answer submitted.")
            y -= 20

        y -= 30

        if y < 100:
            p.showPage()
            y = height - 50

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Exam_{exam.id}_Answers.pdf")


@login_required
def give_test(request):
    """View all exams (completed and new) for the student."""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete. Please contact an administrator.'
        })

    # Completed exams
    completed_exams = Exam.objects.filter(
        section=student_profile.section,
        answers__student=student_profile
    ).distinct()

    for exam in completed_exams:
        exam.student_answers = ExamAnswer.objects.filter(
            exam=exam,
            student=student_profile
        ).select_related("question")

        exam.obtained = exam.student_answers.aggregate(
            total=Sum("marks_obtained")
        )["total"] or 0

    # New exams
    new_exams = Exam.objects.filter(section=student_profile.section).exclude(
        answers__student=student_profile
    )

    return render(request, "student/give_test.html", {
        "completed_exams": completed_exams,
        "new_exams": new_exams,
    })

@login_required(login_url='student_login')
def enroll_course(request, course_id):
    """Enroll the current student in a course."""
    if not request.user.is_student:
        return redirect('student_dashboard')
    
    course = get_object_or_404(Course, id=course_id)
    student, _ = StudentProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'roll_number': f'STU{request.user.id}',
            'student_class': 'Unknown',
            'dob': timezone.now().date(),
            'phone': '0000000000'
        }
    )
    
    _, created = Enrollment.objects.get_or_create(student=student, course=course)
    
    if created:
        Notification.objects.create(
            recipient=request.user,
            notification_type='general',
            title='Course Enrollment Successful',
            message=f'You have successfully enrolled in {course.title}.',
            link='/dashboard/student/dashboard/'
        )
    
    return redirect('student_dashboard')


@login_required
def practice_questions_page(request):
    """Render the AI practice questions page."""
    return render(request, 'student/practice_questions.html')


@login_required
def virtual_abacus(request):
    """Render standalone virtual abacus page."""
    return render(request, "student/virtual_abacus.html")


@login_required
def virtual_abacus_ai_tutor(request):
    """AI tutor for explaining abacus concepts in child-friendly language."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    topic = (payload.get("topic") or "").strip()
    question = (payload.get("question") or "").strip()
    language = (payload.get("language") or "english").strip().lower()

    if not topic and not question:
        return JsonResponse({"error": "Please provide a topic or question."}, status=400)

    allowed_languages = {
        "english": "English",
        "hindi": "Hindi",
        "odia": "Odia",
    }
    if language not in allowed_languages:
        language = "english"

    def fallback_text(selected_topic, selected_question, lang):
        if lang == "hindi":
            return (
                f"Concept: {selected_topic or 'Abacus basics'}\n"
                "Step 1: Abacus me upar wali bead ka value 5 hota hai, niche wali bead ka value 1 hota hai.\n"
                "Step 2: Right se left place value badhta hai: ones, tens, hundreds.\n"
                "Step 3: Number banate waqt pehle ones column set karo, phir tens.\n"
                f"Practice: {selected_question or '47 ya 305 ko abacus par set karke dekho.'}"
            )
        if lang == "odia":
            return (
                f"Concept: {selected_topic or 'Abacus basics'}\n"
                "Step 1: ଉପର bead ର value 5, ତଳ bead ର value 1 ଅଟେ।\n"
                "Step 2: ଡାହାଣୁ ବାମକୁ place value ବଢେ: ones, tens, hundreds.\n"
                "Step 3: Number set କରିବାବେଳେ ପ୍ରଥମେ ones, ପରେ tens set କର।\n"
                f"Practice: {selected_question or '47 କିମ୍ବା 305 କୁ abacus ରେ set କର।'}"
            )
        return (
            f"Concept: {selected_topic or 'Abacus basics'}\n"
            "Step 1: On an abacus, each upper bead is worth 5 and each lower bead is worth 1.\n"
            "Step 2: Columns from right to left are ones, tens, hundreds, and so on.\n"
            "Step 3: Build numbers by setting ones first, then tens, then higher places.\n"
            f"Practice: {selected_question or 'Try setting 47 and 305 on the abacus.'}"
        )

    prompt = (
        "You are an abacus tutor for school children.\n"
        f"Language: {allowed_languages[language]}\n"
        "Explain in very simple words for kids (age 8-14).\n"
        "Keep response in this format only:\n"
        "Concept: ...\n"
        "Step 1: ...\n"
        "Step 2: ...\n"
        "Step 3: ...\n"
        "Practice: ...\n"
        "Do not use markdown.\n\n"
        f"Topic: {topic or 'General abacus concept'}\n"
        f"Student question: {question or 'Explain with a simple example'}\n"
    )

    try:
        from .ai_utils import client, clean_ai_text

        if not client:
            return JsonResponse({"answer": fallback_text(topic, question, language)})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
        )
        raw = response.choices[0].message.content
        return JsonResponse({"answer": clean_ai_text(raw)})
    except Exception:
        return JsonResponse({"answer": fallback_text(topic, question, language)})


@login_required
def holiday_calendar(request):
    """Show holiday calendar page for students (general + section holidays)."""
    student = StudentProfile.objects.select_related("section").filter(user=request.user).first()
    section = student.section if student else None
    holidays_qs = Holiday.objects.all()
    if section:
        holidays_qs = holidays_qs.filter(
            Q(holiday_type=Holiday.TYPE_GENERAL) | Q(holiday_type=Holiday.TYPE_SECTION, section=section)
        )
    else:
        holidays_qs = holidays_qs.filter(holiday_type=Holiday.TYPE_GENERAL)

    holidays = [
        {
            "name": item.title,
            "date": item.date.isoformat(),
            "description": item.description or "",
            "type": item.holiday_type,
        }
        for item in holidays_qs.order_by("date", "title")
    ]
    return render(request, "student/holiday_calendar.html", {"holidays": holidays})


@login_required
def student_attendance(request):
    """Display attendance records marked by teachers for the logged-in student."""
    try:
        student_profile = StudentProfile.objects.select_related(
            "user",
            "assigned_teacher__user",
            "section__class_teacher__user",
        ).get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(
            request,
            "student/profile_missing.html",
            {"message": "Your student profile is incomplete. Please contact an administrator."},
        )

    selected_year = request.GET.get("year", "").strip()
    selected_session = request.GET.get("session", "").strip()

    # Strict scope:
    # 1) Only this logged-in student's attendance
    # 2) Only attendance marked by the section class teacher (not assigned/subject teachers)
    attendance_qs = AttendanceRecord.objects.filter(
        student=student_profile
    ).select_related("teacher__user")

    class_teacher = student_profile.section.class_teacher if student_profile.section else None
    # Fallback: many setups store class-teacher role in TeacherSectionAssignment
    # while section.class_teacher may still be null.
    if not class_teacher and student_profile.section_id:
        class_teacher_assignment = (
            TeacherSectionAssignment.objects.filter(
                section=student_profile.section,
                is_class_teacher=True,
            )
            .select_related("teacher__user")
            .first()
        )
        if class_teacher_assignment and class_teacher_assignment.teacher:
            class_teacher = class_teacher_assignment.teacher
            # Keep section mapping in sync so all screens behave consistently.
            try:
                section_obj = student_profile.section
                section_obj.class_teacher = class_teacher
                section_obj.save(update_fields=["class_teacher"])
            except Exception:
                pass

    if class_teacher:
        attendance_qs = attendance_qs.filter(teacher=class_teacher)
    else:
        attendance_qs = attendance_qs.none()

    available_years = list(
        attendance_qs.order_by("-date").dates("date", "year")
    )
    available_year_values = [str(d.year) for d in available_years]

    if selected_year and selected_year.isdigit():
        attendance_qs = attendance_qs.filter(date__year=int(selected_year))
    elif available_year_values:
        selected_year = available_year_values[0]
        attendance_qs = attendance_qs.filter(date__year=int(selected_year))

    # Session mapping:
    # `odd`: Jul-Dec
    # `even`: Jan-Jun
    if selected_session == "odd":
        attendance_qs = attendance_qs.filter(date__month__gte=7, date__month__lte=12)
    elif selected_session == "even":
        attendance_qs = attendance_qs.filter(date__month__gte=1, date__month__lte=6)

    total_days = attendance_qs.count()
    present_count = attendance_qs.filter(status=AttendanceRecord.STATUS_PRESENT).count()
    absent_count = attendance_qs.filter(status=AttendanceRecord.STATUS_ABSENT).count()
    late_count = attendance_qs.filter(status=AttendanceRecord.STATUS_LATE).count()
    attendance_percentage = round((present_count / total_days) * 100, 2) if total_days else 0

    # Keep attendance table simple: exactly one aggregated row for class teacher.
    teacher_rows = []
    if class_teacher:
        teacher_rows.append(
            {
                "subject_name": "General",
                "faculty_name": class_teacher.user.get_full_name() if class_teacher.user else "Class Teacher",
                "absent": absent_count,
                "total_percentage": attendance_percentage,
                "total_days": total_days,
                "present": present_count,
                "excuses": late_count,
            }
        )

    latest_marked_at = attendance_qs.order_by("-updated_at").values_list("updated_at", flat=True).first()

    # Cumulative report till yesterday (as requested: "kal tak")
    yesterday = timezone.localdate() - timedelta(days=1)
    cumulative_qs = attendance_qs.filter(date__lte=yesterday)
    cumulative_total_days = cumulative_qs.count()
    cumulative_present = cumulative_qs.filter(status=AttendanceRecord.STATUS_PRESENT).count()
    cumulative_absent = cumulative_qs.filter(status=AttendanceRecord.STATUS_ABSENT).count()
    cumulative_late = cumulative_qs.filter(status=AttendanceRecord.STATUS_LATE).count()
    cumulative_percentage = round((cumulative_present / cumulative_total_days) * 100, 2) if cumulative_total_days else 0

    context = {
        "student": student_profile,
        "class_teacher_name": class_teacher.user.get_full_name() if class_teacher and class_teacher.user else "Not Assigned",
        "class_teacher_assigned": bool(class_teacher),
        "latest_marked_at": latest_marked_at,
        "selected_year": selected_year,
        "selected_session": selected_session,
        "available_year_values": available_year_values,
        "teacher_rows": teacher_rows,
        "summary": {
            "total_days": total_days,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "percentage": attendance_percentage,
        },
        "cumulative_summary": {
            "upto_date": yesterday,
            "total_days": cumulative_total_days,
            "present": cumulative_present,
            "absent": cumulative_absent,
            "late": cumulative_late,
            "percentage": cumulative_percentage,
        },
    }
    return render(request, "student/student_attendance.html", context)


@login_required
def subject_list(request):
    """List all subjects available for the student's class."""
    subjects = list(get_accessible_subjects(request.user))
    student = StudentProfile.objects.filter(user=request.user).select_related("section").first()
    section = student.section if student else None
    section_teacher_map = _section_teacher_names_by_subject(section, [subject.id for subject in subjects])

    subject_cards = []
    for subject in subjects:
        teacher_names = section_teacher_map.get(subject.id, [])
        assigned_teacher_name = ", ".join(teacher_names) if teacher_names else "Not Assigned"

        resource_qs = SubjectResource.objects.filter(subject=subject, is_published=True)
        if section:
            resource_qs = resource_qs.filter(Q(section=section) | Q(section__isnull=True))

        resource_counts = {
            "book": resource_qs.filter(resource_type=SubjectResource.TYPE_BOOK).count(),
            "note": resource_qs.filter(resource_type=SubjectResource.TYPE_NOTE).count(),
            "video": resource_qs.filter(resource_type=SubjectResource.TYPE_VIDEO).count(),
            "quiz": resource_qs.filter(resource_type=SubjectResource.TYPE_QUIZ).count(),
            "worksheet": resource_qs.filter(resource_type=SubjectResource.TYPE_WORKSHEET).count(),
        }
        subject_cards.append(
            {
                "subject": subject,
                "assigned_teacher_name": assigned_teacher_name,
                "resource_counts": resource_counts,
            }
        )
    return render(request, 'student/subject_list.html', {'subject_cards': subject_cards})


@login_required
def chapter_list(request, subject_id):
    """List chapters for a specific subject."""
    subject = get_object_or_404(get_accessible_subjects(request.user), id=subject_id)
    chapters = Chapter.objects.filter(subject=subject)
    student = StudentProfile.objects.filter(user=request.user).select_related("section").first()
    section = student.section if student else None
    selected_type = (request.GET.get("type") or "").strip()
    valid_types = {k for k, _ in SubjectResource.TYPE_CHOICES}

    resources = SubjectResource.objects.filter(subject=subject, is_published=True).select_related("uploaded_by__user", "section")
    if section:
        resources = resources.filter(Q(section=section) | Q(section__isnull=True))
    if selected_type in valid_types:
        resources = resources.filter(resource_type=selected_type)

    all_resource_qs = SubjectResource.objects.filter(subject=subject, is_published=True)
    if section:
        all_resource_qs = all_resource_qs.filter(Q(section=section) | Q(section__isnull=True))
    resource_counts = {
        "book": all_resource_qs.filter(resource_type=SubjectResource.TYPE_BOOK).count(),
        "note": all_resource_qs.filter(resource_type=SubjectResource.TYPE_NOTE).count(),
        "video": all_resource_qs.filter(resource_type=SubjectResource.TYPE_VIDEO).count(),
        "quiz": all_resource_qs.filter(resource_type=SubjectResource.TYPE_QUIZ).count(),
        "worksheet": all_resource_qs.filter(resource_type=SubjectResource.TYPE_WORKSHEET).count(),
    }

    assigned_teacher = None
    if section:
        assigned_teacher = SubjectTeacherAssignment.objects.filter(subject=subject, section=section).select_related("teacher__user").first()

    context = {
        'subject': subject,
        'chapters': chapters,
        'resources': resources,
        'selected_type': selected_type,
        'resource_counts': resource_counts,
        'assigned_teacher': assigned_teacher,
    }
    return render(request, 'student/chapter_list.html', context)


@login_required
def chapter_detail(request, chapter_id):
    """
    The Intelligence Panel & Practice Area for a Chapter.
    """
    chapter = get_object_or_404(Chapter.objects.filter(subject__in=get_accessible_subjects(request.user)), id=chapter_id)
    chapter_subject_name = (chapter.subject.name or "").strip()
    chapter_subject_lower = chapter_subject_name.lower()
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('student_dashboard')

    # 1. Fetch/Calculate Subtopic Performance
    # We calculate largely from Questions/StudentAnswers, but check if we have cached model data
    
    # Get all questions for this chapter (both regular and practice)
    # Actually, for Intelligence Panel, we might only want to count 'Practice' or 'Assignment' questions?
    # The prompt implies all attempts count.
    
    questions = Question.objects.filter(chapter=chapter)
    
    # Group by subtopic or concept_tags
    # Logic: Get all answers by this student for this chapter (BOTH assignments AND exams)
    assignment_answers = StudentAnswer.objects.filter(
        student=student_profile, 
        question__chapter=chapter,
        marks_obtained__isnull=False  # Only graded answers
    ).select_related('question')
    
    exam_answers = ExamAnswer.objects.filter(
        student=student_profile,
        exam__chapter=chapter,
        marks_obtained__isnull=False  # Only graded answers
    ).select_related('question')
    
    from collections import defaultdict
    subtopic_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'subtopic': ''})
    math_keywords = {
        "algebra", "calculus", "trigonometry", "geometry", "arithmetic",
        "number system", "probability", "statistics", "mensuration", "equation"
    }

    def is_subject_relevant_subtopic(subtopic_name: str) -> bool:
        normalized = (subtopic_name or "").strip().lower()
        if not normalized:
            return True
        if "english" in chapter_subject_lower:
            return not any(keyword in normalized for keyword in math_keywords)
        return True

    def normalize_subtopic_for_subject(subtopic_name: str) -> str:
        """
        Keep analytics visible even when historical data has cross-subject tags.
        For English chapters, map math-like tags into a neutral bucket.
        """
        cleaned = (subtopic_name or "").strip() or "General"
        if not is_subject_relevant_subtopic(cleaned):
            return "General"
        return cleaned
    
    # Process Assignment Answers
    for ans in assignment_answers:
        # Use subtopic if available, otherwise fall back to concept_tags
        sub = ans.question.subtopic.strip() if ans.question.subtopic else (ans.question.concept_tags.split(',')[0].strip() if ans.question.concept_tags else "General")
        sub = normalize_subtopic_for_subject(sub)
        subtopic_stats[sub]['subtopic'] = sub
        subtopic_stats[sub]['total'] += 1
        
        # Correct if >= 70% marks
        max_m = ans.question.max_marks
        if max_m > 0 and (ans.marks_obtained or 0) / max_m >= 0.7:
             subtopic_stats[sub]['correct'] += 1
    
    # Process Exam Answers
    for ans in exam_answers:
        # Use subtopic if available, otherwise fall back to concept_tags
        sub = ans.question.subtopic.strip() if hasattr(ans.question, 'subtopic') and ans.question.subtopic else (ans.question.concept_tags.split(',')[0].strip() if ans.question.concept_tags else "General")
        sub = normalize_subtopic_for_subject(sub)
        subtopic_stats[sub]['subtopic'] = sub
        subtopic_stats[sub]['total'] += 1
        
        # Correct if >= 70% marks
        max_m = ans.question.marks
        if max_m > 0 and (ans.marks_obtained or 0) / max_m >= 0.7:
             subtopic_stats[sub]['correct'] += 1
             
    # Prepare data for UI
    subtopics_data = []
    total_chapter_attempts = 0
    total_chapter_correct = 0
    
    strong_topics = []
    weak_topics = []
    
    for sub, stats in subtopic_stats.items():
        total = stats['total']
        if total > 0:
            percentage = int((stats['correct'] / total) * 100)
        else:
            percentage = 0
            
        total_chapter_attempts += total
        total_chapter_correct += stats['correct']
        
        # Update or Create SubtopicPerformance model (Cache)
        SubtopicPerformance.objects.update_or_create(
            student=student_profile,
            chapter=chapter,
            subtopic=sub,
            defaults={
                'total_attempts': total,
                'correct_attempts': stats['correct'],
                'mastery_percentage': percentage
            }
        )
        
        status = 'moderate'
        if percentage >= 75:
            status = 'strong'
            stats['badge_color'] = 'green'
            strong_topics.append(sub)
        elif percentage <= 50:
            status = 'weak'
            stats['badge_color'] = 'red'
            weak_topics.append(sub)
        else:
            stats['badge_color'] = 'yellow'
            
        subtopics_data.append({
            'name': sub,
            'percentage': percentage,
            'color': stats['badge_color']
        })
        
    # Overall Mastery
    if total_chapter_attempts > 0:
        overall_mastery = int((total_chapter_correct / total_chapter_attempts) * 100)
    else:
        overall_mastery = 0
        
    # Trend Calculation (Mock logic for now, or compare with last week's snaphost)
    # In a real app, we'd store daily snapshots. Here we'll simulate or just show 0 if no history.
    # Check ChapterPerformance model
    cp, created = ChapterPerformance.objects.get_or_create(student=student_profile, chapter=chapter)
    
    # Calculate difference
    trend = overall_mastery - cp.overall_mastery
    
    # Update current state
    cp.overall_mastery = overall_mastery
    cp.improvement_trend = trend # simplified
    cp.save()
    
    # Color for Overall Bar
    if overall_mastery >= 75:
        overall_color = 'bg-green-500'
        text_color = 'text-green-600'
    elif overall_mastery >= 50:
        overall_color = 'bg-yellow-500'
        text_color = 'text-yellow-600'
    else:
        overall_color = 'bg-red-500'
        text_color = 'text-red-600'

    context = {
        'chapter': chapter,
        'chapter_subject_name': chapter_subject_name,
        'overall_mastery': overall_mastery,
        'overall_color': overall_color,
        'text_color': text_color,
        'subtopics': subtopics_data,
        'strong_topics': strong_topics,
        'weak_topics': weak_topics,
        'trend': trend,
        'trend_direction': 'up' if trend >= 0 else 'down',
        'trend_abs': abs(trend),
    }

    # Load recently generated practice questions for this student/chapter so refresh restores state.
    saved_practice_answers = StudentAnswer.objects.filter(
        student=student_profile,
        question__chapter=chapter,
        question__is_practice=True
    ).select_related('question').order_by('-id')[:20]

    saved_practice_questions = []
    seen_question_ids = set()
    for ans in saved_practice_answers:
        q = ans.question
        if not q or q.id in seen_question_ids:
            continue
        seen_question_ids.add(q.id)
        saved_practice_questions.append({
            'id': q.id,
            'text': q.description,
            'subtopic': q.subtopic or 'General',
            'answered': bool((ans.answer_text or '').strip()),
            'correct': None if ans.marks_obtained is None else bool((ans.marks_obtained or 0) > 0),
        })

    saved_practice_questions.reverse()
    context['saved_practice_questions'] = saved_practice_questions

    return render(request, 'student/chapter_detail.html', context)


@csrf_exempt
@login_required
def submit_practice_answer(request):
    """
    API to submit an answer for an AI-generated practice question.
    It creates a Question object on the fly (if needed) and saves the answer.
    """
    if request.method != "POST":
         return JsonResponse({"error": "Invalid method"}, status=400)
         
    import json
    data = json.loads(request.body)
    
    question_text = data.get('question_text')
    question_id = data.get('question_id')
    subtopic = data.get('subtopic')
    chapter_id = data.get('chapter_id')
    answer_text = data.get('answer_text')
    # For practice, we might assume auto-grading or self-grading?
    # User prompt said: "mastery % = (correct answers / total attempts)"
    # How do we know if it's correct? 
    # AI questions usually need AI grading or simple match.
    # Let's assume for this MVP we use AI to grade it immediately?
    # OR the frontend sends "correct" boolean if it was a quiz UI?
    # Let's assume the frontend sends 'is_correct' if it was client-side checked, 
    # or we trust the student, OR we grade it now.
    # The simplest "production ready" way for text answers is AI grading.
    # But for "Practice", usually it's multiple choice or short answer with immediate feedback.
    # Let's assume we grade it via AI here.
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
        chapter = Chapter.objects.get(id=chapter_id)
        
        # 1. Resolve Question: prefer persisted practice question id, fallback to create.
        question = None
        if question_id:
            question = Question.objects.filter(
                id=question_id,
                chapter=chapter
            ).first()

        if not question:
            question, _ = Question.objects.get_or_create(
                description=question_text,
                chapter=chapter,
                defaults={
                    'teacher': TeacherProfile.objects.first(), # Hack: assign to first teacher or a system bot
                    'teacher_name': request.user, # Assign to self? or system admin
                    'due_date': timezone.now(),
                    'subject': chapter.subject,
                    'subtopic': subtopic,
                    'is_practice': True,
                    'max_marks': 5,
                    'difficulty': 'Medium'
                }
            )
        # Fix teacher assignment if created (needs valid FK)
        # Ideally, we have a "System" teacher. For now, let's skip strict FK checks 
        # if we modify model fields to be nullable, but they are not.
        # We must assign a teacher.
        if not question.teacher_id:
            top_teacher = TeacherProfile.objects.first()
            if top_teacher:
                question.teacher = top_teacher
                question.teacher_name = top_teacher.user
                question.save()

        # 2. Grade the answer (Simple check or AI)
        # Let's Assume FULL MARKS for now to demonstrate mastery (or random logic?)
        # Real Implementation: Call AI Grader
        
        # ... (Calling AI grader - reuse generate_remark_feedback logic?)
        # integrating grading here for "Practice"
        
        grade_prompt = (
            f"Question: {question_text}\n"
            f"Student Answer: {answer_text}\n"
            f"Is this answer correct? Reply with just 'YES' or 'NO'."
        )
        # Quick sync call to Groq (we need to import client)
        from .ai_utils import client
        if client:
             grade_res = client.chat.completions.create(
                 model="llama-3.3-70b-versatile",
                 messages=[{"role": "user", "content": grade_prompt}],
                 max_tokens=10
             )
             is_correct = "YES" in grade_res.choices[0].message.content.upper()
        else:
            is_correct = True # Fallback

        marks = 5 if is_correct else 0
        
        StudentAnswer.objects.update_or_create(
            student=student_profile,
            question=question,
            defaults={
                'student_name': request.user,
                'student_roll': student_profile,
                'answer_text': answer_text,
                'marks_obtained': marks,
            }
        )
        
        return JsonResponse({"status": "success", "correct": is_correct, "marks": marks})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
