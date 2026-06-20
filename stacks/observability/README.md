# Observability Stack

Services:

- Homepage: dashboard.
- Uptime Kuma: monitors and alerts.
- Beszel: host/container metrics.
- Dozzle: live Docker logs.

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

| Hostname | Forward | Access |
|---|---|---|
| `dash.<domain>` | `http://HOST:3002` | VPN/Auth |
| `status.<domain>` | `http://HOST:3001` | VPN/Auth |
| `monitor.<domain>` | `http://HOST:8090` | VPN/Auth |
| `logs.<domain>` | `http://HOST:8088` | Admin only |

## Verification

```bash
curl -I http://HOST:3002
curl -I http://HOST:3001
curl -I http://HOST:8090
curl -I http://HOST:8088
```

## Beszel Agent

The Beszel UI generates `KEY` and `TOKEN` values when you add a system. Copy them into `.env`:

```text
BESZEL_AGENT_KEY=...
BESZEL_AGENT_TOKEN=...
```

Then restart:

```bash
docker compose --env-file .env up -d beszel-agent
```

## Security Notes

- Dozzle and Beszel agent use the Docker socket or host metrics: admin access only.
- Homepage can show internal links, but it must not contain tokens in YAML.
- Uptime Kuma must monitor DNS, VPN, Authentik, proxy, and core apps.
