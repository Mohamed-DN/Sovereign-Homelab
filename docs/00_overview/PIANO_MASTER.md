# PIANO MASTER — l'indice di tutto

> Aggiornato il 2026-07-30. **Questo è il file da cui partire.** I piani erano
> finiti sparsi su cinque documenti: qui c'è l'elenco completo di tutto ciò che
> è stato chiesto, proposto o scoperto, con lo stato e il link a dove è
> descritto per esteso. Se una cosa non è in questa tabella, è stata dimenticata.

---

## 1. I documenti

| Documento | Cosa contiene |
|---|---|
| [HERMES_PIANO_A_FASI.md](HERMES_PIANO_A_FASI.md) | **Il piano operativo**: fasi 0-8, ognuna con la sua verifica |
| [HERMES_ARCHITETTURA_COMPLETA.md](HERMES_ARCHITETTURA_COMPLETA.md) | Dove sta ogni pezzo, memoria fuori dal modello, modalità master, voce, privacy |
| [PIANO_HERMES_ESPANSO.md](PIANO_HERMES_ESPANSO.md) | Voce, web, LLM gratuiti, assistente realtime, creazione contenuti, n8n |
| [PIANO_HERMES_CANALI_E_DB.md](PIANO_HERMES_CANALI_E_DB.md) | Motori oltre Ollama, Telegram, **perché no WhatsApp**, database, controlli |
| [hermes.md](../04_apps/hermes.md) | Il runbook del servizio: com'è fatto, come si ripara |
| [hermes-memoria.md](../04_apps/hermes-memoria.md) | **La memoria**: i tre archivi, le due bugie chiuse, il costo misurato degli embedding |
| [omniroute.md](../04_apps/omniroute.md) | **Il gateway** verso i fornitori esterni: cosa funziona e cosa manca |
| [PIANO_AGGIORNAMENTO_DA_NEXI.md](PIANO_AGGIORNAMENTO_DA_NEXI.md) | Cosa prendere dai repo Nexi DBA AI / DB-AI, **cosa lasciare lì e perché**, con i task in ordine |
| [PRIVACY_E_VISIBILITA_DATI.md](../06_operations_security/PRIVACY_E_VISIBILITA_DATI.md) | Chi vede cosa, servizio per servizio (la domanda su Immich) |
| [ESPOSIZIONE_E_SEGRETI.md](../06_operations_security/ESPOSIZIONE_E_SEGRETI.md) | Cosa si vede da internet, dove stanno i segreti, idea da M-DNVault |

---

## 2. FATTO e verificato

| # | Cosa | Dove |
|---|---|---|
| 1 | Hermes: chat, SSO, ruoli, permessi per utente | [hermes.md](../04_apps/hermes.md) §4 |
| 2 | Motori intercambiabili PC/server/API + pannello impostazioni | §7 |
| 3 | Strumenti: stato infrastruttura, accessi, vault Obsidian | §3 |
| 4 | Web: ricerca + lettura pagine via SearXNG (JSON abilitato) | §3 |
| 5 | Squadra di 13 agenti con ruoli (stile ChatDev) | §7-bis |
| 6 | Email al proprietario dallo strumento `send_mail` | §3 |
| 7 | Caricamento file + **analisi immagini** (modello multimodale) | §3 |
| 8 | Conversazione che sopravvive al ricaricamento pagina | — |
| 9 | Regola **`private`**: motore esterno non vede dati di casa | [fasi](HERMES_PIANO_A_FASI.md) §5 |
| 10 | Notifiche email agli utenti su ogni evento IAM | [dashboard](../03_platform_services/SOVEREIGN_MASTER_DASHBOARD.md) |
| 11 | Pulsante Hermes + robot pixel oro/argento nella dashboard | [hermes.md](../04_apps/hermes.md) §7-bis |
| 12 | Time Garden installato senza rompere LiveSync | [obsidian.md](../04_apps/obsidian.md) |
| **S1** | Firewall Ollama ristretto al server (era aperto su profilo Public) | [hermes.md](../04_apps/hermes.md) §6 |
| **S2** | Vault Obsidian riservato al proprietario (era leggibile da altri utenti) | §3 |
| **S3** | Porta di Hermes chiusa a chi non passa dal login | [esposizione](../06_operations_security/ESPOSIZIONE_E_SEGRETI.md) §2 |
| **S4** | `web_fetch` rifiuta gli indirizzi interni (SSRF) | §2 |
| 13 | **Memoria fuori dal modello**: Postgres + Qdrant + Valkey, con `ricorda`, `ricorda_cerca`, `dimentica`, `agenda_aggiungi`, `agenda_leggi` | [memoria](../04_apps/hermes-memoria.md) |
| 14 | **Ricerca nel vault per significato**: 125 note indicizzate, «time garden» non trova più query Oracle | [memoria](../04_apps/hermes-memoria.md) §5 |
| 14-bis | **I runbook di questo repository sono nell'indice**: 102 documenti, 1227 pezzi. Hermes risponde «come si ripara X» citando il file | [memoria](../04_apps/hermes-memoria.md) §4-bis |
| 15 | **La bugia «ho salvato» è chiusa**: gli ordini espliciti li esegue il codice, e una pretesa non verificata viene dichiarata all'utente | [memoria](../04_apps/hermes-memoria.md) §4 |
| 16 | **Fuso orario**: l'agenda e l'orologio di Hermes erano due ore indietro (il container gira su UTC) | [memoria](../04_apps/hermes-memoria.md) §4 |
| 17 | **OmniRoute** installato, dietro SSO, con `/v1` esente e chiave API. Motore non privato in `backends.json` | [omniroute](../04_apps/omniroute.md) |
| **S5** | Porte di OmniRoute chiuse alla LAN (`DOCKER-USER`): erano aperte a chiunque conoscesse la password condivisa | [omniroute](../04_apps/omniroute.md) §6 |
| **S6** | Archivi della memoria in ascolto **solo** su loopback, con password e chiave API anche lì | [memoria](../04_apps/hermes-memoria.md) §1 |

