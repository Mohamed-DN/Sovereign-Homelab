# Hermes: il programma completo, diviso in fasi

> Scritto il 2026-07-29. Raccoglie **tutto** quello che il proprietario ha
> chiesto e tutto quello che è emerso costruendo, in un ordine che tiene conto
> di cosa dipende da cosa. Ogni fase è verificabile da sola.

> **Indice di tutto**: [PIANO_MASTER.md](PIANO_MASTER.md) — se cerchi una cosa
> e non e' qui dentro, e' elencata la'.

---

## Come leggere questo piano

Ogni voce dice **cosa**, **perché in quella fase**, e **come si verifica**.
Una fase è finita solo quando la verifica passa — non quando il codice è
scritto. Questa regola nasce da un errore reale: lo strumento email ha
riferito «invio fallito» su email che erano state consegnate, e il modello ha
inventato una spiegazione convincente. **Uno strumento che sbaglia non dà
errore: racconta una bugia sicura di sé.**

---

## FASE 0 — Fatto e verificato

| Cosa | Verifica passata |
|---|---|
| Chat con SSO, ruoli, permessi per utente | login reale, `/api/state` → `is_admin: true` |
| Motori intercambiabili (PC/server/API) + pannello | 3 motori, cambio modello dal pannello |
| Stato infrastruttura, accessi, vault Obsidian | 33 note lette, dati veri nelle risposte |
| Web: ricerca e lettura pagine (SearXNG) | Proxmox VE 9.2 trovato online |
| Blocco indirizzi interni in `web_fetch` | `dash.internal`, `127.0.0.1`, RFC1918 → rifiutati |
| Squadra di 13 agenti con ruoli | SRE+Debugger+Sviluppatore assegnati da soli |
| Email al proprietario | «Gatto pixel» consegnata |
| Conversazione che sopravvive al ricaricamento | 24 messaggi ripresi |
| Caricamento file + analisi immagini | immagine descritta correttamente |
| Porta chiusa a chi non passa dal login | LXC 101 bloccato, NPM passa |
| Firewall Ollama ristretto al server | 3 host provati, solo Hermes passa |

---

## FASE 1 — La memoria (la prossima)

**Perché prima di tutto**: tutto ciò che gli racconti prima che esista è perso.
E senza memoria non esistono appuntamenti, persone, preferenze.

- **Postgres** per i fatti strutturati (persone, impegni, preferenze) e
  **Qdrant** per la ricerca per significato (embeddings). Il proprietario ha
  lasciato libera la scelta: Postgres perché i dati sono relazionali e lui è
  DBA; Qdrant perché «cosa mi aveva detto Luna sul lavoro?» non si risolve con
  `LIKE`.
- Strumenti: `ricorda`, `ricorda_cerca`, `dimentica`, `agenda_aggiungi`,
  `agenda_leggi`.
- Ogni voce porta **quando** e **da dove** (detto da lui / dedotto).
- **Model-agnostica**: sta nel database, non nel modello. Cambiando motore non
  si perde niente.

*Verifica*: gli dico un fatto, cambio modello, riavvio il servizio, e lui lo
ricorda ancora.

## FASE 2 — Voce

- **Whisper `large-v3-turbo`** sul PC (GPU), API compatibile OpenAI, firewall
  come Ollama. Registrazione dal browser → trascrizione → chat.
- **Piper** sul server per la risposta parlata (funziona anche a PC spento).
- Il pulsante voce attuale **non funziona** e va debuggato con la console del
  browser aperta: serve l'errore vero, non un'ipotesi.

*Verifica*: gli parlo, mi risponde, e lo sento.

## FASE 3 — Hermes in tasca

- **Telegram**: bot ufficiale, long polling, nessuna porta aperta. Mappatura
  `id → utente` compilata a mano, ID sconosciuti rifiutati.
- **PWA**: `manifest.json` + service worker → icona sulla home dell'iPhone.
  Prima dell'app nativa, che richiede Mac, account Apple e revisione store.
