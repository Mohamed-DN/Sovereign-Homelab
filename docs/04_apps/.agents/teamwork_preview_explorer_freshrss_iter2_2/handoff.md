# FreshRSS Runbook Analysis

## 1. Observation
- **docker-compose.yml**:
  The actual file at `stacks/freshrss/docker-compose.yml` uses:
  - Named volumes: `freshrss_data` and `freshrss_extensions`.
  - Parameterized variables: `${FRESHRSS_TAG}`, `${TZ}`, `${FRESHRSS_BASE_URL}`, `${FRESHRSS_PORT}`.
  - Hardcoded `CRON_MIN: "3,33"`.
- **.env.example**:
  The file at `stacks/freshrss/.env.example` provides default values:
  - `TZ=Europe/Rome`
  - `FRESHRSS_TAG=latest`
  - `FRESHRSS_PORT=8087`
  - `FRESHRSS_BASE_URL=https://rss.internal`
- **Reviewer Feedback**:
  - `CRON_MIN` must only contain the minute interval (e.g., `"3,33"`), not a full cron expression. The current codebase is already correct (`"3,33"`).
  - UID for `www-data` in Alpine is 82, not 33. The reviewer suggested using the `docker exec` chown command as a robust primary setup step instead of host-side `chown 33:33`.
- **Current Runbook (`docs/04_apps/freshrss.md`)**:
  - Contains hallucinated bind mounts (`./data` and `./extensions`).
  - Instructs manual directory creation and `chown -R 33:33` on the host.
  - Instructs the user to create a new `docker-compose.yml`.
  - Contains invalid `CRON_MIN=1,31 * * * *`.

## 2. Logic Chain
1. Since the project uses named volumes (`freshrss_data`), instructing users to manually create directories and run `chown -R 33:33` on the host is both unnecessary and incorrect.
2. Because the stack uses an `.env` file for parametrization, the deployment steps should instruct the user to copy `.env.example` to `.env` and edit it, rather than writing a new `docker-compose.yml` from scratch.
3. The codebase already sets `CRON_MIN: "3,33"`. The runbook only needs to document this correct syntax and explain that it runs the background feed refresh at minutes 3 and 33.
4. If permissions need to be corrected, running `docker exec -u root freshrss chown -R www-data:www-data /var/www/FreshRSS/data /var/www/FreshRSS/extensions` is safer because it automatically resolves the `www-data` UID correctly, avoiding the Alpine (82) vs. Debian (33) discrepancy.

## 3. Caveats
- I did not test the actual deployment of the FreshRSS container since I only have read access. I am relying on the existing files and the reviewer feedback.
- If the user uses a non-Alpine image tag, the UID will be different, which further reinforces using `docker exec` inside the container for permission fixes rather than hardcoded UIDs on the host.

## 4. Conclusion
The runbook at `docs/04_apps/freshrss.md` must be completely rewritten to align with the actual `stacks/freshrss` codebase. The Worker should:
- Remove instructions to `mkdir` and `chown 33:33` host directories.
- Remove instructions to create a new `docker-compose.yml`.
- Add instructions to navigate to `stacks/freshrss`, copy `.env.example` to `.env`, and customize the variables.
- Explain the environment variables based on `.env.example` (TZ, FRESHRSS_TAG, FRESHRSS_PORT, FRESHRSS_BASE_URL) and document the hardcoded `CRON_MIN: "3,33"`.
- If permission setup/fixes are mentioned, suggest using `docker exec -u root freshrss chown -R www-data:www-data /var/www/FreshRSS/data /var/www/FreshRSS/extensions` so it naturally handles the Alpine UID (82) vs Debian UID (33) mismatch.
- Update the backup section to reflect named volume paths instead of bind mounts.

## 5. Verification Method
- **Verify**: The updated `docs/04_apps/freshrss.md` mentions `.env` configuration instead of writing `docker-compose.yml`.
- **Verify**: The updated runbook does not contain `33:33` or `1,31 * * * *`.
- **Verify**: The updated runbook instructs to back up Docker named volumes (or uses `docker exec` tar commands against `/var/www/FreshRSS/data`) rather than `./data`.
