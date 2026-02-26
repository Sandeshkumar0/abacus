# Beginner Checklist (No-Logic-Break Safety)

Use this before and after code edits.

## Before editing

- Confirm the target file belongs to active app code, not backup:
  - Avoid `*.pre_revert*` folders and `views_old_backup.py`
- Read related URL + view + template together (all 3).
- Keep a small scope per change.

## While editing

- Do not hardcode URLs like `"/accounts/reset/done/"` when named URLs exist.
- Do not duplicate imports.
- Keep one import block at top of Python files.
- Avoid mixing debug prints in core logic (use logging later when refactoring).
- Keep comments plain ASCII and clear.

## After editing

- Run: `python manage.py check`
- Open the affected page and test the exact flow you changed.
- If auth changed, test both student and teacher paths.

## Safe file edit order (Django)

1. `urls.py`
2. `views.py`
3. templates
4. static js/css (if needed)

This reduces confusion and keeps behavior traceable.
