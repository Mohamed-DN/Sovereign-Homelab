# Prompt per aprire una nuova sessione

Copia tutto quello che sta fra le righe e incollalo come primo messaggio.

---

Lavoriamo sul **Sovereign Homelab**, la mia infrastruttura di casa. Repository
locale: `c:\DBA\Sovereign-Homelab` (git, branch `main`, si committa e si pusha
su main — è la convenzione di questo repo).

**Parti leggendo `docs/00_overview/PIANO_MASTER.md`**: è l'indice di tutto, con
lo stato di ogni cosa e i link agli altri piani. Poi `docs/04_apps/hermes.md`
per il servizio su cui stiamo lavorando.

## Come raggiungere l'infrastruttura

```bash
ssh -i /c/DBA/sovereign_homelab_audit_ed25519 \
    -o UserKnownHostsFile=/c/DBA/sovereign_known_hosts \
    -o StrictHostKeyChecking=no root@192.168.1.150
```

Da lì si entra nei container con `pct exec <id> -- <comando>`.

| Host | Cosa c'è |
|---|---|
| `192.168.1.150` | nodo Proxmox `pve`, dashboard su :8095 |
| LXC 100 · `.50` | NPM (reverse proxy + gate SSO), AdGuard, Headscale |
| LXC 101 · `.51` | Authentik, Uptime Kuma, relay email :8099 |
| LXC 102 · `.52` | **Hermes :8093**, CouchDB (Obsidian), Ollama, Jellyfin, Forgejo… |
| LXC 103 · `.53` | ntfy, Scrutiny, NetAlertX |
| VM 110/120/130/140 | Immich, Nextcloud, Home Assistant, PBS |
| Il mio PC · `.100` | Windows, **RTX 5070 Ti 16 GB**, Ollama in ascolto per Hermes |

Io sono **`mohamed`**, proprietario e amministratore: ho accesso completo a
tutto, per principio. Non chiedere il permesso per darmi accesso a qualcosa.
I segreti stanno in `/root/sovereign-secrets/` (permessi `0600`), **mai** nel
repository.

## Come voglio che lavori

1. **Verifica prima di dichiarare.** Non dirmi «fatto» se non l'hai provato.
   In questa sessione uno strumento ha riferito «invio fallito» su email che
   erano state consegnate, e il modello ha inventato una spiegazione
   convincente. Uno strumento che sbaglia non dà errore: racconta una bugia
   sicura di sé.
2. **Dimmi quello che non funziona**, anche se è colpa tua. Preferisco un
   difetto detto che una rassicurazione.
3. **Documenta tutto nel repository** e committa: ogni cosa che va in
   produzione deve avere la sua pagina in `docs/`.
4. Prima di committare: `powershell -NoProfile -File scripts/validate-repository.ps1`
   deve passare (10 gruppi). I runbook in `docs/04_apps/` devono contenere le
   sezioni previste dal contratto, in inglese nei titoli.
5. **Non indovinare** su cose che posso dirti io: chiedimi.
6. Su Authentik: quando un provider non va, **non tirare a indovinare un campo
   alla volta** — confronta campo per campo con uno che funziona. Ci è già
   costato due volte.
7. Commenti nel codice in inglese, messaggi all'utente in italiano, Python di
   sola libreria standard.

## Dove siamo

Hermes è **vivo** su `https://hermes.internal` (dietro SSO), gira sulla GPU del
mio PC con ricaduta sul server. Sa: stato dell'infrastruttura, accessi, appunti
Obsidian, ricerca web, email, analisi immagini, squadra di 13 agenti.

**Prossimi passi, in ordine** (dettagli in `PIANO_MASTER.md` §3):

1. **OmniRoute** installato su LXC 102 e collegato — la guardia `private` c'è già
2. **Fase 1 memoria**: PostgreSQL + Qdrant, strumenti `ricorda` / `agenda`
3. **Fase 2 voce**: registratore nella pagina + Whisper sul PC + Piper
4. **Fase 3 Telegram** (anche con audio) e PWA per iPhone

**Difetti noti da tenere a mente** (`PIANO_MASTER.md` §5): il modello a volte
finge di usare uno strumento; la ricerca nel vault conta le parole ed è
imprecisa; il pulsante voce non registra perché l'ingresso non è mai stato
costruito.

---

**Nota per me stesso**: se la sessione precedente è stata lunga, il contesto
può essere stato riassunto. `PIANO_MASTER.md` è scritto apposta per ripartire
senza avere la conversazione davanti.
