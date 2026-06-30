#!/usr/bin/env bash
set -euo pipefail

# Renew the single Smallstep-issued certificate used by every NPM-managed
# *.internal Proxy Host. Run this script on the Proxmox host as root.

WARN_DAYS="${WARN_DAYS:-60}"
FORCE="${FORCE:-0}"
NPM_IP="${NPM_IP:-192.168.1.50}"
CERT_NAME="${CERT_NAME:-Sovereign Internal Wildcard}"
WORKDIR="${WORKDIR:-/root/sovereign-secrets/tmp-npm-internal-cert-renewal}"
LOGDIR="${LOGDIR:-/root/sovereign-secrets/logs}"

aliases=(
  adguard npm headscale proxmox pbs auth dash status monitor logs
  pwd sync paper rss bookmarks search git foto media ai files
  netalert disks alerts ha trust
)

mkdir -p "$WORKDIR" "$LOGDIR"
chmod 700 "$WORKDIR" "$LOGDIR"
umask 077

log="$LOGDIR/renew-npm-internal-certs-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "$log") 2>&1

printf '[%s] checking NPM internal certificate\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ "$FORCE" != "1" ]] && timeout 15 openssl s_client \
  -connect "${NPM_IP}:443" \
  -servername dash.internal </dev/null 2>/dev/null |
  openssl x509 -checkend "$((WARN_DAYS * 86400))" -noout >/dev/null 2>&1; then
  printf '[%s] certificate is valid beyond %s days; renewal is not required\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$WARN_DAYS"
  exit 0
fi

