#!/bin/bash

# Blog Setup Script
# This script sets up the dynamic blog functionality

echo "========================================="
echo "Blog Dynamic Content Setup"
echo "========================================="
echo ""

# Step 1: Run migrations
echo "Step 1: Creating database migrations..."
python manage.py makemigrations core

if [ $? -ne 0 ]; then
    echo "❌ Migration creation failed!"
    exit 1
fi

echo "✅ Migrations created successfully"
echo ""

# Step 2: Apply migrations
echo "Step 2: Applying migrations to database..."
python manage.py migrate

if [ $? -ne 0 ]; then
    echo "❌ Migration failed!"
    exit 1
fi

echo "✅ Migrations applied successfully"
echo ""

# Step 3: Create sample data
echo "Step 3: Creating sample blog data..."
python create_sample_blog_data.py

if [ $? -ne 0 ]; then
    echo "⚠️  Sample data creation failed, but you can add data manually via admin"
else
    echo "✅ Sample data created successfully"
fi

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Run: python manage.py runserver"
echo "2. Visit: http://127.0.0.1:8000/blog/"
echo "3. Admin: http://127.0.0.1:8000/admin/"
echo ""
echo "See BLOG_SETUP_GUIDE.md for detailed documentation"
echo ""
