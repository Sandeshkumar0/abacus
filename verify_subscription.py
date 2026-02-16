
import os
import django
import sys

# Setup Django environment
sys.path.append('c:\\Users\\KIIT0001\\Downloads\\abacusmaster_2\\abacusmaster')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    if isinstance(settings.ALLOWED_HOSTS, tuple):
        settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS)
    settings.ALLOWED_HOSTS.append('testserver')

from django.test import RequestFactory
from core.views import subscribe_newsletter
from core.models import Subscription
import json

def verify_subscription():
    print("Verifying subscription functionality...")
    
    # 1. Clear existing test subscription
    email = "test_user@example.com"
    Subscription.objects.filter(email=email).delete()
    
    # 2. Create a POST request
    factory = RequestFactory()
    data = {
        'name': 'Test User',
        'email': email
    }
    request = factory.post('/subscribe/', data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    # 3. Call the view
    response = subscribe_newsletter(request)
    
    # 4. Check response
    print(f"Response status: {response.status_code}")
    content = json.loads(response.content)
    print(f"Response content: {content}")
    
    if response.status_code == 200 and content.get('success'):
        print("✅ View returned success")
    else:
        print("❌ View failed")
        return

    # 5. Check database
    try:
        sub = Subscription.objects.get(email=email)
        print(f"✅ Subscription object created: {sub}")
        if sub.name == 'Test User':
            print("✅ Name saved correctly")
        else:
            print(f"❌ Name not saved correctly. Got: {sub.name}")
    except Subscription.DoesNotExist:
        print("❌ Subscription object NOT found in database")

if __name__ == "__main__":
    verify_subscription()
