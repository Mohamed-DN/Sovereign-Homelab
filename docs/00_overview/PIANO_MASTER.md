# PIANO MASTER — l'indice di tutto

> Aggiornato il **2026-08-01**. **Questo è il file da cui partire.** I piani erano
> finiti sparsi su cinque documenti: qui c'è l'elenco completo di tutto ciò che
> è stato chiesto, proposto o scoperto, con lo stato e il link a dove è
> descritto per esteso. Se una cosa non è in questa tabella, è stata dimenticata.
>
> **Cosa è cambiato il 2026-08-01, e perché conta.** Il proprietario ha
> guardato lo stato dei lavori e ha detto: *«mi sa che tante cose mancano»*.
> Aveva ragione, e il motivo non era un errore sui fatti: era che due sessioni
> di lavoro avevano consegnato tre pezzi di **fondamenta** (Guardrail,
> interruttore, Verificatore) che sono giusti e necessari ma che lui **non
> vede**. Da qui in avanti l'ordine è cambiato: **prima quello che si usa**.
> Il conto vero delle undici voci del suo documento di progetto sta in
> [PIANO_MOMO_DIGITAL_TWIN](PIANO_MOMO_DIGITAL_TWIN.md) §4, e le sue dodici
> richieste di quel giorno al §4-ter.

---

## 1. I documenti

