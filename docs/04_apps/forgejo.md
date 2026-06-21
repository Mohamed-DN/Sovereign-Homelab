# Forgejo

### Purpose

Forgejo stores Git repositories and infrastructure code. It becomes critical if it holds the homelab repo or automation code.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| Profile | `forgejo` |
| Ports | 3003 HTTP, 2222 SSH |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile forgejo config
docker compose --env-file .env --profile forgejo up -d
```

Set:

| Variable | Value |
|---|---|
| `FORGEJO_HTTP_PORT` | `3003` |
| `FORGEJO_SSH_PORT` | `2222` |
| `FORGEJO_DB_PASSWORD` | strong password |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `git.internal` |
| NPM upstream | `http://LXC102_IP:3003` |
| WebSocket | yes |
| Homepage group | Apps |
| Uptime Kuma web | `app-forgejo`, HTTP(s), `https://git.internal` |
| Uptime Kuma SSH | `tcp-forgejo-ssh`, TCP, `LXC102_IP:2222` |
| Access | VPN/Auth |

### Backup

Back up together:

- Forgejo data volume;
- PostgreSQL database;
- repositories;
- SSH keys;
- `.env`.

### Restore Drill

1. Restore DB and repositories to test instance.
2. Log in.
3. Clone a test repository over HTTPS and SSH.
4. Push a test commit.

### Rollback and Troubleshooting

- If repository metadata and DB are out of sync, restore DB and repos from the same timestamp.
- If SSH fails, verify port `2222` and SSH URL.

Source: <https://forgejo.org/docs/latest/admin/installation/docker/>
