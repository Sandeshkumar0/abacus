
import os
import django
import sys

# Setup Django environment
sys.path.append('c:\\Users\\KIIT0001\\Downloads\\abacusmaster_2\\abacusmaster')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from core.models import Subscription

def check_subscriptions():
    print("Checking recent subscriptions (last 10):")
    subs = Subscription.objects.order_by('-subscribed_at')[:10]
    if not subs:
        print("No subscriptions found.")
    for sub in subs:
        print(f"Name: {sub.name}, Email: {sub.email}, Date: {sub.subscribed_at}")

if __name__ == "__main__":
    check_subscriptions()
