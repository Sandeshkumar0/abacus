import os
import django
import sys
from datetime import date

# Setup Django environment
sys.path.append('/home/aarzoo/Downloads/abacusmaster')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from accounts.models import StudentProfile, TeacherProfile
from dashboard.models import Question, StudentAnswer, Query, Exam

User = get_user_model()

def setup_data():
    print("🚀 Starting Data Population...")

    # 1. Create Teacher
    teacher_email = "teacher@example.com"
    teacher_user, created = User.objects.get_or_create(
        email=teacher_email,
        defaults={
            'username': 'teacher',
            'full_name': 'Ms. Teacher',
            'is_staff': False,
            'is_superuser': False,
            'is_teacher': True,
            'is_student': False
        }
    )
    if created:
        teacher_user.set_password('password123')
        teacher_user.save()
        print(f"✅ Created Teacher User: {teacher_email}")
    else:
        print(f"ℹ️ Teacher User already exists: {teacher_email}")

    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=teacher_user,
        defaults={
            'phone': '1234567890',
            'designation': 'Senior Teacher'
        }
    )

    # 2. Create Student
    student_email = "student@example.com"
    student_user, created = User.objects.get_or_create(
        email=student_email,
        defaults={
            'username': 'student',
            'full_name': 'John Student',
            'is_staff': False,
            'is_superuser': False,
            'is_teacher': False,
            'is_student': True
        }
    )
    if created:
        student_user.set_password('password123')
        student_user.save()
        print(f"✅ Created Student User: {student_email} (Password: password123)")
    else:
        print(f"ℹ️ Student User already exists: {student_email}")

    student_profile, created = StudentProfile.objects.get_or_create(
        user=student_user,
        defaults={
            'roll_number': 'STU001',
            'student_class': '10',
            'dob': date(2005, 5, 20),
            'phone': '9876543210',
            'assigned_teacher': teacher_profile  # Assign the teacher!
        }
    )
    if student_profile.assigned_teacher != teacher_profile:
        student_profile.assigned_teacher = teacher_profile
        student_profile.save()
        print("✅ Assigned teacher to student")

    # 3. Create Questions (Assignments)
    if Question.objects.filter(teacher=teacher_profile).count() == 0:
        print("📝 Creating assignments...")
        q1 = Question.objects.create(
            teacher=teacher_profile,
            teacher_name=teacher_user,
            description="Math Assignment 1: Algebra Basics",
            max_marks=10,
            due_date=timezone.now() + timezone.timedelta(days=7),
            is_exam=False
        )
        print("✅ Created Assignment: Algebra Basics")
        
        q2 = Question.objects.create(
            teacher=teacher_profile,
            teacher_name=teacher_user,
            description="Science Project: Solar System",
            max_marks=20,
            due_date=timezone.now() + timezone.timedelta(days=14),
            is_exam=False
        )
        print("✅ Created Assignment: Solar System")

    # 4. Create an Exam
    if Exam.objects.count() == 0:
        print("📝 Creating exam...")
        exam = Exam.objects.create(
            title="Mid-Term Mathematics",
            description="All chapters covered so far",
            teacher=teacher_profile,
            start_time=timezone.now() + timezone.timedelta(days=1),
            duration=60,
            total_marks=50
        )
        print("✅ Created Exam: Mid-Term Mathematics")

    print("\n🎉 DONE! Data populated.")
    print(f"👉 Login as Student: {student_email} / password123")
    print(f"👉 Login as Teacher: {teacher_email} / password123")

if __name__ == '__main__':
    setup_data()
