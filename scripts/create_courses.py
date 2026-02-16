import os
import django
import sys

sys.path.append('/home/aarzoo/Downloads/abacusmaster')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from dashboard.models import Course

courses = [
    {
        'title': 'Abacus',
        'description': 'Foundational number sense + Virtual Abacus',
        'duration': '3 months',
    },
    {
        'title': 'Abacus Teacher Training',
        'description': 'Certify to teach AbacusMaster curriculum',
        'duration': '6 Weeks',
    },
    {
        'title': 'Vedic',
        'description': 'Strengthens both short-term and long-term memory by engaging mental visualization.',
        'duration': '3 months',
    },
    {
        'title': 'Calligraphy',
        'duration': '3 months',
        'description': 'Showcase Your Work Visually'
    },
    {
        'title': 'Vedic Teacher Training',
        'duration': '6 Weeks',
        'description': 'Certify to teach Vedic curriculum'
    }
]

for course_data in courses:
    try:
        c, created = Course.objects.get_or_create(
            title=course_data['title'],
            defaults=course_data
        )
        if created:
            print(f"Created: {c.title}")
        else:
            print(f"Exists: {c.title}")
    except Exception as e:
        print(f"Error creating {course_data['title']}: {e}")

print("Done!")
