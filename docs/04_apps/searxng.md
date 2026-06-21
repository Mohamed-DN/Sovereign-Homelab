# SearXNG Deployment Runbook

## 1. Overview & Sizing
SearXNG is a privacy-respecting metasearch engine. Do not expose this publicly to avoid your IP being banned by upstream search providers.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB
- **Access**: Strict VPN/Internal access only.

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/searxng
cp .env.example .env
nano .env
```
Update the required variables:
- `SEARXNG_SECRET_KEY`: Generate a random string using `openssl rand -hex 32`.
- `SEARXNG_BASE_URL=https://search.internal`

## 3. Deployment
Validate and start the container along with its Redis cache:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM at `https://npm.internal` and create a Proxy Host:
- **Domain Names**: `search.internal`
- **Scheme / Forward IP / Port**: `http` / `LXC102_IP` / `8084`
- **Websockets Support**: disabled; SearXNG does not need it.
- **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://search.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://search.internal`.

## 6. Backup & Restore
- **Backup**: Only the `searxng_config` needs to be backed up via PBS, as user data is intentionally not retained.
- **Restore Drill**:
  1. Restore config to a test instance.
  2. Run a query and ensure engines respond.

## 7. Rollback and Troubleshooting
- If engines fail, update SearXNG and review engine config (`settings.yml`). Upstream engines often change HTML structures breaking SearXNG extractors.
- Do not expose publicly or you will be quickly rate-limited by Google/Bing.

*Source: [SearXNG Docker Install](https://docs.searxng.org/admin/installation-docker.html)*
