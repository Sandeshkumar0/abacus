from django.shortcuts import render
from django.db import models
import os
from email.mime.image import MIMEImage
from django.conf import settings   # already present in your file

# --------- Public / Marketing pages ---------

def home(request):
    return render(request, "home.html")

def about(request):
    return render(request, "about.html")

def courses(request):
    courses_list = []
    enrolled_ids = []
    try:
        from dashboard.models import Course, Enrollment
        
        # Auto-create courses if none exist (Hardcoded for demo)
        if not Course.objects.exists():
            Course.objects.create(
                title='Abacus', 
                description='Foundational number sense + Virtual Abacus', 
                duration='3 months'
            )
            Course.objects.create(
                title='Abacus Teacher Training', 
                description='Certify to teach AbacusMaster curriculum', 
                duration='6 Weeks'
            )
            Course.objects.create(
                title='Vedic', 
                description='Strengthens both short-term and long-term memory.', 
                duration='3 months'
            )
            Course.objects.create(
                title='Calligraphy', 
                description='Showcase Your Work Visually', 
                duration='3 months'
            )
            Course.objects.create(
                title='Vedic Teacher Training', 
                description='Certify to teach Vedic curriculum', 
                duration='6 Weeks'
            )

        courses_list = Course.objects.all()
        if request.user.is_authenticated and hasattr(request.user, 'studentprofile'):
             enrolled_ids = list(Enrollment.objects.filter(student=request.user.studentprofile).values_list('course_id', flat=True))
    except Exception as e:
        print(f"Error fetching/creating courses: {e}")

    return render(request, "courses.html", {'courses': courses_list, 'enrolled_ids': enrolled_ids})


def attach_inline_logo(msg):
    """
    Attach static/images/logo.png as an inline image with Content-ID <logo>.
    Call this AFTER msg.attach_alternative(html_body, "text/html")
    """
    msg.mixed_subtype = 'related'   # important: allow inline related parts

    logo_path = os.path.join(settings.BASE_DIR, "static", "images", "logo.png")
    try:
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        img = MIMEImage(logo_data)
        img.add_header('Content-ID', '<logo>')
        img.add_header('Content-Disposition', 'inline', filename='logo.png')
        msg.attach(img)
        print("DEBUG: attached inline logo from", logo_path)
    except FileNotFoundError:
        print("DEBUG: logo.png not found at", logo_path)
    except Exception as e:
        print("DEBUG: error attaching logo:", repr(e))


# views.py (modify franchise view). Original file reference: :contentReference[oaicite:3]{index=3}
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, redirect
from django.template.loader import render_to_string

