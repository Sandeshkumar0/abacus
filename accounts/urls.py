from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

urlpatterns = [
    path('student/login/', views.student_login, name='student_login'),
    path('student/signup/', views.student_signup, name='student_signup'),
    path("student/logout/", views.student_logout_view, name="student_logout"),
    path("teacher/logout/", views.teacher_logout_view, name="teacher_logout"),
    path("parent/logout/", views.parent_logout_view, name="parent_logout"),
    path('teacher/login/', views.teacher_login, name='teacher_login'),
    path('teacher/signup/', views.teacher_signup_view , name='teacher_signup'),
    path('parent/login/', views.parent_login, name='parent_login'),
    path('parent/signup/', views.parent_signup, name='parent_signup'),
    path("sections/manage/", views.section_management, name="section_management"),

    # Password reset (Forgot Password) flow
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            success_url=reverse_lazy('password_reset_done')
        ),
        name='password_reset'
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete')
        ),
        name='password_reset_confirm'
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
]
