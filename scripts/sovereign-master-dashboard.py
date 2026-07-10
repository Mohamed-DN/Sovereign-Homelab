#!/usr/bin/env python3
"""Sovereign Master Dashboard.

One unified operations dashboard, served from the Proxmox host, which is the only
place that can natively orchestrate everything:

  - live health (Uptime Kuma per-monitor), Immich status, the Windows mirror
    state, PBS snapshots, host CPU/RAM history, storage usage, per-guest load;
  - FORCE a Windows mirror backup (VM 110) and FORCE a PBS backup;
  - START/STOP the optional apps through the allowlist-only control agent;
  - a full launchpad of .internal service links with live status dots.

The UI is a self-contained page (no external assets): dark/light theme toggle,
animated stat tiles, SVG sparklines with crosshair tooltips, animated donuts,
responsive grid, reduced-motion support. Chart palette validated with the
dataviz six-checks (dark surface #0d1218 and light #fcfcfb both PASS).

Read-only status is open on the LAN/VPN. Control actions are allowlisted, ask
for an actor + reason, and are written to an audit log. The Docker socket is
never exposed to a browser; app control always goes through the agent.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from collections import deque
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
SAMPLE_EVERY = 10          # seconds between host samples
HISTORY = 120              # ring buffer length (120 x 10s = 20 min)
MAX_BODY = 64 * 1024

_cache: dict[str, Any] = {"ts": 0, "data": None}
_lock = threading.Lock()
_cpu_hist: deque[float] = deque(maxlen=HISTORY)
_mem_hist: deque[float] = deque(maxlen=HISTORY)
_prev_cpu: tuple[int, int] | None = None

# Launchpad links (mirrors the Homepage layout; .internal only, no public names).
LINKS: list[dict[str, Any]] = [
    {"group": "Network", "items": [
        {"name": "AdGuard Home", "icon": "\U0001F6E1️", "href": "https://adguard.internal", "desc": "DNS filtering and .internal rewrites", "kw": "adguard"},
        {"name": "Headscale UI", "icon": "\U0001F511", "href": "https://headscale.internal", "desc": "VPN users, devices, routes", "kw": "headscale"},
        {"name": "Nginx Proxy Manager", "icon": "\U0001F500", "href": "https://npm.internal", "desc": "Reverse proxy, aliases, certificates", "kw": "proxy"},
    ]},
    {"group": "Admin", "items": [
        {"name": "Proxmox VE", "icon": "\U0001F5A5️", "href": "https://proxmox.internal", "desc": "VMs, LXCs, storage", "kw": "proxmox ve"},
        {"name": "Proxmox Backup Server", "icon": "\U0001F4BE", "href": "https://pbs.internal", "desc": "Datastore, verify, restore", "kw": "backup server"},
    ]},
    {"group": "Identity", "items": [
        {"name": "Authentik", "icon": "\U0001FAAA", "href": "https://auth.internal", "desc": "SSO, MFA, proxy providers", "kw": "authentik"},
        {"name": "Trust Portal", "icon": "\U0001F4DC", "href": "https://trust.internal", "desc": "Install the internal CA", "kw": "trust"},
    ]},
    {"group": "Monitoring", "items": [
        {"name": "Uptime Kuma", "icon": "\U0001F4C8", "href": "https://status.internal", "desc": "Health checks and alerting", "kw": "kuma"},
        {"name": "Beszel", "icon": "\U0001F4CA", "href": "https://monitor.internal", "desc": "Host and container metrics", "kw": "beszel"},
        {"name": "Dozzle", "icon": "\U0001F9FE", "href": "https://logs.internal", "desc": "Live Docker logs", "kw": "dozzle"},
        {"name": "Homepage", "icon": "\U0001F3E0", "href": "https://homepage.internal", "desc": "Classic launchpad (rollback)", "kw": "homepage"},
        {"name": "NetAlertX", "icon": "\U0001F4E1", "href": "https://netalert.internal", "desc": "LAN device inventory", "kw": "netalert"},
        {"name": "Scrutiny", "icon": "\U0001F4BD", "href": "https://disks.internal", "desc": "SMART disk health", "kw": "scrutiny"},
        {"name": "ntfy", "icon": "\U0001F514", "href": "https://alerts.internal", "desc": "Push notifications", "kw": "ntfy"},
    ]},
    {"group": "Critical Data", "items": [
        {"name": "Vaultwarden", "icon": "\U0001F510", "href": "https://pwd.internal", "desc": "Password vault", "kw": "vaultwarden"},
        {"name": "Immich", "icon": "\U0001F4F7", "href": "https://foto.internal", "desc": "Photos - protected by PBS + dumps + mirror", "kw": "immich"},
        {"name": "Nextcloud", "icon": "☁️", "href": "https://files.internal", "desc": "Personal cloud", "kw": "nextcloud"},
        {"name": "Syncthing", "icon": "\U0001F501", "href": "https://sync.internal", "desc": "Peer-to-peer sync", "kw": "syncthing"},
        {"name": "Paperless-ngx", "icon": "\U0001F4C4", "href": "https://paper.internal", "desc": "OCR document archive", "kw": "paperless"},
    ]},
    {"group": "Apps", "items": [
        {"name": "Home Assistant", "icon": "\U0001F3E1", "href": "https://ha.internal", "desc": "Home automation", "kw": "home assistant"},
        {"name": "Jellyfin", "icon": "\U0001F3AC", "href": "https://media.internal", "desc": "Media server", "kw": "jellyfin"},
        {"name": "FreshRSS", "icon": "\U0001F4F0", "href": "https://rss.internal", "desc": "RSS reader", "kw": "freshrss"},
        {"name": "Karakeep", "icon": "\U0001F516", "href": "https://bookmarks.internal", "desc": "Bookmarks and archive", "kw": "karakeep"},
        {"name": "SearXNG", "icon": "\U0001F50E", "href": "https://search.internal", "desc": "Private metasearch", "kw": "searxng"},
        {"name": "Forgejo", "icon": "\U0001F33F", "href": "https://git.internal", "desc": "Git repositories", "kw": "forgejo"},
        {"name": "Open WebUI", "icon": "\U0001F916", "href": "https://ai.internal", "desc": "Local AI chat", "kw": "webui"},
    ]},
]


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


# ---------------------------------------------------------------- host sampler

def _sample_cpu() -> float | None:
    global _prev_cpu
    try:
        parts = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        nums = [int(x) for x in parts]
        idle, total = nums[3] + nums[4], sum(nums)
        if _prev_cpu is None:
            _prev_cpu = (idle, total)
            return None
        didle, dtotal = idle - _prev_cpu[0], total - _prev_cpu[1]
        _prev_cpu = (idle, total)
        if dtotal <= 0:
            return None
        return round(100.0 * (1 - didle / dtotal), 1)
    except (OSError, ValueError, IndexError):
        return None


def _sample_mem() -> float | None:
    try:
        info: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines()[:5]:
            k, v = line.split(":", 1)
            info[k] = int(v.strip().split()[0])
        total, avail = info["MemTotal"], info.get("MemAvailable", info.get("MemFree", 0))
        return round(100.0 * (1 - avail / total), 1)
    except (OSError, ValueError, KeyError):
        return None


def sampler_loop() -> None:
    while True:
        c = _sample_cpu()
        m = _sample_mem()
        if c is not None:
            _cpu_hist.append(c)
        if m is not None:
            _mem_hist.append(m)
        time.sleep(SAMPLE_EVERY)


# ---------------------------------------------------------------- data sources

def kuma_health() -> dict[str, Any]:
    code = (
        "import json,sqlite3\n"
        "p='/var/lib/docker/volumes/sovereign-observability_uptime_kuma_data/_data/kuma.db'\n"
        "c=sqlite3.connect(p);c.row_factory=sqlite3.Row\n"
        "rows=[]\n"
        "for m in c.execute('select id,name from monitor where active=1'):\n"
        "  h=c.execute('select status from heartbeat where monitor_id=? order by id desc limit 1',(m['id'],)).fetchone()\n"
        "  rows.append({'name':m['name'],'up':bool(h and h['status']==1)})\n"
        "print(json.dumps({'active':len(rows),'down':sum(1 for r in rows if not r['up']),'monitors':rows}))\n"
    )
    status, out = run(["pct", "exec", "101", "--", "python3", "-c", code], timeout=25)
    try:
        return json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return {"active": None, "down": None, "monitors": [], "error": True}


def guests() -> list[dict[str, Any]]:
    status, out = run(["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"], timeout=25)
    try:
        rows = json.loads(out)
        return [{
            "vmid": r.get("vmid"), "name": r.get("name", ""), "type": r.get("type"),
            "status": r.get("status"), "cpu": round(100 * float(r.get("cpu") or 0), 1),
            "mem_pct": round(100 * (r.get("mem") or 0) / (r.get("maxmem") or 1), 1),
            "uptime": r.get("uptime") or 0,
        } for r in sorted(rows, key=lambda x: x.get("vmid", 0))]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def storages() -> list[dict[str, Any]]:
    status, out = run(["pvesh", "get", "/nodes/pve/storage", "--output-format", "json"], timeout=25)
    try:
        rows = json.loads(out)
        result = []
        for r in rows:
            total = r.get("total") or 0
            if not r.get("active") or total <= 0:
                continue
            result.append({"name": r.get("storage"), "used_pct": round(100 * (r.get("used") or 0) / total, 1),
                           "used": r.get("used") or 0, "total": total})
        return sorted(result, key=lambda x: -x["total"])[:4]
    except (json.JSONDecodeError, TypeError):
        return []


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
            data = dict(_cache["data"])
            data["cpu_hist"] = list(_cpu_hist)
            data["mem_hist"] = list(_mem_hist)
            data["jobs"] = jobs_public()
            return data
    data = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "guests": guests(),
        "kuma": kuma_health(),
        "immich": immich_and_mirror(),
        "pbs": pbs_latest(),
        "apps": app_status(),
        "storages": storages(),
        "links": LINKS,
        "sample_every": SAMPLE_EVERY,
        "retention": RETENTION,
        "guest_power": GUEST_POWER_ALLOW,
    }
    with _lock:
        _cache["data"] = data
        _cache["ts"] = time.time()
    data = dict(data)
    data["cpu_hist"] = list(_cpu_hist)
    data["mem_hist"] = list(_mem_hist)
    data["jobs"] = jobs_public()
    return data


# ---------------------------------------------------------------- actions

RELAY_URL = os.environ.get("DASH_RELAY_URL", "http://192.168.1.51:8099/report")
RELAY_TOKEN_FILE = os.environ.get("DASH_RELAY_TOKEN_FILE", "/root/sovereign-secrets/alert-relay-token")
RETENTION = "keep-daily=7, keep-weekly=4, keep-monthly=6 (auto-prune dopo ogni backup riuscito)"

# Background job registry: at most one job per key ("mirror", "pbs-<vmid>").
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def relay_token() -> str:
    try:
        return Path(RELAY_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def notify_email(subject: str, text: str, color: str = "#059669") -> None:
    """Best-effort outcome email through the alert relay. Never raises."""
    token = relay_token()
    if not token:
        print("relay token missing; outcome email skipped")
        return
    html_body = (
        f'<div style="font-family:Segoe UI,Arial,sans-serif;background:#06080b;color:#e5e7eb;padding:22px">'
        f'<div style="max-width:560px;margin:auto;background:#0d1218;border:1px solid #1f2937;'
        f'border-left:4px solid {color};border-radius:10px;overflow:hidden">'
        f'<div style="background:{color};padding:16px 22px;color:#fff;font-size:18px;font-weight:800">{subject}</div>'
        f'<div style="padding:16px 22px;font-size:14px;line-height:1.7;white-space:pre-line">{text}</div>'
        f'<div style="padding:12px 22px;background:#06080b;color:#6b7a8d;font-size:12px;border-top:1px solid #1f2937">'
        f'Sovereign Homelab &middot; master dashboard</div></div></div>'
    )
    payload = json.dumps({"subject": subject, "text": subject + "\n\n" + text, "html": html_body}).encode()
    req = urllib.request.Request(RELAY_URL, data=payload, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as exc:  # noqa: BLE001
        print(f"outcome email failed: {exc}")


def job_start(key: str, label: str) -> bool:
    with _jobs_lock:
        job = _jobs.get(key)
        if job and job.get("state") == "running":
            return False
        _jobs[key] = {"state": "running", "label": label, "started": time.time()}
        return True


def job_end(key: str, ok: bool, detail: str) -> None:
    with _jobs_lock:
        job = _jobs.get(key, {})
        job.update({"state": "ok" if ok else "error", "detail": detail[:300],
                    "ended": time.time(), "duration_s": int(time.time() - job.get("started", time.time()))})
        _jobs[key] = job
    with _lock:
        _cache["ts"] = 0


def jobs_public() -> dict[str, Any]:
    with _jobs_lock:
        return {k: {kk: vv for kk, vv in v.items() if kk != "detail" or v.get("state") == "error"}
                for k, v in _jobs.items()}


def _fmt_dur(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else (f"{minutes}m {sec}s" if minutes else f"{sec}s")


def _pbs_worker(vmid: str, actor: str, reason: str) -> None:
    key = f"pbs-{vmid}"
    started = time.time()
    status, out = run(["vzdump", vmid, "--storage", PBS_STORAGE, "--mode", "snapshot", "--node", "pve"],
                      timeout=6 * 3600)
    ok = status == 0 and "finished successfully" in out.lower()
    dur = _fmt_dur(int(time.time() - started))
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    job_end(key, ok, tail)
    if ok:
        notify_email(f"✅ Backup PBS VM{vmid} completato",
                     f"Attore: {actor}\nMotivo: {reason}\nDurata: {dur}\n"
                     f"Retention: {RETENTION}\nI vecchi snapshot oltre la policy sono stati eliminati automaticamente.",
                     "#059669")
    else:
        notify_email(f"❌ Backup PBS VM{vmid} FALLITO",
                     f"Attore: {actor}\nMotivo: {reason}\nDurata: {dur}\nUltima riga: {tail}\n"
                     f"Controlla /var/log e la dashboard PBS.", "#dc2626")


def _mirror_worker(actor: str, reason: str) -> None:
    key = "mirror"
    started = time.time()
    status, raw = run(["qm", "guest", "exec", "110", "--", "bash", "-lc",
                       "systemctl start --no-block sovereign-immich-windows-restic.service && echo started"], timeout=30)
    if "started" not in guest_out(raw):
        job_end(key, False, guest_out(raw)[:200] or "start failed")
        notify_email("❌ Mirror Windows: avvio fallito",
                     f"Attore: {actor}\nMotivo: {reason}\nDettaglio: {guest_out(raw)[:200]}", "#dc2626")
        return
    # Poll until the unit finishes (the run exits cleanly if the PC is offline).
    deadline = time.time() + 6 * 3600
    state = "activating"
    while time.time() < deadline:
        time.sleep(30)
        s, raw = run(["qm", "guest", "exec", "110", "--", "systemctl", "is-active",
                      "sovereign-immich-windows-restic"], timeout=25)
        state = guest_out(raw).strip() or "unknown"
        if state not in {"activating", "active", "reloading"}:
            break
    dur = _fmt_dur(int(time.time() - started))
    s, raw = run(["qm", "guest", "exec", "110", "--", "cat",
                  "/root/sovereign-secrets/immich-windows/state/last-mirror.json"], timeout=25)
    snap, check = "-", "-"
    fresh = False
    try:
        st = json.loads(guest_out(raw) or "{}")
        snap, check = st.get("snapshot_id", "-"), st.get("check_result", "-")
        created = st.get("created_utc", "")
        when = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        fresh = (datetime.now(timezone.utc) - when).total_seconds() < 2 * 3600 + (time.time() - started)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    ok = state == "inactive" and fresh and check == "passed"
    job_end(key, ok, f"state={state} snapshot={snap} check={check}")
    if ok:
        notify_email("✅ Mirror Windows completato",
                     f"Attore: {actor}\nMotivo: {reason}\nDurata: {dur}\nSnapshot: {snap}\nCheck: {check}\n"
                     f"Retention restic: last 3, daily 7, weekly 8, monthly 12 (i vecchi vengono eliminati automaticamente).",
                     "#059669")
    elif state == "inactive" and not fresh:
        notify_email("ℹ️ Mirror Windows: nessun nuovo snapshot",
                     f"Il run è terminato senza un nuovo snapshot (PC Windows spento o non raggiungibile).\n"
                     f"Attore: {actor}\nMotivo: {reason}\nDurata: {dur}", "#d97706")
    else:
        notify_email("❌ Mirror Windows FALLITO",
                     f"Attore: {actor}\nMotivo: {reason}\nDurata: {dur}\nStato: {state}\nSnapshot: {snap} Check: {check}",
                     "#dc2626")


def audit(entry: dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as h:
        h.write(json.dumps(entry, sort_keys=True) + "\n")
    try:
        AUDIT_LOG.chmod(0o600)
    except OSError:
        pass


def do_app(service: str, action: str, actor: str, reason: str) -> tuple[bool, str]:
    body = json.dumps({"service": service, "action": action, "actor": actor, "reason": reason}).encode()
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


def do_mirror_backup(actor: str, reason: str) -> tuple[bool, str]:
    if not job_start("mirror", "Mirror Windows"):
        return False, "un mirror è già in corso"
    threading.Thread(target=_mirror_worker, args=(actor, reason), daemon=True).start()
    return True, "avviato; riceverai una email con l'esito"


# Whole-VM power control, owner-approved for these guests only. Immich (110) and
# infrastructure guests are deliberately absent and can never be powered off here.
GUEST_POWER_ALLOW = {"120": "Nextcloud", "130": "Home Assistant"}


def do_guest_power(vmid: str, action: str, actor: str, reason: str) -> tuple[bool, str]:
    if vmid not in GUEST_POWER_ALLOW:
        return False, f"guest not allowed: {vmid}"
    if action not in {"start", "stop"}:
        return False, "action must be start or stop"
    name = GUEST_POWER_ALLOW[vmid]
    if action == "stop":
        status, out = run(["qm", "shutdown", vmid, "--timeout", "180"], timeout=200)
    else:
        status, out = run(["qm", "start", vmid], timeout=90)
    ok = status == 0
    verb = "spento" if action == "stop" else "avviato"
    notify_email(
        f"{'⏹️' if action == 'stop' else '▶️'} {name} (VM{vmid}) {verb}" if ok else f"❌ {name} (VM{vmid}) {action} fallito",
        f"Attore: {actor}\nMotivo: {reason}\nDettaglio: {out[:200] or 'ok'}",
        "#059669" if ok else "#dc2626")
    with _lock:
        _cache["ts"] = 0
    return ok, out[:200]


def do_pbs_backup(vmid: str, actor: str, reason: str) -> tuple[bool, str]:
    if vmid not in PBS_BACKUP_ALLOW:
        return False, f"vmid not allowed: {vmid}"
    if not job_start(f"pbs-{vmid}", f"PBS VM{vmid}"):
        return False, f"un backup PBS di {vmid} è già in corso"
    threading.Thread(target=_pbs_worker, args=(vmid, actor, reason), daemon=True).start()
    return True, "avviato; riceverai una email con l'esito"


# ---------------------------------------------------------------- UI

PAGE = r"""<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sovereign Dashboard</title><style>
:root, :root[data-theme="dark"]{
 --bg:#06080b;--plane:#0a0e13;--surface:#0d1218;--raised:#121922;--glass:rgba(13,18,24,.72);
 --line:rgba(148,163,184,.16);--line-strong:rgba(148,163,184,.32);
 --ink:#f4f7fb;--ink2:#c3c9d4;--muted:#8b98a9;--grid:#232a33;
 --accent:#22d3ee;--s1:#3987e5;--s2:#199e70;
 --good:#0ca30c;--warn:#fab219;--crit:#d03b3b;
 --led-good:#2dd4a7;--led-warn:#fbbf24;--led-bad:#fb7185;
 --glow:rgba(34,211,238,.35);--shadow:0 14px 34px rgba(0,0,0,.38);
}
:root[data-theme="light"]{
 --bg:#f9f9f7;--plane:#f3f3f0;--surface:#fcfcfb;--raised:#ffffff;--glass:rgba(252,252,251,.8);
 --line:rgba(11,11,11,.10);--line-strong:rgba(11,11,11,.2);
 --ink:#0b0b0b;--ink2:#3c3b38;--muted:#6b6a64;--grid:#e1e0d9;
 --accent:#0e7490;--s1:#2a78d6;--s2:#1baf7a;
 --good:#0ca30c;--warn:#b45309;--crit:#d03b3b;
 --led-good:#059669;--led-warn:#b45309;--led-bad:#dc2626;
 --glow:rgba(14,116,144,.22);--shadow:0 12px 28px rgba(11,11,11,.10);
}
*{box-sizing:border-box}html{background:var(--bg)}
body{margin:0;min-height:100vh;color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);
background-image:radial-gradient(1200px 500px at 80% -10%, var(--glow), transparent 60%),linear-gradient(color-mix(in srgb,var(--accent) 4%,transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb,var(--accent) 4%,transparent) 1px,transparent 1px);
background-size:auto,34px 34px,34px 34px;background-attachment:fixed;transition:background-color .3s ease,color .3s ease}
header{position:sticky;top:0;z-index:40;display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;padding:13px 20px;
border-bottom:1px solid var(--line-strong);background:var(--glass);backdrop-filter:blur(18px)}
.brand h1{margin:0;font-size:1.02rem;letter-spacing:.05em}.brand .sub{color:var(--muted);font-size:.72rem;margin-top:2px}
.hright{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 13px;border-radius:999px;font-weight:700;font-size:.78rem;border:1px solid var(--line-strong);background:var(--surface)}
#clock{color:var(--muted);font-size:.78rem;font-variant-numeric:tabular-nums}
.iconbtn{width:38px;height:38px;border-radius:10px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);font-size:1.05rem;cursor:pointer;display:grid;place-items:center;transition:transform .15s ease}
.iconbtn:hover{transform:translateY(-1px);border-color:var(--accent)}
.iconbtn:focus-visible,.btn:focus-visible,.tab:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
nav.tabs{position:sticky;top:64px;z-index:30;display:flex;gap:6px;padding:10px 20px;overflow-x:auto;background:var(--glass);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.tab{padding:9px 18px;border-radius:9px;font-weight:700;font-size:.85rem;color:var(--muted);border:1px solid transparent;background:transparent;cursor:pointer;white-space:nowrap;transition:all .18s ease}
.tab:hover{color:var(--ink);background:color-mix(in srgb,var(--accent) 9%,transparent)}
.tab.on{color:var(--ink);background:var(--surface);border-color:var(--line-strong);box-shadow:inset 0 -2px 0 var(--accent)}
.wrap{max-width:min(2280px,96vw);margin:0 auto;padding:20px clamp(16px,3vw,52px)}
@media(min-width:1900px){.tiles{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.charts{grid-template-columns:repeat(3,1fr)}}
@media(min-width:2600px){.grid{grid-template-columns:repeat(auto-fill,minmax(290px,1fr))}}
section.page{display:none;animation:fadein .35s ease}
section.page.on{display:block}
@keyframes fadein{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
h2{display:flex;align-items:center;gap:10px;min-height:34px;margin:24px 0 12px;padding:0 12px;border:1px solid var(--line);border-left:3px solid var(--sec,var(--accent));border-radius:6px;background:var(--surface);font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em}
h2:first-child{margin-top:2px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:12px}
.tile{position:relative;overflow:hidden;padding:15px 16px;border:1px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:var(--shadow)}
.tile::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--tc,var(--accent));opacity:.85}
.tile .k{color:var(--muted);font-size:.68rem;text-transform:uppercase;letter-spacing:.07em}
.tile .v{font-size:1.65rem;font-weight:800;margin-top:6px;font-variant-numeric:tabular-nums}
.tile .f{color:var(--muted);font-size:.72rem;margin-top:4px}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-top:14px}
.chart{position:relative;padding:16px;border:1px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:var(--shadow)}
.chart .t{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.chart .t .n{font-weight:700;font-size:.86rem}
.chart .t .now{font-weight:800;font-size:1.15rem;font-variant-numeric:tabular-nums}
.chart .t .u{color:var(--muted);font-size:.72rem;margin-left:5px}
.chart svg{width:100%;height:96px;display:block}
.tip{position:absolute;pointer-events:none;background:var(--raised);border:1px solid var(--line-strong);border-radius:7px;padding:5px 9px;font-size:.74rem;font-variant-numeric:tabular-nums;opacity:0;transform:translate(-50%,-115%);white-space:nowrap;box-shadow:var(--shadow);z-index:5}
.donuts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:14px}
.donut{display:flex;align-items:center;gap:12px;padding:13px 15px;border:1px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:var(--shadow)}
.donut svg{width:62px;height:62px;flex:0 0 auto}
.donut .ring{fill:none;stroke:var(--grid);stroke-width:8}
.donut .arc{fill:none;stroke-width:8;stroke-linecap:round;transform:rotate(-90deg);transform-origin:center;transition:stroke-dashoffset 1s cubic-bezier(.22,1,.36,1)}
.donut .dl{font-weight:800;font-size:.95rem;font-variant-numeric:tabular-nums}
.donut .ds{color:var(--muted);font-size:.72rem;margin-top:2px}
.guests{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:10px;margin-top:14px}
.guest{padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
.guest .gt{display:flex;justify-content:space-between;align-items:center;font-size:.83rem;font-weight:700}
.guest .gid{color:var(--muted);font-weight:500;font-size:.72rem}
.bar{height:6px;border-radius:4px;background:var(--grid);margin-top:7px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:4px;background:var(--s1);width:0;transition:width .9s cubic-bezier(.22,1,.36,1)}
.bar.m i{background:var(--s2)}
.bl{display:flex;justify-content:space-between;color:var(--muted);font-size:.66rem;margin-top:3px;font-variant-numeric:tabular-nums}
.led{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.up .led,.led.up{background:var(--led-good);box-shadow:0 0 9px var(--led-good)}
.dn .led,.led.dn{background:var(--led-bad);box-shadow:0 0 9px var(--led-bad)}
.wa .led,.led.wa{background:var(--led-warn);box-shadow:0 0 9px var(--led-warn)}
.led.nn{background:var(--muted);opacity:.4}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card{position:relative;padding:15px;border:1px solid var(--line);border-left:3px solid var(--sec,var(--accent));border-radius:13px;background:var(--surface);box-shadow:var(--shadow);transition:transform .18s ease,border-color .18s ease}
.card:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--sec,var(--accent)) 55%,var(--line))}
.card .top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.card .name{font-size:1rem;font-weight:800}
.state{display:inline-flex;align-items:center;gap:7px;font-size:.78rem;color:var(--muted)}
.rows{margin-top:8px;font-size:.78rem;color:var(--muted);line-height:1.65}
.btn{margin-top:12px;width:100%;padding:9px;border-radius:8px;font-weight:800;font-size:.82rem;cursor:pointer;border:1px solid var(--line-strong);color:var(--ink);background:var(--raised);transition:all .15s ease}
.btn:hover{border-color:var(--accent)}.btn:disabled{opacity:.5;cursor:wait}
.btn.stop{border-color:color-mix(in srgb,var(--led-bad) 55%,transparent);color:var(--led-bad)}
.btn.start{border-color:color-mix(in srgb,var(--led-good) 55%,transparent);color:var(--led-good)}
.btn.act{border-color:color-mix(in srgb,var(--s1) 55%,transparent);color:var(--s1)}
a.link{display:flex;gap:12px;align-items:center;padding:13px 15px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);text-decoration:none;box-shadow:var(--shadow);transition:transform .16s ease,border-color .16s ease}
a.link:hover{transform:translateY(-3px);border-color:var(--accent)}
a.link .ic{font-size:1.45rem;width:40px;height:40px;display:grid;place-items:center;border-radius:10px;background:color-mix(in srgb,var(--accent) 9%,transparent);border:1px solid color-mix(in srgb,var(--accent) 22%,transparent)}
a.link .ln{font-weight:700;font-size:.88rem;display:flex;align-items:center;gap:7px}
a.link .ld{color:var(--muted);font-size:.72rem;margin-top:2px}
.note{color:var(--muted);font-size:.77rem;margin:6px 0 14px}
/* Assistant: a faceless animated orb that speaks tips (toggle-able) */
#asst{position:fixed;right:20px;bottom:20px;z-index:55;display:flex;align-items:flex-end;gap:12px;flex-direction:row-reverse}
#orb{width:58px;height:58px;border-radius:50%;cursor:pointer;flex:0 0 auto;position:relative;border:none;
 background:radial-gradient(circle at 32% 30%, #7ff0ff, var(--accent) 42%, #1b6ea3 78%);box-shadow:0 0 0 1px var(--line-strong),0 10px 30px rgba(0,0,0,.4),0 0 26px var(--glow)}
#orb::before,#orb::after{content:"";position:absolute;inset:0;border-radius:50%;border:2px solid var(--accent);opacity:.5}
#orb .wv{position:absolute;left:50%;top:50%;width:22px;height:22px;transform:translate(-50%,-50%);display:flex;gap:2.5px;align-items:center}
#orb .wv i{width:3px;background:#04222e;border-radius:3px;opacity:.85}
#bubble{max-width:min(340px,70vw);background:var(--raised);border:1px solid var(--line-strong);border-radius:14px 14px 4px 14px;
 padding:12px 14px;font-size:.83rem;line-height:1.5;box-shadow:var(--shadow);opacity:0;transform:translateY(10px) scale(.96);
 transform-origin:bottom right;transition:all .28s cubic-bezier(.22,1,.36,1);pointer-events:none}
