"""
Script to populate sample data for testing the student dashboard.
This will add sample questions, answers, and queries to demonstrate the features.
"""

import os
import django
import sys

# Setup Django environment
sys.path.append('/home/aarzoo/Downloads/abacusmaster')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser, StudentProfile, TeacherProfile
from dashboard.models import Question, StudentAnswer, Query

def populate_sample_data():
    """Populate sample data for testing"""
    
    print("🔍 Checking existing data...")
    
    # Get all students
    students = StudentProfile.objects.all()
    if not students.exists():
        print("❌ No students found! Please create a student account first.")
        return
    
    # Get all teachers
    teachers = TeacherProfile.objects.all()
    if not teachers.exists():
        print("❌ No teachers found! Please create a teacher account first.")
        return
    
    student = students.first()
    teacher = teachers.first()
    
    print(f"✅ Found student: {student.user.email}")
    print(f"✅ Found teacher: {teacher.user.email}")
    
    # Update student profile with sample data if fields are empty
    if not student.user.full_name:
        student.user.full_name = "John Doe"
        student.user.save()
        print("✅ Updated student name")
    
    if not student.roll_number:
        student.roll_number = "STU001"
        student.save()
        print("✅ Updated roll number")
    
    if not student.student_class:
        student.student_class = "Grade 10"
        student.save()
        print("✅ Updated class")
    
    if not student.phone:
        student.phone = "+1234567890"
        student.save()
        print("✅ Updated phone")
    
    if not student.dob:
        from datetime import date
        student.dob = date(2005, 1, 15)
        student.save()
        print("✅ Updated DOB")
    
    # Assign teacher if not assigned
    if not student.assigned_teacher:
        student.assigned_teacher = teacher
        student.save()
        print("✅ Assigned teacher to student")
    
    # Create sample questions if none exist
    questions = Question.objects.filter(teacher=teacher)
    if questions.count() < 3:
        print("\n📝 Creating sample questions...")
        
        # Question 1
        q1 = Question.objects.create(
            teacher=teacher,
            teacher_name=teacher.user,
            description="Solve the quadratic equation: x² + 5x + 6 = 0",
            due_date=timezone.now() + timedelta(days=7),
            is_exam=False,
            max_marks=10
        )
        print(f"✅ Created Question #{q1.id}")
        
        # Question 2
        q2 = Question.objects.create(
            teacher=teacher,
            teacher_name=teacher.user,
            description="Explain Newton's First Law of Motion with examples.",
            due_date=timezone.now() + timedelta(days=5),
            is_exam=False,
            max_marks=15
        )
        print(f"✅ Created Question #{q2.id}")
        
        # Question 3
        q3 = Question.objects.create(
            teacher=teacher,
            teacher_name=teacher.user,
            description="Write an essay on the importance of renewable energy.\n\nLaTeX Equation:\nE = mc^2",
            due_date=timezone.now() + timedelta(days=10),
            is_exam=False,
            max_marks=20
        )
        print(f"✅ Created Question #{q3.id}")
    
    # Create sample answered question with remarks
    answered = StudentAnswer.objects.filter(student=student, remarks__isnull=False)
    if answered.count() < 2:
        print("\n✅ Creating sample graded answers...")
        
        # Get or create an answered question
        all_questions = Question.objects.filter(teacher=teacher)[:2]
        for q in all_questions:
            answer, created = StudentAnswer.objects.get_or_create(
                student=student,
                student_name=student.user,
                question=q,
                defaults={
                    'answer_text': 'This is a sample answer submitted by the student.',
                    'remarks': f'Good work! You got {q.max_marks - 2}/{q.max_marks} marks. Keep it up!'
                }
            )
            if created:
                print(f"✅ Created graded answer for Question #{q.id}")
            elif not answer.remarks:
                answer.remarks = f'Excellent! You got {q.max_marks - 1}/{q.max_marks} marks.'
                answer.save()
                print(f"✅ Added remarks to Question #{q.id}")
    
    # Create sample queries
    queries = Query.objects.filter(student=student)
    if queries.count() < 2:
        print("\n💬 Creating sample queries...")
        
        # Query 1 - Answered
        query1, created = Query.objects.get_or_create(
            student=student,
            student_name=student.user,
            student_roll=student,
            query_text="How do I solve quadratic equations using the quadratic formula?",
            defaults={
                'response': 'Use the formula: x = (-b ± √(b²-4ac)) / 2a. Identify a, b, c from your equation and substitute.',
                'responded_by': teacher
            }
        )
        if created:
            print("✅ Created answered query #1")
        
        # Query 2 - Answered
        query2, created = Query.objects.get_or_create(
            student=student,
            student_name=student.user,
            student_roll=student,
            query_text="Can you explain the difference between velocity and speed?",
            defaults={
                'response': 'Speed is scalar (magnitude only), velocity is vector (magnitude + direction). Example: 50 km/h is speed, 50 km/h North is velocity.',
                'responded_by': teacher
            }
        )
        if created:
            print("✅ Created answered query #2")
        
        # Query 3 - Pending
        query3, created = Query.objects.get_or_create(
            student=student,
            student_name=student.user,
            student_roll=student,
            query_text="What is the best way to prepare for the upcoming physics exam?",
            defaults={
                'response': None,
                'responded_by': None
            }
        )
        if created:
            print("✅ Created pending query #3")
    
    print("\n" + "="*50)
    print("🎉 SAMPLE DATA POPULATED SUCCESSFULLY!")
    print("="*50)
    print(f"\n📊 Summary:")
    print(f"   Student: {student.user.full_name} ({student.user.email})")
    print(f"   Roll No: {student.roll_number}")
    print(f"   Class: {student.student_class}")
    print(f"   Questions: {Question.objects.filter(teacher=teacher).count()}")
    print(f"   Graded Answers: {StudentAnswer.objects.filter(student=student, remarks__isnull=False).count()}")
    print(f"   Answered Queries: {Query.objects.filter(student=student, response__isnull=False).count()}")
    print(f"   Pending Queries: {Query.objects.filter(student=student, response__isnull=True).count()}")
    print("\n✅ Now refresh your browser to see the data!")
    print("="*50)

if __name__ == '__main__':
    populate_sample_data()