- **WhatsApp resta escluso** (vedi `PIANO_HERMES_CANALI_E_DB.md` §3: ban del
  numero personale entro 2-8 settimane, e dal 15/01/2026 i chatbot di terze
  parti sono vietati esplicitamente).

*Verifica*: gli scrivo dal telefono fuori casa e risponde con i miei permessi.

## FASE 4 — Scrittura sul vault e ragionamento visibile

- **Scrivere su Obsidian**: va fatto nel formato a pezzi di LiveSync, con la
  revisione giusta, altrimenti corrompe un vault vivo. Si costruisce su una
  copia di prova prima di toccare quello vero.
- **Mostrare il `thinking`**: il campo esiste già nella risposta e oggi lo
  scarto. Va mostrato in un riquadro richiudibile quando la casella è accesa.

*Verifica*: Hermes crea una nota, la vedo comparire su Obsidian sul telefono, e
la sincronizzazione degli altri dispositivi non si rompe.

## FASE 5 — La regola `private` e i motori gratuiti

> **Aggiornato dopo aver letto i repo del proprietario.** La regola `private` e'
> **gia' fatta e verificata** (vedi sotto); resta da collegare il gateway, e il
> gateway non e' piu' LiteLLM ma **OmniRoute**.

### La guardia: fatta

Ogni motore ha un attributo `private`. Un motore **non privato** — cioe' un
fornitore esterno, che con ogni probabilita' si addestra sui prompt — non riceve
mai gli strumenti che toccano roba di casa: vault, stato infrastruttura,
accessi, email.

Due dettagli di disegno che contano:

- **Chiude in caso di dimenticanza**: un motore e' privato *salvo prova
  contraria*, e qualunque motore di tipo `openai` (cioe' il computer di
  qualcun altro) e' considerato non privato finche' non lo dichiari.
- I filtri sono **due e indipendenti**: il ruolo della persona, e la fiducia nel
  motore. Nessuno dei due puo' aggirare l'altro.

Verifica eseguita:

| Motore | privato | strumenti offerti |
|---|---|---|
| locale (Ollama) | si | 8 |
| API esterna | **no** | **2** (solo web) |
| API dichiarata `private: true` (es. vLLM tuo) | si | 8 |

### OmniRoute al posto di LiteLLM

