from django.contrib import messages
from django.http import JsonResponse
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.views.decorators.csrf import requires_csrf_token

@requires_csrf_token
def csrf_failure(request, reason=""):
    """
    Custom CSRF failure view with user-friendly error message and solutions.
    """
    # For AJAX calls, return structured JSON so frontend can handle refresh/retry.
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "error": "CSRF verification failed. Refresh and try again.",
                "reason": reason,
            },
            status=403,
        )

    # For normal form POSTs, rotate token and redirect back instead of hard-stop error page.
    if request.method == "POST":
        rotate_token(request)
        messages.error(
            request,
            "Security token expired. Please submit the form again.",
        )
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "/")

    context = {
        'reason': reason,
        'message': 'CSRF Verification Failed',
    }
    return render(request, 'csrf_error.html', context, status=403)
