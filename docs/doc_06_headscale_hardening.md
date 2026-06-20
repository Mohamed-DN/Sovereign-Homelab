# Runbook 06: Headscale Hardening

Questo runbook porta la VPN da "funziona" a "governata": policy, tag, route approval, exit node controllato, audit e rollback.

Il risultato atteso:

- LXC 100 resta il subnet router per `192.168.1.0/24`.
- Proxmox P710 resta l'exit node per `0.0.0.0/0`.
- Le route sono approvate da policy o da comando esplicito.
- I device utente non hanno accesso illimitato alle UI admin.
- Ogni cambio policy puo essere testato e ripristinato.

---

## Phase A: Architettura della policy

Headscale usa un policy file in formato HuJSON/JSON. Il file viene referenziato in `config.yaml` con `policy.path`.

Modello logico:

| Ruolo | Esempio | Identita policy |
|---|---|---|
| Admin personale | laptop admin, workstation | `group:admin` |
| Dispositivi personali | smartphone, laptop | `group:users` |
| Subnet router | LXC 100 | `tag:router` |
| Exit node | Proxmox P710 | `tag:exit` |
| Servizi web | app dietro NPM | `tag:service` |
| UI amministrative | Headscale-UI, Uptime Kuma, Beszel | `tag:admin` |

Regole di sicurezza:

- Senza grant esplicito, il traffico non deve passare.
- Solo admin puo taggare router, exit node e servizi.
- Solo nodi con `tag:router` possono auto-approvare `192.168.1.0/24`.
- Solo nodi con `tag:exit` possono auto-approvare exit node.
- L'accesso internet via exit node passa da `autogroup:internet` e `via`.

---

## Phase B: Preparare il policy file

Entra in LXC 100:

```bash
cd /opt/core-network
mkdir -p /opt/core-network/headscale/policy
```

Aggiorna il volume del servizio Headscale in `docker-compose.yml`:

```yaml
services:
  headscale:
    volumes:
      - ./headscale/config:/etc/headscale
      - ./headscale/data:/var/lib/headscale
      - ./headscale/policy:/etc/headscale/policy
```

Nel file `/opt/core-network/headscale/config/config.yaml`, aggiungi o correggi:

```yaml
policy:
  path: /etc/headscale/policy/policy.hujson
```

Nota importante: non usare `policy.mode` se la tua versione Headscale non lo prevede. La documentazione stabile richiede `policy.path`.

---

## Phase C: Creare policy iniziale

Crea `/opt/core-network/headscale/policy/policy.hujson`.

Sostituisci `mohamed@` con l'utente reale visto da:

```bash
docker exec headscale headscale users list
```

Policy iniziale:

```json
{
  "groups": {
    "group:admin": ["mohamed@"],
    "group:users": ["mohamed@"]
  },

  "tagOwners": {
    "tag:router": ["group:admin"],
    "tag:exit": ["group:admin"],
    "tag:service": ["group:admin"],
    "tag:admin": ["group:admin"]
  },

  "autoApprovers": {
    "routes": {
      "192.168.1.0/24": ["tag:router"]
    },
    "exitNode": ["tag:exit"]
  },

  "grants": [
    {
      "src": ["group:admin"],
      "dst": ["*"],
      "ip": ["*"]
    },
    {
      "src": ["group:users"],
      "dst": ["192.168.1.50/32"],
      "ip": ["udp:53", "tcp:53", "tcp:80", "tcp:443", "tcp:3000", "icmp:*"]
    },
    {
      "src": ["group:users"],
      "dst": ["tag:service"],
      "ip": ["tcp:80", "tcp:443"]
    },
    {
      "src": ["group:users"],
      "dst": ["autogroup:internet"],
      "via": ["tag:exit"],
      "ip": ["*"]
    }
  ]
}
```

Spiegazione:

- `group:admin` ha accesso completo per gestione.
- `group:users` puo usare DNS/HTTPS verso AdGuard e servizi.
- `autogroup:internet` consente full tunnel solo attraverso nodi `tag:exit`.
- `autoApprovers.routes` auto-approva solo `192.168.1.0/24` da nodi `tag:router`.
- `autoApprovers.exitNode` auto-approva exit node taggati `tag:exit`.

---

## Phase D: Testare prima di riavviare

Esegui un backup rapido dei file:

```bash
cp /opt/core-network/headscale/config/config.yaml /opt/core-network/headscale/config/config.yaml.bak.$(date +%F-%H%M)
cp /opt/core-network/headscale/policy/policy.hujson /opt/core-network/headscale/policy/policy.hujson.bak.$(date +%F-%H%M)
```

Valida la configurazione:

```bash
docker exec headscale headscale configtest
```

Se il container non vede ancora il volume policy, riavvia solo dopo aver aggiornato `docker-compose.yml`:

```bash
docker compose up -d headscale
docker exec headscale headscale configtest
docker logs --tail=100 headscale
```

Non proseguire se `configtest` fallisce.

---

## Phase E: Taggare LXC 100 come subnet router

Sul client Tailscale installato dentro LXC 100:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --advertise-tags tag:router \
  --advertise-routes=192.168.1.0/24 \
  --accept-dns=false