| Documento | Cosa contiene |
|---|---|
| [PIANO_GENERALE.md](PIANO_GENERALE.md) | **LA FILA DA SEGUIRE (2026-07-31)**: venti punti, dal recupero di tutte le sessioni archiviate. Contiene le undici voci che erano state dimenticate, le tre valutazioni (Langfuse sì, LangChain no, OmniRoute+OpenRouter) e l'automazione add/drop dei servizi. **Sostituisce ORDINE_DEI_LAVORI come fila di lavoro** |
| [HERMES_PIANO_A_FASI.md](HERMES_PIANO_A_FASI.md) | **Il piano operativo**: fasi 0-8, ognuna con la sua verifica |
| [HERMES_ARCHITETTURA_COMPLETA.md](HERMES_ARCHITETTURA_COMPLETA.md) | Dove sta ogni pezzo, memoria fuori dal modello, modalità master, voce, privacy |
| [PIANO_HERMES_ESPANSO.md](PIANO_HERMES_ESPANSO.md) | Voce, web, LLM gratuiti, assistente realtime, creazione contenuti, n8n |
| [PIANO_HERMES_CANALI_E_DB.md](PIANO_HERMES_CANALI_E_DB.md) | Motori oltre Ollama, Telegram, **perché no WhatsApp**, database, controlli |
| [hermes.md](../04_apps/hermes.md) | Il runbook del servizio: com'è fatto, come si ripara |
| [hermes-memoria.md](../04_apps/hermes-memoria.md) | **La memoria**: i tre archivi, le due bugie chiuse, il costo misurato degli embedding |
| [sovereign-interruttore.md](../04_apps/sovereign-interruttore.md) | **A4**: l'interruttore RUNNING/PAUSED, condiviso da Hermes, Momo e l'agente app |
| [sovereign-verificatore.md](../04_apps/sovereign-verificatore.md) | **A3**: il Verificatore degli allarmi, dentro il relay su LXC 101 |
| [omniroute.md](../04_apps/omniroute.md) | **Il gateway** verso i fornitori esterni: cosa funziona e cosa manca |
| [ORDINE_DEI_LAVORI.md](ORDINE_DEI_LAVORI.md) | **Da dove si comincia**: tutte le idee in fila, il criterio che decide l'ordine, e la verifica di ognuna. Se non sai cosa fare, apri questo |
| [PIANO_MOMO_DIGITAL_TWIN.md](PIANO_MOMO_DIGITAL_TWIN.md) | **Cosa Momo deve saper fare**: il Sinker a 4 fasi (per stare in 16 GB di VRAM), il Guardrail anti-allucinazione, la libreria di automazione, le sandbox con ciclo di vita, la squadra a grafo, la voce in tempo reale |
| [PIANO_AGENT_MOMO.md](PIANO_AGENT_MOMO.md) | **La fusione dei due Hermes**: il nostro cuore dentro il corpo di `hermes-agent`. Scritto dopo averne letto il codice, non le note di rilascio. Cinque fasi, il registro delle divergenze dal loro codice, e cosa si perde davvero |
| [PIANO_ESECUTIVO_2026-08.md](PIANO_ESECUTIVO_2026-08.md) | **Il piano da eseguire**: catalogo modelli, router per intenti, pannello rifatto, email alle persone, **modalità MASTER**, hermes-agent, voce. Passo per passo, con la verifica di ognuno |
| [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md) | **Il perché di tutto**: i tre principi, le trappole già pagate, il prossimo passo, le decisioni che aspettano. Da leggere per prima cosa quando si riprende il lavoro |
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
| 18 | **Scrittura su Obsidian**: `vault_scrivi`, confinata a `07 Notes/Hermes/`, con un utente CouchDB separato. Verificata: scritta e arrivata sul disco in 10 s | [memoria](../04_apps/hermes-memoria.md) |
| 19 | **Procedure** in Postgres (non fra i vettori: i passi tornano esatti), trovabili per significato | [memoria](../04_apps/hermes-memoria.md) |
| 20 | **AWS Bedrock** come motore, `private: false`. Verificato che riceve 2 strumenti su 16 | [visione](VISIONE_COMPLETA.md) §7 |
| 21 | Pannello impostazioni: pulsante Salva sempre visibile, Invio salva, preset Bedrock | — |
| 17 | **OmniRoute** installato, dietro SSO, con `/v1` esente e chiave API. Motore non privato in `backends.json` | [omniroute](../04_apps/omniroute.md) |
| **S5** | Porte di OmniRoute chiuse alla LAN (`DOCKER-USER`): erano aperte a chiunque conoscesse la password condivisa | [omniroute](../04_apps/omniroute.md) §6 |
| **S6** | Archivi della memoria in ascolto **solo** su loopback, con password e chiave API anche lì | [memoria](../04_apps/hermes-memoria.md) §1 |
| 22 | **PWA (W7.1)**: manifest, service worker (solo la scocca, mai le risposte), icone generate a runtime via `zlib`. Route esenti dal login SSO in NPM | [hermes.md](../04_apps/hermes.md) §7-quinquies |
| 23 | **Catalogo modelli (W1)**: 19 modelli in `models-catalog.json`, scarica/elimina dal pannello con progresso SSE, dimensione letta dal vivo da `/api/tags`. Verificato: `granite4:micro` scaricato ed eliminato dal browser | [hermes.md](../04_apps/hermes.md) §7-quater |
| 24 | Motore **Groq** (fornitore gratuito, W2 in anticipo): chiave fornita dal proprietario, `private:false`. Trovato e chiuso un difetto generale di `http_json()`: Cloudflare blocca lo User-Agent di default di `urllib` | [hermes.md](../04_apps/hermes.md) §7-quater |
| 25 | **Fornitori come preset (W2.1)**: 9 preset, menu "+ fornitore" al posto del bottone unico Bedrock. Solo Groq verificato con chiave reale, gli altri dichiarati "letti, non provati" | [hermes.md](../04_apps/hermes.md) §7-sexies |
| 26 | **Router per intenti (W2.2)**: 5 rotte, `privato` non può mai cadere su un motore non privato — verificato anche contro un tentativo esplicito di forzarlo dal menu motore | [hermes.md](../04_apps/hermes.md) §7-sexies |
| 27 | **Strategie di scelta (W2.3)**: `ordine`/`piu_veloce`/`meno_carico`, default invariato | [hermes.md](../04_apps/hermes.md) §7-sexies |
| 28 | **Rubrica (W4)**: tabella `contacts`, `rubrica_aggiungi/cerca/elenco`, `send_mail` con `destinatario` per nome. Un indirizzo mai visto viene rifiutato, mai inventato. Verificati dal vivo tutti e cinque i percorsi (aggiunta, ricerca per nome/email, invio riuscito, doppio rifiuto) | [hermes.md](../04_apps/hermes.md) §7-septies |
| 30 | **Modalità MASTER (W5)**: azioni come dati (8 nel catalogo), segreti per riferimento, divieto assoluto compilato a codice e **riconfermato dal proprietario**, armamento con scadenza a 30 min, interruttore RUNNING/PAUSED, registro con i rifiuti. Tutte e sette le verifiche passate. Manca la chiave SSH master per le azioni su Proxmox: finché non c'è, falliscono dicendolo | [hermes.md](../04_apps/hermes.md) §7-novies |
| **S7** | **La guardia anti-bugia era spenta in modalità sciame**: `tools=[]` per la sintesi disattivava anche il controllo «hai detto di aver fatto e non hai chiamato niente». Trovato perché Hermes ha inventato un report su una mail mai inviata. Corretto con `guard_tools` | [hermes.md](../04_apps/hermes.md) §7-septies |
| 29 | **Pannello a schede (W3)**: Motori/Modelli/Fornitori/Rotte/Memoria/Rubrica, badge privato+latenza sui motori, editor rotte, stato memoria con reindicizza, rubrica con form. **Trovato e chiuso un difetto che aveva reso l'intero pannello vuoto dal vivo dal momento di W1**: `\n` scritto in una tripla-stringa Python diventava un a-capo vero nel JS, mandando in crash l'intero `<script>` al parse — nessun errore visibile, solo un pannello che sembrava aver perso tutti i motori | [hermes.md](../04_apps/hermes.md) §7-octies |
| 31 | **Guardrail (Momo, fase 4)**: `hermes_guardrail.py`, un file di sola libreria standard importato da Hermes **e** Momo, tre regole deterministiche + uno stadio LLM facoltativo solo su motori di casa. **Chiuso anche nell'Hermes vivo** un buco vero (uno strumento fallito contava come fatto) e nel plugin di memoria di Momo (gli strumenti di memoria erano visibili, non eseguibili, a un motore esterno). Contato dal vivo: motore di casa 20 strumenti, motore esterno 1 (piu' la web_search di hermes-agent, che dal 2026-08-02 sostituisce la nostra) | [momo-guardrail.md](../04_apps/momo-guardrail.md) |
| **S8** | **`ai.internal` (Open WebUI) aveva l'iscrizione libera aperta, con nessun admin ancora rivendicato**: chiunque sulla VPN/LAN arrivasse per primo diventava proprietario dell'istanza, con accesso diretto e senza guardie a Ollama — nessuna memoria, nessun filtro privato/pubblico, nessun Guardrail, nessuna delle protezioni che Hermes e Momo hanno. È un host «VPN only» per scelta scritta (non passa da Authentik come `hermes.internal`), ma l'iscrizione doveva comunque essere chiusa. `ENABLE_SIGNUP=False` in `stacks/ai-ollama/.env`, verificato: `/api/config` ora dichiara `enable_signup:false`. **Nessun account admin esiste ancora**: creerlo (o decidere di spegnere il servizio) resta una scelta del proprietario, non presa qui | `stacks/ai-ollama/docker-compose.yml` |
| 32 | **A4 — interruttore RUNNING/PAUSED**: `sovereign_switch.py`, un solo file condiviso da Hermes, Momo e l'agente app. Verificato dal vivo: in pausa `esegui_azione_master` rifiutato con motivo, la chat risponde ancora, l'agente app dà 423, `armed_until` di MASTER sopravvive alla pausa | [sovereign-interruttore.md](../04_apps/sovereign-interruttore.md) |
| 33 | **A3 — il Verificatore**: `sovereign_verifier.py` dentro il relay. **Trovato e chiuso prima del deploy**: LXC 101 non si fidava della CA interna, il che avrebbe confermato ogni allarme come vero. Verificato dal vivo: `files.internal` sano → `FALSE_ALARM`, un host inesistente → `REAL_CRITICAL` | [sovereign-verificatore.md](../04_apps/sovereign-verificatore.md) |
| 34 | **Momo su Telegram**: `@dn_momo_bot` risponde davvero, `momo-gateway.service`, allowlist di un id solo. **Momo non era nemmeno un servizio** prima di oggi | [momo-telegram.md](../04_apps/momo-telegram.md) |
| 35 | **La voce, in tutti e due i sensi**: capisce i vocali (faster-whisper, lingua riconosciuta da sola) e risponde a voce (Piper, tre voci una per lingua). **Nessun codice nostro**: l'impianto audio è tutto loro, bastava configurarlo — e quattro difetti di configurazione fallivano in silenzio | [momo-telegram.md](../04_apps/momo-telegram.md) §3-bis |
| 36 | **Il layer delle lingue**: modulo deterministico it/en/ar, 37 casi di test. Decide dall'**alfabeto** (l'arabo è certo anche su una trascrizione storpiata) poi dalle parole funzione, e **se non è sicuro non forza niente**. Verificato sul vocale arabo vero: confidenza 1.00 | `scripts/hermes/sovereign_language.py` |
| 37 | **La persona di Momo**: rispondeva come «Hermes Agent di Nous Research» perché il `SOUL.md` di default non era mai stato sostituito. Ora è la persona di casa, con le tre lingue madrelingua, il nome arabo del proprietario, il warning prima di scrivere e il calcolo prima di espandere un disco | `scripts/momo/SOUL.md` |
| **S9** | **Il filtro privato/pubblico giudicava un motore dal solo NOME del provider**, e `custom` è ugualmente vero per Ollama sul PC e per OmniRoute, che inoltra fuori. Con il primo fallback esterno il vault sarebbe andato a un fornitore. Ora giudica anche il `base_url` con un elenco esplicito, e considera **tutti** i motori configurati perché `pre_tool_call` non riceve chi sta rispondendo. Verificato: OmniRoute su un IP di casa risulta correttamente **non** di casa | `scripts/momo/sovereign_tools/__init__.py` |

