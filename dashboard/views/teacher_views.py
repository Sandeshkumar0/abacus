"""
Teacher-related views for the dashboard app.
Handles teacher dashboard, question assignment, exam creation, student management, and grading.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import make_aware
from django.db.utils import ProgrammingError, OperationalError
from datetime import datetime
import json
import os
import tempfile
from dotenv import load_dotenv
from django.contrib import messages

from accounts.models import CustomUser, Section, StudentProfile, TeacherProfile, TeacherSectionAssignment
from ..access_control import get_accessible_sections, get_accessible_students, get_accessible_subjects
from ..models import (
    Question, StudentAnswer, Query, Exam, ExamQuestion, ExamAnswer,
    Course, CourseResource, StudentGroup, Subject, Chapter, GroupCompetition,
    AttendanceRecord, TeacherClassMessage, TeacherNote, SubjectTeacherAssignment, SubjectResource,
    SchoolExamResult, Announcement, StudentSubjectPerformance, Notification, Holiday,
    TeacherMessageEngagement, AnnouncementEngagement, StudentMessageClearState
)
from ..services.dashboard_metrics import get_teacher_metrics


def _optional_ai_remark(student_name: str, subject_name: str, percentage: float, teacher_review: str = "") -> str:
    """
    Optional AI-like remark generator with deterministic fallback.
    Keeps system stable even if external AI is unavailable.
    """
    base_review = (teacher_review or "").strip()
    if percentage < 40:
        auto = f"{student_name} needs improvement in {subject_name}. Focus on fundamentals and regular practice."
    elif percentage > 75:
        auto = f"{student_name} shows excellent performance in {subject_name}. Keep up the consistency."
    else:
        auto = f"{student_name} is making good progress in {subject_name}. Continue revision and timed practice."
    return f"{base_review} {auto}".strip()


@login_required(login_url='teacher_login')
def teacher_dashboard(request):
    """Main dashboard view for teachers."""
    if not request.user.is_authenticated:
        return redirect('teacher_login')
    if request.user.role not in {
        CustomUser.Role.TEACHER,
        CustomUser.Role.CLASS_TEACHER,
        CustomUser.Role.PRINCIPAL,
        CustomUser.Role.ADMIN,
    } and not request.user.is_teacher:
        return redirect('teacher_login')
    
    # Get teacher profile
    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'aadhar_id': 'Not Provided',
            'phone': 'Not Provided'
        }
    )
    
    # Cached production metrics (same keys retained for existing template)
    metrics = get_teacher_metrics(request.user)
    total_students = metrics["total_students"]
    active_assignments = metrics["active_assignments"]
    pending_queries = metrics["pending_queries"]
    upcoming_tests = metrics["upcoming_tests"]
    
    context = {
        'total_students': total_students,
        'active_assignments': active_assignments,
        'pending_queries': pending_queries,
        'upcoming_tests': upcoming_tests,
        'grading_backlog': metrics["grading_backlog"],
        'at_risk_students': metrics["at_risk_students"],
    }
    
    return render(request, 'teacher/teacher_dashboard.html', context)


@login_required
def teacher_profile(request):
    """Display teacher profile."""
    teacher, created = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'aadhar_id': 'Not Provided',
            'phone': 'Not Provided'
        }
    )
    return render(request, 'teacher/profile.html', {'teacher': teacher})


@login_required
def teacher_profile_edit(request):
    """Edit teacher profile - update profile picture and office details."""
    teacher, created = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'aadhar_id': 'Not Provided',
            'phone': 'Not Provided'
        }
    )
    
    if request.method == 'POST':
        # Update profile picture if uploaded
        if 'profile_picture' in request.FILES:
            teacher.profile_picture = request.FILES['profile_picture']
        
        # Update office details
        office_location = request.POST.get('office_location', '').strip()
        office_hours = request.POST.get('office_hours', '').strip()
        
        if office_location:
            teacher.office_location = office_location
        if office_hours:
            teacher.office_hours = office_hours
        
        teacher.save()
        return redirect('teacher_profile')
    
    return render(request, 'teacher/profile_edit.html', {'teacher': teacher})


@csrf_exempt
@login_required
def assign_questions(request):
    """Assign questions/assignments to students."""
    teacher = TeacherProfile.objects.get(user=request.user)
    sections = get_accessible_sections(request.user)

    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        latex_equation = request.POST.get('latex_equation', '').strip()
        max_marks = int(request.POST.get('max_marks', 0))
        is_exam = request.POST.get('is_test') in ['true', 'on', '1']
        section_id = request.POST.get('section_id')
        due_date_str = request.POST.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                due_date = timezone.now()

        section = sections.filter(id=section_id).first() if section_id else None
        if not section:
            return JsonResponse({'status': 'error', 'message': 'Section is required'})

        uploaded_file = request.FILES.get('image')

        full_question = description
        if latex_equation:
            full_question += f"\n\nLaTeX Equation:\n{latex_equation}"

        Question.objects.create(
            teacher=teacher,
            teacher_name=request.user,
            description=full_question,
            due_date=due_date,
            is_exam=is_exam,
            max_marks=max_marks,
            image=uploaded_file,
            section=section,
        )

        return redirect('assign_questions')

    return render(request, 'teacher/assign_questions.html', {"sections": sections})


@login_required
@csrf_exempt
def take_test(request):
    """Create and manage tests/exams (legacy endpoint)."""
    if request.method == "POST":
        exam_heading = request.POST.get("examHeading")
        due_date = request.POST.get("dueDate")
        total_marks = request.POST.get("totalMarks")
        timer_enabled = request.POST.get("timerEnabled") in {"true", "on", "1", "yes"}
        duration_minutes_raw = request.POST.get("durationMinutes")
        duration_minutes = int(duration_minutes_raw) if (duration_minutes_raw and str(duration_minutes_raw).isdigit()) else None
        if timer_enabled and (not duration_minutes or duration_minutes <= 0):
            return JsonResponse({"status": "error", "message": "Duration (minutes) is required when timer is enabled."}, status=400)
        questions_data = request.POST.getlist("questions[]")

        teacher, _ = TeacherProfile.objects.get_or_create(user=request.user)
        sections = get_accessible_sections(request.user)
        section_id = request.POST.get("section_id")
        section = sections.filter(id=section_id).first() if section_id else None
        if not section:
            return JsonResponse({"status": "error", "message": "Section is required."}, status=400)
        exam = Exam.objects.create(
            teacher=teacher,
            teacher_name=request.user,
            title=exam_heading,
            due_date=parse_datetime(due_date),
            total_marks=total_marks,
            timer_enabled=timer_enabled,
            duration_minutes=duration_minutes if timer_enabled else None,
            subject_id=request.POST.get("subject_id"),
            chapter_id=request.POST.get("chapter_id"),
            section=section,
        )

        for i, q in enumerate(questions_data):
            q_obj = json.loads(q)
            q_file = request.FILES.get(f"question_file_{i}")
            ExamQuestion.objects.create(
                exam=exam,
                text=q_obj.get("text", ""),
                latex=q_obj.get("latex", ""),
                marks=q_obj.get("marks", 0),
                file=q_file
            )

        return JsonResponse({"status": "success", "exam_id": exam.id})
    
    # Fetch existing exams created by this teacher
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    exams = Exam.objects.filter(teacher=teacher_profile).order_by('-created_at')
    subjects = Subject.objects.filter(teacher=teacher_profile)
    sections = get_accessible_sections(request.user)

    return render(request, "teacher/take_test.html", {'exams': exams, 'subjects': subjects, "sections": sections})


@csrf_exempt
@login_required
def create_exam(request):
    """Create a new exam with questions."""
    if request.method == "POST":
        exam_heading = request.POST.get("examHeading")
        due_date_str = request.POST.get("dueDate")
        total_marks = request.POST.get("totalMarks")
        timer_enabled = request.POST.get("timerEnabled") in {"true", "on", "1", "yes"}
        duration_minutes_raw = request.POST.get("durationMinutes")
        duration_minutes = int(duration_minutes_raw) if (duration_minutes_raw and str(duration_minutes_raw).isdigit()) else None
        if timer_enabled and (not duration_minutes or duration_minutes <= 0):
            return JsonResponse({"status": "failed", "message": "Duration (minutes) is required when timer is enabled."}, status=400)

        due_date = make_aware(datetime.strptime(due_date_str, "%Y-%m-%d %H:%M"))

        teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
        teacher_user = request.user
        sections = get_accessible_sections(request.user)
        section_id = request.POST.get("section_id")
        section = sections.filter(id=section_id).first() if section_id else None
        if not section:
            return JsonResponse({"status": "failed", "message": "Section is required."}, status=400)

        # Handle Subject
        subject_input = request.POST.get("subject_id")
        subject = None
        if subject_input:
            if subject_input.isdigit():
                subject = Subject.objects.get(id=int(subject_input))
            else:
                # It's a name from AI
                subject, _ = Subject.objects.get_or_create(
                    teacher=teacher_profile,
                    name=subject_input,
                    defaults={'class_level': 'General'} # Default if creating from name
                )

        # Handle Chapter
        chapter_input = request.POST.get("chapter_id")
        chapter = None
        if chapter_input:
            if chapter_input.isdigit():
                chapter = Chapter.objects.get(id=int(chapter_input))
            elif subject:
                # It's a name from AI, create under the subject
                chapter, _ = Chapter.objects.get_or_create(
                    subject=subject,
                    name=chapter_input
                )

        exam = Exam.objects.create(
            teacher=teacher_profile,
            teacher_name=teacher_user,
            title=exam_heading,
            due_date=due_date,
            total_marks=total_marks,
            timer_enabled=timer_enabled,
            duration_minutes=duration_minutes if timer_enabled else None,
            subject=subject,
            chapter=chapter,
            section=section,
        )

        # Save questions
        questions_data = request.POST.getlist("questions[]")
        for idx, q_json in enumerate(questions_data):
            q = json.loads(q_json)
            uploaded_file = request.FILES.get(f"question_file_{idx}")

            ExamQuestion.objects.create(
                exam=exam,
                text=q["text"],
                latex=q.get("latex", ""),
                marks=q["marks"],
                file=uploaded_file if uploaded_file else None,
            )

        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "failed"})


@login_required
def student_list(request):
    """View list of students assigned to the teacher."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'aadhar_id': 'Not Provided',
            'phone': 'Not Provided'
        }
    )
    students = get_accessible_students(request.user).filter(assigned_teacher=teacher_profile)
    return render(request, 'teacher/student_list.html', {'students': students})


