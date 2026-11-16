"""Security: code rotation is recoverable, names can't inject, the counter
can't be flooded, and the deployer won't roll back."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
SRC=os.environ.get("SRC","/home/claude"); OLD, NEW = "old-code-1111", "new-code-2222"
fails=[]
def check(n,c,d=""):
    print(("  ok  " if c else "  XX  ")+n+(f"   [{d}]" if d and not c else ""))
    if not c: fails.append(n)
d=tempfile.mkdtemp()
for f in ("index.html","api.php","deploy.php"): shutil.copy(os.path.join(SRC,f),d)
setcode=lambda c: open(os.path.join(d,"secret.php"),"w").write(f"<?php return '{c}';\n")
setcode(OLD); os.makedirs(os.path.join(d,"data"),exist_ok=True)
k=socket.socket(); k.bind(("127.0.0.1",0)); pt=k.getsockname()[1]; k.close()
srv=subprocess.Popen([shutil.which("php"),"-S",f"127.0.0.1:{pt}","-t",d],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(1.2); B=f"http://127.0.0.1:{pt}"
state=lambda: json.loads(urllib.request.urlopen(f"{B}/api.php").read())
def post(payload,code=OLD,kind="event"):
    r=urllib.request.Request(f"{B}/api.php",data=json.dumps({"token":code,"kind":kind,"payload":payload}).encode(),headers={"Content-Type":"application/json"})
    try: return urllib.request.urlopen(r).status
    except urllib.error.HTTPError as e: return e.code
print("\n=== security ===")
with sync_playwright() as pw:
    br=pw.chromium.launch()
    print("\n1. the crew code is changed mid-week")
    pg=br.new_context().new_page()
    pg.goto(f"{B}/index.html#r={OLD}",wait_until="domcontentloaded"); pg.wait_for_timeout(1000)
    setcode(NEW); time.sleep(3)          # PHP caches compiled files for ~2 s
    check("the old code can no longer write", post({"id":"x","cp":1,"type":"in","t":int(time.time()*1000)})==403)
    pg.click("#bigBtn"); pg.wait_for_timeout(2500)
    check("the phone says the code changed", "code changed" in pg.inner_text("#syncChip").lower(), pg.inner_text("#syncChip"))
    check("the tap is kept, not lost", pg.evaluate("Store.queue().length")==1)
    pg.once("dialog", lambda dl: dl.accept(f"https://singa.studio/utct2026/#r={NEW}"))
    pg.click("#syncChip"); pg.wait_for_timeout(4500)
    check("after pasting the new link, the kept tap reaches the server", [ (e["cp"],e["type"]) for e in state()["events"]]==[(0,"out")], str(state()["events"]))
    check("and the phone is back to normal", pg.inner_text("#syncChip").strip().lower()=="live", pg.inner_text("#syncChip"))

    print("\n2. a name can't carry code onto other phones")
    post({"id":"n1","cp":1,"type":"in","t":int(time.time()*1000),"by":"<img src=x onerror=alert(1)>"},code=NEW)
    v=br.new_context().new_page(); v.goto(f"{B}/index.html#r={NEW}",wait_until="domcontentloaded"); v.wait_for_timeout(1200)
    v.click('.tab[data-pane="paneBoard"]'); v.wait_for_timeout(800)
    check("no injected image in the table", v.locator("#cpBody img").count()==0)
    br.close()

print("\n3. the watcher count can't be flooded")
for n in range(400):
    urllib.request.urlopen(f"{B}/api.php?v=flood{n:04d}x&on=1").read()
stored=len(json.load(open(os.path.join(d,"data","viewers.json"))))
check("the file holds at most 300 viewers", stored<=300, str(stored))
check("the race data is still served", "events" in state())

print("\n4. the deployer won't roll the app back")
def dep(q):
    try: return urllib.request.urlopen(f"{B}/deploy.php?key={NEW}{q}").read().decode()
    except urllib.error.HTTPError as e: return f"{e.code} "+e.read().decode()
r=dep("&ref=9aee00b")
check("an old commit is refused", r.startswith("409"), r[:80])
try:
    urllib.request.urlopen(f"{B}/deploy.php?key={OLD}"); wrong=200
except urllib.error.HTTPError as e: wrong=e.code
check("the leaked old code can't deploy", wrong==403, str(wrong))
srv.terminate(); shutil.rmtree(d,ignore_errors=True)
print("\n"+("SECURITY: all passed" if not fails else f"{len(fails)} FAILED: "+", ".join(fails)))
sys.exit(1 if fails else 0)
