# Immich Runbook Research & Rewrite Strategy

## 1. Observation
- SCOPE.md demands: Deep-dive environment variables, verified disaster recovery/rollback procedures based on official docs, and no missing logical steps from VM setup to monitoring.
- immich.md currently covers deployment broadly but omits critical elements:
  - VM prep steps (installing Docker, configuring storage mounts).
  - Environment variable deep-dive (missing variables like IMMICH_VERSION, TZ, DB_USERNAME).
  - Hardware Acceleration (Quicksync/NVENC devices: - /dev/dri:/dev/dri missing from server/ML containers).
  - Disaster Recovery is abbreviated. It needs specific start/stop sequences for the containers.

## 2. Logic Chain
- To meet the "A-Z deployment" and "VM setup to monitoring" criteria, the runbook must start with VM OS preparation, installing dependencies (Docker Compose), and preparing the storage mount.
- A "deep-dive" into environment variables requires enumerating every variable in the .env file, explaining its purpose, security implications, and how it impacts the containers.
- Immich's official docs stress version pinning and database consistency. A proper "rollback" procedure must document that users cannot just downgrade the Immich version if database migrations have run; they must restore the pg_dumpall dump and the old UPLOAD_LOCATION state.
- For disaster recovery, the exact order of operations is required to prevent data corruption: spin up Postgres, restore dump, then spin up the rest of the stack.

## 3. Caveats
- Due to CODE_ONLY mode, research is based on internalized official Immich documentation.
- The docker-compose.yml file in stacks/immich was not checked for current contents, but the Worker rewriting immich.md should ensure the runbook aligns with the standard multi-container Immich stack (server, machine-learning, redis, database).

## 4. Conclusion
The Worker should rewrite immich.md incorporating the following structure:
1. **VM & Host Setup**: VM specs, OS config, installing Docker, preparing /mnt/photos and /opt/sovereign/stacks/immich.
2. **Environment Variables (Deep-Dive)**: IMMICH_VERSION (pinning), UPLOAD_LOCATION, DB_PASSWORD/USER/NAME, TZ.
3. **Hardware Acceleration**: Adding /dev/dri to Compose for video transcoding and ML.
4. **Deployment**: Composing up, initial admin account creation.
5. **Reverse Proxy**: NPM setup with client_max_body_size 0; and websocket support.
6. **Monitoring**: UptimeKuma pointing to https://foto.internal/api/server-info/ping.
7. **Backup Procedure**: pg_dumpall for DB + filesystem backup of UPLOAD_LOCATION and compose files.
8. **Disaster Recovery & Rollback**:
   - Restore filesystem files.
   - Run docker compose up -d database.
   - Restore database: cat dump.sql | docker exec -i immich_postgres psql -U postgres -d immich.
   - Run docker compose up -d.

## 5. Verification Method
- **Review Output**: Ensure immich.md includes all sections listed in the Conclusion.
- **Validation**: Confirm the disaster recovery steps match the sequence: start database -> restore DB -> start stack. Ensure environment variables are fully explained.
