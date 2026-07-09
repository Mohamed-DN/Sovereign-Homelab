#!/usr/bin/env python3
"""Sovereign safe app-control agent.

A tiny, hardened control surface for starting and stopping ONLY a fixed
allowlist of optional applications on this host. It runs on LXC 102 where the
optional apps live. It is deliberately minimal:

  - Only the services in ALLOWLIST can ever be touched. Anything else is a hard
    400/refused. Critical services (Immich, Vaultwarden, databases, infra) are
    never in the allowlist and cannot be reached through this agent.
  - Only two actions exist: start and stop. There is no generic shell, no
    arbitrary compose, no image pull, no config change.
  - Requests must present the shared bearer token (root-only file).
  - Every action is appended to an audit log with the caller-supplied actor and
    reason (no secrets, no personal filenames).

The Docker socket is NEVER exposed to a browser; only this process talks to
Docker, and only through the fixed allowlist.
"""

from __future__ import annotations

import html as html_lib
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# name -> compose project directory + the exact services to toggle together
ALLOWLIST: dict[str, dict[str, Any]] = {
    "jellyfin": {"dir": "/opt/sovereign-homelab/stacks/jellyfin", "services": ["jellyfin"]},
    "freshrss": {"dir": "/opt/sovereign-homelab/stacks/freshrss", "services": ["freshrss"]},
    "searxng": {"dir": "/opt/sovereign-homelab/stacks/searxng", "services": ["searxng", "searxng-redis"]},
    "karakeep": {"dir": "/opt/sovereign-homelab/stacks/karakeep", "services": ["karakeep", "karakeep-chrome", "karakeep-meilisearch"]},
    "open-webui": {"dir": "/opt/sovereign-homelab/stacks/ai-ollama", "services": ["open-webui"]},
    "ollama": {"dir": "/opt/sovereign-homelab/stacks/ai-ollama", "services": ["ollama"]},
}

BIND = os.environ.get("APP_CONTROL_BIND", "0.0.0.0")
PORT = int(os.environ.get("APP_CONTROL_PORT", "8097"))
TOKEN_FILE = os.environ.get("APP_CONTROL_TOKEN_FILE", "/root/sovereign-secrets/app-control-agent-token")
AUDIT_LOG = Path(os.environ.get("APP_CONTROL_AUDIT_LOG", "/root/sovereign-secrets/app-control-audit.jsonl"))
MAX_BODY = 64 * 1024

# Optional email notification through the existing alert relay (/report endpoint).
RELAY_URL = os.environ.get("APP_CONTROL_RELAY_URL", "")
RELAY_TOKEN_FILE = os.environ.get("APP_CONTROL_RELAY_TOKEN_FILE", "/root/sovereign-secrets/app-control-relay-token")


