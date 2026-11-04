// /normal — Is This Normal? Checker.
//
// Two JSON files power this page, fetched at load and never sent anywhere:
//   assets/normal-data.json      — generated from the Milestones sheet by
//                                  tools/export_normal_data.py; never edit it.
//   assets/normal-editorial.json — the human-editable layer: the 48 approved
//                                  concern lines, search keywords, confidence
//                                  phrases, and the per-band counters.
//
// The only other network call is the Kit signup, posted by kit-form.js; this
// file wraps window.fetch to observe that POST for the analytics funnel.
// Events follow the MVP spec (art_OFGP554H); the spec's checker_concern_select
// is folded into checker_result_show's `mode` prop (chip | search) so each
// interaction lands as exactly one event.

const DATA_URL = "assets/normal-data.json";
const EDITORIAL_URL = "assets/normal-editorial.json";
const KIT_POST_URL = "app.kit.com/forms/";

// Result-line templates for rows without an approved editorial line.
// Concerns are quoted verbatim (never rewritten) so the template stays
// grammatical for any sheet text. The register follows the editorial
// layer's rules: reassurance first, never a diagnosis.
const TEMPLATES = {
  milestone: (concern) =>
    `Short answer: yes — for this band, "${concern}" is a typical skill.`,
  trigger: (concern) =>
    `Heads-up territory: "${concern}" is a known transition for this band — expected when it arrives, and a wave that passes.`,
};

const FALLBACK_WHY = "Checked against the developmental framework — reassurance first, technique second.";

const state = {
  data: null,
  editorial: null,
  band: null,
  lastItem: null,
};

const el = {
  bandChips: document.querySelector("[data-band-chips]"),
  bandLoading: document.querySelector("[data-band-loading]"),
  ageMonths: document.querySelector("[data-age-months]"),
  ageOfframp: document.querySelector("[data-age-offramp]"),
  behavior: document.querySelector("[data-behavior]"),
  concernChips: document.querySelector("[data-concern-chips]"),
  milestoneChips: document.querySelector("[data-milestone-chips]"),
  search: document.querySelector("[data-search]"),
  searchSubmit: document.querySelector("[data-search-submit]"),
  searchError: document.querySelector("[data-search-error]"),
  result: document.querySelector("[data-result]"),
  counterNote: document.querySelector("[data-counter-note]"),
};

function track(name, props) {
  if (typeof window.plausible === "function") {
    window.plausible(name, { props });
  }
}

// Mirrors kit-form.js submitWorked(): Kit answers a JSON POST with a redirect
// to an HTML success page, so ok alone cannot tell success from rejection.
function captureWorked(response) {
  if (!response.ok) return false;
  return response.url.includes("/forms/success");
}

function watchCapture() {
  const nativeFetch = window.fetch;
  if (!nativeFetch) return;
  window.fetch = function (...args) {
    const promise = nativeFetch.apply(this, args);
    const url = typeof args[0] === "string" ? args[0] : args[0] && args[0].url;
    if (url && url.includes(KIT_POST_URL)) {
      promise
        .then((response) => {
          track("checker_capture_success", {
            success: captureWorked(response),
            item: state.lastItem || "none",
          });
        })
        .catch(() => {
          track("checker_capture_success", { success: false, item: state.lastItem || "none" });
        });
    }
    return promise;
  };
}

async function loadData() {
  const [data, editorial] = await Promise.all([
    fetch(DATA_URL).then((response) => {
      if (!response.ok) throw new Error(`data ${response.status}`);
      return response.json();
    }),
    fetch(EDITORIAL_URL).then((response) => {
      if (!response.ok) throw new Error(`editorial ${response.status}`);
      return response.json();
    }),
  ]);
  state.data = data;
  state.editorial = editorial;
}

// Age-band resolution, per the MVP spec's boundary examples: the last band
// whose range contains the month, so a 9-month-old lands in 9–18 months and
// a 36-month-old in 3–5 years. The final band includes its own end (156).
function bandFor(months) {
  const bands = state.data.bands;
  let match = null;
  for (const band of bands) {
    if (months >= band.start && months <= band.end) match = band;
  }
  return match;
}

