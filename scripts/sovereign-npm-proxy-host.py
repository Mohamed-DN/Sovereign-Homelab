#!/usr/bin/env python3
"""Create or update one NPM proxy host for an *.internal service.

Run on the Proxmox host as root. Standard library only.

Two things this script exists to prevent, both learned the hard way:

* A row written straight into NPM's SQLite produces no nginx configuration at
  all - NPM only generates it when the host goes through its own API. So the
  API is the only supported path.
* The Authentik forward-auth snippet is long and easy to get subtly wrong. It
  is generated here from one working reference (the Hermes host) instead of
  being retyped per service.

  python3 sovereign-npm-proxy-host.py --domain omniroute.internal \\
      --forward 192.168.1.52:20128 --sso --unauth-prefix /v1/ --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

NPM_CTID = "100"
NPM_API = "http://192.168.1.50:81/api"
AUTHENTIK_OUTPOST = "http://192.168.1.51:9000"
INTERNAL_CERT_ID = 2  # "Sovereign Internal Wildcard"

# The proxy headers every location needs, forward-auth or not.
COMMON_PROXY = """    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Scheme $scheme;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
"""

# Streaming answers (SSE) must not be buffered, or they arrive all at once at
# the end - or not at all.
STREAMING = """    proxy_buffering off;
    proxy_cache off;
    chunked_transfer_encoding off;
    proxy_read_timeout 900s;
    proxy_send_timeout 900s;
