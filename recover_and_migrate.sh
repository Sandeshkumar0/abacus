#!/bin/bash
# Database Recovery and Migration Script

echo "🔧 Restoring database from backup..."
cp db_backup.sqlite3 db.sqlite3

echo "📦 Installing dependencies..."
source venv/bin/activate
pip install -q channels daphne

echo "🗄️ Running migrations..."
python manage.py makemigrations dashboard
python manage.py migrate

echo "✅ Checking data..."
python manage.py shell -c "
from dashboard.models import Question
from accounts.models import StudentProfile, CustomUser
print(f'Questions: {Question.objects.count()}')
print(f'Students: {StudentProfile.objects.count()}')
print(f'Users: {CustomUser.objects.count()}')
"

echo "🚀 Done! You can now run: python manage.py runserver 8080"
