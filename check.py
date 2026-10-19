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
            'src="kit-form.js"',
            'src="assets/logo.png"',
            'src="assets/hero.webp"',
            'href="assets/favicon.png"',
            # While the UID is unwired, the homepage hands off to /signup.
            'href="signup"',
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
            'property="og:title" content="Parent Pep Talks"',
            'property="og:description" content="Sign up free — one short note in your inbox every morning, starting tomorrow."',
            'property="og:type" content="website"',
            'property="og:url" content="https://parentpeptalks.com/signup"',
            'property="og:image" content="https://parentpeptalks.com/assets/hero.webp"',
            'name="twitter:card" content="summary_large_image"',
            'name="twitter:title" content="Parent Pep Talks"',
            'name="twitter:description" content="Sign up free — one short note in your inbox every morning, starting tomorrow."',
            'name="twitter:image" content="https://parentpeptalks.com/assets/hero.webp"',
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
            'src="assets/logo.png"',
            'href="assets/favicon.png"',
            # While the UID is unwired, /signup's fallback hands off to Kit.
            "https://parent-pep-talks.kit.com",
        ],
    },
}

# The confirmation must speak the Day-1 register (Onboarding Arc, Day 1):
# tomorrow's note, no course-speak.
KIT_FORM_COPY = [
    "You're in. Your first note lands tomorrow morning — one short note a day, not a course. Rest tonight.",
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

for page_path, page in PAGES.items():
    source = Path(page_path)
    html = source.read_text(encoding="utf-8") if source.is_file() else ""
    if not html:
        errors.append(f"{page_path} is missing or empty")
        continue

    parser = Sanity()
    parser.feed(html)
    parser.close()
    if parser.stack:
        errors.append(f"{page_path}: unclosed tags: {parser.stack}")
    if parser.h1_count != 1:
        errors.append(f"{page_path}: expected exactly one <h1>, found {parser.h1_count}")

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

    for url in re.findall(r'(?:src|href)="([^"]+)"', html):
        if url.startswith(("http://", "https://")):
            if not url.startswith("https://"):
                errors.append(f"{page_path}: insecure absolute URL: {url}")
        elif url.endswith("/") or url.startswith(("#", "mailto:", "data:")):
            continue  # directory or non-file reference
        elif not (Path(url).is_file() or Path(url + ".html").is_file()):
            # GitHub Pages serves /signup from signup.html (clean links to an
            # existing .html file resolve), so mirror that tolerance here.
            errors.append(f"{page_path}: local reference does not exist: {url}")

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
print("check passed: doctype/tag balance, single h1, meta parity, links/assets, kit copy, no Airo references")
