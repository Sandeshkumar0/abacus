from django.urls import path
from . import views

urlpatterns = [
    path('student/login/', views.student_login, name='student_login'),
    path('student/signup/', views.student_signup, name='student_signup'),
    path("student/logout/", views.student_logout_view, name="student_logout"),
    path("teacher/logout/", views.teacher_logout_view, name="teacher_logout"),
    path('teacher/login/', views.teacher_login, name='teacher_login'),
    path('teacher/signup/', views.teacher_signup_view , name='teacher_signup'),
]
# This code defines URL patterns for student and teacher signup views in a Django application.
# The `urlpatterns` list maps the URLs to their respective view functions, allowing users to access