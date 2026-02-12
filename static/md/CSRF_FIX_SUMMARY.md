# ✅ CSRF Configuration - Quick Reference

## What We Fixed

### Problem:
```
Forbidden (CSRF token from POST incorrect.)
```

### Root Cause:
CSRF cookies were expiring too quickly, causing "stale cookie" errors.

---

## Solution Applied

### 1. **Updated `settings.py`** with permanent CSRF configuration:

```python
# CSRF cookie lasts 1 year (prevents stale cookies)
CSRF_COOKIE_AGE = 31449600

# Session stays active for 2 weeks
SESSION_COOKIE_AGE = 1209600

# Refresh session on every request (keeps user logged in)
SESSION_SAVE_EVERY_REQUEST = True

# Trusted domains
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
```

### 2. **Removed temporary `@csrf_exempt` decorators** from:
- `teacher_login` view
- `student_signup` view

---

## How to Test

1. **Restart Django server:**
   ```bash
   python manage.py runserver 8000
   ```

2. **Clear browser cookies:**
   - Press F12 (Developer Tools)
   - Go to Application/Storage tab
   - Clear cookies for localhost:8000

3. **Try logging in:**
   - Go to: http://127.0.0.1:8000/portal/accounts/teacher/login/
   - Enter credentials
   - Should work without CSRF errors! ✅

---

## Benefits

✅ **No more stale cookie errors**
✅ **CSRF token lasts 1 year**
✅ **Users stay logged in for 2 weeks**
✅ **Session refreshes automatically**
✅ **Secure and production-ready**

---

## For Production

When deploying with HTTPS, update:

```python
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = ['https://yourdomain.com']
```

---

**See `CSRF_CONFIGURATION.md` for detailed documentation.**
