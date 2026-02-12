from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

# Manager to create users and superusers
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

# Your actual user model
class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100)  # ✅ Add this
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_full_name(self):  # ✅ Needed by __str__ of related models
        return self.full_name

    def __str__(self):
        return self.email


class TeacherProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    aadhar_id = models.CharField(max_length=20)
    phone = models.CharField(max_length=15)
    profile_picture = models.ImageField(upload_to='teacher_profiles/', null=True, blank=True)
    office_location = models.CharField(max_length=200, blank=True, default='')
    office_hours = models.CharField(max_length=200, blank=True, default='')

    def __str__(self):
        return self.user.get_full_name()

class StudentProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    roll_number = models.CharField(max_length=20)
    student_class = models.CharField(max_length=10)
    dob = models.DateField()
    phone = models.CharField(max_length=15)
    assigned_teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True)
    profile_picture = models.ImageField(upload_to='student_profiles/', null=True, blank=True)

    def __str__(self):
        if self.roll_number:
            return f"{self.user.get_full_name()} ({self.roll_number})"
        return self.user.get_full_name()
