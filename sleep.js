// /sleep — the Sleep Disruption Calculator.
//
// Client-side only. The regression timeline lives in
// sleep/data/regression-timeline.json (fetched same-origin); this file
// computes the child's age in calendar months, filters the timeline, and
// renders the result card. The birth date never leaves the page — see the
// capture form below, which posts only the standard first name + email
// through the shared kit-form.js contract.
//
// Analytics (strategy prerequisite #2): Plausible custom events, fired via
// track() below. If the Plausible site doesn't exist on the account yet,
// window.plausible is undefined and tracking is a silent no-op.
//   sleep_result_shown      {mode: "regression"|"dst", window: <row id>}
//   sleep_capture_submitted {window: <row id>, success: <bool>}
// The capture outcome is observed by wrapping fetch — kit-form.js (shared
// with the homepage) owns the POST itself and resolves `fetch` at submit
// time, so this wrapper is in place long before any click. The wrapper
// passes every request through untouched and only inspects the Kit POST.

const DATA_URL = "sleep/data/regression-timeline.json";

// Milestones bands run 0–156 months; outside that, the tool says so honestly.
const MIN_AGE_MONTHS = 0;
const MAX_AGE_MONTHS = 156;

let timeline = null;
let selectedTrigger = null;
let lastWindowId = null;

const birthInput = document.querySelector("[data-birth-date]");
const chipsBox = document.querySelector("[data-chips]");
const computeButton = document.querySelector("[data-compute]");
const resultBox = document.querySelector("[data-result]");
const dstBanner = document.querySelector("[data-dst-banner]");

function track(name, props) {
  if (typeof window.plausible === "function") window.plausible(name, { props });
}

// Parse YYYY-MM-DD as a LOCAL date — DST is a local-clock fact, so the
// calculator must reason in the parent's own timezone, not UTC.
function parseLocalDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function ageInMonths(birth, reference) {
  let months =
    (reference.getFullYear() - birth.getFullYear()) * 12 +
    (reference.getMonth() - birth.getMonth());
  if (reference.getDate() < birth.getDate()) months -= 1;
  return months;
}

function isInDstWindow(now, dst) {
  const start = parseLocalDate(dst.activeWindow.start);
  const end = parseLocalDate(dst.activeWindow.end);
  return now >= start && now <= end;
}

chipsBox.addEventListener("click", (event) => {
  const chip = event.target.closest(".chip");
  if (!chip) return;
  const alreadySelected = chip.classList.contains("selected");
  chipsBox
    .querySelectorAll(".chip")
    .forEach((c) => c.classList.remove("selected"));
  if (!alreadySelected) chip.classList.add("selected");
  selectedTrigger = alreadySelected ? null : chip.dataset.trigger;
});

function showResultError(message) {
  resultBox.hidden = false;
  resultBox.replaceChildren();
  const p = document.createElement("p");
  p.className = "result-error";
  p.textContent = message;
  resultBox.append(p);
}

// The off-ramp is a real state, not an error: ages and symptoms the sourced
// timeline doesn't cover get an honest no, and the capture form stays.
function showOffRamp() {
  resultBox.hidden = false;
  resultBox.replaceChildren();
  const kicker = document.createElement("p");
  kicker.className = "result-kicker";
  kicker.textContent = "The honest answer";
  const title = document.createElement("h3");
  title.className = "result-title";
  title.textContent = "That one's outside what this tool knows yet.";
  const body = document.createElement("p");
  body.className = "result-summary";
  body.textContent =
    "We built the eight windows we could source well first, and yours isn't one of them (yet). The daily notes are still for you.";
  resultBox.append(kicker, title, body);
}

function renderResult(row, alternate, script) {
  const mode = row.triggers.includes("clock-shift") ? "dst" : "regression";
  resultBox.hidden = false;
  resultBox.replaceChildren();

  const kicker = document.createElement("p");
  kicker.className = "result-kicker";
  kicker.textContent =
    mode === "dst" ? "The likely window — the clock change" : "The likely window";

  const title = document.createElement("h3");
  title.className = "result-title";
  title.textContent = row.title;

  const age = document.createElement("p");
  age.className = "result-band";
  age.textContent = row.ageBand;

  const summary = document.createElement("p");
  summary.className = "result-summary";
  summary.textContent = row.summary;

  const why = document.createElement("p");
  why.className = "result-why";
  why.textContent = "What's behind it: " + row.why;

  const duration = document.createElement("p");
  duration.className = "result-duration";
  const strong = document.createElement("strong");
  strong.textContent = "How long this lasts: ";
  duration.append(strong, document.createTextNode(row.durationWeeks));

  const scriptLabel = document.createElement("p");
  scriptLabel.className = "script-label";
  scriptLabel.textContent = "Tonight's script — " + script.label;

  const scriptBody = document.createElement("div");
  scriptBody.className = "script-block";
  const scriptText = document.createElement("p");
  scriptText.textContent = script.body;
  scriptBody.append(scriptText);

  resultBox.append(
    kicker,
    title,
    age,
    summary,
    why,
    duration,
    scriptLabel,
    scriptBody
  );

  if (alternate) {
    const alt = document.createElement("p");
    alt.className = "result-alt";
    alt.textContent =
      "Or it could be: " + alternate.title + " (" + alternate.ageBand + ").";
    resultBox.append(alt);
  }

  lastWindowId = row.id;
  track("sleep_result_shown", { mode, window: row.id });
}

