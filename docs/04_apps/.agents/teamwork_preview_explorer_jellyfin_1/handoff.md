# Jellyfin Runbook Handoff Report

## 1. Observation
- The current runbook (`C:\home_server\Sovereign-Homelab\docs\04_apps\jellyfin.md`) is only 51 lines long and lacks depth on VM setup, environment variables, hardware transcoding (like `/dev/dri` passing), and complete disaster recovery processes.
- The `docker-compose.yml` uses:
  - `jellyfin/jellyfin:${JELLYFIN_TAG}`
  - Ports: `${JELLYFIN_PORT}:8096`
  - Volumes: `JELLYFIN_CONFIG_PATH:/config`, `JELLYFIN_CACHE_PATH:/cache`, `JELLYFIN_MEDIA_PATH:/media:ro`
- The `.env.example` defines these variables using local paths (e.g., `./data/jellyfin/config`).

## 2. Logic Chain & Plan for the Worker
To meet the objective of an exhaustive A-Z deployment, the new `jellyfin.md` must cover:
1. **VM Setup & Prerequisites**: OS sizing, installing Docker, and setting up dedicated storage/NFS mounts for media.
2. **Hardware Transcoding**: Passing `/dev/dri` to Docker containers (Intel QuickSync or AMD VAAPI) or using Nvidia runtime.
3. **Deep-Dive on Environment Variables**: Explaining what `JELLYFIN_TAG`, `JELLYFIN_CONFIG_PATH`, etc., are, and adding important ones like `TZ`.
4. **Deployment & Configuration**: Step-by-step docker-compose setup, folder structure, `.env` file population.
5. **Reverse Proxy (NPM)**: Configuration for NPM, websockets, and SSL, pointing to the container.
6. **Monitoring**: Adding Jellyfin to Homepage.dev and Uptime Kuma with specific configuration.
7. **Backup & Disaster Recovery (DR)**: Explaining how to backup `/config`, ignore `/cache`, and handle media backups, plus the step-by-step restore process.
8. **Troubleshooting**: Fixing permission issues, transcoding failures, and network errors.

**Implementation Plan for Worker:**
1. Overwrite `C:\home_server\Sovereign-Homelab\docs\04_apps\jellyfin.md` with the comprehensive Markdown content provided below.
2. (Optional but recommended) Update `C:\home_server\Sovereign-Homelab\stacks\jellyfin\docker-compose.yml` to include `devices: - /dev/dri:/dev/dri` for hardware transcoding support, so the runbook matches the compose file.
3. Verify formatting.

## 3. Caveats
- I did not modify any files; this is a read-only investigation.
- The actual media storage backend (NFS, SMB, local) is assumed to be mounted at the OS level before running Docker.
- The user is running a generic "VM 150" or "LXC 102". Proxmox hypervisor-level GPU passthrough instructions are mentioned at a high level, focusing primarily on the Docker-level `/dev/dri` mapping.

## 4. Conclusion
The current Jellyfin runbook is insufficient. An exhaustive rewrite is required to ensure robust operations, backup, and performance (transcoding). The draft below contains all the necessary text for the new runbook.

## 5. Verification Method
- Inspect the new `jellyfin.md` using `view_file` to ensure it contains A-Z steps, env var deep dives, and DR processes.
- Run `docker compose --env-file .env.example config` in `stacks/jellyfin` to ensure the YAML is syntactically valid after any updates to `docker-compose.yml`.

---

# Proposed Content for `C:\home_server\Sovereign-Homelab\docs\04_apps\jellyfin.md`

```markdown
# Jellyfin Deployment & Operations Runbook

## 1. Overview & Sizing
Jellyfin is a Free Software Media System that puts you in control of managing and streaming your media. There are no strings attached, no premium licenses or features, and no hidden agendas.

- **Target Node**: VM 150 (`jellyfin`) or LXC 102
- **CPU**: 4 vCPU minimum (Heavy transcoding may require more or a dedicated GPU)
- **RAM**: 8 GB minimum
- **Storage**: 
  - **OS Drive**: 32 GB for OS and Docker
  - **App Data**: 50+ GB for `/config` and `/cache` (Metadata and images take up significant space)
  - **Media Storage**: Terabytes, typically mounted via NFS/SMB or passed through as a secondary virtual disk.

## 2. VM Setup & Prerequisites

1. **Provision OS**: Install Ubuntu Server 22.04/24.04 or Debian 12.
2. **System Updates**: `sudo apt update && sudo apt upgrade -y`
3. **Install Docker**:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```
4. **Mount Media Storage**:
   If using NFS from a NAS, edit `/etc/fstab`:
   ```text
   192.168.1.10:/mnt/tank/media /mnt/media nfs defaults,timeo=900,retrans=5,_netdev 0 0
   ```
   Run `sudo mkdir -p /mnt/media && sudo mount -a`.
5. **GPU Passthrough (Hardware Transcoding)**:
   - For Proxmox LXC: Map `/dev/dri` in the `.conf` file.
   - For Proxmox VM: Add a PCI Device in the VM Hardware settings (e.g., Intel IGD or Nvidia GPU).
   - Verify access: `ls -l /dev/dri`. You should see `renderD128`.

## 3. Environment Variables Deep-Dive
Within the `/opt/sovereign/stacks/jellyfin` directory, create your `.env` file from `.env.example`. 

