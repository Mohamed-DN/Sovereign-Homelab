# Piano esecutivo — agosto 2026

> Scritto il 2026-07-30 per essere **eseguito da un'altra sessione**. Ogni passo
> ha: i file da toccare, cosa fare, e **come si verifica**. Un passo è finito
> quando la verifica passa, non quando il codice è scritto.
>
> Contesto e principi: [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md). Stato
> puntuale: [PIANO_MASTER.md](PIANO_MASTER.md). **Leggi quelli due prima di
> cominciare**: qui non ripeto le quattordici trappole già pagate, e ripagarle
> costa ore.

---

## 0. Quello che ho verificato prima di scrivere questo piano

Distinguo con cura fra ciò che ho **provato** e ciò che ho **letto**, perché il
piano regge solo sulla prima categoria.

### Provato, con il comando in mano

| Fatto | Prova |
|---|---|
| **Ollama scarica i modelli via API**: `POST /api/pull` | scaricato e cancellato `smollm2:135m` sul PC, `{"status":"success"}` |
| **16 modelli esistono** nella libreria Ollama | `HTTP 200` su `ollama.com/library/<nome>`: `gemma4`, `gpt-oss`, `devstral`, `qwen3.5`, `qwen3-coder`, `llama4`, `mistral-small3.2`, `phi4-mini`, `deepseek-r1`, `minicpm-v`, `granite4`, `llava`, `qwen2.5vl`, `embeddinggemma`, `nomic-embed-text`, `bge-m3`, `hermes3`, `nous-hermes2` |
| **`smollm3` e `whisper` NON sono su Ollama** | `HTTP 404`. Whisper non è un modello Ollama: serve un servizio a parte (conta per la fase voce) |
| **Il relay email accetta già un destinatario arbitrario** | `scripts/sovereign-alert-relay.py` `/notify` → `valid_recipient()` + limite orario. Il blocco è solo dentro Hermes |
| **`NousResearch/hermes-agent` è vivo e serio** | MIT, Python, **222 541 stelle**, ultimo push 2026-07-30, ultima release `v2026.7.20`. Moduli: `providers/`, `plugins/`, `skills/`, `toolsets.py`, `gateway/`, `cron/`, `mcp_serve.py`, `native/`. 69 file citano `telegram` |
| **Bedrock funziona** con la chiave del proprietario | `openai.gpt-oss-20b-1:0` → HTTP 200 su us-east-1, us-west-2, eu-central-1 |

### Letto, da confermare provando

- Le **dimensioni** dei modelli: ho provato a estrarle dalle pagine della
  libreria e **il risultato era disallineato** (dava `qwen3.5:9b` a 1,2 GB,
  quando so che sono 6,6 GB). **Non le ho messe nel catalogo**: il pannello
  prenderà la dimensione vera dalla macchina, che è l'unica fonte che non
  sbaglia. Non fidarti di numeri scritti a mano.
- Le **feature di `hermes-agent`** (adattatori Signal/SMS/Matrix/Mattermost/
  DingTalk/Webhook, orchestratore di sotto-agenti, proxy compatibile OpenAI,
  Hermes Desktop) vengono dalle note di rilascio, non da una prova.
- I **limiti dei fornitori gratuiti**: Groq 30 req/min · 14 400/giorno; NVIDIA
  NIM 40 req/min senza tetto giornaliero; Cerebras fino a ~2000 token/s. Da
  riverificare: cambiano spesso.

### La confusione da chiarire subito

Ci sono **due cose diverse che si chiamano Hermes**:

1. **il nostro** `sovereign-hermes.py` — scritto qui, conosce questa casa: SSO,
   ruoli, stato dell'impianto, vault, memoria, procedure;
2. **`NousResearch/hermes-agent`** — un framework generico di agenti, enorme e
   attivissimo, che di questa casa non sa niente.

Il proprietario ha detto «ho scoperto che c'è una nuova versione di Hermes con
tantissime feature». **Presumo che intenda il numero 2**, ma non l'ho chiesto:
è la prima domanda del §9.

---

## 1. La decisione architetturale, e la raccomandazione

Con `hermes-agent` ci sono tre strade.

