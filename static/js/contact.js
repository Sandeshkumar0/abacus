// contact.js — simple form handler (kept similar to your other pages)
document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('contactForm');
  if (!form) return;

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var formData = {
      name: form.querySelector('input[name="name"]').value,
      email: form.querySelector('input[name="email"]').value,
      message: form.querySelector('textarea[name="message"]').value
    };

    // For demo—log and show acknowledgement
    console.log('Contact form submitted:', formData);
    alert('Thanks! Your message has been sent. We will contact you soon.');
    form.reset();
  });
});
