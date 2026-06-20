# Runbook 10: Core Apps

Questa fase installa le app personali principali.

Ordine consigliato:

1. Vaultwarden.
2. Syncthing.
3. Immich.
4. Nextcloud AIO, solo se serve una suite completa.

Non mettere dati reali finche il backup non e verificato.

---

## Phase A: Modello accesso

| App | Hostname | Accesso consigliato |
|---|---|---|
| Vaultwarden | `pwd.<domain>` | VPN-first; pubblico solo se necessario |
| Immich | `foto.<domain>` | VPN-first; pubblico solo se necessario |
| Syncthing | `sync.<domain>` | Solo VPN/admin |
| Nextcloud | `files.<domain>` | VPN-first; pubblico solo se necessario |

Per app con mobile client, puoi esporre via HTTPS pubblico solo dopo:

- TLS valido;
- backup attivo;
- MFA dove supportata;
- password forti;
- monitor Uptime Kuma.

Prima di installare: [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md).

---

## Phase B: Vaultwarden

Template:

```text
stacks/apps/docker-compose.yml
```

Avvio:

```bash
cd /opt/sovereign/stacks/apps
cp .env.example .env
docker compose --env-file .env config
docker compose --env-file .env up -d vaultwarden
```

NPM:

| Campo | Valore |
|---|---|
| Domain | `pwd.<domain>` |
| Forward port | `8082` |
| Websockets | Enabled |
| SSL | Force SSL |

Hardening:

- disabilita registrazioni dopo il primo account;
- usa `ADMIN_TOKEN` forte, preferibilmente hash Argon2 se supportato;
- backup del volume `vaultwarden_data`.

---

## Phase C: Syncthing

Syncthing e peer-to-peer. Non sostituisce il backup.

Avvio:

```bash
docker compose --env-file .env up -d syncthing
```

Accesso UI:

```text
http://SERVER_IP:8384
```

Regole:

- UI solo VPN/admin;
- abilita password UI;
- non sincronizzare cartelle senza capire delete propagation;
- usa versioning per cartelle importanti.

---

## Phase D: Immich

Immich e il sostituto foto/video. E potente ma cambia spesso: verifica sempre la documentazione ufficiale prima di upgrade importanti.

Approccio official-first:

```bash
mkdir -p /opt/sovereign/reference/immich
cd /opt/sovereign/reference/immich
wget -O docker-compose.official.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O example.official.env https://github.com/immich-app/immich/releases/latest/download/example.env
```

Confronta questi file con `stacks/apps` prima di mettere dati reali.

Avvio dal template:

```bash
docker compose --env-file .env --profile immich up -d
```

NPM:

| Campo | Valore |
|---|---|
| Domain | `foto.<domain>` |
| Forward port | `2283` |
| Websockets | Enabled |
| SSL | Force SSL |

Backup minimo:

- upload directory;
- database Immich;
- `.env`;
- compose file.

Prima di importare tutta la libreria foto, fai un test con poche immagini e prova restore.

Nota critica: il backup database Immich non contiene foto e video. Devi proteggere anche `UPLOAD_LOCATION`.

---

## Phase E: Nextcloud AIO

Nextcloud AIO e consigliato se vuoi suite completa: file, calendar, contacts, office/talk.

Avvio:

```bash
docker compose --env-file .env --profile nextcloud up -d nextcloud-aio-mastercontainer
```

Poi apri:

```text
http://SERVER_IP:8086
```

Nota: Nextcloud AIO gestisce container interni e richiede attenzione con reverse proxy e porte. Segui la UI AIO e la documentazione ufficiale.

Se ti basta sync file semplice, preferisci Syncthing.

---

## Phase F: Monitor e backup obbligatori

Per ogni app:

- crea monitor Uptime Kuma;
- aggiungi link Homepage;
- aggiungi volumi al backup PBS/restic;
- documenta porte e hostname;
- verifica login da LAN, VPN e mobile se previsto.

---

## Reference

- Vaultwarden: <https://github.com/dani-garcia/vaultwarden>
- Immich quick start: <https://docs.immich.app/overview/quick-start>
- Immich backup: <https://docs.immich.app/administration/backup-and-restore>
- Nextcloud AIO: <https://github.com/nextcloud/all-in-one>
- Syncthing: <https://syncthing.net/>

---

**Previous:** [Runbook 09: Backup and DR](doc_09_backup_dr.md)
**Next:** [Runbook 11: Security Operations](doc_11_security_operations.md)
