"""Two crew phones, one page, two tabs — against the real PHP backend.
Either phone can log; both see the same board."""
import os, json, os, shutil, subprocess, sys, time
from playwright.sync_api import sync_playwright

SRC, RUN, PORT = "/home/claude", "/tmp/uitest", 8791
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "c737-3c40-1d89-b36e"
LINK = f"{BASE}/index.html#r={TOKEN}"

shutil.rmtree(RUN, ignore_errors=True); os.makedirs(RUN)
for f in ("index.html", "api.php", "sw.js", "manifest.webmanifest"):
    shutil.copy(os.path.join(SRC, f), RUN)
open(os.path.join(RUN, "secret.php"), "w").write('<?php return "c737-3c40-1d89-b36e";')
srv = subprocess.Popen(["php", "-S", f"127.0.0.1:{PORT}"], cwd=RUN,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)

errors, fails = [], []
def chk(name, cond, detail=""):
    print(("  ok  " if cond else "  XX  ") + name + (f" — {detail}" if detail else ""))
    if not cond: fails.append(name)

def api():
    return json.loads(subprocess.run(["curl", "-s", f"{BASE}/api.php"],
                                     capture_output=True, text=True).stdout)

try:
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        mk = lambda: br.new_context(viewport={"width": 390, "height": 844},
                                    device_scale_factor=2, has_touch=True, is_mobile=True,
                                    timezone_id="Africa/Johannesburg")
        c1, c2 = mk(), mk()                      # two different crew phones
        a, b = c1.new_page(), c2.new_page()
        for pg, tag in ((a, "A"), (b, "B")):
            pg.on("console", lambda m, t=tag: errors.append(f"[{t}] {m.text}")
                  if m.type == "error" else None)
            pg.on("pageerror", lambda e, t=tag: errors.append(f"[{t}] {e}"))

        print("\n== load ==")
        a.goto(LINK, wait_until="networkidle")
        b.goto(LINK, wait_until="networkidle")
        a.wait_for_timeout(1200); b.wait_for_timeout(1200)

        chk("opens on the Log tab", a.is_visible("#paneLog") and not a.is_visible("#paneBoard"))
        chk("three tabs present", a.locator(".tab").count() == 3)
        chk("backend live", a.inner_text("#syncChip").strip().lower() == "live",
            a.inner_text("#syncChip"))
        chk("button says START", "START" in a.inner_text("#bbVerb"), a.inner_text("#bbVerb"))

        print("\n== tab switching ==")
        a.click('.tab[data-pane="paneBoard"]'); a.wait_for_timeout(400)
        chk("Status tab shows the table", a.is_visible("#paneBoard") and not a.is_visible("#paneLog"))
        # every checkpoint but the start gets a row; derive it rather than
        # pinning a number that moves whenever the race book does
        rows_want = a.evaluate("CPS.length") - 1
        chk(f"{rows_want} checkpoints listed", a.locator("#cpBody tr").count() == rows_want,
            str(a.locator("#cpBody tr").count()))
        chk("crew-access flags shown", a.locator("#cpBody .crewtag").count() == rows_want)
        chk("plan label reads as a duration", "22h00" in a.inner_text("#planLab").lower(), a.inner_text("#planLab"))
        a.screenshot(path="/tmp/shot_board.png", full_page=True)
        a.click('.tab[data-pane="paneLog"]'); a.wait_for_timeout(400)
        chk("tab choice persists across reload",
            (a.reload(wait_until="networkidle"), a.wait_for_timeout(1200),
             a.is_visible("#paneLog"))[-1])

        print("\n== phone A logs him through ==")
        seq = []
        for i in range(6):
            seq.append(a.inner_text("#bbVerb") + "/" + a.inner_text("#bbPlace"))
            a.click("#bigBtn"); a.wait_for_timeout(300)
            if i == 0: chk("double-tap guard engages", a.is_disabled("#bigBtn"))
            a.wait_for_timeout(2600)
        print("   " + " -> ".join(seq))
        chk("alternates ARRIVES / LEAVES",
            seq[1].startswith("ARRIVES") and seq[2].startswith("LEAVES"), str(seq[1:3]))
        chk("first stop after the gun is Signal Hill", "Signal Hill" in seq[1], seq[1])
        # five button presses; a pass-through timing point logs in and out
        # together, so the server may hold one more event than presses
        n_ev = len(api()["events"])
        chk("every tap reached the server", 6 <= n_ev <= 7, str(n_ev))
        a.screenshot(path="/tmp/shot_log.png")

        print("\n== phone B sees it, and can log too ==")
        b.bring_to_front(); b.wait_for_timeout(9000)                  # B polls every 3s now
        b.click('.tab[data-pane="paneBoard"]'); b.wait_for_timeout(600)
        st = b.inner_text("#cStatus")
        chk("B's board followed A", "Table" in st or "Kloof" in st or "At " in st, st)
        chk("B shows a live projection", b.inner_text("#cFinish").strip() != "—",
            b.inner_text("#cFinish"))
        chk("B shows next crew point", b.inner_text("#cNextEta").strip() != "—",
            b.inner_text("#cNextEta").strip())
        b.click('.tab[data-pane="paneLog"]'); b.wait_for_timeout(500)
        before = len(api()["events"])
        b.click("#bigBtn"); b.wait_for_timeout(2000)
        chk("B can log as well as A", len(api()["events"]) == before + 1,
            f"{before} -> {len(api()['events'])}")
        chk("no duplicate cp+type",
            len({(e["cp"], e["type"]) for e in api()["events"]}) == len(api()["events"]))

        print("\n== 'he asked for' crosses between phones ==")
        a.click("#needsBtn"); a.wait_for_timeout(400)
        a.click('[data-need="Ice"]'); a.wait_for_timeout(250)
        a.click('[data-need="Coke"]'); a.wait_for_timeout(700)
        a.click("#dlgNeeds [data-close]"); a.wait_for_timeout(1500)
        b.bring_to_front(); b.wait_for_timeout(14000)
        b.click('.tab[data-pane="paneBoard"]'); b.wait_for_timeout(600)
        chk("B sees the request card", b.is_visible("#needsCard"))
        chk("request text crossed", "Ice" in b.inner_text("#needsTxt"), b.inner_text("#needsTxt"))

        print("\n== undo ==")
        before = len(api()["events"])
        a.click('.tab[data-pane="paneLog"]'); a.wait_for_timeout(300)
        a.click("#undoBtn"); a.wait_for_timeout(400)
        a.click("#cfGo"); a.wait_for_timeout(1500)
        chk("undo removed one event", len(api()["events"]) == before - 1,
            f"{before} -> {len(api()['events'])}")

        print("\n== wrong-station recovery ==")
        a.click("#fixBtn"); a.wait_for_timeout(400)
        hb = a.evaluate("CPS.findIndex(c => c.s === 'Hout Bay')")
        a.select_option("#fixCp", str(hb)); a.select_option("#fixState", "in")
        a.click("#fixGo"); a.wait_for_timeout(1500)
        chk("jumped to Hout Bay", "Hout Bay" in a.inner_text("#bbPlace"), a.inner_text("#bbPlace"))
        chk("now offers LEAVES", "LEAVES" in a.inner_text("#bbVerb"), a.inner_text("#bbVerb"))

        print("\n== offline tap is not lost ==")
        c1.set_offline(True); a.wait_for_timeout(500)
        a.click("#bigBtn"); a.wait_for_timeout(1500)
        chip = a.inner_text("#syncChip").lower()
        chk("chip warns", "send" in chip or "signal" in chip or "offline" in chip, chip)
        chk("queued locally",
            a.evaluate("JSON.parse(localStorage.getItem('utct.queue.v1')||'[]').length") >= 1)
        chk("UI advanced anyway", a.inner_text("#bbPlace").strip() != "", a.inner_text("#bbPlace"))
        c1.set_offline(False)
        a.evaluate("window.dispatchEvent(new Event('online'))"); a.wait_for_timeout(2500)
        chk("queue drained on reconnect",
            a.evaluate("JSON.parse(localStorage.getItem('utct.queue.v1')||'[]').length") == 0)
        chk("chip back to live", a.inner_text("#syncChip").strip().lower() == "live",
            a.inner_text("#syncChip"))

        print("\n== settings are open to everyone now ==")
        a.click("#cogBtn"); a.wait_for_timeout(400)
        fe = a.evaluate("document.activeElement.tagName")
        assert fe == "H3", "settings must focus the dialog, not a picker: "+fe
        print("ok  settings opens with no field focused")
        chk("target time editable", a.is_visible("#cfgTargetH") and a.is_visible("#cfgTargetM"))
        chk("reset available", a.is_visible("#cfgReset"))
        a.click("#dlgCfg [data-close]"); a.wait_for_timeout(300)

        print("\n== night mode + tap target ==")
        # Night mode arms itself between 18:00 and 06:00, so don't assume the
        # button turns it ON — assert that it toggles whatever it started as.
        before = a.evaluate("document.documentElement.dataset.night")
        a.click("#nightBtn"); a.wait_for_timeout(400)
        after = a.evaluate("document.documentElement.dataset.night")
        chk("night button toggles the theme", after != before, f"{before} -> {after}")
        a.click("#nightBtn"); a.wait_for_timeout(400)
        chk("and toggles back",
            a.evaluate("document.documentElement.dataset.night") == after.__class__(before),
            before)
        a.click("#nightBtn"); a.wait_for_timeout(400)   # leave it dark for the shot
        box = a.locator("#bigBtn").bounding_box()
        chk("button still big", box["height"] > 300 and box["width"] > 340,
            f'{int(box["width"])}x{int(box["height"])}px')
        a.screenshot(path="/tmp/shot_night.png")

        print("\n== reset clears both phones ==")
        a.click("#cogBtn"); a.wait_for_timeout(400)
        a.click("#cfgReset"); a.wait_for_timeout(400)
        a.click("#cfGo"); a.wait_for_timeout(2000)
        chk("server wiped", len(api()["events"]) == 0, str(len(api()["events"])))
        b.reload(wait_until="networkidle"); b.wait_for_timeout(1500)
        b.click('.tab[data-pane="paneBoard"]'); b.wait_for_timeout(500)
        chk("B's board cleared too",
            "Waiting" in b.inner_text("#cStatus") or "Starts in" in b.inner_text("#cStatus"),
            b.inner_text("#cStatus"))
        chk("deleted events stayed deleted", b.locator("#cpBody tr.past").count() == 0)
        br.close()
finally:
    srv.terminate()

print("\n== console ==")
errors = [e for e in errors if "ERR_INTERNET_DISCONNECTED" not in e]
if errors:
    for e in errors[:10]: print("  !!", e)
    fails.append(f"{len(errors)} console error(s)")
else:
    print("  no console errors on either phone")

print()
if fails:
    print(f"{len(fails)} FAILED:"); [print("  -", f) for f in fails]; sys.exit(1)
print("ALL UI CHECKS PASSED")