---

## 2-bis. COSA MANCA — un elenco solo, in ordine di quanto conta

> Aggiunto il **2026-08-03** su richiesta del proprietario: «organizzalo per
> bene, elencami le cose che mancano». Le fasi qui sotto (§3) restano perché
> raccontano *come* si è arrivati fin qui; questa tabella risponde all'unica
> domanda che serve aprendo il file: **cosa resta da fare, e da dove comincio.**
>
> L'ordine non è per difficoltà ma per **cosa costa non averlo**.

| # | Cosa manca | Perché sta qui | Dove |
|---:|---|---|---|
| 1 | **A PC spento il primo messaggio aspetta**, e quanto non lo so ancora | il ripiego ora è corretto (`qwen2.5:3b`, tutto in GPU) ma scatta solo dopo i tentativi sul PC. **Misurato davvero**: 3,1 s per tentativo (è il timeout ARP verso una macchina spenta) e `api_max_retries` era 3. **NON misurato**: il totale, perché fra un tentativo e l'altro c'è un ritardo crescente e non esiste un comando a colpo singolo da cronometrare — e non spengo il servizio vivo per farlo. Il «15-20 s» che avevo detto era una stima mia, non una misura. Fatto intanto: `api_max_retries` da 3 a **2**, che riduce l'attesa qualunque sia il ritardo. Il numero vero si legge alla prossima assenza vera del PC: `journalctl -u momo-gateway \| grep 'trying fallback'` e la distanza dal messaggio precedente | §5 |
| 2 | **Una risposta in arabo viene letta dalla voce italiana** | le tre voci sono installate, ma `tts.piper.voice` accetta **un** nome e a monte non c'è scelta per lingua. Serve una divergenza dichiarata | [architettura](ARCHITECTURE_AND_DATA_FLOWS.md) |
| 3 | **Momo non sa cercare dentro Nextcloud** | fra `vault_search` e `web_search` non c'è niente, e lì stanno i file pesanti | [punto 18-bis](PIANO_GENERALE.md) |
| 4 | **Tappa 5 del testimone**: fermare `sovereign-hermes` | il nome è uscito il 2026-08-03; resta il processo. Ha una condizione: giorni di pannello usato davvero | [testimone](PIANO_TESTIMONE_HERMES_MOMO.md) |
| 5 | **Perché Nextcloud cade** | escluso quasi tutto; il registratore è installato e aspetta il prossimo episodio | [nextcloud](../04_apps/nextcloud.md) §7.1 |
| 6 | **Armare MASTER da Telegram** | tecnicamente banale (il file di stato è condiviso). È una **decisione di sicurezza**, non di comodità: serve la sua parola | §3 fase 6 |
| 7 | **`db_query` in sola lettura** + Oracle thin | il proprietario è DBA e non può interrogare i propri database da Momo | §3 fase 7 |
| 8 | **Controlli programmati** | domanda + orario + dove riferire. Un controllo **riferisce**, non aggiusta | §3 fase 7 |
| 9 | **Google Calendar** | gli appuntamenti stanno solo nell'agenda interna. Serve OAuth | §3 fase 3 |
| 10 | **Mostrare il ragionamento** | il campo `thinking` arriva già, viene scartato | §3 fase 4 |
| 11 | **Clonazione voce** (XTTS-v2) | il copione in tre lingue è pronto: **servono le sue registrazioni** | §6 |
| 12 | **`agent-reach`** | YouTube, Reddit, X, GitHub, RSS dove SearXNG non arriva | [punto 19](PIANO_GENERALE.md) |
| 13 | **Langfuse** | vedere cosa fa davvero un turno, invece di dedurlo dai log | [punto 5](PIANO_GENERALE.md) |
| 14 | **`sovereign-service.py new/drop`** | aggiungere un servizio è ancora una procedura a mano di dodici passi | [punti 6-7](PIANO_GENERALE.md) |
| 15 | **SSO su Proxmox e PBS** | sono gli unici due amministrativi ancora fuori da Authentik | [ROADMAP](ROADMAP.md) §1 |
| 16 | **Healthcheck CouchDB rotto** | sonda senza credenziali → `401` a ogni giro: un allarme sempre acceso maschera il prossimo vero | §3 fase 9 |
| 17 | **Account orfano Immich**, **Forgejo `ACCOUNT_LINKING=auto`** | due residui di identità, stessa classe di rischio dell'incidente Jellyfin | §4 |
| 18 | **Ente Photos** per la sorella | l'unica risposta vera a «non voglio che l'admin veda le mie foto» | [privacy](../06_operations_security/PRIVACY_E_VISIBILITA_DATI.md) §4 |