function bandItems(band) {
  return state.data.items.filter(
    (item) => item.bandStart === band.start && item.bandEnd === band.end
  );
}

function chipButton(label) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip";
  chip.textContent = label;
  return chip;
}

function setSelected(chips, target) {
  for (const chip of chips.querySelectorAll("button.chip")) {
    const selected = chip === target;
    // Class carries the style (the shared .chip.selected rule); aria-pressed
    // carries the state to assistive tech.
    chip.classList.toggle("selected", selected);
    chip.setAttribute("aria-pressed", String(selected));
  }
}

function renderBands() {
  el.bandLoading.remove();
  for (const band of state.data.bands) {
    const chip = chipButton(band.label);
    chip.dataset.bandId = band.id;
    chip.addEventListener("click", () => {
      selectBand(band, "chip", chip);
    });
    el.bandChips.append(chip);
  }
}

function selectBand(band, via, chip) {
  state.band = band;
  el.ageOfframp.hidden = true;
  if (chip) setSelected(el.bandChips, chip);
  renderBehavior(band);
  el.behavior.hidden = false;
  track("checker_age_submit", { band: band.id, via });
}

function renderBehavior(band) {
  el.concernChips.replaceChildren();
  el.milestoneChips.replaceChildren();
  for (const item of bandItems(band)) {
    const chip = chipButton(item.concern);
    chip.addEventListener("click", () => {
      setSelected(el.concernChips, chip);
      setSelected(el.milestoneChips, null);
      showResult(item, "chip");
    });
    if (item.category === "Common parent concern") {
      el.concernChips.append(chip);
    } else {
      el.milestoneChips.append(chip);
    }
  }
}

// Keyword search within the selected band. Every query token must appear in
// the item's concern text or keywords — the editorial layer carries the
// synonyms parents actually type.
const QUERY_STOPWORDS = new Set([
  "the", "and", "for", "with", "that", "this", "what", "when", "how", "why",
  "about", "after", "before", "during", "their", "they", "them", "she", "her",
  "his", "him", "you", "your", "kid", "kids", "child", "son", "daughter",
  "baby", "toddler", "normal", "typical", "worried", "worry", "keeps",
  "keep", "just", "only", "still", "always", "every", "really", "since",
  "because", "should", "would", "could", "does", "doesn", "didn", "isn",
  "aren", "wasn", "won", "don", "cant", "wont", "not", "but", "from",
  "into", "onto", "over", "under", "then", "than", "ours",
]);

