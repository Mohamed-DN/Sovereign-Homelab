# Security Stack

This stack installs CrowdSec as a detection engine.

Important: CrowdSec alone detects. Blocking requires a remediation component, for example Nginx/OpenResty bouncer, firewall bouncer, or another compatible bouncer.

## Deploy

```bash
cd /opt/sovereign-homelab/stacks/security
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
```

## Verification

```bash
docker logs --tail=100 crowdsec
docker exec crowdsec cscli metrics
docker exec crowdsec cscli decisions list
```

## NPM Logs

The template reads:

```text
/opt/core-network/npm/data/logs
```

If NPM lives elsewhere, update `NPM_LOG_DIR` in `.env`.

## Remediation

First phase (done):

- detection only;
- check alerts and false positives.

Second phase — **done, live 2026-07-15**:

- `crowdsec-firewall-bouncer-iptables` installed as an OS-level systemd
  service on the LXC hosting this stack + NPM (not a container — needs direct
  netfilter access), hooked into `DOCKER-USER` so it blocks traffic to NPM's
  published ports without touching Docker's own rules. Verified enforcing
  (local bans + the 31k-entry CAPI community blocklist both loaded into the
  live ipset) with zero impact on legitimate traffic. Full details, exact
  config, and rollback: `docs/06_operations_security/doc_11_security_operations.md`
  Phase E.
