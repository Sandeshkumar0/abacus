from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms

from .models import (
    CustomUser,
    ParentProfile,
    ParentStudentRelation,
    Section,
    StudentProfile,
    TeacherProfile,
    TeacherSectionAssignment,
)
from dashboard.models import Subject, SubjectTeacherAssignment


class TeacherSectionAssignmentAdminForm(forms.ModelForm):
    sections = forms.ModelMultipleChoiceField(
        queryset=Section.objects.all().order_by("class_level", "section"),
        required=False,
        help_text="Optional: pick multiple sections to assign this teacher as Subject Teacher in one step.",
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all().order_by("class_level", "name"),
        required=False,
        help_text="Optional: pick subject(s) to assign this teacher for selected section(s).",
    )

    class Meta:
        model = TeacherSectionAssignment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["section"].required = False

        # On edit, pre-fill the helper multi-select with current section.
        if self.instance and self.instance.pk and self.instance.section_id:
            self.initial.setdefault("sections", [self.instance.section_id])
            existing_subject_ids = SubjectTeacherAssignment.objects.filter(
                teacher=self.instance.teacher,
                section=self.instance.section,
            ).values_list("subject_id", flat=True)
            self.initial.setdefault("subjects", list(existing_subject_ids))

    def clean(self):
        cleaned_data = super().clean()
        section = cleaned_data.get("section")
        sections = cleaned_data.get("sections")
        teacher = cleaned_data.get("teacher")
        is_class_teacher = cleaned_data.get("is_class_teacher")

        selected_sections = list(sections or [])
        if section and section not in selected_sections:
            selected_sections.append(section)

        # At least one section must be selected (single or multiple helper).
        if not selected_sections:
            raise forms.ValidationError("Select at least one section.")

        # Multi-section mode is only for subject-teacher assignment.
        if len(selected_sections) > 1 and is_class_teacher:
            raise forms.ValidationError("For multiple sections, keep 'Is class teacher' unchecked.")

        # If helper sections selected and single section omitted, map first one for form validity.
        if not section and selected_sections:
            cleaned_data["section"] = selected_sections[0]
        cleaned_data["resolved_sections"] = selected_sections

        if not teacher:
            raise forms.ValidationError("Teacher is required.")

        return cleaned_data


class SectionAdminForm(forms.ModelForm):
    sections_bulk = forms.CharField(
        required=False,
        help_text="Optional: add multiple sections at once (e.g. A,B,C,D).",
    )

    class Meta:
        model = Section
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow bulk-only create without filling single `section` field.
        self.fields["section"].required = False

    def clean(self):
        cleaned_data = super().clean()
        section = (cleaned_data.get("section") or "").strip()
        sections_bulk = (cleaned_data.get("sections_bulk") or "").strip()

        if not section and not sections_bulk:
            raise forms.ValidationError("Enter one section or provide multiple sections in bulk field.")

        return cleaned_data


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "role", "is_student", "is_teacher", "is_staff")
    list_filter = ("role", "is_student", "is_teacher", "is_staff")
    ordering = ("email",)
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password", "full_name", "role", "is_student", "is_teacher")}),
        ("Permissions", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "role", "password1", "password2", "is_staff", "is_active")}),
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "office_location")
    search_fields = ("user__email", "user__full_name", "phone")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "roll_number", "student_class", "section", "assigned_teacher")
    search_fields = ("user__email", "user__full_name", "roll_number")
    list_filter = ("student_class", "section")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    form = SectionAdminForm
    list_display = ("class_level", "section", "class_teacher")
    search_fields = ("class_level", "section", "class_teacher__user__full_name")
    list_filter = ("class_level",)

    def save_model(self, request, obj, form, change):
        class_level = (form.cleaned_data.get("class_level") or "").strip()
        section_single = (form.cleaned_data.get("section") or "").strip()
        sections_bulk_raw = (form.cleaned_data.get("sections_bulk") or "").strip()
        class_teacher = form.cleaned_data.get("class_teacher")

        # Edit flow without bulk helper should behave normally.
        if change or not sections_bulk_raw:
            super().save_model(request, obj, form, change)
            return

        # Add flow with bulk sections: create/update all section rows in one step.
        section_tokens = [s.strip() for s in sections_bulk_raw.replace(";", ",").split(",") if s.strip()]
        if section_single:
            section_tokens.insert(0, section_single)

        # Preserve order while removing duplicates.
        seen = set()
        section_values = []
        for token in section_tokens:
            upper_token = token.upper()
            if upper_token not in seen:
                seen.add(upper_token)
                section_values.append(upper_token)

        if not section_values:
            super().save_model(request, obj, form, change)
            return

        first_obj, _ = Section.objects.update_or_create(
            class_level=class_level,
            section=section_values[0],
            defaults={"class_teacher": class_teacher},
        )
        obj.pk = first_obj.pk
        obj.class_level = first_obj.class_level
        obj.section = first_obj.section
        obj.class_teacher = first_obj.class_teacher
        obj._state.adding = False

        for sec in section_values[1:]:
            Section.objects.update_or_create(
                class_level=class_level,
                section=sec,
                defaults={"class_teacher": class_teacher},
            )


@admin.register(TeacherSectionAssignment)
class TeacherSectionAssignmentAdmin(admin.ModelAdmin):
    form = TeacherSectionAssignmentAdminForm
    list_display = ("teacher", "section", "is_class_teacher")
    list_filter = ("is_class_teacher", "section__class_level")
    search_fields = ("teacher__user__email", "teacher__user__full_name", "section__class_level", "section__section")

    def save_model(self, request, obj, form, change):
        sections = list(form.cleaned_data.get("resolved_sections") or form.cleaned_data.get("sections") or [])
        subjects = list(form.cleaned_data.get("subjects") or [])
        teacher = form.cleaned_data.get("teacher")

        target_sections = []

        # Multi-section helper: create/update subject-teacher assignments in bulk.
        if sections and len(sections) > 1:
            # Keep first assignment as the bound admin object for history/redirect.
            first_section = sections[0]
            first_obj, _ = TeacherSectionAssignment.objects.update_or_create(
                teacher=teacher,
                section=first_section,
                defaults={"is_class_teacher": False},
            )
            obj.pk = first_obj.pk
            obj.teacher = first_obj.teacher
            obj.section = first_obj.section
            obj.is_class_teacher = first_obj.is_class_teacher
            obj._state.adding = False
            target_sections = sections

            for section in sections[1:]:
                TeacherSectionAssignment.objects.update_or_create(
                    teacher=teacher,
                    section=section,
                    defaults={"is_class_teacher": False},
                )
        else:
            # Default single-assignment save.
            if sections and not obj.section_id:
                obj.section = sections[0]
            super().save_model(request, obj, form, change)
            if obj.section_id:
                target_sections = [obj.section]

        # Optional: assign selected subjects for the selected section(s).
        if subjects and teacher and target_sections:
            for section in target_sections:
                selected_subject_ids = [subj.id for subj in subjects]
                SubjectTeacherAssignment.objects.filter(
                    teacher=teacher,
                    section=section,
                ).exclude(subject_id__in=selected_subject_ids).delete()

                for subject in subjects:
                    SubjectTeacherAssignment.objects.get_or_create(
                        teacher=teacher,
                        section=section,
                        subject=subject,
                    )


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__email", "user__full_name", "phone")


@admin.register(ParentStudentRelation)
class ParentStudentRelationAdmin(admin.ModelAdmin):
    list_display = ("parent", "student", "relation")
    search_fields = ("parent__user__email", "student__user__email", "student__roll_number")
    list_filter = ("relation",)
