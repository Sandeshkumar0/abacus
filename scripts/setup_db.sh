#!/bin/bash
echo "🐘 Setting up PostgreSQL User & Database..."

# Try to run psql commands as 'postgres' superuser
if sudo -u postgres psql -c "SELECT 1;" >/dev/null 2>&1; then
    
    # 1. Create User
    echo "Creating user 'sandesh'..."
    sudo -u postgres psql -c "CREATE USER sandesh WITH PASSWORD 'ansh1234';" || echo "⚠️  User 'sandesh' might already exist."

    # 2. Create Database
    echo "Creating database 'abacus_db'..."
    sudo -u postgres psql -c "CREATE DATABASE abacus_db OWNER sandesh;" || echo "⚠️  Database 'abacus_db' might already exist."

    # 3. Grant Permissions
    echo "Granting privileges..."
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE abacus_db TO sandesh;"
    
    echo "✅ Setup Complete! You can now run the server."
    echo "If you still see 'Ident authentication failed', you need to edit pg_hba.conf."
else
    echo "❌ Error: Could not connect to PostgreSQL. Is it installed and running?"
    echo "Try running: sudo service postgresql start"
fi
