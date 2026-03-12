import random
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date
from django.utils import timezone

from .models import (
    CustomUser,
    ParentProfile,
    ParentStudentRelation,
    Section,
    StudentProfile,
    TeacherProfile,
    TeacherSectionAssignment,
)


def _get_default_teacher():
    """Cache the default teacher assignment to avoid repeated DB hits."""
    from django.core.cache import cache
    teacher = cache.get("_default_teacher_profile")
    if teacher is None:
        teacher = TeacherProfile.objects.first()
        if teacher:
            cache.set("_default_teacher_profile", teacher, timeout=300)
    return teacher


def _set_session_expiry(request, remember_me):
    """
    Keep existing behavior:
    - remember_me checked => persistent session
    - remember_me unchecked => session ends on browser close
    """
    if remember_me:
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    else:
        request.session.set_expiry(0)


def student_login(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        remember_me = request.POST.get("remember_me") == "on"

        matched_user = CustomUser.objects.filter(email__iexact=email).first()
        auth_email = matched_user.email if matched_user else email
        user = authenticate(request, email=auth_email, password=password)

        if user is not None and user.is_student:
            # Backfill legacy accounts created before role-based auth.
            if user.role != CustomUser.Role.STUDENT:
                user.role = CustomUser.Role.STUDENT
                user.save(update_fields=["role", "is_student", "is_teacher"])
            # Ensure student profile exists; some accounts may be created from admin only.
            if not StudentProfile.objects.filter(user=user).exists():
                roll = str(uuid.uuid4().int)[:8]
                StudentProfile.objects.create(
                    user=user,
                    phone="0000000000",
                    student_class="Unknown",
                    dob=timezone.now().date(),
                    roll_number=roll,
                    assigned_teacher=_get_default_teacher(),
                )
            login(request, user)
            _set_session_expiry(request, remember_me)
            return redirect("student_dashboard")

        return render(
            request,
            "student/student_login.html",
            {
                "error": "Invalid credentials or not a student account.",
                "remember_me": remember_me,
            },
        )

    return render(request, "student/student_login.html")


def student_signup(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        phone = (request.POST.get("phone") or "").strip()
        password = (request.POST.get("password") or "").strip()
        student_class = (request.POST.get("student_class") or "").strip()
        dob = (request.POST.get("dob") or "").strip()

        def generate_unique_roll_number():
            return str(uuid.uuid4().int)[:8]

        assigned_teacher = _get_default_teacher()
        parsed_dob = parse_date(dob)

        existing_user = CustomUser.objects.filter(email__iexact=email).first()
        if existing_user:
            if existing_user.is_teacher:
                messages.error(request, "This email is already registered as a teacher. Please use a different email for student signup.")
                return redirect("student_signup")

            if existing_user.is_student and StudentProfile.objects.filter(user=existing_user).exists():
                messages.error(request, "Student account already exists for this email. Please login.")
                return redirect("student_login")

            existing_user.full_name = name or existing_user.full_name
            existing_user.role = CustomUser.Role.STUDENT
            if password:
                existing_user.set_password(password)
            existing_user.save()

            student_profile, created = StudentProfile.objects.get_or_create(
                user=existing_user,
                defaults={
                    "phone": phone or "0000000000",
                    "student_class": student_class or "Unknown",
                    "dob": parsed_dob or timezone.now().date(),
                    "roll_number": generate_unique_roll_number(),
                    "assigned_teacher": assigned_teacher,
                },
            )
            if not created:
                # Preserve existing values; only update if new non-empty values are provided.
                if phone:
                    student_profile.phone = phone
                if student_class:
                    student_profile.student_class = student_class
                if parsed_dob:
                    student_profile.dob = parsed_dob
                if not student_profile.assigned_teacher:
                    student_profile.assigned_teacher = assigned_teacher
                student_profile.save()

            messages.success(request, "Student profile activated successfully! Please login.")
            return redirect("student_login")

        roll_number = generate_unique_roll_number()
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            full_name=name,
            role=CustomUser.Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=user,
            phone=phone or "0000000000",
            student_class=student_class or "Unknown",
            dob=parsed_dob or timezone.now().date(),
            roll_number=roll_number,
            assigned_teacher=assigned_teacher,
        )

        messages.success(request, "Student registered successfully!")
        return redirect("student_login")

    return render(request, "student/student_signup.html")


def teacher_login(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        remember_me = request.POST.get("remember_me") == "on"

        matched_user = CustomUser.objects.filter(email__iexact=email).first()
        auth_email = matched_user.email if matched_user else email
        user = authenticate(request, email=auth_email, password=password)

        if user is not None and user.is_teacher:
            # Backfill legacy accounts created before role-based auth.
            if user.role not in {CustomUser.Role.TEACHER, CustomUser.Role.CLASS_TEACHER}:
                user.role = CustomUser.Role.TEACHER
                user.save(update_fields=["role", "is_student", "is_teacher"])
            login(request, user)
            _set_session_expiry(request, remember_me)
            return redirect("teacher_dashboard")

        return render(
            request,
            "teacher/teacher_login.html",
            {
                "error": "Invalid credentials or not a teacher account.",
                "remember_me": remember_me,
            },
        )

    return render(request, "teacher/teacher_login.html")


def teacher_signup_view(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        phone = (request.POST.get("phone") or "").strip()
        password = (request.POST.get("password") or "").strip()
        aadhaar = (request.POST.get("aadhaar") or "").strip()

        if CustomUser.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("teacher_signup")

        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            role=CustomUser.Role.TEACHER,
        )
        user.full_name = name
        user.save()

        TeacherProfile.objects.create(
            user=user,
            aadhar_id=aadhaar,
            phone=phone,
        )

        messages.success(request, "Account created successfully!")
        return redirect("teacher_login")

    return render(request, "teacher/teacher_signup.html")


def parent_login(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        remember_me = request.POST.get("remember_me") == "on"

        matched_user = CustomUser.objects.filter(email__iexact=email).first()
        auth_email = matched_user.email if matched_user else email
        user = authenticate(request, email=auth_email, password=password)

        if user is not None and user.role == CustomUser.Role.PARENT:
            login(request, user)
            _set_session_expiry(request, remember_me)
            return redirect("parent_dashboard")

        return render(
            request,
            "parent/parent_login.html",
            {
                "error": "Invalid credentials or not a parent account.",
                "remember_me": remember_me,
            },
        )

    return render(request, "parent/parent_login.html")


def parent_signup(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        phone = (request.POST.get("phone") or "").strip()
        password = (request.POST.get("password") or "").strip()
        child_email = (request.POST.get("child_student_email") or "").strip().lower()
        relation = (request.POST.get("relation") or "Parent").strip()

        if CustomUser.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("parent_signup")

        if not child_email:
            messages.error(request, "Student email is required to link parent account.")
            return redirect("parent_signup")

        child = StudentProfile.objects.filter(user__email__iexact=child_email).first()
        if not child:
            messages.error(request, "Student email not found. Please enter the registered student email.")
            return redirect("parent_signup")

        with transaction.atomic():
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                full_name=name,
                role=CustomUser.Role.PARENT,
            )
            parent_profile = ParentProfile.objects.create(user=user, phone=phone)
            ParentStudentRelation.objects.get_or_create(
                parent=parent_profile,
                student=child,
                defaults={"relation": relation or "Parent"},
            )

        messages.success(request, "Parent account created and student linked successfully.")

        return redirect("parent_login")

    return render(request, "parent/parent_signup.html")


@login_required
def student_logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("portal-landing")
    return render(request, "student/logout.html")


@login_required
def teacher_logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("portal-landing")
    return render(request, "teacher/logout.html")


@login_required
def parent_logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("portal-landing")
    return render(request, "parent/logout.html")


def _can_manage_sections(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.role in {CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}


@login_required
def section_management(request):
    if not _can_manage_sections(request.user):
        messages.error(request, "You do not have permission to manage sections.")
        return redirect("portal-landing")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "create_section":
            class_level = (request.POST.get("class_level") or "").strip()
            section_name = (request.POST.get("section_name") or "").strip().upper()
            if class_level and section_name:
                section, created = Section.objects.get_or_create(
                    class_level=class_level,
                    section=section_name,
                )
                if created:
                    messages.success(request, f"Section {section} created.")
                else:
                    messages.info(request, f"Section {section} already exists.")
            else:
                messages.error(request, "Class level and section are required.")

        elif action == "assign_teacher":
            teacher_id = request.POST.get("teacher_id")
            section_id = request.POST.get("section_id")
            assignment_kind = request.POST.get("assignment_kind")
            teacher = TeacherProfile.objects.filter(pk=teacher_id).first()
            section = Section.objects.filter(pk=section_id).first()

            if not teacher or not section:
                messages.error(request, "Invalid teacher or section.")
            else:
                is_class_teacher = assignment_kind == "class_teacher"
                TeacherSectionAssignment.objects.update_or_create(
                    teacher=teacher,
                    section=section,
                    defaults={"is_class_teacher": is_class_teacher},
                )
                if is_class_teacher:
                    section.class_teacher = teacher
                    section.save(update_fields=["class_teacher"])
                    teacher.user.role = CustomUser.Role.CLASS_TEACHER
                    teacher.user.save(update_fields=["role", "is_student", "is_teacher"])
                    messages.success(
                        request,
                        f"{teacher.user.get_full_name()} assigned as class teacher for {section}.",
                    )
                else:
                    messages.success(
                        request,
                        f"{teacher.user.get_full_name()} assigned as subject teacher for {section}.",
                    )

        elif action == "assign_teacher_multi_subject":
            teacher_id = request.POST.get("teacher_id")
            section_ids = request.POST.getlist("section_ids")
            teacher = TeacherProfile.objects.filter(pk=teacher_id).first()

            if not teacher:
                messages.error(request, "Invalid teacher.")
            elif not section_ids:
                messages.error(request, "Select at least one section.")
            else:
                assigned_count = 0
                already_class_teacher_count = 0
                for sid in section_ids:
                    section = Section.objects.filter(pk=sid).first()
                    if not section:
                        continue

                    assignment = TeacherSectionAssignment.objects.filter(
                        teacher=teacher,
                        section=section,
                    ).first()
                    if assignment:
                        if assignment.is_class_teacher:
                            already_class_teacher_count += 1
                        # already assigned as subject teacher; no-op
                        continue

                    TeacherSectionAssignment.objects.create(
                        teacher=teacher,
                        section=section,
                        is_class_teacher=False,
                    )
                    assigned_count += 1

                if assigned_count:
                    messages.success(
                        request,
                        f"{teacher.user.get_full_name()} assigned as subject teacher to {assigned_count} section(s).",
                    )
                if already_class_teacher_count:
                    messages.info(
                        request,
                        f"Skipped {already_class_teacher_count} section(s) where this teacher is already class teacher.",
                    )

        elif action == "assign_student":
            student_id = request.POST.get("student_id")
            section_id = request.POST.get("section_id")
            student = StudentProfile.objects.filter(pk=student_id).first()
            section = Section.objects.filter(pk=section_id).first()

            if not student or not section:
                messages.error(request, "Invalid student or section.")
            else:
                student.section = section
                student.student_class = section.class_level
                student.save(update_fields=["section", "student_class"])
                messages.success(
                    request,
                    f"{student.user.get_full_name()} assigned to section {section}.",
                )

        return redirect("section_management")

    sections = (
        Section.objects.select_related("class_teacher__user")
        .prefetch_related("students__user", "teacher_assignments__teacher__user")
        .all()
    )
    teachers = TeacherProfile.objects.select_related("user").order_by("user__full_name")
    students = StudentProfile.objects.select_related("user").order_by("user__full_name")

    section_rows = []
    for section in sections:
        subject_teacher_names = sorted(
            {
                assignment.teacher.user.get_full_name()
                for assignment in section.teacher_assignments.all()
                if assignment.teacher_id and not assignment.is_class_teacher
            }
        )
        section_rows.append(
            {
                "section": section,
                "class_teacher": (
                    section.class_teacher.user.get_full_name()
                    if section.class_teacher_id
                    else "-"
                ),
                "subject_teachers": subject_teacher_names,
                "students": [s.user.get_full_name() for s in section.students.all()],
            }
        )

    context = {
        "sections": sections,
        "teachers": teachers,
        "students": students,
        "section_rows": section_rows,
    }
    return render(request, "admin/section_management.html", context)
