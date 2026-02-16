"""
Teacher-related views for the dashboard app.
Handles teacher dashboard, question assignment, exam creation, student management, and grading.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from datetime import datetime
import json
import os
import tempfile
from dotenv import load_dotenv
from django.contrib import messages

from accounts.models import TeacherProfile, StudentProfile, CustomUser
from ..models import Question, StudentAnswer, Query, Exam, ExamQuestion, ExamAnswer, Course, CourseResource, StudentGroup, Subject, Chapter


@login_required(login_url='teacher_login')
def teacher_dashboard(request):
    """Main dashboard view for teachers."""
    if not request.user.is_authenticated:
        return redirect('teacher_login')
    if not request.user.is_teacher:
        return redirect('teacher_login')
    
    # Get teacher profile
    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'aadhar_id': 'Not Provided',
            'phone': 'Not Provided'
        }
    )
    
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

        teacher, _ = TeacherProfile.objects.get_or_create(user=request.user)
        exam = Exam.objects.create(
            teacher=teacher,
            teacher_name=request.user,
            title=exam_heading,
            due_date=parse_datetime(due_date),
            total_marks=total_marks,
            subject_id=request.POST.get("subject_id"),
            chapter_id=request.POST.get("chapter_id")
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
    
    return render(request, "teacher/take_test.html", {'exams': exams, 'subjects': subjects})


@csrf_exempt
@login_required
def create_exam(request):
    """Create a new exam with questions."""
    if request.method == "POST":
        exam_heading = request.POST.get("examHeading")
        due_date_str = request.POST.get("dueDate")
        total_marks = request.POST.get("totalMarks")

        due_date = make_aware(datetime.strptime(due_date_str, "%Y-%m-%d %H:%M"))

        teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
        teacher_user = request.user

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
            subject=subject,
            chapter=chapter
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
        
        # Handle Resources
        files = request.FILES.getlist('resources')
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
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return render(request, 'student/profile_missing.html', {
            'message': 'Your student profile is incomplete or you are logged in as a teacher.'
        })

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


@login_required(login_url='teacher_login')
def manage_groups(request):
    """View to list and manage student study groups."""
    teacher = TeacherProfile.objects.get(user=request.user)
    groups = StudentGroup.objects.filter(teacher=teacher)
    return render(request, 'teacher/manage_groups.html', {'groups': groups})

@login_required(login_url='teacher_login')
def create_group(request):
    """View to create a new student group based on class filter."""
    teacher = TeacherProfile.objects.get(user=request.user)
    
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
            students = StudentProfile.objects.filter(student_class__in=selected_classes)
            group.students.add(*students)
            messages.success(request, f"Group '{name}' created with {students.count()} students from selected classes.")
        else:
            messages.warning(request, f"Group '{name}' created but no students added (no class selected).")
            
        return redirect('manage_groups')
    
    # Get distinct classes for filter dropdown
    available_classes = StudentProfile.objects.values_list('student_class', flat=True).distinct()
    return render(request, 'teacher/create_group.html', {'available_classes': available_classes})


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
    students = StudentProfile.objects.filter(
        (Q(user__full_name__icontains=query) |
        Q(user__email__icontains=query) |
        Q(roll_number__icontains=query)) &
        Q(assigned_teacher=teacher_profile)
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
        Q(student__assigned_teacher=teacher_profile)
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

    if request.method == 'POST':
        # 1. Single Assignment Submission
        if request.POST.get('answer_id'):
            answer_id = request.POST.get('answer_id')
            remark_text = request.POST.get('remark_text')
            answer_type = request.POST.get('answer_type')
            marks = request.POST.get('marks')

            try:
                if answer_type == "student":
                    answer = StudentAnswer.objects.get(id=answer_id)
                else:
                    answer = ExamAnswer.objects.get(id=answer_id)

                if marks:
                    answer.marks_obtained = marks
                
                answer.remarks = remark_text
                answer.save()
            except (StudentAnswer.DoesNotExist, ExamAnswer.DoesNotExist):
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
                            answer = ExamAnswer.objects.get(id=ans_id)
                            if marks:
                                answer.marks_obtained = marks
                            if remark:
                                answer.remarks = remark
                            answer.save()
                    except (ExamAnswer.DoesNotExist, ValueError):
                        continue

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


# ==================== SUBJECT & CHAPTER MANAGEMENT ====================

@login_required
def manage_subjects(request):
    """View and manage teacher's subjects and chapters."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    subjects = Subject.objects.filter(teacher=teacher_profile).prefetch_related('chapters')
    
    context = {
        'subjects': subjects,
    }
    return render(request, 'teacher/manage_subjects.html', context)


@login_required
def create_subject(request):
    """Create a new subject."""
    if request.method == 'POST':
        teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
        name = request.POST.get('name')
        class_level = request.POST.get('class_level', '')
        description = request.POST.get('description', '')
        
        try:
            Subject.objects.create(
                teacher=teacher_profile,
                name=name,
                class_level=class_level,
                description=description
            )
            messages.success(request, f'Subject "{name}" created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating subject: {str(e)}')
        
        return redirect('manage_subjects')
    
    return render(request, 'teacher/create_subject.html')


@login_required
def edit_subject(request, subject_id):
    """Edit an existing subject."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    try:
        subject = Subject.objects.get(id=subject_id, teacher=teacher_profile)
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
            subject = Subject.objects.get(id=subject_id, teacher=teacher_profile)
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
            subject = Subject.objects.get(id=subject_id, teacher=teacher_profile)
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
    
    subjects = Subject.objects.filter(teacher=teacher_profile)
    context = {'subjects': subjects}
    return render(request, 'teacher/create_chapter.html', context)


@login_required
def edit_chapter(request, chapter_id):
    """Edit an existing chapter."""
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    try:
        chapter = Chapter.objects.get(id=chapter_id, subject__teacher=teacher_profile)
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
            chapter = Chapter.objects.get(id=chapter_id, subject__teacher=teacher_profile)
            chapter_name = chapter.name
            chapter.delete()
            messages.success(request, f'Chapter "{chapter_name}" deleted successfully!')
        except Chapter.DoesNotExist:
             messages.error(request, 'Chapter not found.')
             
        return redirect('manage_subjects')

    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
