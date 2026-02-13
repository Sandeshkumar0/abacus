#!/bin/bash
echo "⚠️  WARNING: This will DELETE the existing 'abacus_db' and recreate it properly owned by 'sandesh'."
echo "Only proceed if the database is effectively empty or you have backups."

# Attempt to drop and recreate the database using createdb/dropdb utilities
# These often work better with peer authentication than psql shell

echo "Step 1: Dropping old database (if exists)..."
if sudo -u postgres dropdb abacus_db; then
    echo "Old database dropped."
else
    echo "Database drop failed (maybe it didn't exist or permission denied). Trying to continue..."
fi

echo "Step 2: Creating new database owned by 'sandesh'..."
if sudo -u postgres createdb -O sandesh abacus_db; then
    echo "✅ Database 'abacus_db' created with owner 'sandesh'."
    echo "Permissions should now be correct!"
    echo "Run 'python manage.py migrate' to finish setup."
else
    echo "❌ Failed to create database. Please check postgres permissions."
fi
