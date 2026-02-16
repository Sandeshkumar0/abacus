
import os
import django
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from accounts.models import StudentProfile, TeacherProfile

print(f"Total Students: {StudentProfile.objects.count()}")
print(f"Total Teachers: {TeacherProfile.objects.count()}")

print("\n--- Students ---")
for s in StudentProfile.objects.all():
    t_name = s.assigned_teacher.user.full_name if s.assigned_teacher else "None"
    print(f"Student: {s.user.email} (Roll: {s.roll_number}) -> Teacher: {t_name}")
