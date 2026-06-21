# Vaultwarden

### Purpose

Vaultwarden is the password vault. It is P0 critical because losing it can lock you out of the rest of the lab.

Use it when you want self-hosted Bitwarden-compatible password storage. Do not expose it publicly by default.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 1 vCPU |
| RAM | 1 GB |
| Disk | shared app disk, plus growth for attachments |
| Compose | `stacks/apps` |

### Install

```bash
cd /opt/sovereign/stacks/apps
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d vaultwarden
docker compose --env-file .env logs -f vaultwarden
```

Important `.env` values:

| Variable | Value |
|---|---|
| `VAULTWARDEN_DOMAIN` | `https://pwd.internal` |
| `VAULTWARDEN_ADMIN_TOKEN` | strong value or Argon2 hash |
| `VAULTWARDEN_PORT` | `8082` |

After creating the first user, keep signups disabled.

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `pwd.internal` |
| NPM upstream | `http://LXC102_IP:8082` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma | `app-vaultwarden`, HTTP(s), `https://pwd.internal` |
| Access | VPN-first |

### Backup

Back up:

- `vaultwarden_data` volume;
- `.env` stored in the password vault or offline secret store;
- encrypted Bitwarden export after major password changes.

### Restore Drill

1. Restore the volume to an isolated test LXC.
2. Restore `.env` and admin token.
3. Start Vaultwarden.
4. Verify login, attachments, organizations, and export.

### Rollback and Troubleshooting

- If upgrade breaks login, stop the container and restore the previous volume snapshot.
- If attachments fail, verify `VAULTWARDEN_DOMAIN` matches `https://pwd.internal`.
- If WebSocket sync fails, confirm NPM WebSocket support is enabled.

Source: <https://github.com/dani-garcia/vaultwarden/wiki/Using-Docker-Compose>
