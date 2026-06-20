# Observability Stack

Servizi:

- Homepage: dashboard.
- Uptime Kuma: monitor e alert.
- Beszel: metriche host/container.
- Dozzle: log Docker live.

## Deploy

```bash
cd /opt/sovereign/stacks/observability
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## NPM

| Hostname | Forward | Accesso |
|---|---|---|
| `dash.<domain>` | `http://HOST:3002` | VPN/Auth |
| `status.<domain>` | `http://HOST:3001` | VPN/Auth |
| `monitor.<domain>` | `http://HOST:8090` | VPN/Auth |
| `logs.<domain>` | `http://HOST:8088` | Admin only |

## Verifica

```bash
curl -I http://HOST:3002
curl -I http://HOST:3001
curl -I http://HOST:8090
curl -I http://HOST:8088
```

## Beszel agent

La UI Beszel genera i valori `KEY` e `TOKEN` quando aggiungi un sistema. Copiali in `.env`:

```text
BESZEL_AGENT_KEY=...
BESZEL_AGENT_TOKEN=...
```

Poi riavvia:

```bash
docker compose --env-file .env up -d beszel-agent
```

## Note sicurezza

- Dozzle e Beszel agent usano Docker socket o metriche host: accesso solo admin.
- Homepage puo mostrare link interni, non deve contenere token in YAML.
- Uptime Kuma deve monitorare DNS, VPN, Authentik, proxy e app core.
