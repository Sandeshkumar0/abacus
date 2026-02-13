"""
Student-related views for the dashboard app.
Handles student dashboard, assignments, queries, remarks, and exams.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from django.utils.timezone import now, timedelta
import io
import urllib.parse
import requests
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from accounts.models import StudentProfile, TeacherProfile
from ..models import StudentAnswer, Question, Query, Exam, ExamQuestion, ExamAnswer, Course, Enrollment, Notification


@login_required(login_url='student_login')
def student_dashboard(request):
    """Main dashboard view for students with real statistics."""
    
    # Get the student's profile
    # Get the student's profile
    student_profile, created = StudentProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'roll_number': f'STU{request.user.id}',
            'student_class': 'Unknown',
            'dob': timezone.now().date(),
            'phone': '0000000000'
        }
    )
    # New profile might not have teacher assigned, handle that gracefully if needed later
    
    # Get statistics
    # Total assignments (questions) assigned to this student
    total_assignments = Question.objects.all().count()
    
    # Pending assignments (questions not yet answered by this student)
    submitted_question_ids = StudentAnswer.objects.filter(
        student=student_profile
    ).values_list('question_id', flat=True)
    
    pending_assignments = Question.objects.exclude(
        id__in=submitted_question_ids
    ).count()
    
    # Pending queries (queries by this student that haven't been answered)
    pending_queries = Query.objects.filter(
        student=student_profile,
        response__isnull=True
    ).count()
    
    # Upcoming exams (exams that haven't expired yet)
    upcoming_exams = Exam.objects.filter(
        teacher=student_profile.assigned_teacher,
        due_date__gt=timezone.now()
    ).count()
    
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
    
    # Count of recently graded (last 7 days)
    from datetime import timedelta
    week_ago = timezone.now() - timedelta(days=7)
    recent_graded_count = StudentAnswer.objects.filter(
        student=student_profile,
        remarks__isnull=False,
        id__gte=StudentAnswer.objects.filter(student=student_profile).order_by('-id').first().id - 10 if StudentAnswer.objects.filter(student=student_profile).exists() else 0
    ).count()
    
    # My Enrolled Courses
    enrollments = Enrollment.objects.filter(student=student_profile).select_related('course')

    context = {
        'total_assignments': total_assignments,
        'pending_assignments': pending_assignments,
        'pending_queries': pending_queries,
        'upcoming_exams': upcoming_exams,
        'recent_graded': recent_graded,
        'recent_responses': recent_responses,
        'recent_graded_count': recent_graded_count,
        'enrollments': enrollments,
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
            question = Question.objects.get(id=question_id)
        except Question.DoesNotExist:
             return JsonResponse({'status': 'error', 'message': 'Question not found'}, status=404)
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Student profile not found'}, status=403)

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
    all_questions = Question.objects.all().order_by('created_at')
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
def student_profile(request):
    """Display student profile."""
    try:
        student = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile.html', {
            'student': None,
            'error_message': 'No student profile found. Please contact administrator to create your profile.'
        })
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

    return JsonResponse({"status": "ok", "exam": exam.title, "questions": questions})


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

    if ExamAnswer.objects.filter(exam=exam, student=student_profile).exists():
        return redirect("give_test")

    if request.method == "POST":
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
                marks_obtained=0
            )
        return redirect("give_test")

    context = {"exam": exam, "questions": exam.questions.all()}
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
    new_exams = Exam.objects.exclude(
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
