# Identity Stack: Authentik

Questo template serve per bootstrap rapido. Per produzione e upgrade importanti, confrontalo sempre con il compose ufficiale Authentik:

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

| Hostname | Forward | Note |
|---|---|---|
| `auth.<domain>` | `http://HOST:9000` | Force SSL, WebSockets enabled |

## Verifica

```bash
docker compose ps
docker compose logs --tail=100 authentik-server
curl -I http://HOST:9000
```

## Backup

Proteggi:

- `postgresql_data`
- `media_data`
- `.env` reale
- recovery code admin

## Security

- MFA obbligatoria per admin.
- Registrazione pubblica disabilitata.
- Docker socket nel worker serve agli outpost; valuta socket proxy se vuoi hardening superiore.