| Strada | Cosa comporta | Giudizio |
|---|---|---|
| **A. Sostituire** il nostro con `hermes-agent` | si guadagnano decine di feature; **si perde tutto ciò che sa di questa casa** — identità Authentik, ruoli per persona, `estate_status` filtrato, vault in sola lettura, memoria per proprietario, le due guardie sulle bugie | **no** |
| **B. Copiare le idee** e continuare a mano | nessuna dipendenza nuova; si riscrivono a mano adattatori che esistono già e sono mantenuti da un progetto con 222 mila stelle | **no, spreco** |
| **C. Metterlo accanto, come «le mani»** | il nostro Hermes resta **la regia che conosce la casa**; `hermes-agent` diventa un motore di esecuzione e un fronte di messaggistica. Espone un server compatibile OpenAI, quindi entra in `backends.json` senza codice nuovo; i suoi adattatori (Telegram, Signal, SMS, Matrix) possono parlare **al nostro** Hermes via HTTP | **sì** |

**C è coerente con il principio che governa già tutto qui**: la regia sta sul
server, la forza bruta si prende dove c'è. Lo stesso schema con cui Hermes usa
la GPU del PC senza diventare la GPU del PC.

E c'è un vincolo che decide da solo: **`hermes-agent` non sa chi è Luna.** Non
sa che il vault è privato, che `estate_status` va filtrato per ruolo, che un
motore non privato non deve vedere la memoria. Quelle regole sono il valore di
quello che abbiamo, e non si delegano.

---

## 2. W1 — Il catalogo dei modelli, e scaricarli dal pannello

**Il problema del proprietario, con le sue parole**: «poche opzioni poche
scelte, non posso scaricare tanti modelli».

**La causa**: oggi il pannello mostra un elenco di 6 modelli *consigliati* come
tabella statica, e per installarne uno bisogna entrare in SSH e dare
`ollama pull`. Il pannello non ha nessun modo di installare niente.

**La leva che lo risolve**: `POST /api/pull` di Ollama, verificato funzionante.

### Passi

**W1.1 — Il file di catalogo.**
Nuovo `scripts/hermes/models-catalog.json`. Una voce per modello:

```json
{
  "name": "gemma4:e4b",
  "engine": "ollama",
  "role": ["chat", "vision", "tools"],
  "label": "Gemma 4 e4b — piccolo, vede le immagini, chiama gli strumenti",
  "note": "Il più equilibrato per la GPU: lascia spazio al contesto",
  "recommended_for": ["pc-mohamed", "server"]
}
```

I ruoli sono un insieme chiuso: `chat`, `reasoning`, `coding`, `vision`,
`tools`, `embedding`, `small`, `multilingual`.
**Non mettere le dimensioni a mano** (vedi §0): il pannello le legge da
`/api/tags` per i modelli installati.

Popolalo con i 16 verificati al §0, divisi per ruolo. Includi `hermes3` fra i
`chat` — è un modello Hermes vero, e il proprietario potrebbe intendere quello.

**W1.2 — Le API nel servizio.** In `scripts/sovereign-hermes.py`:

| Endpoint | Cosa fa |
|---|---|
| `GET /api/models/catalog` | il catalogo + per ogni motore Ollama quali sono già installati e la loro dimensione **vera** |
| `POST /api/models/pull` | `{backend, model}` → inoltra a `POST {url}/api/pull` con `stream: true` e **rilancia lo stato al browser** come SSE, così si vede la percentuale |
| `POST /api/models/delete` | `{backend, model}` → `DELETE {url}/api/delete`. Chiedi conferma in pagina |

Solo amministratore. Il nome del modello va **validato contro il catalogo**:
non si inoltra una stringa arbitraria a `/api/pull` presa dal browser.

**W1.3 — Il pannello.** Sostituisci la tabella statica dei consigli con un
catalogo filtrabile per ruolo: per ogni modello badge del ruolo, stato
(*installato* con dimensione reale / *da scaricare*), pulsante **Scarica** con
barra di avanzamento, e **Usa** che lo imposta come modello del motore.

