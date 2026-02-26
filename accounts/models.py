from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        role = extra_fields.get("role")
        if not role:
            if extra_fields.get("is_student"):
                extra_fields["role"] = CustomUser.Role.STUDENT
            elif extra_fields.get("is_teacher"):
                extra_fields["role"] = CustomUser.Role.TEACHER
            else:
                extra_fields["role"] = CustomUser.Role.STUDENT

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", CustomUser.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        PRINCIPAL = "principal", "Principal / Head"
        TEACHER = "teacher", "Teacher"
        CLASS_TEACHER = "class_teacher", "Class Teacher"
        STUDENT = "student", "Student"
        PARENT = "parent", "Parent"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
    )
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        self.is_student = self.role == self.Role.STUDENT
        self.is_teacher = self.role in {self.Role.TEACHER, self.Role.CLASS_TEACHER}
        super().save(*args, **kwargs)

    def has_role(self, *roles):
        return self.role in set(roles)

    def get_full_name(self):
        return self.full_name

    def __str__(self):
        return self.email


class TeacherProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    aadhar_id = models.CharField(max_length=20)
    phone = models.CharField(max_length=15)
    profile_picture = models.ImageField(upload_to="teacher_profiles/", null=True, blank=True)
    office_location = models.CharField(max_length=200, blank=True, default="")
    office_hours = models.CharField(max_length=200, blank=True, default="")

    def __str__(self):
        return self.user.get_full_name()


class Section(models.Model):
    class_level = models.CharField(max_length=10, help_text="e.g. 5")
    section = models.CharField(max_length=10, help_text="e.g. A")
    class_teacher = models.ForeignKey(
        "TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeroom_sections",
    )

    class Meta:
        unique_together = ("class_level", "section")
        ordering = ["class_level", "section"]

    def __str__(self):
        return f"{self.class_level}{self.section}"


class StudentProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    roll_number = models.CharField(max_length=20)
    student_class = models.CharField(max_length=10)
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    dob = models.DateField()
    phone = models.CharField(max_length=15)
    assigned_teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    profile_picture = models.ImageField(upload_to="student_profiles/", null=True, blank=True)

    def __str__(self):
        if self.roll_number:
            return f"{self.user.get_full_name()} ({self.roll_number})"
        return self.user.get_full_name()


class TeacherSectionAssignment(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name="section_assignments",
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
    )
    is_class_teacher = models.BooleanField(default=False)

    class Meta:
        unique_together = ("teacher", "section")

    def __str__(self):
        role = "Class Teacher" if self.is_class_teacher else "Teacher"
        return f"{self.teacher.user.email} -> {self.section} ({role})"


class ParentProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="parent_profile",
    )
    phone = models.CharField(max_length=15, blank=True, default="")

    def __str__(self):
        return self.user.get_full_name() or self.user.email


class ParentStudentRelation(models.Model):
    parent = models.ForeignKey(
        ParentProfile,
        on_delete=models.CASCADE,
        related_name="children_links",
    )
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="parent_links",
    )
    relation = models.CharField(max_length=30, blank=True, default="Parent")

    class Meta:
        unique_together = ("parent", "student")

    def __str__(self):
        return f"{self.parent.user.email} -> {self.student.user.email}"
