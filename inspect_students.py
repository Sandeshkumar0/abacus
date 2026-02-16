
import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from accounts.models import StudentProfile, TeacherProfile, CustomUser

def inspect_students():
    print("--- Students ---")
    students = StudentProfile.objects.all()
    if not students.exists():
        print("No students found in DB.")
        return

    for s in students:
        teacher = s.assigned_teacher
        teacher_name = teacher.user.full_name if teacher else "None"
        print(f"Student: {s.user.email} ({s.user.full_name}) - Assigned Teacher: {teacher_name}")

    print("\n--- Teachers ---")
    teachers = TeacherProfile.objects.all()
    for t in teachers:
        print(f"Teacher: {t.user.email} ({t.user.full_name})")

if __name__ == '__main__':
    inspect_students()
