from django.contrib import admin
from django import forms
from datetime import datetime
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from accounts.models import Section, TeacherProfile, CustomUser, StudentProfile
from .models import (
    Question, StudentAnswer, Query, Exam, ExamQuestion, ExamAnswer, 
    Notification, Course, CourseResource, Enrollment, Subject, Chapter,
    GroupCompetition, SubjectTeacherAssignment, SubjectResource,
    Testimonial, TeacherNote, TeacherClassMessage, AttendanceRecord,
    SubjectIntroCache, TopicLearningCache, Holiday, StudentSubjectPerformance,
    TimetableEntry, Announcement, AnnouncementRead, SchoolExamResult
)

# Register your models here.


class SubjectAdminForm(forms.ModelForm):
    section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("class_level", "section"),
        required=False,
        help_text="Optional: assign this subject to a specific section in one step.",
    )
    class_levels_bulk = forms.CharField(
        required=False,
        help_text="Optional: add same subject to multiple classes at once (e.g. 1,2).",
    )

    class Meta:
        model = Subject
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Admin can create class-wide subjects without manually choosing teacher.
        self.fields["teacher"].required = False

    def clean(self):
        cleaned_data = super().clean()
        class_level = (cleaned_data.get("class_level") or "").strip()
        class_levels_bulk = (cleaned_data.get("class_levels_bulk") or "").strip()
        section = cleaned_data.get("section")

        if not class_level and not class_levels_bulk:
            raise forms.ValidationError("Enter Class level or use Class levels bulk.")

        if class_levels_bulk and section:
            raise forms.ValidationError("Use either Section or Class levels bulk (not both).")

        return cleaned_data


class AnnouncementAdminForm(forms.ModelForm):
    target_section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("class_level", "section"),
        required=False,
        empty_label="All Classes",
        help_text="Select a section, or choose All Classes to send to everyone.",
    )

    class Meta:
        model = Announcement
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        expires_at = cleaned_data.get("expires_at")
        if expires_at and expires_at <= timezone.now():
            raise forms.ValidationError("Expires at must be a future date/time.")
        return cleaned_data


