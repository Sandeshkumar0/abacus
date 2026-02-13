# 🐘 Switching to PostgreSQL

I have updated your project to use **PostgreSQL**.

## 1. Setup Database
You need to create a database in PostgreSQL. Run these commands in your terminal (or use pgAdmin):

```bash
# Login to postgres
sudo -u postgres psql

# Inside psql shell:
CREATE DATABASE abacus_db;
CREATE USER myuser WITH PASSWORD 'mypassword';
ALTER ROLE myuser SET client_encoding TO 'utf8';
ALTER ROLE myuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE myuser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE abacus_db TO myuser;
\q
```

## 2. Update Configuration
Edit your `.env` file to match the user and password you just created:

```bash
DB_NAME=abacus_db
DB_USER=myuser
DB_PASSWORD=mypassword
DB_HOST=localhost
DB_PORT=5432
```

## 3. Apply Migrations
Once configured, run the following to set up the database schema:

```bash
python manage.py migrate
```

## 4. Restore Sample Data (Optional)
Since this is a new database, it will be empty. You can repopulate it:

```bash
python manage.py createsuperuser
python populate_sample_data.py
```