**Aspettano una decisione sua, non un lavoro mio**: Ceph acceso a vuoto
sull'host, i plugin di Time Garden che restano sul solo PC, e le voci 6, 11 e
18 qui sopra.

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
| Registratore **nella pagina** di Hermes | resta da fare, ma **non è più la strada più corta**: la voce via Telegram (sotto) costa molto meno | da fare |
| **Whisper** per capire | ✅ **fatto 2026-08-01 su Momo**: `faster-whisper==1.2.1` sul server, riconoscimento automatico della lingua. Sul PC (GPU) resta da fare, e sarà solo più veloce | ✅ parziale |
| **Piper** sul server | ✅ **fatto 2026-08-01**: tre voci, `it_IT-paola` · `ar_JO-kareem` · `en_US-amy`, una per lingua | ✅ |
| **Clonazione voce** (XTTS-v2) | la sua voce; per voci di altri serve il loro consenso | da fare |
| Audio e video caricati | `ffmpeg` ora c'è su LXC 102; l'audio in ingresso funziona via Telegram | parziale |
| **Layer delle lingue** *(non era in nessun piano)* | ✅ **fatto 2026-08-01**: modulo deterministico it/en/ar, 37 casi di test. Chiesto dal proprietario: *«metti un layer forte, fallo bene anche se ci vuole tanto tempo»* | ✅ |