@login_required
def add_student(request):
    """Add a new student to the teacher's class."""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password', 'student123')  # Default password
        student_class = request.POST.get('student_class')
        dob = request.POST.get('dob')
        
        # Check if email already exists
        if CustomUser.objects.filter(email=email).exists():
            return JsonResponse({'status': 'error', 'message': 'Email already exists'})
        
        # Generate unique roll number
        import random
        while True:
            roll = str(random.randint(10000000, 99999999))
            if not StudentProfile.objects.filter(roll_number=roll).exists():
                break
        
        # Create user
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            full_name=name,
            role=CustomUser.Role.STUDENT
        )
        
        # Get teacher profile
        teacher_profile, _ = TeacherProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'aadhar_id': 'Not Provided',
                'phone': 'Not Provided'
            }
        )
        
        # Create student profile
        from django.utils.dateparse import parse_date
        StudentProfile.objects.create(
            user=user,
            phone=phone,
            student_class=student_class,
            dob=parse_date(dob) if dob else None,
            roll_number=roll,
            assigned_teacher=teacher_profile
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Student added successfully',
            'roll_number': roll
        })
    
    return render(request, 'teacher/add_student.html')


@login_required
def view_student(request, student_id):
    """View detailed information about a specific student."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'aadhar_id': 'Not Provided',
            'phone': 'Not Provided'
        }
    )
    student = get_accessible_students(request.user).filter(
        user_id=student_id,
        assigned_teacher=teacher_profile
    ).first()
    if not student:
        messages.error(request, "Student not found or not permitted.")
        return redirect("student_list")
    
    # Get student's performance data
    total_assignments = StudentAnswer.objects.filter(student=student).count()
    total_exams = ExamAnswer.objects.filter(student=student).values('exam').distinct().count()
    
    context = {
        'student': student,
        'total_assignments': total_assignments,
        'total_exams': total_exams,
    }
    return render(request, 'teacher/view_student.html', context)


@login_required
def edit_student(request, student_id):
    """Edit student information."""
    teacher_profile = TeacherProfile.objects.get(user=request.user)
    student = get_accessible_students(request.user).filter(
        user_id=student_id,
        assigned_teacher=teacher_profile
    ).first()
    if not student:
        return JsonResponse({'status': 'error', 'message': 'Student not found or not permitted'}, status=404)
    
    if request.method == 'POST':
        # Update user information
        student.user.full_name = request.POST.get('name', student.user.full_name)
        student.user.email = request.POST.get('email', student.user.email)
        student.user.save()
        
        # Update student profile
        student.phone = request.POST.get('phone', student.phone)
        student.student_class = request.POST.get('student_class', student.student_class)
        
        dob = request.POST.get('dob')
        if dob:
            from django.utils.dateparse import parse_date
            student.dob = parse_date(dob)
        
        student.save()
        
        return JsonResponse({'status': 'success', 'message': 'Student updated successfully'})
    
    return render(request, 'teacher/edit_student.html', {'student': student})


@login_required
def delete_student(request, student_id):
    """Delete a student from the teacher's class."""
    if request.method == 'POST':
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        try:
            student = get_accessible_students(request.user).get(
                user_id=student_id,
                assigned_teacher=teacher_profile
            )
            user = student.user
            
            # Delete student profile and user
            student.delete()
            user.delete()
            
            return JsonResponse({'status': 'success', 'message': 'Student deleted successfully'})
        except StudentProfile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Student not found'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
def export_students_csv(request):
    """Export student list as CSV file."""
    import csv
    from django.http import HttpResponse
    
    teacher_profile = TeacherProfile.objects.get(user=request.user)
    students = get_accessible_students(request.user).filter(assigned_teacher=teacher_profile)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students_list.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'Name', 'Email', 'Phone', 'Class', 'Date of Birth'])
    
    for student in students:
        writer.writerow([
            student.roll_number,
            student.user.full_name,
            student.user.email,
            student.phone,
            student.student_class,
            student.dob.strftime('%Y-%m-%d') if student.dob else ''
        ])
    
    return response


@login_required(login_url='teacher_login')
def add_course(request):
    """View to allow teachers to add new courses and resources."""
    if not request.user.is_teacher:
       messages.error(request, "Permission denied.")
       return redirect('teacher_dashboard')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        duration = request.POST.get('duration')
        image = request.FILES.get('image')

        # Get teacher profile
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
        except TeacherProfile.DoesNotExist:
             messages.error(request, "Teacher profile not found.")
             return redirect('teacher_dashboard')

        # Create Course
        course = Course.objects.create(
            title=title,
            description=description,
            duration=duration,
            image=image,
            teacher=teacher
        )
        
        # Handle resources from both "resources" and "resources[]" input names.
        files = request.FILES.getlist('resources') or request.FILES.getlist('resources[]')
        if not files:
            single_file = request.FILES.get('resources') or request.FILES.get('resources[]')
            if single_file:
                files = [single_file]

        for f in files:
            CourseResource.objects.create(
                course=course,
                title=f.name, # Use filename as title for now
                file=f
            )

        messages.success(request, 'Course created successfully!')
        return redirect('teacher_dashboard')
    
    return render(request, 'teacher/add_course.html')


