from django.contrib import admin

from django.contrib import admin
from .models import Question, StudentAnswer, Query, Exam, ExamQuestion, ExamAnswer

admin.site.register(Question)
admin.site.register(StudentAnswer)
admin.site.register(Query)

admin.site.register(Exam)
admin.site.register(ExamQuestion)
admin.site.register(ExamAnswer)
