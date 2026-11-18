import os, subprocess, shutil, os, time, sys
from playwright.sync_api import sync_playwright
RUN="/tmp/sm4"; shutil.rmtree(RUN, ignore_errors=True); os.makedirs(RUN)
for f in ("index.html","api.php"): shutil.copy("/home/claude/"+f, RUN)
open(os.path.join(RUN, "secret.php"), "w").write('<?php return "c737-3c40-1d89-b36e";')
srv=subprocess.Popen(["php","-S","127.0.0.1:8811"],cwd=RUN,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(2); fails=[]; errs=[]
def chk(n,c,d=""):
    print(("  ok  " if c else "  XX  ")+n+(f" — {d}" if d else ""))
    if not c: fails.append(n)
try:
    with sync_playwright() as p:
        br=p.chromium.launch(args=["--no-sandbox"])
        pg=br.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True,
                          timezone_id="Africa/Johannesburg").new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
        pg.goto("http://127.0.0.1:8811/index.html#r=c737-3c40-1d89-b36e", wait_until="networkidle")
        pg.wait_for_timeout(1400)
        pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(600)
        lab=lambda: pg.inner_text("#jobsLab").lower()
        chk("jobs card visible pre-race", pg.is_visible("#jobsCard"))
        chk("pre-race shows Start jobs", "start" in lab(), lab())
        chk("no drop bag anywhere in Start jobs", "drop bag" not in pg.inner_text("#jobsCard").lower())
        chk("maps link present", pg.is_visible("#jobsMap"))
        chk("rules: 6 + emergency", (pg.click("#rulesBtn"), pg.wait_for_timeout(450),
             pg.locator("#rulesBody h4").count()==6 and "MYSOS" in pg.inner_text("#dlgRules"))[-1])
        pg.click("#dlgRules [data-close]"); pg.wait_for_timeout(300)
        pg.click('.tab[data-pane="paneLog"]'); pg.wait_for_timeout(300)
        for _ in range(3): pg.click("#bigBtn"); pg.wait_for_timeout(2700)
        pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(700)
        chk("jobs follow to Kloof Nek", "kloof nek" in lab(), lab())
        chk("Kloof Nek cutoff warning", "07h40" in pg.inner_text("#jobsWatch"),
            pg.inner_text("#jobsWatch")[:90])
        chk("drive time pre-filled", "5 min drive" in pg.inner_text("#cNextSub"))
        # the note has its own line now, so it cannot squeeze the timings
        chk("car-park note", "car park" in pg.inner_text("#cNextNote"))
        pg.click('.tab[data-pane="paneLog"]'); pg.wait_for_timeout(300)
        pg.click("#bigBtn"); pg.wait_for_timeout(2700)
        pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(700)
        chk("flips to 'he's here now'", "here now" in lab(), lab())
        # jump to the finish: card must disappear
        pg.click('.tab[data-pane="paneLog"]'); pg.wait_for_timeout(300)
        pg.click("#fixBtn"); pg.wait_for_timeout(400)
        pg.select_option("#fixCp", str(pg.evaluate("CPS.length - 1"))); pg.select_option("#fixState","in")
        pg.click("#fixGo"); pg.wait_for_timeout(1600)
        pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(600)
        chk("jobs card hidden once finished", not pg.is_visible("#jobsCard"))
        errs=[e for e in errs if "DISCONNECTED" not in e]
        chk("no console errors", not errs, str(errs[:3]))
        br.close()
finally: srv.terminate()
print("\nJOBS TEST: " + ("FAILED "+str(fails) if fails else "all passed"))
sys.exit(1 if fails else 0)
