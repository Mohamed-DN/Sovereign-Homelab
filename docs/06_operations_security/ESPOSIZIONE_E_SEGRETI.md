# Cosa si vede da fuori, e dove stanno i segreti

> Verificato il 2026-07-29. Regola voluta dal proprietario: *«i dati privati
> stanno solo qui dentro, nessuno può entrare se non è sulla VPN. Hermes può
> uscire ma nessuno può entrare in lui.»*

---

## 1. L'unica porta su internet

Controllati tutti i proxy host di NPM: **uno solo non finisce in `.internal`**.

| Nome pubblico | Dove porta | A cosa serve |
|---|---|---|
| `vpn.casca-certosa.duckdns.org` | 192.168.1.50:8080 | Headscale — il punto d'ingresso della VPN |

Tutto il resto — Immich, Nextcloud, Vaultwarden, Jellyfin, Obsidian, la
dashboard, Hermes — risponde **solo** a un nome `.internal`, che esiste solo nel
DNS di casa (AdGuard) e non è risolvibile da fuori.

Quindi la postura è già quella richiesta: **per entrare bisogna prima essere
sulla VPN.** L'unica cosa raggiungibile da internet è la porta della VPN stessa,
che è esattamente ciò che deve essere.

> Quello che questo documento **non** può dimostrare: le regole di port
> forwarding sul router, che non sono ispezionabili da qui. Se un domani apri
> una porta sul router, questa pagina non se ne accorge. Verifica lì che l'unico
> inoltro sia quello verso Headscale.

---

## 2. Hermes: esce, ma non si entra

Hermes deve stare in ascolto sulla LAN, perché NPM vive su un altro host
(LXC 100) e deve poterlo raggiungere. Ma «in ascolto sulla LAN» significava che
qualunque macchina di casa poteva bussare direttamente alla porta 8093,
scavalcando il reverse proxy.

Non era un buco di autenticazione — chi non passa da NPM riceve `401`, perché
l'identità viene accettata solo dall'header che solo NPM può impostare — ma era
superficie inutile.

Il proprietario ha precisato: *«va bene che Hermes ascolti, purché i dati li dia
solo a me»*. La regola che segue fa esattamente questo e **non gli toglie
niente**: lui arriva da `hermes.internal`, che continua a funzionare identico.
Chiude solo la strada a chi vorrebbe parlare con Hermes scavalcando il login.

```
ACCEPT  127.0.0.1        tcp dpt:8093   <- console di emergenza
ACCEPT  192.168.1.50     tcp dpt:8093   <- NPM, l'unica via legittima
ACCEPT  192.168.1.150    tcp dpt:8093   <- nodo Proxmox, per la manutenzione
DROP    0.0.0.0/0        tcp dpt:8093   <- tutto il resto
```

Verifica eseguita subito dopo:

| Da dove | Atteso | Reale |
|---|---|---|
| LXC 101 (una macchina qualunque di casa) | bloccato | **bloccato** |
| NPM (192.168.1.50) | passa | HTTP 401 (nessun login: corretto) |
| `https://hermes.internal` | 302 al login | **302** |
| localhost su LXC 102 | passa | HTTP 200 |

Le regole non sopravvivrebbero a un riavvio, quindi **le rimette il servizio
stesso**: `ExecStartPost` nell'unità systemd le riscrive a ogni avvio, e
`ExecStopPost` le toglie quando il servizio si ferma. Sono idempotenti: si
possono riapplicare quante volte si vuole senza accumulare duplicati.

### In uscita, invece, è libero

Hermes esce verso internet per la ricerca web (via SearXNG) e verso la GPU del
PC. In direzione opposta, `web_fetch` **rifiuta gli indirizzi interni**
(`localhost`, `127.0.0.1`, tutte le reti private, qualunque `.internal`):
altrimenti sarebbe un modo per far leggere al server i propri servizi privati
per conto di chi sta chattando.

```
http://192.168.1.150:8095/  -> rifiutato
https://dash.internal/      -> rifiutato
http://127.0.0.1:5984/      -> rifiutato
https://example.com         -> letto
```

---

## 3. I segreti: cosa prendo da M-DNVault

Il proprietario ha condiviso il suo progetto
[M-DNVault](https://github.com/Mohamed-DN/Password-manager) dicendo di prenderne
**l'idea, non la struttura**. L'idea buona è questa, e vale la pena adottarla:

| Principio suo | Come si applica qui |
|---|---|
| Il segreto **non sta** nell'applicazione: l'app conserva un *riferimento*, il valore sta altrove | Già così: `backends.json` contiene `api_key_file`, mai la chiave. Hermes legge il file solo quando serve |
| Percorsi **gerarchici** invece di un mucchio piatto | Da adottare: oggi è `/root/sovereign-secrets/hermes/key-<nome>`, piatto. Meglio `hermes/motori/<nome>/api-key` |
| **Versioning** dei segreti | Da adottare: conservare la chiave precedente permette di tornare indietro se una rotazione va male |
| **Audit** di ogni accesso: chi, quando, da dove | Da adottare per i segreti; per le azioni esiste già il registro della dashboard |
| Ruoli separati (admin / app / sola lettura) | Già così sul lato database e CouchDB (`hermes_reader` non può scrivere) |

**Quello che non prendo**: OpenBao più PostgreSQL più una replica. È
l'architettura giusta per un'azienda con molti sistemi e molti operatori; qui
aggiungerebbe tre servizi da mantenere, da monitorare e da riparare alle due di
notte, per custodire una manciata di segreti che oggi stanno in file `0600`
leggibili solo da root su una macchina che è già la radice della fiducia.

Il valore del tuo disegno non è OpenBao: è **separare il riferimento dal valore,
versionare e tracciare**. Quelle tre cose si possono avere senza aggiungere
nulla, ed è quello che faremo.

> Se un domani i segreti diventano molti e con più persone che li usano, allora
> OpenBao diventa la scelta giusta e questo documento va riscritto.

### Regole già in vigore sui segreti

- Stanno in `/root/sovereign-secrets/`, permessi `0600`, mai nel repository
  (il validatore del repo ha un controllo apposta che cerca segreti nei file).
- Le chiavi API scritte dal pannello di Hermes sono create **direttamente** a
  `0600` con `os.open(..., 0o600)`: scriverle e poi correggere i permessi
  lascerebbe un istante in cui sono leggibili da tutti.
- Il percorso di una chiave lo decide il **nome del motore**, non chi manda la
  richiesta: non si può scegliere dove scrivere.
- Il modello **non vede mai** un segreto: quando serve una credenziale la usa il
  codice, non l'LLM.
