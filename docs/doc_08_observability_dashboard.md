# Runbook 08: Observability, Dashboard, and Logs

This phase lets you quickly understand whether the lab is healthy.

Core components:

- **Homepage**: dashboard and links.
- **Uptime Kuma**: checks and alerts.
- **Beszel**: host/container metrics.
- **Dozzle**: live Docker logs.

---

## Phase A: Access Model

Recommended access:

| Service | Hostname | Access |
|---|---|---|
| Homepage | `dash.<domain>` | VPN or Authentik |
| Uptime Kuma | `status.<domain>` | VPN or Authentik |
| Beszel | `monitor.<domain>` | VPN or Authentik |
| Dozzle | `logs.<domain>` | Admin only via VPN or Authentik |

Dozzle reads the Docker socket. Treat it as an admin tool, not as a public app.

---

## Phase B: Deploy

First check [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md) and [PORTS_AND_DNS_MATRIX.md](PORTS_AND_DNS_MATRIX.md).

Template:

```text
stacks/observability/
  docker-compose.yml
  .env.example
  homepage/
```

Installation:

```bash
cd /opt/sovereign/stacks/observability
cp .env.example .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

---

## Phase C: NPM Proxy Hosts

Configure in Nginx Proxy Manager:

| Hostname | Forward port | Websockets |
|---|---:|---|
| `dash.<domain>` | `3002` | No |
| `status.<domain>` | `3001` | Yes |
| `monitor.<domain>` | `8090` | Yes |
| `logs.<domain>` | `8088` | Yes |

Then choose:

- access only from VPN, using internal DNS;
- or Authentik protection for each proxy host.

---

## Phase D: Minimum Uptime Kuma Monitors

Create monitors:

| Name | Type | Target |
|---|---|---|
| AdGuard DNS | DNS | `192.168.1.50`, record `example.com` |
| Headscale HTTPS | HTTP(s) | `https://vpn.<domain>` |
| Headscale-UI | HTTP(s) | `https://vpn.<domain>/web` |
| NPM UI | HTTP(s) | `http://192.168.1.50:81` or real IP |
| Authentik | HTTP(s) | `https://auth.<domain>` |
| Vaultwarden | HTTP(s) | `https://pwd.<domain>` |
| Immich | HTTP(s) | `https://foto.<domain>` |
| Nextcloud | HTTP(s) | `https://files.<domain>` |

Recommended alerts:

- Telegram;
- email;
- local webhook.

Rule: every service shown in Homepage should also have an Uptime Kuma monitor or a written reason for not having one.

---

## Phase E: Beszel

Beszel is useful for viewing:

- host CPU/RAM;
- disk;
- network;
- Docker containers;
- history and lightweight alerts.

Setup:

1. Open `http://SERVER_IP:8090`.
2. Create admin account.
3. Add the local system.
4. If using an agent, copy the token required by the UI.
5. Add CPU, RAM, disk, and temperature alerts.

---

## Phase F: Homepage

Homepage should be the single panel.

Recommended sections:

- Network: AdGuard, Headscale, NPM.
- Identity: Authentik.
- Monitoring: Uptime Kuma, Beszel, Dozzle.
- Apps: Vaultwarden, Immich, Nextcloud, Syncthing.
- Backup: PBS.
- Admin: Proxmox, Headscale-UI.

Do not put passwords or tokens in public YAML files. If you use widgets with API keys, keep them out of Git or use local `.env` files.

---

## Phase G: Logs

Dozzle turns live logs:

```bash
docker logs -f container_name
```

into:

```text
https://logs.<domain>
```

Rule: Dozzle is admin-only. Anyone who can read logs can see tokens, errors, paths, and sensitive details.

---

## Reference

- Homepage: <https://gethomepage.dev/>
- Uptime Kuma: <https://github.com/louislam/uptime-kuma>
- Beszel: <https://beszel.dev/>
- Dozzle: <https://dozzle.dev/>

---

**Previous:** [Runbook 07: Identity SSO Authentik](doc_07_identity_sso_authentik.md)
**Next:** [Runbook 09: Backup and DR](doc_09_backup_dr.md)
