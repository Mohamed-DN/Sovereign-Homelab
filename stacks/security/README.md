# Security Stack

Questo stack installa CrowdSec come detection engine.

Importante: CrowdSec da solo rileva. Per bloccare serve un remediation component, per esempio Nginx/OpenResty bouncer, firewall bouncer o altro bouncer compatibile.

## Deploy

```bash
cd /opt/sovereign/stacks/security
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
```

## Verifica

```bash
docker logs --tail=100 crowdsec
docker exec crowdsec cscli metrics
docker exec crowdsec cscli decisions list
```

## NPM logs

Il template legge:

```text
/opt/core-network/npm/data/logs
```

Se NPM vive altrove, aggiorna `NPM_LOG_DIR` nel `.env`.

## Remediation

Prima fase:

- solo detection;
- controllare alert e falsi positivi.

Seconda fase:

- aggiungere bouncer adatto;
- testare blocco con IP controllato;
- documentare rollback.
