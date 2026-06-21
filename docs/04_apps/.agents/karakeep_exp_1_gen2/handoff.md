# 1. Observation
- `karakeep.md` Section 3 (Environment Variables) explains the secret key using the variable name `KARAKEEP_NEXTAUTH_SECRET`. 
- `docker-compose.yml` maps this `.env` variable to the application's actual environment variable using `NEXTAUTH_SECRET: ${KARAKEEP_NEXTAUTH_SECRET}`.
- `karakeep.md` Section 7 (Disaster Recovery) instructs the user to back up Docker volumes by archiving the raw host directories (`/var/lib/docker/volumes/karakeep_data` and `/var/lib/docker/volumes/karakeep_meili`).
- `docker-compose.yml` explicitly mounts the named volumes `karakeep_data` to the container path `/data` and `karakeep_meili` to `/meili_data`.

# 2. Logic Chain
1. The reviewer noted that the runbook used `KARAKEEP_NEXTAUTH_SECRET` instead of `NEXTAUTH_SECRET`. To fix this while keeping the runbook aligned with the compose file, the runbook should explain the variable as `NEXTAUTH_SECRET` (the internal app variable) and then explicitly mention that due to the compose file setup, it must be provided in the `.env` file as `KARAKEEP_NEXTAUTH_SECRET`.
2. The reviewer criticized the DR backup for using host-level paths (`/var/lib/docker/volumes/...`). Directly copying these directories can lead to permissions issues and ignores Docker's volume management. To address the reviewer's request to backup "explicitly `/data` and `/meili_data`", the procedure should use a temporary Docker container that mounts the volumes to those paths and archives them from within.

# 3. Caveats
- Since we are splitting away from host path backups, it is cleaner to backup the configuration (`.env` and `docker-compose.yml`) separately from the Docker volumes, rather than trying to construct a single complex `tar` command inside a temporary container. The fix strategy proposes two separate backup archives to keep the commands readable.

# 4. Conclusion
**Fix Strategy for `karakeep.md`:**

**1. Fix Env Vars Section:**
Update Section 3 to replace the heading `- **KARAKEEP_NEXTAUTH_SECRET**:` with `- **NEXTAUTH_SECRET**:`. Add clarifying text so the user knows how to set it:
*"- **NEXTAUTH_SECRET**: This is used to encrypt the NextAuth.js JWT tokens. Because of the `docker-compose.yml` mapping, you must define this in your `.env` file as `KARAKEEP_NEXTAUTH_SECRET`. Generate securely using: ..."*

**2. Fix DR Procedure (Backup & Restore):**
Update Section 7 to use a `docker run` command that explicitly targets `/data` and `/meili_data`. 

*Proposed Backup Commands:*
```bash
# Backup configuration files
tar -czvf karakeep_config_backup_$(date +%F).tar.gz .env docker-compose.yml

# Backup volume data explicitly
docker run --rm \
  -v karakeep_data:/data \
  -v karakeep_meili:/meili_data \
  -v $(pwd):/backup \
  alpine tar -czvf /backup/karakeep_volume_backup_$(date +%F).tar.gz /data /meili_data
```

*Proposed Restore Commands:*
```bash
# Restore configuration files
tar -xzvf karakeep_config_backup_*.tar.gz

# Restore volume data explicitly
docker run --rm \
  -v karakeep_data:/data \
  -v karakeep_meili:/meili_data \
  -v $(pwd):/backup \
  alpine tar -xzvf /backup/karakeep_volume_backup_*.tar.gz -C /
```

# 5. Verification Method
- **Review markdown diffs**: Check that `NEXTAUTH_SECRET` is the primary label used in the environment variable section.
- **Dry-run the backup**: Run the proposed `docker run ... alpine tar ...` command in a test environment to verify it correctly creates an archive containing `/data` and `/meili_data` without requiring root access to `/var/lib/docker/volumes`.
