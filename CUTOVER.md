# Cutover checklist — moving parentpeptalks.com to this static site

Run this when you choose go-live. Nothing here is done in advance: the live
site keeps running on GoDaddy Airo until step 3 flips DNS, and flipping back
is a two-minute undo (see Rollback).

**State this checklist assumes (verified Oct 9, 2026):**

- The repo is public (`gh repo view --json visibility` → `PUBLIC`), so GitHub
  Pages is available free. Pages is not yet enabled (`has_pages` false).
- The live apex `parentpeptalks.com` and `www` both resolve to `160.153.0.185`
  (GoDaddy Airo; `www` is an A record, not a CNAME).
- GitHub Pages apex A records, from GitHub's docs ("Managing a custom domain
  for your GitHub Pages site"): `185.199.108.153`, `185.199.109.153`,
  `185.199.110.153`, `185.199.111.153`.

## 1. Enable GitHub Pages (does not touch the live site)

1. GitHub repo → **Settings** → **Pages**.
2. "Build and deployment" → Source: **Deploy from a branch**; Branch: **main**,
   folder **/ (root)**. Save.
3. Wait for the "pages build and deployment" action to go green (Actions tab).
4. Open `https://allieinherforties-tech.github.io/parentpeptalks/` — the page
   should render with hero, tagline, and the signup area. (Until the Kit form
   is wired, that area shows the fallback button linking to
   `https://daily.parentpeptalks.com`.)

## 2. Attach the custom domain in GitHub (still not touching DNS)

1. Settings → Pages → Custom domain → `parentpeptalks.com` → Save.
2. GitHub adds a `CNAME` file to the repo root automatically (an expected
   commit on main — keep it).
3. The DNS check now shows as failing. Expected — the records still point at
   Airo.

Do this Pages-domain step **before** the DNS step: GitHub's docs warn that
configuring DNS first leaves a window in which someone else could claim the
domain on Pages (domain-takeover risk).

## 3. Flip the DNS records at GoDaddy

GoDaddy → My Products → Domains → `parentpeptalks.com` → DNS → DNS Records.

| Type  | Name | Current                  | Change to                         |
| ----- | ---- | ------------------------ | --------------------------------- |
| A     | @    | 160.153.0.185 (Airo)     | 185.199.108.153                   |
| A     | @    | — (add)                  | 185.199.109.153                   |
| A     | @    | — (add)                  | 185.199.110.153                   |
| A     | @    | — (add)                  | 185.199.111.153                   |
| A→CNAME | www | A → 160.153.0.185 (Airo) | CNAME → allieinherforties-tech.github.io |

1. Edit the existing `A` record `@` from `160.153.0.185` to
   `185.199.108.153`.
2. Add three more `A` records `@` for the other three IPs.
3. Change `www` from its current A record (→ 160.153.0.185) to a CNAME
   pointing at `allieinherforties-tech.github.io` — the bare `github.io`
   domain, without the repository name, is what GitHub expects. (If GoDaddy
   will not let you change the record type, delete the A record and add a
   fresh CNAME.)
4. **Do not touch anything else** — MX/TXT records (email, verification,
   DKIM/SPF for Kit) must stay.

5. Leave the TTL at the default (~600 seconds) so rollback stays fast.
6. Optional IPv6 (AAAA) records, if GoDaddy's editor offers them:
   `2606:50c0:8000::153` through `2606:50c0:8003::153`.

Propagation is usually minutes; officially it can take up to 24–48 hours.

## 4. Verify after the flip

1. `dig +short parentpeptalks.com A` → the four GitHub Pages IPs above.
   (Windows PowerShell: `Resolve-DnsName parentpeptalks.com`.)
2. `dig +short www.parentpeptalks.com CNAME` →
   `allieinherforties-tech.github.io`.
3. Settings → Pages: the custom-domain check turns green; once the
   certificate is issued (can take up to 24 hours), tick **Enforce HTTPS**.
4. In a private/incognito window, open `https://parentpeptalks.com`:
   - hero image, "You're doing better than you think.", tagline, footer all
     present;
   - view-source (Ctrl+U) shows no references to Airo's asset CDN;
   - the signup area shows either the wired form or the fallback link to
     `https://daily.parentpeptalks.com`.
5. Once `daily.parentpeptalks.com` is live, confirm the fallback link lands
   on the Kit signup page.

## Rollback (any time before you're happy)

In GoDaddy DNS: set the `A` `@` record back to `160.153.0.185` and change
`www` back to an A record → `160.153.0.185`. The Airo site returns as soon
as the TTL expires. Optionally remove the custom domain in GitHub Pages
settings afterwards.

## After cutover

- Every push to `main` redeploys the site automatically (1–2 minutes).
- Keep the GoDaddy/Airo hosting until search traffic has moved, then let it
  lapse.
