# Runbook 07: Identity, SSO e Authentik

Authentik diventa il punto centrale per login, MFA e protezione delle UI interne.

Obiettivo:

- un account admin forte;
- MFA obbligatoria;
- protezione delle dashboard interne;
- OIDC pronto per Headscale come fase avanzata.

---

## Phase A: Dove installare Authentik

Consiglio:

- installa Authentik nello stack applicativo Docker, non dentro LXC 100 se vuoi tenere il gateway leggero;
- esponi `auth.<domain>` via Nginx Proxy Manager;
- proteggi l'accesso admin con MFA immediatamente.

Template:

```text
stacks/identity/
  docker-compose.yml
  .env.example
```

---

## Phase B: Preparare i segreti

Prima controlla [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md).

Copia il template:

```bash
cd /opt/sovereign/stacks/identity
cp .env.example .env
```

Genera valori reali:

```bash
openssl rand -base64 48
openssl rand -base64 36
```

Aggiorna `.env` con:

- `AUTHENTIK_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `AUTHENTIK_BOOTSTRAP_PASSWORD`
- `AUTHENTIK_BOOTSTRAP_TOKEN`

Non committare mai `.env`.

---

## Phase C: Avviare Authentik

Approccio consigliato:

- per bootstrap rapido: usa `stacks/identity`;
- per produzione/upgrade: scarica il compose ufficiale Authentik e confrontalo con il template locale.

```bash
mkdir -p /opt/sovereign/reference/authentik
cd /opt/sovereign/reference/authentik
curl -O https://docs.goauthentik.io/compose.yml
```

```bash
docker compose --env-file .env up -d
docker compose ps
docker compose logs -f authentik-server
```

Apri:

```text
http://SERVER_IP:9000
```

Poi crea il proxy host in NPM:

| Campo | Valore |
|---|---|
| Domain Names | `auth.<domain>` |
| Scheme | `http` |
| Forward Hostname/IP | IP host Docker |
| Forward Port | `9000` |
| Websockets | Enabled |
| SSL | Wildcard certificate, Force SSL |

---

## Phase D: Primo hardening

Nel pannello Authentik:

1. Crea gruppo `homelab-admins`.
2. Crea gruppo `homelab-users`.
3. Abilita MFA/TOTP per l'utente admin.
4. Disabilita registrazioni pubbliche.
5. Imposta sessioni admin con durata breve.
6. Documenta recovery code offline.

Regola: se Authentik protegge la casa digitale, il suo admin non deve avere password debole o senza MFA.

---

## Phase E: Proteggere app senza login nativo

Per dashboard come Homepage, Uptime Kuma, Beszel, Dozzle o Headscale-UI puoi usare un **Proxy Provider** Authentik.

Modello:

1. Crea Application in Authentik.
2. Crea Provider di tipo Proxy.
3. Modalita consigliata: forward auth con reverse proxy esistente.
4. Crea Outpost.
5. In NPM aggiungi la configurazione avanzata richiesta da Authentik.

Accesso consigliato:

- Homepage: gruppo `homelab-users`.
- Uptime Kuma, Beszel, Dozzle: gruppo `homelab-admins`.
- Headscale-UI: gruppo `homelab-admins`.

---

## Phase F: OIDC per Headscale

Headscale puo usare OIDC, ma non e obbligatorio per la VPN base.

In Authentik:

1. Crea Application `Headscale`.
2. Provider: OAuth2/OpenID Connect.
3. Redirect URI:

   ```text
   https://vpn.<domain>/oidc/callback
   ```

4. Lascia vuota la Encryption Key.
5. Copia Client ID e Client Secret.

In Headscale:

```yaml
oidc:
  issuer: "https://auth.<domain>/application/o/headscale/"
  client_id: "headscale"
  client_secret: "PASTE_CLIENT_SECRET"
  pkce:
    enabled: true
  allowed_users:
    - "you@example.com"
```

Riavvia:

```bash
cd /opt/core-network
docker compose restart headscale
docker logs --tail=100 headscale
```

---

## Phase G: Backup Authentik

Dati da proteggere:

- volume PostgreSQL;
- media directory;
- `.env`;
- export di configurazione se disponibile.

Prima di usare Authentik in produzione, aggiungi:

- monitor Uptime Kuma su `https://auth.<domain>`;
- backup PBS del container/host;
- eventuale backup restic dei volumi applicativi.

Verifica operativa:

```bash
docker compose ps
docker compose logs --tail=100 authentik-server
curl -I https://auth.<domain>
```

---

## Reference

- Authentik docs: <https://docs.goauthentik.io/>
- Authentik proxy provider: <https://docs.goauthentik.io/add-secure-apps/providers/proxy/>
- Authentik outposts: <https://docs.goauthentik.io/add-secure-apps/outposts/>
- Authentik Headscale integration: <https://integrations.goauthentik.io/networking/headscale/>
- Headscale OIDC: <https://headscale.net/stable/ref/oidc/>

---

**Previous:** [Runbook 06: Headscale Hardening](doc_06_headscale_hardening.md)
**Next:** [Runbook 08: Observability](doc_08_observability_dashboard.md)
