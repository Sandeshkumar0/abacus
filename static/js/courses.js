// static/js/courses.js
document.addEventListener('click', function (e) {
  if (e.target.closest('.demo-btn-primary')) {
    alert('Demo requested — we will contact you to schedule it.');
    e.preventDefault();
  }
  // Enrollment flow is now implemented via backend link.
});
