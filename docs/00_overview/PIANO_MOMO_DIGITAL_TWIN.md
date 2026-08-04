# Agent Momo — da assistente a gemello digitale autonomo

> Documento di progetto consegnato dal proprietario il 2026-07-30, trascritto
> qui con le osservazioni tecniche di chi dovrà eseguirlo. Va letto **dopo**
> [PIANO_AGENT_MOMO.md](PIANO_AGENT_MOMO.md), che descrive la fusione con
> `hermes-agent`: questo documento dice cosa Momo deve **saper fare** una volta
> che il corpo e il cuore sono a posto.
>
> Le fasi 1 e 2 della fusione (respiro e memoria condivisa) sono già fatte e
> verificate. Quanto segue si costruisce sopra quelle.

---

## 1. L'obiettivo, con le sue parole

Evolvere Momo da sistema RAG avanzato a **gemello digitale autonomo**: capace
di ragionare su situazioni inedite, usare strumenti statistici, apprendere in
continuo, gestire il ciclo di vita completo di ambienti sandbox (creazione e
distruzione), mantenere una propria libreria di automazione, e **filtrare le
proprie allucinazioni**.

L'ultima è la più importante, ed è anche quella che questo impianto ha già
pagato tre volte: un modello che dice «ho salvato» con il database vuoto, uno
che riferisce un invio fallito su una mail consegnata, e — oggi stesso — uno
che ha prodotto un report tecnico dettagliato su una mail che non aveva mai
mandato. Il Guardrail della Fase 4 non è un abbellimento: è la risposta
strutturale a un difetto documentato.

## 2. Il vincolo che decide il disegno: 16 GB di VRAM

L'inferenza gira in casa, su una RTX 5070 Ti. Un modello che deve analizzare,
decidere, calcolare, rispondere e verificarsi **in una sola chiamata** o non ci
sta in memoria, o ci sta al prezzo di un contesto ridicolo.

Il **Momo's Sinker** divide il lavoro in quattro fasi, e fra una fase e
l'altra la VRAM si libera. È così che un modello da 7B o 14B produce una catena
di ragionamento che di solito richiede un modello molto più grande.

```
  utente
     │
     ▼
 ┌────────────────────────────────────────────────────────┐
 │ FASE 1 · SINK        LLM leggero                       │
 │ Non risponde. Capisce. Produce SOLO un JSON:           │
 │   emozioni_interlocutore · astrazione_problema         │
 │   tool_richiesti · query_qdrant_memoria                │
 │   query_qdrant_automazione                             │
 └────────────────────────┬───────────────────────────────┘
                          ▼
 ┌────────────────────────────────────────────────────────┐
 │ FASE 2 · COMPUTE     PYTHON, nessun LLM                │
 │ Esegue il JSON: cerca in Qdrant, legge gli script da   │
 │ Postgres JSONB, chiama i tool statistici, crea e       │
 │ distrugge le sandbox. Deterministico: qui non si mente │
 └────────────────────────┬───────────────────────────────┘
                          ▼
 ┌────────────────────────────────────────────────────────┐
 │ FASE 3 · SURFACE     LLM, con TUTTI i fatti in mano    │
 │ <draft_output>  la risposta, in prima persona          │
 │ <automation_commit>  lo script nuovo, se ha funzionato │
 │ <reflect>  il post-mortem, per imparare                │
 └────────────────────────┬───────────────────────────────┘
                          ▼
 ┌────────────────────────────────────────────────────────┐
 │ FASE 4 · GUARDRAIL   LLM, o regola deterministica      │
 │ Confronta il testo generato con i LOG VERI.            │
 │ APPROVATO · oppure · RIFIUTATO + motivo                │
 └────────────────────────┬───────────────────────────────┘
                          ▼
                       utente
```

### Il costo da mettere in conto, misurato su questo impianto

Quattro fasi significano **fino a tre chiamate all'LLM** invece di una. Sulla
GPU del PC una risposta breve costa ~0,8 s; sulla CPU del server la stessa
cosa può costare decine di secondi (vedi
[hermes-memoria](../04_apps/hermes-memoria.md) §6: 97 ms contro 18 s per un
embedding). Conseguenze da progettare fin dall'inizio:

