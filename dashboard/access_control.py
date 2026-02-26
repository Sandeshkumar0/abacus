from django.db.models import Q

from accounts.models import (
    CustomUser,
    ParentProfile,
    ParentStudentRelation,
    Section,
    StudentProfile,
    TeacherProfile,
    TeacherSectionAssignment,
)

from .models import Subject, SubjectTeacherAssignment


def _get_teacher_profile(user):
    if not user.is_authenticated:
        return None
    try:
        return TeacherProfile.objects.get(user=user)
    except TeacherProfile.DoesNotExist:
        return None


def _get_parent_profile(user):
    if not user.is_authenticated:
        return None
    try:
        return ParentProfile.objects.get(user=user)
    except ParentProfile.DoesNotExist:
        return None


def get_accessible_sections(user):
    if not user.is_authenticated:
        return Section.objects.none()
    if user.role in {CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}:
        return Section.objects.all()
    if user.role in {CustomUser.Role.TEACHER, CustomUser.Role.CLASS_TEACHER}:
        teacher = _get_teacher_profile(user)
        if not teacher:
            return Section.objects.none()
        assigned_ids = TeacherSectionAssignment.objects.filter(teacher=teacher).values_list("section_id", flat=True)
        homeroom_ids = Section.objects.filter(class_teacher=teacher).values_list("id", flat=True)
        subject_assignment_ids = SubjectTeacherAssignment.objects.filter(
            teacher=teacher
        ).values_list("section_id", flat=True)
        # Fallback: include sections where students are directly assigned to this teacher.
        student_section_ids = StudentProfile.objects.filter(
            assigned_teacher=teacher,
            section__isnull=False,
        ).values_list("section_id", flat=True)
        return Section.objects.filter(
            id__in=set(assigned_ids)
            .union(set(homeroom_ids))
            .union(set(subject_assignment_ids))
            .union(set(student_section_ids))
        )
    if user.role == CustomUser.Role.STUDENT:
        student = StudentProfile.objects.filter(user=user).select_related("section").first()
        if student and student.section_id:
            return Section.objects.filter(id=student.section_id)
    return Section.objects.none()


def get_accessible_students(user):
    if not user.is_authenticated:
        return StudentProfile.objects.none()
    if user.role in {CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}:
        return StudentProfile.objects.select_related("user", "section", "assigned_teacher")
    if user.role in {CustomUser.Role.TEACHER, CustomUser.Role.CLASS_TEACHER}:
        teacher = _get_teacher_profile(user)
        if not teacher:
            return StudentProfile.objects.none()
        allowed_sections = get_accessible_sections(user).values_list("id", flat=True)
        return StudentProfile.objects.select_related("user", "section", "assigned_teacher").filter(
            Q(assigned_teacher=teacher) | Q(section_id__in=allowed_sections)
        )
    if user.role == CustomUser.Role.STUDENT:
        return StudentProfile.objects.select_related("user", "section", "assigned_teacher").filter(user=user)
    if user.role == CustomUser.Role.PARENT:
        parent = _get_parent_profile(user)
        if not parent:
            return StudentProfile.objects.none()
        child_ids = ParentStudentRelation.objects.filter(parent=parent).values_list("student_id", flat=True)
        return StudentProfile.objects.select_related("user", "section", "assigned_teacher").filter(pk__in=child_ids)
    return StudentProfile.objects.none()


def get_accessible_subjects(user):
    if not user.is_authenticated:
        return Subject.objects.none()
    if user.role in {CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}:
        return Subject.objects.all()
    if user.role in {CustomUser.Role.TEACHER, CustomUser.Role.CLASS_TEACHER}:
        teacher = _get_teacher_profile(user)
        if not teacher:
            return Subject.objects.none()
        assigned_subject_ids = SubjectTeacherAssignment.objects.filter(
            teacher=teacher
        ).values_list("subject_id", flat=True)

        # Also allow class-wide subjects for the sections this teacher can access.
        section_class_levels = [
            str(level).strip()
            for level in get_accessible_sections(user).values_list("class_level", flat=True)
            if str(level).strip()
        ]
        class_level_filters = Q()
        for level in set(section_class_levels):
            class_level_filters |= Q(class_level=level) | Q(class_level=f"Class {level}")

        qs = Subject.objects.filter(Q(id__in=assigned_subject_ids) | Q(teacher=teacher))
        if class_level_filters:
            qs = Subject.objects.filter(
                Q(id__in=assigned_subject_ids) | Q(teacher=teacher) | class_level_filters
            )
        return qs.distinct()
    if user.role == CustomUser.Role.STUDENT:
        student = StudentProfile.objects.select_related("section").filter(user=user).first()
        if not student:
            return Subject.objects.none()
        class_value = ""
        if student.section and student.section.class_level:
            class_value = str(student.section.class_level).strip()
        elif student.student_class:
            class_value = str(student.student_class).strip()

        # Class-wide visibility: all subjects of student's class should be visible
        # across sections (e.g. 2A and 2B both see Class 2 subjects).
        class_qs = Subject.objects.none()
        if class_value:
            class_qs = Subject.objects.filter(
                Q(class_level=class_value) | Q(class_level=f"Class {class_value}")
            )

        # Keep section-specific subject-teacher mapping as additional allowance.
        assigned_subject_ids = []
        if student.section_id:
            assigned_subject_ids = SubjectTeacherAssignment.objects.filter(
                section=student.section
            ).values_list("subject_id", flat=True)

        return Subject.objects.filter(
            Q(id__in=assigned_subject_ids) | Q(id__in=class_qs.values_list("id", flat=True))
        ).distinct()
    if user.role == CustomUser.Role.PARENT:
        parent = _get_parent_profile(user)
        if not parent:
            return Subject.objects.none()
        child_section_ids = ParentStudentRelation.objects.filter(parent=parent).values_list("student__section_id", flat=True)
        assigned_subject_ids = SubjectTeacherAssignment.objects.filter(section_id__in=child_section_ids).values_list("subject_id", flat=True)
        return Subject.objects.filter(id__in=assigned_subject_ids).distinct()
    return Subject.objects.none()


def can_access_student(user, student: StudentProfile):
    return get_accessible_students(user).filter(pk=student.pk).exists()


def can_access_subject(user, subject: Subject, section=None):
    if section is None:
        return get_accessible_subjects(user).filter(pk=subject.pk).exists()
    return SubjectTeacherAssignment.objects.filter(
        teacher__user=user,
        subject=subject,
        section=section,
    ).exists() or user.role in {CustomUser.Role.ADMIN, CustomUser.Role.PRINCIPAL}
