"""Regression tests for the v38 review fixes. Real browser, real PHP."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
SRC, TOKEN = "/home/claude", "tok"
fails=[]
def check(n,c,d=""):
    print(("  ok  " if c else "  XX  ")+n+(f"   [{d}]" if d and not c else ""))
    if not c: fails.append(n)

class Srv:
    def __init__(s):
        s.d=tempfile.mkdtemp(prefix="utct-fable-")
        for f in ("index.html","api.php"): shutil.copy(os.path.join(SRC,f),s.d)
        open(os.path.join(s.d,"secret.php"),"w").write(f"<?php return '{TOKEN}';\n")
        os.makedirs(os.path.join(s.d,"data"),exist_ok=True)
        k=socket.socket(); k.bind(("127.0.0.1",0)); pt=k.getsockname()[1]; k.close()
        s.p=subprocess.Popen([shutil.which("php"),"-S",f"127.0.0.1:{pt}","-t",s.d],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        time.sleep(1.2); s.B=f"http://127.0.0.1:{pt}"
    def state(s): return json.loads(urllib.request.urlopen(f"{s.B}/api.php").read())
    def ev(s): return {(e["cp"],e["type"]):e for e in s.state()["events"]}
    def post(s,kind,payload,token=TOKEN):
        r=urllib.request.Request(f"{s.B}/api.php",data=json.dumps({"token":token,"kind":kind,"payload":payload}).encode(),headers={"Content-Type":"application/json"})
        try: return urllib.request.urlopen(r).status
        except urllib.error.HTTPError as e: return e.code
    def seed(s, upto_cp, last="in", ago_h=3):
        """Log a clean race up to a checkpoint, spaced out in the past."""
        t=int(time.time()*1000)-ago_h*3600*1000; n=0
        s.post("event",{"id":"e0","cp":0,"type":"out","t":t})
        for cp in range(1,upto_cp+1):
            t+=600000; n+=1; s.post("event",{"id":f"i{cp}","cp":cp,"type":"in","t":t})
            if cp<upto_cp or last=="out":
                t+=60000; s.post("event",{"id":f"o{cp}","cp":cp,"type":"out","t":t})
    def close(s): s.p.terminate(); shutil.rmtree(s.d,ignore_errors=True)

def page(br,S,who=None):
    pg=br.new_context().new_page()
    pg.goto(f"{S.B}/index.html#r={TOKEN}",wait_until="domcontentloaded"); pg.wait_for_timeout(1200)
    return pg
BTN=lambda pg: " ".join(pg.inner_text("#bigBtn").split())

print("\n=== v38 review fixes ===")
with sync_playwright() as pw:
    br=pw.chromium.launch()

    print("\n1. wrong station, corrected backwards")
    S=Srv(); S.seed(2,"in"); sh_in=S.ev()[(1,"in")]["t"]
    pg=page(br,S)
    check("starts at Kloof Nek", "LEAVES" in BTN(pg) and "Kloof Nek" in BTN(pg), BTN(pg))
    pg.click("#fixBtn"); pg.select_option("#fixCp","1"); pg.select_option("#fixState","in"); pg.click("#fixGo")
    pg.wait_for_timeout(400)
    check("it asks before removing later taps", pg.is_visible("#dlgConfirm") and "removes 2 taps" in pg.inner_text("#cfBody"), pg.inner_text("#cfBody"))
    pg.click("#cfGo"); pg.wait_for_timeout(2500)
    check("the button moves back to Signal Hill", "LEAVES" in BTN(pg) and "Signal Hill" in BTN(pg), BTN(pg))
    e=S.ev()
    check("server holds nothing beyond Signal Hill", set(e)=={(0,"out"),(1,"in")}, str(sorted(e)))
    check("Signal Hill's original arrival time is kept", e[(1,"in")]["t"]==sh_in)
    pg.click("#fixBtn"); pg.select_option("#fixCp","0"); pg.select_option("#fixState","in"); pg.click("#fixGo")
    pg.wait_for_timeout(400); pg.click("#cfGo"); pg.wait_for_timeout(2500)
    check("back to the start means not started", "START" in BTN(pg) and S.ev()=={}, BTN(pg)+str(S.ev()))
    S.close()

    print("\n2. no signal never costs a tap")
    S=Srv(); pg=page(br,S)
    pg.route("**/api.php*", lambda r: r.abort())
    pg.click("#bigBtn"); pg.wait_for_timeout(2700); pg.click("#bigBtn"); pg.wait_for_timeout(2700); pg.click("#bigBtn"); pg.wait_for_timeout(800)
    for _ in range(12): pg.evaluate("Store.drain()"); pg.wait_for_timeout(150)
    check("three taps still queued after twelve failed sends", pg.evaluate("Store.queue().length")==3, str(pg.evaluate("Store.queue().length")))
    check("the chip says so", "to send" in pg.inner_text("#syncChip").lower() or "signal" in pg.inner_text("#syncChip").lower(), pg.inner_text("#syncChip"))
    pg.unroute("**/api.php*"); pg.wait_for_timeout(5000)
    check("they all arrive once signal returns", set(S.ev())=={(0,"out"),(1,"in"),(1,"out")} and pg.evaluate("Store.queue().length")==0, str(sorted(S.ev())))
    S.close()

    print("\n3. overlapping sends on a slow link")
    S=Srv(); S.seed(2,"out"); pg=page(br,S)
    # first send is slow, the third fails outright: the pattern that used to let
    # one drain overwrite another's record of what was still unsent
    pg.evaluate("""() => { const real = window.fetch; let n = 0;
      window.fetch = function(u, o){
        if(o && o.method === "POST"){ n++;
          if(n === 1) return new Promise(r => setTimeout(() => r(real(u, o)), 2000));
          if(n === 3) return Promise.reject(new TypeError("dropped"));
        }
        return real(u, o); }; }""")
    pg.click("#bigBtn")                                   # Platteklip: in + out, back to back
    pg.wait_for_timeout(9000)
    e=S.ev()
    check("both halves of a timing-point tap reach the server", (3,"in") in e and (3,"out") in e, str(sorted(e)))
    check("nothing is left stranded", pg.evaluate("Store.queue().length")==0)
    S.close()

    print("\n4. a stale phone cannot undo other people's changes")
    S=Srv(); S.seed(2,"in")
    g1=int(time.time()*1000)-7200000; g2=g1+600000
    S.post("config",{"gunMs":g1,"targetSec":79200}); S.post("tick",{"key":"2:0","on":True})
    b=page(br,S)                                          # b now holds g1 and one tick
    b.route("**/api.php*", lambda r: r.abort() if r.request.method=="GET" else r.continue_())   # ...and stops hearing news
    b.wait_for_timeout(300)
    S.post("config",{"gunMs":g2,"targetSec":72000}); S.post("tick",{"key":"2:1","on":True})     # others move on
    b.evaluate("Store.saveConfig({ needs:{ items:['Ice'], t:Date.now() } })"); b.wait_for_timeout(1500)
    c=S.state()["config"]
    check("the need went through", c.get("needs",{}).get("items")==["Ice"], str(c.get("needs")))
    check("job ticks made since survive", c.get("ticks")=={"2:0":True,"2:1":True}, str(c.get("ticks")))
    check("the corrected gun time and target survive", c.get("gunMs")==g2 and c.get("targetSec")==72000, str({k:c.get(k) for k in ("gunMs","targetSec")}))
    S.close()

    print("\n5. a cancelled confirm stays cancelled; undo treats a timing point as one tap")
    S=Srv(); S.seed(3,"out"); pg=page(br,S)                # through Platteklip (a timing point)
    pg.click("#undoBtn"); pg.wait_for_timeout(300)
    check("undo names the pass", "pass through" in pg.inner_text("#cfBody"), pg.inner_text("#cfBody"))
    pg.click("#dlgConfirm [data-close]"); pg.wait_for_timeout(300)
    pg.click("#undoBtn"); pg.wait_for_timeout(300); pg.click("#cfGo"); pg.wait_for_timeout(2500)
    e=S.ev()
    check("one undo removed the whole timing-point tap and nothing else",
          (3,"in") not in e and (3,"out") not in e and (2,"out") in e, str(sorted(e)))
    check("the button offers Platteklip again, as a pass", "PASSES" in BTN(pg) and "Platteklip" in BTN(pg), BTN(pg))
    S.close()

    print("\n6. projections move with the clock when he is late")
    S=Srv(); S.post("event",{"id":"e0","cp":0,"type":"out","t":int(time.time()*1000)-5*3600*1000}); pg=page(br,S)
    r=pg.evaluate("""() => { const P=project(state()); const kn=2;
      return { late:(Date.now()-P.eta[1])/1000, kn:(P.gun+CPS[kn].cut*3600e3-P.eta[kn])/1000 }; }""")
    check("the next arrival is never in the past", r["late"]<=1, f"{r['late']:.0f}s")
    pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(800)
    check("no negative countdown on the card", "−" not in pg.inner_text("#cNextSub"), pg.inner_text("#cNextSub"))
    S.close()

    print("\n7. a missed tap does not leave a passed stop looking current")
    S=Srv(); t=int(time.time()*1000)-3*3600*1000
    S.post("config",{"gunMs":t}); S.post("event",{"id":"a","cp":0,"type":"out","t":t})
    S.post("event",{"id":"b","cp":2,"type":"out","t":t+int(3.9*3600*1000)-3600*1000})   # Kloof Nek OUT only, in was never tapped
    pg=page(br,S); pg.click('.tab[data-pane="paneBoard"]'); pg.wait_for_timeout(1000)
    check("next crew point is Llandudno, not the Kloof Nek he already left", pg.inner_text("#cNextName")=="Llandudno", pg.inner_text("#cNextName"))
    check("no cut-off alarm for a stop behind him", "Kloof" not in (pg.inner_text("#cwBody") if pg.is_visible("#cutWarn") else ""), pg.inner_text("#cwBody"))
    S.close()

    print("\n8. server refuses to save over a state file it could not read")
    S=Srv(); S.seed(2,"in"); f=os.path.join(S.d,"data","state.json"); good=open(f).read()
    open(f,"w").write(good[:len(good)//2])                # torn file
    code=S.post("event",{"id":"zz","cp":5,"type":"in","t":int(time.time()*1000)})
    check("write is refused with a retryable error", code==503, str(code))
    check("the damaged file was not replaced by an empty race", open(f).read()==good[:len(good)//2])
    open(f,"w").write(good)
    S.post("event",{"id":"fut","cp":3,"type":"in","t":int(time.time()*1000)+3600*1000})
    check("a tap stamped an hour in the future is pulled back to now", S.ev()[(3,"in")]["t"]<=time.time()*1000+5000)
    S.close()
    br.close()

print("\n"+("REVIEW FIXES: all passed" if not fails else f"{len(fails)} FAILED: "+", ".join(fails)))
sys.exit(1 if fails else 0)
