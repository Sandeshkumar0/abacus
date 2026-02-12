// static/js/courses.js
document.addEventListener('click', function (e) {
  if (e.target.closest('.demo-btn-primary')) {
    alert('Demo requested — we will contact you to schedule it.');
    e.preventDefault();
  }
  if (e.target.closest('.course-btn-enroll')) {
    alert('Enrollment flow not implemented in demo. Please contact us.');
    e.preventDefault();
  }
});
