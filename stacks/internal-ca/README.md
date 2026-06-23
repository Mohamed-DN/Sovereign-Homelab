# Internal CA Stack

This stack runs Smallstep `step-ca` for private `.internal` certificates.

Use it after DNS, VPN, NPM, dashboards, and PBS are already stable. Do not switch every service to HTTPS until the root CA is trusted on the devices that will use the lab.

## Target

| Field | Value |
|---|---|
| Host | LXC 101 `platform-services` |
| Alias | `ca.internal` |
| Port | `9002` on host, `9000` in container |
| Access | VPN/admin only |
| Backup | Docker volume `internal-ca_step_ca_data` plus root CA fingerprint record |

## Deploy

```bash
cd /opt/sovereign-homelab/stacks/internal-ca
cp .env.example .env
chmod 600 .env
nano .env
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

Store the real `STEP_CA_PASSWORD` in the host secret vault as well as the real `.env`. Never commit it.

## Bootstrap A Client

```bash
docker compose --env-file .env exec step-ca \
  step certificate fingerprint /home/step/certs/root_ca.crt

step ca bootstrap \
  --ca-url https://ca.internal:9002 \
  --fingerprint FINGERPRINT_FROM_ABOVE
```

After bootstrap, install the root certificate into the client trust store. Only then move private aliases from HTTP bootstrap mode to trusted HTTPS.

## Validate

```bash
curl -k https://ca.internal:9002/health
docker compose --env-file .env logs --tail=100 step-ca
```

Expected health response: `ok`.

## Rollback

1. Stop the stack:

   ```bash
   docker compose --env-file .env down
   ```

2. Do not delete the `step_ca_data` volume unless you are intentionally destroying the CA.
3. If the CA was already trusted on clients, remove the root certificate from those trust stores before replacing it.

## Sources

- Smallstep Docker CA tutorial: <https://smallstep.com/docs/tutorials/docker-tls-certificate-authority/>
- Smallstep step-ca overview: <https://smallstep.com/docs/step-ca/>
- Smallstep installation docs: <https://smallstep.com/docs/step-ca/installation/>
