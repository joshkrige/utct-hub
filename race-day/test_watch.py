"""'N watching now': counts open, on-screen pages; never gets in the way."""
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
print("\n=== watching now ===\n")
with sync_playwright() as pw:
    br=pw.chromium.launch()
    crew=br.new_context().new_page(); crew.goto(f"{B}/index.html#r={TOKEN}",wait_until="domcontentloaded")
    fans=[]
    for _ in range(3):
        p=br.new_context().new_page(); p.goto(f"{B}/index.html",wait_until="domcontentloaded"); fans.append(p)
    time.sleep(5)
    fans[0].click('.tab[data-pane="paneMap"]'); fans[0].wait_for_timeout(4000)
    t=fans[0].inner_text("#ovWatch")
    check("supporters see the count", "4 watching now" in t, t)
    check("supporters don't see the crew split", "crew" not in t, t)
    crew.click('.tab[data-pane="paneMap"]'); crew.wait_for_timeout(1000)
    t=crew.inner_text("#ovWatch")
    check("crew see who is crew", "4 watching now · 1 crew" in t, t)
    # a page that goes off screen stops counting
    fans[1].evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))")
    fans[2].close()
    crew.wait_for_timeout(26000)
    t=crew.inner_text("#ovWatch")
    check("closed and hidden pages drop off within half a minute", t.startswith("2 watching"), t)
    # no ids, no ip: only random keys and timestamps on disk
    raw=open(os.path.join(d,"data","viewers.json")).read()
    check("nothing personal is stored", "127.0.0.1" not in raw and all(set(v)<= {"t","c"} for v in json.loads(raw).values()), raw[:160])
    # a broken viewers file must not break the race data
    open(os.path.join(d,"data","viewers.json"),"w").write("{{not json")
    r=json.loads(urllib.request.urlopen(f"{B}/api.php?v=abcdef123&on=1").read())
    check("race data still served if the counter breaks", "events" in r, str(r)[:120])
    os.chmod(os.path.join(d,"data"),0o555)
    try:
        r=json.loads(urllib.request.urlopen(f"{B}/api.php?v=abcdef124&on=1").read())
        check("race data still served if it can't write", "events" in r, str(r)[:120])
    finally: os.chmod(os.path.join(d,"data"),0o755)
    br.close()
srv.terminate(); shutil.rmtree(d,ignore_errors=True)
print("\n"+("WATCHING: all passed" if not fails else f"{len(fails)} FAILED: "+", ".join(fails)))
sys.exit(1 if fails else 0)
