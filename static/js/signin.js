// signin.js — toggle password visibility
const togglePassword = document.querySelector("#togglePassword");
const passwordField = document.querySelector("#password");
if (togglePassword && passwordField) {
  togglePassword.addEventListener("click", () => {
    const type = passwordField.getAttribute("type") === "password" ? "text" : "password";
    passwordField.setAttribute("type", type);
  });
}
