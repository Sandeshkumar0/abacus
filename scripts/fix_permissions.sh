#!/bin/bash
echo "🔧 Fixing PostgreSQL Permissions for user 'sandesh'..."

# Grant schema usage and create privileges
sudo -u postgres psql -d abacus_db -c "GRANT ALL ON SCHEMA public TO sandesh;"
sudo -u postgres psql -d abacus_db -c "ALTER DATABASE abacus_db OWNER TO sandesh;"

echo "✅ Permissions fixed! You can now run 'python manage.py migrate'."
