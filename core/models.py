from django.db import models
from django.utils.text import slugify
from django.conf import settings

# Create your models here.

class BlogCategory(models.Model):
    """Categories for blog posts (Education, Student Success, Teaching Tips, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Blog Categories"
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class BlogPost(models.Model):
    """Blog post model with all necessary fields"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name='posts')
    excerpt = models.TextField(max_length=300, help_text="Short description for the card")
    content = models.TextField(help_text="Full blog post content (supports HTML)")
    
    # Image
    image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, help_text="External image URL (if not uploading)")
    
    # Author
    author_name = models.CharField(max_length=100, default="Admin")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_posts')
    
    # Metadata
    comments_count = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)
    
    # Publishing
    is_published = models.BooleanField(default=True)
    published_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-published_date', '-created_at']
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_image_url(self):
        """Return image URL - either uploaded image or external URL"""
        if self.image:
            return self.image.url
        return self.image_url or 'https://via.placeholder.com/800x400?text=Blog+Post'
    
    def __str__(self):
        return self.title


class ContactSubmission(models.Model):
    """Store contact form submissions"""
    name = models.CharField(max_length=200)
    email = models.EmailField()
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Contact Submission"
        verbose_name_plural = "Contact Submissions"
    
    def __str__(self):
        return f"{self.name} - {self.email} ({self.submitted_at.strftime('%Y-%m-%d %H:%M')})"

