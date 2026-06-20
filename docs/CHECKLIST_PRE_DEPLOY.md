# Pre-Deploy Checklist

Run this checklist before installing or updating any Sovereign Homelab service.

## 1. Service Identity

| Field | Value |
|---|---|
| Service name |  |
| Category | network / identity / observability / backup / app / security |
| Why it exists |  |
| Owner | Mohamed |
| Host/LXC/VM |  |
| Access | LAN / VPN / Authentik / public |
| Hostname |  |
| Internal port |  |
| Data path |  |
| Backup method | PBS / restic / app export / none |

Rule: if you do not know where it stores data, do not install it.

## 2. Network and DNS

- Correct host IP.
- Port is not already used:

```bash
ss -tulpn
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

- DNS rewrite planned in AdGuard.
- NPM proxy host only after local port verification.
- TLS certificate available or planned.
- Admin services are VPN-only or protected by Authentik.

## 3. Files and Secrets

- `.env.example` contains placeholders only.
- Real `.env` is not committed.
- `.gitignore` excludes `.env`, secrets, local backups, and dumps.
- Every `CHANGE_ME` is replaced in the real file.
- No real token in Markdown.
- Passwords generated with:

```bash
openssl rand -base64 36
```

## 4. Compose Validation

Before deploy:

```bash
docker compose --env-file .env config
```

Then:

```bash
docker compose --env-file .env up -d
docker compose ps
docker compose logs --tail=100
```

Do not continue if Compose validation fails.

## 5. Backup

Before using real data:

- data volumes are known;
- database location is known;
- first backup completed;
- restore test planned;
- backup retention documented.

For app databases, filesystem backup alone is not always enough. Prefer app-supported exports or DB dumps when documented by the upstream project.

## 6. Monitoring

Add at least one Uptime Kuma monitor:

- HTTP endpoint for web apps.
- TCP port if the service is not HTTP.
- DNS check for DNS services.
- Certificate expiry check for public HTTPS.

Add the service to Homepage only after the monitor exists.

## 7. Update Safety

Before update:

- read release notes;
- confirm backup exists;
- record current image tag;
- run `docker compose config`;
- update one stack at a time;
- validate login and data after update.

## 8. Rollback

Write the rollback before deploy:

```text
Previous image tag:
Backup location:
Restore command:
DNS/NPM change to undo:
Expected validation after rollback:
```

If data exists, prefer PBS restore instead of manual deletion.