- il Sinker **completo** ha senso quando c'è la GPU; a PC spento serve una via
  breve (Sink + Surface, o Surface soltanto) — altrimenti l'assistente diventa
  inusabile proprio quando serve di più;
- la **Fase 4 non deve essere per forza un LLM**. Molti controlli sono regole:
  «il testo dice *ho mandato* ma nessun tool di invio è stato chiamato» è la
  guardia deterministica che già esiste in `sovereign-hermes.py`
  (`unverified_write_claim`). Regola prima, modello solo per ciò che la regola
  non copre. È lo stesso principio del `VerifierAgent` di Nexi
  ([PIANO_AGGIORNAMENTO_DA_NEXI](PIANO_AGGIORNAMENTO_DA_NEXI.md) §4).

## 3. I paradigmi, uno per uno

### 3.1 Astrazione cognitiva e doppio RAG
La Fase 1 produce un'**astrazione** del problema, non le parole dell'utente. Si
cerca in Qdrant per *pattern decisionale*, così una situazione mai vista trova
comunque il precedente che le somiglia. Due ricerche distinte:
`query_qdrant_memoria` (cosa so) e `query_qdrant_automazione` (cosa so già
fare).

### 3.2 Tool statistico: i numeri non li fa il modello
Microservizi Python per ARIMA, regressioni, previsioni. **Un LLM non calcola,
stima** — e una stima presentata come calcolo è una bugia con i decimali. Si
aggancia direttamente a una voce già aperta:
[A6 di Nexi](PIANO_AGGIORNAMENTO_DA_NEXI.md), la previsione del riempimento
dischi («`ssd_pool` piena fra 40 giorni» vale più di «al 26%»).

### 3.3 Apprendimento continuo
Momo scarica in background e vettorizza su Qdrant/Obsidian. **Da fare passare
dalle guardie esistenti**: `web_fetch` rifiuta già gli indirizzi interni
(difesa SSRF, voce S4 del [PIANO_MASTER](PIANO_MASTER.md)), e quel rifiuto vale
anche qui — un download automatico non deve diventare il modo per far leggere
al server i propri servizi privati.

### 3.4 Voce in tempo reale
LiveKit/WebRTC per lo stream e il **barge-in** (poterlo interrompere mentre
parla), Faster-Whisper per capire, XTTSv2 per rispondere con la voce del
proprietario.

> **Una scelta da fare consapevolmente**: il documento cita *«XTTSv2/ElevenLabs»*.
> XTTSv2 gira in casa; **ElevenLabs è il computer di qualcun altro**, e
> mandargli la voce del proprietario è esattamente il tipo di cosa che questo
> impianto ha scelto di non fare (la regola `private` esiste per questo). Se si
> usa ElevenLabs, che sia una decisione dichiarata e non una comodità presa di
> nascosto.

### 3.5 Automation Library + ciclo di vita delle sandbox
- **Qdrant** cerca *lo scopo* di uno script («deploy database vettoriale»);
  **Postgres `JSONB`** conserva *il payload* vero (bash, Ansible, Compose).
  Stessa divisione già usata per le procedure: i vettori per trovare, il
  relazionale per l'esattezza — perché una procedura si esegue passo per passo
  e deve tornare **esatta**, non somigliante.
- **Riciclo**: prima di scrivere codice nuovo, Momo cerca se ha già uno script
  provato.
- **Ciclo completo**: creare, testare, e **distruggere** l'ambiente per non
  saturare le risorse.
- **Auto-salvataggio**: se lo script nuovo passa il test, si salva da solo.