function matchWindows(ageMonths, trigger, now) {
  // The clock-change chip always leads with the DST plan for the side of the
  // change we're on; early waking inside the DST window rides it too (spec).
  if (trigger === "clock-shift") {
    const leadId =
      now < parseLocalDate(timeline.dst.changeDate) ? "R-DST-01" : "R-DST-02";
    return [
      timeline.windows.find((w) => w.id === leadId),
      timeline.windows.find(
        (w) => w.id !== leadId && w.triggers.includes("clock-shift")
      ),
    ];
  }

  const ageMatches = timeline.windows.filter(
    (w) =>
      !w.triggers.includes("clock-shift") &&
      w.bandStartMonths <= ageMonths &&
      ageMonths <= w.bandEndMonths
  );
  const ranked = ageMatches
    .slice()
    .sort(
      (a, b) =>
        Number(b.triggers.includes(trigger)) -
          Number(a.triggers.includes(trigger)) ||
        a.bandStartMonths - b.bandStartMonths
    );

  if (trigger === "early-rising" && isInDstWindow(now, timeline.dst)) {
    const dstRow = timeline.windows.find((w) =>
      w.triggers.includes("early-rising")
    );
    if (dstRow) ranked.unshift(dstRow);
  }
  return ranked;
}

function compute() {
  if (!timeline) {
    showResultError(
      "The sleep window data didn't load. Refresh in a moment — or the daily notes below are still for you."
    );
    return;
  }
  const now = new Date();
  const birthValue = birthInput.value;
  if (!birthValue) {
    showResultError("Pick a birth date first — the window depends on the age.");
    return;
  }
  const birth = parseLocalDate(birthValue);
  if (birth > now) {
    showResultError(
      "That date's ahead of them — pick the day they were actually born."
    );
    return;
  }
  if (!selectedTrigger) {
    showResultError(
      "Pick what's happening — that's the part that picks the window."
    );
    return;
  }

  const ageMonths = ageInMonths(birth, now);
  if (ageMonths < MIN_AGE_MONTHS || ageMonths > MAX_AGE_MONTHS) {
    showOffRamp();
    return;
  }

  const [lead, alternate] = matchWindows(ageMonths, selectedTrigger, now);
  if (!lead) {
    showOffRamp();
    return;
  }

  const script = timeline.scripts.find((s) => s.id === lead.script);
  renderResult(lead, alternate, script);
}

// Capture outcome reporting: see the header comment. Every request passes
// through untouched; only the Kit POST is inspected, and its own resolution
// is never altered — kit-form.js keeps full ownership of success handling.
const KIT_POST_URL = "https://app.kit.com/forms/10d73dff83/subscriptions";
const nativeFetch = window.fetch;
window.fetch = function (input, init) {
  const promise = nativeFetch.apply(this, arguments);
  try {
    const url = typeof input === "string" ? input : input && input.url;
    if (init && init.method === "POST" && url === KIT_POST_URL) {
      promise
        .then(async (response) => {
          let worked = false;
          if (response.ok) {
            const data = await response.clone().json().catch(() => null);
            worked =
              data && typeof data.status === "string"
                ? data.status === "success"
                : response.url.includes("/forms/success");
          }
          track("sleep_capture_submitted", {
            window: lastWindowId || "unknown",
            success: worked,
          });
        })
        .catch(() =>
          track("sleep_capture_submitted", {
            window: lastWindowId || "unknown",
            success: false,
          })
        );
    }
  } catch {
    // Reporting must never break the form — swallow only the inspection,
    // not the request itself.
  }
  return promise;
};

(async function init() {
  try {
    const response = await nativeFetch(DATA_URL);
    if (!response.ok) throw new Error("HTTP " + response.status);
    timeline = await response.json();
  } catch {
    showResultError(
      "The sleep window data didn't load. Refresh in a moment — or the daily notes below are still for you."
    );
    return;
  }

  const now = new Date();
  if (isInDstWindow(now, timeline.dst)) {
    dstBanner.hidden = false;
    const dstChip = chipsBox.querySelector('[data-trigger="clock-shift"]');
    if (dstChip) dstChip.classList.add("featured");
  }

  birthInput.max = now.toISOString().slice(0, 10);
  computeButton.disabled = false;
})();

computeButton.disabled = true;
computeButton.addEventListener("click", compute);
