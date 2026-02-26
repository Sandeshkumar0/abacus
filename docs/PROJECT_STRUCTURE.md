# Project Structure (Beginner Friendly)

This file explains where to edit code safely.

## Top-level folders

- `abacus_site/`
  - Global Django config (`settings.py`, `urls.py`, `asgi.py`, `wsgi.py`)
- `accounts/`
  - Login/signup/logout, user models, auth URLs
- `core/`
  - Public pages (home/about/contact/blog), shared templates
- `dashboard/`
  - Student/teacher dashboard features, exam/test/query logic, notifications
- `static/`
  - CSS, JS, images
- `media/`
  - Uploaded files (runtime content)
- `scripts/`
  - Utility scripts for setup/data/debug
- `docs/`
  - Project notes and guides

## Where to edit what

- Login/Signup issues:
  - `accounts/views.py`
  - `accounts/urls.py`
  - `core/templates/student/student_login.html`
  - `core/templates/teacher/teacher_login.html`

- Password reset flow:
  - `accounts/urls.py`
  - `core/templates/registration/*`

- Student dashboard features:
  - `dashboard/views/student_views.py`
  - `core/templates/student/*`

- Teacher dashboard features:
  - `dashboard/views/teacher_views.py`
  - `core/templates/teacher/*`

- Notifications:
  - `dashboard/signals.py`
  - `dashboard/consumers.py`
  - `static/js/notifications.js`
  - `static/css/notifications.css`

- Public website pages:
  - `core/views.py`
  - `core/templates/*.html`
  - `static/css/page-*.css`

## Important note on old/backup files

- `core/templates.pre_revert.*` and `dashboard/views_old_backup.py` are backup/history references.
- Do not edit those for active app behavior.

## Debug helpers

- Root-level debug files were moved to `scripts/debug/` for cleaner structure.