[OmniRoute](https://github.com/diegosouzapw/OmniRoute) fa quello che serviva, meglio:

- endpoint **compatibile OpenAI** su `localhost:20128/v1` → entra in
  `backends.json` come qualunque altro motore, **senza codice nuovo**;
- **290+ fornitori**, di cui **40+ gratuiti permanenti** senza carta;
- **resilienza a tre livelli**: circuit breaker per fornitore, backoff per
  chiave, isolamento del singolo modello che fallisce — cioe' esattamente
  *«quando finisce il credito continuo a lavorare»*;
- chiavi cifrate **AES-256-GCM** a riposo, nessuna telemetria;
- MIT, self-hosted, Node.js o Docker.

Lo useranno **sia Hermes sia Claude Code**. Va installato su LXC 102 e
dichiarato `private: false`, cosi' la guardia sopra lo tiene lontano dai dati di
casa in automatico.



- Ogni motore porta `private: true/false`. Un motore **non privato** non riceve
  mai memoria personale, vault, o stato dell'infrastruttura.
- Solo dopo: **LiteLLM** come router unico davanti a tutto, con i provider
  gratuiti ([cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)),
  usabile anche da Claude Code quando finisce il credito.

*Verifica*: con un motore non privato selezionato, gli strumenti sensibili non
vengono nemmeno offerti al modello.

> Questa regola è **l'unica che la modalità master non deve poter spegnere**:
> non protegge lui da Hermes, protegge i suoi dati da un fornitore esterno.

## FASE 6 — Modalità master (azioni sul server)

- **Elenco di azioni permesse** in un file, non una shell libera.
- **Reversibile vs no**: riavviare un container si fa; toccare dati, Immich o
  fermare una VM chiede conferma esplicita in chat.
- **A tempo** (30 minuti), **registro** che Hermes non può riscrivere,
  **interruttore d'emergenza** (`systemctl stop sovereign-hermes`).

*Verifica*: un'azione reversibile parte; una distruttiva si ferma e chiede;
tutto finisce nel registro.

## FASE 7 — Database e controlli programmati

- `db_query` **solo SELECT**, connessioni dichiarate in configurazione, utente
  di database realmente in sola lettura, tetto sulle righe, solo amministratore,
  ogni query registrata.
- **Controlli salvati**: una domanda + un orario + dove riferire (email, ntfy,
  Telegram). Un controllo **riferisce**, non aggiusta.

*Verifica*: una `DELETE` viene rifiutata; un controllo notturno arriva la
mattina dopo.

## FASE 7-bis — agent-reach: arrivare dove SearXNG non arriva

[agent-reach](https://github.com/Panniantong/agent-reach) risolve un problema
diverso da quello che pensavo. Non migliora il *ranking* della ricerca — quello
lo risolve Qdrant nella Fase 1. Serve ad **arrivare su piattaforme che una
ricerca normale non legge**: trascrizioni YouTube, thread Reddit, Twitter/X,
issue GitHub, feed RSS.

E' una CLI Python con un'architettura che vale la pena copiare: **canali** (un
modulo per piattaforma), **backend multipli con ricaduta** (cambiare metodo di
accesso = riordinare una lista, non riscrivere codice) e `doctor` che dice quali
backend funzionano. E' lo stesso schema di `backends.json`, applicato al web.

Integrazione prevista: uno strumento `web_reach(piattaforma, query)` che invoca
la CLI sul server. Da valutare con attenzione perche' porta dipendenze
(`yt-dlp`, `gh`, MCP server) e alcuni backend richiedono chiavi; si parte dai
canali senza chiave (YouTube, RSS, GitHub) e si aggiunge il resto solo se serve.

## FASE 8 — Il resto

- **Audio e video**: trascrizione con Whisper (fase 2) applicata ai file
  caricati; per i video, estrazione dell'audio con `ffmpeg`.
- **Clonazione vocale** (F5-TTS / XTTS-v2) per rispondere con la sua voce.
  La sua voce è sua; per voci di **altre persone reali** serve il loro consenso.
- **Repo → vault**: la documentazione del progetto dentro Obsidian, così Hermes
  e gli altri assistenti la leggono. Direzione unica: repo → vault, mai
  l'inverso, perché la fonte di verità resta git.
- **vLLM** al posto di Ollama sul PC, se lo sciame diventa l'uso normale.
- **Segreti**: percorsi gerarchici, versioning e audit, prendendo l'idea da
  [M-DNVault](https://github.com/Mohamed-DN/Password-manager) senza portarsi
  dietro OpenBao e Postgres (vedi `ESPOSIZIONE_E_SEGRETI.md` §3).

---

## Su Open WebUI

Il proprietario ha chiesto se conviene integrare Hermes lì. Open WebUI ha già
OIDC, caricamento file, RAG e un sistema di strumenti — è software valido.

Ma **manterrebbe due assistenti**: quello che sa di questa casa (identità,
ruoli, stato reale, vault, squadra di agenti) e quello generico. Le sue
funzioni si sovrappongono a quelle già costruite, e ciò che gli manca —
sapere chi sei, cosa puoi vedere, com'è fatta l'infrastruttura — è esattamente
il valore di Hermes.

**Raccomandazione**: tenerli separati. Open WebUI resta il posto dove si prova
un modello nuovo; Hermes resta l'assistente della casa. Se un domani serve
davvero una funzione che solo Open WebUI ha, si valuta allora — questa è una
decisione da prendere insieme, non da subire.

---

## Cosa serve dal proprietario

- **Il pulsante voce**: l'errore vero dalla console del browser (F12).
- **I link** di «Agent rich» e «omni route», mai arrivati.
- **Una decisione** su Open WebUI (sopra).
