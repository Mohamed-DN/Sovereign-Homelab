# Handoff: Paperless Runbook Rewrite

## 1. Observation
- The Forensic Audit Report indicated an INTEGRITY VIOLATION because the previous runbook documented a 5-container architecture (`webserver`, `db`, `broker`, `gotenberg`, `tika`) while the actual stack in `C:\home_server\Sovereign-Homelab\stacks\paperless\docker-compose.yml` only contains 3 services (`paperless`, `paperless-db`, `paperless-redis`).
- The `docker-compose.yml` explicitly defines the main app container as `paperless`, the database as `paperless-db`, and the broker as `paperless-redis`.
- Environment variable mappings in `docker-compose.yml` use these names (e.g., `PAPERLESS_REDIS=redis://paperless-redis:6379`, `PAPERLESS_DBHOST=paperless-db`).
- The Reviewer also required adding a Monitoring section and the exact `docker compose exec ... pg_dump ...` command for Level 2 database backup.
- `.env.example` shows variables like `PAPERLESS_DB`, `PAPERLESS_DB_USER`, `PAPERLESS_DB_PASSWORD`.

## 2. Logic Chain
1. The actual `docker-compose.yml` proves the previous documentation was copied from upstream and not tailored to the current environment. To fix this, the runbook must exactly match the existing 3-container configuration.
2. For creating a superuser, the command must be directed to the existing main container `paperless` instead of the non-existent `webserver`.
3. To fulfill the DR Reviewer requirement, the pg_dump command must target the `paperless-db` container. Because the database uses alpine, `sh -c` is appropriate, and we can leverage the pre-set `$POSTGRES_USER` and `$POSTGRES_DB` variables inside the container to avoid exposing credentials.
4. To fulfill the Monitoring Reviewer requirement, a section on monitoring via Uptime Kuma targeting the Paperless HTTP port must be added.

## 3. Caveats
- I did not test the pg_dump command directly as this is a read-only exploration, but standard postgres alpine images support this exact syntax.
- The monitoring approach suggested is basic HTTP endpoint checking via Uptime Kuma, which is standard for this architecture.

## 4. Conclusion
The worker agent must rewrite the `docs/04_apps/paperless.md` runbook adhering strictly to the real 3-container architecture.
- Remove all mentions of Tika and Gotenberg.
- Update service references: `webserver` -> `paperless`, `db` -> `paperless-db`, `broker` -> `paperless-redis`.
- Update the admin creation command to `docker compose exec paperless manage.py createsuperuser`.
- Add a explicit `pg_dump` backup command targeting `paperless-db` in the Disaster Recovery section.
- Add a new "Monitoring" section describing Uptime Kuma HTTP checks on the exposed port.

## 5. Verification Method
1. Inspect the resulting `docs/04_apps/paperless.md` to ensure no references to `gotenberg`, `tika`, or `webserver` exist.
2. Confirm the `createsuperuser` command targets the `paperless` container.
3. Confirm the presence of a "Monitoring" section.
4. Confirm the Level 2 backup command uses `docker compose exec paperless-db` and `pg_dump`.
