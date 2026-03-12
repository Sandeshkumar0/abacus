from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from accounts.models import StudentProfile, TeacherProfile
from dashboard.models import Exam, ExamAnswer, Query, Question, StudentAnswer


def _student_cache_key(user_id):
    return f"dashboard:student:{user_id}:metrics:v1"


def _teacher_cache_key(user_id):
    return f"dashboard:teacher:{user_id}:metrics:v1"


def get_student_metrics(user):
    """
    LMS-style student dashboard summary.
    Cached for short interval to reduce repeated aggregation load.
    """
    cache_key = _student_cache_key(user.id)
    cached = cache.get(cache_key)
    if cached:
        return cached

    student_profile, _ = StudentProfile.objects.get_or_create(
        user=user,
        defaults={
            "roll_number": f"STU{user.id}",
            "student_class": "Unknown",
            "dob": timezone.now().date(),
            "phone": "0000000000",
        },
    )

    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)

    from django.db.models import Exists, OuterRef

    total_assignments = Question.objects.count()
    pending_assignments = Question.objects.exclude(
        Exists(
            StudentAnswer.objects.filter(
                question=OuterRef('pk'),
                student=student_profile
            )
        )
    ).count()
    pending_queries = Query.objects.filter(student=student_profile).filter(
        Q(response__isnull=True) | Q(response="")
    ).count()
    upcoming_exams = Exam.objects.filter(due_date__gt=now).count()
    recent_graded_count = StudentAnswer.objects.filter(
        student=student_profile,
        remarks__isnull=False,
        submitted_at__gte=week_ago,
    ).count()

    scored = StudentAnswer.objects.filter(
        student=student_profile,
        marks_obtained__isnull=False,
        question__max_marks__gt=0,
    ).values("marks_obtained", "question__max_marks")
    if scored:
        avg_assignment_score = round(
            sum((row["marks_obtained"] / row["question__max_marks"]) * 100 for row in scored)
            / len(scored),
            2,
        )
    else:
        avg_assignment_score = 0.0

    metrics = {
        "student_profile_id": student_profile.pk,
        "total_assignments": total_assignments,
        "pending_assignments": pending_assignments,
        "pending_queries": pending_queries,
        "upcoming_exams": upcoming_exams,
        "recent_graded_count": recent_graded_count,
        "avg_assignment_score": round(float(avg_assignment_score or 0.0), 2),
    }
    cache.set(cache_key, metrics, timeout=60)
    return metrics


def get_teacher_metrics(user):
    """
    LMS-style teacher dashboard summary.
    Includes at-risk student count and grading backlog.
    """
    cache_key = _teacher_cache_key(user.id)
    cached = cache.get(cache_key)
    if cached:
        return cached

    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=user,
        defaults={"aadhar_id": "Not Provided", "phone": "Not Provided"},
    )

    now = timezone.now()
    # Use role-based access rules so class/section-assigned teachers also see
    # correct student counts (not only directly assigned_teacher rows).
    from dashboard.access_control import get_accessible_students

    students_qs = get_accessible_students(user).select_related("user")
    student_ids = list(students_qs.values_list("user_id", flat=True))

    total_students = len(student_ids)
    active_assignments = Question.objects.filter(teacher=teacher_profile).count()
    pending_queries = Query.objects.filter(student__in=students_qs).filter(Q(response__isnull=True) | Q(response="")).count()
    upcoming_tests = Exam.objects.filter(teacher=teacher_profile, due_date__gte=now).count()

    grading_backlog = StudentAnswer.objects.filter(
        question__teacher=teacher_profile
    ).filter(Q(remarks__isnull=True) | Q(remarks="")).count() + ExamAnswer.objects.filter(
        exam__teacher=teacher_profile
    ).filter(Q(remarks__isnull=True) | Q(remarks="")).count()

    at_risk_students = 0
    if student_ids:
        answer_rows = (
            StudentAnswer.objects.filter(student__user_id__in=student_ids, marks_obtained__isnull=False)
            .select_related("question")
            .values("student__user_id", "marks_obtained", "question__max_marks")
        )
        perf = {}
        for row in answer_rows:
            max_marks = row["question__max_marks"] or 0
            if max_marks <= 0:
                continue
            sid = row["student__user_id"]
            if sid not in perf:
                perf[sid] = {"obt": 0, "max": 0}
            perf[sid]["obt"] += row["marks_obtained"] or 0
            perf[sid]["max"] += max_marks

        at_risk_students = sum(
            1 for sid in perf if perf[sid]["max"] > 0 and ((perf[sid]["obt"] / perf[sid]["max"]) * 100) < 40
        )

    metrics = {
        "teacher_profile_id": teacher_profile.pk,
        "total_students": total_students,
        "active_assignments": active_assignments,
        "pending_queries": pending_queries,
        "upcoming_tests": upcoming_tests,
        "grading_backlog": grading_backlog,
        "at_risk_students": at_risk_students,
    }
    cache.set(cache_key, metrics, timeout=60)
    return metrics


def get_teacher_at_risk_students(user, limit=10):
    """
    Return lowest-performing students for intervention workflows.
    """
    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=user,
        defaults={"aadhar_id": "Not Provided", "phone": "Not Provided"},
    )
    from dashboard.access_control import get_accessible_students

    students = get_accessible_students(user).select_related("user")

    risk_rows = []
    for student in students:
        answers = StudentAnswer.objects.filter(
            student=student,
            marks_obtained__isnull=False,
            question__max_marks__gt=0,
        ).values("marks_obtained", "question__max_marks")

        if not answers:
            continue

        obtained = sum(row["marks_obtained"] or 0 for row in answers)
        max_marks = sum(row["question__max_marks"] or 0 for row in answers)
        if max_marks <= 0:
            continue

        pct = round((obtained / max_marks) * 100, 2)
        risk_rows.append(
            {
                "student_id": student.user_id,
                "name": student.user.full_name or student.user.email,
                "roll_number": student.roll_number,
                "accuracy": pct,
            }
        )

    risk_rows.sort(key=lambda r: r["accuracy"])
    return risk_rows[: max(1, limit)]