rm -f "$WORKDIR"/*
pct exec 101 -- docker exec step-ca rm -f \
  /tmp/internal-edge.crt \
  /tmp/internal-edge.key

san_args=()
for name in "${aliases[@]}"; do
  san_args+=(--san "${name}.internal")
done

pct exec 101 -- docker exec step-ca step ca certificate \
  dash.internal \
  /tmp/internal-edge.crt \
  /tmp/internal-edge.key \
  --ca-url https://127.0.0.1:9000 \
  --root /home/step/certs/root_ca.crt \
  --provisioner admin \
  --provisioner-password-file /home/step/secrets/password \
  --san '*.internal' \
  "${san_args[@]}" \
  --not-after 8760h \
  --force

pct exec 101 -- docker cp step-ca:/tmp/internal-edge.crt /tmp/internal-edge.crt
pct exec 101 -- docker cp step-ca:/tmp/internal-edge.key /tmp/internal-edge.key
pct exec 101 -- docker cp step-ca:/home/step/certs/intermediate_ca.crt /tmp/internal-intermediate.crt
pct exec 101 -- docker cp step-ca:/home/step/certs/root_ca.crt /tmp/internal-root-ca.crt

pct pull 101 /tmp/internal-edge.crt "$WORKDIR/certificate.pem"
pct pull 101 /tmp/internal-edge.key "$WORKDIR/certificate-key.pem"
pct pull 101 /tmp/internal-intermediate.crt "$WORKDIR/intermediate.pem"
pct pull 101 /tmp/internal-root-ca.crt "$WORKDIR/root-ca.pem"
chmod 600 "$WORKDIR"/*

# step-ca may return the leaf plus its intermediate in the certificate output.
# NPM appends the separately uploaded intermediate itself, so upload only the
# first PEM block as the leaf or the served chain will duplicate the CA cert.
awk '
  /-----BEGIN CERTIFICATE-----/ { blocks++ }
  blocks == 1 { print }
  /-----END CERTIFICATE-----/ && blocks == 1 { exit }
' "$WORKDIR/certificate.pem" > "$WORKDIR/certificate-leaf.pem"
mv "$WORKDIR/certificate-leaf.pem" "$WORKDIR/certificate.pem"
if [[ "$(grep -c 'BEGIN CERTIFICATE' "$WORKDIR/certificate.pem")" != "1" ]]; then
  echo "could not normalize the Smallstep output to one leaf certificate" >&2
  exit 1
fi

openssl verify \
  -CAfile "$WORKDIR/root-ca.pem" \
  -untrusted "$WORKDIR/intermediate.pem" \
  "$WORKDIR/certificate.pem"

CERT_NAME="$CERT_NAME" WORKDIR="$WORKDIR" python3 - <<'PY'
import json
import os
from pathlib import Path
import base64
import secrets
import subprocess
import urllib.error
import urllib.request

api = "http://192.168.1.50:81/api"
workdir = Path(os.environ["WORKDIR"])
cert_name = os.environ["CERT_NAME"]

node_code = """import tokenModel from '/app/models/token.js';
const token = tokenModel();
const result = await token.create({iss:'api', attrs:{id:2}, scope:['user'], expiresIn:'10m'});
console.log(result.token);"""
output = subprocess.check_output(
    ["pct", "exec", "100", "--", "docker", "exec", "npm", "node", "--input-type=module", "-e", node_code],
    text=True,
)
token = output.strip().splitlines()[-1]


def request(path, method="GET", body=None, content_type=None):
    headers = {"Authorization": "Bearer " + token}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(api + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: HTTP {exc.code}: {detail}") from exc


certificates = request("/nginx/certificates")
certificate = next((item for item in certificates if item["nice_name"] == cert_name), None)
if certificate is None:
    raise SystemExit(f"NPM certificate not found: {cert_name}")

boundary = "----sovereign-" + secrets.token_hex(16)
parts = []
for field, filename in (
    ("certificate", "certificate.pem"),
    ("certificate_key", "certificate-key.pem"),
    ("intermediate_certificate", "intermediate.pem"),
):
    path = workdir / filename
    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: application/x-pem-file\r\n\r\n",
            path.read_bytes(),
            b"\r\n",
        ]
    )
parts.append(f"--{boundary}--\r\n".encode())

request(
    f"/nginx/certificates/{certificate['id']}/upload",
    "POST",
    b"".join(parts),
    f"multipart/form-data; boundary={boundary}",
)

# NPM 2.15 can preserve the uploaded chain bundle in meta.certificate and
# append meta.intermediate_certificate again when writing fullchain.pem.
# Normalize the database-backed custom certificate through NPM's own runtime
# modules so the UI remains authoritative and the served chain has no duplicate.
leaf_b64 = base64.b64encode((workdir / "certificate.pem").read_bytes()).decode()
intermediate_b64 = base64.b64encode((workdir / "intermediate.pem").read_bytes()).decode()
node_code = f"""
import db from '/app/db.js';
import internalCertificate from '/app/internal/certificate.js';
const id = {int(certificate['id'])};
const row = await db()('certificate').where({{id}}).first();
if (!row || row.provider !== 'other') throw new Error('custom certificate record not found');
const meta = typeof row.meta === 'string' ? JSON.parse(row.meta) : {{...row.meta}};
meta.certificate = Buffer.from('{leaf_b64}', 'base64').toString('utf8');
meta.intermediate_certificate = Buffer.from('{intermediate_b64}', 'base64').toString('utf8');
await db()('certificate').where({{id}}).update({{meta: JSON.stringify(meta), modified_on: new Date()}});
await internalCertificate.writeCustomCert({{id, provider: row.provider, meta}});
await db().destroy();
"""
subprocess.run(
    ["pct", "exec", "100", "--", "docker", "exec", "npm", "node", "--input-type=module", "-e", node_code],
    check=True,
    text=True,
    capture_output=True,
)
print(f"updated and normalized NPM certificate id {certificate['id']}")
PY

pct exec 100 -- docker exec npm nginx -t
pct exec 100 -- docker exec npm nginx -s reload
sleep 1

served_chain_count="$({
  timeout 15 openssl s_client -connect "${NPM_IP}:443" -servername dash.internal -showcerts </dev/null 2>/dev/null || true
} | grep -c 'BEGIN CERTIFICATE')"
if [[ "$served_chain_count" != "2" ]]; then
  echo "NPM served chain contains ${served_chain_count} certificates; expected leaf plus one intermediate" >&2
  exit 1
fi

if ! timeout 15 openssl s_client \
  -connect "${NPM_IP}:443" \
  -servername dash.internal </dev/null 2>/dev/null |
  openssl x509 -checkend "$((WARN_DAYS * 86400))" -noout >/dev/null 2>&1; then
  echo "renewed certificate failed the post-renewal validity check" >&2
  exit 1
fi

rm -f "$WORKDIR"/*
printf '[%s] NPM internal certificate renewal complete\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
