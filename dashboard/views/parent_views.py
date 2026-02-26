from datetime import date
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import CustomUser, ParentProfile, ParentStudentRelation, StudentProfile
from dashboard.models import (
    Announcement,
    AttendanceRecord,
    Exam,
    ExamAnswer,
    Notification,
    ParentMessageClearState,
    Question,
    StudentAnswer,
    TeacherClassMessage,
)


def _fallback_explanation(ans):
    marks_text = "Not graded yet"
    if ans.marks_obtained is not None:
        if ans.question and ans.question.max_marks:
            marks_text = f"{ans.marks_obtained}/{ans.question.max_marks}"
        else:
            marks_text = f"{ans.marks_obtained}"

    remark = (ans.remarks or "").strip()
    if ans.marks_obtained is None:
        return (
            "Problem: Assignment has been submitted, but it is not graded yet.\n"
            "Next Step: Ask the teacher for evaluation and help your child revise this topic for 15 minutes daily."
        )

    if not remark:
        return (
            f"Problem: Score is {marks_text}, but detailed teacher feedback is not available yet.\n"
            "Next Step: Review the assignment once, solve 3 similar questions, and ask the teacher where improvement is needed."
        )

    return (
        f"Problem: Score is {marks_text}. Key feedback: {remark}\n"
        "Next Step: Revise this concept, practice similar problems with full steps, and recheck mistakes before next submission."
    )


def _fallback_explanation_localized(ans, language):
    base = _fallback_explanation(ans)
    if language == "hindi":
        return (
            "Problem: असाइनमेंट में सुधार की जरूरत है।\n"
            "Next Step: इसी टॉपिक को दोहराएं, step-by-step हल लिखने की प्रैक्टिस करें, और अगली बार जमा करने से पहले answer check करें।"
        )
    if language == "odia":
        return (
            "Problem: ଏହି assignment ରେ ଆଉ ଭଲ କରିବା ଆବଶ୍ୟକ।\n"
            "Next Step: ଏହି topic କୁ ପୁନଃ ପଢନ୍ତୁ, step-by-step ସମାଧାନ ଲେଖିବାର practice କରନ୍ତୁ, ଏବଂ ପୁନଃ ଯାଞ୍ଚ କରି submit କରନ୍ତୁ।"
        )
    return base


def _fallback_simplified_remark(remark, language):
    text = (remark or "").strip()
    if not text:
        return "Teacher has not added a remark yet."

    lower = text.lower()
    needs_steps = ("step" in lower) or ("show" in lower and "solution" in lower)
    is_correct = ("correct" in lower) or ("right" in lower)
    needs_practice = ("practice" in lower) or ("improv" in lower) or ("revise" in lower)

    if language == "hindi":
        parts = []
        if is_correct:
            parts.append("उत्तर काफी हद तक सही है।")
        if needs_steps:
            parts.append("अगली बार पूरा step-by-step solution भी लिखना जरूरी है।")
        if needs_practice:
            parts.append("थोड़ी और practice और revision से performance बेहतर होगी।")
        if not parts:
            parts.append("शिक्षक का सुझाव: उत्तर को और साफ़ और step-wise तरीके से लिखें।")
        return " ".join(parts)

    if language == "odia":
        parts = []
        if is_correct:
            parts.append("ଉତ୍ତରଟି ଅଧିକାଂଶ ଭାଗରେ ଠିକ୍ ଅଛି।")
        if needs_steps:
            parts.append("ପରବର୍ତ୍ତୀ ବାର ପୂର୍ଣ୍ଣ step-by-step ସମାଧାନ ଲେଖିବା ଆବଶ୍ୟକ।")
        if needs_practice:
            parts.append("ଅଧିକ practice ଏବଂ revision କଲେ ଫଳ ଆଉ ଭଲ ହେବ।")
        if not parts:
            parts.append("ଶିକ୍ଷକଙ୍କ ସୁପାରିଶ: ଉତ୍ତରକୁ ସ୍ପଷ୍ଟ ଏବଂ step-wise ଭାବରେ ଲେଖ।")
        return " ".join(parts)

    simple = text
    simple = simple.replace("However,", "But")
    simple = simple.replace("beneficial", "helpful")
    simple = simple.replace("demonstrate a full understanding", "show full understanding")
    simple = simple.replace("including", "adding")
    return simple[:220]


