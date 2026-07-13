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
import urllib.parse
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
AUTHENTIK_API = os.environ.get("DASH_AUTHENTIK_API", "http://192.168.1.51:9000/api/v3")
AUTHENTIK_TOKEN_FILE = os.environ.get("DASH_AUTHENTIK_TOKEN_FILE", "/root/sovereign-secrets/dashboard/authentik-iam-token")
# The only proxy allowed to assert an authenticated identity via the
# X-authentik-username header (NPM on LXC 100, which enforces the Authentik
# forward-auth login before anything reaches this port).
TRUSTED_PROXIES = set(os.environ.get("DASH_TRUSTED_PROXIES", "192.168.1.50").split(","))
ADMIN_GROUPS = {"dashboard-admins", "authentik Admins"}
AUDIT_LOG = Path(os.environ.get("DASH_AUDIT_LOG", "/root/sovereign-secrets/master-dashboard-audit.jsonl"))
PBS_STORAGE = os.environ.get("DASH_PBS_STORAGE", "pbs-p710")
PBS_BACKUP_ALLOW = {"100", "101", "102", "103", "110", "120", "130"}
CACHE_TTL = int(os.environ.get("DASH_CACHE_TTL", "15"))
SAMPLE_EVERY = 10          # seconds between host samples
HISTORY = 120              # ring buffer length (120 x 10s = 20 min)
MAX_BODY = 64 * 1024
LONG_SAMPLE_EVERY = 60     # seconds between long-term (persisted) samples
LONG_HISTORY_DAYS = 30
LONG_HISTORY_MAX = LONG_HISTORY_DAYS * 24 * 60
METRICS_LOG = Path(os.environ.get("DASH_METRICS_LOG", "/root/sovereign-secrets/dashboard/metrics-long.jsonl"))

_cache: dict[str, Any] = {"ts": 0, "data": None}
_lock = threading.Lock()
_cpu_hist: deque[float] = deque(maxlen=HISTORY)
_mem_hist: deque[float] = deque(maxlen=HISTORY)
_prev_cpu: tuple[int, int] | None = None

# Long-term (persisted, 1-sample-per-minute, up to 30 days) history so the
# charts survive a dashboard restart and can show real multi-day trends.
_long_ts: deque[float] = deque(maxlen=LONG_HISTORY_MAX)
_long_cpu: deque[float] = deque(maxlen=LONG_HISTORY_MAX)
_long_mem: deque[float] = deque(maxlen=LONG_HISTORY_MAX)
_long_writes = 0


def load_long_history() -> None:
    try:
        lines = METRICS_LOG.read_text(encoding="utf-8").splitlines()[-LONG_HISTORY_MAX:]
    except OSError:
        return
    for line in lines:
        try:
            d = json.loads(line)
            _long_ts.append(d["ts"])
            _long_cpu.append(d["cpu"])
            _long_mem.append(d["mem"])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue


def append_long_sample(cpu: float, mem: float) -> None:
    global _long_writes
    ts = time.time()
    _long_ts.append(ts)
    _long_cpu.append(cpu)
    _long_mem.append(mem)
    try:
        METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)
        _long_writes += 1
        # Rewrite trimmed every ~8h instead of appending forever unbounded.
        if _long_writes % 500 == 0:
            METRICS_LOG.write_text(
                "\n".join(json.dumps({"ts": round(t), "cpu": c, "mem": m})
                          for t, c, m in zip(_long_ts, _long_cpu, _long_mem)) + "\n",
                encoding="utf-8")
        else:
            with METRICS_LOG.open("a", encoding="utf-8") as h:
                h.write(json.dumps({"ts": round(ts), "cpu": cpu, "mem": mem}) + "\n")
        METRICS_LOG.chmod(0o600)
    except OSError:
        pass


def metrics_range(range_key: str) -> dict[str, Any]:
    spans = {"20m": 20 * 60, "2h": 2 * 3600, "2d": 2 * 86400, "7d": 7 * 86400}
    if range_key == "20m":
        return {"points": [{"ts": time.time() - (len(_cpu_hist) - 1 - i) * SAMPLE_EVERY, "cpu": c, "mem": m}
                            for i, (c, m) in enumerate(zip(_cpu_hist, _mem_hist))]}
    cutoff = time.time() - spans.get(range_key, spans["2h"])
    points = [{"ts": t, "cpu": c, "mem": m} for t, c, m in zip(_long_ts, _long_cpu, _long_mem) if t >= cutoff]
    return {"points": points}

# Launchpad links (mirrors the Homepage layout; .internal only, no public names).
# "slug" ties each service to its Authentik Application: grants are memberships
# in the matching `access-<slug>` group, and per-user visibility filters on it.
LINKS: list[dict[str, Any]] = [
    {"group": "Network", "items": [
        {"name": "AdGuard Home", "slug": "adguard", "icon": "\U0001F6E1️", "href": "https://adguard.internal", "desc": "DNS filtering and .internal rewrites", "kw": "adguard"},
        {"name": "Headscale UI", "slug": "headscale", "icon": "\U0001F511", "href": "https://headscale.internal", "desc": "VPN users, devices, routes", "kw": "headscale"},
        {"name": "Nginx Proxy Manager", "slug": "npm", "icon": "\U0001F500", "href": "https://npm.internal", "desc": "Reverse proxy, aliases, certificates", "kw": "proxy"},
    ]},
    {"group": "Admin", "items": [
        {"name": "Proxmox VE", "slug": "proxmox", "icon": "\U0001F5A5️", "href": "https://proxmox.internal", "desc": "VMs, LXCs, storage", "kw": "proxmox ve"},
        {"name": "Proxmox Backup Server", "slug": "pbs", "icon": "\U0001F4BE", "href": "https://pbs.internal", "desc": "Datastore, verify, restore", "kw": "backup server"},
    ]},
    {"group": "Identity", "items": [
        {"name": "Authentik", "slug": "authentik", "icon": "\U0001FAAA", "href": "https://auth.internal", "desc": "SSO, MFA, proxy providers", "kw": "authentik"},
        {"name": "Trust Portal", "slug": "trust-portal", "icon": "\U0001F4DC", "href": "https://trust.internal", "desc": "Install the internal CA", "kw": "trust"},
    ]},
    {"group": "Monitoring", "items": [
        {"name": "Uptime Kuma", "slug": "uptime-kuma", "icon": "\U0001F4C8", "href": "https://status.internal", "desc": "Health checks and alerting", "kw": "kuma"},
        {"name": "Beszel", "slug": "beszel", "icon": "\U0001F4CA", "href": "https://monitor.internal", "desc": "Host and container metrics", "kw": "beszel"},
        {"name": "Dozzle", "slug": "dozzle", "icon": "\U0001F9FE", "href": "https://logs.internal", "desc": "Live Docker logs", "kw": "dozzle"},
        {"name": "Homepage", "slug": "homepage", "icon": "\U0001F3E0", "href": "https://homepage.internal", "desc": "Classic launchpad (rollback)", "kw": "homepage"},
        {"name": "NetAlertX", "slug": "netalertx", "icon": "\U0001F4E1", "href": "https://netalert.internal", "desc": "LAN device inventory", "kw": "netalert"},
        {"name": "Scrutiny", "slug": "scrutiny", "icon": "\U0001F4BD", "href": "https://disks.internal", "desc": "SMART disk health", "kw": "scrutiny"},
        {"name": "ntfy", "slug": "ntfy", "icon": "\U0001F514", "href": "https://alerts.internal", "desc": "Push notifications", "kw": "ntfy"},
    ]},
    {"group": "Critical Data", "items": [
        {"name": "Vaultwarden", "slug": "vaultwarden", "icon": "\U0001F510", "href": "https://pwd.internal", "desc": "Password vault", "kw": "vaultwarden"},
        {"name": "Immich", "slug": "immich", "icon": "\U0001F4F7", "href": "https://foto.internal", "desc": "Photos - protected by PBS + dumps + mirror", "kw": "immich"},
        {"name": "Nextcloud", "slug": "nextcloud", "icon": "☁️", "href": "https://files.internal", "desc": "Personal cloud", "kw": "nextcloud"},
        {"name": "Syncthing", "slug": "syncthing", "icon": "\U0001F501", "href": "https://sync.internal", "desc": "Peer-to-peer sync", "kw": "syncthing"},
        {"name": "Paperless-ngx", "slug": "paperless", "icon": "\U0001F4C4", "href": "https://paper.internal", "desc": "OCR document archive", "kw": "paperless"},
    ]},
    {"group": "Apps", "items": [
        {"name": "Home Assistant", "slug": "home-assistant", "icon": "\U0001F3E1", "href": "https://ha.internal", "desc": "Home automation", "kw": "home assistant"},
        {"name": "Jellyfin", "slug": "jellyfin", "icon": "\U0001F3AC", "href": "https://media.internal", "desc": "Media server", "kw": "jellyfin"},
        {"name": "FreshRSS", "slug": "freshrss", "icon": "\U0001F4F0", "href": "https://rss.internal", "desc": "RSS reader", "kw": "freshrss"},
        {"name": "Karakeep", "slug": "karakeep", "icon": "\U0001F516", "href": "https://bookmarks.internal", "desc": "Bookmarks and archive", "kw": "karakeep"},
        {"name": "SearXNG", "slug": "searxng", "icon": "\U0001F50E", "href": "https://search.internal", "desc": "Private metasearch", "kw": "searxng"},
        {"name": "Forgejo", "slug": "forgejo", "icon": "\U0001F33F", "href": "https://git.internal", "desc": "Git repositories", "kw": "forgejo"},
        {"name": "Open WebUI", "slug": "open-webui", "icon": "\U0001F916", "href": "https://ai.internal", "desc": "Local AI chat", "kw": "webui"},
    ]},
]


