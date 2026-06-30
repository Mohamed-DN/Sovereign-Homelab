# Internal CA Trust Portal

This stack publishes only the public root certificate and client onboarding files for the Sovereign Homelab private CA.

## Security Boundary

- `http://LXC101_IP:8095` is the LAN/VPN bootstrap endpoint. It exists because a client cannot trust `https://trust.internal` before installing the root CA.
- `https://trust.internal` is the normal NPM-managed alias after onboarding.
- The stack must never receive the root private key, intermediate private key, provisioner password, application secrets, or API tokens.
- HSTS stays disabled until all personal clients trust the CA.

## Deploy on LXC 101

```bash
cd /opt/sovereign-homelab/stacks/trust-portal
cp .env.example .env
chmod +x render-artifacts.sh
./render-artifacts.sh /var/lib/docker/volumes/internal-ca_step_ca_data/_data/certs/root_ca.crt
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
curl -fsS http://127.0.0.1:8095/healthz
```

Create `trust.internal` as a normal NPM Proxy Host:

| Field | Value |
|---|---|
| Domain | `trust.internal` |
| Scheme | `http` |
| Forward host | `LXC101_IP` |
| Forward port | `8095` |
| WebSockets | no |
| Certificate | `Sovereign Internal Wildcard` |
| Force SSL | yes |
| HSTS | no during onboarding |

## Validation

```bash
curl -fsS http://LXC101_IP:8095/healthz
curl -fsS https://trust.internal/healthz
openssl x509 -in site/downloads/sovereign-root-ca.crt -noout -fingerprint -sha256
grep '^SHA-256:' site/downloads/fingerprint.txt
find site/downloads -maxdepth 1 -type f -printf '%f\n'
```

After installing the root CA, restart browsers and verify `proxmox.internal`, `pbs.internal`, `dash.internal`, and `foto.internal` without bypassing certificate checks.