def franchise(request):
    """
    GET: render the page
    POST: accept form, send HTML email to user, and render the page with a success message.
    """
    if request.method == "POST":
        # get form values (names already match your template fields)
        fullName = request.POST.get("fullName", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        city = request.POST.get("city", "").strip()
        businessExperience = request.POST.get("businessExperience", "").strip()
        investmentCapacity = request.POST.get("investmentCapacity", "").strip()
        additionalMessage = request.POST.get("additionalMessage", "").strip()

        # Minimal validation
        errors = []
        if not fullName:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email is required.")
        # (add more validation as needed)

        if errors:
            # re-render template with errors and previously entered data
            context = {"errors": errors, "form_data": request.POST}
            return render(request, "franchise.html", context)

        # Prepare email context for template
        email_context = {
            "fullName": fullName,
            "email": email,
            "phone": phone,
            "city": city,
            "businessExperience": businessExperience,
            "investmentCapacity": investmentCapacity,
            "additionalMessage": additionalMessage,
            # configure these values
            "logo_url": request.build_absolute_uri('/static/images/logo.png'),  # make sure logo exists
            "company_name": "AbacusMaster",  # update as needed
            "company_address": "Electronic city, Bengaluru",
            "support_email": "info@emesyslearning.com",
            "cta_url": "#",  # placeholder for later integration
        }

        # Render HTML email
        subject = "Thanks for your franchise inquiry — {}".format(email_context["company_name"])
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)
        to_email = [email]

        html_body = render_to_string("emails/franchise_inquiry.html", email_context)

        # Plain-text fallback using f-strings so keys can't mismatch
        text_body = (
            f"Thanks for your interest in {email_context['company_name']} franchise.\n\n"
            "We received your details:\n\n"
            f"Name: {fullName}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n"
            f"City: {city}\n"
            f"Experience: {businessExperience}\n"
            f"Investment: {investmentCapacity}\n\n"
            "Message:\n"
            f"{additionalMessage}\n\n"
            "We will contact you soon."
        )


        # Send email (HTML + plain text)
        print("DEBUG: preparing to send email to", email)
        try:
            # ... after html_body computed ...
            msg = EmailMultiAlternatives(subject, text_body, from_email, [email])
            msg.attach_alternative(html_body, "text/html")
            # attach inline logo for cid:logo to work
            attach_inline_logo(msg)
            result = msg.send(fail_silently=False)
            print("DEBUG: msg.send() returned:", result)
        except Exception as e:
            print("DEBUG: msg.send() EXCEPTION:", repr(e))
            # return friendly error so you can see the message on the page
            return render(request, "franchise.html", {"errors":[str(e)], "form_data": request.POST})

        # optionally: notify internal email address
        try:
            admin_subject = "New franchise inquiry from {}".format(fullName)
            admin_to = [getattr(settings, "FRANCHISE_NOTIFY_EMAIL", "info@emesyslearning.com")]
            admin_text = "New inquiry:\n\n" + text_body
            admin_msg = EmailMultiAlternatives(admin_subject, admin_text, from_email, admin_to)
            admin_msg.attach_alternative(html_body, "text/html")
            admin_msg.send(fail_silently=True)
        except Exception:
            pass

        # Render the page with success message
        return render(request, "franchise.html", {"success": True})

    # GET request
    return render(request, "franchise.html")


def blog_list(request):
    """
    Fetch blog posts from database and display them.
    Support filtering by category and search.
    """
    from .models import BlogPost, BlogCategory
    
    # Get all published posts
    posts = BlogPost.objects.filter(is_published=True)
    
    # Get all categories
    categories = BlogCategory.objects.all()
    
    # Filter by category if provided
    category_filter = request.GET.get('category')
    if category_filter and category_filter != 'All':
        posts = posts.filter(category__slug=category_filter)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        posts = posts.filter(
            models.Q(title__icontains=search_query) |
            models.Q(excerpt__icontains=search_query) |
            models.Q(content__icontains=search_query)
        )
    
    context = {
        'posts': posts,
        'categories': categories,
        'selected_category': category_filter or 'All',
        'search_query': search_query or '',
    }
    
    return render(request, "blog.html", context)
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.mail import EmailMultiAlternatives
# render_to_string, settings are already imported in your file

