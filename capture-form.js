// Waitlist capture wiring — posts email-only signups to our own endpoint.
//
// The form markup works with JS disabled: method="post" + action point at the
// capture service, which answers a urlencoded post with a 303 to /welcome
// (invalid email → /welcome?status=invalid). This script only upgrades the
// experience: it intercepts submit, posts JSON, and shows the outcome inline.
// On any failure it re-arms the native post (form.submit() skips the submit
// event, so the fall-through cannot loop) and lets the server redirect.
//
// Success handling mirrors the old kit-form.js: forms marked data-capture-redirect
// leave for the thank-you page; the rest confirm on-page.

const STATUS_MESSAGES = {
  success: "You're in. You're on the waitlist — one short note a day when we launch. Rest tonight.",
};

const forms = document.querySelectorAll("[data-capture-form]");

function showState(form, state) {
  const statusRegion = form.parentElement.querySelector("[data-form-status]");
  if (!statusRegion) return;
  statusRegion.dataset.state = state;
  statusRegion.textContent = STATUS_MESSAGES[state] || "";
  statusRegion.hidden = false;
}

// The capture endpoint takes first_name optionally; the site asks for email
// only, so the payload is just the address plus the page it came from.
function capturePayload(form) {
  const sourceUrl = form.querySelector('[name="source_url"]');
  return {
    email: form.email.value,
    source_url: sourceUrl ? sourceUrl.value : window.location.href,
  };
}

for (const form of forms) {
  // Stamp the hidden source_url input with the live page URL — the markup
  // ships it empty so a JS-disabled post carries whatever the browser sent.
  const sourceUrl = form.querySelector('[name="source_url"]');
  if (sourceUrl) sourceUrl.value = window.location.href;

  form.addEventListener("submit", async (event) => {
    // Honeypot filled: not a person. Skip the upgrade and let the native post
    // carry the spam marker to the server, which drops it.
    if (form.website && form.website.value) return;

    event.preventDefault();
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(capturePayload(form)),
      });
      if (!response.ok) throw new Error(`capture failed: ${response.status}`);
      const data = await response.json().catch(() => null);
      if (!data || data.ok !== true) throw new Error("capture endpoint answered without ok");

      const handoff = form.dataset.captureRedirect;
      if (handoff) {
        window.location.assign(handoff);
      } else {
        showState(form, "success");
      }
    } catch {
      form.submit(); // native post fall-through: the server owns the redirect
    } finally {
      if (button) button.disabled = false;
    }
  });
}
