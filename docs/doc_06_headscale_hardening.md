# Runbook 06: Headscale Hardening

Questo runbook alza il livello della VPN da "funziona" a "governata": policy, tag, route approval, audit e preparazione OIDC.

Obiettivo:

- evitare allow-all permanente;
- distinguere dispositivi personali, server, router ed exit node;
- approvare route in modo controllato;
- mantenere Headscale leggibile e auditabile.

---

## Phase A: Modello di accesso

Ruoli logici:

| Ruolo | Esempio | Tag/gruppo |
|---|---|---|
| Admin personale | laptop admin, workstation | `group:admin` |
| Dispositivi personali | smartphone, laptop | `group:users` |
| Router LAN | LXC 100 subnet router | `tag:router` |
| Exit node | Proxmox host P710 | `tag:exit` |
| Servizi | container/app server | `tag:service` |
| Admin tools | Headscale-UI, monitoring | `tag:admin` |

Regola pratica:

- I client personali possono usare DNS e servizi base.
- Solo admin puo raggiungere interfacce amministrative.
- Solo router taggati possono annunciare route.
- Solo exit node taggati possono annunciare full tunnel.

---

## Phase B: Abilitare il policy file

Dentro LXC 100, crea una directory dedicata:

```bash
mkdir -p /opt/core-network/headscale/policy
```

Nel file `/opt/core-network/headscale/config/config.yaml`, abilita il policy file. Controlla sempre la sintassi del tuo `config-example.yaml`, ma il modello e questo:

```yaml
policy:
  mode: file
  path: /etc/headscale/policy/policy.json
```

Aggiorna il volume del container Headscale in `docker-compose.yml`:

```yaml
volumes:
  - ./headscale/config:/etc/headscale
  - ./headscale/data:/var/lib/headscale
  - ./headscale/policy:/etc/headscale/policy
```

Poi prepara il file:

```bash
touch /opt/core-network/headscale/policy/policy.json
```

---

## Phase C: Policy iniziale least privilege

Crea `/opt/core-network/headscale/policy/policy.json`.

Sostituisci `mohamed@` con l'utente Headscale reale. Se usi utenti locali Headscale, il nome deve finire con `@` quando viene referenziato nel policy file.

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
      "192.168.1.0/24": ["tag:router"],
      "0.0.0.0/0": ["tag:exit"]
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
      "dst": ["192.168.1.0/24"],
      "ip": ["tcp:53", "udp:53", "tcp:80", "tcp:443", "icmp"]
    },
    {
      "src": ["group:users"],
      "dst": ["tag:service"],
      "ip": ["tcp:80", "tcp:443"]
    }
  ]
}
```

Nota: alcune versioni Headscale/Tailscale possono richiedere piccole differenze nella sintassi `autoApprovers` o `grants`. Se Headscale rifiuta il file, rimuovi temporaneamente `autoApprovers.exitNode`, riavvia, e approva l'exit node manualmente con `nodes approve-routes`.

---

## Phase D: Taggare i nodi infrastrutturali

Quando registri un nodo infrastrutturale, aggiungi il tag.

LXC 100 subnet router:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --advertise-tags tag:router \
  --advertise-routes=192.168.1.0/24 \
  --accept-dns=false
```

Proxmox host exit node:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --advertise-tags tag:exit \
  --advertise-exit-node \
  --hostname proxmox-p710 \
  --accept-dns=false
```

Se un nodo e gia registrato, puoi riapplicare:

```bash
tailscale set --advertise-tags tag:router
tailscale set --advertise-routes=192.168.1.0/24
```

oppure:

```bash
tailscale set --advertise-tags tag:exit
tailscale set --advertise-exit-node
```

---

## Phase E: Riavviare e verificare

Riavvia Headscale:

```bash
cd /opt/core-network
docker compose restart headscale
docker logs --tail=100 headscale
```

Verifica nodi:

```bash
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
```

Se l'auto-approval non viene applicato, approva manualmente:

```bash
docker exec headscale headscale nodes approve-routes --identifier LXC100_NODE_ID --routes 192.168.1.0/24
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 0.0.0.0/0
```

---

## Phase F: OIDC con Authentik come step avanzato

OIDC porta SSO e MFA anche al login Headscale. Non e obbligatorio per la VPN base.

Flusso consigliato:

1. Installa Authentik con [Runbook 07](doc_07_identity_sso_authentik.md).
2. Crea un provider OIDC per Headscale.
3. Redirect URI:

   ```text
   https://vpn.yourdomain.duckdns.org/oidc/callback
   ```

4. In Headscale configura:

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

5. Riavvia Headscale.

Limite importante: Headscale supporta OIDC, ma i gruppi OIDC non vanno trattati come unica fonte per le policy. Mantieni il policy file leggibile e testalo dopo ogni cambio identity.

---

## Phase G: Audit mensile

Esegui questo audit una volta al mese o dopo ogni viaggio.

```bash
docker exec headscale headscale users list
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker exec headscale headscale preauthkeys list -u 1
docker exec headscale headscale apikeys list
```

Controlla:

- nodi vecchi o duplicati;
- route non necessarie;
- exit node che non usi piu;
- pre-auth key ancora valide;
- API key scadute o troppo lunghe;
- dispositivi non riconosciuti.

Azioni:

```bash
docker exec headscale headscale nodes delete -i DEVICE_ID
docker exec headscale headscale nodes expire -i DEVICE_ID
```

Rigenera pre-auth key solo quando devi aggiungere un device:

```bash
docker exec headscale headscale preauthkeys create -u 1 --expiration 2h
```

---

## Phase H: Test di sicurezza

Da un device utente non admin:

- deve risolvere DNS via AdGuard;
- deve raggiungere servizi web personali;
- non deve raggiungere UI admin non autorizzate;
- deve poter usare exit node solo se policy e client lo permettono.

Da un device admin:

- deve raggiungere Headscale-UI, Homepage, Uptime Kuma, Beszel;
- deve poter gestire route e nodi;
- deve poter disattivare exit node dal client.

---

## Reference

- Headscale policy/ACL: <https://headscale.net/stable/ref/acls/>
- Headscale routes: <https://headscale.net/stable/ref/routes/>
- Headscale OIDC: <https://headscale.net/stable/ref/oidc/>
- Tailscale grants: <https://tailscale.com/docs/reference/syntax/grants>
- Tailscale tags: <https://tailscale.com/docs/features/tags>

---

**Previous:** [Runbook 05: Proxmox Exit Node](doc_05_proxmox_exit_node.md)
**Next:** [Runbook 07: Identity SSO Authentik](doc_07_identity_sso_authentik.md)
