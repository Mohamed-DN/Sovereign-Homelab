# Karakeep Runbook Fix Strategy

## 1. Observation
- **Observation 1 (Env Vars):** `karakeep.md` (lines 31, 35) documents the environment variables using the `.env` variable names (`KARAKEEP_NEXTAUTH_SECRET`, `KARAKEEP_MEILI_MASTER_KEY`). However, `docker-compose.yml` (lines 10-11) injects these into the container using the application's expected names (`NEXTAUTH_SECRET`, `MEILI_MASTER_KEY`). Reviewer 2 flagged the documentation for using `KARAKEEP_NEXTAUTH_SECRET` instead of `NEXTAUTH_SECRET`.
- **Observation 2 (Backup Paths):** `karakeep.md` (line 71) recommends backing up Docker volumes by referencing the host path directly: `/var/lib/docker/volumes/karakeep_data` and `/var/lib/docker/volumes/karakeep_meili`. `docker-compose.yml` mounts these named volumes to container-internal paths `/data` and `/meili_data` (lines 17, 29). Reviewer 2 stated the DR process backed up the host paths instead of the internal paths explicitly.

## 2. Logic Chain
- To address **Observation 1** while maintaining accuracy with the `docker-compose.yml` file, the documentation must headline the application variables (`NEXTAUTH_SECRET` and `MEILI_MASTER_KEY`), but explicitly clarify that they are provided via the `.env` file using the `KARAKEEP_` prefixed variables. This satisfies the reviewer's request without breaking the compose file logic.
- To address **Observation 2**, directly archiving host volume paths (`/var/lib/docker/volumes/...`) is generally discouraged. Instead, we should recommend a `docker run` command that spawns a temporary Alpine container, mounts the `karakeep_data` and `karakeep_meili` volumes directly, and archives their container-internal paths (`/data` and `/meili_data`). This exactly matches Reviewer 2's expectation.

## 3. Caveats
- Using a Docker container to archive the configuration files (`.env` and `docker-compose.yml`) alongside the internal volume paths requires careful pathing during the backup. We will mount the current host directory to `/backup` inside the container.
- When restoring, the configuration files will need to be extracted back to the host directory, while the volumes will be restored using another temporary container.

## 4. Conclusion
**Proposed Fix Strategy:**

1. **Update Section 3 (Environment Variables):**
   Modify the bullet points in `karakeep.md` to:
   - `- **`NEXTAUTH_SECRET`** (configured via `KARAKEEP_NEXTAUTH_SECRET` in `.env`): This is used to encrypt...`
   - `- **`MEILI_MASTER_KEY`** (configured via `KARAKEEP_MEILI_MASTER_KEY` in `.env`): The master key securing...`

2. **Update Section 7 (Disaster Recovery):**
   Replace the host-based `tar` command with a robust container-based approach:
   **Backup Command:**
   ```bash
   docker run --rm \
     -v karakeep_data:/data \
     -v karakeep_meili:/meili_data \
     -v $(pwd):/backup \
     alpine tar -czvf /backup/karakeep_backup_$(date +%F).tar.gz /data /meili_data /backup/.env /backup/docker-compose.yml
   ```
   **Restore Command (Adjustments):**
   ```bash
   # 1. Extract configs to the host
   tar -xzvf karakeep_backup_<DATE>.tar.gz backup/.env backup/docker-compose.yml --strip-components=1

   # 2. Restore volumes via container
   docker run --rm \
     -v karakeep_data:/data \
     -v karakeep_meili:/meili_data \
     -v $(pwd):/backup \
     alpine tar -xzvf /backup/karakeep_backup_<DATE>.tar.gz /data /meili_data
   ```

## 5. Verification Method
- **Env Vars:** Verify by reading the rendered `karakeep.md` to ensure `NEXTAUTH_SECRET` is the primary bullet, and by reading `docker-compose.yml` to confirm it continues to map `NEXTAUTH_SECRET: ${KARAKEEP_NEXTAUTH_SECRET}`.
- **Backup Paths:** Verify by running the proposed `docker run` backup command and inspecting the contents of the generated `tar.gz` archive (`tar -tf karakeep_backup_*.tar.gz`) to confirm that `data/` and `meili_data/` exist at the top level of the archive instead of `var/lib/docker/volumes/...`.