def _get_parent_profile(user):
    try:
        return ParentProfile.objects.get(user=user)
    except ParentProfile.DoesNotExist:
        return None


def _parent_guard(request):
    if request.user.role != CustomUser.Role.PARENT:
        return redirect("parent_login")
    profile = _get_parent_profile(request.user)
    if not profile:
        return redirect("parent_login")
    return profile


def _linked_children(parent_profile):
    child_ids = ParentStudentRelation.objects.filter(parent=parent_profile).values_list("student_id", flat=True)
    return StudentProfile.objects.filter(pk__in=child_ids).select_related("user", "section")


def _select_child(request, children):
    selected_child_id = (request.GET.get("child_id") or "").strip()
    selected_child = None

    if selected_child_id.isdigit():
        selected_child = children.filter(pk=int(selected_child_id)).first()

    if not selected_child:
        selected_child = children.first()

    return selected_child, str(selected_child.pk) if selected_child else ""


def _attendance_snapshot(student):
    if not student:
        return {
            "attendance_pct": 0,
            "late_count": 0,
            "present_count": 0,
            "absent_count": 0,
            "monthly_summary": {"present": 0, "absent": 0, "late": 0, "total": 0},
        }

    attendance_qs = AttendanceRecord.objects.filter(student=student)
    present_count = attendance_qs.filter(status=AttendanceRecord.STATUS_PRESENT).count()
    absent_count = attendance_qs.filter(status=AttendanceRecord.STATUS_ABSENT).count()
    late_count = attendance_qs.filter(status=AttendanceRecord.STATUS_LATE).count()
    total = present_count + absent_count + late_count
    attendance_pct = round((present_count / total) * 100, 1) if total else 0

    today = date.today()
    month_start = today.replace(day=1)
    monthly_qs = attendance_qs.filter(date__gte=month_start, date__lte=today)
    monthly_present = monthly_qs.filter(status=AttendanceRecord.STATUS_PRESENT).count()
    monthly_absent = monthly_qs.filter(status=AttendanceRecord.STATUS_ABSENT).count()
    monthly_late = monthly_qs.filter(status=AttendanceRecord.STATUS_LATE).count()

    return {
        "attendance_pct": attendance_pct,
        "late_count": late_count,
        "present_count": present_count,
        "absent_count": absent_count,
        "monthly_summary": {
            "present": monthly_present,
            "absent": monthly_absent,
            "late": monthly_late,
            "total": monthly_present + monthly_absent + monthly_late,
        },
    }


def _performance_graph_data(student):
    if not student:
        return {"labels": [], "values": []}

    points = []

    assignment_answers = (
        StudentAnswer.objects.filter(student=student, marks_obtained__isnull=False)
        .select_related("question")
        .order_by("submitted_at")
    )
    for ans in assignment_answers:
        max_marks = ans.question.max_marks or 0
        if max_marks <= 0:
            continue
        percent = round((float(ans.marks_obtained or 0) / float(max_marks)) * 100, 1)
        points.append(
            {
                "label": f"Q{ans.question_id}",
                "value": percent,
                "date": ans.submitted_at,
            }
        )

    exam_rows = (
        ExamAnswer.objects.filter(student=student, marks_obtained__isnull=False)
        .values("exam_id", "exam__title", "exam__total_marks")
        .annotate(
            obtained=Sum("marks_obtained"),
            submitted_at=Max("submitted_at"),
        )
        .order_by("submitted_at")
    )
    for row in exam_rows:
        total_marks = row.get("exam__total_marks") or 0
        if total_marks <= 0:
            continue
        percent = round((float(row.get("obtained") or 0) / float(total_marks)) * 100, 1)
        points.append(
            {
                "label": f"Exam: {row.get('exam__title') or row.get('exam_id')}",
                "value": percent,
                "date": row.get("submitted_at"),
            }
        )

    points = sorted(points, key=lambda x: x["date"] or timezone.now())[-8:]
    return {
        "labels": [p["label"] for p in points],
        "values": [p["value"] for p in points],
    }


