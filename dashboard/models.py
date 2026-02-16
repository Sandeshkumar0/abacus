from django.db import models
from accounts.models import StudentProfile, TeacherProfile, CustomUser
from django.utils import timezone

class Question(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='questions')
    teacher_name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='teacher_names')
    description = models.TextField()
    image = models.ImageField(upload_to='questions/', blank=True, null=True)
    max_marks = models.PositiveIntegerField(default=0)  # <-- New field
    due_date = models.DateTimeField()
    is_exam = models.BooleanField(default=False)
    subject = models.ForeignKey('Subject', on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    chapter = models.ForeignKey('Chapter', on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
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
    marks_obtained = models.PositiveIntegerField(null=True, blank=True)
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
    subject = models.ForeignKey('Subject', on_delete=models.SET_NULL, null=True, blank=True, related_name='exams')
    chapter = models.ForeignKey('Chapter', on_delete=models.SET_NULL, null=True, blank=True, related_name='exams')
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

# --- NEW MODELS FOR COURSES ---

class Course(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    duration = models.CharField(max_length=50)
    image_url = models.CharField(max_length=500, blank=True, null=True) # Using URL for now as per template or static
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.title

class CourseResource(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='course_resources/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.course.title})"

class Enrollment(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'course')
    
    def __str__(self):
        return f"{self.student.user.email} enrolled in {self.course.title}"

class StudentGroup(models.Model):
    """Group of students created by a teacher (e.g. 'Class 5 Math', 'Advanced Group')"""
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='student_groups')
    students = models.ManyToManyField(StudentProfile, related_name='study_groups', blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.students.count()} students)"


# --- SUBJECT & CHAPTER MODELS (Teacher-Defined) ---

class Subject(models.Model):
    """Teacher-defined subjects (e.g., Mathematics, Science, English)"""
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    class_level = models.CharField(max_length=20, blank=True)  # e.g., "Class 5", "Class 10"
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['class_level', 'name']
        unique_together = ('teacher', 'name', 'class_level')
    
    def __str__(self):
        if self.class_level:
            return f"{self.name} ({self.class_level})"
        return self.name


class Chapter(models.Model):
    """Chapters within a subject with NCERT/resource references"""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='chapters')
    name = models.CharField(max_length=200)
    chapter_number = models.IntegerField(blank=True, null=True)
    ncert_reference = models.CharField(max_length=500, blank=True, help_text="NCERT chapter link or reference")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['chapter_number', 'name']
        unique_together = ('subject', 'name')
    
    def __str__(self):
        if self.chapter_number:
            return f"Ch {self.chapter_number}: {self.name}"
        return self.name