@login_required
def respond_queries(request):
    """Respond to student queries."""
    teacher_profile = TeacherProfile.objects.get(user=request.user)

    if request.method == 'POST':
        query_id = request.POST.get('query_id')
        response_text = request.POST.get('response')

        if query_id and response_text:
            query_obj = Query.objects.get(id=query_id)
            query_obj.response = response_text
            query_obj.responded_by = teacher_profile
            query_obj.save()
            return redirect('respond_queries')

    # Only fetch unanswered queries
    allowed_students = get_accessible_students(request.user)
    queries = Query.objects.filter(response__isnull=True, student__in=allowed_students)

    query_data = []
    for query in queries:
        query_data.append({
            'id': query.id,
            'student_name': query.student_name.get_full_name(),
            'roll_number': query.student_roll.roll_number,
            'query_text': query.query_text,
            'query_image': query.query_image.url if query.query_image else None,
            'submitted_at': query.submitted_at,
        })

    return render(request, 'teacher/respond_query.html', {'queries': query_data})


@login_required
def view_responded_queries(request):
    """Student messages page: teacher messages + principal/admin announcements."""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete or you are logged in as a teacher.'
        })

    now_time = timezone.now()
    clear_state = StudentMessageClearState.objects.filter(student=student_profile).first()
    class_messages = TeacherClassMessage.objects.filter(
        Q(section=student_profile.section) | Q(section__isnull=True)
    ).order_by("-created_at")

    announcements = Announcement.objects.filter(
        Q(scope=Announcement.SCOPE_GENERAL) | Q(scope=Announcement.SCOPE_CLASS, target_section=student_profile.section)
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now_time)
    ).select_related("created_by", "target_section").order_by("-created_at")
    holidays = Holiday.objects.filter(
        Q(holiday_type=Holiday.TYPE_GENERAL) | Q(holiday_type=Holiday.TYPE_SECTION, section=student_profile.section)
    ).order_by("-created_at")

    class_cutoff = None
    announcement_cutoff = None
    if clear_state:
        if clear_state.cleared_at:
            class_cutoff = clear_state.cleared_at
            announcement_cutoff = clear_state.cleared_at
        if clear_state.teacher_messages_cleared_at and (
            not class_cutoff or clear_state.teacher_messages_cleared_at > class_cutoff
        ):
            class_cutoff = clear_state.teacher_messages_cleared_at
        if clear_state.announcements_cleared_at and (
            not announcement_cutoff or clear_state.announcements_cleared_at > announcement_cutoff
        ):
            announcement_cutoff = clear_state.announcements_cleared_at

    if class_cutoff:
        class_messages = class_messages.filter(created_at__gt=class_cutoff)
    if announcement_cutoff:
        announcements = announcements.filter(created_at__gt=announcement_cutoff)
        holidays = holidays.filter(created_at__gt=announcement_cutoff)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "clear_all":
            StudentMessageClearState.objects.update_or_create(
                student=student_profile,
                defaults={
                    "cleared_at": timezone.now(),
                    "teacher_messages_cleared_at": timezone.now(),
                    "announcements_cleared_at": timezone.now(),
                },
            )
            return redirect("view_responded_queries")
        if action == "clear_teacher":
            state, _ = StudentMessageClearState.objects.get_or_create(
                student=student_profile,
                defaults={"cleared_at": timezone.now()},
            )
            state.teacher_messages_cleared_at = timezone.now()
            state.save(update_fields=["teacher_messages_cleared_at"])
            return redirect("view_responded_queries")
        if action == "clear_announcements":
            state, _ = StudentMessageClearState.objects.get_or_create(
                student=student_profile,
                defaults={"cleared_at": timezone.now()},
            )
            state.announcements_cleared_at = timezone.now()
            state.save(update_fields=["announcements_cleared_at"])
            return redirect("view_responded_queries")

        item_type = (request.POST.get("item_type") or "").strip().lower()
        item_id = request.POST.get("item_id")
        comment_text = (request.POST.get("comment_text") or "").strip()

        try:
            if item_id and item_id.isdigit() and item_type in {"message", "announcement"}:
                if item_type == "message":
                    target = class_messages.filter(id=int(item_id)).select_related("teacher__user").first()
                    if target:
                        engagement, _ = TeacherMessageEngagement.objects.get_or_create(
                            message=target,
                            student=student_profile,
                        )
                        if action == "like":
                            engagement.is_liked = not engagement.is_liked
                            engagement.save(update_fields=["is_liked", "updated_at"])
                            if target.teacher and target.teacher.user and target.teacher.user_id != request.user.id:
                                Notification.objects.create(
                                    recipient=target.teacher.user,
                                    notification_type="general",
                                    title="Message liked",
                                    message=f"{request.user.get_full_name()} liked your class message: {target.title}",
                                )
                        elif action == "comment" and comment_text:
                            engagement.comment_text = comment_text
                            engagement.save(update_fields=["comment_text", "updated_at"])
                            if target.teacher and target.teacher.user and target.teacher.user_id != request.user.id:
                                Notification.objects.create(
                                    recipient=target.teacher.user,
                                    notification_type="general",
                                    title="New comment on message",
                                    message=f"{request.user.get_full_name()} commented on your class message: {target.title}",
                                )
                else:
                    target = announcements.filter(id=int(item_id)).first()
                    if target:
                        engagement, _ = AnnouncementEngagement.objects.get_or_create(
                            announcement=target,
                            student=student_profile,
                        )
                        if action == "like":
                            engagement.is_liked = not engagement.is_liked
                            engagement.save(update_fields=["is_liked", "updated_at"])
                            if target.created_by_id and target.created_by_id != request.user.id:
                                Notification.objects.create(
                                    recipient=target.created_by,
                                    notification_type="general",
                                    title="Announcement liked",
                                    message=f"{request.user.get_full_name()} liked your announcement: {target.title}",
                                )
                        elif action == "comment" and comment_text:
                            engagement.comment_text = comment_text
                            engagement.save(update_fields=["comment_text", "updated_at"])
                            if target.created_by_id and target.created_by_id != request.user.id:
                                Notification.objects.create(
                                    recipient=target.created_by,
                                    notification_type="general",
                                    title="New comment on announcement",
                                    message=f"{request.user.get_full_name()} commented on your announcement: {target.title}",
                                )
        except (ProgrammingError, OperationalError):
            pass

        return redirect("view_responded_queries")

    try:
        message_engagements = TeacherMessageEngagement.objects.filter(message__in=class_messages)
        announcement_engagements = AnnouncementEngagement.objects.filter(announcement__in=announcements)

        message_like_counts = {
            row["message_id"]: row["count"]
            for row in message_engagements.filter(is_liked=True).values("message_id").annotate(count=Count("id"))
        }
        message_comment_counts = {
            row["message_id"]: row["count"]
            for row in message_engagements.exclude(comment_text="").values("message_id").annotate(count=Count("id"))
        }
        message_student_map = {
            e.message_id: e
            for e in message_engagements.filter(student=student_profile)
        }

        announcement_like_counts = {
            row["announcement_id"]: row["count"]
            for row in announcement_engagements.filter(is_liked=True).values("announcement_id").annotate(count=Count("id"))
        }
        announcement_comment_counts = {
            row["announcement_id"]: row["count"]
            for row in announcement_engagements.exclude(comment_text="").values("announcement_id").annotate(count=Count("id"))
        }
        announcement_student_map = {
            e.announcement_id: e
            for e in announcement_engagements.filter(student=student_profile)
        }
    except (ProgrammingError, OperationalError):
        # Fallback for environments where migrations are out-of-sync.
        message_like_counts = {}
        message_comment_counts = {}
        message_student_map = {}
        announcement_like_counts = {}
        announcement_comment_counts = {}
        announcement_student_map = {}

    teacher_messages_feed = []
    for msg in class_messages:
        engagement = message_student_map.get(msg.id)
        teacher_messages_feed.append({
            "id": msg.id,
            "title": msg.title,
            "body": msg.message,
            "source": "Teacher Message",
            "sender": msg.teacher.user.get_full_name() if msg.teacher and msg.teacher.user else "Teacher",
            "section": str(msg.section) if msg.section else "All Sections",
            "is_important": msg.is_important,
            "created_at": msg.created_at,
            "is_liked": bool(engagement.is_liked) if engagement else False,
            "comment_text": engagement.comment_text if engagement else "",
            "likes_count": message_like_counts.get(msg.id, 0),
            "comments_count": message_comment_counts.get(msg.id, 0),
        })

    announcements_feed = []
    for ann in announcements:
        engagement = announcement_student_map.get(ann.id)
        announcements_feed.append({
            "id": ann.id,
            "title": ann.title,
            "body": ann.body,
            "source": "Announcement",
            "sender": ann.created_by.get_full_name() if ann.created_by else "Admin",
            "section": str(ann.target_section) if ann.target_section else "All Sections",
            "is_important": True if ann.scope == Announcement.SCOPE_GENERAL else False,
            "created_at": ann.created_at,
            "is_liked": bool(engagement.is_liked) if engagement else False,
            "comment_text": engagement.comment_text if engagement else "",
            "likes_count": announcement_like_counts.get(ann.id, 0),
            "comments_count": announcement_comment_counts.get(ann.id, 0),
        })

    for hol in holidays:
        announcements_feed.append({
            "id": f"holiday-{hol.id}",
            "title": f"Holiday: {hol.title}",
            "body": hol.description or f"Holiday on {hol.date.strftime('%b %d, %Y')}",
            "source": "Holiday",
            "sender": hol.created_by.get_full_name() if hol.created_by else "Admin",
            "section": str(hol.section) if hol.section else "All Sections",
            "is_important": True,
            "created_at": hol.created_at,
            "is_liked": False,
            "comment_text": "",
            "likes_count": 0,
            "comments_count": 0,
        })

    announcements_feed.sort(key=lambda x: x.get("created_at"), reverse=True)

    return render(
        request,
        'student/response_query.html',
        {
            'teacher_messages_feed': teacher_messages_feed,
            'announcements_feed': announcements_feed,
        }
    )


