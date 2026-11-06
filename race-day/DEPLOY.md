# Deploying updates automatically

The app runs at `singa.studio/utct2026/`. After this one-time setup I push to
GitHub and your server picks the change up on its own — you never upload a file
again, and the crew's link never changes.

The app lives in the `race-day/` folder of **joshkrige/utct-hub**.

---

## One-time setup

Open **cPanel → Terminal** (or SSH) and run:

```bash
# 1. a working copy of the repo, outside the web root
git clone --depth 1 https://github.com/joshkrige/utct-hub.git ~/utct-src

# 2. the write token — stays on the server, never in git
cd ~/public_html/utct2026
printf '<?php return "c737-3c40-1d89-b36e";\n' > secret.php
chmod 600 secret.php

# 3. first copy across
cp -f ~/utct-src/race-day/index.html \
      ~/utct-src/race-day/api.php \
      ~/utct-src/race-day/sw.js \
      ~/utct-src/race-day/manifest.webmanifest \
      ~/public_html/utct2026/
```

**Step 2 is not optional.** The new `api.php` reads the token from `secret.php`.
Without that file every write is refused with a 403 and nobody can log anything.

Check it worked: open `https://singa.studio/utct2026/api.php`. You should see
`{"events":[...],"config":{...},"now":...}`. Then open the app and tap something.

---

## The cron job

**cPanel → Cron Jobs**, every 15 minutes (`*/15 * * * *`):

```
cd ~/utct-src && /usr/bin/git pull -q && cp -f race-day/index.html race-day/api.php race-day/sw.js race-day/manifest.webmanifest ~/public_html/utct2026/
```

Leave the cron email blank unless you want a message every 15 minutes.

The copy names each file explicitly rather than syncing the folder, so it can
never touch `secret.php` or `data/` no matter what ends up in the repo.

---

## What a deploy can and can't touch

| Replaced on every pull | Never touched |
|---|---|
| `index.html` | `secret.php` — the write token |
| `api.php` | `data/` — every logged time and tick |
| `sw.js`, `manifest.webmanifest` | |

So a deploy can't wipe the race log, and the token is never public.

---

## Race day

**Turn the cron off on the Friday.** You don't want the app changing under your
crew mid-race, however safe the change looks.

```
cPanel → Cron Jobs → delete the job (or set it to a date in the past)
```

Turn it back on afterwards if you want it.

---

## If something looks wrong after a deploy

Every version is a commit, so rolling back is one command:

```bash
cd ~/utct-src
git log --oneline -5                  # find the commit before the bad one
git checkout <that-commit> -- race-day/
cp -f race-day/*.html race-day/*.php race-day/*.js race-day/*.webmanifest ~/public_html/utct2026/
```

Phones may hold the old page for one load — the service worker fetches the
network copy first and falls back to cache, so a second open always gets the
current version.
