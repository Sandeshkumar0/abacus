#!/bin/bash

echo "🚀 Setting up AbacusMaster project..."

# Step 1: Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Step 2: Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Step 3: Install Django and required packages
echo "📚 Installing Django and dependencies..."
pip install django
pip install python-dotenv
pip install pillow
pip install reportlab
pip install google-generativeai
pip install youtube-transcript-api
pip install requests

# Step 4: Run migrations
echo "🗄️  Running database migrations..."
python manage.py makemigrations
python manage.py migrate

# Step 5: Start server
echo "✅ Setup complete! Starting development server..."
echo "🌐 Server will run at: http://127.0.0.1:8000"
echo ""
python manage.py runserver
