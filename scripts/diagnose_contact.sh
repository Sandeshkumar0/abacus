#!/bin/bash

# Contact Page Diagnostic Script
# Run this to check what might be wrong

echo "=========================================="
echo "Contact Page Diagnostic"
echo "=========================================="
echo ""

cd /home/aarzoo/Downloads/abacusmaster

echo "1. Checking if ContactSubmission model exists in models.py..."
if grep -q "class ContactSubmission" core/models.py; then
    echo "   ✅ ContactSubmission model found"
else
    echo "   ❌ ContactSubmission model NOT found"
fi
echo ""

echo "2. Checking if migration file exists..."
if ls core/migrations/*contact* 2>/dev/null; then
    echo "   ✅ Migration file exists"
else
    echo "   ⚠️  No migration file found - need to run makemigrations"
fi
echo ""

echo "3. Checking contact URL configuration..."
if grep -q "contact" core/urls.py; then
    echo "   ✅ Contact URL configured"
else
    echo "   ❌ Contact URL NOT configured"
fi
echo ""

echo "4. Checking contact template..."
if [ -f "core/templates/contact.html" ]; then
    echo "   ✅ Contact template exists"
else
    echo "   ❌ Contact template NOT found"
fi
echo ""

echo "=========================================="
echo "Recommended Actions:"
echo "=========================================="
echo ""
echo "If migration file doesn't exist, run:"
echo "  python manage.py makemigrations core"
echo ""
echo "Then apply migrations:"
echo "  python manage.py migrate"
echo ""
echo "Then restart server:"
echo "  python manage.py runserver 8000"
echo ""
echo "=========================================="
