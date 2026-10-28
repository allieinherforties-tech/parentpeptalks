"""Static-site sanity check: HTML structure, meta parity, links/assets, no Airo refs.

Lives here and, verbatim, inside .github/workflows/check.yml — the CI step
above the check fails when the two copies drift, so update both together,
byte-identical.
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Split here so this scan does not flag its own source (and the workflow that
# embeds it) as a live Airo reference.
AIRO_ASSET_PREFIX = "airo" + "-assets"

# Every page that must exist, and what each must contain. Strings match
# case-insensitively; meta and copy strings are enforced verbatim so edits
# that break shared tags or the signup copy fail here, not on the live site.
# index.html's strings mirror the live Airo page (captured Oct 9, 2026).
PAGES = {
    "index.html": {
        "required": [
            "<!doctype html",
            "<title>Parent Pep Talks — A daily note for tired parents</title>",
            'name="description" content="A thirty-second note in your inbox every morning. For the parent who\'s holding it together — mostly. Free daily email."',
            'rel="canonical" href="https://parentpeptalks.com/"',
            'property="og:title" content="Parent Pep Talks"',
            'property="og:description" content="A thirty-second note in your inbox every morning. For the parent who\'s holding it together — mostly."',
            'property="og:type" content="website"',
            'property="og:url" content="https://parentpeptalks.com"',
            'property="og:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            'name="twitter:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            'name="twitter:card" content="summary_large_image"',
            'name="twitter:title" content="Parent Pep Talks"',
            'name="twitter:description" content="A thirty-second note in your inbox every morning. For the parent who\'s holding it together — mostly."',
            "You're doing better than you think.",
            "A thirty-second note in your inbox every morning.",
            "For the parent who's mostly holding it together.",
            'placeholder="First name"',
            'placeholder="Email address"',
            "Send me the notes",
            "Free. No spam. Unsubscribe whenever.",
            "Made for the parents in the thick of it.",
            "© 2026 parentpeptalks.com",
            "data-kit-form",
            "data-kit-fallback",
            # Wired success leaves for page two; /welcome takes the handoff
            # (Two-Step Signup Build Sheet, Section 1).
            'data-kit-redirect="welcome"',
            'src="kit-form.js"',
            # Inline SVG lockup — cream variant over the band (navy fold lines).
            'class="logo-mark"',
            'aria-label="Parent Pep Talks — home"',
            'stroke="#0b192d"',
            'src="assets/hero-band.webp"',
            'href="assets/favicon.png"',
            # While the UID is unwired, the homepage fallback hands off straight
            # to Kit's hosted page — one hop, no /signup screen in between.
            'href="https://parent-pep-talks.kit.com"',
        ],
        # The homepage carries structured-data blocks; /signup stays minimal.
        "jsonld_types": ["Organization", "WebSite"],
    },
    "signup.html": {
        "required": [
            "<!doctype html",
            "<title>Parent Pep Talks — Sign up for the daily notes</title>",
            'name="description" content="Sign up free — one short note in your inbox every morning, starting tomorrow."',
            'rel="canonical" href="https://parentpeptalks.com/signup"',
            'property="og:title" content="A thirty-second note every morning"',
            'property="og:description" content="Sign up free — one short note in your inbox every morning, starting tomorrow."',
            'property="og:type" content="website"',
            'property="og:url" content="https://parentpeptalks.com/signup"',
            'property="og:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            'name="twitter:card" content="summary_large_image"',
            'name="twitter:title" content="A thirty-second note every morning"',
            'name="twitter:description" content="Sign up free — one short note in your inbox every morning, starting tomorrow."',
            'name="twitter:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            "You're doing better than you think.",
            'placeholder="First name"',
            'placeholder="Email address"',
            "Send me the notes",
            "Free. No spam. Unsubscribe whenever.",
            "Made for the parents in the thick of it.",
            "© 2026 parentpeptalks.com",
            "data-kit-form",
            "data-kit-fallback",
            'src="kit-form.js"',
            'href="styles.css"',
            # Inline SVG lockup — standard variant (bone fold lines).
            'class="logo-mark"',
            'aria-label="Parent Pep Talks — home"',
            'stroke="#f5f1ea"',
            'href="assets/favicon.png"',
            # While the UID is unwired, /signup's fallback hands off to Kit.
            "https://parent-pep-talks.kit.com",
        ],
    },
    "welcome.html": {
        "required": [
            "<!doctype html",
            "<title>Parent Pep Talks — You're in</title>",
            # Post-signup page: kept crawlable but noindexed (robots.txt does
            # not disallow it — a disallowed URL can still be indexed).
            'name="robots" content="noindex"',
            'name="description" content="You\'re in — your first note lands tomorrow morning. Finish your profile (every question is optional) to unlock the weekly child-insights email."',
            'rel="canonical" href="https://parentpeptalks.com/welcome"',
            'property="og:title" content="You\'re in."',
            'property="og:description" content="You\'re in — your first note lands tomorrow morning. Finish your profile to unlock the weekly child-insights email."',
            'property="og:type" content="website"',
            'property="og:url" content="https://parentpeptalks.com/welcome"',
            'property="og:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            'name="twitter:card" content="summary_large_image"',
            'name="twitter:title" content="You\'re in."',
            'name="twitter:description" content="You\'re in — your first note lands tomorrow morning. Finish your profile to unlock the weekly child-insights email."',
            'name="twitter:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            # Celebration header — the homepage's old on-page success line,
            # verbatim, moved here when the handoff shipped (Build Sheet §2).
            "You're in.",
            "Your first note lands tomorrow morning — one short note a day, not a course. Rest tonight.",
            "Now make it yours.",
            "Complete your profile to unlock the weekly child-insights email: one short email a week about your kid — what's normal for their age, what's worth a closer look, and what you can officially stop worrying about.",
            "Every question is optional. The daily note doesn't change either way — this just makes the weekly email possible.",
            "Not seeing the first note by breakfast tomorrow? Check spam, then add us to your contacts — after that, everything lands on time.",
            "This is where your notes go.",
            "Your kid's first name (first names only)",
            # Sibling rotation hint (Oct 22): one kid to start; siblings join
            # by replying to any note with names and birthdays.
            "Just one kid to start is plenty — if you've got more, reply to any note with their names and birthdays and we'll add them to the rotation.",
            "Your kid's birthday?",
            # Birth-date field (Oct 20 decision): the optional date input
            # replaces the age-band dropdown — the weekly child-insight derives
            # the band at send time from the Milestones sheet, and BDAY-01
            # triggers yearly off the collected date.
            'type="date"',
            "So the weekly note matches their exact age — and we never miss their birthday.",
            "What's the hardest part of most days right now?",
            # Hardest-part dropdown: the eight parent-facing chips, each saved
            # as a Tag.
            "Bedtime",
            "Mornings",
            "Mealtimes",
            "The mess",
            "My own patience",
            "Sibling fights",
            "Screen time",
            "Something else",
            "Finish the sentence: “The kind of parent I’m trying to be is…”",
            'maxlength="50"',
            "50 characters is plenty.",
            "How did you hear about us? (optional)",
            "Save my profile &amp; unlock the weekly insights",
            "data-kit-form",
            "data-kit-fallback",
            'src="welcome-form.js"',
            'href="styles.css"',
            # Inline SVG lockup — standard variant (bone fold lines).
            'class="logo-mark"',
            'aria-label="Parent Pep Talks — home"',
            'stroke="#f5f1ea"',
            'href="assets/favicon.png"',
            # While the profile UID is unwired, /welcome hands off to Kit.
            "https://parent-pep-talks.kit.com",
        ],
    },
    "sleep.html": {
        "required": [
            "<!doctype html",
            "<title>Is it a sleep regression — or the clock change? — Parent Pep Talks</title>",
            'name="description" content="Enter your kid\'s birth date and what\'s happening at night. Get the likely window — the 4-month regression, the 18-month wave, the clock change — and one script for tonight. Free, about 30 seconds."',
            'rel="canonical" href="https://parentpeptalks.com/sleep"',
            'property="og:title" content="Is it a sleep regression — or the clock change?"',
            'property="og:description" content="Enter your kid\'s birth date and what\'s happening at night. Get the likely window and one script for tonight. Free, about 30 seconds."',
            'property="og:type" content="website"',
            'property="og:url" content="https://parentpeptalks.com/sleep"',
            'property="og:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            'name="twitter:card" content="summary_large_image"',
            'name="twitter:title" content="Is it a sleep regression — or the clock change?"',
            'name="twitter:description" content="Enter your kid\'s birth date and what\'s happening at night. Get the likely window and one script for tonight. Free, about 30 seconds."',
            'name="twitter:image" content="https://parentpeptalks.com/assets/og-hero.webp"',
            # Plausible ships with the page (strategy prerequisite #2) —
            # event names live in sleep.js; this pins the loader.
            'data-domain="parentpeptalks.com"',
            'src="https://plausible.io/js/script.js"',
            "Something changed with their sleep. Let's find out what.",
            "How old is the bad sleeper?",
            "What's happening?",
            "The clock change scrambled everything",
            "Show me the likely window",
            "We never send the birth date anywhere — it stays in your browser.",
            # Capture — the homepage's verified contract, untouched.
            "data-kit-form",
            "data-kit-fallback",
            'data-kit-redirect="welcome"',
            'src="kit-form.js"',
            'src="sleep.js"',
            'href="styles.css"',
            # Inline SVG lockup — standard variant (bone fold lines).
            'class="logo-mark"',
            'aria-label="Parent Pep Talks — home"',
            'stroke="#f5f1ea"',
            'href="assets/favicon.png"',
            # While the UID is unwired, /sleep's fallback hands off to Kit.
            "https://parent-pep-talks.kit.com",
            'placeholder="First name"',
            'placeholder="Email address"',
            "Send me the notes",
            "Free. No spam. Unsubscribe whenever.",
            "Made for the parents in the thick of it.",
            "© 2026 parentpeptalks.com",
        ],
    },
    "notes/example/index.html": {
        "required": [
            "<!doctype html",
            "<title>The dishes can wait — Parent Pep Talks</title>",
            'name="robots" content="noindex"',
            'rel="canonical" href="https://parentpeptalks.com/notes/example/"',
            'name="description" content="A thirty-second note about the dishes that can wait until morning — and the parent who should too. This page is the template example, not a real note."',
            # The banner is what keeps the example honest — a page that has
            # stopped saying "template, not a real note" has stopped being one.
            "This page is the template, not a real note",
            "data-kit-form",
            "data-kit-fallback",
            # Note CTAs hand off to /welcome like the homepage form does —
            # a signup from any note gets the profile page too.
            'data-kit-redirect="welcome"',
            'src="../../kit-form.js"',
            'href="../../styles.css"',
            'href="../../assets/favicon.png"',
            "Send me the notes",
            "Free. No spam. Unsubscribe whenever.",
            "Made for the parents in the thick of it.",
            "© 2026 parentpeptalks.com",
        ],
        # The Article block is the archive's structured-data pattern.
        "jsonld_types": ["Article"],
    },
}

# The confirmation must speak the Day-1 register (Onboarding Arc, Day 1):
# tomorrow's note, no course-speak.
KIT_FORM_COPY = [
    "You're in. Your first note lands tomorrow morning — one short note a day, not a course. Rest tonight.",
    "That didn't go through. Give it a moment and try again.",
]

# The wired homepage success redirects to /welcome with the signup fields in
# the query string (Build Sheet Section 1); /welcome's confirmation copy lives
# in welcome-form.js. Strings match the source files byte-for-byte.
KIT_HANDOFF_COPY = ["data-kit-redirect"]

WELCOME_FORM_COPY = [
    "Saved. Your first note lands tomorrow morning — and the weekly child-insights email is on its way.",
    "That didn't go through. Give it a moment and try again.",
]

errors = []

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}


class Sanity(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        self.stack.append(tag)
        if tag == "h1":
            self.h1_count += 1

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            errors.append(f"closing </{tag}> with nothing open")
            return
        opened = self.stack.pop()
        if opened != tag:
            errors.append(f"<{opened}> closed by </{tag}>")


kit_form = Path("kit-form.js")
kit_source = kit_form.read_text(encoding="utf-8") if kit_form.is_file() else ""
for copy in KIT_FORM_COPY:
    if copy not in kit_source:
        errors.append(f"kit-form.js: missing required copy: {copy}")
for needle in KIT_HANDOFF_COPY:
    if needle not in kit_source:
        errors.append(f"kit-form.js: missing handoff wiring: {needle}")

welcome_form = Path("welcome-form.js")
welcome_source = welcome_form.read_text(encoding="utf-8") if welcome_form.is_file() else ""
for copy in WELCOME_FORM_COPY:
    if copy not in welcome_source:
        errors.append(f"welcome-form.js: missing required copy: {copy}")

# Structural sanity runs for EVERY HTML file in the repo — the notes archive
# included — so a broken page fails CI the day it lands, not when someone
# pins it here. Links and assets resolve relative to the page's own
# directory, the way the browser does (a note at notes/<slug>/ references
# ../../styles.css, which the old repo-root resolution could never see).
for html_path in sorted(Path(".").rglob("*.html")):
    if ".git" in html_path.parts:
        continue
    html = html_path.read_text(encoding="utf-8")

    parser = Sanity()
    parser.feed(html)
    parser.close()
    if parser.stack:
        errors.append(f"{html_path}: unclosed tags: {parser.stack}")
    if parser.h1_count != 1:
        errors.append(f"{html_path}: expected exactly one <h1>, found {parser.h1_count}")

    base = html_path.parent
    for url in re.findall(r'(?:src|href)="([^"]+)"', html):
        if url.startswith(("http://", "https://")):
            if not url.startswith("https://"):
                errors.append(f"{html_path}: insecure absolute URL: {url}")
        elif url.endswith("/") or url.startswith(("#", "mailto:", "data:")):
            continue  # directory or non-file reference
        elif not ((base / url).is_file() or (base / (url + ".html")).is_file()):
            # GitHub Pages serves /signup from signup.html (clean links to an
            # existing .html file resolve), so mirror that tolerance here.
            errors.append(f"{html_path}: local reference does not exist: {url}")

# Pinned strings stay per-page: shared tags and signup copy are enforced
# verbatim so edits that break them fail here, not on the live site.
for page_path, page in PAGES.items():
    source = Path(page_path)
    html = source.read_text(encoding="utf-8") if source.is_file() else ""
    if not html:
        errors.append(f"{page_path} is missing or empty")
        continue

    haystack = html.lower()
    for needle in page["required"]:
        if needle.lower() not in haystack:
            errors.append(f"{page_path}: missing required string: {needle}")

    expected_types = page.get("jsonld_types")
    if expected_types is not None:
        ld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        if len(ld_blocks) != len(expected_types):
            errors.append(f"{page_path}: expected {len(expected_types)} JSON-LD blocks, found {len(ld_blocks)}")
        else:
            found_types = []
            for block in ld_blocks:
                try:
                    found_types.append(json.loads(block).get("@type"))
                except json.JSONDecodeError as exc:
                    errors.append(f"{page_path}: JSON-LD does not parse: {exc}")
            if found_types and found_types != expected_types:
                errors.append(f"{page_path}: JSON-LD @type order wrong: {found_types}")

for path in Path(".").rglob("*"):
    if ".git" in path.parts or not path.is_file():
        continue
    if AIRO_ASSET_PREFIX in path.read_text(encoding="utf-8", errors="ignore").lower():
        errors.append(f"Airo asset reference in {path}")

if errors:
    print("CHECK FAILED:")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)
print("check passed: tag balance + one h1 on every page, meta parity, page-relative links/assets, kit copy, welcome handoff, no Airo references")
