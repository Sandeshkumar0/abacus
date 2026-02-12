from django.urls import path
from . import views

urlpatterns = [
    # Public / marketing
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("courses/", views.courses, name="courses"),
    path("franchise/", views.franchise, name="franchise"),

    # Blog
    path("blog/", views.blog_list, name="blog_list"),
    path("blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
    path("subscribe/", views.subscribe_newsletter, name="subscribe_newsletter"),

    # Contact & legal
    path("contact/", views.contact, name="contact"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("refund/", views.refund, name="refund"),

    # Auth (static placeholders for now)
    path("accounts/login/", views.signin, name="signin"),
    path("accounts/signup/", views.signup, name="signup"),
    path("virtual-abacus/", views.virtual_abacus, name="virtual_abacus"),
]