#bubble.show{opacity:1;transform:none;pointer-events:auto}
#bubble b{color:var(--accent)}
#bubble .x{float:right;margin-left:10px;color:var(--muted);cursor:pointer;font-weight:800}
#bubble .hint{display:block;margin-top:8px;color:var(--muted);font-size:.72rem}
#asst.off #bubble{display:none}#asst.off #orb{opacity:.55;filter:grayscale(.5)}
@media(prefers-reduced-motion:no-preference){
 #orb::before{animation:ring 2.8s ease-out infinite}#orb::after{animation:ring 2.8s ease-out .9s infinite}
 @keyframes ring{0%{transform:scale(1);opacity:.5}100%{transform:scale(1.7);opacity:0}}
 #orb .wv i{animation:eq 1.1s ease-in-out infinite}
 #orb .wv i:nth-child(2){animation-delay:.15s}#orb .wv i:nth-child(3){animation-delay:.3s}#orb .wv i:nth-child(4){animation-delay:.45s}
 @keyframes eq{0%,100%{height:6px}50%{height:20px}}
}
@media(prefers-reduced-motion:reduce){#orb .wv i{height:12px}}
#toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%) translateY(20px);padding:12px 18px;border-radius:10px;background:var(--raised);border:1px solid var(--line-strong);font-size:.85rem;opacity:0;transition:all .25s ease;pointer-events:none;max-width:92vw;box-shadow:var(--shadow);z-index:60}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
@media(prefers-reduced-motion:no-preference){
 .up .led,.led.up{animation:pulse 2.6s ease-in-out infinite}
 @keyframes pulse{0%,100%{opacity:.65}50%{opacity:1}}
 .spark path.line{stroke-dasharray:1200;stroke-dashoffset:1200;animation:draw 1.2s ease forwards}
 @keyframes draw{to{stroke-dashoffset:0}}
}
@media(prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}
@media(max-width:720px){.wrap{padding:12px}nav.tabs{top:58px;padding:8px 12px}.tile .v{font-size:1.35rem}header{padding:11px 14px}}
</style></head><body>
<header>
 <div class="brand"><h1>SOVEREIGN DASHBOARD</h1><div class="sub">Proxmox &middot; VPN/LAN only</div></div>
 <div class="hright">
  <span id="clock"></span>
  <span class="pill" id="statuspill"><span class="led nn"></span><span id="statustxt">loading&hellip;</span></span>
  <button class="iconbtn" id="themebtn" title="Tema chiaro/scuro" aria-label="Toggle theme">&#127769;</button>
 </div>
</header>
<nav class="tabs" role="tablist">
 <button class="tab on" data-p="overview">Overview</button>
 <button class="tab" data-p="services">Servizi</button>
 <button class="tab" data-p="data">Dati &amp; Backup</button>
 <button class="tab" data-p="apps">Apps</button>
</nav>
<div class="wrap">

<section class="page on" id="p-overview" style="--sec:var(--accent)">
 <h2>Stato del sistema</h2>
 <div class="tiles" id="tiles"></div>
 <div class="charts">
  <div class="chart" id="c-cpu"><div class="t"><span class="n">CPU host</span><span><span class="now" id="cpu-now">-</span><span class="u">%</span></span></div><svg class="spark" viewBox="0 0 600 96" preserveAspectRatio="none"></svg><div class="tip"></div></div>
  <div class="chart" id="c-mem"><div class="t"><span class="n">RAM host</span><span><span class="now" id="mem-now">-</span><span class="u">%</span></span></div><svg class="spark" viewBox="0 0 600 96" preserveAspectRatio="none"></svg><div class="tip"></div></div>
 </div>
 <h2 style="--sec:var(--s1)">Storage</h2>
 <div class="donuts" id="donuts"></div>
 <h2 style="--sec:var(--s2)">Guest (VM &amp; LXC)</h2>
 <div class="guests" id="guests"></div>
</section>

<section class="page" id="p-services" style="--sec:var(--accent)">
 <div id="linkgroups"></div>
</section>

<section class="page" id="p-data" style="--sec:var(--led-warn)">
 <h2 style="--sec:var(--led-warn)">Dati critici &amp; backup</h2>
 <p class="note">Immich non &egrave; mai arrestabile da qui. Forzare un backup &egrave; sempre sicuro.</p>
 <div class="grid" id="dcards"></div>
 <h2 style="--sec:var(--led-good)">Snapshot PBS</h2>
 <div class="grid" id="pbscards"></div>
</section>

<section class="page" id="p-apps" style="--sec:#a78bfa">
 <h2 style="--sec:#a78bfa">Apps &mdash; start / stop</h2>
 <p class="note">Ogni azione chiede nome + motivo, va nell'audit log e invia una email. Le app con 💾 contengono dati e vengono fermate in modo pulito. <b>Immich, Vaultwarden, NPM, AdGuard, Headscale, PBS, Authentik</b> non sono mai arrestabili da qui.</p>
 <div class="grid" id="acards"></div>
 <h2 style="--sec:#60a5fa">Guest interi (VM)</h2>
 <p class="note">Spegnimento/accensione pulito (ACPI) delle VM approvate. Immich (VM110) e l'infrastruttura non sono qui.</p>
 <div class="grid" id="vmcards"></div>
</section>

</div>
<div id="asst">
 <button id="orb" title="Assistente Sovereign" aria-label="Assistente"><span class="wv"><i></i><i></i><i></i><i></i></span></button>
 <div id="bubble"><span class="x" id="asstx">&times;</span><span id="asstmsg">Ciao! Sono l'assistente.</span><span class="hint">Clicca l'orb per un altro consiglio &middot; la &times; lo nasconde</span></div>
</div>
<div id="toast"></div>
<script>
const $=id=>document.getElementById(id),toast=$('toast');
let D=null,first=true;
/* ---------- theme ---------- */
const root=document.documentElement,tbtn=$('themebtn');
function setTheme(t){root.dataset.theme=t;tbtn.innerHTML=t==='dark'?'&#127769;':'&#9728;&#65039;';localStorage.setItem('sov-theme',t);}
setTheme(localStorage.getItem('sov-theme')||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'));
tbtn.onclick=()=>{setTheme(root.dataset.theme==='dark'?'light':'dark');if(D)render();};
/* ---------- tabs ---------- */
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
 document.querySelectorAll('.page').forEach(p=>p.classList.toggle('on',p.id==='p-'+b.dataset.p));
});
/* ---------- utils ---------- */
function t(m){toast.textContent=m;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),3800);}
function ago(h){if(h==null)return'?';if(h<1)return Math.round(h*60)+' min fa';if(h<48)return h.toFixed(1)+' h fa';return (h/24).toFixed(1)+' g fa';}
function gb(b){return b?(b/1073741824).toFixed(1)+' GB':'-';}
function upd(){const n=new Date();$('clock').textContent=n.toLocaleDateString()+' '+n.toLocaleTimeString();}
setInterval(upd,1000);upd();
function countup(el,val,dec=0,suf=''){
 if(matchMedia('(prefers-reduced-motion: reduce)').matches){el.textContent=val.toFixed(dec)+suf;return;}
 const st=performance.now(),from=0,dur=900;
 function step(ts){const p=Math.min(1,(ts-st)/dur),e=1-Math.pow(1-p,3);
  el.textContent=(from+(val-from)*e).toFixed(dec)+suf;if(p<1)requestAnimationFrame(step);}
 requestAnimationFrame(step);
}
/* ---------- sparkline ---------- */
function css(v){return getComputedStyle(root).getPropertyValue(v).trim();}
function spark(card,data,color){
 const svg=card.querySelector('svg'),tip=card.querySelector('.tip');
 if(!data.length){svg.innerHTML='';return;}
 const W=600,H=96,P=6,n=data.length,max=Math.max(20,...data),min=0;
 const X=i=>P+(W-2*P)*i/Math.max(1,n-1),Y=v=>H-P-(H-2*P)*(v-min)/(max-min);
 let dl='M'+X(0)+','+Y(data[0]);for(let i=1;i<n;i++)dl+=' L'+X(i)+','+Y(data[i]);
 const da=dl+' L'+X(n-1)+','+(H-P)+' L'+X(0)+','+(H-P)+' Z';
 const gid='g'+Math.random().toString(36).slice(2,7);
 svg.innerHTML=`<defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0%" stop-color="${color}" stop-opacity=".28"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
  <line x1="${P}" y1="${Y(25)}" x2="${W-P}" y2="${Y(25)}" stroke="${css('--grid')}" stroke-width="1"/>
  <line x1="${P}" y1="${Y(50)}" x2="${W-P}" y2="${Y(50)}" stroke="${css('--grid')}" stroke-width="1"/>
  <line x1="${P}" y1="${Y(75)}" x2="${W-P}" y2="${Y(75)}" stroke="${css('--grid')}" stroke-width="1"/>
  <path d="${da}" fill="url(#${gid})"/>
  <path class="line" d="${dl}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
  <circle class="dot" r="4" fill="${color}" stroke="${css('--surface')}" stroke-width="2" style="opacity:0"/>
  <line class="cross" y1="${P}" y2="${H-P}" stroke="${css('--line-strong')}" stroke-width="1" style="opacity:0"/>`;
 const dot=svg.querySelector('.dot'),cross=svg.querySelector('.cross');
 svg.onmousemove=e=>{
  const r=svg.getBoundingClientRect(),fx=(e.clientX-r.left)/r.width*W;
  const i=Math.round((fx-P)/((W-2*P)/Math.max(1,n-1)));if(i<0||i>=n)return;
  dot.setAttribute('cx',X(i));dot.setAttribute('cy',Y(data[i]));dot.style.opacity=1;
  cross.setAttribute('x1',X(i));cross.setAttribute('x2',X(i));cross.style.opacity=1;
  const secs=(n-1-i)*(D?D.sample_every:10);
  tip.textContent=data[i].toFixed(1)+'%  ·  '+(secs===0?'ora':secs<60?secs+'s fa':Math.round(secs/60)+'m fa');
  tip.style.left=(X(i)/W*100)+'%';tip.style.top='38px';tip.style.opacity=1;};
 svg.onmouseleave=()=>{dot.style.opacity=0;cross.style.opacity=0;tip.style.opacity=0;};
}
/* ---------- donut ---------- */
function donut(name,pct,sub){
 const r=24,c=2*Math.PI*r,off=c*(1-pct/100);
 const col=pct>=90?css('--crit'):pct>=75?css('--warn'):css('--s1');
 return `<div class="donut"><svg viewBox="0 0 62 62">
  <circle class="ring" cx="31" cy="31" r="${r}"/>
  <circle class="arc" cx="31" cy="31" r="${r}" stroke="${col}" stroke-dasharray="${c}" stroke-dashoffset="${first?c:off}" data-off="${off}"/>
  <text x="31" y="35" text-anchor="middle" font-size="13" font-weight="800" fill="${css('--ink')}">${pct.toFixed(0)}%</text></svg>
  <div><div class="dl">${name}</div><div class="ds">${sub}</div></div></div>`;
}
/* ---------- job-aware button ---------- */
function jobbtn(key,call,label){
 const j=(D&&D.jobs)?D.jobs[key]:null;
 if(j&&j.state==='running'){
  const el=Math.round((Date.now()/1000)-(j.started||Date.now()/1000));
  const mm=Math.floor(el/60),ss=el%60;
  return `<button class="btn act" disabled>⏳ In corso… ${mm}m ${String(ss).padStart(2,'0')}s · email all'esito</button>`;
 }
 let extra='';
 if(j&&j.state==='ok')extra=`<div class="rows" style="color:var(--led-good)">✅ ultimo run OK (${Math.round((j.duration_s||0)/60)}m)</div>`;
 if(j&&j.state==='error')extra=`<div class="rows" style="color:var(--led-bad)">❌ ultimo run fallito${j.detail?': '+j.detail:''}</div>`;
 return extra+`<button class="btn act" onclick="${call}">${label}</button>`;
}
/* ---------- render ---------- */
function render(){
 const d=D,down=d.kuma.down||0,crit=!d.immich.immich_ping;
 const sp=$('statuspill'),stt=$('statustxt');
 stt.textContent=crit?'ATTENZIONE: Immich':down?down+' monitor giù':'tutto operativo';
 sp.querySelector('.led').className='led '+(crit?'dn':down?'wa':'up');
 const m=d.immich.mirror||{};
 const run_g=d.guests.filter(g=>g.status==='running').length;
 const tiles=[
  ['Guest attivi',run_g+'/'+d.guests.length,'VM + LXC','var(--accent)',run_g,0,'/'+d.guests.length],
  ['Monitor OK',((d.kuma.active||0)-down)+'/'+(d.kuma.active||0),down?down+' giù':'tutto su','var(--s2)',(d.kuma.active||0)-down,0,'/'+(d.kuma.active||0)],
  ['Foto Immich',d.immich.files??'-','protette · '+gb(d.immich.photos_bytes),'var(--led-warn)',d.immich.files||0,0,''],
  ['Dump DB',ago(d.immich.protection_dump_age_h),'app-aware giornaliero','var(--s1)',null],
  ['Mirror Windows',m.configured?ago(m.age_h):'non config.',(m.check==='passed'?'check OK ':'')+(m.snapshot?'· '+m.snapshot:''),'var(--accent)',null],
  ['PBS VM110',(d.pbs['110']||'-').slice(5,16).replace('T',' '),'ultimo snapshot','var(--s2)',null],
 ];
 $('tiles').innerHTML=tiles.map((x,i)=>`<div class="tile" style="--tc:${x[3]}"><div class="k">${x[0]}</div><div class="v" id="tv${i}">${x[1]}</div><div class="f">${x[2]}</div></div>`).join('');
 tiles.forEach((x,i)=>{if(first&&x[4]!=null)countup($('tv'+i),x[4],x[5],x[6]);});
 /* charts */
 if(d.cpu_hist.length){$('cpu-now').textContent=d.cpu_hist[d.cpu_hist.length-1].toFixed(0);spark($('c-cpu'),d.cpu_hist,css('--s1'));}
 if(d.mem_hist.length){$('mem-now').textContent=d.mem_hist[d.mem_hist.length-1].toFixed(0);spark($('c-mem'),d.mem_hist,css('--s2'));}
 /* donuts */
 $('donuts').innerHTML=d.storages.map(s=>donut(s.name,s.used_pct,gb(s.used)+' / '+gb(s.total))).join('');
 requestAnimationFrame(()=>requestAnimationFrame(()=>{document.querySelectorAll('.donut .arc').forEach(a=>a.style.strokeDashoffset=a.dataset.off);}));
 /* guests */
 $('guests').innerHTML=d.guests.map(g=>`<div class="guest ${g.status==='running'?'up':'dn'}">
  <div class="gt"><span style="display:flex;align-items:center;gap:7px"><span class="led"></span>${g.name||g.vmid}</span><span class="gid">${g.type==='qemu'?'VM':'LXC'} ${g.vmid}</span></div>
  <div class="bar"><i style="width:0" data-w="${Math.min(100,g.cpu)}%"></i></div><div class="bl"><span>CPU</span><span>${g.cpu.toFixed(1)}%</span></div>
  <div class="bar m"><i style="width:0" data-w="${Math.min(100,g.mem_pct)}%"></i></div><div class="bl"><span>RAM</span><span>${g.mem_pct.toFixed(1)}%</span></div></div>`).join('');
 requestAnimationFrame(()=>requestAnimationFrame(()=>{document.querySelectorAll('.guest .bar i').forEach(b=>b.style.width=b.dataset.w);}));
 /* services links + status dots */
 const mons=(d.kuma.monitors||[]).map(x=>({n:x.name.toLowerCase(),up:x.up}));
 function dot(kw){const f=mons.find(x=>x.n.includes(kw));return f?(f.up?'up':'dn'):'nn';}
 $('linkgroups').innerHTML=d.links.map(g=>`<h2>${g.group}</h2><div class="grid">${g.items.map(it=>
  `<a class="link" href="${it.href}" target="_blank" rel="noopener"><span class="ic">${it.icon}</span>
   <span><span class="ln">${it.name} <span class="led ${dot(it.kw)}"></span></span><br><span class="ld">${it.desc}</span></span></a>`).join('')}</div>`).join('');
 /* data & backup */
 $('dcards').innerHTML=`
  <div class="card" style="--sec:var(--led-warn)"><div class="top"><span class="name">📷 Immich</span><span class="state ${d.immich.immich_ping?'up':'dn'}"><span class="led"></span>${d.immich.immich_ping?'healthy':'CHECK'}</span></div>
   <div class="rows">File: <b>${d.immich.files??'-'}</b> · ${gb(d.immich.photos_bytes)}<br>Dump protezione: ${ago(d.immich.protection_dump_age_h)}<br><a class="ld" href="https://foto.internal" target="_blank" style="color:var(--accent)">foto.internal ↗</a></div></div>
  <div class="card" style="--sec:var(--accent)"><div class="top"><span class="name">🪞 Mirror Windows</span><span class="state ${m.configured?(m.age_h>168?'wa':'up'):'wa'}"><span class="led"></span>${m.configured?ago(m.age_h):'non configurato'}</span></div>
   <div class="rows">Snapshot: <b>${m.snapshot||'-'}</b> · check: ${m.check||'-'}<br>Retention: last 3 · daily 7 · weekly 8 · monthly 12<br>Incrementale quando il PC è online</div>
   ${jobbtn('mirror',`act('mirror-backup',null,this,'Forzare ORA il backup del mirror Windows? Immich resta acceso durante la copia e si ferma solo per pochi secondi per lo snapshot finale (si riavvia da solo).')`,'⚡ Forza backup Windows')}</div>
  <div class="card" style="--sec:var(--led-good)"><div class="top"><span class="name">💾 PBS · Immich VM110</span><span class="state up"><span class="led"></span>${(d.pbs['110']||'-').slice(0,16).replace('T',' ')}</span></div>
   <div class="rows">Storage: __PBS__ <br>Retention: ${d.retention||''}</div>
   ${jobbtn('pbs-110',`act('pbs-backup','110',this,'Forzare ORA uno snapshot PBS di VM110?')`,'⚡ Forza backup PBS')}</div>`;
 $('pbscards').innerHTML=Object.entries(d.pbs).sort().map(([id,ts])=>{
  const g=d.guests.find(x=>String(x.vmid)===id);
  return `<div class="card" style="--sec:var(--led-good)"><div class="top"><span class="name">${g?g.name:'VMID '+id}</span><span class="gid">${g?(g.type==='qemu'?'VM ':'LXC '):''}${id}</span></div>
   <div class="rows">Ultimo: ${ts.replace('T',' ').replace('Z','')}</div>
   ${jobbtn('pbs-'+id,`act('pbs-backup','${id}',this,'Forzare ORA uno snapshot PBS di ${g?g.name:id}?')`,'⚡ Forza backup')}</div>`;}).join('');
 /* apps */
 $('acards').innerHTML='';
 for(const a of d.apps){const r=a.overall==='running';
  const c=document.createElement('div');c.className='card';c.style.setProperty('--sec',a.data?'var(--led-warn)':'#a78bfa');
  c.innerHTML=`<div class="top"><span class="name">${a.data?'💾 ':''}${a.name}</span><span class="state ${r?'up':a.overall==='partial'?'wa':'dn'}"><span class="led"></span>${a.overall}</span></div>
   <div class="rows">${Object.entries(a.services).map(([k,v])=>k+': '+v).join('<br>')}</div>`;
  const b=document.createElement('button');b.className='btn '+(r?'stop':'start');b.textContent=r?'⏹ Stop':'▶ Start';
  const warn=a.data&&r?`⚠️ ${a.name} contiene DATI. Verrà fermato in modo pulito. Continuare?`:null;
  b.onclick=()=>act('app',{service:a.name,action:r?'stop':'start'},b,warn);c.appendChild(b);$('acards').appendChild(c);}
 /* whole-VM power */
 $('vmcards').innerHTML='';
 for(const [vmid,name] of Object.entries(d.guest_power||{})){
  const g=d.guests.find(x=>String(x.vmid)===vmid);const r=g&&g.status==='running';
  const c=document.createElement('div');c.className='card';c.style.setProperty('--sec','#60a5fa');
  c.innerHTML=`<div class="top"><span class="name">🖥️ ${name}</span><span class="state ${r?'up':'dn'}"><span class="led"></span>${g?g.status:'?'} · VM${vmid}</span></div>
   <div class="rows">${r?'CPU '+g.cpu.toFixed(1)+'% · RAM '+g.mem_pct.toFixed(1)+'%':'spenta'}</div>`;
  const b=document.createElement('button');b.className='btn '+(r?'stop':'start');b.textContent=r?'⏹ Spegni VM':'▶ Avvia VM';
  const warn=r?`⚠️ Spegnere l'intera VM ${name} (spegnimento pulito). Continuare?`:null;
  b.onclick=()=>act('guest-power',{vmid,action:r?'stop':'start'},b,warn);c.appendChild(b);$('vmcards').appendChild(c);}
 first=false;assistantTips();
}
/* ---------- assistant ---------- */
const asst=$('asst'),bubble=$('bubble'),amsg=$('asstmsg');let tips=[],ti=0;
if(localStorage.getItem('sov-asst')==='off')asst.classList.add('off');
function assistantTips(){
 const d=D;tips=[];
 if(!d.immich.immich_ping)tips.push('<b>Attenzione:</b> Immich non risponde al ping. Controlla la tab Dati.');
 else tips.push('<b>Immich</b> è sano e protetto da PBS, dump giornalieri e mirror Windows. 📷');
 const m=d.immich.mirror||{};
 if(m.configured)tips.push('Il <b>mirror Windows</b> è aggiornato '+ago(m.age_h)+'. Si aggiorna da solo quando il PC si collega.');
 const down=d.kuma.down||0;
 tips.push(down?('<b>'+down+' monitor</b> sono giù ora — apri Uptime Kuma dalla tab Servizi.'):'Tutti i <b>'+d.kuma.active+' monitor</b> sono verdi. ✅');
 const hs=d.storages.find(s=>s.used_pct>=80);if(hs)tips.push('Lo storage <b>'+hs.name+'</b> è al '+hs.used_pct+'%. Valuta una pulizia.');
 tips.push('Puoi <b>forzare un backup</b> dalla tab Dati & Backup: ti arriva una email con l\'esito.');
 tips.push('Vuoi fermare un\'app? Tab <b>Apps</b>. Immich e i servizi critici non sono arrestabili.');
 tips.push('Tema chiaro/scuro con la 🌙 in alto a destra. Tutto si adatta al tuo schermo.');
}
function speak(t){if(localStorage.getItem('sov-voice')!=='on')return;try{const u=new SpeechSynthesisUtterance(t.replace(/<[^>]+>/g,''));u.lang='it-IT';u.rate=1;speechSynthesis.cancel();speechSynthesis.speak(u);}catch(e){}}
function showTip(){if(asst.classList.contains('off')||!tips.length)return;const t=tips[ti%tips.length];ti++;
 amsg.innerHTML=t;bubble.classList.add('show');speak(t);clearTimeout(showTip._t);showTip._t=setTimeout(()=>bubble.classList.remove('show'),9000);}
