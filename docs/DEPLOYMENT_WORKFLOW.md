# Deployment Workflow

This is the standard procedure for adding a new service without creating operational drift. Apply it even for small apps.

Recommended example for the next service: Paperless-ngx or FreshRSS, because both provide high value with manageable risk when backup and access are configured correctly.

## Phase 0: Decision

Before creating files:

1. Write why the service exists.
2. Check whether an equivalent app already exists.
3. Decide access:
   - VPN only;
   - VPN + Authentik;
   - public HTTPS only when truly required.
4. Decide backup:
   - volumes;
   - database;
   - app export;
   - restore test.
5. Keep the rule in mind: no backup, no production.

## Phase 1: Choose Hostname, Port, and Data Path

Use this convention:

| Type | Example |
|---|---|
| Passwords | `pwd.<domain>` |
| Photos | `foto.<domain>` |
| Files | `files.<domain>` |
| Documents | `paper.<domain>` |
| RSS | `rss.<domain>` |
| Bookmarks | `bookmarks.<domain>` |
| Media | `media.<domain>` |
| Home automation | `ha.<domain>` |

Before deployment:

- verify that the port is not already used;
- create the AdGuard DNS rewrite only when NPM is ready;
- choose predictable volumes, for example `/opt/sovereign/stacks/<stack>`;
- do not store important data in temporary bind mounts.

Commands:

```bash
ss -tulpn
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

## Phase 2: Prepare Files

Pattern:

```bash
cd /opt/sovereign/stacks
mkdir -p <stack-name>
cd <stack-name>
cp .env.example .env
nano .env
```

`.env` rules:

- every `CHANGE_ME` must be replaced in the real file;
- never commit `.env`;
- generate passwords with `openssl rand -base64 36`;
- pin image tags after the first stable deployment;
- keep the real domain only in `.env` when possible, not in public templates.

## Phase 3: Validate Compose

Before starting:

```bash
docker compose --env-file .env config
```

If it fails:

- do not start;
- fix YAML indentation;
- verify missing variables;
- verify duplicate ports.

Start:

```bash
docker compose --env-file .env up -d
docker compose ps
docker compose logs --tail=100
```

## Phase 4: NPM and TLS

In Nginx Proxy Manager:

1. Add Proxy Host.
2. Domain: `service.<domain>`.
3. Scheme: `http`.
4. Forward Hostname/IP: Docker host IP or container name if on the same network.
5. Forward Port: published internal port.
6. Enable WebSockets if the app uses them.
7. Enable SSL with the wildcard certificate.
8. Enable Force SSL.

Access:

- admin UI: VPN/Auth;
- personal app: VPN-first;
- public only when required and documented.

## Phase 5: Authentik

If the service does not have strong MFA or is an admin UI:

1. Create an Application in Authentik.
2. Create a Proxy Provider.
3. Attach the Outpost.
4. Configure NPM with forward auth if needed.
5. Test from a clean browser or private session.

Do not protect the Headscale control plane with generic forward auth: VPN clients must be able to talk to `vpn.<domain>` without an interactive web flow.

## Phase 6: Uptime Kuma and Homepage

Minimum Uptime Kuma coverage:

- HTTP monitor on `https://service.<domain>`;
- TCP monitor for non-HTTP services;
- DNS monitor for AdGuard and critical records.

Homepage:

- add the link to the correct group;
- use the public/VPN hostname, not a raw IP;
- avoid public admin links unless protected.

## Phase 7: Backup and Restore Test

Before declaring production:

1. Run a backup.
2. Restore into an isolated path or VM/LXC.
3. Verify login and data.
4. Document the restore.

For apps with databases:

- data backup and DB backup must be consistent;
- do not copy only the web volume;
- use a DB dump before filesystem backup when possible.

## Phase 8: Update Documentation

Update:

- [Inventory and IP Plan](INVENTORY_AND_IP_PLAN.md)
- [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md)
- [Validation Commands](VALIDATION_COMMANDS.md), if service-specific tests are needed
- [Troubleshooting Matrix](TROUBLESHOOTING_MATRIX.md), if you find recurring failures
- Homepage config in the observability stack, if managed by this repo

## Example: Paperless-ngx

Decision:

- hostname: `paper.<domain>`;
- access: VPN/Auth;
- data: original documents, OCR media, DB;
- backup: DB + media + consume/export;
- monitor: HTTP through Uptime Kuma.

Checklist:

```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
docker compose logs --tail=100
```

Validation:

- admin login;
- test document upload;
- OCR completed;
- search finds the document;
- backup completed;
- restore test with the sample document.

## Example: FreshRSS

Decision:

- hostname: `rss.<domain>`;
- access: VPN/Auth;
- data: feeds, users, DB or data volume;
- backup: data volume or DB;
- monitor: HTTP login page.

Validation:

- admin login;
- feed added;
- automatic refresh works;
- OPML export can be downloaded;
- volume backup tested.

## New Service Rollback

If the service does not work:

```bash
docker compose logs --tail=200
docker compose down
```

Then:

- remove the NPM proxy host if it creates errors;
- remove the DNS rewrite if it points to a service that is not ready;
- keep volumes until you decide whether they are needed for debugging;
- document the cause before trying again.

## Acceptance Criteria

A deployment is complete only when:

- `docker compose config` passes;
- the service is reachable through its hostname;
- access matches the VPN/Auth/public decision;
- Uptime Kuma monitor is configured;
- backup has run;
- minimum restore was tested;
- inventory is updated;
- rollback is written.

## Useful Official Sources

- Paperless-ngx setup: <https://docs.paperless-ngx.com/setup/>
- Home Assistant alternative install: <https://www.home-assistant.io/installation/alternative/>
- FreshRSS Docker image: <https://hub.docker.com/r/freshrss/freshrss>
- Karakeep docs: <https://docs.karakeep.app/>
- Jellyfin container docs: <https://jellyfin.org/docs/general/installation/container/>
- SearXNG Docker install: <https://docs.searxng.org/admin/installation-docker.html>
- Forgejo Docker install: <https://forgejo.org/docs/latest/admin/installation/docker/>
- Open WebUI docs: <https://docs.openwebui.com/>
