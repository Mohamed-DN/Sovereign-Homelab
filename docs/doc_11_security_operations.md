# Runbook 11: Security Operations

Security operations significa avere routine, non solo strumenti.

Obiettivo:

- sapere cosa e esposto;
- ruotare segreti;
- aggiornare in modo controllato;
- rilevare problemi;
- non rompere il lab durante manutenzione.

---

## Phase A: Registro esposizione servizi

Mantieni questa tabella aggiornata:

| Servizio | Pubblico | VPN | Authentik | Note |
|---|---|---|---|---|
| Headscale | Si | Si | No | Pubblico necessario |
| Headscale-UI | No | Si | Si | Admin only |
| Authentik | Si | Si | MFA | Identity provider |
| Homepage | No | Si | Si | Dashboard |
| Uptime Kuma | No | Si | Si | Admin/ops |
| Beszel | No | Si | Si | Admin/ops |
| Dozzle | No | Si | Si | Admin only |
| Vaultwarden | Dipende | Si | App auth | Valutare pubblico |
| Immich | Dipende | Si | App auth | Valutare pubblico |
| Nextcloud | Dipende | Si | App auth/OIDC | Valutare pubblico |

Regola: se non sai perche e pubblico, non deve essere pubblico.

---

## Phase B: Update policy

Frequenza:

- settimanale: controllare alert e backup;
- mensile: update container e host;
- trimestrale: restore test;
- dopo ogni viaggio: audit Headscale.

Procedura update container:

```bash
cd /opt/sovereign/stacks/<stack>
docker compose pull
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

Prima di update app con dati:

- controlla release notes;
- backup recente;
- snapshot o PBS restore point;
- finestra manutenzione.

---

## Phase C: Rotazione segreti

Ogni 90 giorni o dopo sospetto leak:

- Headscale API key;
- Headscale pre-auth key;
- Authentik bootstrap/admin token;
- Vaultwarden admin token;
- DuckDNS token se esposto;
- password account admin;
- chiavi restic.

Comandi Headscale:

```bash
docker exec headscale headscale preauthkeys list -u 1
docker exec headscale headscale apikeys list
docker exec headscale headscale apikeys create --expiration 90d
```

Elimina o lascia scadere tutto cio che non serve.

---

## Phase D: CrowdSec

CrowdSec ha senso se esponi NPM o app pubbliche.

Uso consigliato:

- legge log NPM;
- rileva scan, brute force, CVE probe;
- blocca via bouncer o firewall se configurato.

Template:

```text
stacks/security/
  docker-compose.yml
  .env.example
  crowdsec/acquis.yaml
```

Prima di bloccare traffico, esegui in modalita osservazione e controlla i decision log.

Verifica:

```bash
docker exec crowdsec cscli metrics
docker exec crowdsec cscli decisions list
```

Nota importante: CrowdSec senza bouncer rileva ma non blocca. Per bloccare serve un remediation component.

---

## Phase E: Wazuh

Wazuh e un SIEM/XDR completo. Non installarlo solo per "avere piu roba".

Usalo se vuoi:

- agent su host e VM;
- raccolta log centralizzata;
- regole detection;
- dashboard security.

Richiede piu CPU/RAM e manutenzione. Per ora resta fase avanzata, non core immediato.

---

## Phase F: Hardening base

Checklist:

- SSH solo con chiavi dove possibile.
- Password admin uniche.
- MFA su Authentik.
- Admin UI solo VPN o Authentik.
- Docker socket esposto solo a strumenti admin fidati.
- `.env` fuori Git.
- backup prima di update.
- log monitorati dopo ogni change.
- router domestico con firmware aggiornato.

---

## Phase G: Incident response rapida

Se sospetti compromissione:

1. Disconnetti il servizio esposto in NPM.
2. Disabilita route/exit node se necessario.
3. Ruota token e password.
4. Controlla log NPM, app, Authentik, Headscale.
5. Rimuovi nodi Headscale non riconosciuti.
6. Ripristina da backup se i dati sono alterati.
7. Documenta incidente e fix.

Comandi utili:

```bash
docker ps
docker logs --tail=200 container_name
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
```

---

## Reference

- CrowdSec: <https://docs.crowdsec.net/>
- CrowdSec with NPM: <https://www.crowdsec.net/blog/crowdsec-with-nginx-proxy-manager>
- Wazuh Docker docs: <https://documentation.wazuh.com/current/deployment-options/docker/index.html>
- Dozzle: <https://dozzle.dev/>

---

**Previous:** [Runbook 10: Core Apps](doc_10_core_apps.md)
**Next:** [Roadmap](ROADMAP_SOVEREIGN_HOMELAB.md)
