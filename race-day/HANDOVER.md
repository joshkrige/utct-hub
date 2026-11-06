# UTCT Race Day — where things stand

Crew tracker for Josh Krige's UTCT UT100, **Sat 21 Nov 2026, 04:00**.
Live at `singa.studio/utct2026/`. Source: `joshkrige/utct-hub`, folder `race-day/`.

## Deploying

I push to the repo, then open
`https://singa.studio/utct2026/deploy.php?key=<token>` — it fetches the current
files from GitHub and writes them in about a second. The token is in
`secret.php` on the server and **must never be committed**; the repo is public.
A cPanel cron every 2 hours is the backstop.

## The app

One page, three tabs, no build step, no external dependencies (Leaflet is bundled).

- **Log in / out** — one big button. Walks all 11 checkpoints in order:
  tap as he arrives, tap as he leaves. Any crew phone can tap; entries are keyed
  by checkpoint + type so two people tapping the same thing counts once.
  2.5s double-tap guard, undo, and "Wrong station?" to correct a miss.
- **Status** — where he is, next crew point with a LEAVE NOW countdown, projected
  finish, per-stop tick-list of crew jobs, and every checkpoint with plan vs
  actual vs projected and cut-off margins.
- **Map** — official 2026 GPX. Simple SVG line map by default (works offline),
  or a topo/satellite/streets map. Position pin advances by *effort*
  (climbing ~7x, descent ~2x), so it crawls up Platteklip. 18 named OSM
  landmarks, 10 derived climb tops/bottoms, 3 timing points.

Offline-first: every tap saves locally and queues; the outbox drains when signal
returns. Polls every 3s while visible.

## Race facts in the app

99.17 km · 4,676 m D+ · 26 h limit · 04:00 Sat start. Crew-facing plan **22h00**
(Josh's own sub-20 goal is private and deliberately not in the app).
Cut-offs: Kloof Nek 08:00, Hout Bay 18:30, Alphen 23:00, Newlands 03:00,
finish 06:00. Crew points: Kloof Nek, Llandudno, Hout Bay (+ backup drop bag),
Alphen, Newlands. Signal Hill is tappable but crew have nothing to do there.
Table Mountain, Rocket Road, Constantia Glen are volunteer-only — Josh taps
those himself; each tap sharpens the projection.

## Open / in flight

1. **Attribution** — code is in (name per phone in Settings, stored with each
   tap, shown under the time on Status; `api.php` stores `by`). Needs testing.
2. **Loud cut-off warning** — agreed, not built. A breached or tight cut-off
   should be a banner on Status, not just a red number in the table.
3. **One-page PDF** — agreed, not built. Stops, cut-offs, drive times, for the
   glovebox.
4. **Hout Bay has 12 jobs against an 8-minute stop.** Josh is going to review
   the lists and cut.
5. **Installed-app key.** iOS gives a home-screen app its own storage, so a
   token learned in Safari is invisible to it. Current solution: the app shows
   "This phone can't log yet — tap to paste the crew link", once per device.
   Putting the token in the manifest would remove that step but would leak it
   into the public repo — rejected.

## Testing

`test_*.py` in the working directory drive a real browser against real PHP:
`test_ui` (two phones), `test_jobs`, `test_ticks`, `test_token`, `test_map`,
`test_topo`, `test_loggable`, `test_artifact_db`, and `test_eta.js` for the
projection maths. Run the ones a change touches, not all of them.
