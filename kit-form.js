// Kit signup wiring for the Parent Pep Talks landing page.
//
// Paste the form UID from Kit's embed snippet once the signup form exists.
// Kit's embed code shows the exact POST target; derive both from it, never guess.
const KIT_FORM_UID = ""; // e.g. "1234567" — empty means "not wired yet"

// Kit's custom-HTML embed posts to this template with the form UID filled in.
// When the real embed snippet exists, confirm this URL against it and update
// this one constant if Kit's contract differs.
const KIT_POST_TEMPLATE = "https://app.kit.com/forms/{uid}/subscriptions";

const STATUS_MESSAGES = {
  success: "You're in — check your inbox for a first note from Parent Pep Talks.",
  error: "That didn't go through. Give it a moment and try again.",
};

const form = document.querySelector("[data-kit-form]");
const fallback = document.querySelector("[data-kit-fallback]");
const statusRegion = document.querySelector("[data-form-status]");

function showState(state) {
  if (form && state === "success") form.hidden = true;
  if (statusRegion) {
    statusRegion.dataset.state = state;
    statusRegion.textContent = STATUS_MESSAGES[state] || "";
    statusRegion.hidden = false;
  }
}

async function postToKit(uid, fields) {
  const url = KIT_POST_TEMPLATE.replace("{uid}", encodeURIComponent(uid));
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(fields),
  });
}

// Kit's endpoint answers a POST with a redirect to an HTML page (observed
// Oct 9, 2026: a JSON POST with a test form id landed on
// app.kit.com/forms/success with HTTP 200), so `response.ok` alone cannot
// tell success from rejection. Trust Kit's JSON status when the endpoint
// speaks JSON; otherwise judge by the URL the redirect landed on. Confirm
// both against the real embed snippet when it exists.
async function submitWorked(response) {
  if (!response.ok) return false;
  const data = await response.json().catch(() => null);
  if (data && typeof data.status === "string") return data.status === "success";
  return response.url.includes("/forms/success");
}

if (!form || !fallback) {
  console.error("kit-form: expected [data-kit-form] and [data-kit-fallback] in the document");
} else if (KIT_FORM_UID === "") {
  // Not wired yet: hide the fake-submit path, surface the real destination.
  form.replaceWith(fallback.content.cloneNode(true));
} else {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    try {
      const response = await postToKit(KIT_FORM_UID, {
        first_name: form.firstName.value,
        email: form.email.value,
      });
      showState((await submitWorked(response)) ? "success" : "error");
    } catch {
      showState("error"); // network failure reads the same as a rejection
    } finally {
      if (button) button.disabled = false;
    }
  });
}
