# Stack Templates

Questa directory contiene template Docker Compose riutilizzabili.

Regole:

- copia `.env.example` in `.env`;
- cambia ogni valore `CHANGE_ME`;
- non committare mai `.env`;
- esegui `docker compose --env-file .env config` prima del deploy;
- usa Nginx Proxy Manager per HTTPS e hostname;
- metti le UI admin dietro VPN o Authentik.

## Directory

| Directory | Contenuto |
|---|---|
| `identity/` | Authentik, PostgreSQL, Redis |
| `observability/` | Homepage, Uptime Kuma, Beszel, Dozzle |
| `apps/` | Vaultwarden, Syncthing, Immich, Nextcloud AIO |
| `security/` | CrowdSec template |

## Deploy pattern

```bash
cd /opt/sovereign/stacks/<stack>
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## Backup pattern

Prima di usare dati reali:

- includi i volumi nel backup PBS o restic;
- monitora il servizio in Uptime Kuma;
- documenta hostname, porta, volume dati e procedura restore.