def load_relay_token() -> str:
    value = os.environ.get("APP_CONTROL_RELAY_TOKEN", "")
    if value:
        return value
    try:
        return Path(RELAY_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


RELAY_TOKEN = load_relay_token()


def load_token() -> str:
    value = os.environ.get("APP_CONTROL_TOKEN", "")
    if value:
        return value
    try:
        return Path(TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


TOKEN = load_token()


def container_status(service: str) -> str:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", service],
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip() if result.returncode == 0 else "absent"


def app_status(name: str) -> dict[str, Any]:
    services = ALLOWLIST[name]["services"]
    states = {svc: container_status(svc) for svc in services}
    running = sum(1 for s in states.values() if s == "running")
    if running == len(services):
        overall = "running"
    elif running == 0:
        overall = "stopped"
    else:
        overall = "partial"
    return {"name": name, "overall": overall, "services": states}


def all_status() -> dict[str, Any]:
    return {"apps": [app_status(name) for name in ALLOWLIST]}


def run_compose(name: str, action: str) -> tuple[bool, str]:
    entry = ALLOWLIST[name]
    cmd = ["docker", "compose", "--project-directory", entry["dir"], action, *entry["services"]]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    ok = result.returncode == 0
    return ok, (result.stderr or result.stdout).strip()[:400]


def notify_email(record: dict[str, Any]) -> None:
    """Best-effort email through the alert relay /report endpoint. Never raises."""
    if not RELAY_URL or not RELAY_TOKEN:
        return
    stopped = record["action"] == "stop"
    glyph = "\U0001F6D1" if stopped else "▶️"
    color = "#d97706" if stopped else "#059669"
    verb = "STOPPED" if stopped else "STARTED"
    svc = record["service"]
    subject = f"{glyph} App {verb}: {svc} by {record['actor']}"
    reason = record.get("reason") or "(no reason given)"
    text = (
        f"Sovereign app control\n\n"
        f"Service: {svc}\nAction: {verb}\nActor: {record['actor']}\n"
        f"Reason: {reason}\nWhen: {record['ts']}\nResult: {record['result']}\n"
    )
    body = (
        f'<div style="font-family:Segoe UI,Arial,sans-serif;background:#06080b;color:#e5e7eb;padding:22px">'
        f'<div style="max-width:560px;margin:auto;background:#0d1218;border:1px solid #1f2937;'
        f'border-left:4px solid {color};border-radius:10px;overflow:hidden">'
        f'<div style="background:{color};padding:18px 22px;color:#fff;font-size:20px;font-weight:800">'
        f'{glyph} {html_lib.escape(svc)} {verb}</div>'
        f'<div style="padding:18px 22px;font-size:14px;line-height:1.7">'
        f'<b>Actor:</b> {html_lib.escape(record["actor"])}<br>'
        f'<b>Reason:</b> {html_lib.escape(reason)}<br>'
        f'<b>When:</b> {record["ts"]}<br>'
        f'<b>Result:</b> {record["result"]}</div>'
        f'<div style="padding:12px 22px;background:#06080b;color:#6b7a8d;font-size:12px;border-top:1px solid #1f2937">'
        f'Sovereign Homelab &middot; app-control agent</div></div></div>'
    )
    payload = json.dumps({"subject": subject, "text": text, "html": body}).encode("utf-8")
    request = urllib.request.Request(
        RELAY_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {RELAY_TOKEN}"},
    )
    try:
        urllib.request.urlopen(request, timeout=15).read()
    except Exception as exc:  # noqa: BLE001 - notification must never break a control action
        print(f"relay notification failed: {exc}")


def audit(entry: dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    try:
        AUDIT_LOG.chmod(0o600)
    except OSError:
        pass


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        return bool(TOKEN) and self.headers.get("Authorization", "") == f"Bearer {TOKEN}"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
            return
        if not self._authed():
            self._send(401, {"error": "unauthorized"})
            return
        if self.path == "/status":
            self._send(200, all_status())
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/control":
            self._send(404, {"error": "not found"})
            return
        if not self._authed():
            self._send(401, {"error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_BODY:
            self._send(413, {"error": "bad body length"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send(400, {"error": "invalid json"})
            return

        service = str(payload.get("service", ""))
        action = str(payload.get("action", ""))
        actor = str(payload.get("actor", "unknown"))[:120]
        reason = str(payload.get("reason", ""))[:300]

        if service not in ALLOWLIST:
            self._send(400, {"error": f"service not in allowlist: {service}"})
            return
        if action not in {"start", "stop"}:
            self._send(400, {"error": "action must be start or stop"})
            return

        ok, message = run_compose(service, action)
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actor": actor,
            "service": service,
            "action": action,
            "reason": reason,
            "result": "ok" if ok else "error",
            "detail": message if not ok else "",
        }
        audit(record)
        notify_email(record)
        self._send(200 if ok else 500, {"ok": ok, "service": service, "action": action, "status": app_status(service), "detail": record["detail"]})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    if not TOKEN:
        raise SystemExit("app-control agent refuses to start without a token")
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"sovereign-app-control-agent listening on {BIND}:{PORT}; allowlist={list(ALLOWLIST)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
