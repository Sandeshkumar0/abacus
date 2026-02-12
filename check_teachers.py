#!/usr/bin/env python
"""Quick script to check teacher accounts"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from accounts.models import CustomUser, TeacherProfile

print("=" * 60)
print("TEACHER ACCOUNTS IN DATABASE")
print("=" * 60)

teachers = CustomUser.objects.filter(is_teacher=True)

if not teachers:
    print("❌ No teacher accounts found!")
    print("\nYou need to create a teacher account first.")
else:
    for idx, teacher in enumerate(teachers, 1):
        print(f"\n{idx}. Email: {teacher.email}")
        print(f"   Full Name: {teacher.full_name}")
        print(f"   Is Active: {teacher.is_active}")
        print(f"   Is Teacher: {teacher.is_teacher}")
        
        try:
            profile = TeacherProfile.objects.get(user=teacher)
            print(f"   Has Profile: ✅ Yes")
            print(f"   Phone: {profile.phone}")
            print(f"   Aadhar: {profile.aadhar_id}")
        except TeacherProfile.DoesNotExist:
            print(f"   Has Profile: ❌ No")

print("\n" + "=" * 60)
print("NOTE: You changed the password in admin to '1234'")
print("Try logging in with:")
print("  Email: (one of the emails above)")
print("  Password: 1234")
print("=" * 60)
