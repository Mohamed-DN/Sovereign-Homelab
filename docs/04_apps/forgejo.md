# Forgejo Deployment Runbook

## 1. Overview & Sizing
Forgejo is a lightweight, self-hosted Git service. It becomes **P1 Critical** when storing infrastructure-as-code or this homelab repository.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 2 vCPU / 4 GB
- **Ports**: 3003 HTTP, 2222 SSH

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign-homelab/stacks/forgejo
cp .env.example .env
nano .env
```
Ensure the correct configuration parameters:
- `FORGEJO_DB_PASSWORD`: Strong database password.
- Verify ports `FORGEJO_HTTP_PORT=3003` and `FORGEJO_SSH_PORT=2222`.

## 3. Deployment
Validate and start the database and the Forgejo container:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM at `https://npm.internal` and create a Proxy Host for HTTPS:
- **Domain Names**: `git.internal`
- **Scheme / Forward IP / Port**: `http` / `LXC102_IP` / `3003`
- **Websockets Support**: enabled
- **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured.

*(Note: SSH traffic on port 2222 goes directly to the LXC IP and does not pass through NPM).*

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://git.internal`.
- **Uptime Kuma**: 
  - Add an `HTTP(s)` monitor targeting `https://git.internal`.
  - Add a `TCP` monitor targeting `LXC102_IP:2222` to ensure SSH clones are working.

## 6. Backup & Restore
- **Backup**: Include `forgejo_db` and `forgejo_data` volumes in PBS backups. Save `.env`.
- **Restore Drill**:
  1. Restore the database and data volumes to a test instance.
  2. Log in and verify repositories.
  3. Clone a repository over both HTTPS and SSH, and push a test commit successfully.

Live baseline evidence: on 2026-06-23, LXC102 wrote `/root/sovereign-app-restore-drills/20260623T153506Z`, dumped the Forgejo PostgreSQL database, restored it into a temporary database, counted 121 public tables, dropped the temporary database, and captured a manifest for `forgejo_forgejo_data` with 21 files. Before storing important repositories, repeat the drill with a real test repository and verify clone, commit, push, issue/wiki data if used, and SSH access on `LXC102_IP:2222`.

## 7. Rollback and Troubleshooting
- If repository metadata and DB are out of sync, restore DB and repos from the exact same timestamp.
- If SSH fails, verify port `2222` and the `SSH_DOMAIN` in configuration.

*Source: [Forgejo Docker Install](https://forgejo.org/docs/latest/admin/installation/docker/)*

---

**Previous:** [SearXNG](searxng.md)

**Next:** [Ollama and Open WebUI](ai_ollama.md)
