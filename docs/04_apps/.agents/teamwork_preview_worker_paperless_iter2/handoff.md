# Paperless Worker Handoff

## 1. Observation
- Read the Explorer's handoff report at `C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\teamwork_preview_explorer_paperless_iter2_3\handoff.md`.
- Read the existing `C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md`.
- Replaced the contents of `paperless.md` to perfectly match the requested changes:
  - Removed all references to `tika` and `gotenberg`.
  - Replaced container aliases (`webserver`, `db`, `broker`) with their actual names (`paperless`, `paperless-db`, `paperless-redis`).
  - Added a "Monitoring" section that checks `http://<docker-host-ip>:8010` via Uptime Kuma.
  - Provided the explicit `pg_dump` command: `docker compose exec paperless-db pg_dump -U paperless paperless > paperless_db_backup.sql`.
  - Removed the `webserver`, `broker`, `db` from all parts of the document, including troubleshooting commands.

## 2. Logic Chain
- To accurately reflect the true stack, the runbook must drop generic component mentions and only outline what is actively running.
- By strictly adhering to the findings in `docker-compose.yml` (no `tika` or `gotenberg`, standard 3-tier layout), the runbook is now factually correct.
- Monitoring is provided via the exposed web interface, making it easy to establish HTTP health checks.
- Backing up `paperless-db` using `pg_dump -U paperless paperless` ensures reliable database exports in case of disaster, exactly as requested by the audit.

## 3. Caveats
- No caveats. The file was completely overwritten to correct all integration/layout issues found in previous iterations.

## 4. Conclusion
- The Paperless runbook has been fully rewritten according to the Explorer's analysis and the Milestone 2 integrity mandate.

## 5. Verification Method
- Execute `cat C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md` and verify that the file reflects the 3-container stack (`paperless`, `paperless-db`, `paperless-redis`).
- Check that there are zero results for `grep tika C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md` or `grep gotenberg C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md`.
- Confirm the new Monitoring section exists.
