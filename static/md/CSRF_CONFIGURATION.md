# CSRF Configuration Guide for AbacusMaster

## 🔒 What is CSRF?

**CSRF (Cross-Site Request Forgery)** is a security attack where a malicious website tricks a user's browser into performing unwanted actions on a trusted site where the user is authenticated.

**Example Attack:**
1. User logs into `yoursite.com`
2. User visits `evilsite.com` (in another tab)
3. `evilsite.com` sends a hidden form to `yoursite.com/delete-account`
4. Without CSRF protection, the account gets deleted!

**Django's Protection:**
Django uses CSRF tokens - unique, secret values that must be included in every form submission.

---

## ✅ What We Configured

### 1. **CSRF Cookie Settings** (in `settings.py`)

```python
CSRF_COOKIE_AGE = 31449600  # 1 year in seconds
```
- **Purpose:** Makes the CSRF cookie last for 1 year
- **Benefit:** Prevents "stale cookie" errors
- **Before:** Cookie expired quickly, causing login failures
- **After:** Cookie persists, no more CSRF errors

```python
CSRF_COOKIE_SECURE = False  # Set to True in production with HTTPS
```
- **Development:** `False` (works with HTTP)
- **Production:** `True` (requires HTTPS)
- **Security:** Ensures cookie only sent over secure connections in production

```python
CSRF_COOKIE_HTTPONLY = False
```
- **Purpose:** Allows JavaScript to read the cookie if needed
- **Note:** Must be `False` for AJAX requests to work
- **Security:** Still safe because the token itself is validated server-side

```python
CSRF_COOKIE_SAMESITE = 'Lax'
```
- **Options:** `'Strict'`, `'Lax'`, or `'None'`
- **'Lax':** Allows cookies on top-level navigation (clicking links)
- **'Strict':** Only sends cookies for same-site requests (more restrictive)
- **Chosen:** `'Lax'` for better user experience

```python
CSRF_USE_SESSIONS = False
```
- **False:** Store CSRF token in cookies (recommended)
- **True:** Store CSRF token in session (less reliable)
- **Why False?** Cookies are more persistent and reliable

---

### 2. **CSRF Trusted Origins**

```python
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
```
- **Purpose:** Whitelist domains that can make requests
- **Add production domains here:**
  ```python
  CSRF_TRUSTED_ORIGINS = [
      'http://localhost:8000',
      'http://127.0.0.1:8000',
      'https://yourdomain.com',      # Add your domain
      'https://www.yourdomain.com',  # Add www version
  ]
  ```

---

### 3. **Session Settings** (Related to CSRF)

```python
SESSION_COOKIE_AGE = 1209600  # 2 weeks
```
- **Purpose:** How long users stay logged in
- **2 weeks:** Good balance between security and convenience

```python
SESSION_SAVE_EVERY_REQUEST = True
```
- **Purpose:** Refresh session on every request
- **Benefit:** User stays logged in as long as they're active
- **Without this:** Session expires after 2 weeks even if user is active

```python
SESSION_COOKIE_HTTPONLY = True
```
- **Purpose:** Prevent JavaScript from accessing session cookie
- **Security:** Protects against XSS (Cross-Site Scripting) attacks

---

## 🎯 How CSRF Protection Works Now

### **Login Flow:**

1. **User visits login page**
   ```
   GET /accounts/teacher/login/
   ```
   - Django generates CSRF token
   - Stores in cookie (lasts 1 year!)
   - Embeds in form via `{% csrf_token %}`

2. **User submits form**
   ```
   POST /accounts/teacher/login/
   Cookie: csrftoken=abc123...
   Form data: csrfmiddlewaretoken=abc123...
   ```
   - Browser sends cookie AND form token
   - Django compares them
   - If match → ✅ Process request
   - If mismatch → ❌ 403 Forbidden

3. **Token persists**
   - Cookie lasts 1 year
   - No more "stale cookie" errors!
   - Works across browser sessions

---

## 🔧 Template Usage

### **In HTML Forms:**

```html
<form method="POST" action="{% url 'teacher_login' %}">
    {% csrf_token %}  <!-- This is REQUIRED! -->
    <input type="email" name="email" />
    <input type="password" name="password" />
    <button type="submit">Login</button>
</form>
```

**What `{% csrf_token %}` does:**
```html
<!-- Renders as: -->
<input type="hidden" name="csrfmiddlewaretoken" value="abc123...">
```

---

### **In AJAX Requests:**

```javascript
// Get CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// Include in fetch request
fetch('/api/endpoint/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({data: 'value'})
});
```

---

## 🚨 Common CSRF Errors & Solutions

### **Error: "CSRF token missing or incorrect"**

**Causes:**
1. Forgot `{% csrf_token %}` in form
2. Cookie was deleted/blocked
3. Form submitted from different domain

**Solutions:**
1. ✅ Add `{% csrf_token %}` to all POST forms
2. ✅ Clear browser cookies and reload
3. ✅ Check `CSRF_TRUSTED_ORIGINS` includes your domain

---

### **Error: "CSRF cookie not set"**

**Causes:**
1. Cookies are blocked in browser
2. Form loaded via AJAX without proper headers

**Solutions:**
1. ✅ Enable cookies in browser
2. ✅ Use `@ensure_csrf_cookie` decorator on view

---

### **Error: "CSRF token from POST incorrect"**

**Causes:**
1. Stale cookie from old session
2. Cookie and form token don't match

**Solutions:**
1. ✅ Our new settings fix this! (1-year cookie age)
2. ✅ Hard refresh page (Ctrl+Shift+R)
3. ✅ Clear browser cache

---

## 🔐 Production Checklist

When deploying to production with HTTPS:

```python
# settings.py (Production)

# Enable secure cookies
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Add your production domain
CSRF_TRUSTED_ORIGINS = [
    'https://yourdomain.com',
    'https://www.yourdomain.com',
]

# Optional: More strict SameSite
CSRF_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_SAMESITE = 'Strict'
```

---

## 📊 Settings Summary

| Setting | Development | Production | Purpose |
|---------|-------------|------------|---------|
| `CSRF_COOKIE_AGE` | 31449600 (1 year) | 31449600 (1 year) | Cookie lifespan |
| `CSRF_COOKIE_SECURE` | False | **True** | HTTPS only |
| `CSRF_COOKIE_HTTPONLY` | False | False | JS access |
| `CSRF_COOKIE_SAMESITE` | 'Lax' | 'Strict' | Cross-site |
| `SESSION_COOKIE_AGE` | 1209600 (2 weeks) | 1209600 (2 weeks) | Login duration |
| `SESSION_COOKIE_SECURE` | False | **True** | HTTPS only |

---

## 🎓 Key Takeaways

1. **CSRF tokens prevent malicious form submissions**
2. **Our configuration makes tokens last 1 year** (no more stale cookies!)
3. **Always use `{% csrf_token %}` in POST forms**
4. **AJAX requests need `X-CSRFToken` header**
5. **Production requires HTTPS and secure cookies**

---

## 🔗 Useful Resources

- [Django CSRF Documentation](https://docs.djangoproject.com/en/stable/ref/csrf/)
- [OWASP CSRF Guide](https://owasp.org/www-community/attacks/csrf)
- [Django Security Best Practices](https://docs.djangoproject.com/en/stable/topics/security/)

---

**Last Updated:** 2026-02-10
**Project:** AbacusMaster
**Author:** AI Assistant
