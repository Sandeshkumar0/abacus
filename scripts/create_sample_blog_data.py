"""
Script to create sample blog data for testing
Run this after migrations: python manage.py shell < create_sample_blog_data.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from core.models import BlogCategory, BlogPost
from datetime import date

# Create categories
categories_data = [
    "Education",
    "Student Success",
    "Teaching Tips",
    "Competition",
    "Parent Guide",
    "Research"
]

print("Creating categories...")
for cat_name in categories_data:
    category, created = BlogCategory.objects.get_or_create(name=cat_name)
    if created:
        print(f"✓ Created category: {cat_name}")
    else:
        print(f"- Category already exists: {cat_name}")

# Create sample blog posts
blog_posts_data = [
    {
        "title": "The Benefits of Mental Math for Children",
        "category": "Education",
        "excerpt": "Discover how mental math training improves cognitive development and problem-solving skills in young learners.",
        "content": """<p>Mental math is a crucial skill that goes beyond simple arithmetic. It helps children develop cognitive abilities, improve concentration, and build confidence in their mathematical abilities.</p>
        
<h2>Key Benefits</h2>
<ul>
    <li>Enhanced problem-solving skills</li>
    <li>Improved memory and concentration</li>
    <li>Faster calculation abilities</li>
    <li>Increased confidence in mathematics</li>
</ul>

<p>Regular practice with abacus training can significantly boost these mental math capabilities.</p>""",
        "image_url": "https://cdn.builder.io/api/v1/image/assets%2Fc419bd14efe1424cbd2ad3b976103678%2Fb1ae7f18370e44b8b3956c710e83c32a?format=webp&width=800",
        "author_name": "Windy Bond",
        "comments_count": 136,
    },
    {
        "title": "How Abacus Training Boosts Confidence",
        "category": "Student Success",
        "excerpt": "Learn how mastering abacus techniques can significantly improve a child's self-esteem and performance in school.",
        "content": """<p>Abacus training is more than just learning to calculate - it's about building confidence and self-esteem in young learners.</p>
        
<h2>Confidence Building Through Abacus</h2>
<p>When children master abacus techniques, they experience:</p>
<ul>
    <li>A sense of achievement</li>
    <li>Improved academic performance</li>
    <li>Better concentration skills</li>
    <li>Enhanced self-belief</li>
</ul>

<p>These benefits extend far beyond mathematics into all areas of learning.</p>""",
        "image_url": "https://cdn.builder.io/api/v1/image/assets%2Fc419bd14efe1424cbd2ad3b976103678%2Fde44fc1a8e60406488931512e97f2ce2?format=webp&width=800",
        "author_name": "Priya Sharma",
        "comments_count": 136,
    },
    {
        "title": "Teaching Strategies for Online Abacus Classes",
        "category": "Teaching Tips",
        "excerpt": "Effective techniques for engaging students in virtual learning environments and maintaining strong results.",
        "content": """<p>Online abacus teaching requires special strategies to keep students engaged and ensure effective learning.</p>
        
<h2>Best Practices for Online Teaching</h2>
<ol>
    <li>Use interactive tools and visual aids</li>
    <li>Keep sessions short and focused</li>
    <li>Encourage regular practice</li>
    <li>Provide immediate feedback</li>
    <li>Create a supportive online community</li>
</ol>

<p>With the right approach, online abacus classes can be just as effective as in-person sessions.</p>""",
        "image_url": "https://cdn.builder.io/api/v1/image/assets%2Fc419bd14efe1424cbd2ad3b976103678%2Ff35ab5d4f4ca4ea69b4f1dd3cb88f914?format=webp&width=800",
        "author_name": "Raj Patel",
        "comments_count": 136,
    },
]

print("\nCreating blog posts...")
for post_data in blog_posts_data:
    category = BlogCategory.objects.get(name=post_data["category"])
    post, created = BlogPost.objects.get_or_create(
        title=post_data["title"],
        defaults={
            "category": category,
            "excerpt": post_data["excerpt"],
            "content": post_data["content"],
            "image_url": post_data["image_url"],
            "author_name": post_data["author_name"],
            "comments_count": post_data["comments_count"],
            "is_published": True,
        }
    )
    if created:
        print(f"✓ Created post: {post_data['title']}")
    else:
        print(f"- Post already exists: {post_data['title']}")

print("\n✅ Sample blog data created successfully!")
print(f"Total categories: {BlogCategory.objects.count()}")
print(f"Total published posts: {BlogPost.objects.filter(is_published=True).count()}")
