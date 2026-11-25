// Dark by default; the choice is remembered in this browser only.
(function () {
  const KEY = "inbox-planner-theme";
  const root = document.documentElement;
  root.dataset.theme = localStorage.getItem(KEY) === "light" ? "light" : "dark";

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("theme-toggle");
    if (!button) return;
    const label = () => {
      button.textContent = root.dataset.theme === "dark" ? "☀ Clair" : "☾ Sombre";
    };
    label();
    button.addEventListener("click", () => {
      root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem(KEY, root.dataset.theme);
      label();
    });
  });
})();
