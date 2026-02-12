// static/js/newsletter.js
(function () {
  // helper to read csrftoken from cookie
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  function showToast(message, isError) {
    // simple alert for now; you can replace with nicer UI
    if (isError) {
      alert("Error: " + message);
    } else {
      alert(message);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('.newsletter-form');
    if (!form) return;

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const formData = new FormData(form);
      const email = formData.get('email') || form.querySelector('input[type=email]').value;

      if (!email) {
        showToast("Please enter your email address", true);
        return;
      }

      const csrftoken = getCookie('csrftoken');

      fetch('/subscribe/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json'
        },
        body: formData
      })
      .then(r => r.json().catch(() => { throw new Error('Invalid response from server'); }))
      .then(data => {
        if (data && data.success) {
          showToast(data.message || 'Thanks — confirmation sent to your email.');
          form.reset();
        } else {
          const err = data && data.errors ? data.errors.join('; ') : 'Subscription failed';
          showToast(err, true);
        }
      })
      .catch(err => {
        console.error('Newsletter submit error:', err);
        showToast('Something went wrong. Please try again later.', true);
      });
    });
  });
})();