function searchTokens(query) {
  return query
    .toLowerCase()
    .split(/[^a-z0-9']+/)
    .filter((token) => token.length >= 3 && !/^\d+$/.test(token) && !QUERY_STOPWORDS.has(token));
}

function findMatches(band, query) {
  const tokens = searchTokens(query);
  if (tokens.length === 0) return [];
  const matches = [];
  for (const item of bandItems(band)) {
    const editorial = state.editorial.items[item.id] || {};
    const keywords = (editorial.keywords || []).join(" ").toLowerCase();
    const concern = item.concern.toLowerCase();
    const haystack = `${concern} ${keywords}`;
    // Rank by how many of the parent's words land; requiring every word
    // (tokens.every) made natural queries like "biting at daycare" return nothing.
    const inHaystack = tokens.filter((token) => haystack.includes(token)).length;
    if (inHaystack === 0) continue;
    const inConcern = tokens.filter((token) => concern.includes(token)).length;
    const isConcernRow = item.category === "Common parent concern" ? 5 : 0;
    matches.push({ item, score: inConcern * 100 + inHaystack * 10 + isConcernRow });
  }
  matches.sort((a, b) => b.score - a.score || a.item.id.localeCompare(b.item.id));
  return matches.map((match) => match.item);
}

function normalLine(item) {
  const editorial = state.editorial.items[item.id] || {};
  if (editorial.normal) return editorial.normal;
  if (item.category === "Trigger moment") return TEMPLATES.trigger(item.concern);
  return TEMPLATES.milestone(item.concern);
}

function addLine(parent, className, text) {
  const line = document.createElement("p");
  line.className = className;
  line.textContent = text;
  parent.append(line);
  return line;
}

function showSafetyNet(result) {
  const label = document.createElement("p");
  label.className = "script-label";
  label.textContent = "And the one thing we always say:";
  const block = document.createElement("div");
  block.className = "script-block";
  addLine(block, "", state.editorial.safetyNet);
  result.append(label, block);
}

function showResult(item, mode) {
  state.lastItem = item.id;
  const why = state.editorial.confidenceShort[item.confidence] || FALLBACK_WHY;
  const counter = state.editorial.counters[state.band.id] || "";

  el.result.replaceChildren();
  addLine(el.result, "result-kicker", "The short version");
  addLine(el.result, "result-title", item.concern);
  addLine(el.result, "result-band", item.band);
  addLine(el.result, "result-summary", normalLine(item));
  addLine(el.result, "result-why", `Why we're not worried: ${why}`);
  if (counter) addLine(el.result, "result-counter", counter);
  showSafetyNet(el.result);

  el.result.hidden = false;
  el.counterNote.hidden = !counter;
  el.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  track("checker_result_show", { item: item.id, mode });
}

function showNoMatch(query) {
  state.lastItem = null;
  const noMatch = state.editorial.noMatch;
  el.result.replaceChildren();
  addLine(el.result, "result-kicker", "The honest version");
  addLine(el.result, "result-title", noMatch.title);
  addLine(el.result, "result-band", state.band.label);
  addLine(el.result, "result-summary", noMatch.body);
  const counter = state.editorial.counters[state.band.id] || "";
  if (counter) addLine(el.result, "result-counter", counter);
  showSafetyNet(el.result);

  el.result.hidden = false;
  el.counterNote.hidden = !counter;
  el.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  track("checker_no_match_show", { term: query.trim().slice(0, 100) });
}

function runSearch() {
  const query = el.search.value;
  if (searchTokens(query).length === 0) {
    // All filler words — nothing to match on. Inline hint, not a result card.
    el.searchError.hidden = false;
    return;
  }
  el.searchError.hidden = true;
  const matches = findMatches(state.band, query);
  if (matches.length === 0) {
    showNoMatch(query);
    return;
  }
  setSelected(el.concernChips, null);
  setSelected(el.milestoneChips, null);
  showResult(matches[0], "search");
  if (matches.length > 1) {
    const alts = matches.slice(1, 4).map((match) => `"${match.concern}"`).join(" · ");
    addLine(el.result, "result-alt", `Or maybe: ${alts}`);
  }
}

function showLoadError() {
  el.bandLoading.remove();
  const error = document.createElement("p");
  error.className = "result-error";
  error.textContent = "The checker couldn't load just now. Give it a moment and try again.";
  const retry = chipButton("Try again");
  retry.addEventListener("click", () => window.location.reload());
  el.bandChips.append(error, retry);
}

function watchMonths() {
  el.ageMonths.addEventListener("change", () => {
    const months = Number.parseInt(el.ageMonths.value, 10);
    if (Number.isNaN(months)) return; // cleared field — leave the band as-is
    if (months < 0 || months > 156) {
      el.ageOfframp.hidden = false;
      return;
    }
    const band = bandFor(months);
    if (!band) {
      el.ageOfframp.hidden = false;
      return;
    }
    el.ageOfframp.hidden = true;
    if (!state.band || state.band.id !== band.id) {
      const chip = el.bandChips.querySelector(`[data-band-id="${band.id}"]`);
      selectBand(band, "months", chip);
    }
  });
}

function init() {
  watchCapture();
  loadData()
    .then(() => {
      renderBands();
      watchMonths();
    })
    .catch(() => showLoadError());

  el.searchSubmit.addEventListener("click", () => {
    if (!state.band) return;
    runSearch();
  });
  el.search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (state.band) runSearch();
    }
  });
}

init();