> **Il punto delicato, e la regola che lo risolve.** «Distruggere» tocca il
> divieto assoluto di MASTER, che il proprietario ha confermato il 2026-07-30
> e che la guardia sull'host applica con 29 casi verificati. La conciliazione
> è già nelle sue parole: *«può creare tutto e può cancellare le robe che lui
> crea»*. Quindi il teardown deve poter distruggere **solo ciò che ha
> provisionato lui**, e l'unico modo onesto di garantirlo è che
> l'orchestratore Python (Fase 2) **tenga il registro di ciò che ha creato** e
> passi al teardown solo identificatori presi da quel registro — mai un nome
> costruito dal modello. La guardia dell'host resta l'ultima parola: `qm
> destroy`, `zfs destroy` e `rm -rf` restano vietati comunque, sandbox o no.

### 3.6 La squadra che parla in tutte le direzioni
Richiesta del proprietario: *«la squadra di agenti può consegnare ad altri
componenti, cioè il flusso scende e sale e può risalire o scendere; un dev può
riparlare in alto o passare a un altro CEO, a un altro cyber, o allo stesso —
valuta lui»*.

È un cambio di forma reale: oggi lo sciame è **lineare** (dividi → assegna →
ricuci, [hermes.md](../04_apps/hermes.md) §7-ter). Qui diventa un **grafo con
instradamento deciso dagli agenti stessi**: lo Sviluppatore che trova un
problema di sicurezza può passare la palla al CISO, il quale può rimandarla
all'Architetto, che può richiamare lo Sviluppatore.

Tre cose da mettere nel disegno **prima** di scrivere una riga, perché un
grafo senza freni non termina:
1. un **tetto di salti** (e cosa succede quando lo si raggiunge: si risponde
   con quello che si ha, dicendolo);
2. il **rilevamento dei cicli** — A manda a B che rimanda ad A;
3. `delegate_task` di hermes-agent oggi conosce **due soli ruoli**
   (`leaf`/`orchestrator`) e non ha un catalogo di agenti con persona: i nostri
   13 ruoli nominati vanno mantenuti nel plugin, non nel loro codice.

## 3-bis. Decisioni e scoperte del 2026-07-30 (secondo giro)

### La GPU del server esiste, e non la usa nessuno

Il proprietario ha chiesto quale modello usare a PC spento, dicendo di non
conoscere la GPU del server. **Verificato**: il nodo Proxmox ha una
**NVIDIA T600 (TU117GL), 4 GB**, e `nvidia-smi` non è nemmeno installato —
quindi oggi quella scheda **non è usata da niente**.

Cosa cambia: in 4 GB ci sta `qwen3.5:4b` (3,4 GB), che è **esattamente** il
modello di scorta che oggi arranca sulla CPU. La "corsia lenta" del §2
smetterebbe di essere lenta, e la domanda «a PC spento uso API esterne?»
perderebbe quasi tutta la sua urgenza.

Cosa serve (non ancora fatto): driver NVIDIA sul nodo, passthrough del device
a LXC 102, e Ollama configurato per vederla. Da misurare **prima e dopo**, con
lo stesso metodo già usato per gli embedding (97 ms su GPU contro 18 s su CPU):
un numero misurato vale più di una promessa.

### Le API esterne restano il ripiego del ripiego

Ordine dichiarato dal proprietario: prima la GPU del PC, poi la GPU del server,
e **solo se serve** un'API esterna — che deve essere **gratuita**. Groq è già
configurato e verificato (30 richieste/min); i preset per Cerebras, NVIDIA NIM,
Cloudflare e gli altri sono pronti in `providers-presets.json`.

### La voce: tutto in casa, deciso

Il proprietario: *«per eleven labs io preferirei tutto in locale»*. **Deciso**:
Faster-Whisper per capire e **XTTSv2 per parlare**, entrambi in casa. La voce
del proprietario non esce dall'impianto. La riga «XTTSv2/ElevenLabs» del
documento originale si legge quindi come **XTTSv2 e basta**.

### Più conversazioni, una sola memoria

Difetto notato dal proprietario provando Hermes: *«valutava solo la nuova
domanda scordandosi del filo logico»*, e la richiesta che ne segue: *«voglio
poter aprire più chat con lui, con una memoria centrale ma memoria logica per
chat»*.

