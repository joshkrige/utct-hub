"""Look ahead: any crew stop's jobs can be read without changing the race."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from playwright.sync_api import sync_playwright
SRC, TOKEN = "/home/claude", "tok"
fails=[]
def check(n,c,d=""):
    print(("  ok  " if c else "  XX  ")+n+(f"   [{d}]" if d and not c else ""))
    if not c: fails.append(n)
d=tempfile.mkdtemp()
for f in ("index.html","api.php"): shutil.copy(os.path.join(SRC,f),d)
open(os.path.join(d,"secret.php"),"w").write(f"<?php return '{TOKEN}';\n"); os.makedirs(os.path.join(d,"data"),exist_ok=True)
k=socket.socket(); k.bind(("127.0.0.1",0)); pt=k.getsockname()[1]; k.close()
srv=subprocess.Popen([shutil.which("php"),"-S",f"127.0.0.1:{pt}","-t",d],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(1.2); B=f"http://127.0.0.1:{pt}"
state=lambda: json.loads(urllib.request.urlopen(f"{B}/api.php").read())
t=int(time.time()*1000)-3600000
r=urllib.request.Request(f"{B}/api.php",data=json.dumps({"token":TOKEN,"kind":"event","payload":{"id":"a","cp":0,"type":"out","t":t}}).encode(),headers={"Content-Type":"application/json"}); urllib.request.urlopen(r).read()
print("\n=== look ahead ===\n")
with sync_playwright() as pw:
    br=pw.chromium.launch()
    pg=br.new_context(viewport={"width":390,"height":900},device_scale_factor=2,is_mobile=True,timezone_id="Africa/Johannesburg").new_page()
    pg.goto(f"{B}/index.html#r={TOKEN}",wait_until="domcontentloaded"); pg.wait_for_timeout(1200)
    btn=lambda: " ".join(pg.inner_text("#bigBtn").split())
    before_btn=btn(); before=state()
    pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(800)
    check("a chip for every crew stop", pg.locator("#stopPick button").count()==7, str(pg.locator("#stopPick button").count()))
    check("live stop is Kloof Nek", "kloof nek" in pg.inner_text("#jobsLab").lower() and pg.is_hidden("#aheadBar"))
    pg.click('#stopPick button[data-stop="7"]'); pg.wait_for_timeout(1500)
    check("Hout Bay's list opens", "hout bay" in pg.inner_text("#jobsLab").lower() and "grey sls" in pg.inner_text("#jobsList").lower(), pg.inner_text("#jobsLab"))
    check("it says it's looking ahead, with an expected time", pg.is_visible("#aheadBar") and "expected about" in pg.inner_text("#aheadTxt"), pg.inner_text("#aheadTxt"))
    check("it stays put across the 1-second refresh", "hout bay" in pg.inner_text("#jobsLab").lower())
    pg.locator("#jobsList li").first.click(); pg.wait_for_timeout(1200)
    check("ticks can't be made while looking ahead", not state()["config"].get("ticks"), str(state()["config"].get("ticks")))
    check("nothing about the race changed", state()["events"]==before["events"])
    pg.click('.tab[data-pane="paneLog"]'); pg.wait_for_timeout(500)
    check("the tap button is untouched", btn()==before_btn, btn())
    pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(500)
    pg.screenshot(path="/tmp/ahead.png", clip={"x":0,"y":0,"width":390,"height":900})
    pg.click("#aheadBack"); pg.wait_for_timeout(800)
    check("Back to now returns to the live stop", "kloof nek" in pg.inner_text("#jobsLab").lower() and pg.is_hidden("#aheadBar"))
    pg.click('#stopPick button[data-stop="11"]'); pg.wait_for_timeout(500)
    pg.click('#stopPick button[data-stop="2"]'); pg.wait_for_timeout(800)
    check("tapping the live stop's chip also returns to now", pg.is_hidden("#aheadBar"))
    pg.locator("#jobsList li").first.click(); pg.wait_for_timeout(1500)
    check("ticks work again on the live stop", state()["config"].get("ticks")=={"2:0":True}, str(state()["config"].get("ticks")))
    br.close()
srv.terminate(); shutil.rmtree(d,ignore_errors=True)
print("\n"+("LOOK AHEAD: all passed" if not fails else f"{len(fails)} FAILED: "+", ".join(fails)))
sys.exit(1 if fails else 0)
