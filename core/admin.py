from django.contrib import admin
from .models import BlogPost, BlogCategory, ContactSubmission

# Register your models here.

@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author_name', 'published_date', 'is_published', 'views_count', 'comments_count']
    list_filter = ['is_published', 'category', 'published_date']
    search_fields = ['title', 'excerpt', 'content', 'author_name']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_date'
    list_editable = ['is_published']
    readonly_fields = ['published_date', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'category', 'excerpt')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Image', {
            'fields': ('image', 'image_url'),
            'description': 'Upload an image OR provide an external URL'
        }),
        ('Author', {
            'fields': ('author_name', 'author')
        }),
        ('Metadata', {
            'fields': ('comments_count', 'views_count', 'is_published'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('published_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'submitted_at', 'is_read']
    list_filter = ['is_read', 'submitted_at']
    search_fields = ['name', 'email', 'message']
    readonly_fields = ['name', 'email', 'message', 'submitted_at']
    list_editable = ['is_read']
    date_hierarchy = 'submitted_at'
    
    def has_add_permission(self, request):
        # Prevent manual addition - only through the form
        return False
