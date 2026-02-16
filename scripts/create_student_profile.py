#!/usr/bin/env python
"""
Quick script to create a student profile for a user
Run with: python manage.py shell < create_student_profile.py
"""

from accounts.models import CustomUser, StudentProfile, TeacherProfile
from datetime import date

# Get all users who are students but don't have profiles
users = CustomUser.objects.filter(is_student=True)

for user in users:
    if not hasattr(user, 'studentprofile'):
        print(f"Creating profile for student: {user.email}")
        
        # Get a teacher to assign (or None)
        teacher = TeacherProfile.objects.first()
        
        StudentProfile.objects.create(
            user=user,
            roll_number=f"STU{user.id:04d}",
            student_class="10",
            dob=date(2005, 1, 1),
            phone="0000000000",
            assigned_teacher=teacher
        )
        print(f"✅ Created profile for {user.email}")
    else:
        print(f"✓ Profile already exists for {user.email}")

print("\n📊 Summary:")
print(f"Total students: {CustomUser.objects.filter(is_student=True).count()}")
print(f"With profiles: {StudentProfile.objects.count()}")
