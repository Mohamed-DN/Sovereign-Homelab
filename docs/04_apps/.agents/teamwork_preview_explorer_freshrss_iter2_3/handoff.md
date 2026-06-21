# Handoff Report: FreshRSS Runbook Integrity Fix

## Observation
- The generated runbook (`C:\home_server\Sovereign-Homelab\docs\04_apps\freshrss.md`) incorrectly uses bind mounts (`./data`, `./extensions`), hardcoded environment variables, and incorrect cron syntax (`CRON_MIN=1,31 * * * *`). It also incorrectly instructs the user to run `chown -R 33:33` on a manually created data directory.
- The actual codebase in `C:\home_server\Sovereign-Homelab\stacks\freshrss\docker-compose.yml` uses:
  - Named volumes: `freshrss_data` and `freshrss_extensions`.
  - Parameterized environment variables loaded from `.env`: `${FRESHRSS_TAG}`, `${TZ}`, `${FRESHRSS_BASE_URL}`, `${FRESHRSS_PORT}`.
  - A correct minute-interval for cron: `CRON_MIN: "3,33"`.
- The reviewer feedback specifically highlights that `CRON_MIN` must only contain the minute interval and that if Alpine is used, `www-data` maps to UID 82, not 33.

## Logic Chain
1. To align the runbook with the repository's codebase, the "Docker Compose & Environment Variables Deep Dive" section must reflect the actual `docker-compose.yml` and `.env.example` contents found in `stacks/freshrss`.
2. The "Environment & Pre-requisites" section must be rewritten to remove the manual `mkdir` and `chown 33:33` commands, as named volumes are used.
3. The UID mismatch issue needs to be explicitly noted. As recommended by the reviewer, the `docker exec` command (`docker exec -u root freshrss chown -R www-data:www-data /var/www/FreshRSS/data`) should be suggested as the primary method to fix permissions, explaining that Alpine uses UID 82 for `www-data`.
4. The backup instructions under "Level 2: File-level Backup" must be adapted for named volumes (e.g., using a temporary Alpine container to tar the volume, or backing up from `/var/lib/docker/volumes/freshrss_data/_data`) instead of a local `./data` bind mount.
5. `CRON_MIN` must be correctly explained as taking only the minute interval (e.g., `"3,33"`), not a full cron string.

## Caveats
- No caveats. The codebase dictates the exact configuration, and the reviewer's instructions are clear.

## Conclusion
The worker agent needs to edit `C:\home_server\Sovereign-Homelab\docs\04_apps\freshrss.md` to:
1. Replace the boilerplate `docker-compose.yml` block with the true contents of `stacks/freshrss/docker-compose.yml` and the parameterized variables (`.env.example`).
2. Explain the actual parameterized variables (`FRESHRSS_TAG`, `TZ`, `FRESHRSS_BASE_URL`, `FRESHRSS_PORT`).
3. Explain `CRON_MIN` syntax correctly (only the minutes, e.g., "3,33").
4. Remove the manual `mkdir` and `chown -R 33:33` from pre-requisites, as named volumes are used.
5. Add a note about the Alpine `www-data` UID 82 difference and recommend the `docker exec chown` method for permission fixes.
6. Update the file-level backup section to support backing up a Docker named volume instead of a bind mount directory.

## Verification Method
1. Read `C:\home_server\Sovereign-Homelab\docs\04_apps\freshrss.md` after edits to ensure no `bind mounts` or `1,31 * * * *` exist.
2. Verify that the file-level backup command correctly refers to named volumes.
3. Ensure the text explicitly mentions Alpine's `www-data` UID 82.
