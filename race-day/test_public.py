"""The public view.

Anyone can be given the plain link. They must be able to follow the race and
must not be able to change it, read the crew's checklists, or be shown a
button that quietly does nothing.
"""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from playwright.sync_api import sync_playwright

SRC, TOKEN = "/home/claude", "crew-code-1234"
fails = []


def check(name, cond, detail=""):
    print(("  ok  " if cond else "  XX  ") + name + (f"   [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


d = tempfile.mkdtemp(prefix="utct-pub-")
for f in ("index.html", "api.php"):
    shutil.copy(os.path.join(SRC, f), d)
open(os.path.join(d, "secret.php"), "w").write(f"<?php return '{TOKEN}';\n")
os.makedirs(os.path.join(d, "data"), exist_ok=True)
sk = socket.socket(); sk.bind(("127.0.0.1", 0)); port = sk.getsockname()[1]; sk.close()
srv = subprocess.Popen([shutil.which("php"), "-S", f"127.0.0.1:{port}", "-t", d],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.3)
base = f"http://127.0.0.1:{port}"
events = lambda: json.loads(urllib.request.urlopen(f"{base}/api.php").read())["events"]

print("\n=== public view ===\n")
with sync_playwright() as pw:
    br = pw.chromium.launch()

    print("crew phone (has the code)")
    cc = br.new_context(); crew = cc.new_page()
    crew.goto(f"{base}/index.html#r={TOKEN}", wait_until="domcontentloaded")
    crew.wait_for_timeout(1000)
    check("crew get the Log tab", crew.is_visible('.tab[data-pane="paneLog"]'))
    check("crew get the tap button", crew.is_visible("#bigBtn"))
    crew.click("#bigBtn"); crew.wait_for_timeout(2200)
    check("crew tap reaches the server", len(events()) == 1, str(events()))
    crew.click('.tab[data-pane="paneBoard"]'); crew.wait_for_timeout(1000)
    check("crew see their job list", crew.is_visible("#jobsCard"))
    check("crew see drive logistics", "drive" in crew.inner_text("#cNextSub").lower(),
          crew.inner_text("#cNextSub"))
    check("no crew link offered to crew", crew.is_hidden("#crewLink"))
    check("crew keep settings", crew.is_visible("#cogBtn"))
    check("crew keep the rules card", crew.is_visible("#rulesBtn"))

    print("\nstranger (plain link, no code)")
    pc = br.new_context(); vis = pc.new_page()
    vis.goto(f"{base}/index.html", wait_until="domcontentloaded")
    vis.wait_for_timeout(1400)
    check("lands on Overview, not Log", vis.is_visible("#paneMap") and not vis.is_visible("#paneLog"))
    check("no Log tab", vis.is_hidden('.tab[data-pane="paneLog"]'))
    check("no tap button to press in vain", vis.is_hidden("#bigBtn"))
    check("chip reads Following, not an error",
          vis.inner_text("#syncChip").strip().lower() == "following",
          vis.inner_text("#syncChip"))
    check("crew job list is hidden", vis.is_hidden("#jobsCard"))
    check("needs card is hidden", vis.is_hidden("#needsCard"))
    check("no drive logistics", "drive" not in vis.inner_text("#cNextSub").lower(),
          vis.inner_text("#cNextSub"))

    # but they can follow the race
    board = vis.inner_text("#paneBoard")
    check("they can see where he is", "Signal Hill" in board or "Start" in board, board[:120])
    check("they see projected times", ":" in vis.inner_text("#cFinish"),
          vis.inner_text("#cFinish"))
    check("the map is still theirs", vis.is_visible('.tab[data-pane="paneMap"]'))
    check("no settings button", vis.is_hidden("#cogBtn"))
    check("no crew rules button", vis.is_hidden("#rulesBtn"))
    check("night mode stays, it is for everyone", vis.is_visible("#nightBtn"))

    print("\nstranger cannot change anything")
    before = len(events())
    r = vis.evaluate("""async () => {
      const res = await fetch('api.php', { method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ token:'', kind:'event',
          payload:{ id:'hack1', cp:3, type:'in', t:Date.now() } }) });
      return res.status;
    }""")
    check("a forged write is refused", r == 403, f"http {r}")
    check("nothing was written", len(events()) == before, str(events()))

    r2 = vis.evaluate("""async () => {
      const res = await fetch('api.php', { method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ token:'guess', kind:'config',
          payload:{ targetSec: 36000 } }) });
      return res.status;
    }""")
    check("a guessed code is refused", r2 == 403, f"http {r2}")

    print("\na crew member who opened the plain link can still get in")
    check("crew link is offered", vis.is_visible("#crewLink"))
    vis.evaluate("t => { const a=JSON.parse(localStorage.getItem('utct.pref.v1')||'{}');"
                 "a.token=t; localStorage.setItem('utct.pref.v1', JSON.stringify(a)); }", TOKEN)
    vis.reload(wait_until="domcontentloaded"); vis.wait_for_timeout(1200)
    check("after entering the code they get the Log tab",
          vis.is_visible('.tab[data-pane="paneLog"]'))
    check("and the crew link goes away", vis.is_hidden("#crewLink"))
    br.close()

srv.terminate(); shutil.rmtree(d, ignore_errors=True)
print("\n" + ("PUBLIC VIEW: all passed" if not fails else f"{len(fails)} FAILED: " + ", ".join(fails)))
sys.exit(1 if fails else 0)

