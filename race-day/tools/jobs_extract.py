"""Pull every crew stop's job list, plus planned arrival and cut-off, out of the app.
Usage: python3 jobs_extract.py /path/to/index.html > jobs.json"""
import json, shutil, socket, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright

d = tempfile.mkdtemp(); shutil.copy(sys.argv[1], d)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([shutil.which("php"), "-S", f"127.0.0.1:{port}", "-t", d],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)
try:
    with sync_playwright() as pw:
        br = pw.chromium.launch(); pg = br.new_page()
        pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded")
        pg.wait_for_timeout(1200)
        out = pg.evaluate("""() => {
          const st = state(); const P = project(st);
          const lastLight = lastLightStop(P, true);
          const hm = ms => { const d = new Date(ms);
            return String(d.getHours()).padStart(2,"0") + ":" + String(d.getMinutes()).padStart(2,"0"); };
          return { version: VERSION, target: st.config.targetSec,
            stops: Object.keys(JOBS).map(Number).sort((a,b)=>a-b).map(ji => {
              const J = JOBS[ji], c = CPS[ji], jt = P.eta[ji];
              let lead = J.lead;
              if(ji === lastLight && ji > 0)
                lead = '<b>Last stop in daylight — dark by ' + SUN.dusk.replace(":", "h") + '.</b> Bring a lamp for the rest. ' + lead;
              else if(isDark(raceClock(jt, P)) && ji > 0)
                lead = '<b>This one is in the dark.</b> ' + lead;
              return { n:c.n, s:c.s, km:c.km, cut:c.cut||null, eta: ji===0 ? hm(P.gun) : hm(jt),
                       bag:!!c.bag, lead, do:J.do, watch:J.watch||"" };
            }) };
        }""")
        print(json.dumps(out))
        br.close()
finally:
    srv.terminate()
