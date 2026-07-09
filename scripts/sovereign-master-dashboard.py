#!/usr/bin/env python3
"""Sovereign Master Dashboard.

One unified operations dashboard, served from the Proxmox host, which is the only
place that can natively orchestrate everything:

  - read live health (Uptime Kuma), Immich status, the Windows mirror state, and
    PBS snapshots;
  - FORCE a Windows mirror backup (VM 110) and FORCE a PBS backup;
  - START/STOP the optional apps through the allowlist-only control agent.

Read-only status is open on the LAN/VPN. Control actions are allowlisted, ask for
an actor + reason, and are written to an audit log. The Docker socket is never
exposed to a browser; app control always goes through the agent.

Bind LAN-only and publish through NPM at dash.internal. Add Authentik in front
before treating the actor field as a real identity.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

BIND = os.environ.get("DASH_BIND", "0.0.0.0")
PORT = int(os.environ.get("DASH_PORT", "8095"))
AGENT_URL = os.environ.get("DASH_AGENT_URL", "http://192.168.1.52:8097")
AGENT_TOKEN_FILE = os.environ.get("DASH_AGENT_TOKEN_FILE", "/root/sovereign-secrets/app-control-agent-token")
AUDIT_LOG = Path(os.environ.get("DASH_AUDIT_LOG", "/root/sovereign-secrets/master-dashboard-audit.jsonl"))
PBS_STORAGE = os.environ.get("DASH_PBS_STORAGE", "pbs-p710")
PBS_BACKUP_ALLOW = {"100", "101", "102", "103", "110", "120", "130"}
CACHE_TTL = int(os.environ.get("DASH_CACHE_TTL", "15"))
MAX_BODY = 64 * 1024

_cache: dict[str, Any] = {"ts": 0, "data": None}
_lock = threading.Lock()


def agent_token() -> str:
    try:
        return Path(AGENT_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    return p.returncode, (p.stdout + p.stderr).strip()


def guest_out(raw: str) -> str:
    try:
        return json.loads(raw).get("out-data", "")
    except (json.JSONDecodeError, TypeError):
        return ""


def kuma_health() -> dict[str, Any]:
    code = (
        "import json,sqlite3;"
        "p='/var/lib/docker/volumes/sovereign-observability_uptime_kuma_data/_data/kuma.db';"
        "c=sqlite3.connect(p);c.row_factory=sqlite3.Row;"
        "act=c.execute('select count(*) n from monitor where active=1').fetchone()['n'];"
        "down=0;\n"
        "for m in c.execute('select id from monitor where active=1'):\n"
        " h=c.execute('select status from heartbeat where monitor_id=? order by id desc limit 1',(m['id'],)).fetchone();\n"
        " down+= 1 if (h and h['status']==0) else 0\n"
        "print(json.dumps({'active':act,'down':down}))"
    )
    status, out = run(["pct", "exec", "101", "--", "python3", "-c", code], timeout=25)
    try:
        return json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return {"active": None, "down": None, "error": True}


def guests() -> dict[str, int]:
    status, out = run(["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"], timeout=25)
    try:
        rows = json.loads(out)
        running = sum(1 for r in rows if r.get("status") == "running")
        return {"running": running, "total": len(rows)}
    except (json.JSONDecodeError, TypeError):
        return {"running": 0, "total": 0}


def immich_and_mirror() -> dict[str, Any]:
    script = r'''
import json,glob,os,time
out={}
try:
    import subprocess
    r=subprocess.run(["bash","-lc","curl -fsS --max-time 6 http://127.0.0.1:2283/api/server/ping"],capture_output=True,text=True,timeout=12)
    out["immich_ping"]= '"res":"pong"' in r.stdout
except Exception:
    out["immich_ping"]=False
root="/root/sovereign-secrets/immich-protection"
dumps=sorted(glob.glob(root+"/daily/immich-db-*.sql.gz"),key=os.path.getmtime)
out["protection_dump_age_h"]=round((time.time()-os.path.getmtime(dumps[-1]))/3600,1) if dumps else None
sums=sorted(glob.glob(root+"/daily/summary-*.json"),key=os.path.getmtime)
if sums:
    s=json.load(open(sums[-1])); out["photos_bytes"]=s.get("total_bytes"); out["files"]=s.get("file_count")
st="/root/sovereign-secrets/immich-windows/state/last-mirror.json"
if os.path.exists(st):
    d=json.load(open(st)); c=d.get("created_utc")
    age=None
    if c:
        try:
            from datetime import datetime,timezone
            w=datetime.strptime(c,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age=round((datetime.now(timezone.utc)-w).total_seconds()/3600,1)
        except Exception: pass
    out["mirror"]={"configured":True,"age_h":age,"snapshot":d.get("snapshot_id"),"check":d.get("check_result")}
else:
    out["mirror"]={"configured":False}
print(json.dumps(out))
'''
    status, raw = run(["qm", "guest", "exec", "110", "--", "python3", "-c", script], timeout=40)
    try:
        return json.loads(guest_out(raw) or "{}")
    except (json.JSONDecodeError, TypeError):
        return {"immich_ping": False, "mirror": {"configured": False}, "error": True}


def pbs_latest() -> dict[str, str]:
    status, out = run(["pvesm", "list", PBS_STORAGE, "--content", "backup"], timeout=45)
    latest: dict[str, tuple[datetime, str]] = {}
    for m in re.finditer(r"(?:ct|vm)/(\d+)/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", out):
        vmid, stamp = m.groups()
        v = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if vmid not in latest or v > latest[vmid][0]:
            latest[vmid] = (v, stamp)
    return {k: v[1] for k, v in latest.items()}


def app_status() -> list[dict[str, Any]]:
    try:
        req = urllib.request.Request(f"{AGENT_URL}/status", headers={"Authorization": f"Bearer {agent_token()}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("apps", [])
    except Exception:
        return []


def overview(force: bool = False) -> dict[str, Any]:
    with _lock:
        if not force and _cache["data"] and time.time() - _cache["ts"] < CACHE_TTL:
            return _cache["data"]
    data = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "guests": guests(),
        "kuma": kuma_health(),
        "immich": immich_and_mirror(),
        "pbs": pbs_latest(),
        "apps": app_status(),
    }
    with _lock:
        _cache["data"] = data
        _cache["ts"] = time.time()
    return data


def audit(entry: dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as h:
        h.write(json.dumps(entry, sort_keys=True) + "\n")
    try:
        AUDIT_LOG.chmod(0o600)
    except OSError:
        pass


def do_app(service: str, action: str) -> tuple[bool, str]:
    body = json.dumps({"service": service, "action": action, "actor": "master-dashboard", "reason": "via master dashboard"}).encode()
    req = urllib.request.Request(f"{AGENT_URL}/control", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {agent_token()}"})
    try:
        with urllib.request.urlopen(req, timeout=200) as r:
            d = json.load(r)
            return bool(d.get("ok")), d.get("detail", "")
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read()).get("error", str(e))
        except Exception:
            return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def do_mirror_backup() -> tuple[bool, str]:
    status, raw = run(["qm", "guest", "exec", "110", "--", "bash", "-lc",
                       "systemctl start --no-block sovereign-immich-windows-restic.service && echo started"], timeout=30)
    return ("started" in guest_out(raw)), guest_out(raw)[:200]


def do_pbs_backup(vmid: str) -> tuple[bool, str]:
    if vmid not in PBS_BACKUP_ALLOW:
        return False, f"vmid not allowed: {vmid}"
    # Detached so the HTTP request returns immediately; vzdump runs in the background.
    cmd = f"nohup vzdump {vmid} --storage {PBS_STORAGE} --mode snapshot --node pve >/var/log/dash-vzdump-{vmid}.log 2>&1 &"
    status, out = run(["bash", "-lc", cmd], timeout=20)
    return status == 0, out[:200]


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sovereign Master Dashboard</title><style>
:root{--bg:#06080b;--surface:#0d1218;--raised:#121922;--line:rgba(148,163,184,.2);--text:#f4f7fb;--muted:#9aa8b8;--cyan:#22d3ee;--green:#2dd4a7;--blue:#60a5fa;--amber:#fbbf24;--red:#fb7185;--violet:#a78bfa}
*{box-sizing:border-box}html{color-scheme:dark;background:var(--bg)}
body{margin:0;min-height:100vh;color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);
background-image:linear-gradient(rgba(34,211,238,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,.035) 1px,transparent 1px);background-size:32px 32px;background-attachment:fixed}
header{position:sticky;top:0;z-index:10;display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;padding:15px 22px;border-bottom:1px solid rgba(34,211,238,.22);background:rgba(6,8,11,.94);backdrop-filter:blur(14px)}
header h1{margin:0;font-size:1.05rem;letter-spacing:.03em}.sub{color:var(--muted);font-size:.76rem}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;font-weight:700;font-size:.8rem;border:1px solid var(--line)}
.wrap{max-width:1180px;margin:0 auto;padding:20px}
h2{display:flex;align-items:center;gap:10px;min-height:36px;margin:26px 0 12px;padding:0 12px;border:1px solid var(--line);border-left:3px solid var(--accent,var(--cyan));border-radius:3px;background:rgba(10,15,21,.92);font-size:.8rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
#ovw{--accent:var(--cyan)}#data h2{--accent:var(--amber)}#apps h2{--accent:var(--violet)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{padding:14px;border:1px solid var(--line);border-left:3px solid var(--accent,var(--cyan));border-radius:8px;background:var(--surface)}
.tile .k{color:var(--muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}.tile .v{font-size:1.5rem;font-weight:800;margin-top:5px}.tile .f{color:var(--muted);font-size:.72rem;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.card{padding:16px;border:1px solid var(--line);border-left:3px solid var(--accent,var(--cyan));border-radius:8px;background:var(--surface);box-shadow:0 12px 28px rgba(0,0,0,.3)}
#data .card{--accent:var(--amber)}#apps .card{--accent:var(--violet)}
.card:hover{background:var(--raised)}
.top{display:flex;align-items:center;justify-content:space-between;gap:8px}.name{font-size:1.05rem;font-weight:800}
.state{display:inline-flex;align-items:center;gap:7px;font-size:.8rem;color:var(--muted)}.led{width:10px;height:10px;border-radius:50%}
.run .led,.ok .led{background:var(--green);box-shadow:0 0 8px var(--green)}.stop .led,.bad .led{background:var(--red);box-shadow:0 0 8px var(--red)}.warn .led{background:var(--amber);box-shadow:0 0 8px var(--amber)}
.rows{margin-top:8px;font-size:.8rem;color:var(--muted);line-height:1.7}
.btn{margin-top:12px;width:100%;padding:9px;border-radius:6px;font-weight:800;font-size:.82rem;cursor:pointer;border:1px solid var(--line);color:var(--text);background:rgba(7,11,15,.9)}
.btn:hover{background:var(--raised)}.btn:disabled{opacity:.5;cursor:wait}.btn:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}
.btn.stop{border-color:color-mix(in srgb,var(--red) 55%,transparent);color:var(--red)}.btn.start{border-color:color-mix(in srgb,var(--green) 55%,transparent);color:var(--green)}
.btn.act{border-color:color-mix(in srgb,var(--blue) 55%,transparent);color:var(--blue)}
.note{color:var(--muted);font-size:.78rem;margin:6px 0 14px}
#toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);padding:12px 18px;border-radius:8px;background:var(--raised);border:1px solid var(--line);font-size:.85rem;opacity:0;transition:opacity .2s;pointer-events:none;max-width:92vw}
#toast.show{opacity:1}
@media(prefers-reduced-motion:no-preference){.ok .led,.run .led{animation:p 2.6s ease-in-out infinite}@keyframes p{0%,100%{opacity:.7}50%{opacity:1}}}
@media(prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}
</style></head><body>
<header><div><h1>SOVEREIGN MASTER DASHBOARD</h1><div class="sub">status &middot; backups &middot; controls &middot; VPN/LAN only</div></div>
<span class="pill" id="status">loading&hellip;</span></header>
<div class="wrap">
<div id="ovw"><h2>Overview</h2><div class="tiles" id="tiles">&hellip;</div></div>
<div id="data"><h2>Data &amp; Backups</h2>
<p class="note">Immich can never be stopped from here. Backups are safe to force at any time.</p>
<div class="grid" id="dcards">&hellip;</div></div>
<div id="apps"><h2>Apps &mdash; start / stop</h2>
<p class="note">Only optional apps. Every action asks your name + reason, is logged, and emails you.</p>
<div class="grid" id="acards">&hellip;</div></div>
</div><div id="toast"></div>
<script>
const $=id=>document.getElementById(id),toast=$('toast');
function t(m){toast.textContent=m;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),4000);}
function ago(h){if(h==null)return'unknown';if(h<24)return h.toFixed(1)+' h ago';return (h/24).toFixed(1)+' d ago';}
function gb(b){return b?(b/1073741824).toFixed(1)+' GB':'-';}
async function load(){
 let d;try{d=await(await fetch('api/overview')).json();}catch(e){$('status').textContent='backend unreachable';return;}
 const down=d.kuma.down||0,crit=!d.immich.immich_ping;
 const sp=$('status');sp.textContent=(crit?'ATTENTION':down?down+' monitor(s) down':'all systems nominal');
 sp.style.color=crit?'var(--red)':down?'var(--amber)':'var(--green)';sp.style.borderColor=sp.style.color;
 const m=d.immich.mirror||{};
 $('tiles').innerHTML=[
  ['Guests',`${d.guests.running}/${d.guests.total}`,'running'],
  ['Monitors',`${(d.kuma.active||0)-down}/${d.kuma.active||0}`,down?down+' down':'all up'],
  ['Immich',d.immich.immich_ping?'OK':'CHECK','foto.internal'],
  ['Immich dump',ago(d.immich.protection_dump_age_h),'app-aware'],
  ['Windows mirror',m.configured?ago(m.age_h):'not set',m.snapshot?('snap '+m.snapshot):''],
  ['PBS VM110',(d.pbs['110']||'none').replace('T',' ').replace('Z',''),'latest snapshot'],
 ].map(x=>`<div class="tile"><div class="k">${x[0]}</div><div class="v">${x[1]}</div><div class="f">${x[2]}</div></div>`).join('');
 // data & backups cards
 $('dcards').innerHTML=`
  <div class="card"><div class="top"><span class="name">Immich</span><span class="state ${d.immich.immich_ping?'ok':'bad'}"><span class="led"></span>${d.immich.immich_ping?'healthy':'check'}</span></div>
   <div class="rows">Files: ${d.immich.files??'-'} &middot; ${gb(d.immich.photos_bytes)}<br>Protection dump: ${ago(d.immich.protection_dump_age_h)}</div></div>
  <div class="card"><div class="top"><span class="name">Windows mirror</span><span class="state ${m.configured?(m.age_h>168?'warn':'ok'):'warn'}"><span class="led"></span>${m.configured?ago(m.age_h):'not configured'}</span></div>
   <div class="rows">Snapshot: ${m.snapshot||'-'} &middot; check: ${m.check||'-'}</div>
   <button class="btn act" onclick="act('mirror-backup',null,this,'Force a Windows mirror backup now?')">Force Windows backup</button></div>
  <div class="card"><div class="top"><span class="name">PBS (Immich VM110)</span><span class="state ok"><span class="led"></span>${(d.pbs['110']||'none')}</span></div>
   <div class="rows">Storage: ${'${PBS_STORAGE}'}</div>
   <button class="btn act" onclick="act('pbs-backup','110',this,'Force a PBS snapshot of VM110 now?')">Force PBS backup (VM110)</button></div>`;
 // apps
 $('acards').innerHTML='';
 for(const a of d.apps){const r=a.overall==='running';
  const c=document.createElement('div');c.className='card';
  c.innerHTML=`<div class="top"><span class="name">${a.name}</span><span class="state ${r?'run':'stop'}"><span class="led"></span>${a.overall}</span></div>
   <div class="rows">${Object.entries(a.services).map(([k,v])=>k+': '+v).join('<br>')}</div>`;
  const b=document.createElement('button');b.className='btn '+(r?'stop':'start');b.textContent=r?'Stop':'Start';
  b.onclick=()=>act('app',{service:a.name,action:r?'stop':'start'},b,null);c.appendChild(b);$('acards').appendChild(c);}
}
async function act(op,arg,btn,confirmMsg){
 if(confirmMsg&&!confirm(confirmMsg))return;
 const who=prompt('Your name (for the audit log):');if(!who)return;
 const reason=prompt('Reason:');if(reason===null)return;
 btn.disabled=true;const old=btn.textContent;btn.textContent='Working…';
 const body={op,actor:who,reason};
 if(op==='app'){body.service=arg.service;body.action=arg.action;}
 if(op==='pbs-backup'){body.vmid=arg;}
 try{const d=await(await fetch('api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  t(d.ok?'Done — logged'+(op!=='app'?' & running in background':''):'Failed: '+(d.detail||d.error||'error'));}
 catch(e){t('Request failed');}
 btn.textContent=old;setTimeout(()=>{btn.disabled=false;load();},2000);
}
load();setInterval(load,15000);
</script></body></html>""".replace("${PBS_STORAGE}", PBS_STORAGE)


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
        elif self.path == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
        elif self.path == "/api/overview":
            try:
                self._send(200, json.dumps(overview()).encode("utf-8"), "application/json")
            except Exception as exc:  # noqa: BLE001
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
        else:
            self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self) -> None:
        if self.path != "/api/action":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_BODY:
            self._send(413, b'{"error":"bad body"}', "application/json")
            return
        try:
            p = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send(400, b'{"error":"invalid json"}', "application/json")
            return
        op = str(p.get("op", ""))
        actor = str(p.get("actor", "unknown"))[:120]
        reason = str(p.get("reason", ""))[:300]
        ok, detail = False, "unknown op"
        if op == "app":
            ok, detail = do_app(str(p.get("service", "")), str(p.get("action", "")))
        elif op == "mirror-backup":
            ok, detail = do_mirror_backup()
        elif op == "pbs-backup":
            ok, detail = do_pbs_backup(str(p.get("vmid", "")))
        audit({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor,
               "op": op, "target": p.get("service") or p.get("vmid") or "", "reason": reason,
               "result": "ok" if ok else "error", "detail": detail if not ok else ""})
        with _lock:
            _cache["ts"] = 0
        self._send(200 if ok else 500, json.dumps({"ok": ok, "detail": detail}).encode("utf-8"), "application/json")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"sovereign-master-dashboard listening on {BIND}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
