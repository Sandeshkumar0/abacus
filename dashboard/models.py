from django.db import models

from django.db import models
from accounts.models import StudentProfile, TeacherProfile, CustomUser

class Question(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='questions')
    teacher_name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='teacher_names')
    description = models.TextField()
    image = models.ImageField(upload_to='questions/', blank=True, null=True)
    max_marks = models.PositiveIntegerField(default=0)  # <-- New field
    due_date = models.DateTimeField()
    is_exam = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q by {self.teacher_name.get_full_name()} (Due {self.due_date.date()})"

class StudentAnswer(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    student_name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='student_names')
    student_roll = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='student_rolls')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True)
    answer_file = models.FileField(upload_to='answers/', blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Answer by {self.student_name.email} for Q-{self.question.id}"

class Query(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    student_name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='query_student_names')
    student_roll = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='query_student_rolls')
    query_text = models.TextField()
    query_image = models.ImageField(upload_to='queries/', blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    response = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Query by {self.student_name.email} ({self.student_roll.roll_number})"

class Exam(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name="exams")
    teacher_name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="exam_teachers")
    title = models.CharField(max_length=255)
    due_date = models.DateTimeField()
    total_marks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} (Due {self.due_date.date()})"
    
    def is_expired(self):
        """Check if the exam deadline has passed"""
        from django.utils import timezone
        return timezone.now() > self.due_date
    
    def get_status(self):
        """Get the current status of the exam"""
        return "Expired" if self.is_expired() else "Active"



class ExamQuestion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    latex = models.TextField(blank=True, null=True)
    marks = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to="exam_questions/", blank=True, null=True)

    def __str__(self):
        return f"Q{self.id} ({self.exam.title})"


class ExamAnswer(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name="answers")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="exam_answers")
    student_name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="exam_student_names")
    student_roll = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="exam_student_rolls")
    
    answer_text = models.TextField(blank=True)
    answer_file = models.FileField(upload_to="exam_answers/", blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    marks_obtained = models.IntegerField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Answer by {self.student_name.email} for {self.exam.title} Q{self.question.id}"


class Notification(models.Model):
    """Model for real-time notifications to students and teachers"""
    NOTIFICATION_TYPES = [
        ('test_assigned', 'Test Assigned'),
        ('exam_assigned', 'Exam Assigned'),
        ('answer_graded', 'Answer Graded'),
        ('query_responded', 'Query Responded'),
        ('general', 'General Notification'),
    ]
    
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, null=True)  # URL to redirect when clicked
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: Link to related objects
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} for {self.recipient.email} - {self.title}"