@require_http_methods(["POST", "GET"])
def subscribe_newsletter(request):
    """
    POST: accept email, send a welcome/confirmation HTML email to the subscriber,
          and optionally notify internal support email. If request is AJAX -> return JSON.
    GET: redirect or render blog page (fallback).
    """
    if request.method == "GET":
        # fallback - redirect to blog
        return render(request, "blog.html")

    # POST
    email = request.POST.get("email", "").strip()
    errors = []
    if not email:
        errors.append("Please provide a valid email address.")

    # Basic email format check (very simple)
    if email and "@" not in email:
        errors.append("Please enter a valid email address.")

    if errors:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": errors}, status=400)
        return render(request, "blog.html", {"errors": errors})

    # Build email context
    email_context = {
        "subscriber_email": email,
        "logo_url": request.build_absolute_uri('/static/images/logo.png'),  # ensure file exists
        "company_name": "AbacusMaster",
        "support_email": "info@emesyslearning.com",
        "company_address": "Electronic city, Bengaluru",
    }

    subject = f"Welcome to {email_context['company_name']} Newsletter"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)
    to_email = [email]

    # Render HTML and plain text
    html_body = render_to_string("emails/newsletter_subscription.html", email_context)
    text_body = (
        f"Welcome to {email_context['company_name']}!\n\n"
        "Thanks for subscribing to our newsletter. We'll send useful articles and tips to this address.\n\n"
        f"If you need help, reach us at {email_context['support_email']}.\n\n"
        "— The AbacusMaster Team"
    )

    # Attempt to send the subscriber email
    email_sent = False
    try:
        print("DEBUG: sending newsletter confirmation to", email)
        msg = EmailMultiAlternatives(subject, text_body, from_email, to_email, reply_to=[settings.FRANCHISE_NOTIFY_EMAIL])
        msg.attach_alternative(html_body, "text/html")
        attach_inline_logo(msg)
        sent = msg.send(fail_silently=False)
        print("DEBUG: newsletter send() returned:", sent)
        email_sent = True
    except Exception as e:
        print("DEBUG: newsletter send EXCEPTION:", repr(e))
        # Don't fail the entire request - just note that email failed
        email_sent = False

    # Optionally notify admin/support about the new subscriber (optional; silent on failure)
    try:
        admin_subject = f"New newsletter subscriber: {email}"
        admin_to = [getattr(settings, "FRANCHISE_NOTIFY_EMAIL", "info@emesyslearning.com")]
        admin_text = f"New subscriber: {email}\n\nFrom page: Blog newsletter"
        admin_msg = EmailMultiAlternatives(admin_subject, admin_text, from_email, admin_to,
                                           reply_to=[email])
        admin_msg.attach_alternative(html_body, "text/html")
        admin_msg.send(fail_silently=True)
    except Exception as e:
        print("DEBUG: admin notification failed:", repr(e))

    # Success response (even if email failed - subscription is recorded)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        if email_sent:
            return JsonResponse({"success": True, "message": "Subscription successful! Check your email for confirmation."})
        else:
            return JsonResponse({"success": True, "message": "Subscription successful! (Email confirmation pending)"})
    else:
        # fallback: render blog page with success flag
        return render(request, "blog.html", {"newsletter_success": True})
def blog_detail(request, slug):
    """
    Minimal placeholder detail view. Use `slug` to fetch the post later.
    """
    # For testing, just pass the slug to the template
    return render(request, "blog_detail.html", {"slug": slug})

def contact(request):
    """
    Handle contact form submissions.
    GET: render the contact page
    POST: save submission to database and send email notification
    """
    if request.method == "POST":
        from .models import ContactSubmission
        
        # Get form data
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()
        
        # Validate
        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if not message:
            errors.append("Message is required.")
        
        if errors:
            return render(request, "contact.html", {"errors": errors, "form_data": request.POST})
        
        # Save to database
        try:
            submission = ContactSubmission.objects.create(
                name=name,
                email=email,
                message=message
            )
            
            # Send email notification to admin (optional)
            try:
                admin_subject = f"New Contact Form Submission from {name}"
                admin_to = [getattr(settings, "FRANCHISE_NOTIFY_EMAIL", "info@emesyslearning.com")]
                admin_text = f"""
New contact form submission:

Name: {name}
Email: {email}
Message:
{message}

Submitted at: {submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
                admin_msg = EmailMultiAlternatives(admin_subject, admin_text, settings.EMAIL_HOST_USER, admin_to, reply_to=[email])
                admin_msg.send(fail_silently=True)
            except Exception as e:
                print(f"DEBUG: Failed to send admin notification: {repr(e)}")
            
            # Return success
            return render(request, "contact.html", {"success": True})
            
        except Exception as e:
            print(f"DEBUG: Failed to save contact submission: {repr(e)}")
            errors.append("An error occurred. Please try again.")
            return render(request, "contact.html", {"errors": errors, "form_data": request.POST})
    
    # GET request
    return render(request, "contact.html")

def privacy(request):
    return render(request, "privacy.html")

def virtual_abacus(request):
    return render(request, "virtual_abacus.html")

def terms(request):
    return render(request, "terms.html")

def refund(request):
    return render(request, "refund.html")


# --------- Auth pages (static placeholders for now) ---------

def signin(request):
    return render(request, "signin.html")

def signup(request):
    return render(request, "signup.html")
