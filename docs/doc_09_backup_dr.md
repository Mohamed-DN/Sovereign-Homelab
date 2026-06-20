# Runbook 09: Backup e Disaster Recovery

Backup non significa solo avere file. Backup significa poter ripristinare.

Obiettivo:

- PBS per VM/LXC;
- restore test periodico;
- retention e verify job;
- restic offsite opzionale per dati critici.

---

## Phase A: Cosa proteggere

| Dato | Metodo primario | Metodo opzionale |
|---|---|---|
| LXC 100 core-network | PBS | export config |
| VM/LXC app | PBS | restic per volumi |
| Docker compose | Git repo | copia `/opt/sovereign` |
| `.env` reali | vault offline/restic cifrato | stampa recovery |
| Immich uploads | PBS + restic | disco esterno |
| Vaultwarden data | PBS + restic | export cifrato |
| Authentik DB | PBS + dump | restic |

Regola: i dati app personali hanno doppia protezione.

---

## Phase B: Proxmox Backup Server

PBS va installato come VM dedicata o appliance separata.

Configurazione minima:

1. Crea datastore.
2. Aggiungi PBS a Proxmox VE come storage.
3. Crea backup job per:
   - LXC 100;
   - LXC/VM servizi;
   - VM Home Assistant;
   - VM PBS esclusa o protetta diversamente.
4. Abilita verify job.
5. Configura prune/retention.

Retention consigliata homelab:

```text
keep-last: 7
keep-daily: 14
keep-weekly: 8
keep-monthly: 6
```

Adatta in base allo spazio disponibile.

---

## Phase C: Restore test

Ogni trimestre fai un restore test.

Procedura:

1. Scegli una VM/LXC non critica o clona il backup su nuovo ID.
2. Esegui restore da PBS.
3. Avvia il sistema isolato o con IP temporaneo.
4. Verifica:
   - boot;
   - filesystem;
   - servizio principale;
   - log senza errori gravi.
5. Documenta data, backup usato, esito e tempo di restore.

Template nota:

```text
Restore test
Date:
Source backup:
Target VM/CT ID:
Service:
Result:
Issues:
Next action:
```

---

## Phase D: restic offsite opzionale

restic e utile per backup cifrati di cartelle applicative.

Esempio repository locale/offsite:

```bash
export RESTIC_REPOSITORY=/mnt/backup/restic/sovereign
export RESTIC_PASSWORD_FILE=/root/.config/restic/sovereign.pass
restic init
```

Backup:

```bash
restic backup /opt/sovereign /opt/core-network
restic snapshots
restic check
```

Retention:

```bash
restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 6 --prune
```

Non mettere `RESTIC_PASSWORD` in shell history. Usa `RESTIC_PASSWORD_FILE`.

---

## Phase E: Backup applicativi sensibili

### Vaultwarden

Proteggi:

- database volume;
- attachments;
- `ADMIN_TOKEN`;
- eventuale export cifrato periodico.

### Immich

Proteggi:

- upload directory;
- PostgreSQL database;
- `.env`;
- compose file.

Immich richiede attenzione: foto e database devono essere consistenti. Preferisci snapshot/PBS o procedura ufficiale.

### Authentik

Proteggi:

- PostgreSQL;
- media;
- `.env`;
- recovery code admin.

---

## Phase F: Checklist produzione

Prima di inserire dati reali:

- backup job creato;
- primo backup completato;
- verify job completato;
- restore test eseguito almeno su un servizio;
- `.env` reali salvati fuori Git;
- Uptime Kuma monitora il servizio;
- sai come fermare e ripristinare il container.

---

## Reference

- Proxmox VE backup: <https://pve.proxmox.com/wiki/Backup_and_Restore>
- Proxmox Backup Server: <https://pbs.proxmox.com/docs/>
- PBS maintenance: <https://pbs.proxmox.com/docs/maintenance.html>
- restic: <https://restic.net/>
- Immich backup: <https://docs.immich.app/administration/backup-and-restore>

---

**Previous:** [Runbook 08: Observability](doc_08_observability_dashboard.md)
**Next:** [Runbook 10: Core Apps](doc_10_core_apps.md)