| Variable | Description |
|----------|-------------|
| `TZ` | **Timezone** (e.g., `Europe/Rome`). Ensures accurate log timestamps and scheduled tasks (like library scans). |
| `JELLYFIN_TAG` | **Docker Image Tag**. Use `latest` for stable rolling releases, or pin to a specific version like `10.8.13` for stability. |
| `JELLYFIN_PORT` | **Host Port Binding**. The port exposed on your host (default `8096`). Change only if there are host port conflicts. |
| `JELLYFIN_CONFIG_PATH` | **Configuration Path**. Persistent storage for users, database, and metadata. *Crucial for backups.* |
| `JELLYFIN_CACHE_PATH` | **Cache Path**. Temporary transcoding chunks and resized images. *Should NOT be backed up.* Can be mapped to a fast SSD or `tmpfs`. |
| `JELLYFIN_MEDIA_PATH` | **Media Directory**. The base directory containing your Movies, TV Shows, etc. Passed as `:ro` (Read-Only) to prevent accidental deletions from the UI. |

## 4. Deployment Configuration

### `docker-compose.yml`
Ensure your `docker-compose.yml` includes the following (note the `devices` mapping for transcoding):

```yaml
name: jellyfin

services:
  jellyfin:
    image: jellyfin/jellyfin:${JELLYFIN_TAG}
    container_name: jellyfin
    restart: unless-stopped
    ports:
      - "${JELLYFIN_PORT}:8096"
    volumes:
      - ${JELLYFIN_CONFIG_PATH}:/config
      - ${JELLYFIN_CACHE_PATH}:/cache
      - ${JELLYFIN_MEDIA_PATH}:/media:ro
    devices:
      - /dev/dri:/dev/dri # Required for Intel QuickSync / AMD VAAPI transcoding
```

### Execution
```bash
cd /opt/sovereign/stacks/jellyfin
cp .env.example .env
nano .env # Adjust paths and timezone
docker compose up -d
docker compose logs -f
```

## 5. Configuration & Nginx Proxy Manager (NPM)

1. Navigate to `http://[Target_IP]:8096` and complete the initial setup wizard.
2. In the Jellyfin UI, go to **Dashboard > Playback** and enable **Hardware Acceleration** (e.g., Video Acceleration API (VAAPI) or Intel QuickSync).
3. Log into NPM (`http://[NPM_IP]:81`) and create a Proxy Host:
   - **Domain Names**: `media.internal` (or your public domain)
   - **Scheme**: `http`
   - **Forward IP**: `[Target_IP]`
   - **Forward Port**: `8096`
   - **Websockets Support**: ✅ Enabled (Crucial for playback progress sync and client communication)
   - **Block Common Exploits**: ✅ Enabled
   - **SSL**: Select your certificate, enable Force SSL, HTTP/2, and HSTS.

## 6. Dashboard & Monitoring

### Homepage.dev
Add Jellyfin to your `services.yaml` to show active streams and server status:
```yaml
- Jellyfin:
    href: https://media.internal
    icon: jellyfin.png
    widget:
      type: jellyfin
      url: http://[Target_IP]:8096
      key: YOUR_API_KEY # Generate in Jellyfin Dashboard > API Keys
```

### Uptime Kuma
- Add a new **HTTP(s)** monitor.
- **URL**: `https://media.internal/health` (or the main URL).
- **Accepted Status Codes**: 200-299.

## 7. Disaster Recovery & Backup Procedures

### Backup Strategy
- **DO BACKUP**: The folder defined in `JELLYFIN_CONFIG_PATH`. This contains your SQL database, user watch histories, and custom metadata.
- **DO NOT BACKUP**: The folder defined in `JELLYFIN_CACHE_PATH`. It is volatile and wastes backup space.
- **Media**: Follow your standard NAS/Storage 3-2-1 backup strategy for the actual video files.

**Sample Cron Backup Script (`/opt/sovereign/scripts/backup_jellyfin.sh`)**:
```bash
#!/bin/bash
tar -czvf /backups/jellyfin_config_$(date +%F).tar.gz -C /opt/sovereign/stacks/jellyfin/data/config .
```

### Restore Drill (A-Z)
1. Provision a fresh VM or LXC and install Docker.
2. Re-create the folder structure: `mkdir -p /opt/sovereign/stacks/jellyfin/data/config`
3. Extract the backup: `tar -xzvf /backups/jellyfin_config_YYYY-MM-DD.tar.gz -C /opt/sovereign/stacks/jellyfin/data/config`
4. Copy over your `docker-compose.yml` and `.env` files.
5. Remount your `/mnt/media` drive.
6. Run `docker compose up -d`. Jellyfin will start with all users, passwords, and watch progress intact.

## 8. Troubleshooting

| Issue | Resolution |
|-------|------------|
| **Endless Buffering / Transcoding Fails** | Check `/dev/dri` permissions inside the container. Ensure the Jellyfin user has access to the `render` group. Temporarily disable Hardware Transcoding in Playback settings to confirm if the GPU is the culprit. |
| **Media Files Not Showing** | Check permissions of `JELLYFIN_MEDIA_PATH`. The Jellyfin container runs as root by default unless specified otherwise. Ensure the host path is readable by Docker. Verify the NFS mount is active on the host. |
| **Clients Unsyncing / Not Pausing** | Verify that **WebSockets** are enabled in Nginx Proxy Manager. Jellyfin requires WebSockets for real-time client-server communication. |
| **Out of Space Errors** | Check your Cache directory size. If `/cache` is on a small root partition, transcoding large 4K files can fill it up. Move the cache to a larger disk. |
```