@login_required(login_url='teacher_login')
def manage_groups(request):
    """View to list and manage student study groups."""
    if not request.user.is_teacher:
        return redirect('teacher_login')
    teacher, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={'aadhar_id': 'Not Provided', 'phone': 'Not Provided'}
    )
    groups = StudentGroup.objects.filter(teacher=teacher)
    return render(request, 'teacher/manage_groups.html', {'groups': groups})

@login_required(login_url='teacher_login')
def create_group(request):
    """View to create a new student group based on class filter."""
    if not request.user.is_teacher:
        return redirect('teacher_login')
    teacher, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={'aadhar_id': 'Not Provided', 'phone': 'Not Provided'}
    )
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        selected_classes = request.POST.getlist('classes')  # List of selected classes
        
        group = StudentGroup.objects.create(
            name=name,
            teacher=teacher,
            description=description
        )
        
        # Add students from selected classes
        if selected_classes:
            students = get_accessible_students(request.user).filter(student_class__in=selected_classes)
            group.students.add(*students)
            messages.success(request, f"Group '{name}' created with {students.count()} students from selected classes.")
        else:
            messages.warning(request, f"Group '{name}' created but no students added (no class selected).")
            
        return redirect('manage_groups')
    
    # Get distinct classes for filter dropdown
    available_classes = get_accessible_students(request.user).values_list('student_class', flat=True).distinct()
    return render(request, 'teacher/create_group.html', {'available_classes': available_classes})


@login_required(login_url='teacher_login')
def group_competition(request, group_id):
    """Assign competition questions to a group and show first-answer leaderboard."""
    if not request.user.is_teacher:
        return redirect('teacher_login')
    teacher, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={'aadhar_id': 'Not Provided', 'phone': 'Not Provided'}
    )
    group = StudentGroup.objects.filter(id=group_id, teacher=teacher).first()
    if not group:
        messages.error(request, "Group not found.")
        return redirect('manage_groups')

    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        if question_id:
            question = Question.objects.filter(id=question_id, teacher=teacher, is_exam=False).first()
            if question:
                competition, created = GroupCompetition.objects.get_or_create(
                    group=group,
                    question=question,
                    defaults={'created_by': teacher}
                )
                if created:
                    messages.success(request, "Competition question assigned successfully.")
                else:
                    messages.info(request, "This question is already assigned to the group competition.")
            else:
                messages.error(request, "Invalid question selected.")
        else:
            messages.error(request, "Please select a question.")
        return redirect('group_competition', group_id=group.id)

    available_questions = Question.objects.filter(
        teacher=teacher,
        is_exam=False
    ).order_by('-created_at')

    competitions = GroupCompetition.objects.filter(group=group).select_related('question')
    group_students = list(group.students.select_related('user').all())
    competition_rows = []

    for competition in competitions:
        answers_qs = StudentAnswer.objects.filter(
            question=competition.question,
            student__in=group_students
        ).select_related('student__user').order_by('submitted_at', 'id')

        first_answer_by_student = {}
        for ans in answers_qs:
            if ans.student_id not in first_answer_by_student:
                first_answer_by_student[ans.student_id] = ans

        leaderboard = sorted(
            first_answer_by_student.values(),
            key=lambda x: (x.submitted_at, x.id)
        )

        leaderboard_data = []
        for rank, ans in enumerate(leaderboard, start=1):
            leaderboard_data.append({
                'rank': rank,
                'student_name': ans.student.user.get_full_name(),
                'student_email': ans.student.user.email,
                'submitted_at': ans.submitted_at,
            })

        pending_count = max(0, len(group_students) - len(leaderboard_data))

        competition_rows.append({
            'competition': competition,
            'leaderboard': leaderboard_data,
            'pending_count': pending_count,
        })

    context = {
        'group': group,
        'available_questions': available_questions,
        'competition_rows': competition_rows,
    }
    return render(request, 'teacher/group_competition.html', context)


@login_required
def search_dashboard(request):
    """Universal search for teacher dashboard."""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return render(request, 'teacher/search_results.html', {'query': query})
    
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {'message': 'Teacher profile not found.'})

    # 1. Search Students (assigned to this teacher)
    allowed_students = get_accessible_students(request.user).values_list("pk", flat=True)
    students = StudentProfile.objects.filter(
        (Q(user__full_name__icontains=query) |
        Q(user__email__icontains=query) |
        Q(roll_number__icontains=query)) &
        Q(pk__in=allowed_students)
    ).select_related('user')
    
    # 2. Search Assignments/Questions
    assignments = Question.objects.filter(
        description__icontains=query,
        teacher=teacher_profile
    )
    
    # 3. Search Exams
    exams = Exam.objects.filter(
        title__icontains=query,
        teacher=teacher_profile
    )
    
    # 4. Search Queries (from students)
    # Filter queries where student is assigned to this teacher
    queries = Query.objects.filter(
        (Q(query_text__icontains=query) |
        Q(student_name__full_name__icontains=query)) &
        Q(student__in=get_accessible_students(request.user))
    ).select_related('student_name', 'student')

    context = {
        'query': query,
        'students': students,
        'assignments': assignments,
        'exams': exams,
        'queries': queries,
        'total_results': students.count() + assignments.count() + exams.count() + queries.count()
    }
    
    return render(request, 'teacher/search_results.html', context)


