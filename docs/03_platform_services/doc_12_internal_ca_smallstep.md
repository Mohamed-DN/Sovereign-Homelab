# Runbook 12: Internal CA with Smallstep

**Previous:** [Runbook 11: Security Operations](../06_operations_security/doc_11_security_operations.md)

**Next:** [Operations Manual](../06_operations_security/OPERATIONS_MANUAL.md)

## Purpose

The lab starts with HTTP-only `.internal` aliases over LAN/VPN because that is simple and reliable during bootstrap. That is acceptable for initial build work, but production services that handle passwords, files, photos, identity, or admin sessions should move to trusted private HTTPS.

Smallstep `step-ca` gives the lab an open-source private certificate authority. The goal is not public exposure. The goal is trusted TLS for `*.internal` while keeping every private service behind LAN/VPN.

## Architecture

```text
LAN/VPN client -> AdGuard -> ca.internal -> step-ca on LXC101
LAN/VPN client -> AdGuard -> service.internal -> NPM -> app upstream
```

The CA is used only after VPN/DNS/NPM/PBS are stable. Do not make `ca.internal` public. Do not use DuckDNS for private service certificates.

## Target

| Field | Value |
|---|---|
| Host | LXC 101 `platform-services` |
| Stack | `stacks/internal-ca` |
| Container | `step-ca` |
| Client URL | `https://ca.internal:9002` |
| Backup | `internal-ca_step_ca_data` Docker volume plus root fingerprint record |
| Access | VPN/admin only |

## Prerequisites

- LXC 101 exists and is backed up by PBS.
- `ca.internal` resolves through AdGuard to NPM or directly to LXC101 during bootstrap.
- The operator has a secure place for the CA password outside Git, for example `/root/sovereign-secrets/step-ca-password`.
- No real CA password is committed to `.env.example`, Markdown, shell scripts, or Git history.

## Install

On LXC 101:

```bash
cd /opt/sovereign-homelab/stacks/internal-ca
cp .env.example .env
chmod 600 .env
nano .env
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

Use a long random value for `STEP_CA_PASSWORD`. Store it in the host secret vault:

```bash
install -d -m 700 /root/sovereign-secrets
printf '%s\n' 'CHANGE_ME_LONG_RANDOM_CA_PASSWORD' > /root/sovereign-secrets/step-ca-password
chmod 600 /root/sovereign-secrets/step-ca-password
```

## DNS and NPM

Recommended bootstrap options:

| Mode | Use when | Rule |
|---|---|---|
| Direct | only admins need the CA API | resolve/use `https://LXC101_IP:9002` or `https://ca.internal:9002` directly |
| NPM alias | you want the same dashboard path as other services | add `ca.internal` to NPM and proxy to `https://LXC101_IP:9002` |

If you create an NPM host for `ca.internal`, keep it VPN/admin only. Do not attach Authentik forward auth to the CA API until certificate issuance and renewal flows are proven, because ACME clients may not be able to complete an interactive SSO flow.

## Client Trust Bootstrap

From a trusted admin workstation with the `step` CLI installed:

```bash
ssh root@LXC101_IP
cd /opt/sovereign-homelab/stacks/internal-ca
docker compose --env-file .env exec step-ca \
  step certificate fingerprint /home/step/certs/root_ca.crt
```

Then on the client:

```bash
step ca bootstrap \
  --ca-url https://ca.internal:9002 \
  --fingerprint FINGERPRINT_FROM_SERVER
```

Install the root CA into the OS/browser trust store only on devices you control.

## Issue a Test Certificate

Use a harmless test name first:

```bash
step ca certificate test.internal test.internal.crt test.internal.key \
  --ca-url https://ca.internal:9002
```

Verify the certificate:

```bash
openssl x509 -in test.internal.crt -noout -subject -issuer -dates
```

## Move a Service to HTTPS

Do this one service at a time:

1. Confirm the service has a PBS backup and a working HTTP alias.
2. Issue a certificate for the exact hostname, for example `pwd.internal`.
3. Import the certificate and key into Nginx Proxy Manager as a custom certificate.
4. Enable SSL for that single proxy host.
5. Test from a trusted client:

   ```bash
   curl -I https://pwd.internal
   ```

6. Update Uptime Kuma from HTTP to HTTPS.
7. Update the service runbook and live build log.

Rollback is simple: disable SSL for that one NPM proxy host and return the monitor to HTTP.

## Validation

```bash
curl -k https://ca.internal:9002/health
docker compose --env-file .env logs --tail=100 step-ca
docker compose --env-file .env ps
```

Expected:

- health endpoint returns `ok`;
- container is healthy;
- no CA password appears in logs;
- clients that trust the root CA can open the migrated `.internal` HTTPS alias without a browser warning.

## Backup

Back up:

- Docker volume `internal-ca_step_ca_data`;
- the root CA fingerprint in the operations notes;
- the real `.env` and CA password through a secure root-only secret backup.

Do not lose the CA private material after clients trust it. Losing it forces a CA replacement and client trust cleanup.

## Restore Drill

1. Restore LXC 101 to a temporary ID or restore only the Docker volume to a temporary host.
2. Start the `internal-ca` stack on an isolated test IP.
3. Confirm `/health` returns `ok`.
4. Confirm the root certificate fingerprint matches the recorded fingerprint.
5. Destroy the temporary restore target.

## Troubleshooting

| Symptom | Check | Fix |
|---|---|---|
| `curl` reports certificate error | client trust store | install the root CA on that client |
| CA starts with a new root unexpectedly | Docker volume missing | stop immediately and restore `step_ca_data`; do not trust the new root blindly |
| ACME/renewal fails through NPM | access policy or proxy mode | test direct CA URL first; remove interactive forward auth from CA issuance path |
| NPM HTTPS migration breaks one app | NPM custom cert or upstream scheme | roll back that one proxy host to HTTP and retry with a test alias |

## Official Sources

- Smallstep `step-ca` overview: <https://smallstep.com/docs/step-ca/>
- Smallstep Docker CA tutorial: <https://smallstep.com/docs/tutorials/docker-tls-certificate-authority/>
- Smallstep installation docs: <https://smallstep.com/docs/step-ca/installation/>
- Nginx Proxy Manager guide: <https://nginxproxymanager.com/guide/>
