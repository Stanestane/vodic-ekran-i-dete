import json, subprocess, time, base64, urllib.request, os, sys
from websocket import create_connection

FOLDER = os.path.expanduser("~/Documents/vodic-ekran-i-dete")
HTML   = "file://" + os.path.join(FOLDER, "vodic-ekran-i-dete.html")
OUT    = os.path.join(FOLDER, "vodic-ekran-i-dete.pdf")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT   = 9222
WIDTH  = 839
profile = "/tmp/chrome-pdf-%d" % int(time.time())

proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=%d" % PORT,
    "--user-data-dir=%s" % profile, "--no-first-run", "--no-default-browser-check",
    "--disable-gpu", "--hide-scrollbars", "--remote-allow-origins=*", "--window-size=%d,1200" % WIDTH,
    "--force-device-scale-factor=1", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws_url = None
for _ in range(60):
    try:
        data = json.load(urllib.request.urlopen("http://localhost:%d/json" % PORT))
        for t in data:
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                ws_url = t["webSocketDebuggerUrl"]; break
        if ws_url: break
    except Exception:
        pass
    time.sleep(0.5)
if not ws_url:
    print("ERROR: no devtools page target"); proc.terminate(); sys.exit(1)

ws = create_connection(ws_url, max_size=None)
_id = [0]
def cmd(method, params=None):
    _id[0] += 1; mid = _id[0]
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            if "error" in msg: raise RuntimeError(str(msg["error"]))
            return msg.get("result", {})

cmd("Page.enable"); cmd("Runtime.enable")
cmd("Emulation.setDeviceMetricsOverride",
    {"width": WIDTH, "height": 1200, "deviceScaleFactor": 1, "mobile": False})
cmd("Page.navigate", {"url": HTML})
time.sleep(3.0)
res = cmd("Runtime.evaluate", {
    "expression": "document.fonts.ready.then(function(){return document.documentElement.scrollHeight})",
    "awaitPromise": True, "returnByValue": True})
height = int(res["result"]["value"])
print("SCROLLHEIGHT_PX:", height, "INCHES:", round(height/96.0, 2))

MAX_PX = 19000  # ~197.9 in, sigurno ispod Chrome granice od 200 in
scale = 1.0 if height <= MAX_PX else MAX_PX / float(height)
paperW = (WIDTH * scale) / 96.0
paperH = (height * scale) / 96.0
print("SCALE:", round(scale, 4), "PAGE_IN:", round(paperW, 2), "x", round(paperH, 2))
r = cmd("Page.printToPDF", {"printBackground": True, "paperWidth": paperW, "paperHeight": paperH,
    "scale": scale,
    "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0,
    "pageRanges": "1", "preferCSSPageSize": False})
pdf = base64.b64decode(r["data"])
open(OUT, "wb").write(pdf)
print("WROTE:", OUT, "BYTES:", len(pdf))
try: cmd("Browser.close")
except Exception: pass
try: ws.close()
except Exception: pass
proc.terminate()
