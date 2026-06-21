# Identity Stack: Authentik

This template is for quick bootstrap. For production and important upgrades, always compare it with the official Authentik Compose file:

```bash
curl -O https://docs.goauthentik.io/compose.yml
```

## Deploy

```bash
cd /opt/sovereign/stacks/identity
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env pull
docker compose --env-file .env up -d
docker compose ps
```

## NPM

| Hostname | Forward | Notes |
|---|---|---|
| `auth.internal` | `http://HOST:9000` | WebSockets enabled; use internal TLS when ready |

## Verification

```bash
docker compose ps
docker compose logs --tail=100 authentik-server
curl -I http://HOST:9000
```

## Backup

Protect:

- `postgresql_data`
- `media_data`
- real `.env`
- admin recovery codes

## Security

- MFA is mandatory for admin.
- Public registration is disabled.
- Docker socket in the worker is used by outposts; consider a socket proxy if you want stronger hardening.
