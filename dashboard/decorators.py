from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect

from accounts.models import CustomUser, StudentProfile

from .access_control import can_access_student


def role_required(*allowed_roles, login_url="student_login"):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(login_url)
            if request.user.role not in set(allowed_roles):
                return redirect(login_url)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def teacher_required_json(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        if request.user.role not in {CustomUser.Role.TEACHER, CustomUser.Role.CLASS_TEACHER}:
            return JsonResponse({"error": "Teacher access required."}, status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


def student_required_json(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        if request.user.role != CustomUser.Role.STUDENT:
            return JsonResponse({"error": "Student access required."}, status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


def student_access_required_json(student_kwarg="student_id"):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            student_id = kwargs.get(student_kwarg)
            if not student_id:
                return JsonResponse({"error": "Student id is required."}, status=400)
            student = StudentProfile.objects.filter(user_id=student_id).first()
            if not student:
                return JsonResponse({"error": "Student not found."}, status=404)
            if not can_access_student(request.user, student):
                return JsonResponse({"error": "Access denied for this student."}, status=403)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
