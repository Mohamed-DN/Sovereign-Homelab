#!/usr/bin/env python3
"""Authenticated Uptime Kuma webhook relay with HTML email and anti-spam state.

The relay uses only the Python standard library. It sends the first DOWN alert
after one minute, one reminder after five minutes, and one recovery message.
SMTP credentials and the webhook token are loaded from environment variables or
root-only files; they must never be committed to the repository.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import smtplib
import ssl
import string
import sys
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def load_env_file() -> None:
    path = Path(os.environ.get("ALERT_ENV_FILE", "/root/sovereign-secrets/alert-relay.env"))
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


load_env_file()

STATE_PATH = Path(os.environ.get("ALERT_STATE_PATH", "/var/lib/sovereign-alert-relay/state.json"))
default_template_dir = Path(__file__).resolve().parent / "alerting" / "templates"
if not default_template_dir.is_dir():
    default_template_dir = Path(__file__).resolve().parent / "templates"
TEMPLATE_DIR = Path(os.environ.get("ALERT_TEMPLATE_DIR", str(default_template_dir)))
BIND = os.environ.get("ALERT_RELAY_BIND", "127.0.0.1")
PORT = int(os.environ.get("ALERT_RELAY_PORT", "8099"))
FIRST_DELAY = int(os.environ.get("ALERT_FIRST_DELAY_SECONDS", "60"))
REMINDER_DELAY = int(os.environ.get("ALERT_REMINDER_DELAY_SECONDS", "300"))
CHECK_INTERVAL = int(os.environ.get("ALERT_CHECK_INTERVAL_SECONDS", "10"))
ATTEMPT_THROTTLE = int(os.environ.get("ALERT_ATTEMPT_THROTTLE_SECONDS", "60"))
MAX_PAYLOAD_BYTES = int(os.environ.get("ALERT_MAX_PAYLOAD_BYTES", "1048576"))
DRY_RUN = os.environ.get("ALERT_DRY_RUN", "false").lower() in {"1", "true", "yes"}


def read_secret(value_name: str, file_name: str) -> str:
    value = os.environ.get(value_name, "")
    if value:
        return value
    file_path = os.environ.get(file_name, "")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    return ""


RELAY_TOKEN = read_secret("ALERT_RELAY_TOKEN", "ALERT_RELAY_TOKEN_FILE")
SMTP_HOST = os.environ.get("ALERT_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("ALERT_SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("ALERT_SMTP_USERNAME", "")
SMTP_PASSWORD = read_secret("ALERT_SMTP_PASSWORD", "ALERT_SMTP_PASSWORD_FILE")
SMTP_FROM = os.environ.get("ALERT_SMTP_FROM", SMTP_USERNAME)
SMTP_TO = os.environ.get("ALERT_EMAIL_TO", "")
SMTP_STARTTLS = os.environ.get("ALERT_SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}

LOCK = threading.Lock()


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"incidents": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = STATE_PATH.with_suffix(f".bad.{int(time.time())}.json")
        STATE_PATH.replace(backup)
        return {"incidents": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(STATE_PATH)


def monitor_key(payload: dict[str, Any]) -> str:
    monitor = payload.get("monitor") or {}
    return str(monitor.get("id") or monitor.get("name") or payload.get("monitorName") or "unknown")


def monitor_name(payload: dict[str, Any]) -> str:
    monitor = payload.get("monitor") or {}
    return str(monitor.get("name") or payload.get("monitorName") or monitor_key(payload))


def heartbeat_message(payload: dict[str, Any]) -> str:
    heartbeat = payload.get("heartbeat") or {}
    message = str(heartbeat.get("msg") or payload.get("msg") or "No diagnostic message was provided.")
    return message[:800]


def is_up(payload: dict[str, Any]) -> bool:
    heartbeat = payload.get("heartbeat") or {}
    raw = heartbeat.get("status", payload.get("status", payload.get("msg", "")))
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return int(raw) == 1
    return str(raw).strip().lower() in {"up", "ok", "online", "1", "200", "resolved"}


def format_duration(seconds: int) -> str:
    seconds = max(0, seconds)
    minutes, remainder = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {remainder}s"
    return f"{remainder}s"


def priority_for(name: str) -> str:
    lowered = name.lower()
    p0 = ("headscale public", "adguard dns", "proxmox backup", "vaultwarden", "immich", "nextcloud")
    return "P0" if any(item in lowered for item in p0) else "P1"


def guidance_for(name: str) -> tuple[str, list[str], list[str], str]:
    lowered = name.lower()
    if "headscale" in lowered:
        return (
            "Remote VPN enrollment or administration may be unavailable.",
            ["Check the public edge, NPM, Headscale container, and approved routes."],
            ["pct exec 100 -- docker ps", "pct exec 100 -- docker logs --tail 100 headscale"],
            "https://headscale.internal",
        )
    if "adguard" in lowered:
        return (
            "LAN/VPN DNS filtering and private name resolution may be unavailable.",
            ["Check AdGuard health, port 53, and the .internal rewrite policy."],
            ["pct exec 100 -- docker ps", "dig @192.168.1.50 dash.internal"],
            "https://adguard.internal",
        )
    if "proxmox backup" in lowered or "pbs" in lowered:
        return (
            "Recent infrastructure backups or restore operations may be at risk.",
            ["Check PBS datastore capacity, failed tasks, and the latest backup snapshot."],
            ["pvesm status", "pvesh get /nodes/pve/tasks --limit 20"],
            "https://pbs.internal",
        )
    if "proxmox" in lowered:
        return (
            "VM/LXC management and host-level operations may be unavailable.",
            ["Check pveproxy, storage pools, failed units, and host resource pressure."],
            ["systemctl --failed", "pvesm status", "zpool status -x"],
            "https://proxmox.internal",
        )
    return (
        "The service or its private access path is unavailable.",
        ["Check the service container/VM, NPM target, DNS alias, and recent logs."],
        ["systemctl --failed", "docker ps --format 'table {{.Names}}\\t{{.Status}}'"],
        "https://status.internal",
    )


def incident_id(key: str, first_seen: int) -> str:
    digest = hashlib.sha256(f"{key}:{first_seen}".encode()).hexdigest()[:8].upper()
    date = datetime.fromtimestamp(first_seen, timezone.utc).strftime("%Y%m%d")
    return f"SH-{date}-{digest}"


def render_template(path: Path, context: dict[str, str]) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"email template not found: {path}")
    return string.Template(path.read_text(encoding="utf-8")).safe_substitute(context)


def render_incident(event: str, incident: dict[str, Any], now: int) -> tuple[str, str, str]:
    name = str(incident.get("name", "unknown-monitor"))
    first_seen = int(incident.get("first_seen", now))
    payload = incident.get("payload") or {}
    priority = priority_for(name)
    impact, actions, commands, link = guidance_for(name)
    labels = {
        "down": ("DOWN", "#dc2626", "\U0001F534", f"ALERT: {name} is DOWN"),
        "reminder": ("STILL DOWN", "#d97706", "\U0001F7E0", f"REMINDER: {name} is still DOWN"),
        "resolved": ("RESOLVED", "#059669", "\U0001F7E2", f"RESOLVED: {name} returned UP"),
        "warning": ("WARNING", "#d97706", "⚠️", f"WARNING: {name}"),
        "test": ("TEST", "#2563eb", "\U0001F535", f"TEST: {name}"),
    }
    label, color, glyph, subject = labels[event]
    context = {
        "event": event,
        "status": label,
        "status_color": color,
        "status_glyph": glyph,
        "priority": priority,
        "service": html.escape(name),
        "service_text": name,
        "timestamp": datetime.fromtimestamp(now, timezone.utc).astimezone().isoformat(timespec="seconds"),
        "duration": format_duration(now - first_seen),
        "impact": html.escape(impact),
        "impact_text": impact,
        "message": html.escape(heartbeat_message(payload)),
        "message_text": heartbeat_message(payload),
        "actions_html": "".join(f"<li>{html.escape(item)}</li>" for item in actions),
        "actions_text": "\n".join(f"- {item}" for item in actions),
        "commands_html": "<br>".join(html.escape(item) for item in commands),
        "commands_text": "\n".join(commands),
        "link": html.escape(link),
        "incident_id": str(incident.get("incident_id") or incident_id(monitor_key(payload), first_seen)),
        "anti_spam": "One initial alert, one reminder, and one recovery email per incident.",
    }
    text_body = render_template(TEMPLATE_DIR / f"alert_{event}.txt", context)
    html_body = render_template(TEMPLATE_DIR / f"alert_{event}.html", context)
    return subject, text_body, html_body


def send_email(subject: str, text_body: str, html_body: str | None = None) -> None:
    if DRY_RUN:
        print(json.dumps({"subject": subject, "text": text_body, "has_html": bool(html_body)}, indent=2))
        return
    missing = [
        name
        for name, value in {
            "ALERT_SMTP_HOST": SMTP_HOST,
            "ALERT_SMTP_USERNAME": SMTP_USERNAME,
            "ALERT_SMTP_PASSWORD or ALERT_SMTP_PASSWORD_FILE": SMTP_PASSWORD,
            "ALERT_SMTP_FROM": SMTP_FROM,
            "ALERT_EMAIL_TO": SMTP_TO,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"missing SMTP configuration: {', '.join(missing)}")

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = SMTP_TO
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    if SMTP_STARTTLS:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls(context=context)
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
    else:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as smtp:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)


def try_send_incident(event: str, incident: dict[str, Any], now: int) -> bool:
    try:
        send_email(*render_incident(event, incident, now))
    except Exception as exc:  # noqa: BLE001 - relay must keep processing later incidents
        print(f"email send failed: {exc}")
        return False
    return True


def prune_suppressions(state: dict[str, Any], now: int) -> dict[str, int]:
    supp = {k: int(v) for k, v in state.get("suppress", {}).items() if int(v) > now}
    state["suppress"] = supp
    return supp


def is_suppressed(state: dict[str, Any], name: str, now: int) -> bool:
    lowered = name.lower()
    return any(match.lower() in lowered for match in prune_suppressions(state, now))


def set_suppression(match: str, minutes: int) -> None:
    """Suppress DOWN alerts for monitors whose name contains `match`.

    minutes<=0 clears the suppression. Used when an app/VM is intentionally
    stopped from the dashboard, so a deliberate stop never pages anyone.
    """
    now = int(time.time())
    with LOCK:
        state = load_state()
        prune_suppressions(state, now)
        supp = state.setdefault("suppress", {})
        if minutes > 0:
            supp[match] = now + minutes * 60
            # a currently-open incident for this match should stop reminding
            for k in list(state.get("incidents", {})):
                if match.lower() in str(state["incidents"][k].get("name", "")).lower():
                    state["incidents"].pop(k, None)
        else:
            for k in list(supp):
                if k.lower() == match.lower():
                    supp.pop(k, None)
        save_state(state)


def register_event(payload: dict[str, Any]) -> None:
    key = monitor_key(payload)
    name = monitor_name(payload)
    now = int(time.time())
    with LOCK:
        state = load_state()
        incidents = state.setdefault("incidents", {})
        incident = incidents.get(key)
        if not is_up(payload) and is_suppressed(state, name, now):
            # intentionally stopped: do not open/keep an incident
            incidents.pop(key, None)
            save_state(state)
            return
        if is_up(payload):
            if incident and incident.get("emails_sent", 0) > 0:
                incident["payload"] = payload
                if not try_send_incident("resolved", incident, now):
                    raise RuntimeError("recovery email could not be sent")
            incidents.pop(key, None)
            save_state(state)
            return

        if not incident:
            incidents[key] = {
                "name": name,
                "first_seen": now,
                "last_seen": now,
                "emails_sent": 0,
                "payload": payload,
                "incident_id": incident_id(key, now),
            }
        else:
            incident.update({"name": name, "last_seen": now, "payload": payload})
        save_state(state)


def process_notifications_once(now: int | None = None) -> None:
    now = now or int(time.time())
    with LOCK:
        state = load_state()
        changed = False
        for incident in state.get("incidents", {}).values():
            first_seen = int(incident.get("first_seen", now))
            emails_sent = int(incident.get("emails_sent", 0))
            last_attempt = int(incident.get("last_attempt", 0))
            elapsed = now - first_seen
            if now - last_attempt < ATTEMPT_THROTTLE:
                continue
            event = None
            if emails_sent == 0 and elapsed >= FIRST_DELAY:
                event = "down"
            elif emails_sent == 1 and elapsed >= REMINDER_DELAY:
                event = "reminder"
            if event:
                incident["last_attempt"] = now
                changed = True
                if try_send_incident(event, incident, now):
                    incident["emails_sent"] = emails_sent + 1
        if changed:
            save_state(state)


def notification_loop() -> None:
    while True:
        time.sleep(CHECK_INTERVAL)
        process_notifications_once()


def authenticated(headers: Any) -> bool:
    return bool(RELAY_TOKEN) and headers.get("Authorization", "") == f"Bearer {RELAY_TOKEN}"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok\n")

    def do_POST(self) -> None:
        if self.path not in {"/webhook", "/kuma", "/report", "/suppress"}:
            self.send_error(404)
            return
        if not authenticated(self.headers):
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_PAYLOAD_BYTES:
            self.send_error(413)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/report":
                send_email(str(payload["subject"]), str(payload["text"]), str(payload["html"]))
            elif self.path == "/suppress":
                set_suppression(str(payload["match"]), int(payload.get("minutes", 0)))
            else:
                register_event(payload)
        except Exception as exc:  # noqa: BLE001 - return a useful webhook failure
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"accepted\n")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        print(f"{self.address_string()} - {format % args}")


def self_test() -> int:
    import tempfile

    global STATE_PATH, TEMPLATE_DIR, FIRST_DELAY, REMINDER_DELAY, ATTEMPT_THROTTLE, send_email
    sent: list[tuple[str, str, str | None]] = []
    originals = (STATE_PATH, TEMPLATE_DIR, FIRST_DELAY, REMINDER_DELAY, ATTEMPT_THROTTLE, send_email)

    def fake_send(subject: str, text_body: str, html_body: str | None = None) -> None:
        sent.append((subject, text_body, html_body))

    with tempfile.TemporaryDirectory(prefix="sovereign-alert-relay-test-") as tmpdir:
        try:
            STATE_PATH = Path(tmpdir) / "state.json"
            FIRST_DELAY, REMINDER_DELAY, ATTEMPT_THROTTLE = 1, 5, 0
            send_email = fake_send
            down = {"monitor": {"id": "test", "name": "Relay Self Test"}, "heartbeat": {"status": 0, "msg": "timeout"}}
            up = {"monitor": {"id": "test", "name": "Relay Self Test"}, "heartbeat": {"status": 1, "msg": "200 OK"}}
            register_event(down)
            state = load_state()
            state["incidents"]["test"]["first_seen"] = 1000
            state["incidents"]["test"]["incident_id"] = incident_id("test", 1000)
            save_state(state)
            process_notifications_once(1001)
            process_notifications_once(1005)
            process_notifications_once(1010)
            register_event(up)
            expected = ["ALERT: Relay Self Test is DOWN", "REMINDER: Relay Self Test is still DOWN", "RESOLVED: Relay Self Test returned UP"]
            if [item[0] for item in sent] != expected:
                raise AssertionError("incident message sequence differs from expected")
            if any(not item[2] or "Sovereign Homelab" not in item[2] for item in sent):
                raise AssertionError("HTML body was not rendered")
            if load_state().get("incidents"):
                raise AssertionError("incident state was not cleared")
            print("sovereign-alert-relay self-test OK")
            return 0
        except Exception as exc:  # noqa: BLE001 - concise test failure
            print(f"self-test failed: {exc}")
            return 1
        finally:
            STATE_PATH, TEMPLATE_DIR, FIRST_DELAY, REMINDER_DELAY, ATTEMPT_THROTTLE, send_email = originals


def send_report_file(path: str) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    send_email(str(payload["subject"]), str(payload["text"]), str(payload["html"]))
    return 0


def main() -> None:
    threading.Thread(target=notification_loop, daemon=True).start()
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"sovereign-alert-relay listening on {BIND}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    if "--send-report" in sys.argv:
        index = sys.argv.index("--send-report")
        raise SystemExit(send_report_file(sys.argv[index + 1]))
    main()