def _message_feeds_for_student(student):
    if not student:
        return [], []

    section = student.section
    now_time = timezone.now()

    teacher_messages = (
        TeacherClassMessage.objects.filter(Q(section=section) | Q(section__isnull=True))
        .select_related("teacher__user", "section")
        .order_by("-created_at")
    )

    announcements = (
        Announcement.objects.filter(
            Q(scope=Announcement.SCOPE_GENERAL)
            | Q(scope=Announcement.SCOPE_CLASS, target_section=section)
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now_time))
        .select_related("created_by", "target_section")
        .order_by("-created_at")
    )

    teacher_feed = [
        {
            "title": msg.title,
            "body": msg.message,
            "sender": msg.teacher.user.get_full_name() if msg.teacher and msg.teacher.user else "Teacher",
            "section": str(msg.section) if msg.section else "All Sections",
            "created_at": msg.created_at,
        }
        for msg in teacher_messages[:8]
    ]

    ann_feed = [
        {
            "title": ann.title,
            "body": ann.body,
            "sender": ann.created_by.get_full_name() if ann.created_by else "Admin",
            "section": str(ann.target_section) if ann.target_section else "All Classes",
            "created_at": ann.created_at,
            "scope": ann.scope,
        }
        for ann in announcements[:8]
    ]

    return teacher_feed, ann_feed


@login_required(login_url="parent_login")
def parent_dashboard(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile

    children = _linked_children(parent_profile)
    selected_child, selected_child_id = _select_child(request, children)
    attendance_stats = _attendance_snapshot(selected_child)

    pending_assignments = Question.objects.none()
    upcoming_exams = Exam.objects.none()
    teacher_messages_feed, announcements_feed = ([], [])

    if selected_child and selected_child.section_id:
        answered_q_ids = StudentAnswer.objects.filter(student=selected_child).values_list("question_id", flat=True)
        pending_assignments = (
            Question.objects.filter(section=selected_child.section, is_exam=False)
            .exclude(id__in=answered_q_ids)
            .order_by("due_date")[:8]
        )

        upcoming_exams = (
            Exam.objects.filter(section=selected_child.section, due_date__gte=timezone.now())
            .select_related("subject", "chapter", "section")
            .order_by("due_date")[:8]
        )

        teacher_messages_feed, announcements_feed = _message_feeds_for_student(selected_child)

    performance_graph = _performance_graph_data(selected_child)
    notifications_feed = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:6]

    context = {
        "children": children,
        "selected_child": selected_child,
        "selected_child_id": selected_child_id,
        "attendance_pct": attendance_stats["attendance_pct"],
        "late_count": attendance_stats["late_count"],
        "present_count": attendance_stats["present_count"],
        "absent_count": attendance_stats["absent_count"],
        "monthly_summary": attendance_stats["monthly_summary"],
        "pending_assignments": pending_assignments,
        "pending_assignments_count": pending_assignments.count(),
        "upcoming_exams": upcoming_exams,
        "upcoming_exams_count": upcoming_exams.count(),
        "teacher_messages_feed": teacher_messages_feed,
        "announcements_feed": announcements_feed,
        "notifications_feed": notifications_feed,
        "performance_graph_labels": performance_graph["labels"],
        "performance_graph_values": performance_graph["values"],
    }
    return render(request, "parent/parent_dashboard.html", context)