*Verifica di W1*: dal browser, scaricare `granite4:micro` (il più piccolo) e
vederlo comparire come installato con la dimensione giusta, senza aprire un
terminale. Poi cancellarlo dalla stessa pagina.

---

## 3. W2 — Collegare i modelli senza sapere cosa sia un endpoint

**Il problema**: «sistema il come posso collegare i modelli, poco intuitivo e
complesso». Oggi per aggiungere un fornitore bisogna sapere URL, percorso `/v1`,
nome esatto del modello e, per i modelli di ragionamento, che serve
`reasoning_effort`.

### Passi

**W2.1 — Fornitori come preset, non come URL da scrivere.**
Nuovo `scripts/hermes/providers-presets.json`: per ogni fornitore il nome
leggibile, l'URL base, dove si prende la chiave, i modelli gratuiti noti, i
limiti, e gli `extra` necessari.

Da mettere dentro, tutti con iscrizione gratuita e senza carta: **Groq**,
**Cerebras**, **NVIDIA NIM**, **Cloudflare Workers AI**, **OpenRouter**,
**Google AI Studio**, **GitHub Models**, **HuggingFace**, più **AWS Bedrock**
(già configurato e provato) e **OmniRoute** (locale).

Nel pannello diventa: scegli il fornitore da un menu → **incolla solo la
chiave** → Salva. URL, percorso e `extra` li mette il preset.

**W2.2 — Il router per intenti.** È l'idea presa da `ruflo`
(`ruflo/src/ruvocal/docs/source/configuration/llm-router.md`): l'utente non
scegli un modello, dichiara **cosa gli serve**.

Nuovo `scripts/hermes/routes.json`:

```json
[
  {"name": "veloce",   "descrizione": "domande brevi, risposte immediate",
   "primary": "pc-mohamed", "fallback": ["server", "bedrock"]},
  {"name": "ragiona",  "descrizione": "problemi difficili, analisi",
   "primary": "bedrock", "fallback": ["pc-mohamed"]},
  {"name": "codice",   "descrizione": "scrivere o correggere codice",
   "primary": "pc-mohamed", "fallback": ["bedrock"]},
  {"name": "immagini", "descrizione": "capire una foto o uno screenshot",
   "primary": "pc-mohamed", "fallback": []},
  {"name": "privato",  "descrizione": "roba di casa: vault, memoria, impianto",
   "primary": "pc-mohamed", "fallback": ["server"],
   "solo_privati": true}
]
```

`solo_privati: true` è la regola che conta: quella rotta **non può** cadere su
un motore non privato, nemmeno se è l'unico acceso. Meglio nessuna risposta che
il vault a un fornitore esterno.

In pagina: un menu **«cosa ti serve»** con le rotte, e `auto` come default.
Con `auto`, la scelta è per regole deterministiche prima che per modello: c'è
un'immagine allegata → `immagini`; la richiesta tocca strumenti privati →
`privato`; contiene blocchi di codice → `codice`; altrimenti `veloce`.
**Non usare un modello per classificare** in prima battuta: aggiunge una
chiamata, latenza e un altro punto in cui può mentire.

