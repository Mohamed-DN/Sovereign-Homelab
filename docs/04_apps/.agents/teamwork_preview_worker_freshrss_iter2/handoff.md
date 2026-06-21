# FreshRSS Runbook Rewrite

## 1. Observation
- The Explorer's handoff analysis pointed out multiple integrity violations in the previous `docs/04_apps/freshrss.md` implementation, specifically:
  - Mentioning hardcoded `chown 33:33` and `mkdir` operations on the host, whereas the `stacks/freshrss/docker-compose.yml` actually uses named Docker volumes (`freshrss_data` and `freshrss_extensions`).
  - Instructing the user to create a new `docker-compose.yml` instead of utilizing the existing one and just configuring `.env` from `.env.example`.
  - Stating `CRON_MIN=1,31 * * * *`, while the actual docker-compose defines `CRON_MIN: "3,33"`.
  - Creating bind mounts (`./data` and `./extensions`) instead of named volumes in backup and stack instructions.
- The repository at `C:\home_server\Sovereign-Homelab\stacks\freshrss\docker-compose.yml` confirmed that the image parameterizes tags and ports via `.env`, and uses named volumes `freshrss_data` and `freshrss_extensions`.
- `docs/04_apps/freshrss.md` was overwritten using `write_to_file` with the corrected configuration logic.

## 2. Logic Chain
1. To ensure the documentation matched reality (and avoided Integrity Violations), I completely rewrote the "Environment & Pre-requisites" section, removing `mkdir` and host-side `chown 33:33` instructions.
2. The "Docker Compose & Environment Variables" section was modified to point the user to `cd /opt/sovereign/stacks/freshrss` and `cp .env.example .env` rather than creating a new config from scratch.
3. The environment variables explanation was aligned with what is actually configured in the codebase (`TZ`, `FRESHRSS_TAG`, `FRESHRSS_PORT`, `FRESHRSS_BASE_URL` and hardcoded `CRON_MIN: "3,33"`).
4. For fixing container volume permissions natively, I added the `docker exec -u root freshrss chown -R www-data:www-data /var/www/FreshRSS/data /var/www/FreshRSS/extensions` command inside the Troubleshooting section, explicitly calling out its safety mechanism (resolving the Alpine/Debian mismatch inside the container context).
5. The backup sequence was updated to run a `tar` backup against the named data volume using `--volumes-from freshrss` with an Alpine helper container to avoid assuming local filesystem paths for named volumes.

## 3. Caveats
- Assuming `freshrss` is the actual container name as deployed. Since the provided `docker-compose.yml` specifies `container_name: freshrss`, this is a safe assumption.
- The path `/opt/sovereign/stacks/freshrss` is a typical convention matching the previous runbook, used for illustrative deployment paths on the target host.

## 4. Conclusion
The runbook at `docs/04_apps/freshrss.md` has been fully rewritten. It correctly documents the pre-existing Docker Compose configuration, removing all hallucinated host-side setups, bind mounts, and incorrect cron syntax, cleanly addressing the Milestone 3 requirements and satisfying the Explorer's fix strategy.

## 5. Verification Method
1. `cat C:\home_server\Sovereign-Homelab\docs\04_apps\freshrss.md`
2. Ensure there are no instances of `33:33` or `1,31 * * * *`.
3. Check that the backup command does not rely on backing up an explicit `./data` host directory, but rather uses `--volumes-from` or explicitly mounts the volume.
4. Verify the `.env` process is documented over `nano docker-compose.yml`.
