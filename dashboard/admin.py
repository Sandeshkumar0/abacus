from django.contrib import admin
from .models import (
    Question, StudentAnswer, Query, Exam, ExamQuestion, ExamAnswer, 
    Notification, Course, CourseResource, Enrollment, Subject, Chapter
)

# Register your models here.

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'duration', 'teacher', 'created_at')
    search_fields = ('title', 'description')
    list_filter = ('teacher', 'created_at')

@admin.register(CourseResource)
class CourseResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'uploaded_at')
    list_filter = ('course', 'uploaded_at')

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at')
    list_filter = ('course', 'enrolled_at')
    search_fields = ('student__user__email', 'course__title')

# Simple registrations for others
admin.site.register(Question)
admin.site.register(StudentAnswer)
admin.site.register(Query)
admin.site.register(Exam)
admin.site.register(ExamQuestion)
admin.site.register(ExamAnswer)
admin.site.register(Notification)

# Subject and Chapter management
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'class_level', 'teacher', 'created_at')
    list_filter = ('teacher', 'class_level', 'created_at')
    search_fields = ('name', 'description')

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('name', 'chapter_number', 'subject', 'ncert_reference')
    list_filter = ('subject', 'subject__teacher')
    search_fields = ('name', 'description', 'ncert_reference')
