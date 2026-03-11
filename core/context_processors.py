from accounts.models import StudentProfile


def student_sidebar_context(request):
    """
    Safe context for student sidebar/topbar blocks.
    Avoids template crashes when StudentProfile is missing.
    """
    section_label = "N/A"
    if getattr(request, "user", None) and request.user.is_authenticated:
        profile = (
            StudentProfile.objects.select_related("section")
            .filter(user=request.user)
            .first()
        )
        if profile:
            if profile.section_id and profile.section:
                section_label = str(profile.section)
            elif profile.student_class:
                section_label = str(profile.student_class)
    return {
        "topbar_student_section_label": section_label,
    }