@login_required
def give_remarks(request):
    """Grade student answers and provide remarks/feedback."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    assignment_owner_q = Q(question__teacher=teacher_profile) | Q(question__teacher_name=request.user)
    exam_owner_q = Q(exam__teacher=teacher_profile) | Q(exam__teacher_name=request.user)
    allowed_students = get_accessible_students(request.user).select_related("user", "section")
    allowed_subjects = get_accessible_subjects(request.user)
    homeroom_sections = Section.objects.filter(class_teacher=teacher_profile)
    # For class teachers, manual school-result upload is restricted to their own class sections only.
    is_class_teacher_context = request.user.role == CustomUser.Role.CLASS_TEACHER or homeroom_sections.exists()
    manual_students = allowed_students
    if is_class_teacher_context:
        manual_students = manual_students.filter(section__in=homeroom_sections)

    if request.method == 'POST':
        # 0. Manual school exam result upload
        if request.POST.get("action") == "manual_school_result":
            student_id = request.POST.get("student_id")
            subject_id = request.POST.get("subject_id")
            exam_type = (request.POST.get("exam_type") or "").strip()
            exam_name = (request.POST.get("exam_name") or "").strip()
            exam_date = parse_date((request.POST.get("exam_date") or "").strip())
            total_marks_raw = request.POST.get("total_marks")
            marks_obtained_raw = request.POST.get("marks_obtained")
            generate_ai_remark = request.POST.get("generate_ai_remark") == "on"
            review = (request.POST.get("review") or "").strip()

            student = manual_students.filter(user_id=student_id).first()
            subject = allowed_subjects.filter(id=subject_id).first() if subject_id else None

            try:
                total_marks = float(total_marks_raw) if total_marks_raw else 0
                marks_obtained = float(marks_obtained_raw) if marks_obtained_raw else 0
            except (TypeError, ValueError):
                messages.error(request, "Invalid marks format.")
                return redirect("give_remarks")

            if not student:
                messages.error(request, "Invalid student selection.")
                return redirect("give_remarks")
            if not subject:
                messages.error(request, "Please select a valid subject.")
                return redirect("give_remarks")
            if exam_type not in dict(SchoolExamResult.EXAM_TYPE_CHOICES):
                messages.error(request, "Invalid exam type.")
                return redirect("give_remarks")
            if total_marks <= 0:
                messages.error(request, "Total marks must be greater than 0.")
                return redirect("give_remarks")
            if marks_obtained < 0 or marks_obtained > total_marks:
                messages.error(request, "Obtained marks must be between 0 and total marks.")
                return redirect("give_remarks")

            percentage = (marks_obtained / total_marks) * 100
            final_review = review
            if generate_ai_remark:
                final_review = _optional_ai_remark(
                    student_name=student.user.get_full_name(),
                    subject_name=subject.name,
                    percentage=percentage,
                    teacher_review=review,
                )

            SchoolExamResult.objects.create(
                teacher=teacher_profile,
                student=student,
                section=student.section,
                subject=subject,
                exam_type=exam_type,
                exam_name=exam_name,
                exam_date=exam_date,
                total_marks=total_marks,
                marks_obtained=marks_obtained,
                review=final_review,
            )

            # Update aggregated subject performance shown in student dashboard graph.
            agg = SchoolExamResult.objects.filter(
                student=student,
                subject=subject,
            ).aggregate(
                total_obtained=Sum("marks_obtained"),
                total_max=Sum("total_marks"),
            )
            perf, _ = StudentSubjectPerformance.objects.get_or_create(
                student=student,
                subject=subject,
                defaults={"updated_by": teacher_profile},
            )
            perf.marks_obtained = float(agg.get("total_obtained") or 0)
            perf.total_marks = float(agg.get("total_max") or 0)
            perf.recompute_percentage_and_remark()
            if generate_ai_remark:
                perf.ai_remark = final_review
            perf.updated_by = teacher_profile
            perf.save()

            messages.success(request, f"School exam result uploaded. Percentage: {percentage:.2f}%")
            return redirect("give_remarks")

        # 1. Single Assignment Submission
        if request.POST.get('answer_id'):
            answer_id = request.POST.get('answer_id')
            remark_text = request.POST.get('remark_text')
            answer_type = request.POST.get('answer_type')
            marks = request.POST.get('marks')

            try:
                if answer_type == "student":
                    answer = StudentAnswer.objects.filter(assignment_owner_q, id=answer_id).first()
                else:
                    answer = ExamAnswer.objects.filter(exam_owner_q, id=answer_id).first()

                if not answer:
                    return redirect('give_remarks')

                if marks:
                    answer.marks_obtained = marks
                
                answer.remarks = remark_text
                answer.save()
            except (ValueError, TypeError):
                pass

        # 2. Bulk Exam Submission (from remarks.html)
        else:
            # Loop through keys to find answers[<id>][id]
            for key in request.POST:
                if key.startswith('answers[') and key.endswith('][id]'):
                    try:
                        ans_id = request.POST[key]
                        ans_type = request.POST.get(f'answers[{ans_id}][type]')
                        marks = request.POST.get(f'answers[{ans_id}][marks]')
                        remark = request.POST.get(f'answers[{ans_id}][remark]')

                        if ans_type == 'exam':
                            answer = ExamAnswer.objects.filter(exam_owner_q, id=ans_id).first()
                            if not answer:
                                continue
                            if marks:
                                answer.marks_obtained = marks
                            if remark:
                                answer.remarks = remark
                            answer.save()
                    except ValueError:
                        continue

        return redirect('give_remarks')

    # Fetch unanswered Student Answers
    student_answers = StudentAnswer.objects.filter(
        assignment_owner_q
    ).filter(
        Q(remarks__isnull=True) | Q(remarks='')
    ).select_related('question', 'student_name')

    student_list = []
    for ans in student_answers:
        desc = ans.question.description
        if "LaTeX Equation:" in desc:
            parts = desc.split("LaTeX Equation:")
            question_text = parts[0].strip()
            latex = parts[1].strip()
        else:
            question_text = desc.strip()
            latex = ""
        student_list.append({
            'id': ans.id,
            'answer_type': "student",
            'question_text': question_text,
            'latex': latex,
            'answer_text': ans.answer_text,
            'answer_file': ans.answer_file.url if ans.answer_file else None,
            'remarks': ans.remarks,
            'student_name': ans.student_name.get_full_name(),
        })

    # Fetch unanswered Exam Answers
    exam_answers = ExamAnswer.objects.filter(
        exam_owner_q
    ).filter(
        Q(remarks__isnull=True) | Q(remarks='')
    ).select_related('exam', 'question', 'student_name')

    exam_list = []
    for ans in exam_answers:
        exam_list.append({
            'id': ans.id,
            'answer_type': "exam",
            'exam_title': ans.exam.title,
            'question_text': ans.question.text,
            'latex': ans.question.latex,
            'answer_text': ans.answer_text,
            'answer_file': ans.answer_file.url if ans.answer_file else None,
            'remarks': ans.remarks,
            'student_name': ans.student_name.get_full_name(),
        })

    # Reviewed assignment answers
    reviewed_student_answers = StudentAnswer.objects.filter(
        assignment_owner_q
    ).filter(
        Q(remarks__isnull=False) & ~Q(remarks='')
    ).select_related("question", "student_name").order_by("-submitted_at")[:60]
    reviewed_student_list = []
    for ans in reviewed_student_answers:
        desc = ans.question.description
        question_text = desc.split("LaTeX Equation:")[0].strip() if "LaTeX Equation:" in desc else desc.strip()
        reviewed_student_list.append(
            {
                "id": ans.id,
                "student_name": ans.student_name.get_full_name(),
                "question_text": question_text,
                "marks_obtained": ans.marks_obtained,
                "remarks": ans.remarks,
                "submitted_at": ans.submitted_at,
            }
        )

    # Reviewed exam answers
    reviewed_exam_answers = ExamAnswer.objects.filter(
        exam_owner_q
    ).filter(
        Q(remarks__isnull=False) & ~Q(remarks='')
    ).select_related("exam", "question", "student_name").order_by("-submitted_at")[:80]
    reviewed_exam_list = []
    for ans in reviewed_exam_answers:
        reviewed_exam_list.append(
            {
                "id": ans.id,
                "exam_title": ans.exam.title,
                "student_name": ans.student_name.get_full_name(),
                "question_text": ans.question.text,
                "marks_obtained": ans.marks_obtained,
                "remarks": ans.remarks,
                "submitted_at": ans.submitted_at,
            }
        )

    manual_results = SchoolExamResult.objects.filter(
        teacher=teacher_profile
    ).select_related("student__user", "section", "subject").order_by("-created_at")[:100]

    context = {
        'student_answers': student_list,
        'exam_answers': exam_list,
        'reviewed_student_answers': reviewed_student_list,
        'reviewed_exam_answers': reviewed_exam_list,
        'manual_exam_results': manual_results,
        'manual_exam_type_choices': SchoolExamResult.EXAM_TYPE_CHOICES,
        'manual_students': manual_students,
        'manual_subjects': allowed_subjects,
    }

    return render(request, 'teacher/remarks.html', context)


@login_required
def lecture_notes(request):
    """Student class notes page: teacher notes + virtual abacus."""
    try:
        student_profile = StudentProfile.objects.select_related("section").get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(
            request,
            "student/profile_missing.html",
            {"message": "Your student profile is incomplete. Please contact an administrator."},
        )

    notes_qs = (
        TeacherNote.objects.filter(is_published=True)
        .select_related("teacher__user", "subject", "section")
        .order_by("-created_at")
    )
    if student_profile.section_id:
        notes_qs = notes_qs.filter(Q(section=student_profile.section) | Q(section__isnull=True))
    else:
        notes_qs = notes_qs.filter(section__isnull=True)

    resources_qs = (
        SubjectResource.objects.filter(is_published=True)
        .select_related("subject", "section", "uploaded_by__user")
        .order_by("-created_at")
    )
    if student_profile.section_id:
        resources_qs = resources_qs.filter(section=student_profile.section)
    else:
        resources_qs = resources_qs.none()

    context = {
        "notes_feed": notes_qs[:50],
        "resource_feed": resources_qs[:80],
        "student_section": student_profile.section,
    }
    return render(request, "student/lecture_notes.html", context)


@login_required(login_url='teacher_login')
def teacher_assigned_sections(request):
    """List sections visible to the current teacher."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={"aadhar_id": "Not Provided", "phone": "Not Provided"},
    )
    sections = get_accessible_sections(request.user).prefetch_related("students", "class_teacher__user")
    section_ids = list(sections.values_list("id", flat=True))
    assignment_qs = SubjectTeacherAssignment.objects.filter(
        teacher=teacher_profile,
        section_id__in=section_ids,
    ).select_related("subject")

    assigned_subjects_by_section = {}
    for item in assignment_qs:
        names = assigned_subjects_by_section.setdefault(item.section_id, [])
        if item.subject and item.subject.name not in names:
            names.append(item.subject.name)

    selected_scope = (request.GET.get("scope") or "all").strip().lower()
    valid_scopes = {"all", "my_class_teacher", "assigned_teacher", "without_class_teacher"}
    if selected_scope not in valid_scopes:
        selected_scope = "all"

    section_rows = []
    for section in sections:
        assignment = TeacherSectionAssignment.objects.filter(
            teacher=teacher_profile,
            section=section,
        ).first()
        is_class_teacher = section.class_teacher_id == teacher_profile.user_id or (
            assignment and assignment.is_class_teacher
        )
        if is_class_teacher:
            role_label = "Class Teacher"
        elif assignment:
            role_label = "Assigned Teacher"
        else:
            role_label = "Visible by Access"

        class_teacher_name = (
            section.class_teacher.user.get_full_name()
            if section.class_teacher and section.class_teacher.user
            else "Not Assigned"
        )
        section_rows.append(
            {
                "section": section,
                "assigned_subjects": assigned_subjects_by_section.get(section.id, []),
                "role_label": role_label,
                "is_class_teacher": is_class_teacher,
                "is_assigned_teacher": bool(assignment) and not is_class_teacher,
                "class_teacher_name": class_teacher_name,
                "has_class_teacher": bool(section.class_teacher_id),
            }
        )

    sections_without_class_teacher = [row for row in section_rows if not row["has_class_teacher"]]
    filtered_section_rows = section_rows
    if selected_scope == "my_class_teacher":
        filtered_section_rows = [row for row in section_rows if row["is_class_teacher"]]
    elif selected_scope == "assigned_teacher":
        filtered_section_rows = [row for row in section_rows if row["is_assigned_teacher"]]
    elif selected_scope == "without_class_teacher":
        filtered_section_rows = [row for row in section_rows if not row["has_class_teacher"]]

    context = {
        "section_rows": filtered_section_rows,
        "all_section_rows_count": len(section_rows),
        "class_teacher_rows_count": sum(1 for row in section_rows if row["is_class_teacher"]),
        "assigned_teacher_rows_count": sum(1 for row in section_rows if row["is_assigned_teacher"]),
        "without_class_teacher_rows_count": len(sections_without_class_teacher),
        "selected_scope": selected_scope,
        "sections_without_class_teacher": sections_without_class_teacher,
    }
    return render(request, "teacher/assigned_sections.html", context)


