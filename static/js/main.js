// main.js — shared scripts (taken directly from your existing code)
document.addEventListener("DOMContentLoaded", function() {
  // Example: Navbar toggle if present in your HTML
  const toggle = document.querySelector(".nav-toggle");
  const navMenu = document.querySelector(".nav-menu");
  if (toggle && navMenu) {
    toggle.addEventListener("click", () => {
      navMenu.classList.toggle("active");
    });
  }
});
