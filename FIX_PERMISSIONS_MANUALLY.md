# 🔐 Fixing PostgreSQL Permissions Manually

The automatic script failed because it requires sudo password interaction. Please follow these steps to fix the "permission denied" error manually.

## Step 1: Login as Postgres Superuser
Open your terminal and run:

```bash
sudo -u postgres psql
```
*(Enter your system password if prompted)*

## Step 2: Fix Permissions
Once inside the `postgres=#` prompt, copy and paste these commands one by one:

```sql
-- Connect to the database
\c abacus_db

-- Option A: Grant full access to 'public' schema (Recommended)
GRANT ALL ON SCHEMA public TO sandesh;
GRANT ALL PRIVILEGES ON DATABASE abacus_db TO sandesh;
ALTER DATABASE abacus_db OWNER TO sandesh;

-- Verify user can create tables
CREATE TABLE verify_permission (id serial PRIMARY KEY);
DROP TABLE verify_permission;

-- Exit
\q
```

## Step 3: Run Migrations Again
Now that permissions are fixed, run the migration in your project terminal:

```bash
python manage.py migrate
```

## Troubleshooting
If `sudo -u postgres psql` fails with `password authentication failed`, try:
```bash
sudo -i -u postgres
psql
```
