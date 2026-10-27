# The notes archive

Every daily pep talk gets a page here: `/notes/<slug>/`. The email is the
product; these pages are how a tired parent who has never heard of us finds
one note at three in the morning, reads it, and joins the list. One note per
directory, no build step, no framework — the same hand-maintained static site
as the rest of parentpeptalks.com.

## The pattern every note page follows

- **URL** — `/notes/<slug>/`. A directory with an `index.html` inside; GitHub
  Pages serves it as a clean URL with nothing configured.
- **Title** — `<title>The dishes can wait — Parent Pep Talks</title>`. The
  note's own title first, the brand after the em dash. No keyword stuffing;
  the title is the note, not a search query.
- **Description** — one sentence a person would actually say out loud about
  this note. If it reads like ad copy, rewrite it.
- **Kicker** — the date and the category, set small above the title.
- **Body** — the note itself, in the site's Georgia serif. Short. It is
  thirty seconds of someone's morning.
- **Signup CTA** — the last thing on the page, every time, wired through
  `kit-form.js` with `data-kit-redirect="welcome"` so a signup from any note
  lands on the profile page like a homepage signup does.
- **Structured data** — one `Article` JSON-LD block (headline, datePublished,
  author, url). It is how the archive reads as an archive to search engines.

## Categories

Use the same eight words the welcome form uses for its hardest-part question:
Bedtime, Mornings, Mealtimes, The mess, My own patience, Sibling fights,
Screen time, Something else. One note, one category. That list is already
saved as Kit Tags on every subscriber who answers it — when category pages
come (they are a later milestone, see the 90-Day Growth Plan), the archive
vocabulary and the list-segmentation vocabulary are already the same words.

## Publishing a note (the whole flow)

1. Copy the example: `cp -r notes/example notes/<slug>/`.
2. Replace every `FILL:` comment in `notes/<slug>/index.html` — slug, date,
   category, title, description, body, prev/next links, canonical URL.
3. Delete the example banner paragraph and the
   `<meta name="robots" content="noindex">` line. The example wears both so
   it can never pass as a real note; a real note must never wear them.
4. Add `https://parentpeptalks.com/notes/<slug>/` to `sitemap.xml` (it is
   hand-maintained on purpose — there are exactly two other entries).
5. Commit and push. Pages redeploys in a minute or two.

Slug rules: lowercase, hyphens, three to six words, no dates — the slug
names the feeling (`the-dishes-can-wait`), not the day it shipped. A slug
that only makes sense today will still make sense in year three.

## What the CI check does for you

`check.py` (embedded byte-identical in `.github/workflows/check.yml`) runs on
every push and validates **every HTML file in the repo** — notes included —
for balanced tags, exactly one `<h1>`, and local links/assets that resolve
relative to the page. You do not touch check.py to publish a note. The
example page is additionally pinned by exact strings (banner, noindex,
canonical), so if the template pattern ever drifts, CI says so.

## Deliberately not here yet

No archive index at `/notes/`, no prev/next automation, no RSS. Each note
page links to its neighbors by hand for now. The 90-Day Growth Plan document
sequences those — an empty-looking index page is worse than none, so the
index ships when there are enough real notes to make it warm.
