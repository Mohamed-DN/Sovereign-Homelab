#!/usr/bin/env python3
"""Sovereign Console backend.

Serves the interactive console UI and is the ONLY component that holds the
app-control agent token. The browser never receives the token: it calls this
backend's /api endpoints, and the backend calls the agent. This keeps the
security rule "the frontend never receives secrets" intact.

Read-only status and two control actions (start/stop) are proxied to the
allowlist-only agent, which is the sole component that touches Docker.
"""

from __future__ import annotations

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

BIND = os.environ.get("CONSOLE_BIND", "0.0.0.0")
PORT = int(os.environ.get("CONSOLE_PORT", "8098"))
AGENT_URL = os.environ.get("CONSOLE_AGENT_URL", "http://127.0.0.1:8097")
AGENT_TOKEN_FILE = os.environ.get("CONSOLE_AGENT_TOKEN_FILE", "/root/sovereign-secrets/app-control-agent-token")
MAX_BODY = 64 * 1024


def agent_token() -> str:
    value = os.environ.get("CONSOLE_AGENT_TOKEN", "")
    if value:
        return value
    try:
        return Path(AGENT_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


TOKEN = agent_token()


def agent_get(path: str) -> tuple[int, Any]:
    request = urllib.request.Request(f"{AGENT_URL}{path}", headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, json.load(response)


def agent_post(path: str, body: dict[str, Any]) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{AGENT_URL}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=200) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sovereign Console</title><style>
:root{--bg:#06080b;--surface:#0d1218;--raised:#121922;--line:rgba(148,163,184,.2);--text:#f4f7fb;--muted:#9aa8b8;--cyan:#22d3ee;--green:#2dd4a7;--amber:#fbbf24;--red:#fb7185;--violet:#a78bfa}
*{box-sizing:border-box}html{color-scheme:dark;background:var(--bg)}
body{margin:0;min-height:100vh;color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);
background-image:linear-gradient(rgba(34,211,238,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,.035) 1px,transparent 1px);background-size:32px 32px;background-attachment:fixed}
header{position:sticky;top:0;z-index:10;display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;padding:16px 22px;border-bottom:1px solid rgba(34,211,238,.22);background:rgba(6,8,11,.94);backdrop-filter:blur(14px)}
header h1{margin:0;font-size:1.1rem;letter-spacing:.03em}header .sub{color:var(--muted);font-size:.78rem}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;border:1px solid color-mix(in srgb,var(--green) 40%,transparent);background:color-mix(in srgb,var(--green) 12%,transparent);color:var(--green);font-weight:700;font-size:.8rem}
.wrap{max-width:1100px;margin:0 auto;padding:22px}
h2{display:flex;align-items:center;gap:10px;min-height:38px;margin:0 0 14px;padding:0 12px;border:1px solid var(--line);border-left:3px solid var(--violet);border-radius:3px;background:rgba(10,15,21,.92);font-size:.82rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.card{position:relative;overflow:clip;padding:16px;border:1px solid var(--line);border-left:3px solid var(--violet);border-radius:8px;background:var(--surface);box-shadow:0 12px 28px rgba(0,0,0,.3);transition:transform .16s ease,border-color .16s ease}
.card:hover{transform:translateY(-2px);background:var(--raised)}
.card .top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.card .name{font-size:1.05rem;font-weight:800}
.state{display:inline-flex;align-items:center;gap:7px;font-size:.8rem;color:var(--muted)}
.led{width:10px;height:10px;border-radius:50%}
.run .led{background:var(--green);box-shadow:0 0 8px var(--green)}.stop .led{background:var(--red);box-shadow:0 0 8px var(--red)}.part .led{background:var(--amber);box-shadow:0 0 8px var(--amber)}
.svc{margin-top:8px;color:var(--muted);font-size:.72rem;font-family:Consolas,monospace}
.btn{margin-top:14px;width:100%;padding:10px;border-radius:6px;font-weight:800;font-size:.85rem;cursor:pointer;border:1px solid var(--line);color:var(--text);background:rgba(7,11,15,.9);transition:all .15s ease}
.btn.stop{border-color:color-mix(in srgb,var(--red) 55%,transparent);color:var(--red)}.btn.start{border-color:color-mix(in srgb,var(--green) 55%,transparent);color:var(--green)}
.btn:hover{background:var(--raised)}.btn:disabled{opacity:.5;cursor:wait}
.btn:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}
.note{color:var(--muted);font-size:.8rem;margin:8px 0 18px}
#toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);padding:12px 18px;border-radius:8px;background:var(--raised);border:1px solid var(--line);font-size:.85rem;opacity:0;transition:opacity .2s ease;pointer-events:none;max-width:90vw}
#toast.show{opacity:1}
@media(prefers-reduced-motion:no-preference){.run .led{animation:p 2.6s ease-in-out infinite}@keyframes p{0%,100%{opacity:.7}50%{opacity:1}}}
@media(prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}
</style></head><body>
<header><div><h1>SOVEREIGN CONSOLE</h1><div class="sub">Optional-app controls &middot; VPN/LAN only</div></div>
<span class="pill"><span class="led" style="background:var(--green);width:9px;height:9px;box-shadow:0 0 10px var(--green)"></span> agent connected</span></header>
<div class="wrap">
<h2>Apps &mdash; start / stop</h2>
<p class="note">Only optional apps are here. Critical services (Immich, Vaultwarden, databases, infrastructure) are never controllable. Every action asks for your name and a reason, is written to the audit log, and sends an email.</p>
<div class="grid" id="apps">Loading&hellip;</div>
</div>
<div id="toast"></div>
<script>
const g=document.getElementById('apps'),toast=document.getElementById('toast');
function t(m){toast.textContent=m;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),3500);}
function cls(o){return o==='running'?'run':o==='stopped'?'stop':'part';}
async function load(){
 try{const r=await fetch('api/status');const d=await r.json();render(d.apps||[]);}catch(e){g.textContent='Cannot reach the agent.';}
}
function render(apps){
 g.innerHTML='';
 for(const a of apps){
  const running=a.overall==='running';
  const card=document.createElement('div');card.className='card';
  const svc=Object.entries(a.services).map(([k,v])=>k+': '+v).join(' · ');
  card.innerHTML=`<div class="top"><span class="name">${a.name}</span><span class="state ${cls(a.overall)}"><span class="led"></span>${a.overall}</span></div>
   <div class="svc">${svc}</div>`;
  const b=document.createElement('button');
  b.className='btn '+(running?'stop':'start');b.textContent=running?'Stop':'Start';
  b.onclick=()=>act(a.name,running?'stop':'start',b);
  card.appendChild(b);g.appendChild(card);
 }
}
async function act(service,action,btn){
 const who=prompt('Your name (for the audit log):');if(!who)return;
 const reason=prompt('Reason for '+action+' '+service+':');if(reason===null)return;
 btn.disabled=true;btn.textContent=(action==='stop'?'Stopping':'Starting')+'…';
 try{
  const r=await fetch('api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service,action,actor:who,reason})});
  const d=await r.json();
  t(d.ok?`${service} ${action==='stop'?'stopped':'started'} — emailed & logged`:`Failed: ${d.detail||d.error||'error'}`);
 }catch(e){t('Request failed');}
 setTimeout(load,1500);
}
load();setInterval(load,10000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
            return
        if self.path == "/api/status":
            try:
                _, data = agent_get("/status")
                self._send(200, json.dumps(data).encode("utf-8"), "application/json")
            except Exception as exc:  # noqa: BLE001
                self._send(502, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
            return
        self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self) -> None:
        if self.path != "/api/control":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_BODY:
            self._send(413, b'{"error":"bad body"}', "application/json")
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send(400, b'{"error":"invalid json"}', "application/json")
            return
        body = {
            "service": str(payload.get("service", "")),
            "action": str(payload.get("action", "")),
            "actor": str(payload.get("actor", "console"))[:120],
            "reason": str(payload.get("reason", ""))[:300],
        }
        try:
            code, data = agent_post("/control", body)
            self._send(code, json.dumps(data).encode("utf-8"), "application/json")
        except Exception as exc:  # noqa: BLE001
            self._send(502, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    if not TOKEN:
        raise SystemExit("console backend refuses to start without the agent token")
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"sovereign-console-backend listening on {BIND}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
