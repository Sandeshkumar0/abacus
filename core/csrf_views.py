from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token

@requires_csrf_token
def csrf_failure(request, reason=""):
    """
    Custom CSRF failure view with user-friendly error message and solutions.
    """
    context = {
        'reason': reason,
        'message': 'CSRF Verification Failed',
    }
    return render(request, 'csrf_error.html', context, status=403)