Lo stato reale, verificato nel codice: la cronologia **esiste** (ultimi 20
scambi, `load_chat`/`save_chat`), ma è **una sola per persona**
(`chat_path(username)`). Tutto si mescola in un unico filo, e argomenti diversi
si contaminano.

Il disegno chiesto, e che va costruito:

| Livello | Cosa contiene | Ambito |
|---|---|---|
| **Conversazione** | il filo del discorso: domande e risposte di *questa* chat | una chat |
| **Memoria** | fatti, agenda, procedure, rubrica, vault, runbook | **tutte** le chat, tutti i dispositivi |

Così una chat sul lavoro non si mescola con una sulla casa, ma un fatto detto
in una **lo sa anche l'altra** — perché la memoria è già centrale (verificato
in fase 2: un fatto salvato da Momo lo rilegge Hermes).

Nota tecnica: hermes-agent ha già le sessioni (`gateway/session.py`,
`session_id` ovunque, `/api/sessions ... /fork`), e il nostro
`MemoryProvider` riceve già `session_id` in `prefetch` e `sync_turn`. Quindi
questa richiesta si serve **più facilmente dentro Momo** che dentro l'Hermes
attuale: è un buon argomento in più per la fusione.

### Gli agenti di Ruflo

Richiesta: *«assicurati che Momo abbia i vari agenti di Ruflo e altro»*.
Ruflo è già una sorgente dichiarata di questo progetto
([PIANO_ESECUTIVO_2026-08](PIANO_ESECUTIVO_2026-08.md) §11): da lì vengono il
router per intenti (fatto, W2.2) e le strategie di scelta (fatte, W2.3). I suoi
**agenti** non sono ancora stati studiati — va fatto con lo stesso metodo usato
per `hermes-agent`: leggere il codice, non le note di rilascio, e riferire cosa
regge davvero.

## 4. IL PUNTEGGIO — le undici voci del documento, una per una

> **Aggiunto il 2026-08-01, su richiesta esplicita del proprietario**, che ha
> guardato lo stato dei lavori e ha detto: *«mi sa che tante cose mancano»* —
> aveva ragione. E poi: *«mi assicuro che voglio tutte ste cose»*. Quindi
> nessuna di queste righe si scarta: sono tutte in fila.
>
> Prima di oggi questa tabella non esisteva, e la §4 conteneva una lista vaga
> di "si aggancia a / da fare" che **non permetteva di contare**. La regola
> del [PIANO_MASTER](PIANO_MASTER.md) dice che ciò che non è in tabella è
> dimenticato: qui si conta, e il conto è **1 su 11**.
>
> Ogni "zero righe" qui sotto è stato verificato cercando nel codice il
> 2026-08-01, non ricordato.
>
> ⚠️ **RICONTATO IL 2026-08-04 — questa tabella è superata.** Cercando dentro
> `hermes-agent` invece che solo dentro il nostro codice è saltato fuori che
> le voci **7, 8, 9 e 10 non sono da costruire: esistono già nel motore e sono
> spente** (`skill_manager_tool.py` è l'Automation Library,
> `tools/environments/docker.py` è il ciclo di vita delle sandbox, con
> `reap_orphan_containers()` già scritto). E le voci **5 e 6 sono state fatte**
> il 2-3 agosto (Faster-Whisper e Piper). Il conto vero è **3 fatte, 4 da
> accendere con le guardie, 4 da scrivere**.
> Tabella aggiornata e architettura completa:
> **[PIANO_MOMO_PROGRAMMATORE.md](PIANO_MOMO_PROGRAMMATORE.md)**.