class TimetableEntryAdminForm(forms.ModelForm):
    day_periods_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text=(
            "Optional bulk add for one day. One line format: "
            "Period 1 | English | 08:30 | 09:10 | teacher@email.com (teacher optional)"
        ),
    )

    class Meta:
        model = TimetableEntry
        fields = "__all__"

    DAY_CHOICES = [
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["day_of_week"].widget = forms.Select(choices=self.DAY_CHOICES)
        self.fields["day_of_week"].help_text = "Select day name."
        # Allow bulk mode without forcing single-row required fields.
        self.fields["subject"].required = False
        self.fields["period_label"].required = False
        self.fields["start_time"].required = False
        self.fields["end_time"].required = False

    def _parse_time(self, value, line_no):
        token = (value or "").strip()
        for fmt in ("%H:%M", "%I:%M %p"):
            try:
                return datetime.strptime(token, fmt).time()
            except ValueError:
                continue
        raise forms.ValidationError(
            f"Line {line_no}: invalid time '{token}'. Use HH:MM (24h) or HH:MM AM/PM."
        )

    def _resolve_subject(self, section, subject_name, line_no):
        query = Subject.objects.filter(name__iexact=subject_name.strip())
        if section and section.class_level:
            class_level = str(section.class_level).strip()
            query = query.filter(
                Q(class_level=class_level) | Q(class_level=f"Class {class_level}")
            )
        subject = query.first()
        if not subject:
            raise forms.ValidationError(
                f"Line {line_no}: subject '{subject_name}' not found for class {section.class_level if section else '-'}."
            )
        return subject

    def _resolve_teacher(self, teacher_token, line_no):
        token = (teacher_token or "").strip()
        if not token:
            return None
        teacher = TeacherProfile.objects.filter(
            Q(user__email__iexact=token) | Q(user__full_name__iexact=token)
        ).first()
        if not teacher:
            raise forms.ValidationError(
                f"Line {line_no}: teacher '{token}' not found (use exact email or full name)."
            )
        return teacher

    def clean(self):
        cleaned_data = super().clean()
        day_periods_text = (cleaned_data.get("day_periods_text") or "").strip()
        section = cleaned_data.get("section")
        day_of_week = cleaned_data.get("day_of_week")

        if day_periods_text:
            if not section:
                raise forms.ValidationError("Section is required for bulk timetable add.")
            if not day_of_week:
                raise forms.ValidationError("Day of week is required for bulk timetable add.")

            parsed_rows = []
            for idx, raw_line in enumerate(day_periods_text.splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                parts = [part.strip() for part in line.split("|")]
                if len(parts) < 4:
                    raise forms.ValidationError(
                        f"Line {idx}: expected at least 4 parts -> Period | Subject | Start | End"
                    )

                period_label = parts[0]
                subject = self._resolve_subject(section, parts[1], idx)
                start_time = self._parse_time(parts[2], idx)
                end_time = self._parse_time(parts[3], idx)
                teacher = self._resolve_teacher(parts[4], idx) if len(parts) >= 5 else None

                if end_time <= start_time:
                    raise forms.ValidationError(
                        f"Line {idx}: end time must be after start time."
                    )

                parsed_rows.append(
                    {
                        "period_label": period_label,
                        "subject": subject,
                        "start_time": start_time,
                        "end_time": end_time,
                        "teacher": teacher,
                    }
                )

            if not parsed_rows:
                raise forms.ValidationError("Bulk text is empty. Add at least one valid line.")
            cleaned_data["parsed_rows"] = parsed_rows
            return cleaned_data

        # Single-row mode validation
        required_fields = ("section", "day_of_week", "subject", "period_label", "start_time", "end_time")
        missing = [f for f in required_fields if not cleaned_data.get(f)]
        if missing:
            raise forms.ValidationError("For single entry, section/day/subject/period/start/end are required.")

        if cleaned_data.get("end_time") <= cleaned_data.get("start_time"):
            raise forms.ValidationError("End time must be after start time.")
        return cleaned_data


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
admin.site.register(GroupCompetition)
admin.site.register(TeacherNote)
admin.site.register(TeacherClassMessage)
admin.site.register(SubjectIntroCache)
admin.site.register(TopicLearningCache)
admin.site.register(StudentSubjectPerformance)
admin.site.register(AnnouncementRead)
admin.site.register(SchoolExamResult)

# Subject and Chapter management
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    form = SubjectAdminForm
    list_display = ('name', 'class_level', 'teacher', 'created_at')
    list_filter = ('teacher', 'class_level', 'created_at')
    search_fields = ('name', 'description')

    def save_model(self, request, obj, form, change):
        section = form.cleaned_data.get("section")
        class_levels_bulk = (form.cleaned_data.get("class_levels_bulk") or "").strip()
        teacher = form.cleaned_data.get("teacher")
        if not teacher:
            teacher, _ = TeacherProfile.objects.get_or_create(
                user=request.user,
                defaults={"aadhar_id": "Not Provided", "phone": "Not Provided"},
            )
            obj.teacher = teacher
        if section and not (obj.class_level or "").strip():
            obj.class_level = section.class_level

        # Bulk class mode: create same subject across multiple class levels in one save.
        if not change and class_levels_bulk:
            class_tokens = [
                token.strip() for token in class_levels_bulk.replace(";", ",").split(",") if token.strip()
            ]
            seen = set()
            class_levels = []
            for token in class_tokens:
                if token not in seen:
                    seen.add(token)
                    class_levels.append(token)

            if not class_levels:
                super().save_model(request, obj, form, change)
                return

            first_obj = None
            for cls in class_levels:
                created_obj, _ = Subject.objects.get_or_create(
                    teacher=obj.teacher,
                    name=obj.name,
                    class_level=cls,
                    defaults={"description": obj.description},
                )
                if not first_obj:
                    first_obj = created_obj

            if first_obj:
                obj.pk = first_obj.pk
                obj.teacher = first_obj.teacher
                obj.name = first_obj.name
                obj.class_level = first_obj.class_level
                obj.description = first_obj.description
                obj._state.adding = False
            return

        super().save_model(request, obj, form, change)

        if section and obj.teacher_id:
            SubjectTeacherAssignment.objects.get_or_create(
                teacher=obj.teacher,
                subject=obj,
                section=section,
            )


@admin.register(SubjectTeacherAssignment)
class SubjectTeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ("teacher", "subject", "section")
    list_filter = ("section__class_level", "subject")
    search_fields = ("teacher__user__email", "subject__name", "section__class_level", "section__section")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("date", "student", "student_section", "teacher", "status", "remarks")
    list_filter = ("date", "status", "student__section__class_level", "student__section", "teacher")
    search_fields = (
        "student__user__email",
        "student__user__full_name",
        "student__roll_number",
        "student__section__class_level",
        "student__section__section",
        "teacher__user__email",
        "teacher__user__full_name",
    )
    date_hierarchy = "date"
    list_select_related = ("student__user", "student__section", "teacher__user")
    ordering = ("-date", "student__section__class_level", "student__section__section", "student__roll_number")

    @admin.display(description="Section")
    def student_section(self, obj):
        return obj.student.section if obj.student_id and obj.student.section_id else "-"


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    form = TimetableEntryAdminForm
    list_display = (
        "section",
        "day_name",
        "period_label",
        "start_time",
        "end_time",
        "subject",
        "teacher",
    )
    list_filter = ("section__class_level", "section", "day_of_week", "subject", "teacher")
    search_fields = (
        "section__class_level",
        "section__section",
        "period_label",
        "subject__name",
        "teacher__user__full_name",
        "teacher__user__email",
    )
    list_select_related = ("section", "subject", "teacher__user")
    ordering = ("section__class_level", "section__section", "day_of_week", "start_time")

    @admin.display(description="Day")
    def day_name(self, obj):
        labels = {
            1: "Monday",
            2: "Tuesday",
            3: "Wednesday",
            4: "Thursday",
            5: "Friday",
            6: "Saturday",
            7: "Sunday",
        }
        return labels.get(obj.day_of_week, str(obj.day_of_week))

    def save_model(self, request, obj, form, change):
        day_periods_text = (form.cleaned_data.get("day_periods_text") or "").strip()
        if not day_periods_text:
            super().save_model(request, obj, form, change)
            return

        section = form.cleaned_data["section"]
        day_of_week = int(form.cleaned_data["day_of_week"])
        default_teacher = form.cleaned_data.get("teacher")
        parsed_rows = form.cleaned_data.get("parsed_rows", [])

        created = 0
        updated = 0
        first_obj = None
        for row in parsed_rows:
            entry, was_created = TimetableEntry.objects.update_or_create(
                section=section,
                day_of_week=day_of_week,
                period_label=row["period_label"],
                defaults={
                    "subject": row["subject"],
                    "teacher": row.get("teacher") or default_teacher,
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
            if not first_obj:
                first_obj = entry

        if first_obj:
            obj.pk = first_obj.pk
            obj.section = first_obj.section
            obj.day_of_week = first_obj.day_of_week
            obj.period_label = first_obj.period_label
            obj.subject = first_obj.subject
            obj.teacher = first_obj.teacher
            obj.start_time = first_obj.start_time
            obj.end_time = first_obj.end_time
            obj._state.adding = False

        self.message_user(
            request,
            f"Timetable saved for {section} ({self.day_name(first_obj)}): {created} created, {updated} updated.",
        )

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('name', 'chapter_number', 'subject', 'ncert_reference')
    list_filter = ('subject', 'subject__teacher')
    search_fields = ('name', 'description', 'ncert_reference')


@admin.register(SubjectResource)
class SubjectResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "resource_type", "subject", "section", "uploaded_by", "created_at")
    list_filter = ("resource_type", "subject", "section", "created_at")
    search_fields = ("title", "description", "subject__name", "uploaded_by__user__email")

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'author_role', 'rating', 'is_active', 'created_at')
    list_filter = ('is_active', 'rating', 'created_at')
    search_fields = ('author_name', 'text')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    form = AnnouncementAdminForm
    list_display = ("title", "scope", "target_section", "created_by", "expires_at", "created_at")
    list_filter = ("scope", "target_section", "created_at")
    search_fields = ("title", "body", "created_by__email")

    def save_model(self, request, obj, form, change):
        # If no section is selected (All Classes), treat as general broadcast.
        if not obj.target_section_id:
            obj.scope = Announcement.SCOPE_GENERAL
        super().save_model(request, obj, form, change)

        # On create, fan out notification to relevant students.
        if not change:
            recipients_qs = StudentProfile.objects.select_related("user")
            if obj.scope == Announcement.SCOPE_CLASS and obj.target_section_id:
                recipients_qs = recipients_qs.filter(section=obj.target_section)

            feed_link = reverse("view_responded_queries")
            notifications = []
            for student in recipients_qs:
                if not student.user_id:
                    continue
                notifications.append(
                    Notification(
                        recipient=student.user,
                        notification_type="general",
                        title=f"New Announcement: {obj.title}",
                        message=(obj.body or "")[:500],
                        link=feed_link,
                    )
                )
            if notifications:
                Notification.objects.bulk_create(notifications, ignore_conflicts=False)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "holiday_type", "section", "created_by")
    list_filter = ("holiday_type", "section", "date")
    search_fields = ("title", "description", "section__class_level", "section__section")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id and request.user and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

        # On create, notify students similar to announcements.
        if not change:
            recipients_qs = StudentProfile.objects.select_related("user")
            if obj.holiday_type == Holiday.TYPE_SECTION and obj.section_id:
                recipients_qs = recipients_qs.filter(section=obj.section)

            feed_link = reverse("view_responded_queries")
            notifications = []
            for student in recipients_qs:
                if not student.user_id:
                    continue
                notifications.append(
                    Notification(
                        recipient=student.user,
                        notification_type="general",
                        title=f"Holiday Notice: {obj.title}",
                        message=f"Holiday on {obj.date.strftime('%b %d, %Y')}.",
                        link=feed_link,
                    )
                )
            if notifications:
                Notification.objects.bulk_create(notifications, ignore_conflicts=False)