### Fase 3 — Hermes in tasca

| Cosa | Nota | Stato |
|---|---|---|
| **Telegram** (bot ufficiale, long polling) | ✅ **FATTO E VERIFICATO 2026-08-01**: `@dn_momo_bot` risponde, `momo-gateway.service` su LXC 102, allowlist con un id solo catturato da `getUpdates`. Nessuna porta aperta. Con Momo arrivano tutte le guardie senza codice in più | ✅ [runbook](../04_apps/momo-telegram.md) |
| **Telegram con audio** | ✅ **fatto 2026-08-01**: capisce i vocali (faster-whisper) e risponde a voce (Piper), modalità `voice_only` — audio solo se l'ingresso era un vocale | ✅ |
| **Momo è un servizio** *(non era in nessun piano)* | ✅ girava solo da riga di comando fino al 2026-08-01. È anche un prerequisito del punto 21 | ✅ |
| **PWA** per iPhone | `manifest.json`, service worker, icone | ✅ (W7.1) |
| App iOS nativa | solo se la PWA non basta: serve Mac + account Apple | valutare |
| **WhatsApp** | **escluso**: ban del numero entro 2-8 settimane, e dal 15/01/2026 vietati i chatbot di terze parti | [motivazione](PIANO_HERMES_CANALI_E_DB.md) §3 |
| **Google Calendar** | Chiesto dal proprietario il 2026-07-30: fissare appuntamenti/colloqui sul calendario vero, non solo nell'agenda interna di Hermes (`agenda_aggiungi`). Serve OAuth Google e uno scope calendario — disegno da fare quando si arriva qui, dopo W7 | da fare |

### Fase 4 — Vault e trasparenza

| Cosa | Nota | Stato |
|---|---|---|
| **Scrivere sul vault** Obsidian | ✅ **fatto**: `vault_scrivi` scrive nel formato a pezzi di LiveSync, con un utente CouchDB separato e **confinato a `07 Notes/Hermes/`**. Verificato: la nota è arrivata sul disco in 10 s e la sincronizzazione non si è rotta | ✅ |
| Scrivere **fuori** da quella cartella | volutamente non permesso: è il confine che rende vera la frase «Hermes non può danneggiare il vault» | per scelta |
| **Mostrare il ragionamento** (`thinking`) | il campo esiste già, oggi lo scarto | da fare |
| **Repo → vault**: la documentazione dentro Obsidian | ~~da fare~~ — **fatto 2026-07-31**: `Sync-DocsToVault.ps1` + task ogni 30 min, verificato (98 file su disco) | ✅ |

### Fase 5 — Motori esterni

| Cosa | Nota | Stato |
|---|---|---|
| Regola **`private`** | **fatta**: motore esterno → solo strumenti web | ✅ |
| **OmniRoute** (sostituisce LiteLLM) | 290+ fornitori, 40+ gratuiti, circuit breaker, chiavi AES-256 | da installare |
| Provider gratuiti | Preset in `providers-presets.json` (W2.1): solo **Groq** verificato con chiave reale, gli altri sette pronti ma non provati | parziale |
| **vLLM** al posto di Ollama sul PC | solo se lo sciame diventa l'uso normale; su Blackwell serve CUDA 12.8+ | valutare |

### Fase 6 — Modalità master ✅ FATTA, e ora vale anche per Momo

