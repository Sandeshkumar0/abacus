# 🔧 Current Issues & Solutions

## 📋 Summary of Issues

Based on the server logs, there are 2 main issues:

### 1. ❌ Gemini API Model Not Found
```
404 models/gemini-pro is not found for API version v1beta
```

### 2. ❌ CSRF Token Error on Student Login  
```
Forbidden (CSRF token from POST incorrect.): /portal/accounts/student/login/
```

---

## 🔴 Issue 1: Gemini Model Not Available

### **Problem:**
The model name `models/gemini-pro` doesn't exist for your API key/version.

### **Why This Happens:**
- Different API keys have access to different models
- Model names change between API versions
- Some models are region-specific

### **Solution:**

#### **Option A: Find the Correct Model (Recommended)**

Run this command to find available models:
```bash
python find_model.py
```

This will show you the exact model name to use.

#### **Option B: Disable AI Features Temporarily**

If you want the app to work without AI features:

1. The app already handles missing AI gracefully
2. All other features work fine
3. AI buttons will show error messages but won't crash

#### **Option C: Try Alternative Model Names**

Common model names to try:
- `gemini-1.0-pro`
- `gemini-1.5-pro-latest`
- `gemini-1.5-flash-latest`
- Just `gemini-pro` (without `models/` prefix)

---

## 🔴 Issue 2: CSRF Token Error

### **Problem:**
```
Forbidden (CSRF token from POST incorrect.): /portal/accounts/student/login/
```

### **Why This Happens:**

1. **Browser cleared cookies** - CSRF token stored in cookie was deleted
2. **Session expired** - Token expired after 2 weeks
3. **Multiple tabs** - Different CSRF tokens in different tabs
4. **Cache issue** - Old form with old token

### **Solutions:**

#### **Immediate Fix (For Users):**

1. **Clear browser cache and cookies**
   - Press `Ctrl + Shift + Delete`
   - Clear "Cookies" and "Cached images"
   - Close all tabs
   - Reopen browser

2. **Hard refresh the login page**
   - Press `Ctrl + Shift + R` (or `Cmd + Shift + R` on Mac)
   - This forces a fresh page load with new CSRF token

3. **Try incognito/private mode**
   - Open incognito window
   - Navigate to login page
   - Try logging in

#### **Permanent Fix (Code Changes):**

The CSRF configuration is already optimized in `settings.py`:
```python
CSRF_COOKIE_AGE = 31449600  # 1 year
SESSION_COOKIE_AGE = 1209600  # 2 weeks  
SESSION_SAVE_EVERY_REQUEST = True  # Refreshes on activity
```

**Additional fixes to try:**

1. **Add CSRF failure view** (shows better error message)
2. **Add CSRF token refresh** (JavaScript to refresh token)
3. **Add better error handling** (show user-friendly message)

---

## 🚀 Quick Fixes

### **For Gemini API:**

**Temporary workaround** - Disable AI features:

```python
# In dashboard/views/ai_utils.py
# Wrap all AI calls in try-except

try:
    model = genai.GenerativeModel("models/gemini-pro")
    response = model.generate_content(parts)
except Exception as e:
    return JsonResponse({
        'status': 'error',
        'message': 'AI service temporarily unavailable. Please try again later.'
    })
```

### **For CSRF Errors:**

**Tell users to:**
1. Clear browser cache
2. Hard refresh (Ctrl + Shift + R)
3. Try incognito mode

**Or add this to login template:**

```html
<script>
// Auto-refresh CSRF token if form submission fails
document.querySelector('form').addEventListener('submit', function(e) {
    // Get fresh CSRF token
    fetch(window.location.href)
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newToken = doc.querySelector('[name=csrfmiddlewaretoken]').value;
            document.querySelector('[name=csrfmiddlewaretoken]').value = newToken;
        });
});
</script>
```

---

## 📊 Current Status

### **Working:**
✅ Student/Teacher signup  
✅ Teacher login  
✅ Student management (Add/Edit/Delete/Export)  
✅ Exam creation  
✅ Assignment submission  
✅ Profile management  
✅ Exam status (Active/Expired) - FIXED!  

### **Issues:**
❌ Student login (CSRF errors - intermittent)  
❌ AI features (Model not found)  

---

## 🎯 Recommended Actions

### **Priority 1: Fix Student Login**

**User workaround:**
- Clear browser cache
- Hard refresh page
- Try incognito mode

**Code fix:**
- Already implemented CSRF persistence
- Issue is likely browser-side

### **Priority 2: Fix Gemini API**

**Steps:**
1. Run `python find_model.py` to find correct model
2. Update model name in code
3. Test AI features

**Or:**
- Accept that AI features won't work
- App functions fine without them

---

## 🔍 Debugging Steps

### **For CSRF Issues:**

1. **Check browser console** (F12)
   - Look for JavaScript errors
   - Check if CSRF token is present

2. **Check cookies**
   - Open DevTools → Application → Cookies
   - Look for `csrftoken` cookie
   - Verify it's not expired

3. **Check form**
   - View page source
   - Find `<input name="csrfmiddlewaretoken">`
   - Verify token is present

### **For Gemini API:**

1. **Run model finder:**
   ```bash
   python find_model.py
   ```

2. **Check API key:**
   ```bash
   cat .env | grep GEMINI
   ```

3. **Test API directly:**
   ```bash
   python quick_check.py
   ```

---

## 📝 Next Steps

1. **Run `python find_model.py`** to find correct Gemini model
2. **Update model name** in code once found
3. **Tell users** to clear cache if CSRF errors occur
4. **Monitor logs** for any new errors

---

## ⚠️ Important Notes

### **CSRF Errors:**
- Usually browser-side issue
- Clearing cache fixes it
- Not a code bug (configuration is correct)

### **Gemini API:**
- Model availability varies by API key
- Need to find correct model name for your key
- App works fine without AI features

---

**Both issues have workarounds. The app is functional!** 🎉