@login_required(login_url='teacher_login')
def upload_notes(request):
    """Upload and manage teacher notes."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={"aadhar_id": "Not Provided", "phone": "Not Provided"},
    )
    sections = get_accessible_sections(request.user)
    subjects = get_accessible_subjects(request.user)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        content = (request.POST.get("content") or "").strip()
        section_id = request.POST.get("section_id")
        subject_id = request.POST.get("subject_id")
        attachment = request.FILES.get("attachment")

        if not title:
            messages.error(request, "Title is required.")
            return redirect("teacher_upload_notes")
        if not content and not attachment:
            messages.error(request, "Add note content or upload a file.")
            return redirect("teacher_upload_notes")

        section = None
        if section_id:
            section = sections.filter(id=section_id).first()
        subject = None
        if subject_id:
            subject = subjects.filter(id=subject_id).first()

        TeacherNote.objects.create(
            teacher=teacher_profile,
            section=section,
            subject=subject,
            title=title,
            content=content,
            attachment=attachment,
            is_published=True,
        )
        messages.success(request, "Note uploaded successfully.")
        return redirect("teacher_upload_notes")

    notes = TeacherNote.objects.filter(teacher=teacher_profile).select_related("section", "subject")
    return render(
        request,
        "teacher/upload_notes.html",
        {"sections": sections, "subjects": subjects, "notes": notes},
    )


@login_required(login_url='teacher_login')
def post_class_message(request):
    """Post and view class messages."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={"aadhar_id": "Not Provided", "phone": "Not Provided"},
    )
    sections = get_accessible_sections(request.user)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        message_text = (request.POST.get("message") or "").strip()
        section_id = request.POST.get("section_id")
        is_important = request.POST.get("is_important") == "on"

        if not title or not message_text:
            messages.error(request, "Both title and message are required.")
            return redirect("teacher_post_class_message")

        section = None
        if section_id:
            section = sections.filter(id=section_id).first()

        TeacherClassMessage.objects.create(
            teacher=teacher_profile,
            section=section,
            title=title,
            message=message_text,
            is_important=is_important,
        )
        messages.success(request, "Class message posted successfully.")
        return redirect("teacher_post_class_message")

    messages_feed = TeacherClassMessage.objects.filter(teacher=teacher_profile).select_related("section")
    return render(
        request,
        "teacher/post_class_message.html",
        {"sections": sections, "messages_feed": messages_feed},
    )