| # | Voce del documento | Stato | Prova |
|---|---|---|---|
| 1 | **Doppio RAG**: JSON astratto → pattern decisionali su Qdrant | ❌ zero righe | il Sinker Fase 1 non esiste. `MemoryStore.recall()` accetta `origins`, quindi il pezzo *sotto* c'è, ma nessuno genera l'astrazione |
| 2 | **Tool statistico**: microservizi Python (ARIMA), niente numeri dall'LLM | ❌ zero righe | nessun file. Chiude anche A6 di Nexi |
| 3 | **Apprendimento continuo**: download in background → Qdrant/Obsidian | ❌ zero righe | dovrà passare dalle guardie di `web_fetch` (difesa SSRF, S4) |
| 4 | **Voce real-time**: LiveKit/WebRTC, barge-in | ❌ zero righe | — |
| 5 | **STT**: Faster-Whisper | ❌ zero righe | cercato `whisper` in tutto `scripts/`: nessun file. **Ma il punto d'innesto esiste**: `agent/transcription_provider.py`, una ABC di 193 righe con due soli metodi astratti (`name`, `transcribe`) |
| 6 | **TTS**: XTTSv2 (deciso: **non** ElevenLabs, §3-bis) | ❌ zero righe | l'adattatore Telegram sa già mandare un vocale nativo (`send_voice`), manca chi genera l'audio |
| 7 | **Automation Library**: Qdrant per gli scopi, Postgres `JSONB` per i payload | ❌ zero righe | la tabella `procedures` esiste e usa la stessa divisione: è il modello da copiare |
| 8 | **Riciclo**: cerca uno script provato prima di scriverne uno nuovo | ❌ zero righe | dipende dal 7 |
| 9 | **Sandbox lifecycle**: provision → test → teardown | ❌ zero righe | la guardia host esiste (29 casi); manca il registro di ciò che Momo ha creato, che è l'unico modo onesto di limitare il teardown |
| 10 | **Auto-salvataggio**: se il test passa, lo script si salva da solo | ❌ zero righe | dipende dal 7 |
| 11 | **Sinker Fase 4 — GUARDRAIL** | ✅ **fatto e verificato (2026-07-31)** | [momo-guardrail.md](../04_apps/momo-guardrail.md), 23 casi di test |

E le tre fasi del Sinker che restano, dalla PARTE 2 del documento:

| Fase | Cosa | Stato |
|---|---|---|
| **1 · SINK** | JSON con `emozioni_interlocutore`, `astrazione_problema`, `tool_richiesti`, `query_qdrant_memoria`, `query_qdrant_automazione` | ❌ da fare |
| **2 · COMPUTE** | orchestrazione Python, nessun LLM, deterministica | ❌ da fare |
| **3 · SURFACE** | `<draft_output>` / `<automation_commit>` / `<reflect>` | ❌ da fare |
| **4 · GUARDRAIL** | il filtro anti-allucinazione | ✅ fatto |

### 4-bis. E le tre cose che non sono nel documento ma che il proprietario usa

Dette il 2026-08-01: *«Momo non ha ancora preso il posto di Hermes, se sì
Hermes lo vedo ancora sulla dashboard»*, *«Momo non manda messaggi»*,
*«Momo non ha la mia voce»*. Tutte e tre vere, verificate:

| Cosa | Stato reale, verificato il 2026-08-01 |
|---|---|
| **Momo al posto di Hermes** | ❌ `hermes.internal` → `192.168.1.52:8093`, che è `sovereign-hermes.py`. Momo non è dietro nessun URL e **non è nemmeno un servizio**: gira solo da riga di comando. Prerequisiti veri nel punto 21 di [PIANO_GENERALE](PIANO_GENERALE.md) |
| **Momo manda messaggi (Telegram)** | ❌ `config.yaml` di Momo ha 4 plugin, nessuna piattaforma. Il bot **è vivo** (`@dn_momo_bot`, id `8863073080`, `getMe` risponde) e il token c'è dal 30/7, ma non è collegato a niente |
| **Momo ha la voce** | ❌ vedi righe 4-6 sopra |

**La scoperta utile del 2026-08-01**: la voce **via Telegram** costa molto meno
della voce nel browser, perché l'adattatore di hermes-agent fa già tutto
l'impianto audio. Scarica i vocali in arrivo per la trascrizione
(`adapter.py:9013`) e sa mandare un vocale nativo, la bollicina tonda
(`adapter.py:6798`, per `.ogg`/`.opus`). Restano da scrivere **solo i due
motori**, e il primo ha già la sua ABC pronta. Il registratore nel browser e
LiveKit (voce real-time con barge-in) restano da fare, ma non sono più la
strada più corta per avere una voce che funziona.

