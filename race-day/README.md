# UTCT Race Day — crew tracker

Lives at `singa.studio/utct2026/`. One link for the whole crew; any of them can
log Josh in and out of an aid station, and everyone sees the same board.

- `index.html` — the whole app: Log tab, Status tab, Map tab. No build step,
  no external dependencies (Leaflet is bundled). Works with no signal.
- `api.php` — ~140 line JSON backend, file-locked atomic writes.
- `sw.js`, `manifest.webmanifest` — offline shell and home-screen install.

Not in this repo, and never overwritten by a deploy:

- `secret.php` — the write token. One line: `<?php return 'your-token';`
- `data/` — the live race log.

See `DEPLOY.md` for the server setup and the cron job.
