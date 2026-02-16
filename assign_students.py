
import os
import django
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from accounts.models import StudentProfile, TeacherProfile

def assign():
    teachers = TeacherProfile.objects.all()
    if not teachers.exists():
        print("Error: No teacher profile found.")
        return

    # Assign to first teacher (assuming single teacher context or main admin)
    teacher = teachers.first() 
    print(f"Assigning students to Teacher: {teacher.user.full_name} ({teacher.user.email})")

    students = StudentProfile.objects.filter(assigned_teacher__isnull=True)
    count = students.count()
    
    if count == 0:
        print("No unassigned students found.")
        return

    print(f"Found {count} unassigned students.")
    for s in students:
        s.assigned_teacher = teacher
        s.save()
        print(f"Assigned {s.user.email} -> {teacher.user.full_name}")

    print("Assignment complete.")

if __name__ == '__main__':
    assign()