```

Se e gia registrato:

```bash
tailscale set --advertise-tags tag:router
tailscale set --advertise-routes=192.168.1.0/24
tailscale set --accept-dns=false
```

Verifica:

```bash
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
```

La route `192.168.1.0/24` deve apparire come approvata e servita. Se non succede:

```bash
docker exec headscale headscale nodes approve-routes --identifier LXC100_NODE_ID --routes 192.168.1.0/24
```

---

## Phase F: Taggare Proxmox P710 come exit node

Sul Proxmox host:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --advertise-tags tag:exit \
  --advertise-exit-node \
  --hostname proxmox-p710 \
  --accept-dns=false
```

Se e gia registrato:

```bash
tailscale set --advertise-tags tag:exit
tailscale set --advertise-exit-node
tailscale set --accept-dns=false
```

Verifica da LXC 100:

```bash
docker exec headscale headscale nodes list-routes
```

Un exit node annuncia `0.0.0.0/0` e, se IPv6 e attivo, `::/0`. Se non viene auto-approvato:

```bash
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 0.0.0.0/0
```

---

## Phase G: Test da client reale

Da telefono su 4G/5G:

1. Connetti il client alla tailnet.
2. Abilita "Use exit node" e scegli `proxmox-p710`.
3. Se disponibile, abilita "Allow LAN access".

Test:

```bash
ping 192.168.1.50
nslookup example.com 192.168.1.50
```

Apri un sito di IP check. Deve mostrare l'IP pubblico della linea di casa.

Da un device non admin:

- deve raggiungere AdGuard e servizi HTTPS;
- non deve raggiungere UI admin non autorizzate;
- deve usare exit node solo tramite `tag:exit`.

Da un device admin:

- deve raggiungere Headscale-UI;
- deve raggiungere monitoring/admin;
- deve poter gestire route e nodi.

---

## Phase H: High availability route

Headscale supporta piu router che annunciano la stessa route.

Schema consigliato:

- primario: LXC 100 `tag:router`, route `192.168.1.0/24`;
- backup: Proxmox host o secondo LXC, stessa route ma usato solo se serve.

Non abilitare HA routing finche non hai monitoring, perche due router configurati male rendono il troubleshooting piu difficile.

---

## Phase I: OIDC con Authentik

OIDC e fase avanzata. Prima stabilizza la VPN locale.

In Authentik:

- Application: `Headscale`
- Provider: OAuth2/OpenID Connect
- Redirect URI:

```text
https://vpn.yourdomain.duckdns.org/oidc/callback
```

In `config.yaml` Headscale:

```yaml
oidc:
  issuer: "https://auth.yourdomain.duckdns.org/application/o/headscale/"
  client_id: "headscale"
  client_secret: "PASTE_CLIENT_SECRET"
  pkce:
    enabled: true
  allowed_users:
    - "you@example.com"
```

Test:

```bash
docker exec headscale headscale configtest
docker compose restart headscale
docker logs --tail=100 headscale
```

---

## Phase J: Rollback

Se la policy rompe accessi:

```bash
cd /opt/core-network
docker compose stop headscale
cp /opt/core-network/headscale/config/config.yaml.bak.YYYY-MM-DD-HHMM /opt/core-network/headscale/config/config.yaml
cp /opt/core-network/headscale/policy/policy.hujson.bak.YYYY-MM-DD-HHMM /opt/core-network/headscale/policy/policy.hujson
docker compose up -d headscale
docker exec headscale headscale configtest
```

Se serve disattivare temporaneamente le policy:

1. Commenta o rimuovi `policy.path` da `config.yaml`.
2. Riavvia Headscale.
3. Correggi il policy file offline.
4. Riattiva `policy.path`.

---

## Phase K: Audit mensile

```bash
docker exec headscale headscale users list
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker exec headscale headscale preauthkeys list -u 1
docker exec headscale headscale apikeys list
```

Controlla:

- nodi vecchi o sconosciuti;
- route non necessarie;
- exit node non usati;
- pre-auth key ancora valide;
- API key troppo lunghe;
- dispositivi duplicati.

Azioni tipiche:

```bash
docker exec headscale headscale nodes expire -i DEVICE_ID
docker exec headscale headscale nodes delete -i DEVICE_ID
docker exec headscale headscale preauthkeys create -u 1 --expiration 2h
```

---

## Fonti ufficiali

- Headscale configuration: <https://headscale.net/stable/ref/configuration/>
- Headscale ACL/policy: <https://headscale.net/stable/ref/acls/>
- Headscale routes and exit nodes: <https://headscale.net/stable/ref/routes/>
- Headscale OIDC: <https://headscale.net/stable/ref/oidc/>
- Tailscale policy file: <https://tailscale.com/docs/reference/syntax/policy-file>
- Tailscale grants: <https://tailscale.com/docs/reference/syntax/grants>

---

**Previous:** [Runbook 05: Proxmox Exit Node](doc_05_proxmox_exit_node.md)
**Next:** [Runbook 07: Identity SSO Authentik](doc_07_identity_sso_authentik.md)