| Cosa | Nota | Stato |
|---|---|---|
| Elenco di **azioni permesse** (non una shell libera) | ✅ `actions.json`, **10 azioni** (erano 8; il 2026-08-01 si aggiungono `spazio_pool` ed `espandi_disco`). Il modello **sceglie** da un elenco, non compone comandi | ✅ |
| Conferma esplicita per l'irreversibile | ✅ campo `conferma` per azione. `espandi_disco` la chiede: un disco cresciuto non si rimpicciolisce | ✅ |
| Scadenza a 30 minuti, registro non riscrivibile, interruttore d'emergenza | ✅ tutti e tre. L'interruttore è ora [globale](../04_apps/sovereign-interruttore.md) (A4), non più solo di MASTER | ✅ |
| **MASTER dentro Momo** | ✅ **verificato 2026-08-01 e c'era già**: `sovereign_tools` registra ogni strumento di Hermes, quindi MASTER era lì dalla Fase 3. Condivisi catalogo, divieto, armamento, registro e chiave SSH — **armare dal pannello di Hermes arma anche Momo** | ✅ |
| **Espandere un disco** *(chiesto il 2026-08-01)* | ✅ `spazio_pool` per calcolare + `espandi_disco`. Rimpicciolire è **impossibile per costruzione**: l'incremento è un enum di soli valori positivi, non un controllo aggirabile | ✅ |
| Armare MASTER **da Telegram** | il file di stato è condiviso, quindi tecnicamente basta poco. È una decisione di **sicurezza**, non di comodità: chi arma autorizza azioni sull'impianto | da fare |
| Allargare il catalogo (il «tutto tutto tutto» chiesto) | ogni azione nuova entra come **dato** in `actions.json`, con parametri vincolati da enum o regex | in corso |

*Verifica del divieto assoluto, interrogato **da Momo mentre era armato** (2026-08-01):
`qm stop 110`, `qm destroy 110`, `zfs destroy`, `rm -rf`, fermare PBS e toccare
`actions.json` tutti **rifiutati**; `df -h` permesso.*

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

### Fase 9 — Recuperate il 2026-07-31 (non erano in nessuna tabella)

> Emerse rileggendo le quattro sessioni archiviate e i file di memoria. La
> regola di questo documento dice che ciò che non è in tabella è stato
> dimenticato: queste lo erano. Dettaglio e ordine in
> [PIANO_GENERALE.md](PIANO_GENERALE.md).

