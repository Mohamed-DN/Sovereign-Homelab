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

## 4. Come si incastra con quello che esiste già

| Pezzo nuovo | Si aggancia a | Stato di partenza |
|---|---|---|
| Guardrail (Fase 4) | `unverified_write_claim` / `unmet_write_request` | esistono e sono stati corretti oggi |
| Automation Library | `actions.json` di MASTER + tabella `procedures` | esistono |
| Teardown sandbox | guardia host `hermes-master-guard.py` | esiste, 29 casi verificati |
| Tool statistici | A6 di Nexi (previsione dischi) | da fare |
| Doppio RAG | `MemoryStore.recall()` con `origins` | esiste già, accetta origini diverse |
| Voce | W7.2-7.4 del piano esecutivo | da fare |
| Squadra a grafo | sciame lineare + `roles.json` | da riscrivere |

## 5. Ordine consigliato

Prima le fasi 3 e 4 della fusione (**gli strumenti** e **le guardie**), perché
tutto quanto sopra si appoggia su quelle. Poi, in ordine di rapporto fra
valore e rischio:

1. **Guardrail** — è la difesa contro un difetto che è già costato tre volte;
2. **Tool statistici** — piccolo, isolato, e chiude una voce già aperta;
3. **Automation Library** — riusa schemi già in casa;
4. **Sandbox con ciclo di vita** — potente, ma tocca il divieto assoluto:
   va fatto dopo che il Guardrail è in piedi, non prima;
5. **Squadra a grafo** — da progettare con i tre freni sopra;
6. **Voce in tempo reale** — il pezzo più grosso, e il più visibile.

## 6. Sorgenti

- Documento di progetto del proprietario, 2026-07-30 (trascritto qui)
- [PIANO_AGENT_MOMO.md](PIANO_AGENT_MOMO.md) — la fusione, fasi 1-2 fatte
- [PIANO_AGGIORNAMENTO_DA_NEXI.md](PIANO_AGGIORNAMENTO_DA_NEXI.md) — A3 (il Verificatore), A5 (azioni come dati), A6 (previsione)
- [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md) §2.2 — «uno strumento che sbaglia non dà errore: racconta una bugia sicura di sé»
