#!/usr/bin/env python3
"""Sovereign operational alerts.

Runs on the Proxmox host on a timer. Checks the things web-uptime monitoring
does not see, and emails a single digest through the alert relay ONLY when
something needs attention:

  - PBS / vzdump backup job failures in the recent window;
  - ZFS pool health (degraded) and capacity;
  - TLS certificate expiry (public VPN edge and the internal CA cert);
  - DuckDNS updater failures.

No secrets are printed. Email goes through the LXC 101 relay `/report` endpoint,
so the SMTP secret stays on LXC 101.
"""

from __future__ import annotations

import json
import socket
import ssl
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RELAY_URL = "http://192.168.1.51:8099/report"
RELAY_TOKEN_FILE = "/root/sovereign-secrets/alert-relay-token"
INTERNAL_CA = "/root/sovereign-secrets/ca/sovereign-root-ca.crt"
NPM_IP = "192.168.1.50"
PUBLIC_EDGE = "vpn.casca-certosa.duckdns.org"
CERT_WARN_DAYS = 21
ZFS_WARN_PCT = 80
ZFS_CRIT_PCT = 90
BACKUP_WINDOW_HOURS = 26
DUCKDNS_UNIT = "sovereign-duckdns-update.service"


def run(cmd: list[str], timeout: int = 40) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    return p.returncode, (p.stdout + p.stderr).strip()


def cert_days(host: str, sni: str, cafile: str | None = None, port: int = 443) -> int | None:
    """Days until the cert at host:port (validated) expires, or None if unreadable.

    getpeercert() only returns a parsed dict when the cert is validated, so use
    the system CAs for the public edge and the internal CA for `.internal`.
    """
    try:
        ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni) as s:
                not_after = s.getpeercert()["notAfter"]
        exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return (exp - datetime.now(timezone.utc)).days
    except Exception:
        return None


def check() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    # 1. ZFS health + capacity
    _, zx = run(["zpool", "status", "-x"])
    if zx and "all pools are healthy" not in zx.lower():
        issues.append({"sev": "critical", "what": "ZFS pool not healthy", "detail": zx[:300]})
    _, zl = run(["zpool", "list", "-H", "-o", "name,capacity"])
    for line in zl.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].endswith("%"):
            pct = int(parts[1][:-1])
            if pct >= ZFS_CRIT_PCT:
                issues.append({"sev": "critical", "what": f"ZFS pool {parts[0]} {pct}% full", "detail": "Free space critical."})
            elif pct >= ZFS_WARN_PCT:
                issues.append({"sev": "warning", "what": f"ZFS pool {parts[0]} {pct}% full", "detail": "Plan a cleanup or expansion."})

    # 2. PBS / vzdump job failures in the recent window
    code, out = run(["pvesh", "get", "/nodes/pve/tasks", "--limit", "60", "--output-format", "json"])
    try:
        tasks = json.loads(out) if code == 0 else []
        now = datetime.now(timezone.utc).timestamp()
        for t in tasks:
            if not str(t.get("type", "")).startswith("vzdump"):
                continue
            if now - int(t.get("starttime", 0)) > BACKUP_WINDOW_HOURS * 3600:
                continue
            status = str(t.get("status", ""))
            if status and status != "OK":
                issues.append({"sev": "critical", "what": "Backup job failed",
                               "detail": f"vzdump {t.get('id','')} status: {status[:160]}"})
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # 3. Certificate expiry (public edge + internal CA on dash.internal)
    for label, host, sni, ca in [("public VPN edge", PUBLIC_EDGE, PUBLIC_EDGE, None),
                                 ("internal CA cert", NPM_IP, "dash.internal", INTERNAL_CA)]:
        days = cert_days(host, sni, ca)
        if days is None:
            issues.append({"sev": "warning", "what": f"Cannot read {label} certificate", "detail": f"{host} did not present a readable cert."})
        elif days < 0:
            issues.append({"sev": "critical", "what": f"{label} certificate EXPIRED", "detail": f"Expired {-days} days ago."})
        elif days < CERT_WARN_DAYS:
            issues.append({"sev": "warning", "what": f"{label} certificate expires in {days} days", "detail": "Renew soon."})

    # 4. DuckDNS updater
    code, res = run(["systemctl", "show", "-p", "Result", "--value", DUCKDNS_UNIT])
    if code == 0 and res and res not in {"success", ""}:
        issues.append({"sev": "warning", "what": "DuckDNS updater last run not successful", "detail": f"systemd Result: {res}"})
    code, failed = run(["systemctl", "is-failed", DUCKDNS_UNIT])
    if failed.strip() == "failed":
        issues.append({"sev": "critical", "what": "DuckDNS updater unit is failed", "detail": "Public VPN name may be stale; check the timer and token."})

    return issues


def send(issues: list[dict[str, str]]) -> None:
    token = Path(RELAY_TOKEN_FILE).read_text(encoding="utf-8").strip()
    crit = sum(1 for i in issues if i["sev"] == "critical")
    color = "#dc2626" if crit else "#d97706"
    subject = f"{'🔴' if crit else '🟠'} Sovereign ops alert: {len(issues)} issue(s)"
    lines = [f"[{i['sev'].upper()}] {i['what']} — {i['detail']}" for i in issues]
    text = "Operational checks found issues:\n\n" + "\n".join(lines)
    rows = "".join(
        f'<div style="border-left:4px solid {"#dc2626" if i["sev"]=="critical" else "#d97706"};'
        f'background:#121922;margin:8px 0;padding:10px 12px;border-radius:6px">'
        f'<b>{i["what"]}</b><br><span style="color:#9aa8b8">{i["detail"]}</span></div>' for i in issues)
    html = (f'<div style="font-family:Segoe UI,Arial,sans-serif;background:#06080b;color:#e5e7eb;padding:22px">'
            f'<div style="max-width:600px;margin:auto;background:#0d1218;border:1px solid #1f2937;'
            f'border-left:4px solid {color};border-radius:10px;padding:18px 22px">'
            f'<div style="font-size:18px;font-weight:800;color:{color}">Operational alert</div>{rows}'
            f'<div style="color:#6b7a8d;font-size:12px;margin-top:10px">Sovereign Homelab · ops checks</div></div></div>')
    payload = json.dumps({"subject": subject, "text": text, "html": html}).encode()
    req = urllib.request.Request(RELAY_URL, data=payload, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    urllib.request.urlopen(req, timeout=20).read()


def main() -> int:
    issues = check()
    force = "--test" in sys.argv
    if issues:
        send(issues)
        print(f"sent alert with {len(issues)} issue(s)")
    elif force:
        send([{"sev": "warning", "what": "Test alert", "detail": "Manual --test run; no real issues found."}])
        print("test alert sent; no real issues")
    else:
        print("no issues; no email sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
