import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from accounts.models import TeacherProfile, StudentProfile, CustomUser

def inspect_data():
    with open('debug_output.txt', 'w') as f:
        f.write("--- Teachers ---\n")
        teachers = TeacherProfile.objects.all()
        for t in teachers:
            f.write(f"Teacher: {t.user.email} (ID: {t.user.id}, Profile ID: {t.pk})\n")

        f.write("\n--- Students ---\n")
        students = StudentProfile.objects.all()
        for s in students:
            assigned = s.assigned_teacher
            assigned_str = f"{assigned.user.email} (ID: {assigned.pk})" if assigned else "None"
            f.write(f"Student: {s.user.email} (ID: {s.user.id}) -> Assigned To: {assigned_str}\n")

        f.write("\n--- Summary ---\n")
        f.write(f"Total Teachers: {teachers.count()}\n")
        f.write(f"Total Students: {students.count()}\n")
    print("Debug output written to debug_output.txt")

if __name__ == "__main__":
    inspect_data()
