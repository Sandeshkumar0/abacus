#!/bin/bash

# Quick Fix for Contact Form Error
# Run this command to create the ContactSubmission table

echo "Applying migrations to create ContactSubmission table..."
python manage.py migrate

echo ""
echo "✅ Done! Now restart your server and test the contact form again."
echo ""
echo "To restart server:"
echo "  python manage.py runserver 8000"