@login_required(login_url='teacher_login')
def manage_holidays(request):
    """Create and view holidays from teacher/principal side."""
    sections = get_accessible_sections(request.user)
    can_create_general = (
        request.user.is_superuser
        or request.user.is_staff
        or request.user.role in {CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}
    )

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        date_raw = (request.POST.get("date") or "").strip()
        holiday_type = (request.POST.get("holiday_type") or Holiday.TYPE_SECTION).strip()
        section_id = (request.POST.get("section_id") or "").strip()
        description = (request.POST.get("description") or "").strip()

        if not title or not date_raw:
            messages.error(request, "Title and date are required.")
            return redirect("teacher_manage_holidays")

        date_obj = parse_date(date_raw)
        if not date_obj:
            messages.error(request, "Invalid date.")
            return redirect("teacher_manage_holidays")

        if holiday_type == Holiday.TYPE_GENERAL and not can_create_general:
            messages.error(request, "Only principal/admin can create general holidays.")
            return redirect("teacher_manage_holidays")

        section = None
        if holiday_type == Holiday.TYPE_SECTION:
            if not section_id:
                messages.error(request, "Section is required for section holiday.")
                return redirect("teacher_manage_holidays")
            section = sections.filter(id=section_id).first()
            if not section:
                messages.error(request, "Invalid section selection.")
                return redirect("teacher_manage_holidays")

        Holiday.objects.create(
            created_by=request.user,
            title=title,
            date=date_obj,
            holiday_type=holiday_type,
            section=section,
            description=description,
        )
        messages.success(request, "Holiday added successfully.")
        return redirect("teacher_manage_holidays")

    holidays_qs = Holiday.objects.filter(
        Q(created_by=request.user) | Q(section__in=sections)
    ).order_by("-date", "-created_at")

    return render(
        request,
        "teacher/manage_holidays.html",
        {
            "sections": sections,
            "holidays_feed": holidays_qs[:80],
            "can_create_general": can_create_general,
            "holiday_type_choices": Holiday.TYPE_CHOICES,
        },
    )


@login_required(login_url='teacher_login')
def attendance_marking(request):
    """Mark attendance for accessible students with per-day upsert."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={"aadhar_id": "Not Provided", "phone": "Not Provided"},
    )
    homeroom_sections = Section.objects.filter(class_teacher=teacher_profile)
    is_homeroom_teacher = homeroom_sections.exists() and request.user.role in {
        CustomUser.Role.TEACHER,
        CustomUser.Role.CLASS_TEACHER,
    }
    if is_homeroom_teacher:
        sections = homeroom_sections
    else:
        sections = get_accessible_sections(request.user)
    selected_section_id = request.GET.get("section") or request.POST.get("section_id") or ""
    selected_date_raw = request.GET.get("date") or request.POST.get("attendance_date") or timezone.localdate().isoformat()
    today = timezone.localdate()
    selected_date_obj = parse_date(selected_date_raw) or today
    if selected_date_obj > today:
        if request.method == "POST":
            messages.error(request, "Future date attendance is not allowed. You can mark attendance only up to today.")
            safe_section = f"&section={selected_section_id}" if selected_section_id else ""
            return redirect(f"{request.path}?date={today.isoformat()}{safe_section}")
        messages.error(request, "Future date is not allowed. Showing today's attendance sheet.")
        selected_date_obj = today
    selected_date = selected_date_obj.isoformat()

    if is_homeroom_teacher:
        students = StudentProfile.objects.select_related("user", "section").filter(section__in=sections)
    else:
        students = get_accessible_students(request.user).select_related("user", "section")
    allowed_section_ids = set(sections.values_list("id", flat=True))
    if selected_section_id and selected_section_id.isdigit() and int(selected_section_id) not in allowed_section_ids:
        selected_section_id = ""
    if selected_section_id:
        students = students.filter(section_id=selected_section_id)

    existing_records = AttendanceRecord.objects.filter(
        student__in=students,
        date=selected_date_obj,
    )
    existing_map = {record.student_id: record for record in existing_records}

    if request.method == "POST":
        updated = 0
        for student in students:
            status = request.POST.get(f"attendance_{student.user_id}", AttendanceRecord.STATUS_PRESENT)
            if status not in {
                AttendanceRecord.STATUS_PRESENT,
                AttendanceRecord.STATUS_ABSENT,
                AttendanceRecord.STATUS_LATE,
            }:
                status = AttendanceRecord.STATUS_PRESENT
            remarks = (request.POST.get(f"remarks_{student.user_id}") or "").strip()
            AttendanceRecord.objects.update_or_create(
                student=student,
                date=selected_date_obj,
                defaults={
                    "teacher": teacher_profile,
                    "status": status,
                    "remarks": remarks,
                },
            )
            updated += 1

        messages.success(request, f"Attendance saved for {updated} students.")
        return redirect(f"{request.path}?date={selected_date}&section={selected_section_id}")

    summary = {
        "present": existing_records.filter(status=AttendanceRecord.STATUS_PRESENT).count(),
        "absent": existing_records.filter(status=AttendanceRecord.STATUS_ABSENT).count(),
        "late": existing_records.filter(status=AttendanceRecord.STATUS_LATE).count(),
        "total": students.count(),
    }

    student_rows = []
    for student in students:
        student_rows.append({
            "student": student,
            "existing": existing_map.get(student.user_id),
        })

    context = {
        "sections": sections,
        "students": students,
        "student_rows": student_rows,
        "selected_section_id": str(selected_section_id),
        "selected_date": selected_date,
        "today_date": today.isoformat(),
        "summary": summary,
    }
    return render(request, "teacher/attendance_marking.html", context)


# ==================== SUBJECT & CHAPTER MANAGEMENT ====================

@login_required
def manage_subjects(request):
    """View and manage teacher's subjects and chapters."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    subjects = get_accessible_subjects(request.user).prefetch_related('chapters')
    subject_rows = []
    for subject in subjects:
        assignments = SubjectTeacherAssignment.objects.filter(subject=subject).select_related("section", "teacher__user")
        subject_rows.append(
            {
                "subject": subject,
                "assignments": assignments,
                "resources_count": SubjectResource.objects.filter(subject=subject).count(),
            }
        )
    
    context = {
        'subjects': subjects,
        'subject_rows': subject_rows,
    }
    return render(request, 'teacher/manage_subjects.html', context)


