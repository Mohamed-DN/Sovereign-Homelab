# Forgejo Deployment Runbook

Forgejo is the private Git service for infrastructure code, application repositories, issues, releases, packages, and SSH keys. It becomes P1 critical as soon as it contains the only copy of a repository or the automation needed to rebuild the lab.

## Purpose and Architecture

```text
browser or Git client -> https://git.internal -> NPM -> LXC102:3003 -> Forgejo
SSH Git client        -> LXC102:2222                         -> Forgejo SSH
Forgejo               -> private Docker network             -> PostgreSQL
```

The web interface is LAN/VPN-only. SSH does not pass through NPM. Public registration stays disabled.

## Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU / RAM | 2 vCPU / 4 GB shared allocation |
| Stack | `/opt/sovereign-homelab/stacks/forgejo` |
| Web alias | `https://git.internal` |
| Web upstream | `http://LXC102_IP:3003` |
| SSH endpoint | `LXC102_IP:2222` |
| Persistent data | `forgejo_data`, `forgejo_db` |
| Classification | P1 important |

Increase storage before enabling large package registries, Actions artifacts, or Git LFS.

## Install from an Empty LXC

1. Complete the common Docker host procedure.
2. Place the repository stack on LXC 102.
3. Create root-only environment values:

```bash
cd /opt/sovereign-homelab/stacks/forgejo
cp .env.example .env
chmod 600 .env
openssl rand -base64 36
nano .env
```

Required values:

| Variable | Purpose |
|---|---|
| `FORGEJO_TAG` | reviewed and pinned Forgejo release |
| `FORGEJO_ROOT_URL` | exactly `https://git.internal/` |
| `FORGEJO_DOMAIN` | exactly `git.internal` |
| `FORGEJO_HTTP_PORT` | host web port `3003` |
| `FORGEJO_SSH_PORT` | advertised and exposed SSH port `2222` |
| `FORGEJO_DB_PASSWORD` | random PostgreSQL password, never a human login password |

Validate and deploy:

```bash
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=100 forgejo forgejo-db
```

Create the first administrator through the web onboarding page or the official CLI. Keep a local break-glass administrator even after OIDC is introduced.

## DNS and NPM

AdGuard wildcard resolution sends `git.internal` to NPM.

Create this NPM Proxy Host:

| Setting | Value |
|---|---|
| Domain | `git.internal` |
| Scheme | `http` |
| Forward host | `LXC102_IP` |
| Forward port | `3003` |
| WebSocket support | enabled |
| Access | LAN/VPN only |
| Certificate | shared internal Smallstep certificate |
| Force SSL | enabled |

Do not proxy port `2222`. Clients use:

```bash
git clone ssh://git@LXC102_IP:2222/OWNER/REPOSITORY.git
```

## Homepage and Uptime Kuma

Homepage card:

```yaml
- Forgejo:
    id: app-forgejo
    icon: forgejo.png
    href: https://git.internal
    siteMonitor: https://git.internal
    description: Git repositories and infrastructure code
```

Required Kuma monitors:

| Monitor | Type | Target |
|---|---|---|
| Forgejo web | HTTPS | `https://git.internal` |
| Forgejo SSH | TCP | `LXC102_IP:2222` |

A green TCP port does not prove Git works. The operational test is a clone, commit, push, and fetch against a test repository.

## Backup

Forgejo uses PostgreSQL plus `/data`. Both must represent the same point in time.

Before an upgrade:

```bash
cd /opt/sovereign-homelab/stacks/forgejo
install -d -m 0700 /root/forgejo-backup
docker compose stop forgejo
docker compose exec -T forgejo-db sh -lc \
  'pg_dump --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -9 > /root/forgejo-backup/forgejo.sql.gz
docker run --rm \
  -v forgejo_forgejo_data:/source:ro \
  -v /root/forgejo-backup:/backup \
  alpine:3.22 tar -C /source -czf /backup/forgejo-data.tar.gz .
docker compose start forgejo
gzip -t /root/forgejo-backup/forgejo.sql.gz
sha256sum /root/forgejo-backup/* > /root/forgejo-backup/SHA256SUMS
```

Use the actual Compose project volume name shown by `docker volume ls`; do not assume it when the project name was changed. PBS remains the full-LXC recovery layer.

The official `forgejo dump` command is useful as an additional export, but the Forgejo upgrade guidance warns that its embedded SQL dump is not the preferred database recovery source. Keep a separate native `pg_dump`.

## Restore Drill

1. Restore the database dump and `/data` archive into an isolated Compose project.
2. Start it with a temporary hostname and no production webhooks or email delivery.
3. Run `forgejo doctor check --all` inside the test container.
4. Log in and inspect repositories, issues, attachments, releases, packages, and LFS if used.
5. Clone through HTTPS and SSH.
6. Commit and push a harmless test change.
7. Record the Forgejo image tag, database table count, repository count, and result.

The 2026-06-23 baseline proved that the PostgreSQL dump restored with 121 public tables and that the data volume could be inventoried. Repeat with a representative repository before relying on Forgejo as the only Git copy.

## Upgrade and Rollback

The live 2026-07-03 inventory still reports Forgejo major version 9, which is discontinued upstream. Do not jump majors without reading every intervening release note.

Controlled upgrade:

1. Confirm the app-aware backup and current PBS snapshot.
2. Clone and push against the pre-upgrade instance.
3. Read the Forgejo 10 through 15 upgrade notes.
4. Use an isolated restored LXC or Compose project to test the target tag first.
5. Update only `FORGEJO_TAG` and redeploy.
6. Run `forgejo doctor check --all`, then repeat clone/push and UI tests.

Rollback before accepting writes on the new version:

1. Stop Forgejo.
2. Restore the previous image tag, PostgreSQL dump, and `/data` from the same timestamp.
3. Start the old version.
4. Verify repositories and Git operations.

Once users write data after a database migration, an image-only rollback is unsafe.

## Troubleshooting

| Symptom | Check | Response |
|---|---|---|
| Clone URL advertises port 22 | `FORGEJO_SSH_PORT`, generated `app.ini` | set port `2222`, restart, verify a newly rendered clone URL |
| HTTPS clones work but SSH fails | Kuma TCP monitor, host firewall, authorized keys | test `ssh -p 2222 git@LXC102_IP`; do not send SSH through NPM |
| Login redirects loop | `ROOT_URL`, NPM forwarded headers | ensure the canonical URL is `https://git.internal/` |
| Repositories exist but issues/users are missing | database restore | restore PostgreSQL and `/data` from the same checkpoint |
| Upgrade migration fails | container logs and release notes | stop writes and restore the complete pre-upgrade checkpoint |
| Actions runner is compromised | runner isolation and secrets | disable runners; never mount the production Docker socket into untrusted jobs |

## Official Sources

- [Forgejo Docker installation](https://forgejo.org/docs/latest/admin/installation/docker/)
- [Forgejo CLI and dump](https://forgejo.org/docs/latest/admin/command-line/)
- [Forgejo upgrade guide](https://forgejo.org/docs/latest/admin/upgrade/)
- [Forgejo releases](https://forgejo.org/releases/)

---

**Previous:** [SearXNG](searxng.md)

**Next:** [Ollama and Open WebUI](ai_ollama.md)
