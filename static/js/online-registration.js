document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('registrationForm');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    // If you want to do client-side validation:
    // e.preventDefault(); ... validate and then submit via fetch/ajax if desired.
    // For now let the server handle submission.
  });

  // Mobile menu toggle if you need it (kept from original)
  const mobileMenu = document.querySelector('.mobile-menu');
  const nav = document.querySelector('nav');
  if (mobileMenu && nav) {
    mobileMenu.addEventListener('click', () => {
      nav.style.display = nav.style.display === 'flex' ? 'none' : 'flex';
    });
  }
});