## 4-ter. Le richieste del 2026-08-01 — dette a voce mentre si lavorava

> Il proprietario le ha dette una alla volta, interrompendo il lavoro, e ha
> chiesto: *«continua con i tuoi piani poi appena finisci fai il resto ma non
> scordarti questi dettagli»*. Sono qui perché non si scordino. Quelle già
> fatte hanno la prova accanto; le altre sono lavoro dichiarato.

| # | Richiesta, con le sue parole | Stato |
|---|---|---|
| T1 | *«momo deve girare sulla mia gpu del pc finché è connesso, se chiudo il pc sulla gpu del server»* | 🟡 **metà**: il PC è il primario ✅; il ripiego è configurato ma oggi cade sulla **CPU** del server, non sulla GPU — la T600 non ha driver (punto 20) |
| T2 | *«poi non scordarti omniroute»* | ❌ da fare: OmniRoute come terzo anello della catena, dopo la GPU del server |
| T3 | *«vado a fare una chiave bedrock di 2 giorni»* | ⏳ in arrivo. Bedrock **è già** fra i provider di fallback che hermes-agent supporta: si aggiunge a `fallback_providers` |
| T4 | *«va bene anche se le robe passano ai api provider ma dammi sempre un warn prima di scrivere»* | ✅ fatto: `SOVEREIGN_ALLOW_EXTERNAL_ENGINES` (default acceso, reversibile in una riga) + la regola «prima di scrivere, avvisa» nella persona |
| T5 | *«momo deve per forza imparare e essere madrelingua in tre lingue: inglese, italiano e arabo»* | ✅ fatto nella persona: risponde nella lingua in cui gli si scrive, arabo standard moderno, termini tecnici non tradotti |
| T6 | `محمد ابوالسعود` *«è il mio nome in arabo»* | ✅ nella persona: su Telegram compare col nome arabo, ed è lui |
| T7 | *«deve poter salvare modificare e tutto»* | ❌ **da fare, ed è il pezzo grosso**: è MASTER dentro Momo. Oggi Momo legge e ricorda, ma non tocca l'impianto |
| T8 | *«vorrei un'interfaccia di gestione di momo che metterai su dash»* | ❌ da fare: pannello su `dash.internal` per dare/togliere poteri a Momo, vedere cosa ha fatto, armare MASTER |
| T9 | *«attraverso telegram se gli do comando master lui sa che è master ecc e tutte le funzioni partono»* | ❌ da fare, e **dipende da T7 e T8**: l'armamento va fatto da un canale che sa chi sei davvero, poi Telegram lo usa |
| T10 | *«momo deve rispondere con un audio»* | 🟡 **il motore c'è**: Piper installato con voce italiana, provato e la voce è arrivata su Telegram. Manca il plugin che lo aggancia alle risposte automaticamente |
| T11 | *«se gli dico plz scrivi che non posso sentire ora, l'audio trascrive o recupera quello che mi ha detto in audio»* | ❌ da fare: il testo della risposta parlata va tenuto e restituito a richiesta |
| T12 | *«la memoria di momo è su più posti, sia il db nosql sia obsidian, o vedi tu cosa è il meglio»* | ✅ **già così**, ed è il disegno giusto — vedi §4-quater |

### 4-quater. La memoria su più posti: com'è già fatta, e perché

Risposta a T12. La memoria di Momo **è già distribuita su quattro archivi**, e
ognuno c'è per una ragione diversa. Non è un doppione: è la divisione
«i vettori per **trovare**, il relazionale per l'**esattezza**».

