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
   newgrp docker
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
| `JELLYFIN_TAG` | **Docker Image Tag**. Keep the pinned tag from [Pinned Image Versions](../99_reference/PINNED_IMAGE_VERSIONS.md) unless you are performing a tested update. |
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
    environment:
      - TZ=${TZ}
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
   - **Domain Names**: `media.internal`
   - **Scheme**: `http`
   - **Forward IP**: `[Target_IP]`
   - **Forward Port**: `8096`
   - **Websockets Support**: enabled; Jellyfin uses it for playback progress sync and client communication.
   - **Block Common Exploits**: enabled.
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
source /opt/sovereign/stacks/jellyfin/.env
tar -czvf /backups/jellyfin_config_$(date +%F).tar.gz -C ${JELLYFIN_CONFIG_PATH} .
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

## 9. Rollback

If a Jellyfin update breaks playback or metadata:

1. Stop the stack.
2. Restore the previous `JELLYFIN_CONFIG_PATH` backup and `.env`.
3. Keep `JELLYFIN_MEDIA_PATH` mounted read-only and unchanged.
4. Start the previous image tag.
5. Verify login, library scan, one direct-play stream, and one transcode stream.

## 10. Official Sources

- Jellyfin container documentation: <https://jellyfin.org/docs/general/installation/container/>

---

**Previous:** [Home Assistant OS](home_assistant.md)

**Next:** [FreshRSS](freshrss.md)