| Cosa | Nota | Stato |
|---|---|---|
| **Repo → vault Obsidian** | chiesto dal 2026-07-15, mai costruito fino ad oggi. **Costruito ed eseguito il 2026-07-31**: `scripts/windows/Sync-DocsToVault.ps1` + task ogni 30 min, verificato dal vivo (98 file copiati). CouchDB aspetta la prossima apertura di Obsidian | ✅ |
| **Healthcheck CouchDB rotto** | sonda `/` senza credenziali, CouchDB risponde `401`: **282 giri falliti**. Il servizio è vivo, l'allarme è falso — e un allarme sempre acceso maschera il prossimo vero | da fare (punto 1) |
| **Due cartelle `VaultMohamed`** | una in `Documents\VaultMohamed\VaultMohamed` (con `.obsidian`, quella viva), una in `C:\Users\Mohamed\VaultMohamed`. Da chiarire prima di scrivere nel vault | da fare (punto 1) |
| **Primo login OIDC su Headplane** | ~~porta aperta~~ — **verificato 2026-07-31: già fatto** il 2026-07-14 (commento nel compose di `core-network`). La nota di memoria era scritta a metà lavoro | ✅ |
| **Ruotare la password admin riusata** | issue #2 §6b, aperta dal 2026-07-14 | da fare (punto 2) |
| **Ritirare `headscale-ui`** | ~~da fare~~ — **verificato 2026-07-31: già fatto** il 2026-07-14, nessun container in nessun LXC | ✅ |
| **`authentik-server` si riavvia da solo** | scoperto verificando quanto sopra: riavvii non programmati causano 503 transitori sulla discovery OIDC di Headplane. Non blocca, ma la causa non è nota | da capire (punto 2, R12) |
| **Interruttore RUNNING/PAUSED (A4) e Verificatore (A3)** | ~~da fare~~ — **fatto e verificato il 2026-08-01**, vedi voci 32-33 sopra | ✅ |
| **Momo sostituisce Hermes** | implicito nella Fase 5 di [PIANO_AGENT_MOMO](PIANO_AGENT_MOMO.md) ma mai messo in fila con i suoi prerequisiti veri, fino a oggi: punto 21 di [PIANO_GENERALE](PIANO_GENERALE.md) | da fare, dopo la Fase 4 della fusione |
| **Persistere la finestra metriche** | ~~da fare~~ — **verificato 2026-07-31: già fatto**, `metrics-long.jsonl` ha 25 985 campioni (~18 giorni) | ✅ |
| **Potare lo snapshot VM110 `preimmich_v302`** | ~~da fare~~ — **non esiste più**: sostituito da `preimmich_auto_1785405203` (rollback dell'update del 30/7), ancora nella sua finestra di 24h | ✅ |
| **Deprovisioning a scadenza** | tolto un ruolo, dopo una settimana si cancella il profilo sul servizio (chiesto il 2026-07-13) | da verificare |
| **SSO Tier 1: Proxmox e PBS** | Paperless fatto, questi due no ([ROADMAP](ROADMAP.md) §1) | da fare |
| **`agent-reach`** | passato il 2026-07-29: YouTube, Reddit, X, GitHub, RSS dove SearXNG non arriva | da fare (punto 19) |
| **Open WebUI** | domanda chiusa: **spento e rimosso**, verificato sul vivo il 2026-07-31 (container assente, porta 3004 muta) | ✅ |
| **Langfuse (A7)** | confermato come scelta migliore. Nota: **ClickHouse ha acquisito Langfuse il 2026-01-16** — resta MIT e self-hostable | da fare (punto 5) |
| **`sovereign-service.py new` / `drop`** | richiesta del 2026-07-31: automatizzare la parte comune, censire la variabile in un manifesto, e un drop pulito che di default **non tocca i dati** | da fare (punti 6-7) |
| **Momo crea contenuti** | testo, voce (Piper), montaggio (`ffmpeg`), immagini (ComfyUI solo se avanza VRAM). Vincolo confermato: niente volti, esseri viventi, musica | da fare (punto 16) |

---

## 4. Fuori da Hermes — cose dell'impianto rimaste aperte

| Cosa | Nota | Stato |
|---|---|---|
| **Nextcloud 502 intermittente** | diagnosticato: il backend rifiuta le connessioni ~1 volta su 4, ogni ~5 minuti. Backend sano 20/20 se interrogato diretto. **Serve accesso SSH alla VM 120**, oggi non autorizzato | bloccato |
| ~~Monitor Kuma per Hermes~~ → **per Momo** | ✅ **fatto 2026-08-03**, id 49, `https://momo.internal/`, 60s, 2 tentativi. Batte 200 OK. Il vecchio blocco («niente API REST, e su LXC 101 manca l'uscita internet») è **caduto**: l'uscita c'è, e il client 1.x non serve — Kuma 2.4 ha riscritto l'API ma gli **eventi** sono gli stessi, letti nel loro `server.js` e provati sul vivo. Strumento riusabile: `scripts/sovereign-kuma-monitor.py` | ✅ |
| **Kuma era raggiungibile senza login da tutta la LAN** | scoperto il 2026-08-03 mentre creavo il monitor. `disableAuth = true` (l'autenticazione è delegata ad Authentik davanti a `status.internal`) **ma Docker pubblica la 3001 su 0.0.0.0**, e quel percorso non passa da NPM: collegandosi col socket nudo arrivavano `monitorList`, `apiKeyList` e `certInfo` **senza fare login**. È il terzo caso dello stesso schema in questa casa (Ollama sul PC, OmniRoute su LXC 102). Chiuso con `sovereign-kuma-firewall.sh` + unit, sullo stesso modello di OmniRoute | ✅ |
| ~~Tolleranza monitor Nextcloud~~ | **da NON fare, e la ragione conta.** Misurato il 2026-08-03: il monitor ha già `maxretries=3` a 60s, quindi un singolo 502 dà giallo, non rosso. Diventa rosso perché gli episodi durano **4-8 minuti veri**. Alzare i tentativi non toglierebbe un falso allarme: nasconderebbe un guasto vero. La strada giusta è il registratore già installato sulla VM 120 | ✅ chiusa con una decisione |
| **Ente Photos** per la sorella | l'unica risposta tecnica vera a «non voglio che l'admin veda le mie foto»: cifratura end-to-end | [privacy](../06_operations_security/PRIVACY_E_VISIBILITA_DATI.md) §4 |
| **Account orfano Immich** `luna222@gmail.com` | 0 foto, l'utente Authentik non esiste più | da pulire |
| **Forgejo `ACCOUNT_LINKING = auto`** | unisce gli account per email: stessa classe di rischio dell'incidente Jellyfin | da valutare |
| Escludere `06 Templates/Images` dalla sincronizzazione | **36 MB** misurati di mp3/gif scaricati da ogni dispositivo | opzionale |
| **Time Garden**: la nota giornaliera nasceva col template grezzo | Causa trovata leggendo il codice dei due plugin: **corsa all'avvio** — `journals` con `openOnStartup` crea la nota prima che Templater sia caricato, non trova la sua API e incolla il testo letterale. Aggravante: la config di Time Garden usa `trigger_on_file_creation_mode`, **un'impostazione che in Templater non esiste**. Corretto: template a `journals` (che sa chiamare Templater da solo), `openOnStartup` spento, `trigger_on_file_creation` spento perché non deve intromettersi sul file vuoto | ✅ da confermare con un clic |
| **Momo non sa cercare dentro Nextcloud** | chiesto il 2026-08-03: «i software pesanti vanno su Nextcloud, l'AI cerca lì e poi sul web». Verificato contando gli strumenti: c'è `vault_search` per le note e `web_search` per fuori, **in mezzo niente**. Disegno completo, vincoli e le due strade (solo nomi / tutto testo) nel punto **18-bis** del [PIANO_GENERALE](PIANO_GENERALE.md) | da fare |
| **`rustdesk.internal` puntava al proxy invece che al server** | trovato il 2026-08-03 rispondendo a «come mi collego al PC dal Mac». Il nome cadeva nella riscrittura generale `*.internal → .50` (NPM), ma RustDesk usa TCP/UDP grezzi che un proxy HTTP non inoltra: la 21116 su `.50` è muta, su `.52` risponde. Chi seguiva il runbook aveva un client che non si registrava mai. Aggiunta la riscrittura specifica in AdGuard, come già per `ca.internal` | ✅ |
| **Password di AdGuard non registrata** | era «TODO: fill manually» da giugno: senza, ogni modifica al DNS richiede di editare il file e riavviare il servizio — 9 secondi di DNS fermo per tutta la casa. Registrata il 2026-08-03 in `/root/sovereign-secrets/adguard-admin` (0600) e provata contro l'API: la prossima modifica passa dall'API e non ferma niente | ✅ |
| **I motori FUORI CASA non hanno mai funzionato** | `momo-motore` scriveva la chiave in `CUSTOM_API_KEY`, che con provider `custom` **non viene mai letta**: hermes-agent deriva il nome della variabile dall'HOST del base_url (`_host_derived_api_key`), quindi per openrouter.ai cerca `OPENROUTER_API_KEY`. Il provider nasceva con `api_key: ''` e l'agente moriva con «No LLM provider configured». I motori di casa non lo mostravano perche' a Ollama la chiave non serve. Trovato il 2026-08-04 dai log della notte in cui Mohamed era rimasto senza assistente. Corretto: ogni motore dichiara il suo `key_env` | ✅ |
| **Il rimedio della GPU al boot non reggeva** | `nvidia-modprobe` NON ricrea i nodi se il driver e' gia' inizializzato: ritorna 0 senza fare niente. Al riavvio del 2026-08-03 19:20 la GPU non era ancora enumerata tre secondi dopo il modulo, il comando singolo e' fallito, e Ollama e' rimasto giu' nove ore. Ora uno script che RIPROVA e usa anche `nvidia-smi`, che aprendo la scheda i nodi li crea davvero | ✅ |
| I plugin di Time Garden restano **sul solo PC** | LiveSync ha `syncInternalFiles = false`: `.obsidian` non si sincronizza. Sul telefono i plugin vanno installati a parte, o si attiva la sincronizzazione dei file nascosti | da decidere |

---

## 5. Difetti noti di Hermes, da non dimenticare

| Difetto | Nota |
|---|---|
| Il modello **finge di usare gli strumenti** | **mitigato, non guarito.** Gli ordini espliciti ora li esegue il codice, e una pretesa non verificata viene dichiarata all'utente ([memoria](../04_apps/hermes-memoria.md) §4). Ma su una richiesta indiretta `qwen3.5:9b` può ancora saltare uno strumento senza che nessuno se ne accorga |
| ~~La ricerca nel vault è **primitiva**~~ | **risolta**: 125 note indicizzate in Qdrant, cerca per significato. La ricerca a parole resta come ripiego dichiarato |
| Gli strumenti dei sotto-agenti non sono visibili in pagina | si vede il piano, non le singole chiamate. Lo risolverebbe **Langfuse** (vedi il piano di aggiornamento) |
| Il pulsante voce non registra | vedi fase 2: non è un bug, è una parte mai costruita |
| ~~Il **motore degli embedding sulla CPU è 180× più lento**~~ | **spiegato e ridotto**: LXC 102 aveva 4 core su 40. Portato a 16, da 17,7 s a 3,6 s ([analisi del carico](../01_proxmox_foundation/ANALISI_CARICO_2026-07-30.md) §2). Resta 37× la GPU: la corsia lenta è lenta per natura |
| **Ceph gira a vuoto sull'host** | 0 OSD, 0 pool, 0 dati, ~770 MB di RAM e un `HEALTH_WARN` permanente che maschera i prossimi avvisi veri. **Aspetta una decisione**: fermarlo, o tenerlo per un secondo nodo futuro ([analisi](../01_proxmox_foundation/ANALISI_CARICO_2026-07-30.md) §3) |
| Il database di OmniRoute **non è cifrato** a riposo | nonostante `STORAGE_ENCRYPTION_KEY`. Le chiavi dei fornitori dentro invece lo sono ([omniroute](../04_apps/omniroute.md) §6) |

---

## 6. Serve dal proprietario

- L'errore vero del pulsante voce dalla console del browser (F12).
- Una decisione su **Open WebUI** (tenerli separati è la raccomandazione).
- Autorizzazione SSH alla **VM 120** per chiudere il caso Nextcloud.
- Se vuole **Ente Photos** per la sorella, o se preferisce restare com'è.
