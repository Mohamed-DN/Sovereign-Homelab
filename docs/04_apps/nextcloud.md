# Nextcloud AIO

### Purpose

Nextcloud AIO provides a full cloud suite. Use it only if you need Nextcloud features beyond simple file sync.

### Target and Sizing

| Field | Value |
|---|---|
| Target | VM 120 `nextcloud-aio` |
| CPU | 4 vCPU |
| RAM | 8-12 GB |
| OS disk | 120 GB |
| Data mount | dedicated if used seriously |
| Compose | official Nextcloud AIO mastercontainer |

### Install

```bash
mkdir -p /opt/nextcloud-aio
cd /opt/nextcloud-aio
nano compose.yml
docker compose config
docker compose up -d
```

Required reverse proxy model:

| Setting | Value |
|---|---|
| Public/internal app hostname | `files.internal` |
| Apache port | `11000` |
| AIO admin UI | `VM120_IP:8086`, VPN/admin only |
| NPM proxy | `files.internal -> http://VM120_IP:11000` |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `files.internal` |
| NPM upstream | `http://VM120_IP:11000` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma | `app-nextcloud`, HTTP(s), `https://files.internal` |
| Access | VPN-first |

### Backup

Use:

- Nextcloud AIO backup;
- PBS VM backup;
- separate data mount backup if large.

### Restore Drill

1. Restore AIO backup into a test VM.
2. Verify admin login.
3. Verify file listing and file download.
4. Verify calendar/contact if used.

### Rollback and Troubleshooting

- If AIO update fails, use the AIO backup first.
- If proxy fails, verify NPM forwards to Apache port `11000`, not the AIO UI port.

Source: <https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md>
