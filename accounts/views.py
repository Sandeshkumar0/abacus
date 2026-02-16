from django.shortcuts import render

from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import StudentSignUpForm, TeacherSignUpForm

from django.shortcuts import render

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect

def student_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if user is not None and user.is_student:
            login(request, user)
            return redirect('student_dashboard')
        else:
            return render(request, 'student/student_login.html', {
                'error': 'Invalid credentials or not a student account.'
            })

    return render(request, 'student/student_login.html')

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import CustomUser, StudentProfile, TeacherProfile
from django.utils.dateparse import parse_date
import random


def student_signup(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        student_class = request.POST.get('student_class')
        dob = request.POST.get('dob')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect('student_signup')

        # ✅ Generate a unique 8-digit roll number
        def generate_unique_roll_number():
            while True:
                roll = str(random.randint(10000000, 99999999))
                if not StudentProfile.objects.filter(roll_number=roll).exists():
                    return roll

        roll_number = generate_unique_roll_number()

        # Create user using create_user method (proper password hashing)
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            full_name=name,
            is_student=True
        )

        # Assign to a dummy or first teacher
        assigned_teacher = TeacherProfile.objects.first()

        # ✅ Create student profile with generated roll number
        StudentProfile.objects.create(
            user=user,
            phone=phone,
            student_class=student_class,
            dob=parse_date(dob),
            roll_number=roll_number,  # ✅ Added
            assigned_teacher=assigned_teacher
        )

        messages.success(request, "Student registered successfully!")
        return redirect('student_login')

    return render(request, 'student/student_signup.html')


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.urls import reverse
from .models import CustomUser

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect

def teacher_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if user is not None and user.is_teacher:
            login(request, user)
            return redirect('teacher_dashboard')
        else:
            return render(request, 'teacher/teacher_login.html', {
                'error': 'Invalid credentials or not a teacher account.'
            })

    return render(request, 'teacher/teacher_login.html')

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import CustomUser, TeacherProfile
def teacher_signup_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        aadhaar = request.POST.get('aadhaar')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect('teacher_signup')

        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            is_teacher=True,
        )
        user.full_name = name
        user.save()

        TeacherProfile.objects.create(
            user=user,
            aadhar_id=aadhaar,
            phone=phone
        )

        messages.success(request, "Account created successfully!")
        return redirect('teacher_login')

    return render(request, 'teacher/teacher_signup.html')


from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

@login_required
def student_logout_view(request):
    if request.method == "POST":  # if user confirms logout
        logout(request)
        return redirect("portal-landing")   # redirect to your login page
    return render(request, "student/logout.html")  # show modal

@login_required
def teacher_logout_view(request):
    if request.method == "POST":  # if user confirms logout
        logout(request)
        return redirect("portal-landing")   # redirect to your login page
    return render(request, "teacher/logout.html")  # show modal