**W2.3 — Strategie di scelta.** Preso da `ruflo`
(`v3/@claude-flow/providers`): oggi Hermes prende «il primo sano in ordine».
Aggiungi in `backends.json` un campo di strategia globale: `ordine` (l'attuale),
`piu_veloce` (misura la latenza dell'ultima chiamata e preferisce la più bassa),
`meno_carico` (chiamate in volo / `parallel`). Default `ordine`: cambiare il
default non è un miglioramento, è una sorpresa.

*Verifica di W2*: aggiungere Groq incollando solo la chiave, e vedere `ragiona`
che ci finisce sopra. Poi spegnere il PC e verificare che `privato` **non**
cada su Groq ma dica che non c'è un motore adatto.

---

## 4. W3 — Il pannello, rifatto

Oggi è una pagina sola con l'elenco dei motori. Serve una pagina con sezioni:

1. **Motori** — quello che c'è oggi, più: badge *privato / non privato* (con la
   spiegazione di cosa cambia), latenza dell'ultima chiamata, e la strategia.
2. **Modelli** — il catalogo di W1, con Scarica.
3. **Fornitori** — i preset di W2.1, con «incolla la chiave».
4. **Rotte** — le rotte di W2.2, riordinabili.
5. **Memoria** — quello che `--memory-status` dice già oggi (Postgres, Qdrant,
   Valkey, tempo di un embedding, conteggi), più un pulsante *reindicizza*.
6. **Rubrica** — W4.
7. **Master** — W5, e **solo se armato**.

Regole di interfaccia da rispettare, tutte nate da difetti reali:
- il pulsante che salva è **`position: fixed`**, non `sticky` (era il difetto
  «manca il pulsante invio»);
- **Invio salva** dentro qualunque campo di testo;
- dopo il salvataggio, ricarica e mostra lo stato vero, non un «✓» ottimista;
- ogni voce che può rompere qualcosa porta accanto **una riga** che dice cosa
  rompe.

*Verifica di W3*: dal telefono, in verticale, tutte le sezioni sono usabili e
il pulsante Salva è visibile senza scorrere.

---

## 5. W4 — Email alle persone, senza diventare un cannone da spam

**Il problema**: «Hermes non può mandare mail alle persone attraverso la mia
mail».

**Perché è così oggi**: `send_mail` legge il destinatario da un file leggibile
solo da root e **ignora quello che dice il modello**. È stato scritto così di
proposito: senza quel vincolo, un prompt malevolo o un modello confuso manda
posta a chiunque, dalla casella del proprietario.

**Il relay non è il problema**: `/notify` accetta già un destinatario
arbitrario, lo valida e ha un limite orario. Il vincolo è tutto in Hermes.

### La forma giusta: una rubrica, non un campo libero

**W4.1 — Tabella `contacts`** in `scripts/hermes/memory-schema.sql`:
`id, owner, name, email, note, allowed (bool), created_at, last_used_at,
times_used`. Vincolo di unicità su `(owner, email)`.

**W4.2 — Strumenti**: `rubrica_aggiungi`, `rubrica_cerca`, `rubrica_elenco`.
Riservati all'amministratore. In `PRIVATE_TOOLS`: gli indirizzi delle persone
non escono di casa.

**W4.3 — `send_mail` con destinatario**, e queste regole:
- il parametro è un **nome**, non un indirizzo: «manda una mail a Luna». Hermes
  risolve il nome sulla rubrica. Se non è in rubrica, **rifiuta e lo dice**;
- un indirizzo mai visto non si manda: si propone di aggiungerlo alla rubrica,
  e serve un'altra richiesta esplicita dell'utente;
- l'oggetto e il corpo restano ripuliti da CR/LF (l'iniezione di intestazioni è
  già chiusa, non riaprirla);
- **ogni invio va nel registro**: a chi, quando, oggetto. Mai il corpo.

**W4.4 — Il mittente.** Oggi il relay manda da `ALERT_SMTP_FROM`. Per «dalla
mia mail» verifica che quella casella sia la sua e, se serve, imposta
`Reply-To` sul suo indirizzo personale. **Non** inventare un mittente diverso da
quello autenticato in SMTP: finisce nello spam e può far bloccare la casella.

*Verifica di W4*: «manda una mail a Luna dicendo che la cena è alle 20» →
Hermes trova Luna in rubrica e manda. «Manda una mail a
`sconosciuto@example.com`» → rifiuta, e propone di aggiungerlo.

---

## 6. W5 — La modalità MASTER

**La richiesta**: un pulsante `master` che, premuto, permette a Hermes di agire
su tutto — toccare il codice, mettere in piedi servizi, sapere dove sono le
password, cambiare l'architettura, «proprio come fai tu».

**Va detto una volta con chiarezza**: questo è l'elemento più rischioso di tutto
il progetto. Un modello con i permessi di root può fare danni **senza volerlo**,
e i modelli in casa hanno già mentito tre volte su cose che non avevano fatto.
Non è un argomento per non farlo — è la sua infrastruttura e la richiesta è
legittima. È l'argomento per cui il disegno che segue **non è negoziabile nei
suoi vincoli**: sono quelli che rendono la differenza fra uno strumento potente
e una roulette.