def agent_token() -> str:
    try:
        return Path(AGENT_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def authentik_token() -> str:
    try:
        return Path(AUTHENTIK_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def ak_api(path: str, method: str = "GET", body: dict[str, Any] | None = None) -> tuple[bool, Any]:
    """Minimal client for the Authentik REST API using the scoped svc-dashboard-iam
    token (view/add users, view/change groups, view apps, manage policy bindings
    only — never a superuser token). Never exposed to the browser."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{AUTHENTIK_API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {authentik_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            return True, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read())
        except Exception:
            return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, str(e)


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
    ticks_per_long = LONG_SAMPLE_EVERY // SAMPLE_EVERY
    tick = 0
    while True:
        c = _sample_cpu()
        m = _sample_mem()
        if c is not None:
            _cpu_hist.append(c)
        if m is not None:
            _mem_hist.append(m)
        tick += 1
        if tick % ticks_per_long == 0 and c is not None and m is not None:
            append_long_sample(c, m)
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
            "node": r.get("node", ""), "maxcpu": r.get("maxcpu"),
            "mem": r.get("mem"), "maxmem": r.get("maxmem"),
            "disk": r.get("disk"), "maxdisk": r.get("maxdisk"),
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


def scrutiny_disks() -> list[dict[str, Any]]:
    """Read disk temperature + health from Scrutiny (no auth, read-only)."""
    try:
        req = urllib.request.Request("http://192.168.1.53:8085/api/summary")
        with urllib.request.urlopen(req, timeout=12) as r:
            summ = json.load(r).get("data", {}).get("summary", {})
        out = []
        for wwn, d in summ.items():
            dev = d.get("device", {})
            smart = d.get("smart", {})
            out.append({
                "name": dev.get("device_name") or wwn[-8:],
                "model": (dev.get("model_name") or "")[:22],
                "temp": smart.get("temp"),
                "status": "passed" if dev.get("device_status", 0) == 0 else "failed",
            })
        return sorted(out, key=lambda x: str(x["name"]))
    except Exception:
        return []


def app_status() -> list[dict[str, Any]]:
    try:
        req = urllib.request.Request(f"{AGENT_URL}/status", headers={"Authorization": f"Bearer {agent_token()}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("apps", [])
    except Exception:
        return []


def overview(force: bool = False) -> dict[str, Any]:
    # Serve-from-cache-first: a background warmer keeps the cache fresh, so the
    # request path returns instantly (no 10s cold start on first page load).
    with _lock:
        if not force and _cache["data"]:
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
        "disks": scrutiny_disks(),
        "audit": audit_tail(),
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


def overview_for(w: dict[str, Any]) -> dict[str, Any]:
    """Shape the overview payload by role: admins get everything; normal users
    get only their granted services plus an overall up/down summary — no host
    internals, no backup state, no audit, no jobs."""
    data = overview()
    data["me"] = {"username": w["username"], "is_admin": w["is_admin"],
                  "apps": sorted(w["apps"]) if w["apps"] is not None else None,
                  "via": w["via"]}
    if w["is_admin"]:
        return data
    slugs = w["apps"] or set()
    links = []
    for g in data["links"]:
        items = [it for it in g["items"] if it.get("slug") in slugs]
        if items:
            links.append({"group": g["group"], "items": items})
    kws = {it["kw"] for g in links for it in g["items"]}
    mons = [m for m in data["kuma"].get("monitors", [])
            if any(k in m["name"].lower() for k in kws)]
    return {"generated": data["generated"], "me": data["me"], "links": links,
            "kuma": {"active": len(mons), "down": sum(1 for m in mons if not m["up"]),
                     "monitors": mons},
            "sample_every": data["sample_every"],
            "guests": [], "storages": [], "disks": [], "audit": [], "apps": [],
            "guest_power": {}, "pbs": {}, "immich": {"immich_ping": True, "mirror": {}},
            "cpu_hist": [], "mem_hist": [], "jobs": {}, "retention": ""}


# ------------------------------------------------------------ IAM console
# Thin read/write layer over Authentik's own API (the real IAM/LDAP backend).
# svc-dashboard-iam only has: view/add user, view/change group, view app,
# add/view/change policybinding — never superuser, never a password reset on
# an existing account, never delete.

BREAK_GLASS_USERS = {"akadmin", "mohamed", "svc-ldap", "svc-dashboard-iam"}
HIDDEN_USER_PREFIXES = ("ak-outpost-",)

# Cached authorization snapshot from Authentik (users, groups, app bindings).
# Serves both the RBAC checks on every request and the IAM console. On fetch
# failure the last good snapshot is served (Authentik being down also blocks
# NPM's forward-auth, so no new SSO request can arrive without it anyway).
_authz_cache: dict[str, Any] = {"ts": 0.0, "snap": None}
_authz_lock = threading.Lock()


def _authz_fetch() -> dict[str, Any] | None:
    # NOTE: deliberately no /core/applications/ list call — Authentik policy-
    # filters that list per requesting user, so the scoped service account
    # would see nothing once every app is bound to its access group. The app
    # catalog is LINKS (the dashboard owns it) and a grant is simply
    # membership in the matching `access-<slug>` group.
    ok_u, users = ak_api("/core/users/?page_size=200&ordering=username")
    ok_g, groups = ak_api("/core/groups/?page_size=200&ordering=name&include_users=true")
    if not (ok_u and ok_g):
        return None
    ulist, glist = users.get("results", []), groups.get("results", [])
    user_by_pk = {u["pk"]: u["username"] for u in ulist}
    group_members = {g["name"]: {user_by_pk[pk] for pk in (g.get("users") or []) if pk in user_by_pk}
                     for g in glist}
    group_pk_by_name = {g["name"]: g["pk"] for g in glist}
    user_groups = {u["username"]: {g["name"] for g in (u.get("groups_obj") or [])} for u in ulist}
    users_info = {u["username"]: {"pk": u["pk"], "name": u.get("name", ""), "email": u.get("email", ""),
                                   "is_active": u.get("is_active", True), "type": u.get("type", "")}
                  for u in ulist}
    catalog = [{"name": it["name"], "slug": it["slug"], "url": it["href"]}
               for g in LINKS for it in g["items"]]
    return {"users": users_info, "user_groups": user_groups,
            "group_members": group_members, "group_pks": group_pk_by_name,
            "apps": catalog}


def authz_snapshot(force: bool = False) -> dict[str, Any] | None:
    now = time.time()
    with _authz_lock:
        if not force and _authz_cache["snap"] is not None and now - _authz_cache["ts"] < 60:
            return _authz_cache["snap"]
    snap = _authz_fetch()
    with _authz_lock:
        if snap is not None:
            _authz_cache["ts"], _authz_cache["snap"] = now, snap
        return _authz_cache["snap"]


def authz_invalidate() -> None:
    with _authz_lock:
        _authz_cache["ts"] = 0.0


def user_app_slugs(username: str, snap: dict[str, Any]) -> set[str]:
    ug = snap["user_groups"].get(username, set())
    return {g[len("access-"):] for g in ug if g.startswith("access-")}


def who(handler: Any) -> dict[str, Any] | None:
    """Resolve the authenticated identity of a request, or None.

    Identity is only ever accepted from (a) localhost — break-glass admin so
    the host root can always reach the API even with Authentik down — or
    (b) the trusted NPM proxy, which performs the Authentik forward-auth login
    before any request reaches this port and asserts X-authentik-username.
    Roles/grants come from the Authentik snapshot, never from client headers.
    """
    ip = handler.client_address[0]
    if ip in {"127.0.0.1", "::1"}:
        return {"username": "root-console", "is_admin": True, "apps": None, "via": "console"}
    if ip in TRUSTED_PROXIES:
        u = (handler.headers.get("X-authentik-username") or "").strip()[:150]
        if u:
            snap = authz_snapshot()
            if snap is None:
                return {"username": u, "is_admin": False, "apps": set(), "via": "sso"}
            if ADMIN_GROUPS & snap["user_groups"].get(u, set()):
                return {"username": u, "is_admin": True, "apps": None, "via": "sso"}
            return {"username": u, "is_admin": False, "apps": user_app_slugs(u, snap), "via": "sso"}
    return None


def iam_data() -> dict[str, Any]:
    snap = authz_snapshot(force=True)
    if snap is None:
        return {"error": True, "users": [], "groups": [], "apps": []}
    users = []
    for uname in sorted(snap["users"]):
        if uname.startswith(HIDDEN_USER_PREFIXES):
            continue
        info = snap["users"][uname]
        groups = sorted(snap["user_groups"].get(uname, set()))
        users.append({"username": uname, "name": info["name"], "email": info["email"],
                      "is_active": info["is_active"], "groups": groups,
                      "is_admin": bool(ADMIN_GROUPS & set(groups)),
                      "apps": sorted(user_app_slugs(uname, snap)),
                      "protected": uname in BREAK_GLASS_USERS})
    apps = [{"name": a["name"], "slug": a["slug"],
             "users": sorted(snap["group_members"].get(f"access-{a['slug']}", set()))}
            for a in snap["apps"] if a["slug"] != "sovereign-dashboard"]
    return {"users": users, "groups": sorted(snap["group_members"]), "apps": apps}


def iam_self(username: str) -> dict[str, Any]:
    snap = authz_snapshot()
    if snap is None:
        return {"self": True, "error": True, "username": username, "apps": [], "all_apps": []}
    info = snap["users"].get(username, {})
    return {"self": True, "username": username, "name": info.get("name", ""),
            "email": info.get("email", ""),
            "groups": sorted(snap["user_groups"].get(username, set())),
            "apps": sorted(user_app_slugs(username, snap)),
            "all_apps": [{"name": a["name"], "slug": a["slug"]}
                          for a in snap["apps"] if a["slug"] != "sovereign-dashboard"]}


def _find_user_pk(username: str) -> int | None:
    ok, res = ak_api(f"/core/users/?username={urllib.parse.quote(username)}")
    if ok and res.get("results"):
        return res["results"][0]["pk"]
    return None


def do_iam_create_user(username: str, name: str, email: str, password: str,
                        actor: str, reason: str) -> tuple[bool, str]:
    username = re.sub(r"[^a-zA-Z0-9._-]", "", username)[:64]
    if not username or not password or len(password) < 8:
        return False, "username e password (min 8 caratteri) sono obbligatori"
    ok, res = ak_api("/core/users/", "POST", {
        "username": username, "name": name or username, "email": email,
        "is_active": True, "path": "users",
    })
    if not ok:
        return False, str(res.get("username") or res.get("email") or res)
    pk = res["pk"]
    ok2, res2 = ak_api(f"/core/users/{pk}/set_password/", "POST", {"password": password})
    if not ok2:
        return False, f"utenza creata ma password non impostata: {res2}"
    print(f"[iam] utenza '{username}' creata da {actor}: {reason}")
    return True, f"utenza '{username}' creata; stessa password valida su LDAP e ovunque sia collegato"


def do_iam_grant_access(username: str, app_slug: str, actor: str, reason: str) -> tuple[bool, str]:
    ok_u, u = ak_api(f"/core/users/?username={username}")
    if not ok_u or not u.get("results"):
        return False, "utente non trovato"
    user_pk = u["results"][0]["pk"]
    ok_a, a = ak_api(f"/core/applications/{app_slug}/")
    if not ok_a:
        return False, "app non trovata"
    group_name = f"access-{app_slug}"
    ok_g, g = ak_api(f"/core/groups/?name={group_name}")
    if ok_g and g.get("results"):
        group_pk = g["results"][0]["pk"]
    else:
        ok_gc, gc = ak_api("/core/groups/", "POST", {"name": group_name})
        if not ok_gc:
            return False, f"impossibile creare il gruppo di accesso: {gc}"
        group_pk = gc["pk"]
        ok_b, bindings = ak_api("/policies/bindings/?page_size=200")
        already = any(b.get("target") == a["pk"] and b.get("group") == group_pk
                      for b in (bindings.get("results", []) if ok_b else []))
        if not already:
            ak_api("/policies/bindings/", "POST",
                   {"target": a["pk"], "group": group_pk, "enabled": True, "order": 0})
    ok_add, _ = ak_api(f"/core/groups/{group_pk}/add_user/", "POST", {"pk": user_pk})
    if not ok_add:
        return False, "impossibile aggiungere l'utente al gruppo di accesso"
    authz_invalidate()
    print(f"[iam] {actor} ha concesso a '{username}' accesso a '{app_slug}': {reason}")
    return True, f"'{username}' ora ha accesso a '{a.get('name', app_slug)}' (stessa password LDAP)"


def do_iam_revoke_access(username: str, app_slug: str, actor: str) -> tuple[bool, str]:
    if username in BREAK_GLASS_USERS:
        return False, f"'{username}' è protetto: il suo accesso non si revoca da qui"
    snap = authz_snapshot(force=True)
    if snap is None:
        return False, "Authentik non raggiungibile"
    group_name = f"access-{app_slug}"
    group_pk = snap["group_pks"].get(group_name)
    user_pk = snap["users"].get(username, {}).get("pk")
    if group_pk is None or user_pk is None:
        return False, "utente o gruppo di accesso non trovato"
    ok, res = ak_api(f"/core/groups/{group_pk}/remove_user/", "POST", {"pk": user_pk})
    if not ok:
        return False, f"revoca fallita: {res}"
    authz_invalidate()
    return True, f"accesso a '{app_slug}' revocato per '{username}'"


def do_iam_delete_user(username: str, actor: str) -> tuple[bool, str]:
    if username in BREAK_GLASS_USERS or username.startswith(HIDDEN_USER_PREFIXES):
        return False, "account protetto: non eliminabile dalla dashboard"
    pk = _find_user_pk(username)
    if pk is None:
        return False, "utente non trovato"
    ok, res = ak_api(f"/core/users/{pk}/", "DELETE")
    if not ok:
        return False, f"eliminazione fallita: {res}"
    authz_invalidate()
    return True, f"utenza '{username}' eliminata definitivamente"


def do_iam_set_active(username: str, active: bool, actor: str) -> tuple[bool, str]:
    if username in BREAK_GLASS_USERS or username.startswith(HIDDEN_USER_PREFIXES):
        return False, "account protetto: non modificabile dalla dashboard"
    pk = _find_user_pk(username)
    if pk is None:
        return False, "utente non trovato"
    ok, res = ak_api(f"/core/users/{pk}/", "PATCH", {"is_active": bool(active)})
    if not ok:
        return False, f"modifica fallita: {res}"
    authz_invalidate()
    return True, f"utenza '{username}' {'riattivata' if active else 'disattivata'}"


def do_iam_reset_password(username: str, password: str, actor: str) -> tuple[bool, str]:
    if username in BREAK_GLASS_USERS or username.startswith(HIDDEN_USER_PREFIXES):
        return False, "account protetto: reset non permesso da qui"
    if len(password) < 8:
        return False, "password troppo corta (min 8 caratteri)"
    pk = _find_user_pk(username)
    if pk is None:
        return False, "utente non trovato"
    ok, res = ak_api(f"/core/users/{pk}/set_password/", "POST", {"password": password})
    if not ok:
        return False, f"reset fallito: {res}"
    return True, f"password di '{username}' aggiornata (vale subito anche su LDAP)"


def do_iam_set_admin(username: str, admin: bool, actor: str) -> tuple[bool, str]:
    if username in BREAK_GLASS_USERS or username.startswith(HIDDEN_USER_PREFIXES):
        return False, "account protetto: il suo ruolo non si tocca da qui"
    snap = authz_snapshot(force=True)
    if snap is None:
        return False, "Authentik non raggiungibile"
    group_pk = snap["group_pks"].get("dashboard-admins")
    user_pk = snap["users"].get(username, {}).get("pk")
    if group_pk is None or user_pk is None:
        return False, "utente o gruppo dashboard-admins non trovato"
    verb = "add_user" if admin else "remove_user"
    ok, res = ak_api(f"/core/groups/{group_pk}/{verb}/", "POST", {"pk": user_pk})
    if not ok:
        return False, f"modifica ruolo fallita: {res}"
    authz_invalidate()
    return True, f"'{username}' ora {'È' if admin else 'NON è più'} amministratore della dashboard"


def do_iam_change_my_password(username: str, password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "password troppo corta (min 8 caratteri)"
    pk = _find_user_pk(username)
    if pk is None:
        return False, "utente non trovato"
    ok, res = ak_api(f"/core/users/{pk}/set_password/", "POST", {"password": password})
    if not ok:
        return False, f"cambio password fallito: {res}"
    return True, "password aggiornata: vale subito per la dashboard e per tutti i servizi collegati"


def do_iam_request_access(username: str, app_slug: str, message: str) -> tuple[bool, str]:
    app = app_slug.strip()[:60] or "(nessuna app specifica)"
    msg = message.strip()[:800] or "(nessun messaggio)"
    notify_email(f"🔑 Richiesta accesso da {username}",
                  f"Utente: {username}\nApp richiesta: {app}\nMessaggio:\n{msg}\n\n"
                  f"Per concedere: dashboard → IAM → Concedi accesso.", "#7c3aed")
    return True, "richiesta inviata all'amministratore via email"


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


def suppress_monitor(match: str, minutes: int) -> None:
    """Pause/resume a Kuma alert around a deliberate VM stop/start (best-effort)."""
    token = relay_token()
    if not token or not RELAY_URL:
        return
    url = RELAY_URL.rsplit("/", 1)[0] + "/suppress"
    data = json.dumps({"match": match, "minutes": minutes}).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as exc:  # noqa: BLE001
        print(f"suppression call failed: {exc}")


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


def audit_tail(limit: int = 8) -> list[dict[str, Any]]:
    """Last actions from the dashboard + agent audit logs (no secrets)."""
    rows: list[dict[str, Any]] = []
    try:
        for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                e = json.loads(line)
                rows.append({k: e.get(k, "") for k in ("ts", "actor", "op", "target", "reason", "result")})
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return rows[::-1]


def _weekly_report_worker(actor: str) -> None:
    status, out = run(["/usr/local/sbin/sovereign-weekly-report.py", "--send"], timeout=600)
    job_end("weekly-report", status == 0, out.strip().splitlines()[-1][:200] if out.strip() else "")


def do_weekly_report(actor: str) -> tuple[bool, str]:
    if not job_start("weekly-report", "Weekly report"):
        return False, "un report è già in generazione"
    threading.Thread(target=_weekly_report_worker, args=(actor,), daemon=True).start()
    return True, "report in generazione; arriverà via email"


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


# Dedicated, narrowly-scoped SSH key on VM110: the Windows PC's authorized_keys
# forces this key to run ONLY Rebuild-ImmichFromBackup.ps1 (no shell). Separate
# from the SFTP-only mirror key so neither can be used to do the other's job.
REBUILD_SSH_KEY = "/root/sovereign-secrets/immich-windows/rebuild_id_ed25519"
REBUILD_KNOWN_HOSTS = "/root/sovereign-secrets/immich-windows/known_hosts"
REBUILD_LOG = "/root/sovereign-secrets/immich-windows/rebuild-run.log"
REBUILD_HOST = "Mohamed@192.168.1.100"


def _rebuild_windows_worker(actor: str, reason: str) -> None:
    key = "rebuild-windows"
    started = time.time()
    # Step 1: fresh backup first (same wait-for-completion logic as the plain mirror button).
    status, raw = run(["qm", "guest", "exec", "110", "--", "bash", "-lc",
                       "systemctl start --no-block sovereign-immich-windows-restic.service && echo started"], timeout=30)
    if "started" not in guest_out(raw):
        job_end(key, False, "avvio backup fallito: " + guest_out(raw)[:200])
        notify_email("❌ Backup+Rialza Windows: avvio backup fallito",
                      f"Attore: {actor}\nMotivo: {reason}\nDettaglio: {guest_out(raw)[:200]}", "#dc2626")
        return
    deadline = time.time() + 3 * 3600
    state = "activating"
    while time.time() < deadline:
        time.sleep(20)
        s, raw = run(["qm", "guest", "exec", "110", "--", "systemctl", "is-active",
                      "sovereign-immich-windows-restic"], timeout=25)
        state = guest_out(raw).strip() or "unknown"
        if state not in {"activating", "active", "reloading"}:
            break
    if state != "inactive":
        job_end(key, False, f"backup non terminato: {state}")
        notify_email("❌ Backup+Rialza Windows: il backup non è terminato",
                      f"Attore: {actor}\nMotivo: {reason}\nStato: {state}", "#dc2626")
        return
    # Step 2: trigger the rebuild in the background on the Windows PC (forced
    # command on the SSH key ignores whatever we send and runs the real script),
    # then poll VM110 until that SSH session ends, since a rebuild takes minutes.
    run(["qm", "guest", "exec", "110", "--", "bash", "-lc",
         f"rm -f {REBUILD_LOG}; nohup ssh -o StrictHostKeyChecking=yes "
         f"-o UserKnownHostsFile={REBUILD_KNOWN_HOSTS} -o IdentitiesOnly=yes "
         f"-i {REBUILD_SSH_KEY} {REBUILD_HOST} trigger > {REBUILD_LOG} 2>&1 &"], timeout=15)
    deadline = time.time() + 40 * 60
    running = True
    while time.time() < deadline:
        time.sleep(15)
        s, raw = run(["qm", "guest", "exec", "110", "--", "bash", "-lc",
                      "pgrep -f '[r]ebuild_id_ed25519' >/dev/null && echo RUNNING || echo DONE"], timeout=20)
        running = guest_out(raw).strip() != "DONE"
        if not running:
            break
    s, raw = run(["qm", "guest", "exec", "110", "--", "tail", "-n", "6", REBUILD_LOG], timeout=20)
    tail = guest_out(raw).strip()
    dur = _fmt_dur(int(time.time() - started))
    ok = (not running) and ("RIALZATO" in tail or "pong" in tail.lower())
    job_end(key, ok, tail[-200:] if tail else ("timeout" if running else "nessun output"))
    if ok:
        notify_email("✅ Backup + Rialza Immich (Windows) completato",
                      f"Attore: {actor}\nMotivo: {reason}\nDurata: {dur}\n\nBackup fresco eseguito, poi Immich "
                      f"rialzato su questo PC dall'ultimo backup (Podman).\nUltimo output:\n{tail}",
                      "#059669")
    else:
        notify_email("❌ Backup + Rialza Immich (Windows) FALLITO",
                      f"Attore: {actor}\nMotivo: {reason}\nDurata: {dur}\n"
                      f"In esecuzione ancora: {running}\nUltimo output:\n{tail}", "#dc2626")


def do_rebuild_windows(actor: str, reason: str) -> tuple[bool, str]:
    if not job_start("rebuild-windows", "Backup + Rialza Immich (Windows)"):
        return False, "un backup+rialzo è già in corso"
    threading.Thread(target=_rebuild_windows_worker, args=(actor, reason), daemon=True).start()
    return True, "avviato: prima il backup, poi il rialzo da Podman; riceverai una email con l'esito"


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
        suppress_monitor(name, 1440)
        status, out = run(["qm", "shutdown", vmid, "--timeout", "180"], timeout=200)
    else:
        status, out = run(["qm", "start", vmid], timeout=90)
        suppress_monitor(name, 0)
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
.rng{display:flex;gap:5px;margin-bottom:8px}
.rngbtn{padding:3px 9px;border-radius:7px;font-size:.68rem;font-weight:800;cursor:pointer;
 border:1px solid var(--line-strong);background:transparent;color:var(--muted);transition:all .15s ease}
.rngbtn:hover{color:var(--ink);border-color:var(--sec,var(--accent))}
.rngbtn.on{color:#fff;background:var(--sec,var(--accent));border-color:var(--sec,var(--accent))}
.tip{position:absolute;pointer-events:none;background:var(--raised);border:1px solid var(--line-strong);border-radius:7px;padding:5px 9px;font-size:.74rem;font-variant-numeric:tabular-nums;opacity:0;transform:translate(-50%,-100%);white-space:nowrap;box-shadow:var(--shadow);z-index:5;max-width:calc(100% - 12px)}
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

/* ============ v5 LAUNCHER ============ */
:root{--hA:var(--accent);--hB:#a78bfa;--hC:#2dd4a7}
/* App-drawer launcher tiles */
.lgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:12px}
.ltile{position:relative;display:flex;flex-direction:column;align-items:center;gap:9px;padding:18px 8px 13px;
 border:1px solid var(--line);border-radius:16px;background:var(--surface);cursor:pointer;text-decoration:none;color:var(--ink);
 transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}
.ltile:hover{transform:translateY(-4px) scale(1.03);box-shadow:0 14px 30px rgba(0,0,0,.28);
 border-color:transparent;background:linear-gradient(var(--raised),var(--raised)) padding-box,linear-gradient(120deg,var(--hA),var(--hB),var(--hC)) border-box}
.ltile .lic{width:46px;height:46px;border-radius:12px;display:grid;place-items:center;font-size:1.7rem;overflow:hidden;
 background:color-mix(in srgb,var(--accent) 7%,transparent)}
.ltile .lic img{width:38px;height:38px;object-fit:contain}
.ltile .lname{font-size:.76rem;font-weight:700;text-align:center;line-height:1.2;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.ltile .led{position:absolute;top:9px;right:9px}
.ltile .inf{position:absolute;top:6px;left:6px;width:20px;height:20px;border-radius:50%;border:none;cursor:pointer;
 font:700 .7rem system-ui;color:var(--muted);background:color-mix(in srgb,var(--muted) 14%,transparent);opacity:0;transition:opacity .15s ease}
.ltile:hover .inf{opacity:1}
.ltile .inf:hover{color:var(--ink);background:color-mix(in srgb,var(--accent) 25%,transparent)}
.lsec{margin:20px 0 10px;display:flex;align-items:center;gap:10px;color:var(--muted);font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em}
.lsec::after{content:"";flex:1;height:1px;background:var(--line)}
/* ===== bento services (v6) ===== */
#linkgroups{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px;align-items:start}
.bento{position:relative;overflow:hidden;border-radius:22px;padding:18px 18px 16px;border:1px solid var(--line);
 background:linear-gradient(165deg,color-mix(in srgb,var(--bc,#888) 9%,var(--surface)),var(--surface) 55%);box-shadow:var(--shadow)}
.bento::before{content:"";position:absolute;top:-46%;right:-18%;width:65%;height:95%;border-radius:50%;
 background:var(--bc,#888);filter:blur(70px);opacity:.16;pointer-events:none}
.bento h3{display:flex;align-items:center;gap:9px;margin:0 0 13px;font-size:.74rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink2)}
.bento h3 .cnt{margin-left:auto;font-size:.68rem;font-weight:800;padding:3px 10px;border-radius:999px;
 background:color-mix(in srgb,var(--bc,#888) 18%,transparent);color:var(--bc,#888)}
.bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:9px;position:relative}
.bapp{position:relative;display:flex;flex-direction:column;align-items:center;gap:7px;padding:13px 4px 10px;border-radius:15px;
 background:color-mix(in srgb,var(--ink) 4.5%,transparent);border:1px solid transparent;text-decoration:none;color:var(--ink);
 cursor:pointer;transition:transform .15s ease,border-color .15s ease,background .15s ease}
.bapp:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--bc,#888) 65%,transparent);background:color-mix(in srgb,var(--bc,#888) 10%,transparent)}
.bapp .lic{width:40px;height:40px;border-radius:11px;display:grid;place-items:center;font-size:1.45rem;overflow:hidden;background:transparent}
.bapp .lic img{width:34px;height:34px;object-fit:contain}
.bapp .bn{font-size:.67rem;font-weight:700;text-align:center;line-height:1.15;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.bapp .led{position:absolute;top:8px;right:8px;width:7px;height:7px}
.bapp .inf{position:absolute;top:5px;left:5px;width:18px;height:18px;border-radius:50%;border:none;cursor:pointer;
 font:700 .66rem system-ui;color:var(--muted);background:color-mix(in srgb,var(--muted) 14%,transparent);opacity:0;transition:opacity .15s ease}
.bapp:hover .inf{opacity:1}
/* full-width hero banner at the top: pixel-cyberpunk-cute, same language as #quick */
.bento.hero{grid-column:1/-1;border:none;color:var(--ink);cursor:pointer;
 display:grid;grid-template-columns:auto 1fr auto;gap:26px;align-items:center;padding:22px 26px;
 border-radius:0;image-rendering:pixelated;
 clip-path:polygon(14px 0,calc(100% - 14px) 0,100% 14px,100% calc(100% - 14px),calc(100% - 14px) 100%,14px 100%,0 calc(100% - 14px),0 14px);
 background:linear-gradient(165deg,color-mix(in srgb,#22d3ee 8%,var(--surface)),color-mix(in srgb,#ff2fd0 5%,var(--surface))) padding-box,
   linear-gradient(115deg,#ff2fd0,#22d3ee 45%,#a78bfa 100%) border-box;
 border:3px solid transparent}
.bento.hero::before{content:none}
.bento.hero::after{content:"";position:absolute;inset:-8px;z-index:-1;clip-path:inherit;
 background:linear-gradient(115deg,#ff2fd0,#22d3ee 45%,#a78bfa 100%);filter:blur(26px);opacity:.28}
.bento.hero .hleft{min-width:150px}
.bento.hero h3{color:var(--muted);margin:0 0 4px}
.bento.hero .hnum{font-size:3rem;font-weight:800;line-height:1;font-variant-numeric:tabular-nums;
 background:linear-gradient(120deg,#22d3ee,#a78bfa 60%,#ff2fd0);-webkit-background-clip:text;background-clip:text;color:transparent}
.bento.hero .hsub{color:var(--muted);font-size:.8rem;margin-top:2px}
.bento.hero .hbar{height:8px;border-radius:0;background:color-mix(in srgb,var(--ink) 10%,transparent);overflow:hidden;margin:12px 0 0;max-width:260px}
.bento.hero .hbar i{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a78bfa,#ff2fd0);box-shadow:0 0 10px #22d3ee;
 transition:width .9s cubic-bezier(.22,1,.36,1)}
.bento.hero .hstats{text-align:right;font-size:.8rem;color:var(--muted);line-height:1.8;white-space:nowrap}
.bento.hero .hstats b{color:var(--ink);font-size:1.05rem}
/* alert state: something is down -> the whole hero shifts to a red/amber warning glow */
.bento.hero.alert{background:linear-gradient(165deg,color-mix(in srgb,#ef4444 12%,var(--surface)),color-mix(in srgb,#f59e0b 6%,var(--surface))) padding-box,
   linear-gradient(115deg,#ef4444,#fb7185 50%,#f59e0b 100%) border-box}
.bento.hero.alert::after{background:linear-gradient(115deg,#ef4444,#fb7185 50%,#f59e0b 100%)}
.bento.hero.alert .hnum{background:linear-gradient(120deg,#fb7185,#ef4444 60%,#f59e0b);-webkit-background-clip:text;background-clip:text;color:transparent}
.bento.hero.alert .hbar i{background:linear-gradient(90deg,#f59e0b,#ef4444);box-shadow:0 0 10px #ef4444}
/* middle column: merges the status summary with the quick-launch app shelf */
.hmid{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;gap:10px}
.halert{color:#fb7185;font-size:.76rem;font-weight:800;text-align:center;letter-spacing:.02em}
#quick{display:flex;gap:10px;overflow-x:auto;padding:2px;justify-content:center;flex-wrap:wrap;max-width:100%}
#quick .ltile{
 min-width:72px;padding:10px 6px 8px;border:2px solid transparent;border-radius:0;image-rendering:pixelated;
 clip-path:polygon(7px 0,calc(100% - 7px) 0,100% 7px,100% calc(100% - 7px),calc(100% - 7px) 100%,7px 100%,0 calc(100% - 7px),0 7px);
 background:linear-gradient(var(--surface),var(--surface)) padding-box,
   linear-gradient(135deg,#ff2fd0,#22d3ee 50%,#a78bfa 100%) border-box;
 box-shadow:0 0 0 1px rgba(0,0,0,.28),0 8px 18px rgba(0,0,0,.32);
 transition:transform .22s cubic-bezier(.22,1.4,.36,1),box-shadow .22s ease}
#quick .ltile::after{content:"";position:absolute;inset:-3px;z-index:-1;
 clip-path:inherit;background:linear-gradient(135deg,#ff2fd0,#22d3ee 50%,#a78bfa 100%);filter:blur(9px);opacity:.3}
#quick .ltile:nth-child(odd):hover{transform:translateY(-5px) scale(1.08) rotate(-2deg)}
#quick .ltile:nth-child(even):hover{transform:translateY(-5px) scale(1.08) rotate(2deg)}
#quick .ltile:hover{box-shadow:0 0 0 1px rgba(0,0,0,.28),0 0 22px rgba(34,211,238,.6),0 14px 26px rgba(0,0,0,.4)}
#quick .lic{width:30px;height:30px;font-size:1.1rem;border-radius:0;
 clip-path:polygon(5px 0,calc(100% - 5px) 0,100% 5px,100% calc(100% - 5px),calc(100% - 5px) 100%,5px 100%,0 calc(100% - 5px),0 5px)}
#quick .lic img{width:23px;height:23px}
#quick .ltile .led{top:8px;right:8px;border-radius:0;width:7px;height:7px}
#quick .ltile .lname{font-weight:800;letter-spacing:.02em;font-size:.66rem}
@media(max-width:900px){.bento.hero{grid-template-columns:1fr;gap:16px;text-align:center}.bento.hero .hstats{text-align:center}.bento.hero .hbar{margin-inline:auto}}
/* modal */
#mask{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.55);backdrop-filter:blur(3px);display:none}
#mask.show{display:block}
#modal{position:fixed;z-index:81;top:50%;left:50%;transform:translate(-50%,-48%) scale(.97);opacity:0;pointer-events:none;
 width:min(480px,92vw);max-height:80vh;overflow:auto;background:var(--raised);border:1px solid var(--line-strong);border-radius:16px;
 box-shadow:0 30px 70px rgba(0,0,0,.5);transition:all .22s cubic-bezier(.22,1,.36,1)}
#modal.show{opacity:1;transform:translate(-50%,-50%) scale(1);pointer-events:auto}
#modal .mh{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid var(--line)}
#modal .mh .lic{width:44px;height:44px;border-radius:12px;display:grid;place-items:center;font-size:1.6rem;background:color-mix(in srgb,var(--accent) 8%,transparent)}
#modal .mh .lic img{width:34px;height:34px;object-fit:contain}
#modal .mh b{font-size:1.05rem}
#modal .mh .x{margin-left:auto;width:30px;height:30px;border-radius:8px;border:none;cursor:pointer;color:var(--muted);background:transparent;font-size:1.1rem}
#modal .mh .x:hover{background:color-mix(in srgb,var(--muted) 15%,transparent);color:var(--ink)}
#modal .mb{padding:14px 18px 18px;font-size:.86rem;line-height:1.65}
#modal .mb .mrow{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px dashed var(--line)}
#modal .mb .mrow span:first-child{color:var(--muted)}
#modal .mb .btn{margin-top:14px}
/* bento-ize every individual card/tile across all tabs (parity with Servizi) */
#audit{
 border-radius:22px;border:1px solid var(--line);padding:16px;
 background:linear-gradient(165deg,color-mix(in srgb,var(--sec,var(--accent)) 7%,var(--surface)),var(--surface) 60%);
 box-shadow:var(--shadow)}
section.page>h2{border:none;background:transparent;padding:0 4px;min-height:28px;box-shadow:none}
.card,.tile,.donut,.guest,.chart{
 position:relative;overflow:hidden;border-radius:20px;
 background:linear-gradient(165deg,color-mix(in srgb,var(--sec,var(--tc,var(--bc,var(--accent)))) 11%,var(--surface)),var(--surface) 58%)}
.card::after,.tile::after,.donut::after,.guest::after,.chart::after{
 content:"";position:absolute;top:-55%;right:-20%;width:62%;height:100%;border-radius:50%;
 background:var(--sec,var(--tc,var(--bc,var(--accent))));filter:blur(60px);opacity:.16;pointer-events:none;z-index:0}
.card>*,.tile>*,.donut>*,.guest>*,.chart>*{position:relative;z-index:1}
.tile::before{z-index:1}
/* search bar (Servizi + Apps) */
.svcbar{margin:0 0 14px}
.svcbar input{width:100%;max-width:420px;padding:10px 15px;border-radius:12px;border:1px solid var(--line-strong);
 background:var(--surface);color:var(--ink);font-size:.85rem;outline:none;transition:border-color .15s ease}
.svcbar input:focus{border-color:var(--accent)}
.svcbar input::placeholder{color:var(--muted)}
#hero{margin:2px 0 20px}
/* monogram icon fallback (instead of emoji) */
.mono{width:100%;height:100%;display:grid;place-items:center;border-radius:inherit;color:#fff;font-weight:800;font-size:.95rem;letter-spacing:.02em}
/* role gating: normal users see only the hero on Overview (no host internals) */
body.role-user #p-overview>h2,body.role-user #p-overview .tiles,body.role-user #p-overview .charts,
body.role-user #p-overview .donuts,body.role-user #p-overview #disks,body.role-user #p-overview .guests,
body.role-user .bento.hero .hstats{display:none}
/* small icon buttons on IAM rows */
.ibt{width:26px;height:26px;border-radius:7px;border:1px solid var(--line-strong);background:var(--surface);
 color:var(--ink);cursor:pointer;font-size:.8rem;display:inline-grid;place-items:center;transition:all .15s ease}
.ibt:hover{border-color:var(--accent);transform:translateY(-1px)}
.ibt.danger:hover{border-color:var(--led-bad);color:var(--led-bad)}
/* audit list */
#audit{grid-column:1/-1}
#audit .arow{display:flex;gap:10px;align-items:center;padding:8px 6px;border-bottom:1px dashed var(--line);font-size:.8rem}
#audit .arow:last-child{border-bottom:none}
#audit .abadge{padding:3px 9px;border-radius:999px;font-size:.68rem;font-weight:800}
/* footer */
/* ===== v8: symmetry + motion ===== */
.tiles{grid-template-columns:repeat(6,1fr)}
@media(max-width:1500px){.tiles{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){.tiles{grid-template-columns:repeat(2,1fr)}}
.charts{grid-template-columns:1fr 1fr}
@media(max-width:760px){.charts{grid-template-columns:1fr}}
.disks .tile,#disks{}
#disks{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
/* equal-height cards, action pinned to bottom -> symmetric rows */
.grid{align-items:stretch}
.grid>.card{display:flex;flex-direction:column}
.grid>.card>.btn:last-child,.grid>.card .rows+*:last-child{margin-top:auto}
.guests,.donuts{align-items:stretch}
.guest{display:flex;flex-direction:column;justify-content:center}
/* refined hover on everything interactive */
.tile,.donut,.guest,.chart{transition:transform .18s cubic-bezier(.22,1,.36,1),box-shadow .18s ease}
.tile:hover,.donut:hover,.chart:hover{transform:translateY(-3px)}
/* smooth entrance for panels + cards (calm, not flashy) */
@media(prefers-reduced-motion:no-preference){
 section.page.on .bento,section.page.on #tiles,section.page.on .charts,
 section.page.on .donuts,section.page.on #disks,section.page.on .guests,
 section.page.on #dcards,section.page.on #pbscards,section.page.on #acards,
 section.page.on #vmcards,section.page.on #audit,section.page.on #quick{
  animation:rise .45s cubic-bezier(.22,1,.36,1) both}
 @keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
 .bento .bapp,.lgrid .ltile,#quick .ltile{animation:pop .4s cubic-bezier(.22,1,.36,1) both}
 @keyframes pop{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}
}
/* section headers: animated accent underline */
section.page>h2{position:relative}
section.page>h2::after{content:"";position:absolute;left:0;bottom:-3px;height:2px;width:38px;border-radius:2px;
 background:linear-gradient(90deg,var(--sec,var(--accent)),transparent);opacity:.9}
footer{margin:34px 0 14px;text-align:center;color:var(--muted);font-size:.78rem;line-height:1.9}
footer a{color:var(--accent);text-decoration:none;font-weight:700}
footer a:hover{text-decoration:underline}
/* assistant Q&A chips */
#qa{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
#qa button{font:600 .74rem system-ui;padding:6px 10px;border-radius:8px;cursor:pointer;color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent);border:1px solid color-mix(in srgb,var(--accent) 35%,transparent)}
#qa button:hover{background:color-mix(in srgb,var(--accent) 20%,transparent)}
</style></head><body>
<header>
 <div class="brand"><h1>SOVEREIGN DASHBOARD</h1><div class="sub">Proxmox &middot; VPN/LAN only</div></div>
 <div class="hright">
  <span id="clock"></span>
  <span class="pill" id="statuspill"><span class="led nn"></span><span id="statustxt">loading&hellip;</span></span>
  <span class="pill" id="userpill" style="display:none">👤 <b id="username"></b></span>
  <button class="iconbtn" id="logoutbtn" title="Esci" aria-label="Logout" style="display:none">🚪</button>
  <button class="iconbtn" id="themebtn" title="Tema chiaro/scuro" aria-label="Toggle theme">&#127769;</button>
 </div>
</header>
<nav class="tabs" role="tablist">
 <button class="tab on" data-p="overview">Overview</button>
 <button class="tab" data-p="services">Servizi</button>
 <button class="tab" data-p="data">Dati &amp; Backup</button>
 <button class="tab" data-p="apps">Apps</button>
 <button class="tab" data-p="iam">IAM</button>
</nav>
<div class="wrap">
<div id="hero"></div>

<section class="page on" id="p-overview" style="--sec:var(--accent)">
 <h2>Stato del sistema</h2>
 <div class="tiles" id="tiles"></div>
 <div class="charts">
  <div class="chart" id="c-cpu" style="--sec:var(--s1)"><div class="t"><span class="n">CPU host</span><span><span class="now" id="cpu-now">-</span><span class="u">%</span></span></div>
   <div class="rng"><button class="rngbtn on" data-r="20m" onclick="setChartRange('cpu','20m')">20m</button><button class="rngbtn" data-r="2h" onclick="setChartRange('cpu','2h')">2h</button><button class="rngbtn" data-r="2d" onclick="setChartRange('cpu','2d')">2g</button><button class="rngbtn" data-r="7d" onclick="setChartRange('cpu','7d')">7g</button></div>
   <svg class="spark" viewBox="0 0 600 96" preserveAspectRatio="none"></svg><div class="tip"></div></div>
  <div class="chart" id="c-mem" style="--sec:var(--s2)"><div class="t"><span class="n">RAM host</span><span><span class="now" id="mem-now">-</span><span class="u">%</span></span></div>
   <div class="rng"><button class="rngbtn on" data-r="20m" onclick="setChartRange('mem','20m')">20m</button><button class="rngbtn" data-r="2h" onclick="setChartRange('mem','2h')">2h</button><button class="rngbtn" data-r="2d" onclick="setChartRange('mem','2d')">2g</button><button class="rngbtn" data-r="7d" onclick="setChartRange('mem','7d')">7g</button></div>
   <svg class="spark" viewBox="0 0 600 96" preserveAspectRatio="none"></svg><div class="tip"></div></div>
 </div>
 <h2 style="--sec:var(--s1)">Storage</h2>
 <div class="donuts" id="donuts"></div>
 <h2 style="--sec:#fbbf24">Temperatura dischi (SMART)</h2>
 <div class="tiles" id="disks"></div>
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
 <h2 style="--sec:var(--s1)">Operazioni &amp; audit</h2>
 <div class="grid" style="grid-template-columns:1fr">
  <div id="audit"></div>
 </div>
</section>

<section class="page" id="p-apps" style="--sec:#a78bfa">
 <h2 style="--sec:#a78bfa">Apps &mdash; start / stop</h2>
 <p class="note">Ogni azione chiede nome + motivo, va nell'audit log e invia una email. Le app con 💾 contengono dati e vengono fermate in modo pulito. <b>Immich, Vaultwarden, NPM, AdGuard, Headscale, PBS, Authentik</b> non sono mai arrestabili da qui.</p>
 <div class="svcbar"><input id="app-search" type="search" placeholder="🔎 Cerca un'app…" autocomplete="off"></div>
 <div class="grid" id="acards"></div>
 <h2 style="--sec:#60a5fa">Guest interi (VM)</h2>
 <p class="note">Spegnimento/accensione pulito (ACPI) delle VM approvate. Immich (VM110) e l'infrastruttura non sono qui.</p>
 <div class="grid" id="vmcards"></div>
</section>

<section class="page" id="p-iam" style="--sec:#2dd4a7">
 <h2 style="--sec:#2dd4a7">Utenze (LDAP / Authentik) &mdash; una password ovunque</h2>
 <p class="note" id="iam-note">Con LDAP/SSO la stessa password vale su tutti i servizi collegati.</p>
 <div class="grid" style="grid-template-columns:1fr">
  <div class="card" style="--sec:#2dd4a7"><div class="top" id="iam-admin-head"><span class="name">👤 Utenze</span>
    <button class="btn act" style="width:auto;margin:0;padding:8px 14px" onclick="iamCreateUser()">➕ Nuova utenza</button></div>
   <div class="rows" id="iam-users">caricamento…</div></div>
 </div>
 <h2 style="--sec:#a78bfa" id="iam-apps-h">App &amp; accessi</h2>
 <div class="grid" id="iam-apps"></div>
</section>

<footer>
 <b>Sovereign Homelab</b> · gestito da NPM + AdGuard + Headscale · nessun tracciamento<br>
 <a href="https://github.com/Mohamed-DN/Sovereign-Homelab" target="_blank" rel="noopener">📦 Repository GitHub</a>
 &nbsp;·&nbsp; <a href="https://trust.internal" target="_blank" rel="noopener">🔏 Il browser non si fida? Installa la CA (trust.internal)</a>
 &nbsp;·&nbsp; <a href="https://homepage.internal" target="_blank" rel="noopener">🏠 Homepage classica</a>
</footer>
</div>
<div id="mask"></div>
<div id="modal" role="dialog" aria-modal="true">
 <div class="mh"><span class="lic" id="m-ic"></span><b id="m-t"></b><button class="x" id="m-x">&times;</button></div>
 <div class="mb" id="m-b"></div>
</div>
<div id="asst">
 <button id="orb" title="Assistente Sovereign" aria-label="Assistente"><span class="wv"><i></i><i></i><i></i><i></i></span></button>
 <div id="bubble"><span class="x" id="asstx">&times;</span><span id="asstmsg">Ciao! Chiedimi qualcosa 👇</span><div id="qa"></div><span class="hint">Scegli una domanda &middot; la &times; nasconde l'assistente</span></div>
</div>
<div id="toast"></div>
<script>
const $=id=>document.getElementById(id),toast=$('toast');
let D=null,first=true;
/* Curated brand icons (homarr-labs/dashboard-icons via jsdelivr) used only when
   a service's own favicon.ico fails to load. No image-generation tool is
   available in this environment, so this is the closest practical substitute
   for "nice retro icons where they're missing" -- one small cached SVG fetch
   per uncovered service, same pattern many self-hosted dashboards use. */
const ICON_CDN_BASE='https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@main/svg/';
const ICON_CDN_FILES={adguard:'adguard-home',headscale:'headscale',npm:'nginx-proxy-manager',proxmox:'proxmox',
 pbs:'proxmox-backup-server',authentik:'authentik','uptime-kuma':'uptime-kuma',beszel:'beszel',dozzle:'dozzle',
 netalertx:'netalertx',scrutiny:'scrutiny',ntfy:'ntfy',vaultwarden:'vaultwarden',immich:'immich',
 nextcloud:'nextcloud',syncthing:'syncthing',paperless:'paperless-ngx','home-assistant':'home-assistant',
 jellyfin:'jellyfin',freshrss:'freshrss',karakeep:'karakeep',searxng:'searxng',forgejo:'forgejo',
 'open-webui':'open-webui'};
const ICON_CDN=Object.fromEntries(Object.entries(ICON_CDN_FILES).map(([slug,f])=>[slug,ICON_CDN_BASE+f+'.svg']));
/* ---------- theme ---------- */
const root=document.documentElement,tbtn=$('themebtn');
function setTheme(t){root.dataset.theme=t;tbtn.innerHTML=t==='dark'?'&#127769;':'&#9728;&#65039;';localStorage.setItem('sov-theme',t);}
setTheme(localStorage.getItem('sov-theme')||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'));
tbtn.onclick=()=>{setTheme(root.dataset.theme==='dark'?'light':'dark');if(D)render();};
/* ---------- tabs ---------- */
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
 document.querySelectorAll('.page').forEach(p=>p.classList.toggle('on',p.id==='p-'+b.dataset.p));
 if(b.dataset.p==='iam')loadIam();
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
let chartRange={cpu:'20m',mem:'20m'};
async function setChartRange(key,r){
 chartRange[key]=r;
 const card=$(key==='cpu'?'c-cpu':'c-mem');
 card.querySelectorAll('.rngbtn').forEach(b=>b.classList.toggle('on',b.dataset.r===r));
 if(r==='20m'){if(D)render();return;}
 try{
  const j=await(await fetch('api/metrics?range='+r)).json();
  const pts=j.points||[];
  spark(card,pts.map(p=>p[key]),css(key==='cpu'?'--s1':'--s2'),pts.map(p=>p.ts));
  if(!pts.length)t('Nessuno storico ancora per questo intervallo');
 }catch(e){t('Impossibile caricare lo storico');}
}
function fmtWhen(ts){
 const secs=Math.max(0,(Date.now()/1000)-ts);
 const rel=secs<5?'ora':secs<60?Math.round(secs)+'s fa':secs<3600?Math.round(secs/60)+'m fa':
  secs<86400?(secs/3600).toFixed(1)+'h fa':(secs/86400).toFixed(1)+'g fa';
 const dt=new Date(ts*1000);
 const abs=dt.toLocaleDateString('it-IT',{day:'2-digit',month:'2-digit'})+' '+
  dt.toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
 return rel+' · '+abs;
}
function spark(card,data,color,timestamps){
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
  const ts=(timestamps&&timestamps[i]!=null)?timestamps[i]:(Date.now()/1000-(n-1-i)*(D?D.sample_every:10));
  tip.textContent=data[i].toFixed(1)+'%  ·  '+fmtWhen(ts);
  // position relative to the CARD, not the svg (the svg is offset below the
  // header + range buttons), and clamp so it never slides past the edges.
  const cardTop=card.getBoundingClientRect().top;
  const svgOffsetInCard=r.top-cardTop;
  tip.style.left=Math.max(14,Math.min(86,X(i)/W*100))+'%';
  tip.style.top=Math.max(8,svgOffsetInCard+Y(data[i])*(r.height/H)-8)+'px';
  tip.style.opacity=1;};
 svg.onmouseleave=()=>{dot.style.opacity=0;cross.style.opacity=0;tip.style.opacity=0;};
}
/* ---------- donut ---------- */
function donut(name,pct,sub){
 const r=24,c=2*Math.PI*r,off=c*(1-pct/100);
 const col=pct>=90?css('--crit'):pct>=75?css('--warn'):css('--s1');
 return `<div class="donut" style="--sec:${col}"><svg viewBox="0 0 62 62">
  <circle class="ring" cx="31" cy="31" r="${r}"/>
  <circle class="arc" cx="31" cy="31" r="${r}" stroke="${col}" stroke-dasharray="${c}" stroke-dashoffset="${first?c:off}" data-off="${off}"/>
  <text x="31" y="35" text-anchor="middle" font-size="13" font-weight="800" fill="${css('--ink')}">${pct.toFixed(0)}%</text></svg>
  <div><div class="dl">${name}</div><div class="ds">${sub}</div></div></div>`;
}
/* ---------- modal ---------- */
const mask=$('mask'),modal=$('modal');
function openModal(icon,title,body){$('m-ic').innerHTML=icon;$('m-t').textContent=title;$('m-b').innerHTML=body;mask.classList.add('show');modal.classList.add('show');}
function closeModal(){mask.classList.remove('show');modal.classList.remove('show');}
mask.onclick=closeModal;$('m-x').onclick=closeModal;
addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
function mrow(k,v){return `<div class="mrow"><span>${k}</span><span>${v}</span></div>`;}
function svcInfo(name){
 const it=(D.links||[]).flatMap(g=>g.items.map(i=>({...i,group:g.group}))).find(x=>x.name===name);if(!it)return;
 const mon=(D.kuma.monitors||[]).find(m=>m.name.toLowerCase().includes(it.kw));
 const g=D.guests.find(x=>(x.name||'').toLowerCase().includes(it.kw))||null;
 openModal(`<img src="${it.href.replace(/\/$/,'')}/favicon.ico" onerror="this.outerHTML='${it.icon}'">`,it.name,
  `<p style="margin:0 0 10px;color:var(--ink2)">${it.desc}</p>`
  +mrow('Categoria',it.group)+mrow('URL',`<a href="${it.href}" target="_blank" style="color:var(--accent)">${it.href.replace('https://','')}</a>`)
  +mrow('Monitor',mon?(mon.up?'🟢 UP':'🔴 DOWN')+' · '+mon.name:'— non monitorato direttamente')
  +(g?mrow('Guest',(g.type==='qemu'?'VM ':'LXC ')+g.vmid+' · CPU '+g.cpu.toFixed(1)+'% · RAM '+g.mem_pct.toFixed(1)+'%'):'')
  +`<button class="btn act" onclick="window.open('${it.href}','_blank')">Apri ${it.name} ↗</button>`);
}
function heroInfo(){
 const d=D,down=(d.kuma.monitors||[]).filter(x=>!x.up);
 const up=(d.kuma.active||0)-(d.kuma.down||0),tot=d.kuma.active||0;
 openModal('📊','Panoramica del sistema',
  mrow('Servizi online',`${up}/${tot}`)
  +mrow('Guest attivi',`${d.guests.filter(g=>g.status==='running').length}/${d.guests.length}`)
  +mrow('CPU host',(d.cpu_hist.length?d.cpu_hist[d.cpu_hist.length-1].toFixed(0):'–')+'%')
  +mrow('RAM host',(d.mem_hist.length?d.mem_hist[d.mem_hist.length-1].toFixed(0):'–')+'%')
  +mrow('Foto Immich protette',(d.immich.files??'-')+' · '+gb(d.immich.photos_bytes))
  +(down.length?`<div style="margin-top:10px;font-weight:800;font-size:.78rem;color:var(--led-bad)">🔴 Monitor giù (${down.length})</div>`
     +down.map(m=>mrow(m.name,'DOWN')).join('')
   :`<div style="margin-top:10px;color:var(--led-good);font-weight:700">✅ Tutti i monitor sono su</div>`));
}
let IAM=null;
async function iamPost(body,okCb){
 const r=await fetch('api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 let d;try{d=await r.json();}catch(e){location.reload();return;}
 t(d.detail);if(d.ok){closeModal();if(okCb)okCb();}
}
async function loadIam(){
 try{IAM=await(await fetch('api/iam')).json();}catch(e){IAM=null;}
 if(!IAM||IAM.error){$('iam-users').innerHTML='<span style="color:var(--led-bad)">Authentik non raggiungibile</span>';$('iam-apps').innerHTML='';return;}
 if(IAM.self){renderIamSelf();return;}
 $('iam-admin-head').style.display='';
 const ub=u=>{
  if(u.protected)return `<span style="margin-left:auto;color:var(--muted)" title="account di base: non modificabile da qui">🔒</span>`;
  const esc=u.username.replace(/'/g,"\\'");
  return `<span style="margin-left:auto;display:flex;gap:5px">
   <button class="ibt" title="Reset password" onclick="iamResetPw('${esc}')">🔑</button>
   <button class="ibt" title="${u.is_admin?'Togli ruolo admin':'Rendi admin'}" onclick="iamToggleAdmin('${esc}',${!u.is_admin})">${u.is_admin?'👑':'☆'}</button>
   <button class="ibt" title="${u.is_active?'Disattiva':'Riattiva'}" onclick="iamToggleActive('${esc}',${!u.is_active})">${u.is_active?'⏻':'▶'}</button>
   <button class="ibt danger" title="Elimina utenza" onclick="iamDeleteUser('${esc}')">🗑</button></span>`;
 };
 const appsLine=u=>u.is_admin
  ?'<span style="color:var(--led-good);font-weight:700;font-size:.76rem">✦ tutti i servizi (admin)</span>'
  :(u.apps&&u.apps.length
    ?u.apps.map(a=>`<span class="hchip" style="font-size:.68rem;padding:3px 9px">${a}</span>`).join(' ')
    :'<span style="color:var(--muted);font-style:italic;font-size:.78rem">nessun accesso ancora</span>');
 $('iam-users').innerHTML=IAM.users.map(u=>
   `<div class="arow" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;row-gap:8px;
     padding:10px 4px;border-bottom:1px dashed var(--line)">
    <span class="abadge" style="background:color-mix(in srgb,${u.is_active?'var(--led-good)':'var(--led-bad)'} 15%,transparent);color:${u.is_active?'var(--led-good)':'var(--led-bad)'};padding:3px 9px;border-radius:999px;font-size:.68rem;font-weight:800">${u.is_active?'attivo':'disattivo'}</span>
    <b>${u.username}</b>${u.is_admin?'<span title="amministratore">👑</span>':''}
    <span style="color:var(--muted)">${u.name||''}${u.email?' · '+u.email:''}</span>
    ${ub(u)}
    <div style="flex-basis:100%;display:flex;flex-wrap:wrap;gap:6px">${appsLine(u)}</div>
   </div>`
 ).join('')||'<div style="color:var(--muted)">nessuna utenza</div>';
 const protectedUsers=new Set(IAM.users.filter(u=>u.protected).map(u=>u.username));
 $('iam-apps').innerHTML=IAM.apps.map(a=>{
  const esc=a.slug, escName=a.name.replace(/'/g,"\\'");
  const members=(a.users||[]).map(u=>`<span class="hchip" style="font-size:.7rem;padding:3px 8px">${u}${protectedUsers.has(u)?' 🔒':
    ` <button class="ibt" style="width:16px;height:16px;font-size:.6rem" title="Revoca" onclick="iamRevoke('${u.replace(/'/g,"\\'")}','${esc}')">✕</button>`}</span>`).join(' ');
  return `<div class="card" style="--sec:#a78bfa"><div class="top"><span class="name">${a.name}</span></div>
    <div class="rows">Chi ha accesso: ${members||'<i>nessuno</i>'}</div>
    <button class="btn act" onclick="iamGrantAccess('${esc}','${escName}')">+ Concedi accesso</button></div>`;
 }).join('');
}
function renderIamSelf(){
 $('iam-admin-head').style.display='none';
 $('iam-users').innerHTML=
  `<div style="font-size:.9rem;line-height:2">
    <b style="font-size:1.05rem">👤 ${IAM.username}</b> ${IAM.name?'· '+IAM.name:''} ${IAM.email?'· '+IAM.email:''}<br>
    Le tue app: ${(IAM.apps||[]).length?IAM.apps.join(', '):'<i>nessuna ancora — chiedi un accesso qui sotto</i>'}
   </div>
   <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
    <button class="btn act" style="width:auto;padding:9px 16px" onclick="iamMyPassword()">🔑 Cambia la mia password</button>
    <button class="btn act" style="width:auto;padding:9px 16px" onclick="iamAskAccess()">✉️ Chiedi accesso / assistenza</button>
   </div>`;
 $('iam-apps').innerHTML='';
}
function iamCreateUser(){
 openModal('➕','Nuova utenza',
  `<div class="mrow"><label style="width:100%">Username<br><input id="f-username" style="width:100%;margin-top:4px" placeholder="es. giulia"></label></div>
   <div class="mrow"><label style="width:100%">Nome completo<br><input id="f-name" style="width:100%;margin-top:4px"></label></div>
   <div class="mrow"><label style="width:100%">Email<br><input id="f-email" type="email" style="width:100%;margin-top:4px"></label></div>
   <div class="mrow"><label style="width:100%">Password (min 8 caratteri, usata ovunque via LDAP)<br><input id="f-password" type="password" style="width:100%;margin-top:4px"></label></div>
   <button class="btn act" id="iam-go">Crea utenza</button>`);
 $('iam-go').onclick=()=>iamPost({op:'iam-create-user',reason:'creazione da console IAM',
  username:$('f-username').value.trim(),name:$('f-name').value.trim(),email:$('f-email').value.trim(),password:$('f-password').value},loadIam);
}
function iamGrantAccess(slug,appName){
 openModal('🔑','Concedi accesso a '+appName,
  `<div class="mrow"><label style="width:100%">Username esistente<br><input id="f-grantuser" style="width:100%;margin-top:4px" placeholder="es. giulia"></label></div>
   <button class="btn act" id="iam-grant-go">Concedi accesso</button>`);
 $('iam-grant-go').onclick=()=>iamPost({op:'iam-grant-access',reason:'accesso concesso da console IAM',
  username:$('f-grantuser').value.trim(),app_slug:slug},loadIam);
}
function iamRevoke(user,slug){
 openModal('🚫','Revoca accesso',
  `<p>Togliere a <b>${user}</b> l'accesso a <b>${slug}</b>?</p>
   <button class="btn stop" id="iam-rv-go">Revoca</button>`);
 $('iam-rv-go').onclick=()=>iamPost({op:'iam-revoke-access',reason:'revoca da console IAM',username:user,app_slug:slug},loadIam);
}
function iamResetPw(user){
 openModal('🔑','Reset password · '+user,
  `<div class="mrow"><label style="width:100%">Nuova password (min 8 caratteri)<br><input id="f-newpw" type="password" style="width:100%;margin-top:4px"></label></div>
   <button class="btn act" id="iam-pw-go">Imposta password</button>`);
 $('iam-pw-go').onclick=()=>iamPost({op:'iam-reset-password',reason:'reset password da console IAM',username:user,password:$('f-newpw').value},loadIam);
}
function iamToggleAdmin(user,makeAdmin){
 openModal(makeAdmin?'👑':'☆',(makeAdmin?'Rendere amministratore ':'Togliere il ruolo admin a ')+user+'?',
  `<p style="color:var(--muted)">${makeAdmin?'Vedrà e potrà fare TUTTO sulla dashboard.':'Tornerà a vedere solo i propri servizi.'}</p>
   <button class="btn act" id="iam-adm-go">Conferma</button>`);
 $('iam-adm-go').onclick=()=>iamPost({op:'iam-set-admin',reason:'cambio ruolo da console IAM',username:user,admin:makeAdmin},loadIam);
}
function iamToggleActive(user,makeActive){
 openModal(makeActive?'▶':'⏻',(makeActive?'Riattivare ':'Disattivare ')+user+'?',
  `<p style="color:var(--muted)">${makeActive?'Potrà di nuovo accedere ovunque.':'Non potrà più accedere a nessun servizio (reversibile).'}</p>
   <button class="btn ${makeActive?'act':'stop'}" id="iam-act-go">Conferma</button>`);
 $('iam-act-go').onclick=()=>iamPost({op:'iam-set-active',reason:'cambio stato da console IAM',username:user,active:makeActive},loadIam);
}
function iamDeleteUser(user){
 openModal('🗑','Elimina utenza · '+user,
  `<p style="color:var(--led-bad);font-weight:700">Eliminazione DEFINITIVA.</p>
   <p style="color:var(--muted)">Scrivi <b>${user}</b> per confermare:</p>
   <input id="f-delconf" style="width:100%" placeholder="${user}">
   <button class="btn stop" id="iam-del-go">Elimina per sempre</button>`);
 $('iam-del-go').onclick=()=>{
  if($('f-delconf').value.trim()!==user){t('Conferma non corrispondente');return;}
  iamPost({op:'iam-delete-user',reason:'eliminazione da console IAM',username:user},loadIam);
 };
}
function iamMyPassword(){
 openModal('🔑','Cambia la mia password',
  `<div class="mrow"><label style="width:100%">Nuova password (min 8 caratteri, varrà ovunque)<br><input id="f-mypw" type="password" style="width:100%;margin-top:4px"></label></div>
   <div class="mrow"><label style="width:100%">Ripeti password<br><input id="f-mypw2" type="password" style="width:100%;margin-top:4px"></label></div>
   <button class="btn act" id="iam-mypw-go">Cambia password</button>`);
 $('iam-mypw-go').onclick=()=>{
  if($('f-mypw').value!==$('f-mypw2').value){t('Le password non coincidono');return;}
  iamPost({op:'iam-change-my-password',reason:'cambio password personale',password:$('f-mypw').value},loadIam);
 };
}
function iamAskAccess(){
 const opts=(IAM.all_apps||[]).map(a=>`<option value="${a.slug}">${a.name}</option>`).join('');
 openModal('✉️','Chiedi accesso / assistenza',
  `<div class="mrow"><label style="width:100%">App (opzionale)<br><select id="f-reqapp" style="width:100%;margin-top:4px"><option value="">— nessuna app specifica —</option>${opts}</select></label></div>
   <div class="mrow"><label style="width:100%">Messaggio per l'amministratore<br><textarea id="f-reqmsg" style="width:100%;margin-top:4px" rows="3" placeholder="es. mi serve accesso alle foto"></textarea></label></div>
   <button class="btn act" id="iam-req-go">Invia richiesta</button>`);
 $('iam-req-go').onclick=()=>iamPost({op:'iam-request-access',reason:'richiesta via console IAM',
  app_slug:$('f-reqapp').value,message:$('f-reqmsg').value},null);
}
function wireSearch(inputId,itemSel,nameSel){
 const inp=$(inputId);if(!inp)return;
 inp.oninput=()=>{
  const q=inp.value.trim().toLowerCase();
  document.querySelectorAll(itemSel).forEach(el=>{
   const n=(el.querySelector(nameSel)?.textContent||el.dataset.name||'').toLowerCase();
   el.style.display=(!q||n.includes(q))?'':'none';
  });
 };
}
function fmtUptime(s){if(!s)return'spento';const d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60);
 return(d?d+'g ':'')+(h?h+'h ':'')+m+'m';}
function guestInfo(vmid){
 const g=(D.guests||[]).find(x=>x.vmid===vmid);if(!g)return;
 openModal(g.type==='qemu'?'\u{1F5A5}️':'\u{1F4E6}',(g.name||('vmid '+vmid))+' · '+(g.type==='qemu'?'VM':'LXC')+' '+vmid,
  mrow('Stato',g.status==='running'?'🟢 in esecuzione':'🔴 fermo')
  +mrow('Nodo',g.node||'-')
  +mrow('CPU',g.cpu.toFixed(1)+'%'+(g.maxcpu?' · '+g.maxcpu+' vCPU':''))
  +mrow('RAM',g.mem_pct.toFixed(1)+'%'+(g.maxmem?' · '+gb(g.mem)+' / '+gb(g.maxmem):''))
  +(g.maxdisk?mrow('Disco',gb(g.disk)+' / '+gb(g.maxdisk)):'')
  +mrow('Uptime',fmtUptime(g.uptime))
  +`<button class="btn act" onclick="window.open('https://proxmox.internal','_blank')">Apri in Proxmox ↗</button>`);
}
function appInfo(name){
 const a=(D.apps||[]).find(x=>x.name===name);if(!a)return;
 openModal('🧩',a.name,
  `<p style="margin:0 0 10px;color:var(--ink2)">${a.data?'App con DATI: viene fermata in modo pulito e sicuro.':'App opzionale senza dati critici.'}</p>`
  +Object.entries(a.services).map(([k,v])=>mrow(k,v==='running'?'🟢 running':'🔴 '+v)).join('')
  +mrow('Stato complessivo',a.overall)
  +mrow('Audit',"ogni start/stop chiede nome+motivo, va nell'audit log e invia email")
  +mrow('Allarme Kuma','in pausa automatica durante uno stop voluto'));
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
 if(d.cpu_hist.length){$('cpu-now').textContent=d.cpu_hist[d.cpu_hist.length-1].toFixed(0);
  if(chartRange.cpu==='20m')spark($('c-cpu'),d.cpu_hist,css('--s1'));}
 if(d.mem_hist.length){$('mem-now').textContent=d.mem_hist[d.mem_hist.length-1].toFixed(0);
  if(chartRange.mem==='20m')spark($('c-mem'),d.mem_hist,css('--s2'));}
 /* donuts */
 $('donuts').innerHTML=d.storages.map(s=>donut(s.name,s.used_pct,gb(s.used)+' / '+gb(s.total))).join('');
 $('disks').innerHTML=(d.disks||[]).map(x=>`<div class="tile" style="--tc:${x.status==='passed'?'var(--led-good)':'var(--led-bad)'}"><div class="k">${x.name}</div><div class="v">${x.temp?x.temp+'°C':'—'}</div><div class="f">${(x.model||'').slice(0,18)} · ${x.status}</div></div>`).join('')||'<div class="foot" style="color:var(--muted);padding:6px">Scrutiny non raggiungibile</div>';
 requestAnimationFrame(()=>requestAnimationFrame(()=>{document.querySelectorAll('.donut .arc').forEach(a=>a.style.strokeDashoffset=a.dataset.off);}));
 /* guests */
 $('guests').innerHTML=d.guests.map(g=>`<div class="guest ${g.status==='running'?'up':'dn'}" style="--sec:${g.status==='running'?'var(--led-good)':'var(--led-bad)'};cursor:pointer" onclick="guestInfo(${g.vmid})">
  <div class="gt"><span style="display:flex;align-items:center;gap:7px"><span class="led"></span>${g.name||g.vmid}</span><span class="gid">${g.type==='qemu'?'VM':'LXC'} ${g.vmid}</span></div>
  <div class="bar"><i style="width:0" data-w="${Math.min(100,g.cpu)}%"></i></div><div class="bl"><span>CPU</span><span>${g.cpu.toFixed(1)}%</span></div>
  <div class="bar m"><i style="width:0" data-w="${Math.min(100,g.mem_pct)}%"></i></div><div class="bl"><span>RAM</span><span>${g.mem_pct.toFixed(1)}%</span></div></div>`).join('');
 requestAnimationFrame(()=>requestAnimationFrame(()=>{document.querySelectorAll('.guest .bar i').forEach(b=>b.style.width=b.dataset.w);}));
 /* services: app-launcher grid with real favicons + info modals */
 const mons=(d.kuma.monitors||[]).map(x=>({n:x.name.toLowerCase(),up:x.up}));
 function dot(kw){const f=mons.find(x=>x.n.includes(kw));return f?(f.up?'up':'dn'):'nn';}
 function monoOf(n){let h=0;for(const c of n)h=(h*31+c.charCodeAt(0))%360;const ini=n.split(/\s+/).map(w=>w[0]).join('').slice(0,2).toUpperCase();
  return `<span class=&quot;mono&quot; style=&quot;background:linear-gradient(135deg,hsl(${h} 65% 52%),hsl(${(h+40)%360} 65% 42%))&quot;>${ini}</span>`;}
 function favImg(it){
  const cdn=ICON_CDN[it.slug];
  const onerr=cdn?`this.onerror=function(){this.outerHTML='${monoOf(it.name)}'};this.src='${cdn}'`
              :`this.outerHTML='${monoOf(it.name)}'`;
  return `<img src="${it.href.replace(/\/$/,'')}/favicon.ico" loading="lazy" alt="" onerror="${onerr}">`;}
 function ltile(it,small){return `<a class="ltile" href="${it.href}" target="_blank" rel="noopener" data-app="${it.name}">
   <button class="inf" title="Info" onclick="event.preventDefault();event.stopPropagation();svcInfo('${it.name.replace(/'/g,"\\'")}')">i</button>
   <span class="led ${dot(it.kw)}"></span><span class="lic">${favImg(it)}</span><span class="lname">${it.name}</span></a>`;}
 function bapp(it){return `<a class="bapp" href="${it.href}" target="_blank" rel="noopener">
   <button class="inf" title="Info" onclick="event.preventDefault();event.stopPropagation();svcInfo('${it.name.replace(/'/g,"\\'")}')">i</button>
   <span class="led ${dot(it.kw)}"></span><span class="lic">${favImg(it)}</span><span class="bn">${it.name}</span></a>`;}
 const bAcc=['#22d3ee','#60a5fa','#a78bfa','#fbbf24','#2dd4a7','#fb7185'];
 const upN=(d.kuma.active||0)-(d.kuma.down||0),totN=d.kuma.active||0;
 const downMon=(d.kuma.monitors||[]).filter(x=>!x.up).map(x=>x.name);
 const alert=downMon.length>0;
 const cpuNow=d.cpu_hist.length?d.cpu_hist[d.cpu_hist.length-1].toFixed(0):'–';
 const ramNow=d.mem_hist.length?d.mem_hist[d.mem_hist.length-1].toFixed(0):'–';
 const gRun=d.guests.filter(g=>g.status==='running').length;
 /* the hero merges the status summary + the quick-launch shelf into one unit */
 const quickApps=['Immich','Vaultwarden','Nextcloud','Authentik','AdGuard Home','Syncthing','Paperless-ngx',
  'Jellyfin','Home Assistant','Uptime Kuma','Proxmox VE','Proxmox Backup Server'];
 const allItems=d.links.flatMap(g=>g.items);
 const quickHtml=quickApps.map(n=>{const it=allItems.find(x=>x.name===n||x.name.startsWith(n));return it?ltile(it,1):'';}).join('');
 $('hero').innerHTML=
  `<div class="bento hero${alert?' alert':''}" id="herobox" title="Clicca per il dettaglio">
     <div class="hleft"><h3>Panoramica</h3><div class="hnum">${upN}<span style="font-size:1.4rem;opacity:.75">/${totN}</span></div>
       <div class="hsub">servizi online adesso</div><div class="hbar"><i style="width:${totN?Math.round(100*upN/totN):0}%"></i></div></div>
     <div class="hmid">
      ${alert?`<div class="halert">🔴 ${downMon.length} giù: ${downMon.slice(0,3).join(', ')}${downMon.length>3?'…':''}</div>`:''}
      <div id="quick">${quickHtml}</div>
     </div>
     <div class="hstats"><b>${cpuNow}%</b> CPU host<br><b>${ramNow}%</b> RAM host<br><b>${gRun}/${d.guests.length}</b> guest attivi</div>
   </div>`;
 $('herobox').onclick=e=>{if(!e.target.closest('#quick'))heroInfo();};
 $('linkgroups').innerHTML=
  `<div class="svcbar"><input id="svc-search" type="search" placeholder="🔎 Cerca un servizio…" autocomplete="off"></div>`
  +d.links.map((g,i)=>`<div class="bento" style="--bc:${bAcc[i%bAcc.length]}"><h3>${g.group}<span class="cnt">${g.items.length}</span></h3>
    <div class="bgrid">${g.items.map(bapp).join('')}</div></div>`).join('');
 wireSearch('svc-search','#linkgroups .bapp','.bn');
 /* data & backup */
 $('dcards').innerHTML=`
  <div class="card" style="--sec:var(--led-warn)"><div class="top"><span class="name">📷 Immich</span><span class="state ${d.immich.immich_ping?'up':'dn'}"><span class="led"></span>${d.immich.immich_ping?'healthy':'CHECK'}</span></div>
   <div class="rows">File: <b>${d.immich.files??'-'}</b> · ${gb(d.immich.photos_bytes)}<br>Dump protezione: ${ago(d.immich.protection_dump_age_h)}<br><a class="ld" href="https://foto.internal" target="_blank" style="color:var(--accent)">foto.internal ↗</a></div></div>
  <div class="card" style="--sec:var(--accent)"><div class="top"><span class="name">🪞 Mirror Windows</span><span class="state ${m.configured?(m.age_h>168?'wa':'up'):'wa'}"><span class="led"></span>${m.configured?ago(m.age_h):'non configurato'}</span></div>
   <div class="rows">Snapshot: <b>${m.snapshot||'-'}</b> · check: ${m.check||'-'}<br>Retention: last 3 · daily 7 · weekly 8 · monthly 12<br>Incrementale quando il PC è online</div>
   ${jobbtn('mirror',`act('mirror-backup',null,this,'Forzare ORA il backup del mirror Windows? Immich resta acceso durante la copia e si ferma solo per pochi secondi per lo snapshot finale (si riavvia da solo).')`,'⚡ Forza backup Windows')}
   ${jobbtn('rebuild-windows',`act('rebuild-windows',null,this,'Eseguire ORA un backup fresco e poi rialzare Immich sul PC Windows (Podman) con quel nuovo backup? Richiede diversi minuti; funziona anche se è già acceso (viene ricreato da zero).')`,'🚀 Backup + Rialza Immich (emergenza)')}</div>
  <div class="card" style="--sec:var(--led-good)"><div class="top"><span class="name">💾 PBS · Immich VM110</span><span class="state up"><span class="led"></span>${(d.pbs['110']||'-').slice(0,16).replace('T',' ')}</span></div>
   <div class="rows">Storage: __PBS__ <br>Retention: ${d.retention||''}</div>
   ${jobbtn('pbs-110',`act('pbs-backup','110',this,'Forzare ORA uno snapshot PBS di VM110?')`,'⚡ Forza backup PBS')}</div>`;
 /* audit + weekly report */
 const abColor=r=>r==='ok'?'var(--led-good)':'var(--led-bad)';
 $('audit').innerHTML=`<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
   <b style="font-size:.85rem">🧾 Ultime azioni</b>
   <span style="margin-left:auto">${jobbtn('weekly-report',`act('weekly-report',null,this,'Generare e inviare ORA il report settimanale via email?')`,'📧 Invia weekly report ora')}</span></div>`
  +((d.audit||[]).map(a=>`<div class="arow">
    <span class="abadge" style="background:color-mix(in srgb,${abColor(a.result)} 15%,transparent);color:${abColor(a.result)}">${a.result}</span>
    <b>${a.op}${a.target?' · '+a.target:''}</b>
    <span style="color:var(--muted)">${a.actor}</span>
    <span style="color:var(--muted);font-style:italic;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:34ch">${a.reason||''}</span>
    <span style="margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums">${(a.ts||'').replace('T',' ').replace('Z','')}</span></div>`).join('')
   ||'<div style="color:var(--muted);font-size:.8rem;padding:6px">nessuna azione registrata</div>');
 $('pbscards').innerHTML=Object.entries(d.pbs).sort().map(([id,ts])=>{
  const g=d.guests.find(x=>String(x.vmid)===id);
  return `<div class="card" style="--sec:var(--led-good)"><div class="top"><span class="name">${g?g.name:'VMID '+id}</span><span class="gid">${g?(g.type==='qemu'?'VM ':'LXC '):''}${id}</span></div>
   <div class="rows">Ultimo: ${ts.replace('T',' ').replace('Z','')}</div>
   ${jobbtn('pbs-'+id,`act('pbs-backup','${id}',this,'Forzare ORA uno snapshot PBS di ${g?g.name:id}?')`,'⚡ Forza backup')}</div>`;}).join('');
 /* apps */
 $('acards').innerHTML='';
 for(const a of d.apps){const r=a.overall==='running';
  const c=document.createElement('div');c.className='card';c.style.setProperty('--sec',a.data?'var(--led-warn)':'#a78bfa');
  c.innerHTML=`<div class="top"><span class="name">${a.data?'💾 ':''}${a.name}
    <button class="inf" style="position:static;opacity:1;width:20px;height:20px;border-radius:50%;border:none;cursor:pointer;font:700 .7rem system-ui;color:var(--muted);background:color-mix(in srgb,var(--muted) 14%,transparent)" title="Info" onclick="appInfo('${a.name}')">i</button></span>
   <span class="state ${r?'up':a.overall==='partial'?'wa':'dn'}"><span class="led"></span>${a.overall}</span></div>
   <div class="rows">${Object.entries(a.services).map(([k,v])=>k+': '+v).join('<br>')}</div>`;
  const b=document.createElement('button');b.className='btn '+(r?'stop':'start');b.textContent=r?'⏹ Stop':'▶ Start';
  const warn=a.data&&r?`⚠️ ${a.name} contiene DATI. Verrà fermato in modo pulito. Continuare?`:null;
  b.onclick=()=>act('app',{service:a.name,action:r?'stop':'start'},b,warn);c.appendChild(b);$('acards').appendChild(c);}
 wireSearch('app-search','#acards .card','.name');
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
/* ---------- assistant (Q&A, no LLM) ---------- */
const asst=$('asst'),bubble=$('bubble'),amsg=$('asstmsg'),qa=$('qa');
if(localStorage.getItem('sov-asst')==='off')asst.classList.add('off');
let voiceOn=localStorage.getItem('sov-voice')==='on';
function speak(t){if(!voiceOn)return;try{const u=new SpeechSynthesisUtterance(t.replace(/<[^>]+>/g,''));u.lang='it-IT';speechSynthesis.cancel();speechSynthesis.speak(u);}catch(e){}}
function QAset(){
 const d=D;if(!d)return [];
 const m=d.immich.mirror||{},down=d.kuma.down||0;
 const hs=(d.storages||[]).slice().sort((a,b)=>b.used_pct-a.used_pct)[0];
 const ht=(d.disks||[]).slice().sort((a,b)=>(b.temp||0)-(a.temp||0))[0];
 return [
  ['Le mie foto sono al sicuro?', d.immich.immich_ping?('Sì ✅ Immich risponde, protetto da <b>PBS</b> giornaliero, <b>dump</b> app-aware e <b>mirror Windows</b> ('+ago(m.age_h)+'). Restore test superato: 110 GiB.'):'<b>Attenzione:</b> Immich non risponde. Apri la tab Dati.'],
  ['Cosa è giù adesso?', down?('<b>'+down+'</b> monitor giù. Apri Uptime Kuma (tab Servizi) per i dettagli.'):'Tutto verde ✅ ('+d.kuma.active+' monitor OK).'],
  ['Quanto è pieno lo storage?', hs?('Più pieno: <b>'+hs.name+'</b> al <b>'+hs.used_pct+'%</b> ('+gb(hs.used)+'/'+gb(hs.total)+').'+(hs.used_pct>=85?' Valuta pulizia.':'')):'Dati storage non disponibili.'],
  ['I dischi sono caldi?', ht&&ht.temp?('Il più caldo è <b>'+ht.name+'</b> a <b>'+ht.temp+'°C</b> (stato '+ht.status+').'):'Temperature dischi non disponibili (Scrutiny).'],
  ['Il mirror Windows?', m.configured?('Ultimo snapshot <b>'+ago(m.age_h)+'</b> (check '+(m.check||'?')+'). Incrementale quando il PC si collega.'):'Mirror non ancora configurato.'],
  ['Come fermo un servizio?', 'Tab <b>Apps</b> → Stop. Chiede nome+motivo, mette in pausa l\'allarme e invia email. Immich e i critici non sono arrestabili.'],
  ['Come forzo un backup?', 'Tab <b>Dati & Backup</b> → "Forza backup". Ricevi una <b>email con l\'esito</b>; i vecchi backup si cancellano da soli.'],
  ['Se casca il server?', 'Sul PC apri <b>C:\\Sovereign-Restore\\LEGGIMI-EMERGENZA-IMMICH.txt</b>: ricrei Immich dai dati del backup (restore già testato).'],
 ];
}
function assistantTips(){
 if(!qa)return;qa.innerHTML='';
 QAset().forEach(([q,a])=>{const b=document.createElement('button');b.textContent=q;b.onclick=()=>{amsg.innerHTML='<b>'+q+'</b><br>'+a;speak(q+'. '+a);};qa.appendChild(b);});
 const v=document.createElement('button');v.textContent=voiceOn?'🔊 voce':'🔇 voce';
 v.onclick=()=>{voiceOn=!voiceOn;localStorage.setItem('sov-voice',voiceOn?'on':'off');v.textContent=voiceOn?'🔊 voce':'🔇 voce';};qa.appendChild(v);
}
function openAsst(){if(asst.classList.contains('off')){asst.classList.remove('off');localStorage.removeItem('sov-asst');}amsg.innerHTML='Ciao! Chiedimi qualcosa 👇';bubble.classList.add('show');}
$('orb').onclick=openAsst;
$('asstx').onclick=()=>{bubble.classList.remove('show');asst.classList.add('off');localStorage.setItem('sov-asst','off');t('Assistente nascosto — clicca l\'orb');};
setTimeout(()=>{if(!asst.classList.contains('off'))openAsst();},2500);
function applyRole(){
 const me=D&&D.me;if(!me)return;
 const adm=!!me.is_admin;
 document.body.classList.toggle('role-user',!adm);
 document.querySelectorAll('.tab').forEach(b=>{
  const p=b.dataset.p;
  b.style.display=(adm||p==='overview'||p==='services'||p==='iam')?'':'none';
 });
 if(me.via==='sso'){
  $('userpill').style.display='';$('username').textContent=me.username;
  $('logoutbtn').style.display='';
  $('logoutbtn').onclick=()=>{location.href='/outpost.goauthentik.io/sign_out';};
 }
 $('iam-note').textContent=adm
  ?'Crea utenze, assegna/revoca accessi e ruoli: con LDAP/SSO la stessa password vale su tutti i servizi collegati. Gli account di base sono protetti (🔒).'
  :'Qui gestisci il tuo profilo: cambi la password (vale ovunque) o chiedi un accesso all\'amministratore.';
 $('iam-apps-h').style.display=adm?'':'none';
}
async function load(){
 try{
  const r=await fetch('api/overview');
  if(r.redirected||!(r.headers.get('content-type')||'').includes('json')){location.reload();return;}
  if(r.status===401){location.reload();return;}
  D=await r.json();applyRole();render();
 }catch(e){$('statustxt').textContent='backend non raggiungibile';}
}
/* ---------- beautiful action modal (replaces ugly prompt/confirm) ---------- */
function act(op,arg,btn,confirmMsg){
 const danger=/stop|spegn/i.test(btn.textContent)||/Spegnere/.test(confirmMsg||'');
 const title=btn.textContent.replace(/^[⏹▶⚡🛑\s]+/,'').trim()||'Conferma azione';
 const meName=(D&&D.me&&D.me.username)||'';
 openModal(danger?'🛑':'⚡',title,
  `${confirmMsg?`<div style="padding:10px 12px;border-radius:10px;margin-bottom:12px;font-size:.82rem;line-height:1.5;
     background:color-mix(in srgb,${danger?'var(--led-bad)':'var(--led-warn)'} 12%,transparent);
     border:1px solid color-mix(in srgb,${danger?'var(--led-bad)':'var(--led-warn)'} 35%,transparent)">${confirmMsg}</div>`:''}
   <div style="font-size:.78rem;color:var(--muted);margin:2px 0 8px">Firmato come <b style="color:var(--ink)">👤 ${meName}</b></div>
   <label style="display:block;font-size:.72rem;color:var(--muted);margin:12px 0 4px;text-transform:uppercase;letter-spacing:.06em">Motivo</label>
   <textarea id="f-reason" rows="2" placeholder="perché lo stai facendo…" style="width:100%;padding:11px 13px;border-radius:10px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);font-size:.9rem;resize:vertical"></textarea>
   <div style="display:flex;gap:10px;margin-top:16px">
     <button class="btn" style="flex:1" onclick="closeModal()">Annulla</button>
     <button class="btn ${danger?'stop':'act'}" style="flex:2" id="f-go">${danger?'🛑 Conferma':'⚡ Esegui'}</button>
   </div>`);
 setTimeout(()=>$('f-reason').focus(),150);
 $('f-go').onclick=async()=>{
  const reason=$('f-reason').value.trim();
  if(!reason){$('f-reason').style.borderColor='var(--led-bad)';return;}
  closeModal();
  btn.disabled=true;const old=btn.textContent;btn.textContent='⏳ In corso…';
  const body={op,reason};
  if(op==='app'){body.service=arg.service;body.action=arg.action;}
  if(op==='pbs-backup'){body.vmid=arg;}
  if(op==='guest-power'){body.vmid=arg.vmid;body.action=arg.action;}
  try{const d=await(await fetch('api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
   t(d.ok?'✅ Fatto — registrato'+(/backup/.test(op)?' · email all\'esito':' · email inviata'):'❌ '+(d.detail||d.error||'errore'));}
  catch(e){t('❌ richiesta fallita');}
  btn.textContent=old;setTimeout(()=>{btn.disabled=false;load();},2200);
 };
}
load();setInterval(load,15000);
</script></body></html>""".replace("__PBS__", PBS_STORAGE)


LOGIN_REDIRECT_PAGE = (
    "<!doctype html><html lang=it><meta charset=utf-8>"
    "<meta http-equiv=refresh content='3;url=https://dash.internal/'>"
    "<title>Sovereign Dashboard</title>"
    "<body style='font-family:system-ui;background:#06080b;color:#e5e7eb;display:grid;"
    "place-items:center;height:100vh;margin:0'><div style='text-align:center'>"
    "<div style='font-size:2.4rem'>🔐</div><h2>Accesso richiesto</h2>"
    "<p>Entra dalla porta principale:<br>"
    "<a href='https://dash.internal' style='color:#22d3ee;font-weight:700'>https://dash.internal</a></p>"
    "</div></body></html>"
)

# Ops a non-admin user may invoke; everything else requires the admin role.
SELF_OPS = {"iam-change-my-password", "iam-request-access"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
            return
        w = who(self)
        if self.path in {"/", "/index.html"}:
            if w is None:
                self._send(200, LOGIN_REDIRECT_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            else:
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if w is None:
            self._send(401, b'{"error":"non autenticato"}', "application/json")
            return
        if self.path == "/api/overview":
            try:
                self._send(200, json.dumps(overview_for(w)).encode("utf-8"), "application/json")
            except Exception as exc:  # noqa: BLE001
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
        elif self.path == "/api/iam":
            try:
                payload = iam_data() if w["is_admin"] else iam_self(w["username"])
                self._send(200, json.dumps(payload).encode("utf-8"), "application/json")
            except Exception as exc:  # noqa: BLE001
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
        elif self.path.startswith("/api/metrics"):
            if not w["is_admin"]:
                self._send(403, b'{"error":"solo amministratori"}', "application/json")
                return
            qs = urllib.parse.urlparse(self.path).query
            range_key = urllib.parse.parse_qs(qs).get("range", ["20m"])[0]
            if range_key not in {"20m", "2h", "2d", "7d"}:
                range_key = "20m"
            try:
                self._send(200, json.dumps(metrics_range(range_key)).encode("utf-8"), "application/json")
            except Exception as exc:  # noqa: BLE001
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
        else:
            self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self) -> None:
        if self.path != "/api/action":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        w = who(self)
        if w is None:
            self._send(401, b'{"error":"non autenticato"}', "application/json")
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
        # The actor is ALWAYS the authenticated identity; whatever the client
        # sends is ignored so the audit log cannot be spoofed.
        actor = w["username"]
        reason = str(p.get("reason", ""))[:300]
        if op not in SELF_OPS and not w["is_admin"]:
            audit({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor,
                   "op": op, "target": p.get("service") or p.get("vmid") or p.get("username") or "",
                   "reason": reason, "result": "denied", "detail": "ruolo insufficiente"})
            self._send(403, json.dumps({"ok": False, "detail": "non autorizzato: serve il ruolo admin"}).encode("utf-8"),
                       "application/json")
            return
        ok, detail = False, "unknown op"
        if op == "app":
            ok, detail = do_app(str(p.get("service", "")), str(p.get("action", "")), actor, reason)
        elif op == "mirror-backup":
            ok, detail = do_mirror_backup(actor, reason)
        elif op == "rebuild-windows":
            ok, detail = do_rebuild_windows(actor, reason)
        elif op == "pbs-backup":
            ok, detail = do_pbs_backup(str(p.get("vmid", "")), actor, reason)
        elif op == "guest-power":
            ok, detail = do_guest_power(str(p.get("vmid", "")), str(p.get("action", "")), actor, reason)
        elif op == "weekly-report":
            ok, detail = do_weekly_report(actor)
        elif op == "iam-create-user":
            ok, detail = do_iam_create_user(str(p.get("username", "")), str(p.get("name", "")),
                                             str(p.get("email", "")), str(p.get("password", "")), actor, reason)
        elif op == "iam-grant-access":
            ok, detail = do_iam_grant_access(str(p.get("username", "")), str(p.get("app_slug", "")), actor, reason)
        elif op == "iam-revoke-access":
            ok, detail = do_iam_revoke_access(str(p.get("username", "")), str(p.get("app_slug", "")), actor)
        elif op == "iam-delete-user":
            ok, detail = do_iam_delete_user(str(p.get("username", "")), actor)
        elif op == "iam-set-active":
            ok, detail = do_iam_set_active(str(p.get("username", "")), bool(p.get("active")), actor)
        elif op == "iam-reset-password":
            ok, detail = do_iam_reset_password(str(p.get("username", "")), str(p.get("password", "")), actor)
        elif op == "iam-set-admin":
            ok, detail = do_iam_set_admin(str(p.get("username", "")), bool(p.get("admin")), actor)
        elif op == "iam-change-my-password":
            ok, detail = do_iam_change_my_password(actor, str(p.get("password", "")))
        elif op == "iam-request-access":
            ok, detail = do_iam_request_access(actor, str(p.get("app_slug", "")), str(p.get("message", "")))
        audit({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor,
               "op": op, "target": p.get("service") or p.get("vmid") or p.get("username") or p.get("app_slug") or "",
               "reason": reason, "result": "ok" if ok else "error", "detail": detail if not ok else ""})
        with _lock:
            _cache["ts"] = 0
        self._send(200 if ok else 500, json.dumps({"ok": ok, "detail": detail}).encode("utf-8"), "application/json")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def cache_warmer() -> None:
    """Refresh the overview cache continuously so requests are always instant."""
    while True:
        try:
            overview(force=True)
        except Exception as exc:  # noqa: BLE001
            print(f"cache warm failed: {exc}")
        time.sleep(CACHE_TTL)


def main() -> None:
    load_long_history()
    threading.Thread(target=sampler_loop, daemon=True).start()
    threading.Thread(target=cache_warmer, daemon=True).start()
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"sovereign-master-dashboard listening on {BIND}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
