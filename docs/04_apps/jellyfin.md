# Jellyfin

### Purpose

Jellyfin serves private media. It is not as critical as photos/passwords, but metadata and watched state are worth protecting.

### Target and Sizing

| Field | Value |
|---|---|
| Target | VM 150 `jellyfin` or LXC 102 profile for light use |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | media mount plus config/cache |
| Profile | `jellyfin` |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile jellyfin config
docker compose --env-file .env --profile jellyfin up -d
```

Set:

| Variable | Value |
|---|---|
| `JELLYFIN_CONFIG_PATH` | persistent config path |
| `JELLYFIN_CACHE_PATH` | cache path |
| `JELLYFIN_MEDIA_PATH` | read-only media path |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `media.internal` |
| NPM upstream | `http://VM150_IP:8096` or `http://LXC102_IP:8096` |
| WebSocket | yes |
| Homepage group | Apps |
| Uptime Kuma | `app-jellyfin`, HTTP(s), `https://media.internal` |
| Access | VPN/Auth |

### Backup

Back up:

- Jellyfin config;
- metadata if you care about watched state;
- media library source separately.

### Restore Drill

1. Restore config to test container/VM.
2. Mount a small test media folder.
3. Verify library scan and playback.

### Rollback and Troubleshooting

- If playback fails, test direct upstream before NPM.
- Add GPU passthrough only if transcoding is required.

Source: <https://jellyfin.org/docs/general/installation/container/>