---

## 3. DA FARE — l'elenco completo, niente escluso

### Fase 1 — Memoria e database ✅ FATTA

| Cosa | Perché | Stato |
|---|---|---|
| **PostgreSQL** — fatti strutturati: persone, impegni, preferenze | i dati sono relazionali, e il proprietario è DBA | ✅ live |
| **Qdrant** — ricerca per significato (embeddings) | «cosa mi aveva detto sul lavoro?» non si risolve con `LIKE`; risolve anche la ricerca scadente nel vault | ✅ live, 125 note |
| **Valkey** — cache e code | serve già adesso: un embedding sulla CPU del server costa 18 s | ✅ live (cache embedding) |
| Strumenti `ricorda`, `ricorda_cerca`, `dimentica`, `agenda_aggiungi`, `agenda_leggi` | — | ✅ live |
| Memoria **fuori dal modello**, con data e origine di ogni voce | cambiando modello non si perde nulla | ✅ verificata col riavvio |
| Reindicizzazione notturna del vault | una nota scritta oggi è cercabile domani | ✅ timer 03:20 |

### Fase 2 — Voce

| Cosa | Nota | Stato |
|---|---|---|
| **Registratore nella pagina** | **oggi non esiste**: il pulsante voce fa solo *parlare*, non *ascoltare*. Omissione mia | da fare |
| **Whisper `large-v3-turbo`** sul PC (GPU) | trascrizione, API compatibile OpenAI, firewall come Ollama | da fare |
| **Piper** sul server | risposta parlata, funziona anche a PC spento | da fare |
| **Clonazione voce** (F5-TTS / XTTS-v2) | la sua voce; per voci di altri serve il loro consenso | da fare |
| Audio e video caricati | oggi rifiutati con spiegazione; servono Whisper + `ffmpeg` | da fare |

### Fase 3 — Hermes in tasca

| Cosa | Nota | Stato |
|---|---|---|
| **Telegram** (bot ufficiale, long polling) | mappatura `id → utente` a mano, sconosciuti rifiutati | da fare |
| **Telegram con audio** | dipende da Whisper (fase 2) | da fare |
| **PWA** per iPhone | `manifest.json`, icona sulla home | da fare |
| App iOS nativa | solo se la PWA non basta: serve Mac + account Apple | valutare |
| **WhatsApp** | **escluso**: ban del numero entro 2-8 settimane, e dal 15/01/2026 vietati i chatbot di terze parti | [motivazione](PIANO_HERMES_CANALI_E_DB.md) §3 |

### Fase 4 — Vault e trasparenza

| Cosa | Nota | Stato |
|---|---|---|
| **Scrivere sul vault** Obsidian | formato a pezzi di LiveSync; si prova su una copia prima | da fare |
| **Mostrare il ragionamento** (`thinking`) | il campo esiste già, oggi lo scarto | da fare |
| **Repo → vault**: la documentazione dentro Obsidian | direzione unica, la verità resta git | da fare |

### Fase 5 — Motori esterni

| Cosa | Nota | Stato |
|---|---|---|
| Regola **`private`** | **fatta**: motore esterno → solo strumenti web | ✅ |
| **OmniRoute** (sostituisce LiteLLM) | 290+ fornitori, 40+ gratuiti, circuit breaker, chiavi AES-256 | da installare |
| Provider gratuiti | [free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources) | dopo OmniRoute |
| **vLLM** al posto di Ollama sul PC | solo se lo sciame diventa l'uso normale; su Blackwell serve CUDA 12.8+ | valutare |

### Fase 6 — Modalità master

| Cosa | Nota | Stato |
|---|---|---|
| Elenco di **azioni permesse** (non una shell libera) | un `rm -rf` generato per refuso non deve poter partire | da fare |
| Conferma esplicita per l'irreversibile | dati, Immich, fermare una VM | da fare |
| Scadenza a 30 minuti, registro non riscrivibile, interruttore d'emergenza | — | da fare |

