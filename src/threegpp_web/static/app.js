"use strict";

// GET-only refresh: observing a job never starts or retries work.
const poll = document.querySelector("[data-job-poll]");
if (poll) {
  window.setTimeout(() => {
    if (document.visibilityState === "visible") window.location.reload();
  }, 5000);
}

// Preserve native form validation, and avoid accidental double submissions.
document.querySelectorAll("form").forEach((form) => {
  form.addEventListener("submit", () => {
    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.setAttribute("aria-busy", "true");
      window.setTimeout(() => { button.disabled = true; }, 0);
    }
  });
});