| Dove | Cosa ci sta | Perché lì |
|---|---|---|
| **Postgres** | fatti, agenda, procedure, rubrica, registro | una procedura si esegue passo per passo e deve tornare **esatta**, non somigliante |
| **Qdrant** | il *significato* di fatti, note del vault, runbook | «cosa mi aveva detto sul lavoro?» non si risolve con `LIKE` |
| **Valkey** | cache degli embedding | un embedding sulla CPU costava 18 s; ricalcolarlo ogni volta è insostenibile |
| **CouchDB / Obsidian** | le note scritte a mano, sincronizzate su tutti i dispositivi | è il vault vero, e si legge dal telefono anche offline |

**Il consiglio richiesto** (*«vedi tu cosa è il meglio»*): tenerli tutti e
quattro, con questa regola su dove scrivere una cosa nuova —

- se è un **fatto** o un **impegno** → Postgres, via `ricorda`/`agenda_*`:
  strutturato, cancellabile, e `dimentica` dimentica davvero;
- se è una **nota da rileggere da umano** → Obsidian, dentro
  `07 Notes/Hermes/`: la sola cartella che Momo può toccare, così un errore
  non può rovinare i tuoi appunti;
- **mai la stessa cosa in due posti**: due copie divergono, e la divergenza è
  invisibile finché una delle due non è sbagliata. È la stessa regola per cui
  il Guardrail è un file solo.

Quello che **manca** e che è nel documento (voce 7): l'**Automation Library**,
cioè gli *script* — Qdrant per lo scopo, Postgres `JSONB` per il payload.
Stessa divisione, contenuto diverso.

## 5. Ordine — rifatto il 2026-08-01

**Il criterio è cambiato, e l'ha cambiato il proprietario.** Fino al 31/7
l'ordine era «prima le fondamenta, poi le capacità», ed è così che in due
sessioni sono arrivati il Guardrail, l'interruttore e il Verificatore: tutta
roba giusta che **lui non vede**. Il 2026-08-01 ha guardato il risultato e ha
detto che mancano le cose che usa. Quindi ora l'ordine è: **prima quello che
si vede e si usa.**

1. **Telegram** — *scelto dal proprietario come primo, 2026-08-01*. È il più
   corto a dargli qualcosa in mano: il bot esiste, il token esiste,
   l'adattatore esiste. Obbliga anche a fare una cosa che serve comunque,
   **rendere Momo un servizio vivo** invece di un comando da terminale.
2. **La voce, via Telegram** — vedi §4-bis: da qui costa molto meno che dal
   browser. Prima l'ascolto (Faster-Whisper dietro `TranscriptionProvider`),
   poi la risposta parlata (Piper), poi la sua voce (XTTSv2).
3. **Tool statistici** — piccolo, isolato, non può rompere niente, e chiude
   A6 di Nexi.
4. **Automation Library** (voci 7, 8, 10) — riusa schemi già in casa.
5. **Il Sinker completo** (fasi 1-3) — ha bisogno della GPU del server
   (punto 20 di [PIANO_GENERALE](PIANO_GENERALE.md)), altrimenti tre chiamate
   al modello sulla CPU lo rendono inusabile.
6. **Sandbox con ciclo di vita** — tocca il divieto assoluto: dopo il
   Guardrail (fatto) e dopo il drop pulito (punto 7 del PIANO_GENERALE).
7. **Squadra a grafo** — con i tre freni del §3.6.
8. **Voce real-time (LiveKit, barge-in)** — il pezzo più grosso; dopo che la
   voce a messaggi funziona.

Resta vero che **le guardie vengono prima dei poteri**: il punto 6 non si
tocca prima del suo prerequisito. Ma le guardie che servivano ai punti 1-5
sono già in piedi, quindi non c'è più niente da aspettare.

## 6. Sorgenti

- Documento di progetto del proprietario, 2026-07-30 (trascritto qui)
- [PIANO_AGENT_MOMO.md](PIANO_AGENT_MOMO.md) — la fusione, fasi 1-2 fatte
- [PIANO_AGGIORNAMENTO_DA_NEXI.md](PIANO_AGGIORNAMENTO_DA_NEXI.md) — A3 (il Verificatore), A5 (azioni come dati), A6 (previsione)
- [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md) §2.2 — «uno strumento che sbaglia non dà errore: racconta una bugia sicura di sé»
