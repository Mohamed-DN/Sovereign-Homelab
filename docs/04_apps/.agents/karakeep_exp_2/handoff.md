# Handoff Report: Karakeep Runbook Analysis

## 1. Observation
- **Existing Runbook (`docs/04_apps/karakeep.md`)**: Contains brief steps for LXC 102 setup (2 vCPU / 4 GB), environment setup, `docker compose up -d`, NPM proxy (port `3010`, Websockets Enabled), Homepage/Uptime Kuma monitoring, and basic PBS backup/restore drills.
- **Docker Compose (`stacks/karakeep/docker-compose.yml`)**: 
  - `karakeep` (Next.js app): depends on `karakeep-meilisearch` and `karakeep-chrome`. Exposes port 3000 to `${KARAKEEP_PORT}`. Binds volume `karakeep_data:/data`.
  - `karakeep-meilisearch`: Uses `getmeili/meilisearch:v1.13`. Binds volume `karakeep_meili:/meili_data`.
  - `karakeep-chrome`: Uses `gcr.io/zenika-hub/alpine-chrome:124` for headless web archiving.
- **Environment Variables (`stacks/karakeep/.env.example`)**:
  - Requires `KARAKEEP_NEXTAUTH_SECRET`, `KARAKEEP_MEILI_MASTER_KEY`, `KARAKEEP_PORT=3010`, `KARAKEEP_TAG=release`, `TZ=Europe/Rome`.

## 2. Logic Chain
1. **VM & Pre-requisites**: The current runbook skips the actual VM creation and Docker installation steps. An A-Z guide requires detailing LXC creation, Docker provisioning, and directory setup (`mkdir -p /opt/sovereign/stacks/karakeep`).
2. **Environment Variables Deep Dive**:
   - `KARAKEEP_NEXTAUTH_SECRET`: Essential for NextAuth session encryption. Must be cryptographically secure (e.g., generated via `openssl rand -base64 32`). If changed, all active sessions are invalidated.
   - `NEXTAUTH_URL`: Must exactly match the public URL (`https://bookmarks.internal`). If this mismatches, NextAuth will silently fail callbacks and logins will break.
   - `KARAKEEP_MEILI_MASTER_KEY`: Protects the Meilisearch instance. The app uses this to authenticate. It must match between the app container and the Meilisearch container.
   - `BROWSER_WEB_URL`: Points to the Chrome sidecar (`http://karakeep-chrome:9222`) for capturing page metadata and archiving web pages.
3. **Storage & DB Architecture**: Since there is no Postgres/MySQL container, Karakeep uses a local SQLite database stored inside `karakeep_data:/data`. 
4. **Disaster Recovery (DR)**: 
   - *Backup*: Proxmox Backup Server (PBS) backs up the entire LXC, which captures `karakeep_data` and `karakeep_meili`.
   - *Restore*: The DR procedure in the current runbook is abstract. A concrete DR step involves: stopping the stack, restoring the `/data` and `/meili_data` contents from PBS file-level restore, and bringing the stack back up.
5. **Troubleshooting**: 
   - *Archiving Failures*: Chrome sidecar can run out of memory or crash on heavy SPAs. Restarting `karakeep-chrome` or checking `docker logs -f karakeep-chrome` is required.
   - *Search Index Corruption*: If search is broken, the Meilisearch index might be corrupted. The fix is to stop the stack, delete the contents of `karakeep_meili`, restart, and trigger a reindex from the Karakeep UI or API.
   - *Login Failures*: Usually caused by `NEXTAUTH_URL` missing `https://` or mismatching the NPM configuration.

## 3. Caveats
- Due to strict network mode restrictions (CODE_ONLY), the live "official documentation" (`https://docs.karakeep.app`) could not be fetched. The deep-dive analysis is synthesized via reverse-engineering the NextAuth + Meilisearch + Chrome architecture from the `docker-compose.yml` and `.env.example` files, combined with standard operating procedures for similar Next.js-based bookmarking apps (e.g., Hoarder).
- Assumes SQLite is the default database inside the `karakeep_data` volume since no external database is defined.

## 4. Conclusion
The Worker should rewrite `docs/04_apps/karakeep.md` into an exhaustive A-Z runbook with the following structure:
1. **Infrastructure Provisioning**: LXC 102 specifications, OS setup, Docker installation.
2. **Deployment Configuration**: Explicit instructions for cloning/creating the `docker-compose.yml` and `.env` files. Provide the `openssl` command for generating secrets.
3. **Environment Variables Deep Dive**: Add a table explaining the exact purpose and criticality of `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, and `MEILI_MASTER_KEY`.
4. **Nginx Proxy Manager**: Detailed proxy host setup including Websockets (critical for Next.js apps) and SSL.
5. **Monitoring**: Homepage dashboard widget config and Uptime Kuma monitoring targets.
6. **Disaster Recovery**: Step-by-step backup validation, and explicit commands to restore SQLite data and Meili indices.
7. **Troubleshooting Guide**: Include specific fixes for login loops (NextAuth URL mismatch), Chrome OOM (Out-of-Memory) errors, and Meilisearch reindexing.

## 5. Verification Method
- **Review**: Check the newly written `docs/04_apps/karakeep.md` to ensure all 7 sections outlined in the Conclusion are present and detailed.
- **Test**: Run `docker compose --env-file .env config` in `stacks/karakeep/` to ensure no syntax errors exist in the baseline configuration. Verify the secrets generation commands provided in the runbook are valid standard bash commands.
