# Karakeep Deployment Runbook

## 1. Overview & Sizing
Karakeep is a modern bookmarking and web archiving tool. It becomes personal-data critical if it is your only bookmark archive.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 2 vCPU / 4 GB

## 2. VM Preparation & Prerequisites
Karakeep requires a container runtime. We host this in our `apps-light` LXC container.
1. **Access LXC 102**: SSH into your Proxmox host and `pct enter 102`, or SSH directly into LXC 102 (`apps-light`).
2. **Install Docker**: Ensure Docker and Docker Compose are installed and running.
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   systemctl enable --now docker
   ```
3. **Directory Scaffolding**: Create the required directory structure for the stack.
   ```bash
   mkdir -p /opt/sovereign-homelab/stacks/karakeep
   cd /opt/sovereign-homelab/stacks/karakeep
   ```
4. **Create `docker-compose.yml`**: Ensure your compose file defines the app, meilisearch, and headless chrome services, as well as the named volumes (`karakeep_data` and `karakeep_meili`).

## 3. Environment Variables & Secrets Deep-Dive
Within the `/opt/sovereign-homelab/stacks/karakeep` directory, create your `.env` file (`cp .env.example .env` if you have an example file, or create it fresh):
```bash
nano .env
```
Key security and configuration variables must be set correctly:

- **`NEXTAUTH_SECRET`**: This is used to encrypt the NextAuth.js JWT tokens (often mapped from `.env` in your `docker-compose.yml`). If this changes, all users are logged out. Generate securely using:
  ```bash
  openssl rand -base64 32
  ```
- **`MEILI_MASTER_KEY`**: The master key securing your Meilisearch instance (often mapped from `.env` in your `docker-compose.yml`). The app uses this to communicate with the search container. Generate securely using:
  ```bash
  openssl rand -base64 32
  ```
- **`NEXTAUTH_URL`**: The canonical URL of your deployment (e.g., `https://bookmarks.internal`). **Crucial**: NextAuth requires this to exactly match the base URL you use to access the app, including `https://` or `http://`. A mismatch will cause login loops and failures.

## 4. Deployment
Validate the configuration and start the containers:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 5. Nginx Proxy Manager (NPM) Setup
Log into NPM at `https://npm.internal` and create a Proxy Host:
- **Domain Names**: `bookmarks.internal`
- **Scheme / Forward IP / Port**: `http` / `LXC102_IP` / `3010`
- **Websockets Support**: enabled
- **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured.

## 6. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://bookmarks.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://bookmarks.internal`.

## 7. Disaster Recovery (DR) Procedure
Data integrity for Karakeep relies on SQLite and Meilisearch. **Live backups can cause severe database corruption.**

### Backup Procedure
1. **Stop Containers**: You MUST stop the containers before copying data.
   ```bash
   cd /opt/sovereign-homelab/stacks/karakeep
   docker compose down
   ```
2. **Backup Volumes & Config**: Use a temporary container to safely archive the named volumes, and standard `tar` for config files.
   ```bash
   docker run --rm -v karakeep_data:/data -v karakeep_meili:/meili_data -v $(pwd):/backup alpine tar -czvf /backup/karakeep_volumes_$(date +%F).tar.gz -C / data meili_data
   tar -czvf karakeep_config_$(date +%F).tar.gz .env docker-compose.yml
   ```
3. **Restart Containers**:
   ```bash
   docker compose up -d
   ```
*(Note: If using Proxmox Backup Server (PBS) to snapshot the entire LXC, ensure a pre-backup hook stops the Docker containers and a post-backup hook starts them.)*

### Restore Procedure
1. **Stop running containers** on the target machine (if any): `docker compose down`.
2. **Restore Config**: Extract the configuration archive into `/opt/sovereign-homelab/stacks/karakeep`.
   ```bash
   tar -xzvf karakeep_config_*.tar.gz
   ```
3. **Restore Docker Volumes**: Use a temporary container to extract the volume archive directly into the named volumes.
   ```bash
   docker run --rm -v karakeep_data:/data -v karakeep_meili:/meili_data -v $(pwd):/backup alpine sh -c "tar -xzvf /backup/karakeep_volumes_*.tar.gz -C /"
   ```
4. **Start Application**: Run `docker compose up -d` in `/opt/sovereign-homelab/stacks/karakeep`.
5. **Verify**: Log in, search for a bookmark, and verify archived pages render correctly.

## 8. Troubleshooting
- **NextAuth Login Failures**: If you are repeatedly kicked back to the login screen, check your `NEXTAUTH_URL` in `.env`. It must exactly match the URL in your browser (e.g., `https://bookmarks.internal`), without any trailing slash.
- **Chrome OOM (Out of Memory) Crashes**: If archiving fails on heavy JavaScript sites, the headless Chrome container might be crashing due to memory limits.
  - Check logs: `docker logs karakeep-chrome`
  - *Fix*: Increase memory limits in `docker-compose.yml` for the chrome service or provide more RAM to LXC 102.
- **Meilisearch Recovery**: If search returns 0 results or errors out:
  - Verify `MEILI_MASTER_KEY` matches between the app and meilisearch service.
  - If the index is hopelessly corrupted, stop the stack, delete the `karakeep_meili` volume, start the stack, and trigger a full re-index from the Karakeep settings menu.

*Source: [Karakeep Docker Docs](https://docs.karakeep.app/installation/docker/)*

---

**Previous:** [FreshRSS](freshrss.md)

**Next:** [SearXNG](searxng.md)
