from django import forms
from .models import CustomUser, StudentProfile, TeacherProfile


class StudentSignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    name = forms.CharField(label="Full Name")
    phone = forms.CharField()
    student_class = forms.CharField()
    dob = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = CustomUser
        fields = ['email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_student = True
        user.first_name = self.cleaned_data['name']  # Store name in first_name
        if commit:
            user.save()
            StudentProfile.objects.create(
                user=user,
                roll_number="ROLL_TEMP",  # Replace if you capture roll in form
                phone=self.cleaned_data["phone"],
                student_class=self.cleaned_data["student_class"],
                dob=self.cleaned_data["dob"]
            )
        return user


class TeacherSignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    name = forms.CharField(label="Full Name")
    phone = forms.CharField()
    aadhar_id = forms.CharField()

    class Meta:
        model = CustomUser
        fields = ['email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_te_
