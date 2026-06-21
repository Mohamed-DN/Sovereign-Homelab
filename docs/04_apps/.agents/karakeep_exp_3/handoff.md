# Karakeep Investigation Handoff Report

## 1. Observation
- Read `docs/04_apps/karakeep.md`: Found a high-level runbook describing LXC 102 sizing (2 vCPU / 4 GB RAM), Nginx Proxy Manager setup, `.env` file creation, and basic backup commands.
- Read `stacks/karakeep/docker-compose.yml`: Confirmed the stack uses 3 containers:
  - `karakeep` (App container, image: `ghcr.io/karakeep-app/karakeep:${KARAKEEP_TAG}`)
  - `karakeep-meilisearch` (Search DB, image: `getmeili/meilisearch:v1.13`)
  - `karakeep-chrome` (Headless browser for archiving, image: `gcr.io/zenika-hub/alpine-chrome:124`)
- Read `stacks/karakeep/.env.example`: Identified core variables required (`KARAKEEP_TAG`, `KARAKEEP_PORT`, `KARAKEEP_NEXTAUTH_SECRET`, `KARAKEEP_MEILI_MASTER_KEY`).
- Identified volumes: `karakeep_data` (mounted to app's `/data`) and `karakeep_meili` (mounted to meilisearch's `/meili_data`).
- External docs referenced (`https://docs.karakeep.app/installation/docker/`) could not be fetched due to network constraints.

## 2. Logic Chain
- **VM Setup to Monitoring**: The deployment begins with setting up LXC 102 (`apps-light`) and navigating to `/opt/sovereign/stacks/karakeep`. Secrets must be generated in the `.env` file. Once running, NPM routes `bookmarks.internal` to LXC IP (`192.168.1.52`) on the defined `${KARAKEEP_PORT}` (default 3010). Uptime Kuma and Homepage.dev monitor `https://bookmarks.internal`.
- **Deep-Dive Env Vars**:
  - `NEXTAUTH_SECRET`: Used by the app container to secure session tokens. Must match `KARAKEEP_NEXTAUTH_SECRET`.
  - `MEILI_MASTER_KEY`: Secures the Meilisearch instance and is used by the app (`MEILI_ADDR: http://karakeep-meilisearch:7700`) to authenticate.
  - `BROWSER_WEB_URL`: Instructs the app to use `http://karakeep-chrome:9222` for capturing webpage archives.
- **Disaster Recovery (DR) Procedure**:
  - **Backup**: Must include the `.env` file (for secrets), the `karakeep_data` docker volume (for bookmarks and archives), and `karakeep_meili` (for search indexes) via Proxmox Backup Server (PBS).
  - **Restore**: Recreate the VM/LXC, copy `.env` to the stack folder, restore volumes using PBS, and spin up `docker-compose up -d`.
- **Troubleshooting**: If archiving fails, logs for `karakeep-chrome` will show headless browser errors. If search fails, the Meilisearch container might need an index rebuild or restoration of the `karakeep_meili` volume.

## 3. Caveats
- **No External Access**: Operating in CODE_ONLY mode, I could not browse the official `docs.karakeep.app`. The findings and "A-Z steps" are purely reverse-engineered from the existing markdown and compose files.
- **Index Rebuilding**: The specific CLI command to rebuild the Meilisearch index within the Karakeep app is not documented locally and might need to be sourced from Meilisearch docs or Karakeep community guides if needed by the Worker.

## 4. Conclusion
The local repository contains a comprehensive blueprint for Karakeep. The environment variables clearly segment the application, search, and headless browser components. The disaster recovery steps must cover both the stateful volumes (`/data`, `/meili_data`) and the `.env` configuration file. A Worker agent has sufficient structured data here to rewrite the runbook ensuring no steps are missed from VM provisioning to monitoring and troubleshooting.

## 5. Verification Method
- **Inspect Configuration**: Run `docker compose --env-file .env.example config` in `C:\home_server\Sovereign-Homelab\stacks\karakeep` to verify the variable interpolation and volume mounts.
- **Review Volumes**: Inspect the output of the configuration to ensure `karakeep_data` and `karakeep_meili` map correctly to `/data` and `/meili_data` respectively.
