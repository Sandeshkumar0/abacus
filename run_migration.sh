#!/bin/bash

# Simple Migration Script
# Run this in your terminal to create the database tables

echo "======================================"
echo "Creating Blog Database Tables"
echo "======================================"
echo ""

# Navigate to project directory
cd /home/aarzoo/Downloads/abacusmaster

# Run migration
echo "Running: python manage.py migrate"
python manage.py migrate

echo ""
echo "======================================"
echo "Migration Complete!"
echo "======================================"
echo ""
echo "Now run: python create_sample_blog_data.py"
echo "Then visit: http://127.0.0.1:8000/blog/"