### Fase 7 — Database esterni e controlli

| Cosa | Nota | Stato |
|---|---|---|
| **`db_query` solo SELECT** | utente DB realmente in sola lettura, tetto righe, solo admin, ogni query registrata | da fare |
| Oracle via `oracledb` thin mode | niente client Oracle da installare | da fare |
| **Controlli programmati** | domanda + orario + dove riferire. Un controllo **riferisce**, non aggiusta | da fare |

### Fase 8 — Integrazioni dai repo

| Cosa | A cosa serve | Stato |
|---|---|---|
| **[agent-reach](https://github.com/Panniantong/agent-reach)** | arrivare dove SearXNG non arriva: YouTube, Reddit, X, GitHub, RSS. Partire dai canali senza chiave | da fare |
| **[OmniRoute](https://github.com/diegosouzapw/OmniRoute)** | vedi fase 5 | da installare |
| **[M-DNVault](https://github.com/Mohamed-DN/Password-manager)** | idea presa: percorsi gerarchici, versioning, audit dei segreti. **Non** OpenBao+Postgres | parziale |
| **n8n** (2000 workflow) | solo come catalogo di idee: le automazioni qui restano script systemd | valutare |
| **Cluely / Natively** | assistente realtime sul PC, puntato su OmniRoute e Whisper di casa | valutare |
| Creazione contenuti (senza volti, persone, musica) | Piper + `ffmpeg`; immagini con ComfyUI **solo se avanza VRAM** | valutare |
| **Open WebUI** | raccomandazione: **tenerli separati**. Decisione del proprietario | da decidere |

---

## 4. Fuori da Hermes — cose dell'impianto rimaste aperte

| Cosa | Nota | Stato |
|---|---|---|
| **Nextcloud 502 intermittente** | diagnosticato: il backend rifiuta le connessioni ~1 volta su 4, ogni ~5 minuti. Backend sano 20/20 se interrogato diretto. **Serve accesso SSH alla VM 120**, oggi non autorizzato | bloccato |
| **Monitor Kuma per Hermes** | da creare a mano: Kuma non ha API REST e su LXC 101 manca l'uscita internet per `python-socketio`. HTTP su `https://hermes.internal/health`, 60s | da fare |
| **Tolleranza monitor Nextcloud** | alzare i tentativi così un singolo 502 non colora tutto di rosso | da fare |
| **Ente Photos** per la sorella | l'unica risposta tecnica vera a «non voglio che l'admin veda le mie foto»: cifratura end-to-end | [privacy](../06_operations_security/PRIVACY_E_VISIBILITA_DATI.md) §4 |
| **Account orfano Immich** `luna222@gmail.com` | 0 foto, l'utente Authentik non esiste più | da pulire |
| **Forgejo `ACCOUNT_LINKING = auto`** | unisce gli account per email: stessa classe di rischio dell'incidente Jellyfin | da valutare |
| Escludere `06 Templates/Images` dalla sincronizzazione | 35 MB di mp3/gif scaricati da ogni dispositivo | opzionale |

---

## 5. Difetti noti di Hermes, da non dimenticare

| Difetto | Nota |
|---|---|
| Il modello **finge di usare gli strumenti** | **mitigato, non guarito.** Gli ordini espliciti ora li esegue il codice, e una pretesa non verificata viene dichiarata all'utente ([memoria](../04_apps/hermes-memoria.md) §4). Ma su una richiesta indiretta `qwen3.5:9b` può ancora saltare uno strumento senza che nessuno se ne accorga |
| ~~La ricerca nel vault è **primitiva**~~ | **risolta**: 125 note indicizzate in Qdrant, cerca per significato. La ricerca a parole resta come ripiego dichiarato |
| Gli strumenti dei sotto-agenti non sono visibili in pagina | si vede il piano, non le singole chiamate. Lo risolverebbe **Langfuse** (vedi il piano di aggiornamento) |
| Il pulsante voce non registra | vedi fase 2: non è un bug, è una parte mai costruita |
| Il **motore degli embedding sulla CPU è 180× più lento** della GPU | 18 s contro 97 ms per la stessa frase. Con il PC spento la prima ricerca è lentissima. Non indagato a fondo ([memoria](../04_apps/hermes-memoria.md) §6) |
| Il database di OmniRoute **non è cifrato** a riposo | nonostante `STORAGE_ENCRYPTION_KEY`. Le chiavi dei fornitori dentro invece lo sono ([omniroute](../04_apps/omniroute.md) §6) |

---

## 6. Serve dal proprietario

- L'errore vero del pulsante voce dalla console del browser (F12).
- Una decisione su **Open WebUI** (tenerli separati è la raccomandazione).
- Autorizzazione SSH alla **VM 120** per chiudere il caso Nextcloud.
- Se vuole **Ente Photos** per la sorella, o se preferisce restare com'è.
