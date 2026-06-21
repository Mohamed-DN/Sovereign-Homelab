# Handoff Report: Jellyfin Runbook Rewrite (Iteration 2)

## 1. Observation
- **File:** `C:\home_server\Sovereign-Homelab\stacks\jellyfin\docker-compose.yml`
  - *Observation:* The file contains the `jellyfin` service definition (lines 4-15) but lacks an `environment:` block, specifically missing the `TZ` variable.
- **File:** `C:\home_server\Sovereign-Homelab\docs\04_apps\jellyfin.md`
  - *Observation 1:* Lines 52-68 provide a snippet for `docker-compose.yml`, which mirrors the actual file and also lacks the `environment:` block.
  - *Observation 2:* Lines 19-23 contain bash commands for installing Docker and adding the user to the `docker` group, but omit the `newgrp docker` command to apply the group change immediately.
  - *Observation 3:* Lines 118-122 show a sample cron backup script that hardcodes the path `/opt/sovereign/stacks/jellyfin/data/config` rather than using the `.env` variable `${JELLYFIN_CONFIG_PATH}`.

## 2. Logic Chain
1. To address the Critical issue, the `environment:` block with `- TZ=${TZ}` must be injected into the `jellyfin` service inside `C:\home_server\Sovereign-Homelab\stacks\jellyfin\docker-compose.yml`. The same injection must be performed on the markdown snippet in `jellyfin.md` to keep documentation and code in sync.
2. To address the Major issue, `newgrp docker` needs to be appended to the bash block in `jellyfin.md` right after `sudo usermod -aG docker $USER`.
3. To address the Minor issue, the backup script in `jellyfin.md` needs to be updated. It should source the `.env` file first (`source /opt/sovereign/stacks/jellyfin/.env`) and use the variable in the `tar` command (`tar -czvf /backups/jellyfin_config_$(date +%F).tar.gz -C ${JELLYFIN_CONFIG_PATH} .`).

## 3. Caveats
- Assuming that `/opt/sovereign/stacks/jellyfin/.env` is the correct, definitive path for the environment variables in the context of the backup script, as `cd /opt/sovereign/stacks/jellyfin` is used in the Execution section.
- No other caveats.

## 4. Conclusion
The issues identified are present in the files and require direct string replacement. The worker agent must apply these precise changes to resolve the issues.

**Proposed Changes for the Worker Agent:**

**File 1: `C:\home_server\Sovereign-Homelab\stacks\jellyfin\docker-compose.yml`**
Insert `environment:` under the `jellyfin` service.
*Replacement chunk:*
```yaml
    container_name: jellyfin
    restart: unless-stopped
    environment:
      - TZ=${TZ}
    ports:
```

**File 2: `C:\home_server\Sovereign-Homelab\docs\04_apps\jellyfin.md`**

*Edit 1 (Add `newgrp docker`):*
```markdown
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```
```

*Edit 2 (Add `environment:` to snippet):*
```markdown
  jellyfin:
    image: jellyfin/jellyfin:${JELLYFIN_TAG}
    container_name: jellyfin
    restart: unless-stopped
    environment:
      - TZ=${TZ}
    ports:
```

*Edit 3 (Update backup script):*
```markdown
**Sample Cron Backup Script (`/opt/sovereign/scripts/backup_jellyfin.sh`)**:
```bash
#!/bin/bash
source /opt/sovereign/stacks/jellyfin/.env
tar -czvf /backups/jellyfin_config_$(date +%F).tar.gz -C ${JELLYFIN_CONFIG_PATH} .
```
```

## 5. Verification Method
- Execute `cat C:\home_server\Sovereign-Homelab\stacks\jellyfin\docker-compose.yml` to verify the presence of the `environment:` block with `- TZ=${TZ}`.
- Execute `cat C:\home_server\Sovereign-Homelab\docs\04_apps\jellyfin.md` and check:
  1. `newgrp docker` is present.
  2. The `environment` block is present in the docker-compose YAML snippet.
  3. The backup script includes `source /opt/sovereign/stacks/jellyfin/.env` and uses `${JELLYFIN_CONFIG_PATH}`.
