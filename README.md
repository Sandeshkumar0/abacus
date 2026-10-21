# Abacus

A Django education portal with student, teacher, and parent workflows. The repository combines public course pages with assignments, exams, attendance, learning resources, and portal notifications.

## Features in the codebase

- Custom accounts and role-specific student, teacher, and parent profiles.
- Sections, teacher assignments, and parent–student relationships.
- Questions, student answers, exams, feedback, and queries.
- Courses, subjects, chapters, resources, and learning-performance records.
- Attendance, timetables, holidays, announcements, and messages.
- Django Channels infrastructure for portal notifications.
- Optional AI-assisted learning and lecture-note utilities, which need their own service credentials and media dependencies.

This is a project overview, not a claim of production deployment or measured learning outcomes.

## Stack

Python, Django, Django templates, HTML/CSS/JavaScript, PostgreSQL, Django Channels, and Daphne. Redis is optional for shared channel and cache backends. Document and media utilities use packages such as ReportLab, yt-dlp, and Whisper.

## Structure

```text
abacus_site/    Django configuration and top-level routes
accounts/       Custom users, profiles, role relationships, and authentication
core/           Public pages and shared portal templates
dashboard/      Learning workflows, notifications, views, and models
static/         Stylesheets, scripts, and images
docs/           Workflow and architecture notes
scripts/        Data/setup/debug utilities; inspect before running
```

Start with [the project map](docs/PROJECT_STRUCTURE.md), [portal workflow guide](docs/EMESYS_Portal_Workflow_Guide.md), and [feature map](FEATURE_MAP.md). `core/templates.pre_revert.*` and other backup files are historical copies, not the active templates.

## Local setup

Prerequisites: Python with `venv`, PostgreSQL, and a dedicated local database and database user. The settings require PostgreSQL; SQLite is not the current default. The repository does not pin a Python interpreter version or provide a lockfile, so the complete installation needs a fresh-environment verification before claiming a supported version range.

```bash
git clone https://github.com/Sandeshkumar0/abacus.git
cd abacus
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`. The dependency list includes the media/ML utilities, so installation can be considerably larger than a minimal Django app. `requirements-prod.txt` contains additional Redis packages; it is not a replacement for `requirements.txt`.

Create a root `.env` using your own local database credentials:

```dotenv
DJANGO_DEBUG=True
DB_NAME=abacus_local
DB_USER=your_local_database_user
DB_PASSWORD=your_local_database_password
DB_HOST=127.0.0.1
DB_PORT=5432
CHANNEL_LAYER_BACKEND=channels.layers.InMemoryChannelLayer
USE_REDIS_CACHE=False
```

Create that database and grant the user access using your PostgreSQL administration tool. Then run:

```bash
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the public site, `/portal/` for the portal landing page, and `/admin/` for Django administration. Use the admin interface to create synthetic course and account data for a local demonstration.

## Configuration and optional services

- For a multi-process notification service, configure the Redis-backed channel layer instead of the in-memory development layer.
- Email behavior is configured in `abacus_site/settings.py`; verify it before testing email flows. The backend is currently selected in code rather than by an `EMAIL_BACKEND` environment switch.
- AI and media helpers need the corresponding provider configuration and, for relevant media processing, external tools such as FFmpeg. These integrations were not exercised in this review.
- Existing setup and recovery scripts can change or reset data. Read them first; they are not part of the default quick start above.

## Verification and next steps

The setup commands above were checked against `manage.py`, `requirements.txt`, settings, URL routes, and migrations. A full PostgreSQL-backed installation and browser workflow were **not run** during this documentation review. The standard commands to run after configuring a local database are:

```bash
python manage.py check
python manage.py test
```

The three top-level app test modules currently contain placeholders rather than behavioral tests. Prioritize tests for role boundaries, parent–student access, teacher section access, exam submissions, and notifications. Add a small repeatable seed command using synthetic data, a dependency lock, and CI before describing the project as reliably reproducible.

## Demo and screenshots

No public demo URL was confirmed. The repository includes static site assets, but no curated walkthrough screenshots. Add a public landing page, one student dashboard, and one teacher workflow captured from a local synthetic dataset. Do not use real student records in portfolio images.
