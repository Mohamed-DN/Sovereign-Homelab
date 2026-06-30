# Runbook 12: Internal CA with Smallstep

**Previous:** [Runbook 11: Security Operations](../06_operations_security/doc_11_security_operations.md)

**Next:** [Operations Manual](../06_operations_security/OPERATIONS_MANUAL.md)

## Purpose

The lab starts with HTTP-only `.internal` aliases over LAN/VPN because that is simple and reliable during bootstrap. That is acceptable for initial build work, but production services that handle passwords, files, photos, identity, or admin sessions should move to trusted private HTTPS.

Smallstep `step-ca` gives the lab an open-source private certificate authority. The goal is not public exposure. The goal is trusted TLS for `*.internal` while keeping every private service behind LAN/VPN.

## Architecture

```text
LAN/VPN client -> AdGuard -> ca.internal -> step-ca on LXC101
Untrusted LAN/VPN client -> http://LXC101_IP:8095 -> public root CA onboarding
Trusted LAN/VPN client -> AdGuard -> trust.internal -> NPM -> trust portal
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
| Trust portal | direct bootstrap `http://LXC101_IP:8095`, normal alias `https://trust.internal` |
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

## Managed Client Trust Bootstrap

Deploy the pinned read-only portal after `step-ca` is healthy:

```bash
cd /opt/sovereign-homelab/stacks/trust-portal
cp .env.example .env
chmod +x render-artifacts.sh
./render-artifacts.sh /var/lib/docker/volumes/internal-ca_step_ca_data/_data/certs/root_ca.crt
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
curl -fsS http://127.0.0.1:8095/healthz
```

The direct HTTP listener is an intentional bootstrap exception. It is reachable only on the private LXC address through LAN/VPN. It exists because an untrusted client cannot validate `https://trust.internal` yet. The portal serves only the root certificate, fingerprint, Windows installer, Apple profile, and instructions. It never receives private CA material.

Create `trust.internal` as a normal NPM Proxy Host targeting `http://LXC101_IP:8095`, assign `Sovereign Internal Wildcard`, enable Force SSL, and leave HSTS disabled during onboarding.

Verify the root fingerprint from the CA host before installation:

```bash
docker exec step-ca step certificate fingerprint /home/step/certs/root_ca.crt
```

| Client | Required action |
|---|---|
| Windows | run the portal installer as Administrator; it imports the verified root into `LocalMachine\Root` and enables Firefox enterprise roots |
| Firefox | current Firefox normally uses the OS trust store; if disabled, enable `security.enterprise_roots.enabled` or deploy the Mozilla `ImportEnterpriseRoots` policy |
| iPhone/iPad | install the `.mobileconfig`, then manually enable full trust under Settings > General > About > Certificate Trust Settings |
| macOS | import the root into the System keychain and set SSL trust to Always Trust |
| Android | install the user CA under security credentials; note that some apps intentionally ignore user-installed CAs |

The `step` CLI remains useful for administrators and certificate diagnostics:

```bash
step ca bootstrap \
  --ca-url https://ca.internal:9002 \
  --fingerprint FINGERPRINT_FROM_SERVER
```

## Issue a Test Certificate

Use a harmless test name first:

```bash
step ca certificate test.internal test.internal.crt test.internal.key \
  --ca-url https://ca.internal:9002 \
  --not-after 8760h
```

Verify the certificate:

```bash
openssl x509 -in test.internal.crt -noout -subject -issuer -dates
```

## Add a Service to the Internal HTTPS Edge

The live lab uses one NPM-managed certificate for all private web aliases. For a new service:

1. Confirm the service has a PBS backup and its direct upstream responds.
2. Create the Proxy Host in the NPM UI; do not write a numbered Nginx file manually.
3. Add the hostname to the SAN list in `scripts/sovereign-renew-npm-internal-certs.sh`.
4. Run a forced certificate renewal during the change window and confirm NPM updates the custom certificate record.
5. Assign `Sovereign Internal Wildcard`, enable Force SSL, HTTP/2, and WebSocket support when required.
6. Test from a trusted client:

   ```bash
   curl -I https://pwd.internal
   ```

7. Add an HTTPS Uptime Kuma monitor with certificate validation enabled.
8. Update the service runbook and live build log.

Rollback restores the NPM database/config backup from before the change or disables only the new Proxy Host. Do not make client-side HTTP the normal rollback state.

## Live Full Internal-Edge Migration

On 2026-06-29, the lab migrated all private web aliases to client-side HTTPS:

| Property | Live value |
|---|---|
| NPM Proxy Hosts | 27 total: one public API plus 26 private aliases |
| Custom certificate name | `Sovereign Internal Wildcard` |
| Certificate names | `*.internal` plus every explicit private web alias SAN |
| Private client scheme | HTTPS with HTTP redirect |
| NPM UI ownership | all Proxy Hosts and the certificate are database-managed and editable |

The CA was configured with a 365-day `maxTLSCertDuration` and `defaultTLSCertDuration` for internal service aliases. The lab still renews them automatically before expiry; the longer duration is only a resilience buffer if the renewal timer is missed.

Validation:

```bash
curl -k -s -o /dev/null -w '%{http_code}\n' https://proxmox.internal/
curl -k -s -o /dev/null -w '%{http_code}\n' https://pbs.internal/
```

Expected result: `200` for both `GET` checks. `curl -I` can return Proxmox/PBS-specific `HEAD` behavior, so do not treat that alone as a failure.

Renewal gate:

- keep a root-only renewal script or timer on the Proxmox host;
- upload renewal through NPM so its UI/database and generated files stay synchronized;
- verify Homepage and Uptime Kuma stay green;
- run the expiry audit after adding or removing any SAN.

Live renewal path:

```text
/usr/local/sbin/sovereign-renew-npm-internal-certs
/etc/systemd/system/sovereign-renew-npm-internal-certs.service
/etc/systemd/system/sovereign-renew-npm-internal-certs.timer
/usr/local/sbin/sovereign-cert-expiry-audit
/etc/systemd/system/sovereign-cert-expiry-audit.service
/etc/systemd/system/sovereign-cert-expiry-audit.timer
```

The renewal script is root-only, stores transient private keys under `/root/sovereign-secrets`, uploads through the authenticated local NPM API, removes temporary files, runs `nginx -t`, and reloads only the NPM container. It renews only inside the 60-day warning window unless explicitly forced.

The expiry-audit timer runs daily. It checks:

- public Headscale certificate;
- the shared internal edge through `dash.internal`;
- representative aliases `proxmox.internal`, `pbs.internal`, and `files.internal`.

If the shared certificate enters the warning window, the audit triggers renewal and checks the aliases again. The audit fails if any checked certificate still expires within the configured window.

## Validation

```bash
curl -k https://ca.internal:9002/health
curl -fsS http://LXC101_IP:8095/healthz
curl -fsS https://trust.internal/healthz
docker compose --env-file .env logs --tail=100 step-ca
docker compose --env-file .env ps
```

Expected:

- health endpoint returns `ok`;
- container is healthy;
- no CA password appears in logs;
- clients that trust the root CA can open the migrated `.internal` HTTPS alias without a browser warning.
- `proxmox.internal`, `pbs.internal`, `dash.internal`, and `foto.internal` validate without `-k` after client onboarding.

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
| Proxmox/PBS HTTPS works with `-k` but browser warns | Smallstep root not trusted on the workstation | install the Smallstep root CA on that admin client |
| Firefox shows `SEC_ERROR_UNKNOWN_ISSUER` after Windows import | Firefox is not using enterprise roots or needs restart | enable automatic third-party root trust, deploy `ImportEnterpriseRoots`, and restart Firefox |
| iPhone profile installs but HTTPS still warns | full trust was not enabled | enable the root under Certificate Trust Settings |
| Proxmox/PBS certificate expires | renewal timer or CA max duration | renew the cert, copy it into NPM custom SSL storage, reload NPM, then test the alias |
| CA starts with a new root unexpectedly | Docker volume missing | stop immediately and restore `step_ca_data`; do not trust the new root blindly |
| ACME/renewal fails through NPM | access policy or proxy mode | test direct CA URL first; remove interactive forward auth from CA issuance path |
| NPM HTTPS migration breaks one app | NPM custom cert or upstream scheme | roll back that one proxy host to HTTP and retry with a test alias |

## Official Sources

- Smallstep `step-ca` overview: <https://smallstep.com/docs/step-ca/>
- Smallstep Docker CA tutorial: <https://smallstep.com/docs/tutorials/docker-tls-certificate-authority/>
- Smallstep installation docs: <https://smallstep.com/docs/step-ca/installation/>
- Nginx Proxy Manager guide: <https://nginxproxymanager.com/guide/>
- Microsoft `certutil` reference: <https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/certutil>
- Mozilla certificate authority setup: <https://support.mozilla.org/en-US/kb/setting-certificate-authorities-firefox>
- Mozilla enterprise policy templates: <https://mozilla.github.io/policy-templates/>
- Apple manually installed certificate trust: <https://support.apple.com/en-us/102390>
- Android network security configuration: <https://developer.android.com/privacy-and-security/security-config>
