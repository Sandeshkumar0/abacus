#!/bin/bash

# Activate virtual environment
source /home/aarzoo/Downloads/abacusmaster/venv/bin/activate

# Navigate to project directory
cd /home/aarzoo/Downloads/abacusmaster

# Create migrations
echo "Creating migrations..."
python manage.py makemigrations accounts

# Apply migrations
echo "Applying migrations..."
python manage.py migrate

echo "✅ Migrations complete! Now run: python manage.py runserver"
