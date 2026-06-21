# FreshRSS Runbook Integrity Analysis

## Context
The previous iteration of the FreshRSS runbook failed the Forensic Audit due to an INTEGRITY VIOLATION. The agent hallucinated a generic docker-compose.yml setup instead of documenting the actual codebase. This report details the actual implementation.

## Actual Codebase Findings
**Path**: C:\home_server\Sovereign-Homelab\stacks\freshrss\docker-compose.yml
**Path**: C:\home_server\Sovereign-Homelab\stacks\freshrss\.env.example

### 1. File Structure and Deployment
The codebase already contains docker-compose.yml and .env.example. The runbook should **not** instruct the user to create the file via 
ano docker-compose.yml with pasted content. Instead, it should instruct them to:
`ash
cd /opt/sovereign/stacks/freshrss
cp .env.example .env
nano .env
docker compose up -d
`

### 2. Environment Variables
The actual docker-compose.yml uses parameterized variables from .env:
- ${TZ}
- ${FRESHRSS_TAG}
- ${FRESHRSS_PORT}
- ${FRESHRSS_BASE_URL}

The only hardcoded variable in the Compose file is CRON_MIN: "3,33".
**Note on CRON_MIN**: The previous runbook used CRON_MIN=1,31 * * * *, which is invalid syntax. The actual codebase uses "3,33", which correctly specifies only the minute intervals.

### 3. Volumes & Permissions
The previous runbook instructed the user to manually mkdir -p and chown -R 33:33 bind-mounted directories (./data and ./extensions).
However, the actual code uses **Docker named volumes**:
- reshrss_data:/var/www/FreshRSS/data
- reshrss_extensions:/var/www/FreshRSS/extensions
Since Docker manages named volumes, manual directory creation and host-level chown are unnecessary and misleading. If there's a need to fix permissions, the runbook should recommend using docker exec (e.g., docker exec -u root freshrss chown -R www-data:www-data /var/www/FreshRSS/data). Also, as noted by the reviewer, on Alpine images, www-data is UID 82, not 33, making the previous chown 33:33 potentially incorrect.

## Recommended Strategy for the Worker
1. **Remove Boilerplate Creation**: Delete the section instructing the user to paste the docker-compose.yml contents.
2. **Document Actual Variables**: Detail the variables found in .env.example (TZ, FRESHRSS_TAG, FRESHRSS_PORT, FRESHRSS_BASE_URL) and the hardcoded CRON_MIN. Explain that CRON_MIN expects only minute values (like 3,33), not a full cron string.
3. **Update Volumes**: Mention the use of named volumes (reshrss_data, reshrss_extensions). Remove manual directory creation commands.
4. **Update Troubleshooting/Permissions**: Replace host-level chown 33:33 commands with docker exec -u root freshrss chown -R www-data:www-data /var/www/FreshRSS/data. Mention that www-data on Alpine is UID 82 if manual checks are needed.
