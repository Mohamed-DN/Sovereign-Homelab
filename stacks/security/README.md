# Security Stack

This stack installs CrowdSec as a detection engine.

Important: CrowdSec alone detects. Blocking requires a remediation component, for example Nginx/OpenResty bouncer, firewall bouncer, or another compatible bouncer.

## Deploy

```bash
cd /opt/sovereign/stacks/security
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

First phase:

- detection only;
- check alerts and false positives.

Second phase:

- add the appropriate bouncer;
- test blocking with a controlled IP;
- document rollback.
