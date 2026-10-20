// Kit profile wiring for /welcome — page two of the two-step signup
// (Two-Step Signup Build Sheet, Section 2).
//
// The profile form posts to its OWN Kit form endpoint so the homepage form's
// endpoint never touches profile data: the four custom fields (child name,
// child birth date, Goal 2, referral source) plus the hardest-part answer,
// which Kit saves as a Tag. UID pasted from Allie's embed snippet, received
// Oct 20, 2026 (loader: https://parent-pep-talks.kit.com/c6cf175e6d/index.js
// — Cloudflare-gated against datacenter fetches, so the embed could not be
// read from here).
//
// ⚠️ DELTA REPORTED Oct 20, 2026: Kit's subscriptions endpoint answered every
// POST to this UID with "Couldn't find a form for this request" — the UID does
// not resolve to a live (published) inline Form. The wiring below is real and
// follows the verified contract, but capture stays dead until the Kit-side
// form exists/publishes under this UID (or Allie sends a corrected UID).
const KIT_PROFILE_FORM_UID = "c6cf175e6d";

// Same endpoint template and success contract as the homepage form
// (kit-form.js): trust Kit's JSON status when the endpoint speaks JSON,
// otherwise judge by the URL the redirect landed on — never response.ok alone.
const KIT_POST_TEMPLATE = "https://app.kit.com/forms/{uid}/subscriptions";

const STATUS_MESSAGES = {
  success: "Saved. Your first note lands tomorrow morning — and the weekly child-insights email is on its way.",
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

// Mirrors kit-form.js: Kit's endpoint answers a POST with a redirect to an
// HTML page (observed Oct 9, 2026: a JSON POST with a test form id landed on
// app.kit.com/forms/success with HTTP 200), so response.ok alone cannot tell
// success from rejection.
async function submitWorked(response) {
  if (!response.ok) return false;
  const data = await response.json().catch(() => null);
  if (data && typeof data.status === "string") return data.status === "success";
  return response.url.includes("/forms/success");
}

// THE wiring-time mapping, against the only key vocabulary verified live
// (Oct 20, 2026, homepage form /subscriptions.json probe — validation passed):
//   {first_name, email_address, fields{...}, tags[...]}
// The plain route both pages post to accepted {first_name, email} (302 to
// /forms/success), so the scalars keep the build-sheet names. Custom fields
// nest under fields{} with underscored keys — Allie's four custom fields are
// named "Child name", "Child birth date", "Goal 2", "Referral source" (her
// checklist step 2); Kit derives the API keys by lowercasing and
// underscoring the names. That derivation is the one unverified link — it
// could not be read from the embed (Cloudflare) or probed (the profile form
// did not resolve). If Kit stores different keys, fix them here and in the
// embed mapping — one function, nothing else.
// The hardest-part answer is a Tag, not a field (it is a category), so it
// rides tags[] and only when chosen. Birth date rides as ISO YYYY-MM-DD,
// the native date-input format, per the Oct 20 decision.
function profilePayload(values) {
  const payload = {
    first_name: values.firstName,
    email: values.email,
    fields: {
      child_name: values.childName,
      child_birth_date: values.birthDate,
      goal_2: values.goal2,
      referral_source: values.referral,
    },
  };
  if (values.hardestPart) payload.tags = [values.hardestPart];
  return payload;
}

// first_name and email arrive as query params from the homepage's redirect
// (welcome?first_name=…&email=…). First name prefills editable; email prefills
// locked — it is the subscription key. Unknown params are ignored, and a
// direct visit with no params renders the same form empty and fully functional.
function prefillFromParams() {
  const params = new URLSearchParams(window.location.search);
  const firstName = params.get("first_name");
  const email = params.get("email");
  if (firstName) form.firstName.value = firstName;
  if (email) {
    form.email.value = email;
    form.email.readOnly = true;
    form.email.classList.add("field-locked");
  }
}

function wireCharacterCounter() {
  const counter = form.querySelector("[data-char-counter]");
  if (!counter) return;
  const goal = form.goal2;
  const render = () => { counter.textContent = `${goal.value.length} / ${goal.maxLength}`; };
  goal.addEventListener("input", render);
  render();
}

if (!form || !fallback) {
  console.error("welcome-form: expected [data-kit-form] and [data-kit-fallback] in the document");
} else if (KIT_PROFILE_FORM_UID === "") {
  // Not wired yet: every word of the page copy stays, and the profile form
  // gives way to Kit's hosted page — the same one-hop fallback the signup
  // pages use while their UID is unwired.
  form.replaceWith(fallback.content.cloneNode(true));
} else {
  prefillFromParams();
  wireCharacterCounter();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    try {
      const response = await postToKit(KIT_PROFILE_FORM_UID, profilePayload({
        firstName: form.firstName.value,
        email: form.email.value,
        childName: form.childName.value,
        birthDate: form.birthDate.value,
        hardestPart: form.hardestPart.value,
        goal2: form.goal2.value,
        referral: form.referral.value,
      }));
      showState((await submitWorked(response)) ? "success" : "error");
    } catch {
      showState("error"); // network failure reads the same as a rejection
    } finally {
      if (button) button.disabled = false;
    }
  });
}
