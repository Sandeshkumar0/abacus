
import os
import django
import sys

# Setup Django environment
sys.path.append('/home/aarzoo/Downloads/abacusmaster')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from accounts.models import StudentProfile, TeacherProfile, CustomUser

def assign_students():
    print("🚀 Assigning students to a teacher...")
    
    # 1. Find the target teacher (You!)
    # Try to find 'sandeshkr07@gmail.com' or the first teacher available
    target_email = 'sandeshkr07@gmail.com'
    try:
        user = CustomUser.objects.get(email=target_email)
        teacher_profile, created = TeacherProfile.objects.get_or_create(user=user)
        print(f"✅ Found target teacher: {target_email}")
    except CustomUser.DoesNotExist:
        print(f"⚠️ User {target_email} not found. Using the first available teacher.")
        teacher_profile = TeacherProfile.objects.first()
        if not teacher_profile:
            print("❌ No teachers found in database! Creating one...")
            user = CustomUser.objects.create_user(email='teacher@example.com', password='password123', is_teacher=True)
            teacher_profile = TeacherProfile.objects.create(user=user)
    
    if not teacher_profile:
        print("❌ Failed to find or create a teacher profile.")
        return

    # 2. Get all students
    students = StudentProfile.objects.all()
    count = 0
    for student in students:
        if student.assigned_teacher != teacher_profile:
            student.assigned_teacher = teacher_profile
            student.save()
            print(f"👉 Assigned student '{student.user.email}' to {teacher_profile.user.email}")
            count += 1
        else:
            print(f"✓ Student '{student.user.email}' is already assigned correctly.")
            
    print(f"\n🎉 DONE! Assigned {count} students to {teacher_profile.user.email}.")
    print("Now refresh your Teacher Dashboard to see them!")

if __name__ == '__main__':
    assign_students()