@login_required(login_url="parent_login")
def parent_children(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile
    children = _linked_children(parent_profile)
    return render(request, "parent/parent_children.html", {"children": children})


@login_required(login_url="parent_login")
def parent_assignments(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile
    children = _linked_children(parent_profile)
    selected_child, selected_child_id = _select_child(request, children)

    assignments = Question.objects.none()
    if selected_child and selected_child.section_id:
        assignments = (
            Question.objects.filter(section=selected_child.section, is_exam=False)
            .select_related("teacher_name", "section")
            .order_by("-created_at")[:50]
        )

    return render(
        request,
        "parent/parent_assignments.html",
        {
            "children": children,
            "selected_child": selected_child,
            "selected_child_id": selected_child_id,
            "assignments": assignments,
        },
    )


@login_required(login_url="parent_login")
def parent_assignment_explain(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=400)

    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return JsonResponse({"error": "Unauthorized."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    answer_id = payload.get("answer_id") or request.POST.get("answer_id")
    language = (payload.get("language") or request.POST.get("language") or "english").strip().lower()
    try:
        answer_id = int(answer_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Valid answer_id is required."}, status=400)

    allowed_languages = {
        "english": "English",
        "hindi": "Hindi",
        "odia": "Odia",
    }
    if language not in allowed_languages:
        language = "english"

    children = _linked_children(parent_profile)
    ans = (
        StudentAnswer.objects.filter(student__in=children, pk=answer_id)
        .select_related("student__user", "question")
        .first()
    )
    if not ans:
        return JsonResponse({"error": "Assignment answer not found."}, status=404)

    student_name = ans.student.user.get_full_name() or "Student"
    marks_text = "Not graded yet"
    if ans.marks_obtained is not None:
        if ans.question and ans.question.max_marks:
            marks_text = f"{ans.marks_obtained}/{ans.question.max_marks}"
        else:
            marks_text = f"{ans.marks_obtained}"
    teacher_remark = (ans.remarks or "").strip()

    prompt = (
        "You are a school counselor assistant writing for a parent.\n"
        "Explain this assignment result in very simple language.\n"
        f"Language: {allowed_languages[language]}\n"
        "Output exactly two short sections with these labels:\n"
        "Problem: ...\n"
        "Next Step: ...\n"
        "Keep practical, gentle, and specific. Max 90 words total.\n\n"
        f"Student: {student_name}\n"
        f"Assignment Question ID: {ans.question_id}\n"
        f"Marks: {marks_text}\n"
        f"Teacher Remark: {teacher_remark or 'No teacher remark yet'}\n"
    )

    try:
        from .ai_utils import client, clean_ai_text

        if not client:
            return JsonResponse({"explanation": _fallback_explanation_localized(ans, language)})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
        )
        raw = response.choices[0].message.content
        return JsonResponse({"explanation": clean_ai_text(raw)})
    except Exception:
        return JsonResponse({"explanation": _fallback_explanation_localized(ans, language)})


@login_required(login_url="parent_login")
def parent_assignment_simplify_remark(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=400)

    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return JsonResponse({"error": "Unauthorized."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    answer_id = payload.get("answer_id") or request.POST.get("answer_id")
    language = (payload.get("language") or request.POST.get("language") or "english").strip().lower()

    try:
        answer_id = int(answer_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Valid answer_id is required."}, status=400)

    allowed_languages = {
        "english": "English",
        "hindi": "Hindi",
        "odia": "Odia",
    }
    if language not in allowed_languages:
        language = "english"

    children = _linked_children(parent_profile)
    ans = StudentAnswer.objects.filter(student__in=children, pk=answer_id).first()
    if not ans:
        return JsonResponse({"error": "Assignment answer not found."}, status=404)

    original_remark = (ans.remarks or "").strip()
    if not original_remark:
        return JsonResponse({"simplified": "Teacher has not added a remark yet."})

    target_language = allowed_languages[language]
    prompt = (
        "Rewrite the teacher remark for a parent in very simple words.\n"
        f"Language: {target_language}\n"
        "Keep meaning same, tone respectful, max 60 words.\n"
        "Return only the simplified text.\n\n"
        f"Teacher remark:\n{original_remark}"
    )

    try:
        from .ai_utils import client, clean_ai_text

        if not client:
            return JsonResponse({"simplified": _fallback_simplified_remark(original_remark, language)})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=180,
        )
        raw = response.choices[0].message.content
        return JsonResponse({"simplified": clean_ai_text(raw)})
    except Exception:
        return JsonResponse({"simplified": _fallback_simplified_remark(original_remark, language)})


@login_required(login_url="parent_login")
def parent_notes(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile
    children = _linked_children(parent_profile)
    return render(request, "parent/parent_notes.html", {"children": children})


@login_required(login_url="parent_login")
def parent_messages(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile

    children = _linked_children(parent_profile)
    selected_child, selected_child_id = _select_child(request, children)
    teacher_messages_feed, announcements_feed = _message_feeds_for_student(selected_child)
    if selected_child:
        clear_state = ParentMessageClearState.objects.filter(parent=parent_profile, child=selected_child).first()
        if clear_state and clear_state.teacher_messages_cleared_at:
            teacher_messages_feed = [
                item for item in teacher_messages_feed
                if (item.get("created_at") and item["created_at"] > clear_state.teacher_messages_cleared_at)
            ]
        if clear_state and clear_state.announcements_cleared_at:
            announcements_feed = [
                item for item in announcements_feed
                if (item.get("created_at") and item["created_at"] > clear_state.announcements_cleared_at)
            ]
    notifications_feed = Notification.objects.filter(recipient=request.user).order_by("-created_at")

    return render(
        request,
        "parent/parent_messages.html",
        {
            "children": children,
            "selected_child": selected_child,
            "selected_child_id": selected_child_id,
            "teacher_messages_feed": teacher_messages_feed,
            "announcements_feed": announcements_feed,
            "notifications_feed": notifications_feed,
        },
    )


@login_required(login_url="parent_login")
def parent_clear_teacher_messages(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=400)

    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return JsonResponse({"error": "Unauthorized."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    child_id = payload.get("child_id") or request.POST.get("child_id")
    try:
        child_id = int(child_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Valid child_id is required."}, status=400)

    children = _linked_children(parent_profile)
    child = children.filter(pk=child_id).first()
    if not child:
        return JsonResponse({"error": "Child not found."}, status=404)

    state, _ = ParentMessageClearState.objects.get_or_create(parent=parent_profile, child=child)
    state.teacher_messages_cleared_at = timezone.now()
    state.save(update_fields=["teacher_messages_cleared_at", "updated_at"])
    return JsonResponse({"success": True})


@login_required(login_url="parent_login")
def parent_clear_announcements(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=400)

    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return JsonResponse({"error": "Unauthorized."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    child_id = payload.get("child_id") or request.POST.get("child_id")
    try:
        child_id = int(child_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Valid child_id is required."}, status=400)

    children = _linked_children(parent_profile)
    child = children.filter(pk=child_id).first()
    if not child:
        return JsonResponse({"error": "Child not found."}, status=404)

    state, _ = ParentMessageClearState.objects.get_or_create(parent=parent_profile, child=child)
    state.announcements_cleared_at = timezone.now()
    state.save(update_fields=["announcements_cleared_at", "updated_at"])
    return JsonResponse({"success": True})


@login_required(login_url="parent_login")
def parent_holidays(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile
    holidays = [
        {"name": "Republic Day", "date": "2026-01-26"},
        {"name": "Holi", "date": "2026-03-04"},
        {"name": "Independence Day", "date": "2026-08-15"},
        {"name": "Gandhi Jayanti", "date": "2026-10-02"},
        {"name": "Diwali", "date": "2026-11-08"},
        {"name": "Christmas", "date": "2026-12-25"},
    ]
    return render(request, "parent/parent_holidays.html", {"holidays": holidays})


@login_required(login_url="parent_login")
def parent_performance(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile
    children = _linked_children(parent_profile)
    selected_child, selected_child_id = _select_child(request, children)
    answers = StudentAnswer.objects.none()
    if selected_child:
        answers = StudentAnswer.objects.filter(student=selected_child).select_related("student__user", "question").order_by("-submitted_at")[:50]
    return render(
        request,
        "parent/parent_performance.html",
        {
            "children": children,
            "selected_child": selected_child,
            "selected_child_id": selected_child_id,
            "answers": answers,
        },
    )


@login_required(login_url="parent_login")
def parent_exam_portion(request):
    parent_profile = _parent_guard(request)
    if not isinstance(parent_profile, ParentProfile):
        return parent_profile
    children = _linked_children(parent_profile)
    selected_child, selected_child_id = _select_child(request, children)
    exams = Exam.objects.none()
    if selected_child and selected_child.section_id:
        exams = (
            Exam.objects.filter(section=selected_child.section, due_date__gte=timezone.now())
            .select_related("subject", "chapter", "section")
            .order_by("due_date")[:30]
        )
    return render(
        request,
        "parent/parent_exam_portion.html",
        {
            "children": children,
            "selected_child": selected_child,
            "selected_child_id": selected_child_id,
            "exams": exams,
        },
    )
