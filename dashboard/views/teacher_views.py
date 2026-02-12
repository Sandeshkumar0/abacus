"""
Teacher-related views for the dashboard app.
Handles teacher dashboard, question assignment, exam creation, student management, and grading.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from datetime import datetime
import json
import os
import tempfile
from dotenv import load_dotenv

from accounts.models import TeacherProfile, StudentProfile
from ..models import Question, Query, StudentAnswer, ExamAnswer, Exam, ExamQuestion


@login_required(login_url='teacher_login')
def teacher_dashboard(request):
    """Main dashboard view for teachers."""
    if not request.user.is_authenticated:
        return redirect('teacher_login')
    if not request.user.is_teacher:
        return redirect('teacher_login')
    
    # Get teacher profile
    teacher_profile = TeacherProfile.objects.get(user=request.user)
    
    # Calculate statistics
    total_students = StudentProfile.objects.filter(assigned_teacher=teacher_profile).count()
    active_assignments = Question.objects.filter(teacher=teacher_profile).count()
    pending_queries = Query.objects.filter(response__isnull=True).count()
    upcoming_tests = Exam.objects.filter(
        teacher=teacher_profile,
        due_date__gte=timezone.now()
    ).count()
    
    context = {
        'total_students': total_students,
        'active_assignments': active_assignments,
        'pending_queries': pending_queries,
        'upcoming_tests': upcoming_tests,
    }
    
    return render(request, 'teacher/teacher_dashboard.html', context)


@login_required
def teacher_profile(request):
    """Display teacher profile."""
    teacher = TeacherProfile.objects.get(user=request.user)
    return render(request, 'teacher/profile.html', {'teacher': teacher})


@login_required
def teacher_profile_edit(request):
    """Edit teacher profile - update profile picture and office details."""
    teacher = TeacherProfile.objects.get(user=request.user)
    
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
    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        latex_equation = request.POST.get('latex_equation', '').strip()
        max_marks = int(request.POST.get('max_marks', 0))
        is_exam = request.POST.get('is_test') in ['true', 'on', '1']
        due_date_str = request.POST.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                due_date = timezone.now()

        teacher = TeacherProfile.objects.get(user=request.user)
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
            image=uploaded_file
        )

        return redirect('assign_questions')

    return render(request, 'teacher/assign_questions.html')


@login_required
@csrf_exempt
def take_test(request):
    """Create and manage tests/exams (legacy endpoint)."""
    if request.method == "POST":
        exam_heading = request.POST.get("examHeading")
        due_date = request.POST.get("dueDate")
        total_marks = request.POST.get("totalMarks")
        questions_data = request.POST.getlist("questions[]")

        teacher = TeacherProfile.objects.get(user=request.user)
        exam = Exam.objects.create(
            teacher=teacher,
            teacher_name=request.user,
            title=exam_heading,
            due_date=parse_datetime(due_date),
            total_marks=total_marks,
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
    teacher_profile = TeacherProfile.objects.get(user=request.user)
    exams = Exam.objects.filter(teacher=teacher_profile).order_by('-created_at')
    
    return render(request, "teacher/take_test.html", {'exams': exams})


@csrf_exempt
@login_required
def create_exam(request):
    """Create a new exam with questions."""
    if request.method == "POST":
        exam_heading = request.POST.get("examHeading")
        due_date_str = request.POST.get("dueDate")
        total_marks = request.POST.get("totalMarks")

        due_date = make_aware(datetime.strptime(due_date_str, "%Y-%m-%d %H:%M"))

        teacher_profile = request.user.teacherprofile
        teacher_user = request.user

        exam = Exam.objects.create(
            teacher=teacher_profile,
            teacher_name=teacher_user,
            title=exam_heading,
            due_date=due_date,
            total_marks=total_marks,
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
    teacher_profile = TeacherProfile.objects.get(user=request.user)
    students = StudentProfile.objects.filter(assigned_teacher=teacher_profile)
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
            is_student=True
        )
        
        # Get teacher profile
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        
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
    teacher_profile = TeacherProfile.objects.get(user=request.user)
    student = StudentProfile.objects.get(user_id=student_id, assigned_teacher=teacher_profile)
    
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
    student = StudentProfile.objects.get(user_id=student_id, assigned_teacher=teacher_profile)
    
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
            student = StudentProfile.objects.get(user_id=student_id, assigned_teacher=teacher_profile)
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
    students = StudentProfile.objects.filter(assigned_teacher=teacher_profile)
    
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
    queries = Query.objects.filter(response__isnull=True)

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
    """View queries that have been responded to (student view)."""
    student_profile = StudentProfile.objects.get(user=request.user)

    queries = Query.objects.filter(
        student=student_profile,
        response__isnull=False
    ).select_related('responded_by__user')

    query_data = []
    for query in queries:
        query_data.append({
            'id': query.id,
            'query_text': query.query_text,
            'query_image': query.query_image.url if query.query_image else None,
            'response': query.response,
            'teacher_name': query.responded_by.user.get_full_name() if query.responded_by else "N/A",
            'submitted_at': query.submitted_at,
        })

    return render(request, 'student/response_query.html', {'queries': query_data})


@login_required
def give_remarks(request):
    """Grade student answers and provide remarks/feedback."""
    teacher_profile = TeacherProfile.objects.get(user=request.user)

    if request.method == 'POST':
        answer_id = request.POST.get('answer_id')
        remark_text = request.POST.get('remark_text')
        answer_type = request.POST.get('answer_type')

        if answer_type == "student":
            answer = StudentAnswer.objects.get(id=answer_id)
        else:  # exam
            answer = ExamAnswer.objects.get(id=answer_id)

        answer.remarks = remark_text
        answer.save()

        return redirect('give_remarks')

    # Fetch unanswered Student Answers
    student_answers = StudentAnswer.objects.filter(
        question__teacher=teacher_profile,
        remarks__isnull=True
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
        exam__teacher=teacher_profile,
        remarks__isnull=True
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

    context = {
        'student_answers': student_list,
        'exam_answers': exam_list,
    }

    return render(request, 'teacher/remarks.html', context)


def lecture_notes(request):
    """Render lecture notes page."""
    return render(request, "student/lecture_notes.html")