Il modello di riferimento sono i tre strati di Nexi: **Direttive** (le regole,
scritte da persone) → **Orchestrazione** (l'agente decide *quando*) →
**Esecuzione** (comandi deterministici).

### W5.1 — Le azioni sono dati, non codice

Nuovo `scripts/hermes/actions.json`. Il modello **sceglie** da un elenco e
riempie parametri dichiarati; **non compone mai una stringa di shell**.

```json
{
  "name": "riavvia_container",
  "descrizione": "Riavvia un container Docker su un host dell'impianto",
  "comando": ["pct", "exec", "{ctid}", "--", "docker", "restart", "{nome}"],
  "parametri": {
    "ctid": {"tipo": "enum", "valori": ["100", "101", "102", "103"]},
    "nome": {"tipo": "regex", "pattern": "^[a-z0-9][a-z0-9_.-]{0,40}$"}
  },
  "reversibile": true,
  "conferma": false,
  "timeout": 60
}
```

Perché il comando è una **lista** e non una riga: una lista non ha shell, quindi
non ha `;`, `&&`, backtick o espansioni. È la differenza fra un parametro e una
iniezione. Un parametro che non passa il suo `enum` o la sua `regex` fa fallire
l'azione **prima** di eseguire qualunque cosa.

Elenco iniziale, volutamente corto: riavviare un container, riavviare un
servizio systemd, leggere gli ultimi log di un servizio, `df`/`free`/`pct list`,
ricaricare nginx di NPM, riavviare Hermes. **Si allarga guadagnando fiducia**,
non prima.

### W5.2 — Le password: sapere dov'è, non sapere qual è

Hermes deve poter *usare* un segreto senza *vederlo*. Nei parametri si scrive un
riferimento, mai un valore:

```json
{"password": {"tipo": "secret", "path": "hermes/couchdb-password"}}
```

L'esecutore sostituisce il valore leggendolo da
`/root/sovereign-secrets/<path>` **al momento di eseguire**, fuori dal contesto
del modello. Il valore non entra mai nel prompt, non finisce nella
conversazione salvata, non compare nel registro. Un `path` fuori da
`/root/sovereign-secrets/` è un errore, non un tentativo.

E uno strumento `segreti_elenco` che restituisce **i nomi** dei file di segreti,
non il contenuto: così alla domanda «dove sta la password di CouchDB» Hermes
risponde con il percorso, che è quello che serve, senza leggere niente.

### W5.3 — Codice e servizi nuovi: si propone, non si applica

Qui non basta un elenco di azioni: scrivere codice è aperto per natura. La
risposta è **lavorare come lavoro io**:

1. l'azione `proponi_modifica` crea un **worktree git** in `/opt/sovereign-work`
   su un ramo nuovo;
2. l'agente scrive i file **là dentro**, non sull'impianto vivo;
3. gira `scripts/validate-repository.ps1` (o l'equivalente Linux) e i controlli
   di sintassi. Se non passano, si ferma;
4. produce **il diff** e lo mostra in pagina;
5. **niente arriva su `main` né su un host vivo senza che il proprietario
   prema Applica.**

Così «può mettere in piedi servizi» diventa vero — scrive lo stack, il runbook,
l'unità systemd — ma con l'approvazione umana nel punto in cui conta. È lo
stesso patto che c'è fra me e lui.

### W5.4 — Il divieto assoluto

Una lista di rifiuti che **non dipende dall'armamento** e non si cambia dalla
chat. Compilata a codice, non in un file modificabile:

- niente che tocchi i dati di Immich, in nessuna forma;
- `zfs destroy`, `qm destroy`, `pct destroy`, `rm -rf` su percorsi di dati;
- cancellare o svuotare un datastore PBS o uno snapshot;
- disattivare `sovereign-omniroute-firewall`, la guardia di sola lettura di
  CouchDB, o il forward-auth di NPM;
- scrivere nel registro di audit;
- creare utenti o cambiare permessi in Authentik;
- toccare `actions.json` e il divieto stesso.

Il criterio: **ciò che un backup non rimette a posto in un'ora non si automatizza.**

### W5.5 — Armamento, scadenza, registro, interruttore

- Il pulsante **MASTER** compare **solo** all'amministratore e **solo** da
  `hermes.internal` (mai da Telegram, mai dalla PWA in prima battuta).
- Armare chiede una **conferma esplicita** con scritto quante azioni sono
  permesse e per quanto tempo. Scade da sola dopo **30 minuti**.
- Ogni azione: chi, quando, quale azione, quali parametri, esito, per intero,
  in una tabella **che il ruolo di Hermes non può aggiornare né cancellare**
  (`REVOKE UPDATE, DELETE`). Un registro che l'agente può riscrivere non è un
  registro.
- Un **interruttore globale** `RUNNING`/`PAUSED` (è la voce A4 di Nexi), letto
  prima di ogni azione. In pausa Hermes continua a parlare e a leggere: si
  fermano solo le azioni.
- Ogni azione irreversibile chiede conferma **in chat, con il comando esatto
  scritto sotto gli occhi**, prima di partire.
- Prima riga di ogni azione: un `--dry-run` che stampa il comando risolto.

*Verifica di W5* (tutte e cinque devono passare):
1. non armato: un'azione viene rifiutata;
2. armato: `riavvia_container` su `searxng` funziona e finisce nel registro;
3. un parametro fuori dall'`enum` viene rifiutato **prima** di eseguire;
4. un'azione dell'elenco di divieto viene rifiutata **anche** armato;
5. dopo 31 minuti l'armamento è scaduto da solo.

---

## 7. W6 — `hermes-agent` accanto al nostro

**W6.1 — Provarlo isolato.** Container su LXC 102, **niente** credenziali di
casa, `docker compose` dal loro repo. Obiettivo del passo: sapere cos'è, non
metterlo in produzione. Verificare la licenza (MIT, verificato) e cosa manda
fuori (`.env.example` e le impostazioni di telemetria: leggerle, non
presumerle).

**W6.2 — Come motore.** Espone un server compatibile OpenAI: entra in
`backends.json` con `private: false` finché non è dimostrato il contrario.
La guardia gli nega automaticamente vault, memoria, impianto e accessi — quella
è già scritta e verificata.

**W6.3 — Come fronte di messaggistica.** È il pezzo che vale davvero: ha già
gli adattatori per **Telegram, Signal, SMS, Matrix, Mattermost, DingTalk,
Webhook**. Invece di scrivere il bot Telegram a mano (era la Fase 3), si
configura il suo adattatore a inoltrare **al nostro** Hermes via HTTP.

Il vincolo che non si tocca: **l'identità.** Il nostro Hermes accetta
un'identità solo da NPM (`X-authentik-username` da 192.168.1.50). Un adattatore
che parla da un'altra origine non può asserire chi sei. Quindi serve una
mappatura `id del canale → utente di casa`, **compilata a mano**, e gli id
sconosciuti si rifiutano. Vale per Telegram come per Signal.

**W6.4 — MCP, e questo è il moltiplicatore vero.** `hermes-agent` ha
`mcp_serve.py` e una cartella `optional-mcps`. Se il **nostro** Hermes impara a
parlare MCP come *client*, ogni server MCP esistente diventa uno strumento
senza scrivere codice nostro. È la risposta strutturale a «poche opzioni»: si
smette di aggiungere strumenti uno per uno.
Da fare **dopo** W5, perché uno strumento MCP è codice di qualcun altro dentro
il nostro processo, e va dietro la stessa guardia privato/non privato.

*Verifica di W6*: un messaggio Telegram da un id mappato riceve la risposta del
**nostro** Hermes con i **suoi** permessi; da un id sconosciuto viene rifiutato.

---

## 8. W7 — Voce e telefono (la Fase 2 e 3 di prima)

Restano, e restano nell'ordine di prima perché l'ordine era giusto: la PWA non
ha prerequisiti, la voce ne ha.

**W7.1 — PWA**: `manifest.json`, service worker (solo la scocca dell'app, **mai
le risposte**), icone, `apple-mobile-web-app-capable`. Icona sulla home
dell'iPhone, funziona sulla VPN.

**W7.2 — Registratore in pagina**: `MediaRecorder` → `POST /api/audio` →
trascrizione → nella chat come un messaggio scritto. Il pulsante voce oggi
*parla* ma non *ascolta*: l'ingresso non è mai stato costruito.

**W7.3 — Whisper.** **Attenzione: non è un modello Ollama** (verificato: 404).
Serve un servizio a parte. Scelta consigliata: `faster-whisper` in un container
con GPU sul PC, e `base`/`small` su CPU come ripiego sul server. Vale il
principio del §2.1 della visione: PC prima, server sempre.

**W7.4 — Piper** sul server per la risposta parlata: funziona anche a PC spento.

*Verifica di W7*: dall'iPhone, dall'icona sulla home, tenere premuto, parlare,
e ricevere una risposta — letta ad alta voce.

---

## 9. Quello che serve dal proprietario

Senza queste, i passi indicati restano fermi.

1. **«Nuova versione di Hermes»: quale?** Presumo `NousResearch/hermes-agent`.
   Se intendeva un altro progetto, W6 cambia.
2. **Il token Telegram** da @BotFather (o la scelta di un altro canale fra
   quelli che `hermes-agent` supporta: Signal, SMS, Matrix).
3. **Una chiave gratuita** fra Groq, Cerebras, NVIDIA NIM, Cloudflare: bastano
   una email e due minuti, e accendono W2.
4. **La rubrica**: nome e indirizzo delle persone a cui Hermes può scrivere.
5. **Conferma su MASTER**: che il patto di W5.3 — *codice e servizi si
   propongono come diff, si applicano con un suo clic* — sia quello che vuole.
   Se vuole l'applicazione automatica, va detto qui, perché cambia il disegno e
   cambia il rischio.
6. Le decisioni ancora aperte da [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md) §8:
   Ceph, `psycopg2`, Open WebUI, Ente Photos, SSH alla VM 120.

---

## 10. L'ordine, e cosa dipende da cosa

```
W1 catalogo+download ─┐
W2 preset+rotte ──────┼──> W3 pannello rifatto
W4 rubrica email ─────┘
                       └──> W5 MASTER (azioni, segreti, diff, registro)
                                 └──> W6.4 MCP
W6.1-6.3 hermes-agent (indipendente) ──> W7.2 voce da Telegram
W7.1 PWA (nessun prerequisito: si può fare subito)
```

**L'ordine consigliato**: `W7.1` (la PWA, perché è mezz'ora e gli dà Hermes in
tasca subito) → `W1` → `W2` → `W4` → `W3` → `W5` → `W6` → `W7.2-7.4`.

`W5` sta dopo `W3` per una ragione: la modalità master ha bisogno di
un'interfaccia dove mostrare i diff e le conferme, e quell'interfaccia è `W3`.

Regola valida per ogni passo, senza eccezioni: **si committa solo con
`scripts/validate-repository.ps1` che passa 10 gruppi su 10**, e un runbook
nuovo in `docs/04_apps/` deve rispettare il contratto (scopo, sizing, DNS, NPM,
Homepage, Kuma, backup, restore, rollback, troubleshooting, sorgenti).

---

## 11. Fonti

- Ruflo (harness, router per intenti, astrazione fornitori) — <https://github.com/ruvnet/ruflo>
- NousResearch/hermes-agent — <https://github.com/NousResearch/hermes-agent>
- Modelli Ollama, catalogo — <https://ollama.com/library>
- API di Ollama (`/api/pull`, `/api/tags`, `/api/delete`) — <https://docs.ollama.com/api>
- Migliori modelli per 16 GB di VRAM — <https://localaimaster.com/vram/best-ollama-models-16gb-vram> · <https://www.morphllm.com/best-ollama-models>
- Fornitori gratuiti e limiti — <https://github.com/cheahjs/free-llm-api-resources> · <https://github.com/amardeeplakshkar/awesome-free-llm-apis> · <https://freellm.net/providers/>
- Bedrock, endpoint compatibile OpenAI — <https://docs.aws.amazon.com/bedrock/latest/userguide/inference-openai.html>