@login_required
def create_subject(request):
    """Create a new subject."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    homeroom_sections = Section.objects.filter(
        Q(class_teacher=teacher_profile)
        | Q(teacher_assignments__teacher=teacher_profile, teacher_assignments__is_class_teacher=True)
    ).distinct()
    is_homeroom_teacher = homeroom_sections.exists()
    allowed_roles = {CustomUser.Role.CLASS_TEACHER, CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}
    if request.user.role not in allowed_roles and not is_homeroom_teacher:
        messages.error(request, "Only Class Teacher, Principal, or Admin can create section subjects.")
        return redirect("manage_subjects")

    if is_homeroom_teacher:
        sections = homeroom_sections
    else:
        sections = get_accessible_sections(request.user)
    section_ids = list(sections.values_list("id", flat=True))
    teacher_ids = list(TeacherSectionAssignment.objects.filter(section_id__in=section_ids).values_list("teacher_id", flat=True))
    if is_homeroom_teacher:
        teacher_ids.append(teacher_profile.user_id)
    if teacher_ids:
        available_teachers = TeacherProfile.objects.filter(user_id__in=set(teacher_ids)).select_related("user")
    else:
        available_teachers = TeacherProfile.objects.select_related("user")

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        section_id = request.POST.get('section_id')
        assigned_teacher_id = request.POST.get('assigned_teacher_id')
        description = (request.POST.get('description') or '').strip()
        class_level = (request.POST.get('class_level') or '').strip()
        if not name:
            messages.error(request, "Subject name is required.")
            return redirect('create_subject')
        if not section_id:
            messages.error(request, "Please select section.")
            return redirect('create_subject')
        section = sections.filter(id=section_id).first()
        if not section:
            messages.error(request, "Invalid section selected.")
            return redirect('create_subject')
        if not class_level:
            class_level = section.class_level
        assigned_teacher = available_teachers.filter(user_id=assigned_teacher_id).first()
        if not assigned_teacher:
            messages.error(request, "Please select a valid assigned subject teacher.")
            return redirect('create_subject')
        
        try:
            subject = Subject.objects.create(
                teacher=teacher_profile,
                name=name,
                class_level=class_level,
                description=description
            )
            SubjectTeacherAssignment.objects.create(
                teacher=assigned_teacher,
                subject=subject,
                section=section,
            )
            messages.success(request, f'Subject "{name}" created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating subject: {str(e)}')
        
        return redirect('manage_subjects')
    
    context = {
        "sections": sections,
        "available_teachers": available_teachers,
    }
    return render(request, 'teacher/create_subject.html', context)


@login_required
def teacher_subject_resources(request, subject_id):
    """Assigned subject teacher uploads Books/Notes/Videos/Quiz/Worksheets."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    subject = Subject.objects.filter(id=subject_id).first()
    if not subject:
        messages.error(request, "Subject not found.")
        return redirect("manage_subjects")

    is_assigned = SubjectTeacherAssignment.objects.filter(subject=subject, teacher=teacher_profile).exists()
    is_creator = subject.teacher_id == teacher_profile.user_id
    is_admin_role = request.user.role in {CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}
    if not (is_assigned or is_creator or is_admin_role):
        messages.error(request, "You are not allowed to manage resources for this subject.")
        return redirect("manage_subjects")

    section_assignments = SubjectTeacherAssignment.objects.filter(subject=subject).select_related("section", "teacher__user")
    allowed_sections = [a.section for a in section_assignments]
    allowed_section_ids = {s.id for s in allowed_sections if s}

    if request.method == "POST":
        resource_type = (request.POST.get("resource_type") or "").strip()
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        external_url = (request.POST.get("external_url") or "").strip()
        section_id = request.POST.get("section_id")
        file_obj = request.FILES.get("file")

        if resource_type not in dict(SubjectResource.TYPE_CHOICES):
            messages.error(request, "Invalid resource type.")
            return redirect("teacher_subject_resources", subject_id=subject.id)
        if not title:
            messages.error(request, "Title is required.")
            return redirect("teacher_subject_resources", subject_id=subject.id)
        if not file_obj and not external_url:
            messages.error(request, "Upload file or provide URL.")
            return redirect("teacher_subject_resources", subject_id=subject.id)

        section = None
        if section_id and section_id.isdigit():
            sid = int(section_id)
            if sid not in allowed_section_ids:
                messages.error(request, "Invalid section for this subject.")
                return redirect("teacher_subject_resources", subject_id=subject.id)
            section = Section.objects.filter(id=sid).first()

        SubjectResource.objects.create(
            subject=subject,
            section=section,
            uploaded_by=teacher_profile,
            resource_type=resource_type,
            title=title,
            description=description,
            file=file_obj,
            external_url=external_url,
            is_published=True,
        )
        messages.success(request, "Resource uploaded successfully.")
        return redirect("teacher_subject_resources", subject_id=subject.id)

    resources = SubjectResource.objects.filter(subject=subject).select_related("uploaded_by__user", "section")
    counts = {
        "book": resources.filter(resource_type=SubjectResource.TYPE_BOOK).count(),
        "note": resources.filter(resource_type=SubjectResource.TYPE_NOTE).count(),
        "video": resources.filter(resource_type=SubjectResource.TYPE_VIDEO).count(),
        "quiz": resources.filter(resource_type=SubjectResource.TYPE_QUIZ).count(),
        "worksheet": resources.filter(resource_type=SubjectResource.TYPE_WORKSHEET).count(),
    }
    context = {
        "subject": subject,
        "section_assignments": section_assignments,
        "resources": resources,
        "counts": counts,
        "resource_choices": SubjectResource.TYPE_CHOICES,
    }
    return render(request, "teacher/subject_resources.html", context)


@login_required
def edit_subject(request, subject_id):
    """Edit an existing subject."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    try:
        subject = get_accessible_subjects(request.user).get(id=subject_id)
    except Subject.DoesNotExist:
        messages.error(request, "Subject not found.")
        return redirect('manage_subjects')
    
    if request.method == 'POST':
        subject.name = request.POST.get('name', subject.name)
        subject.class_level = request.POST.get('class_level', subject.class_level)
        subject.description = request.POST.get('description', subject.description)
        subject.save()
        
        messages.success(request, f'Subject "{subject.name}" updated successfully!')
        return redirect('manage_subjects')
    
    context = {'subject': subject}
    return render(request, 'teacher/edit_subject.html', context)


@login_required
@login_required
def delete_subject(request, subject_id):
    """Delete a subject."""
    if request.method == 'POST':
        teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
        try:
            subject = get_accessible_subjects(request.user).get(id=subject_id)
            subject_name = subject.name
            subject.delete()
            messages.success(request, f'Subject "{subject_name}" deleted successfully!')
        except Subject.DoesNotExist:
            messages.error(request, 'Subject not found.')
        
        return redirect('manage_subjects')
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
def create_chapter(request):
    """Create a new chapter within a subject."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        name = request.POST.get('name')
        chapter_number = request.POST.get('chapter_number')
        ncert_reference = request.POST.get('ncert_reference', '')
        description = request.POST.get('description', '')
        
        try:
            subject = get_accessible_subjects(request.user).get(id=subject_id)
            Chapter.objects.create(
                subject=subject,
                name=name,
                chapter_number=int(chapter_number) if chapter_number else None,
                ncert_reference=ncert_reference,
                description=description
            )
            messages.success(request, f'Chapter "{name}" created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating chapter: {str(e)}')
        
        return redirect('manage_subjects')
    
    subjects = get_accessible_subjects(request.user)
    context = {'subjects': subjects}
    return render(request, 'teacher/create_chapter.html', context)


@login_required
def edit_chapter(request, chapter_id):
    """Edit an existing chapter."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    try:
        chapter = Chapter.objects.get(id=chapter_id, subject__in=get_accessible_subjects(request.user))
    except Chapter.DoesNotExist:
        messages.error(request, "Chapter not found.")
        return redirect('manage_subjects')
    
    if request.method == 'POST':
        chapter.name = request.POST.get('name', chapter.name)
        chapter_number = request.POST.get('chapter_number')
        chapter.chapter_number = int(chapter_number) if chapter_number else None
        chapter.ncert_reference = request.POST.get('ncert_reference', chapter.ncert_reference)
        chapter.description = request.POST.get('description', chapter.description)
        chapter.save()
        
        messages.success(request, f'Chapter "{chapter.name}" updated successfully!')
        return redirect('manage_subjects')
    
    context = {'chapter': chapter}
    return render(request, 'teacher/edit_chapter.html', context)


@login_required
def delete_chapter(request, chapter_id):
    """Delete a chapter."""
    if request.method == 'POST':
        teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
        try:
            chapter = Chapter.objects.get(id=chapter_id, subject__in=get_accessible_subjects(request.user))
            chapter_name = chapter.name
            chapter.delete()
            messages.success(request, f'Chapter "{chapter_name}" deleted successfully!')
        except Chapter.DoesNotExist:
             messages.error(request, 'Chapter not found.')
             
        return redirect('manage_subjects')

    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
