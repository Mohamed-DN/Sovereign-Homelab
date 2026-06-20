# Runbook 08: Observability, Dashboard e Log

Questa fase ti permette di capire rapidamente se il lab e sano.

Componenti core:

- **Homepage**: dashboard e link.
- **Uptime Kuma**: controlli e alert.
- **Beszel**: metriche host/container.
- **Dozzle**: log Docker live.

---

## Phase A: Modello di accesso

Accesso consigliato:

| Servizio | Hostname | Accesso |
|---|---|---|
| Homepage | `dash.<domain>` | VPN o Authentik |
| Uptime Kuma | `status.<domain>` | VPN o Authentik |
| Beszel | `monitor.<domain>` | VPN o Authentik |
| Dozzle | `logs.<domain>` | Solo admin via VPN o Authentik |

Dozzle legge il Docker socket. Trattalo come strumento admin, non come app pubblica.

---

## Phase B: Deploy

Template:

```text
stacks/observability/
  docker-compose.yml
  .env.example
  homepage/
```

Installazione:

```bash
cd /opt/sovereign/stacks/observability
cp .env.example .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

---

## Phase C: NPM proxy hosts

Configura in Nginx Proxy Manager:

| Hostname | Forward port | Websockets |
|---|---:|---|
| `dash.<domain>` | `3002` | No |
| `status.<domain>` | `3001` | Yes |
| `monitor.<domain>` | `8090` | Yes |
| `logs.<domain>` | `8088` | Yes |

Poi scegli:

- accesso solo da VPN, usando DNS interno;
- oppure protezione Authentik per ogni proxy host.

---

## Phase D: Uptime Kuma monitor minimi

Crea monitor:

| Nome | Tipo | Target |
|---|---|---|
| AdGuard DNS | DNS | `192.168.1.50`, record `example.com` |
| Headscale HTTPS | HTTP(s) | `https://vpn.<domain>` |
| Headscale-UI | HTTP(s) | `https://vpn.<domain>/web` |
| NPM UI | HTTP(s) | `http://192.168.1.50:81` o IP reale |
| Authentik | HTTP(s) | `https://auth.<domain>` |
| Vaultwarden | HTTP(s) | `https://pwd.<domain>` |
| Immich | HTTP(s) | `https://foto.<domain>` |
| Nextcloud | HTTP(s) | `https://files.<domain>` |

Alert consigliati:

- Telegram;
- email;
- webhook locale.

---

## Phase E: Beszel

Beszel e utile per vedere:

- CPU/RAM host;
- disco;
- rete;
- container Docker;
- storico e alert leggeri.

Setup:

1. Apri `http://SERVER_IP:8090`.
2. Crea account admin.
3. Aggiungi il sistema locale.
4. Se usi agent, copia il token richiesto dalla UI.
5. Aggiungi alert CPU, RAM, disk e temperature.

---

## Phase F: Homepage

Homepage deve essere il pannello unico.

Sezioni consigliate:

- Network: AdGuard, Headscale, NPM.
- Identity: Authentik.
- Monitoring: Uptime Kuma, Beszel, Dozzle.
- Apps: Vaultwarden, Immich, Nextcloud, Syncthing.
- Backup: PBS.
- Admin: Proxmox, Headscale-UI.

Non mettere password o token nei file YAML pubblici. Se usi widget con API key, tienili fuori da Git o usa file `.env` locali.

---

## Phase G: Log

Dozzle serve per log live:

```bash
docker logs -f container_name
```

diventa:

```text
https://logs.<domain>
```

Regola: Dozzle solo admin. Chi vede i log puo vedere token, errori, path e dettagli sensibili.

---

## Reference

- Homepage: <https://gethomepage.dev/>
- Uptime Kuma: <https://github.com/louislam/uptime-kuma>
- Beszel: <https://beszel.dev/>
- Dozzle: <https://dozzle.dev/>

---

**Previous:** [Runbook 07: Identity SSO Authentik](doc_07_identity_sso_authentik.md)
**Next:** [Runbook 09: Backup and DR](doc_09_backup_dr.md)
