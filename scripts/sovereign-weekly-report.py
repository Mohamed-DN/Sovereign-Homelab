#!/usr/bin/env python3
"""Generate and optionally email the Sovereign Homelab weekly operations report.

Run on the Proxmox host as root. Application API calls use the read-only
sole_monitor tokens; root is used only for local host, storage, ZFS, SMART, and
guest inventory commands. Email delivery is delegated to the existing relay on
LXC 101, so the SMTP secret is not copied to the Proxmox host.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import socket
import ssl
import string
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


PVE_ENV = Path("/root/sovereign-secrets/monitoring/pve-api-token.env")
PBS_ENV = Path("/root/sovereign-secrets/monitoring/pbs-api-token.env")
CA_PATH = Path("/root/sovereign-secrets/ca/sovereign-root-ca.crt")
REPORT_DIR = Path("/root/sovereign-secrets/reports")
TEMPLATE_DIR = Path(__file__).resolve().parent / "reporting" / "templates"
if not TEMPLATE_DIR.is_dir():
    TEMPLATE_DIR = Path("/opt/sovereign-reporting/templates")
REQUIRED_BACKUP_IDS = {"100", "101", "102", "103", "110", "120", "130"}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def run(command: list[str], timeout: int = 30) -> tuple[int, str]:
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, output


def api_get(url: str, authorization: str) -> Any:
    context = ssl.create_default_context(cafile=str(CA_PATH))
    request = urllib.request.Request(url, headers={"Authorization": authorization})
    try:
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            return json.load(response).get("data")
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"API request failed for {url}: {exc}") from exc


def kuma_summary() -> dict[str, Any]:
    code = r'''
import json, sqlite3
p='/var/lib/docker/volumes/sovereign-observability_uptime_kuma_data/_data/kuma.db'
c=sqlite3.connect(p)
c.row_factory=sqlite3.Row
active=c.execute('select count(*) n from monitor where active=1').fetchone()['n']
rows=[]
for m in c.execute('select id,name,type,url,hostname,port from monitor where active=1 order by id'):
    last=c.execute('select status,msg,time from heartbeat where monitor_id=? order by id desc limit 1',(m['id'],)).fetchone()
    week=c.execute("select count(*) incidents,coalesce(sum(duration),0) downtime from heartbeat where monitor_id=? and status=0 and important=1 and time>=datetime('now','-7 days')",(m['id'],)).fetchone()
    rows.append({'id':m['id'],'name':m['name'],'status':last['status'] if last else None,'message':last['msg'] if last else 'no heartbeat','last':last['time'] if last else None,'incidents':week['incidents'],'downtime':week['downtime']})
print(json.dumps({'active':active,'monitors':rows}))
c.close()
'''
    status, output = run(["pct", "exec", "101", "--", "python3", "-c", code], timeout=30)
    if status:
        raise RuntimeError(f"Kuma query failed: {output}")
    return json.loads(output)


def certificate_expiry() -> str:
    context = ssl.create_default_context(cafile=str(CA_PATH))
    with socket.create_connection(("192.168.1.50", 443), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname="dash.internal") as tls:
            expiry = tls.getpeercert()["notAfter"]
    value = datetime.strptime(expiry, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    return f"{value.date().isoformat()} ({(value - datetime.now(timezone.utc)).days} days)"


def credential_lifecycle() -> tuple[bool, str]:
    """Check durable access credentials without reading or reporting secrets."""
    checks: list[str] = []
    healthy = True

    status, output = run(["chage", "-l", "root"])
    pve_root_ok = status == 0 and "Password expires" in output and "Password expires" + "\t" * 5 + ": never" in output
    if not pve_root_ok:
        pve_root_ok = status == 0 and bool(re.search(r"Password expires\s*:\s*never", output, re.I))
    checks.append(f"PVE root password expiration: {'never' if pve_root_ok else 'CHECK REQUIRED'}")
    healthy &= pve_root_ok

    pbs_ssh = [
        "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-i", "/root/sovereign-secrets/pbs-bootstrap-ed25519", "root@192.168.1.20",
    ]
    status, output = run(pbs_ssh + ["chage -l root"])
    pbs_root_ok = status == 0 and bool(re.search(r"Password expires\s*:\s*never", output, re.I))
    checks.append(f"PBS root password expiration: {'never' if pbs_root_ok else 'CHECK REQUIRED'}")
    healthy &= pbs_root_ok

    status, output = run(["pveum", "user", "token", "list", "sole_monitor@pve", "--output-format", "json"])
    try:
        pve_tokens = json.loads(output) if status == 0 else []
        pve_token_ok = any(item.get("tokenid") == "homepage" and int(item.get("expire", -1)) == 0 for item in pve_tokens)
    except (json.JSONDecodeError, TypeError, ValueError):
        pve_token_ok = False
    checks.append(f"PVE sole_monitor token expiration: {'none' if pve_token_ok else 'CHECK REQUIRED'}")
    healthy &= pve_token_ok

    status, output = run(pbs_ssh + ["proxmox-backup-manager user list-tokens sole_monitor@pbs --output-format json"])
    try:
        pbs_tokens = json.loads(output) if status == 0 else []
        pbs_token_ok = any(item.get("tokenid") == "sole_monitor@pbs!homepage" and int(item.get("expire", -1)) == 0 for item in pbs_tokens)
    except (json.JSONDecodeError, TypeError, ValueError):
        pbs_token_ok = False
    checks.append(f"PBS sole_monitor token expiration: {'none' if pbs_token_ok else 'CHECK REQUIRED'}")
    healthy &= pbs_token_ok

    status, output = run(["pct", "exec", "100", "--", "docker", "exec", "headscale", "headscale", "nodes", "list", "--output", "json"])
    try:
        start, end = output.find("["), output.rfind("]")
        nodes = json.loads(output[start:end + 1]) if status == 0 and start >= 0 and end >= start else []
        expiring = [node.get("name", str(node.get("id"))) for node in nodes if int(node.get("expiry", {}).get("seconds", 0)) > 0]
        nodes_ok = bool(nodes) and not expiring
        node_state = f"none ({len(nodes)} nodes checked)" if nodes_ok else "CHECK REQUIRED: " + ", ".join(expiring or ["inventory unavailable"])
    except (json.JSONDecodeError, TypeError, ValueError):
        nodes_ok, node_state = False, "CHECK REQUIRED: inventory unavailable"
    checks.append(f"Headscale node expiration: {node_state}")
    healthy &= nodes_ok

    return healthy, "\n".join(checks)


def latest_backups() -> dict[str, str]:
    status, output = run(["pvesm", "list", "pbs-p710", "--content", "backup"], timeout=60)
    if status:
        return {}
    latest: dict[str, tuple[datetime, str]] = {}
    pattern = re.compile(r"backup/(?:ct|vm)/(\d+)/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)")
    for match in pattern.finditer(output):
        vmid, stamp = match.groups()
        value = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if vmid not in latest or value > latest[vmid][0]:
            latest[vmid] = (value, stamp)
    return {key: value[1] for key, value in latest.items()}


def immich_protection() -> dict[str, Any]:
    """Read aggregate backup health from VM110 without exposing personal filenames."""
    guest_script = r'''
import glob
import json
import os
import shutil
import subprocess
import time

root = "/root/sovereign-secrets/immich-protection"
summaries = sorted(glob.glob(root + "/daily/summary-*.json"), key=os.path.getmtime)
dumps = sorted(glob.glob(root + "/daily/immich-db-*.sql.gz"), key=os.path.getmtime)
summary = json.load(open(summaries[-1])) if summaries else {}
disk = shutil.disk_usage("/mnt/immich-library")
timers = ["sovereign-immich-daily.timer", "sovereign-immich-weekly.timer", "sovereign-immich-quarterly.timer"]
timers_ok = all(
    subprocess.run(["systemctl", "is-enabled", "--quiet", timer]).returncode == 0
    and subprocess.run(["systemctl", "is-active", "--quiet", timer]).returncode == 0
    for timer in timers
)
dump_age_hours = round((time.time() - os.path.getmtime(dumps[-1])) / 3600, 1) if dumps else None
restore_marker = os.path.exists(root + "/state/last-database-restore-test")
healthy = bool(summary and dumps and dump_age_hours is not None and dump_age_hours <= 30 and timers_ok and restore_marker)
print(json.dumps({
    "healthy": healthy,
    "dump_age_hours": dump_age_hours,
    "file_count": summary.get("file_count"),
    "total_bytes": summary.get("total_bytes"),
    "data_used_percent": round((disk.used / disk.total) * 100, 1),
    "timers_ok": timers_ok,
    "restore_marker": restore_marker,
}))
'''
    status, output = run(["qm", "guest", "exec", "110", "--", "python3", "-c", guest_script], timeout=90)
    if status:
        return {"healthy": False, "error": output[:300]}
    try:
        wrapper = json.loads(output)
        return json.loads(wrapper.get("out-data", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {"healthy": False, "error": "VM110 protection status could not be parsed"}


def immich_windows_mirror() -> dict[str, Any]:
    """Read the temporary Windows mirror status from VM110 without exposing filenames.

    The mirror is an occasionally online, temporary copy. A missing state file
    means it has not been configured yet, which is a pending enhancement rather
    than a failure, so it must not raise an alert on its own.
    """
    guest_script = r'''
import json
import os
from datetime import datetime, timezone

state = "/root/sovereign-secrets/immich-windows/state/last-mirror.json"
if not os.path.exists(state):
    print(json.dumps({"configured": False}))
else:
    data = json.load(open(state))
    created = data.get("created_utc")
    age_hours = None
    if created:
        try:
            when = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age_hours = round((datetime.now(timezone.utc) - when).total_seconds() / 3600, 1)
        except ValueError:
            age_hours = None
    print(json.dumps({
        "configured": True,
        "age_hours": age_hours,
        "snapshot_id": data.get("snapshot_id"),
        "snapshot_time": data.get("snapshot_time"),
        "check_result": data.get("check_result"),
    }))
'''
    status, output = run(["qm", "guest", "exec", "110", "--", "python3", "-c", guest_script], timeout=60)
    if status:
        return {"configured": False, "error": output[:300]}
    try:
        wrapper = json.loads(output)
        return json.loads(wrapper.get("out-data", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {"configured": False, "error": "VM110 Windows mirror status could not be parsed"}


def disk_usage() -> list[dict[str, Any]]:
    status, output = run(["df", "-P", "-x", "tmpfs", "-x", "devtmpfs"], timeout=20)
    if status:
        return []
    rows = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[4].endswith("%"):
            rows.append({"filesystem": parts[0], "used": int(parts[4][:-1]), "mount": parts[5]})
    return rows


def smart_health() -> list[str]:
    status, output = run(["smartctl", "--scan-open"], timeout=20)
    if status:
        return ["SMART scan unavailable"]
    results = []
    for line in output.splitlines():
        device = line.split()[0] if line.split() else ""
        if not device:
            continue
        _, health = run(["smartctl", "-H", device], timeout=20)
        match = re.search(r"overall-health self-assessment test result:\s*(.+)", health, re.I)
        if not match:
            match = re.search(r"SMART Health Status:\s*(.+)", health, re.I)
        results.append(f"{device}: {match.group(1).strip() if match else 'health result unavailable'}")
    return results or ["No SMART-capable devices found"]


def card(label: str, value: str, color: str) -> str:
    return (
        f'<td style="padding:6px"><div style="background:#1f2937;border:1px solid #374151;'
        f'border-left:4px solid {color};border-radius:6px;padding:14px">'
        f'<div style="color:#9ca3af;font-size:12px">{html.escape(label)}</div>'
        f'<div style="color:#f9fafb;font-size:22px;font-weight:bold;margin-top:5px">{html.escape(value)}</div>'
        "</div></td>"
    )


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f'<th style="text-align:left;padding:8px;border-bottom:1px solid #4b5563">{html.escape(x)}</th>' for x in headers)
    body = "".join(
        "<tr>" + "".join(f'<td style="padding:8px;border-bottom:1px solid #374151">{html.escape(str(cell))}</td>' for cell in row) + "</tr>"
        for row in rows
    )
    return f'<table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:13px"><tr>{head}</tr>{body}</table>'


def build_report() -> dict[str, str]:
    pve = load_env(PVE_ENV)
    pbs = load_env(PBS_ENV)
    pve_auth = f"PVEAPIToken={pve['PVE_API_TOKEN_ID']}={pve['PVE_API_TOKEN_SECRET']}"
    pbs_auth = f"PBSAPIToken={pbs['PBS_API_TOKEN_ID']}:{pbs['PBS_API_TOKEN_SECRET']}"

    resources = api_get("https://proxmox.internal/api2/json/cluster/resources", pve_auth)
    datastore = api_get("https://pbs.internal/api2/json/status/datastore-usage", pbs_auth)
    kuma = kuma_summary()
    backups = latest_backups()
    immich = immich_protection()
    windows_mirror = immich_windows_mirror()
    disks = disk_usage()
    smart = smart_health()
    _, failed_units = run(["systemctl", "--failed", "--no-legend", "--plain"])
    _, zpool = run(["zpool", "status", "-x"])
    _, storage = run(["pvesm", "status"])
    _, headscale = run(["pct", "exec", "100", "--", "docker", "exec", "headscale", "headscale", "nodes", "list-routes"])
    _, relay = run(["pct", "exec", "101", "--", "curl", "-fsS", "http://127.0.0.1:8099/health"])
    lifecycle_ok, lifecycle = credential_lifecycle()

    down = [item for item in kuma["monitors"] if item["status"] != 1]
    weekly_incidents = sum(int(item["incidents"] or 0) for item in kuma["monitors"])
    weekly_downtime = sum(int(item["downtime"] or 0) for item in kuma["monitors"])
    running_guests = sum(1 for item in resources if item.get("type") in {"qemu", "lxc"} and item.get("status") == "running")
    total_guests = sum(1 for item in resources if item.get("type") in {"qemu", "lxc"})

    actions: list[dict[str, str]] = []
    if down:
        actions.append({"severity": "P0", "problem": f"{len(down)} active Kuma monitor(s) are down", "impact": "A monitored service or access path is unavailable.", "action": "Open status.internal, inspect the failing monitor, then follow its service runbook."})
    if failed_units.strip():
        actions.append({"severity": "P1", "problem": "Proxmox has failed systemd units", "impact": failed_units[:300], "action": "Run systemctl --failed and inspect journalctl for each unit."})
    if "all pools are healthy" not in zpool.lower():
        actions.append({"severity": "P0", "problem": "ZFS pool health is not clean", "impact": zpool[:300], "action": "Run zpool status -v immediately and investigate the affected device."})
    for row in disks:
        if row["used"] >= 80:
            actions.append({"severity": "P1", "problem": f"Filesystem {row['mount']} is {row['used']}% full", "impact": "Services or backups may fail when free space is exhausted.", "action": "Identify growth, prune only approved data, and expand storage if needed."})
    missing = sorted(REQUIRED_BACKUP_IDS - set(backups))
    if missing:
        actions.append({"severity": "P0", "problem": "Required PBS snapshots are missing", "impact": "Guests without a current snapshot cannot meet the recovery objective.", "action": "Check the sovereign-core-nightly job and run a controlled backup for VMIDs: " + ", ".join(missing)})
    if relay.strip() != "ok":
        actions.append({"severity": "P1", "problem": "Email relay health check failed", "impact": "Future incidents may not send email.", "action": "Check sovereign-alert-relay.service on LXC 101."})
    if not lifecycle_ok:
        actions.append({"severity": "P1", "problem": "A durable credential has an unexpected expiration state", "impact": lifecycle[:500], "action": "Review root account aging, sole_monitor token expiration, and Headscale node expiration before access is lost."})
    if not immich.get("healthy"):
        actions.append({"severity": "P0", "problem": "Immich app-aware protection is incomplete or stale", "impact": str(immich)[:500], "action": "Check VM110 protection timers, rerun the daily job, and repeat the isolated database restore test before changing photo data."})

    # Temporary Windows Immich mirror. Occasionally online by design, so a stale
    # mirror is a soft warning (P1 at 14 days), never a P0, and a missing mirror
    # is treated as "not configured" without any alert.
    mirror_age = windows_mirror.get("age_hours")
    if not windows_mirror.get("configured"):
        mirror_label, mirror_color, mirror_age_label = "not set", "#6b7280", "-"
    else:
        mirror_age_label = f"{mirror_age / 24:.1f} d" if isinstance(mirror_age, (int, float)) else "unknown"
        mirror_stale = isinstance(mirror_age, (int, float)) and mirror_age > 24 * 7
        mirror_critical = isinstance(mirror_age, (int, float)) and mirror_age > 24 * 14
        mirror_check_failed = windows_mirror.get("check_result") == "failed"
        if mirror_check_failed:
            mirror_label, mirror_color = "CHECK", "#dc2626"
        elif mirror_critical:
            mirror_label, mirror_color = f"STALE {mirror_age_label}", "#dc2626"
        elif mirror_stale:
            mirror_label, mirror_color = f"AGING {mirror_age_label}", "#d97706"
        else:
            mirror_label, mirror_color = "OK", "#059669"
        if mirror_check_failed:
            actions.append({"severity": "P1", "problem": "Windows Immich mirror integrity check failed", "impact": str(windows_mirror)[:400], "action": "Bring the Windows PC online and rerun the mirror check; keep the previous copy until it passes."})
        elif mirror_critical:
            actions.append({"severity": "P1", "problem": "Windows Immich mirror is older than 14 days", "impact": f"Newest mirror snapshot age is {mirror_age_label}. This is a temporary copy; PBS remains the primary backup.", "action": "Bring the Windows PC online so the logon trigger refreshes the mirror, or run the mirror manually."})

    severity = "HEALTHY"
    color = "#059669"
    if any(item["severity"] == "P0" for item in actions):
        severity, color = "CRITICAL", "#dc2626"
    elif actions or weekly_incidents:
        severity, color = "WARNING", "#d97706"

    action_html = "".join(
        f'<div style="border-left:4px solid {"#dc2626" if item["severity"] == "P0" else "#d97706"};background:#1f2937;padding:12px;margin:10px 0;border-radius:5px">'
        f'<strong>{html.escape(item["severity"] + " - " + item["problem"])}</strong><br>'
        f'<span style="color:#d1d5db">Impact: {html.escape(item["impact"])}</span><br>'
        f'<span style="color:#d1fae5">Action: {html.escape(item["action"])}</span></div>'
        for item in actions
    ) or '<div style="border-left:4px solid #059669;background:#1f2937;padding:12px;border-radius:5px">No manual action is required this week.</div>'
    action_text = "\n\n".join(f"{x['severity']} - {x['problem']}\nImpact: {x['impact']}\nAction: {x['action']}" for x in actions) or "No manual action is required this week."

    monitor_rows = [[x["name"], "UP" if x["status"] == 1 else "DOWN", str(x["incidents"]), str(x["downtime"])] for x in kuma["monitors"]]
    backup_rows = [[vmid, backups.get(vmid, "MISSING")] for vmid in sorted(REQUIRED_BACKUP_IDS)]
    guest_rows = [[str(x.get("vmid")), str(x.get("name", "")), str(x.get("type")), str(x.get("status"))] for x in resources if x.get("type") in {"qemu", "lxc"}]
    pbs_rows = [[str(x.get("store", "")), str(x.get("used", "")), str(x.get("total", "")), str(x.get("avail", ""))] for x in datastore]

    context = {
        "status": severity,
        "status_color": color,
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary_cards": "<table width=\"100%\"><tr>" + card("Kuma monitors", str(kuma["active"]), color) + card("Active failures", str(len(down)), "#dc2626" if down else "#059669") + "</tr><tr>" + card("Weekly incidents", str(weekly_incidents), "#d97706" if weekly_incidents else "#059669") + card("Running guests", f"{running_guests}/{total_guests}", "#2563eb") + "</tr><tr>" + card("Immich protection", "OK" if immich.get("healthy") else "CHECK", "#059669" if immich.get("healthy") else "#dc2626") + card("Immich data disk", f"{immich.get('data_used_percent', '?')}% used", "#2563eb") + "</tr><tr>" + card("Windows mirror", mirror_label, mirror_color) + card("Mirror age", mirror_age_label, "#2563eb") + "</tr></table>",
        "actions_html": action_html,
        "actions_text": action_text,
        "monitor_table": table(["Monitor", "Current", "Incidents", "Down seconds"], monitor_rows),
        "backup_table": table(["VMID", "Latest PBS snapshot"], backup_rows),
        "guest_table": table(["VMID", "Name", "Type", "Status"], guest_rows),
        "pbs_table": table(["Datastore", "Used", "Total", "Available"], pbs_rows),
        "storage": html.escape(storage),
        "zpool": html.escape(zpool),
        "smart": html.escape("\n".join(smart)),
        "headscale": html.escape(headscale[:4000]),
        "certificate_expiry": html.escape(certificate_expiry()),
        "credential_lifecycle": html.escape(lifecycle),
        "credential_lifecycle_text": lifecycle,
        "immich_protection": html.escape(json.dumps(immich, indent=2, sort_keys=True)),
        "immich_protection_text": json.dumps(immich, indent=2, sort_keys=True),
        "windows_mirror": html.escape(json.dumps(windows_mirror, indent=2, sort_keys=True)),
        "windows_mirror_text": json.dumps(windows_mirror, indent=2, sort_keys=True),
        "failed_units": html.escape(failed_units or "none"),
        "monitor_text": "\n".join(" | ".join(row) for row in monitor_rows),
        "backup_text": "\n".join(" | ".join(row) for row in backup_rows),
        "guest_text": "\n".join(" | ".join(row) for row in guest_rows),
        "pbs_text": "\n".join(" | ".join(row) for row in pbs_rows),
        "smart_text": "\n".join(smart),
    }
    html_body = string.Template((TEMPLATE_DIR / "weekly_report.html").read_text(encoding="utf-8")).safe_substitute(context)
    text_body = string.Template((TEMPLATE_DIR / "weekly_report.txt").read_text(encoding="utf-8")).safe_substitute(context)
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d")
    return {"subject": f"[{severity}] Sovereign Homelab Weekly Report - {stamp}", "text": text_body, "html": html_body}


def write_payload(payload: dict[str, str]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.chmod(0o700)
    path = REPORT_DIR / f"weekly-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def send_via_lxc101(path: Path) -> None:
    remote = "/root/sovereign-secrets/weekly-report-payload.json"
    status, output = run(["pct", "push", "101", str(path), remote, "--perms", "0600"], timeout=30)
    if status:
        raise RuntimeError(f"could not stage report on LXC 101: {output}")
    status, output = run(["pct", "exec", "101", "--", "/opt/sovereign-alert-relay/sovereign-alert-relay.py", "--send-report", remote], timeout=60)
    if status:
        raise RuntimeError(f"relay could not send weekly report: {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="send through the LXC 101 relay")
    args = parser.parse_args()
    payload = build_report()
    path = write_payload(payload)
    if args.send:
        send_via_lxc101(path)
        print("weekly report sent")
    else:
        print(f"weekly report generated: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
