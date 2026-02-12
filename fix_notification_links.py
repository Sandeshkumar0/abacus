"""
Script to fix old notification links in the database.
This updates all notifications with broken links to the correct portal URLs.
"""

import os
import django
import sys

# Setup Django environment
sys.path.append('/home/aarzoo/Downloads/abacusmaster')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from dashboard.models import Notification

def fix_notification_links():
    """Fix all notification links to use correct portal URLs"""
    
    print("🔍 Checking for broken notification links...")
    
    # Fix test_assigned notifications
    test_notifications = Notification.objects.filter(
        notification_type='test_assigned',
        link='/dashboard/student/'
    )
    count = test_notifications.count()
    if count > 0:
        test_notifications.update(link='/portal/dashboard/student/view-assign/')
        print(f"✅ Fixed {count} test assignment notification(s)")
    
    # Fix exam_assigned notifications
    exam_notifications = Notification.objects.filter(
        notification_type='exam_assigned',
        link='/dashboard/student/'
    )
    count = exam_notifications.count()
    if count > 0:
        exam_notifications.update(link='/portal/dashboard/student/give-test/')
        print(f"✅ Fixed {count} exam assignment notification(s)")
    
    # Fix answer_graded notifications
    graded_notifications = Notification.objects.filter(
        notification_type='answer_graded',
        link='/dashboard/student/'
    )
    count = graded_notifications.count()
    if count > 0:
        graded_notifications.update(link='/portal/dashboard/student/view-remarks/')
        print(f"✅ Fixed {count} answer graded notification(s)")
    
    # Fix query_responded notifications
    query_notifications = Notification.objects.filter(
        notification_type='query_responded',
        link='/dashboard/student/'
    )
    count = query_notifications.count()
    if count > 0:
        query_notifications.update(link='/portal/dashboard/student/view-responded-queries/')
        print(f"✅ Fixed {count} query response notification(s)")
    
    # Summary
    total_fixed = Notification.objects.filter(link='/dashboard/student/').count()
    
    if total_fixed == 0:
        print("\n🎉 All notification links are correct!")
    else:
        print(f"\n⚠️  Warning: {total_fixed} notifications still have broken links")
    
    # Show current notification stats
    print("\n📊 Notification Summary:")
    print(f"   Total notifications: {Notification.objects.count()}")
    print(f"   Test assigned: {Notification.objects.filter(notification_type='test_assigned').count()}")
    print(f"   Exam assigned: {Notification.objects.filter(notification_type='exam_assigned').count()}")
    print(f"   Answer graded: {Notification.objects.filter(notification_type='answer_graded').count()}")
    print(f"   Query responded: {Notification.objects.filter(notification_type='query_responded').count()}")
    
    print("\n✅ All notification links have been fixed!")
    print("🔄 Refresh your browser to see the changes.")

if __name__ == '__main__':
    fix_notification_links()