$('orb').onclick=()=>{if(asst.classList.contains('off')){asst.classList.remove('off');localStorage.removeItem('sov-asst');}showTip();};
$('asstx').onclick=()=>{bubble.classList.remove('show');asst.classList.add('off');localStorage.setItem('sov-asst','off');t('Assistente nascosto — clicca l\'orb per riattivarlo');};
setTimeout(()=>{if(!asst.classList.contains('off'))showTip();},2500);
setInterval(()=>{if(!asst.classList.contains('off')&&Math.random()<.5)showTip();},45000);
async function load(){
 try{D=await(await fetch('api/overview')).json();render();}
 catch(e){$('statustxt').textContent='backend non raggiungibile';}
}
async function act(op,arg,btn,confirmMsg){
 if(confirmMsg&&!confirm(confirmMsg))return;
 const who=prompt('Il tuo nome (per l’audit log):');if(!who)return;
 const reason=prompt('Motivo:');if(reason===null)return;
 btn.disabled=true;const old=btn.textContent;btn.textContent='⏳ In corso…';
 const body={op,actor:who,reason};
 if(op==='app'){body.service=arg.service;body.action=arg.action;}
 if(op==='pbs-backup'){body.vmid=arg;}
 try{const d=await(await fetch('api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  t(d.ok?'✅ Fatto — registrato'+(op!=='app'?' · in esecuzione in background':' · email inviata'):'❌ '+(d.detail||d.error||'errore'));}
 catch(e){t('❌ richiesta fallita');}
 btn.textContent=old;setTimeout(()=>{btn.disabled=false;load();},2200);
}
load();setInterval(load,15000);
</script></body></html>""".replace("__PBS__", PBS_STORAGE)


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
            ok, detail = do_app(str(p.get("service", "")), str(p.get("action", "")), actor, reason)
        elif op == "mirror-backup":
            ok, detail = do_mirror_backup(actor, reason)
        elif op == "pbs-backup":
            ok, detail = do_pbs_backup(str(p.get("vmid", "")), actor, reason)
        elif op == "guest-power":
            ok, detail = do_guest_power(str(p.get("vmid", "")), str(p.get("action", "")), actor, reason)
        audit({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor,
               "op": op, "target": p.get("service") or p.get("vmid") or "", "reason": reason,
               "result": "ok" if ok else "error", "detail": detail if not ok else ""})
        with _lock:
            _cache["ts"] = 0
        self._send(200 if ok else 500, json.dumps({"ok": ok, "detail": detail}).encode("utf-8"), "application/json")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    threading.Thread(target=sampler_loop, daemon=True).start()
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"sovereign-master-dashboard listening on {BIND}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
