#!/usr/bin/env python3
"""Small webhook-to-email relay for Uptime Kuma anti-spam alerting.

The relay uses only Python standard-library modules. It is intentionally simple:

- first DOWN email after ALERT_FIRST_DELAY_SECONDS, default 60 seconds;
- one REMINDER email after ALERT_REMINDER_DELAY_SECONDS, default 300 seconds;
- no more DOWN email for the same incident until recovery;
- one RESOLVED email when the monitor recovers after an alert was sent.

Secrets come from environment variables or root-only files. Do not commit real
SMTP credentials or relay tokens.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


STATE_PATH = Path(os.environ.get("ALERT_STATE_PATH", "/var/lib/sovereign-alert-relay/state.json"))
BIND = os.environ.get("ALERT_RELAY_BIND", "127.0.0.1")
PORT = int(os.environ.get("ALERT_RELAY_PORT", "8099"))
FIRST_DELAY = int(os.environ.get("ALERT_FIRST_DELAY_SECONDS", "60"))
REMINDER_DELAY = int(os.environ.get("ALERT_REMINDER_DELAY_SECONDS", "300"))
CHECK_INTERVAL = int(os.environ.get("ALERT_CHECK_INTERVAL_SECONDS", "10"))


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
    tmp.replace(STATE_PATH)


def monitor_key(payload: dict[str, Any]) -> str:
    monitor = payload.get("monitor") or {}
    return str(monitor.get("id") or monitor.get("name") or payload.get("monitorName") or "unknown-monitor")


def monitor_name(payload: dict[str, Any]) -> str:
    monitor = payload.get("monitor") or {}
    return str(monitor.get("name") or payload.get("monitorName") or monitor_key(payload))


def is_up(payload: dict[str, Any]) -> bool:
    heartbeat = payload.get("heartbeat") or {}
    raw = heartbeat.get("status", payload.get("status", payload.get("msg", "")))
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return int(raw) == 1
    status = str(raw).strip().lower()
    return status in {"up", "ok", "online", "1", "200", "resolved"}


def send_email(subject: str, body: str) -> None:
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
    message.set_content(body)

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


def try_send_email(subject: str, body: str) -> bool:
    try:
        send_email(subject, body)
    except Exception as exc:  # noqa: BLE001 - keep relay loop alive and log cause
        print(f"email send failed: {exc}")
        return False
    return True


def register_event(payload: dict[str, Any]) -> None:
    key = monitor_key(payload)
    name = monitor_name(payload)
    now = int(time.time())
    up = is_up(payload)

    with LOCK:
        state = load_state()
        incidents = state.setdefault("incidents", {})
        incident = incidents.get(key)

        if up:
            if incident and incident.get("emails_sent", 0) > 0:
                subject = f"RESOLVED: {name} returned UP"
                body = json.dumps({"event": "resolved", "monitor": name, "payload": payload}, indent=2)
                send_email(subject, body)
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
            }
        else:
            incident["name"] = name
            incident["last_seen"] = now
            incident["payload"] = payload
        save_state(state)


def notification_loop() -> None:
    while True:
        time.sleep(CHECK_INTERVAL)
        with LOCK:
            state = load_state()
            changed = False
            now = int(time.time())
            for incident in state.get("incidents", {}).values():
                first_seen = int(incident.get("first_seen", now))
                emails_sent = int(incident.get("emails_sent", 0))
                last_attempt = int(incident.get("last_attempt", 0))
                name = incident.get("name", "unknown-monitor")
                elapsed = now - first_seen
                if now - last_attempt < 60:
                    continue
                if emails_sent == 0 and elapsed >= FIRST_DELAY:
                    subject = f"ALERT: {name} is DOWN"
                    body = json.dumps({"event": "down", "elapsed_seconds": elapsed, "incident": incident}, indent=2)
                    incident["last_attempt"] = now
                    changed = True
                    if try_send_email(subject, body):
                        incident["emails_sent"] = 1
                elif emails_sent == 1 and elapsed >= REMINDER_DELAY:
                    subject = f"REMINDER: {name} is still DOWN after 5 minutes"
                    body = json.dumps({"event": "reminder", "elapsed_seconds": elapsed, "incident": incident}, indent=2)
                    incident["last_attempt"] = now
                    changed = True
                    if try_send_email(subject, body):
                        incident["emails_sent"] = 2
            if changed:
                save_state(state)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok\n")

    def do_POST(self) -> None:
        if self.path not in {"/webhook", "/kuma"}:
            self.send_response(404)
            self.end_headers()
            return
        if RELAY_TOKEN:
            expected = f"Bearer {RELAY_TOKEN}"
            if self.headers.get("Authorization", "") != expected:
                self.send_response(401)
                self.end_headers()
                return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        try:
            register_event(payload)
        except Exception as exc:  # noqa: BLE001 - return failure to Kuma webhook
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"accepted\n")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    threading.Thread(target=notification_loop, daemon=True).start()
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"sovereign-alert-relay listening on {BIND}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
