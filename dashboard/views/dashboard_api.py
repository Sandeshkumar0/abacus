from django.http import JsonResponse
from django.views.decorators.http import require_GET

from dashboard.decorators import student_required_json, teacher_required_json
from dashboard.services.dashboard_metrics import (
    get_student_metrics,
    get_teacher_at_risk_students,
    get_teacher_metrics,
)


@require_GET
@student_required_json
def student_dashboard_snapshot(request):
    """
    API for student dashboard summary.
    LMS-style backend feature for mobile widgets and analytics integrations.
    """
    return JsonResponse({"ok": True, "data": get_student_metrics(request.user)})


@require_GET
@teacher_required_json
def teacher_dashboard_snapshot(request):
    """
    API for teacher dashboard summary.
    Includes backlog and risk counts for intervention planning.
    """
    return JsonResponse({"ok": True, "data": get_teacher_metrics(request.user)})


@require_GET
@teacher_required_json
def teacher_at_risk_students(request):
    """
    API returning lowest-performing students for targeted support workflows.
    """
    try:
        limit = int(request.GET.get("limit", "10"))
    except ValueError:
        limit = 10
    limit = min(max(1, limit), 50)
    rows = get_teacher_at_risk_students(request.user, limit=limit)
    return JsonResponse({"ok": True, "count": len(rows), "data": rows})
