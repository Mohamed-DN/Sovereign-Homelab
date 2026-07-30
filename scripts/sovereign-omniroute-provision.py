#!/usr/bin/env python3
"""Provision OmniRoute so Hermes can use it: one free keyless provider and one
API key, written where Hermes already looks for engine keys.

Runs INSIDE LXC 102 (it talks to 127.0.0.1:20128 and writes that container's
secret store). Standard library only.

Idempotent. The plaintext API key is returned by OmniRoute exactly once, at
creation; if the local key file is missing we must therefore delete the old key
and mint a new one - there is no way to read an existing key back.

  python3 sovereign-omniroute-provision.py [--dry-run]
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("OMNIROUTE_URL", "http://127.0.0.1:20128")
ENV_FILE = os.environ.get("OMNIROUTE_ENV_FILE", "/opt/sovereign-homelab/stacks/omniroute/.env")
KEY_FILE = os.environ.get("OMNIROUTE_HERMES_KEY_FILE", "/root/sovereign-secrets/hermes/key-omniroute")
KEY_NAME = "hermes"

# Free and keyless: the one provider that can be verified without the owner
# opening an account anywhere. Everything else needs his own credentials.
FREE_CONNECTIONS = [{"provider": "pollinations", "name": "pollinations-free"}]

DRY_RUN = "--dry-run" in sys.argv


def read_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.cookie: str | None = None

    def call(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode() or "{}"
                # The session cookie carries the Secure flag, so it is replayed
                # by hand rather than through a cookie jar (loopback is http).
                for header in resp.headers.get_all("Set-Cookie") or []:
                    match = re.match(r"(auth_token=[^;]+)", header)
                    if match:
                        self.cookie = match.group(1)
                return resp.status, json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode() or "{}"
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, {"error": raw[:300]}

    def login(self, password: str) -> None:
        status, data = self.call("POST", "/api/auth/login", {"password": password})
        if status != 200 or not self.cookie:
            raise SystemExit(f"login failed: HTTP {status} {json.dumps(data)[:200]}")


def write_secret(path: str, value: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Open with 0600 from the start: a chmod after the write leaves an instant
    # in which the key is world-readable.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value + "\n")


def main() -> int:
    env = read_env(ENV_FILE)
    password = env.get("OMNIROUTE_INITIAL_PASSWORD")
    if not password:
        raise SystemExit(f"OMNIROUTE_INITIAL_PASSWORD missing from {ENV_FILE}")

    client = Client(BASE)
    client.login(password)
    print("login: ok")

    # --- providers -----------------------------------------------------------
    _, data = client.call("GET", "/api/providers")
    existing = {c.get("name") for c in data.get("connections", [])}
    for wanted in FREE_CONNECTIONS:
        if wanted["name"] in existing:
            print(f"provider {wanted['name']}: already present")
            continue
        if DRY_RUN:
            print(f"provider {wanted['name']}: would create")
            continue
        status, created = client.call("POST", "/api/providers", {**wanted, "isActive": True})
        conn = created.get("connection", {})
        if status not in (200, 201) or not conn.get("id"):
            print(f"provider {wanted['name']}: FAILED {json.dumps(created)[:200]}")
            continue
        _, test = client.call("POST", f"/api/providers/{conn['id']}/test")
        print(f"provider {wanted['name']}: created, reachable={test.get('valid')}")

    # --- api key -------------------------------------------------------------
    have_file = os.path.exists(KEY_FILE) and os.path.getsize(KEY_FILE) > 0
    _, keys = client.call("GET", "/api/keys")
    mine = [k for k in keys.get("keys", []) if k.get("name") == KEY_NAME and not k.get("revokedAt")]

    if mine and have_file:
        print(f"api key {KEY_NAME}: already present, local copy in {KEY_FILE}")
        return 0
    if DRY_RUN:
        print(f"api key {KEY_NAME}: would (re)create")
        return 0

    for stale in mine:
        # No way to read the plaintext back, so a key we cannot use is dead
        # weight - remove it rather than leave a second valid credential around.
        client.call("DELETE", f"/api/keys/{stale['id']}")
        print(f"api key {KEY_NAME}: removed orphan {stale.get('keyPrefix')}")

    status, created = client.call("POST", "/api/keys", {"name": KEY_NAME})
    if status not in (200, 201):
        raise SystemExit(f"api key creation failed: HTTP {status} {json.dumps(created)[:300]}")

    def find_plaintext(node: object) -> str | None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in {"key", "value", "apikey", "plainkey", "secret"} \
                        and isinstance(value, str) and value.startswith("sk-") and "*" not in value:
                    return value
                found = find_plaintext(value)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = find_plaintext(item)
                if found:
                    return found
        return None

    plaintext = find_plaintext(created)
    if not plaintext:
        raise SystemExit(f"api key created but plaintext not found in response: {json.dumps(created)[:300]}")

    write_secret(KEY_FILE, plaintext)
    print(f"api key {KEY_NAME}: created, written to {KEY_FILE} (0600)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
