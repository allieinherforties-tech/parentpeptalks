// Kit signup wiring for the Parent Pep Talks landing page.
//
// UID pasted from Allie's embed snippet, received Oct 20, 2026 (loader:
// https://parent-pep-talks.kit.com/10d73dff83/index.js — Cloudflare-gated
// against datacenter fetches, so field keys were verified against the live
// endpoint directly, see the POST notes below).
const KIT_FORM_UID = "10d73dff83"; // homepage inline form — live POST verified Oct 20, 2026

// Kit's custom-HTML embed posts to this template with the form UID filled in.
// Probed against the real form Oct 20, 2026:
//   - JSON POST {first_name, email} → 302 redirect to app.kit.com/forms/success
//     (reproduced twice; matches the Oct 9 observation).
//   - Kit's JSON-negotiated variant (POST /subscriptions.json) speaks a
//     stricter dialect: it wants email_address (not email), nests custom
//     fields under fields{}, and takes tags[] — that shape passed validation
//     on the live form. The plain route this page posts to accepted
//     {first_name, email}; if Kit ever tightens it, flip the key here first.
//   - Kit bot-quarantines datacenter/scripted requests on the .json route,
//     and during the Oct 20 session Kit returned "Account is cancelled and
//     can not accept new subscribers" on one probe — subscriber creation
//     could not be confirmed from here until the account billing/downgrade
//     (checklist step 1) is settled.
const KIT_POST_TEMPLATE = "https://app.kit.com/forms/{uid}/subscriptions";

const STATUS_MESSAGES = {
  success: "You're in. Your first note lands tomorrow morning — one short note a day, not a course. Rest tonight.",
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
  // Each page's [data-kit-fallback] template carries its own target — both
  // link straight to Kit's hosted page, no intermediate screen.
  form.replaceWith(fallback.content.cloneNode(true));
} else {
  // The homepage marks the two-step handoff with data-kit-redirect: wired
  // success leaves for /welcome with the signup fields riding the query
  // string, and page two takes over (prefill + profile form). Pages without
  // the attribute — /signup — keep the on-page confirmation.
  const handoff = form.dataset.kitRedirect;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    try {
      const fields = {
        first_name: form.firstName.value,
        email: form.email.value,
      };
      const response = await postToKit(KIT_FORM_UID, fields);
      if (await submitWorked(response)) {
        if (handoff) {
          const params = new URLSearchParams(fields);
          window.location.assign(`${handoff}?${params.toString()}`);
        } else {
          showState("success");
        }
      } else {
        showState("error");
      }
    } catch {
      showState("error"); // network failure reads the same as a rejection
    } finally {
      if (button) button.disabled = false;
    }
  });
}
