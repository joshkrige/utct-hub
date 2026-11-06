# Deploying updates automatically

The app lives on your hosting at `singa.studio/utct2026/`. After this one-time
setup, I push to GitHub and your server picks the change up on its own — you
never upload a file again, and the crew's link never changes.

## One-time setup

Open **cPanel → Terminal** (or SSH in) and run:

```bash
cd ~/public_html/utct2026

# keep the live race data, drop the hand-uploaded copies of the app
rm -f index.html sw.js manifest.webmanifest api.php README.md

git init -b main
git remote add origin https://github.com/joshkrige/utct-race-day.git
git fetch origin
git reset --hard origin/main

# the write token, kept out of the repo
printf '<?php return "c737-3c40-1d89-b36e";\n' > secret.php
chmod 600 secret.php
```

Then check `https://singa.studio/utct2026/api.php` still returns
`{"events":[...],"config":{...}}`. If it does, you're done.

## The cron job

**cPanel → Cron Jobs**, every 15 minutes (`*/15 * * * *`):

```
cd ~/public_html/utct2026 && /usr/bin/git pull --quiet origin main
```

Set the cron email to blank unless you want a message on every run.

## What is and isn't in the repo

| In git (replaced on every pull) | Not in git (yours, never touched) |
|---|---|
| `index.html` | `secret.php` — the write token |
| `api.php` | `data/` — every logged time and tick |
| `sw.js`, `manifest.webmanifest` | |

So a deploy can never wipe the race log, and the token is never public.

## On race day

Turn the cron off the day before, so nothing changes under your crew mid-race:

```
cPanel → Cron Jobs → delete (or comment out) the job
```

Turn it back on afterwards if you want it.