"""

OUTPOST_BLOCK = """location /outpost.goauthentik.io {{
    proxy_pass {outpost}/outpost.goauthentik.io;
    proxy_set_header Host $host;
    proxy_set_header X-Original-URL $scheme://$http_host$request_uri;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    add_header Set-Cookie $auth_cookie;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}}

location @goauthentik_proxy_signin {{
    internal;
    add_header Set-Cookie $auth_cookie;
    return 302 /outpost.goauthentik.io/start?rd=$scheme://$http_host$request_uri;
}}
"""

FORWARD_AUTH = """    auth_request /outpost.goauthentik.io/auth/nginx;
    error_page 401 = @goauthentik_proxy_signin;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    add_header Set-Cookie $auth_cookie;
    auth_request_set $authentik_username $upstream_http_x_authentik_username;
    auth_request_set $authentik_groups $upstream_http_x_authentik_groups;
    auth_request_set $authentik_email $upstream_http_x_authentik_email;
    auth_request_set $authentik_name $upstream_http_x_authentik_name;
    proxy_set_header X-authentik-username $authentik_username;
    proxy_set_header X-authentik-groups $authentik_groups;
    proxy_set_header X-authentik-email $authentik_email;
    proxy_set_header X-authentik-name $authentik_name;
"""


def mint_token() -> str:
    """Ask NPM for an API token using its own token model.

    NPM has no documented way to obtain a token without the admin password;
    minting one inside the container avoids storing that password anywhere.
    """
    code = ('import tokenModel from "/app/models/token.js"; const t = tokenModel(); '
            'const r = await t.create({iss:"api", attrs:{id:2}, scope:["user"], expiresIn:"10m"}); '
            "console.log(r.token);")
    out = subprocess.run(
        ["pct", "exec", NPM_CTID, "--", "docker", "exec", "npm", "node",
         "--input-type=module", "-e", code],
        capture_output=True, text=True, check=True)
    token = out.stdout.strip().splitlines()[-1].strip()
    if len(token) < 100:
        raise SystemExit(f"token looks wrong ({len(token)} chars)")
    return token


def api(token: str, path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, object]:
    """NPM's API is only reachable from inside LXC 100, so curl runs there."""
    # No `-o /dev/stdout` here: under `pct exec` curl fails with exit 23
    # ("failure writing output") on that destination. The body already goes to
    # stdout by default and -w appends the status after it.
    cmd = ["pct", "exec", NPM_CTID, "--", "curl", "-s",
           "-w", "\n%{http_code}", "-X", method,
           "-H", f"Authorization: Bearer {token}",
           "-H", "Content-Type: application/json"]
    if payload is not None:
        cmd += ["--data-binary", json.dumps(payload)]
    cmd.append(NPM_API + path)
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    body, _, status = out.stdout.rpartition("\n")
    try:
        return int(status.strip()), (json.loads(body) if body.strip() else None)
    except (ValueError, json.JSONDecodeError):
        return int(status.strip() or 0), body[:400]


def build_advanced(forward: str, sso: bool, unauth_prefixes: list[str],
                   extra_locations: list[tuple[str, str]], streaming: bool) -> str:
    """Assemble the advanced_config: exempt locations first, root last."""
    target = f"http://{forward}"
    parts: list[str] = []
    if sso:
        parts.append(OUTPOST_BLOCK.format(outpost=AUTHENTIK_OUTPOST))
    for path, upstream in extra_locations:
        block = [f"location {path} {{", COMMON_PROXY]
        if streaming:
            block.append(STREAMING)
        block.append(f"    proxy_pass {upstream};\n}}\n")
        parts.append("\n".join(block))
    # Prefixes that must stay reachable without a browser session: an API used
    # by a program cannot follow an SSO redirect. Its own credential guards it.
    for prefix in unauth_prefixes:
        block = [f"location {prefix} {{", COMMON_PROXY]
        if streaming:
            block.append(STREAMING)
        block.append(f"    proxy_pass {target};\n}}\n")
        parts.append("\n".join(block))
    root = ["location / {"]
    if sso:
        root.append(FORWARD_AUTH)
    root.append(COMMON_PROXY)
    if streaming:
        root.append(STREAMING)
    root.append(f"    proxy_pass {target};\n}}\n")
    parts.append("\n".join(root))
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--forward", required=True, help="host:port of the backend")
    ap.add_argument("--sso", action="store_true", help="put Authentik forward-auth on /")
    ap.add_argument("--unauth-prefix", action="append", default=[],
                    help="path prefix served without SSO (repeatable)")
    ap.add_argument("--location", action="append", default=[],
                    help="extra location as PATH=UPSTREAM_URL (repeatable)")
    ap.add_argument("--no-streaming", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    host, _, port = args.forward.partition(":")
    if not port.isdigit():
        raise SystemExit("--forward must be host:port")

    extra: list[tuple[str, str]] = []
    for item in args.location:
        path, _, upstream = item.partition("=")
        if not path or not upstream:
            raise SystemExit(f"bad --location: {item}")
        extra.append((path, upstream))

    advanced = build_advanced(args.forward, args.sso, args.unauth_prefix, extra,
                              not args.no_streaming)

    body = {
        "domain_names": [args.domain],
        "forward_scheme": "http",
        "forward_host": host,
        "forward_port": int(port),
        "certificate_id": INTERNAL_CERT_ID,
        "ssl_forced": True,
        "http2_support": True,
        "allow_websocket_upgrade": True,
        "block_exploits": False,
        "caching_enabled": False,
        "hsts_enabled": False,
        "hsts_subdomains": False,
        "access_list_id": 0,
        "advanced_config": advanced,
        "locations": [],
        "meta": {"letsencrypt_agree": False, "dns_challenge": False},
    }

    if args.dry_run:
        print(advanced)
        print(f"\n--- would PUT/POST for {args.domain} -> {args.forward} (sso={args.sso})")
        return 0

    token = mint_token()
    status, hosts = api(token, "/nginx/proxy-hosts")
    if status != 200 or not isinstance(hosts, list):
        raise SystemExit(f"cannot list proxy hosts: HTTP {status} {hosts}")
    existing = next((h for h in hosts if args.domain in (h.get("domain_names") or [])), None)

    if existing:
        status, data = api(token, f"/nginx/proxy-hosts/{existing['id']}", "PUT", body)
        action = f"updated id {existing['id']}"
    else:
        status, data = api(token, "/nginx/proxy-hosts", "POST", body)
        action = "created"
    if status not in (200, 201):
        raise SystemExit(f"{args.domain}: HTTP {status} {json.dumps(data)[:400]}")
    print(f"{args.domain}: {action}")

    check = subprocess.run(["pct", "exec", NPM_CTID, "--", "docker", "exec", "npm", "nginx", "-t"],
                           capture_output=True, text=True)
    print((check.stderr or check.stdout).strip().splitlines()[-1])
    return 0 if check.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
