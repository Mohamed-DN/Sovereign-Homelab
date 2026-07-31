# Agent Momo — la fusione dei due Hermes

> Scritto il 2026-07-30, dopo aver **letto il codice** di
> [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
> (v0.19.0, MIT, 352 348 righe di Python, 3 657 file), non le sue note di
> rilascio. Questo documento sostituisce il "piano C" del
> [PIANO_ESECUTIVO_2026-08](PIANO_ESECUTIVO_2026-08.md) §1, che prevedeva di
> tenere i due progetti affiancati.

---

## 1. La decisione, e chi l'ha presa

Il proprietario ha chiesto tre volte di unire i due Hermes, e alla terza ha
detto come: *«agiremo come un chirurgo e pianteremo il cuore del nostro Hermes
e le sue braccia e piedi nel corpo del nuovo Hermes […] faremo nascere il
nostro nuovo agente super forte, agent momo, che avrà anche lo sciame dei
passa agenti 60 o più»*.

Le prime due volte la risposta era stata no, per una ragione che resta valida —
`hermes-agent` non sa niente di questa casa — ma che **non era una ragione per
non fondere**: era una ragione per non *sostituire alla cieca*. Letto il codice,
la fusione è fattibile e conveniente. Questo documento dice come, e cosa costa.

## 2. Cosa abbiamo scoperto leggendo il loro codice

### Quello che ci viene incontro

| Cosa | Dove, verificato |
|---|---|
| **Sistema di plugin di prima classe** | `hermes_cli/plugins.py` (2 485 righe): 4 sorgenti di discovery, `~/.hermes/plugins/<nome>/` con `plugin.yaml` + `register(ctx)`. **18 metodi di registrazione**, **~25 hook** |
| **Policy scritta che protegge l'interfaccia** | `AGENTS.md:124-127`: rifiutano le PR con *«plugin che toccano i file del core. I plugin vivono nella loro directory e lavorano dentro le ABC/hook che forniamo; se a un plugin serve di più, si allarga la superficie generica, non si fa un caso speciale nel core»* |
| **Memoria astratta dietro una ABC** | `agent/memory_provider.py`: `initialize / system_prompt_block / prefetch / sync_turn / get_tool_schemas / handle_tool_call`, più `on_memory_write`, `on_pre_compress`. Qdrant e pgvector sono **già** backend noti (`plugins/memory/mem0/_oss_providers.py`) |
| **Ollama first-class** | `plugins/model-providers/custom/`: *«Ollama instances and OpenAI-compatible reasoning endpoints»*, `ollama_num_ctx` incluso |
| **MCP in entrambi i sensi** | client `tools/mcp_tool.py` (6 829 righe, stdio/HTTP/SSE, config dichiarativa); server `mcp_serve.py` |
| **OIDC/Authentik già previsto** | `plugins/dashboard_auth/self_hosted/`: *«speaks plain OIDC […] Authentik · Keycloak · …»*, *«touches nothing in core auth/runtime/login»* |
| **60+ agenti = un numero in un file** | `tools/delegate_tool.py`: `delegation.max_concurrent_children`, e nei commenti *«No upper ceiling on spawn depth»* |
| **Gate di approvazione umano già fail-closed** | `agent/tool_executor.py:418` → `resolve_pre_tool_block`: *«un `approve` il cui gate va in errore, nega o scade è fail-closed a un blocco»* |

### La privacy: coincide con la nostra, e non è una promessa a voce

- `AGENTS.md:118-121` rifiuta le PR con *«telemetria in uscita senza opt-in»*.
- `telemetry.shared_metrics.enabled = False`, e *«non esiste nessun sink remoto»*.
- Dove una libreria di terzi ha telemetria propria (cua-driver→PostHog,
  Vercel), **la spengono loro**.
- Dipendenze **pinnate esatte** per paura dei worm su PyPI, con i CVE nei
  commenti. L'unico upload di conversazioni è un comando manuale che passa dal
  redattore di segreti e **si blocca** se la redazione fallisce.

### I costi veri, e sono due

**Primo: l'identità della persona non arriva al filtro degli strumenti.**
`invoke_hook("pre_tool_call", ...)` passa `tool_name, args, task_id,
session_id, tool_call_id, turn_id, api_request_id, middleware_trace` —
nessun `user_id`. hermes-agent sa *se* uno è autorizzato (allowlist binaria per
piattaforma, `gateway/authz_mixin.py`), non *chi è*. I ruoli esistono solo per
gli slash command (`gateway/slash_access.py`, due livelli) e come booleano
Discord.

Il nostro doppio filtro — *cosa il ruolo della persona permette* × *cosa il
motore è degno di vedere* — ha bisogno di quel dato nel punto esatto in cui
oggi non c'è.

**Secondo, trovato il 2026-07-31 costruendo il Guardrail: i tool di un
`MemoryProvider` non passano dal `check_fn` che protegge tutto il resto.**
`ctx.register_tool()` valuta `check_fn` prima di offrire un tool al modello —
è così che `sovereign_tools` nasconde gli strumenti di casa a un motore
esterno. Ma `MemoryManager.inject_memory_provider_tools()`
(`agent/memory_manager.py`) aggiunge gli schemi restituiti da
`get_tool_schemas()` **senza nessun controllo**: nessun `check_fn`, nessuna
consapevolezza del motore che risponde. Il nostro `SovereignMemoryProvider`
(memoria di casa: `ricorda`, `dimentica`, `rubrica_*`, …) li offriva sempre.

**L'esecuzione era comunque al sicuro**: `pre_tool_call` è un cancello globale
in `model_tools.py::handle_function_call`, valutato **prima** di qualunque
instradamento — plugin, core o memory-provider. Il `guard_private` che
`sovereign_tools` registra lì blocca quindi anche una chiamata a `ricorda`
instradata dal `MemoryProvider`, verificato chiamandolo direttamente con il
motore forzato esterno. Il buco vero era più piccolo: la **visibilità**, non
l'esecuzione — un motore esterno poteva vedere che gli strumenti di memoria
esistono e leggerne la descrizione, anche se chiamarli falliva sempre. Chiuso
in `scripts/momo/sovereign/__init__.py`: `get_tool_schemas()` ora consulta lo
stesso `_engine_is_private()` di `sovereign_tools` e ritorna `[]` su un
motore non privato, con lo stesso rifiuto in `handle_tool_call()` come
seconda linea di difesa. Dettaglio completo in
[momo-guardrail.md](../04_apps/momo-guardrail.md) §1.

## 3. La strada scelta: fork minimo, e perché non è un compromesso

Il proprietario ha chiesto: *«se faccio il fork minimo posso comunque
implementare tutto? qual è il compromesso?»*

**Non c'è un compromesso di capacità.** La differenza fra fork minimo e fork
completo non è *cosa si può fare*, è **quanto codice loro diverge dal nostro**,
e quindi quanto costa ogni aggiornamento:

- fork minimo: `git pull` + riapplicare due patch piccole;
- fork completo: un merge da negoziare su 352 000 righe, per sempre.

Se durante il lavoro serve toccare altro nel core, **si tocca** — il fork
cresce e viene documentato. La regola non è "non toccare", è: **ogni riga di
divergenza dal loro codice va giustificata e scritta qui sotto**, così sappiamo
sempre cosa ci costerà il prossimo aggiornamento.

### Registro delle divergenze dal codice originale

| # | File | Cosa | Perché | Proposto a monte? |
|---|---|---|---|---|
| — | — | *(ancora nessuna: si compila mentre si lavora)* | — | — |

Le due modifiche previste (entrambe piccole e generiche, quindi buone
candidate per una PR a monte, che è la strada che la loro stessa policy
prescrive):
1. passare l'identità della persona nei kwargs di `pre_tool_call`;
2. esporre `set_thread_tool_whitelist` sul `PluginContext` — **esiste già**,
   è fail-closed, è valutata prima degli hook: manca solo di essere pubblica.

## 4. Le cinque fasi

Regola che vale per tutte: **l'Hermes attuale resta acceso e intatto** su
`hermes.internal` finché Momo non ha passato le verifiche. Nessun giorno senza
assistente. Decisione del proprietario, 2026-07-30.

### Fase 1 — Momo respira ✅ **FATTA E VERIFICATA (2026-07-30)**

Ambiente isolato su LXC 102, **zero credenziali di casa**: venv in
`/opt/momo/venv`, `HOME=/opt/momo/home` e `HERMES_HOME=/opt/momo/home/.hermes`,
così `~/.hermes` non può collidere né confondersi con nulla che l'Hermes vivo
possieda. Provider `custom` puntato a `http://192.168.1.100:11434/v1`.

*Verifica passata*: `hermes -z "Rispondi solo con la parola: pronto"` →
**`pronto`**, generato dalla GPU del PC. E, nello stesso momento,
`sovereign-hermes` **ancora `active`** con `/health` a 200: i due convivono
senza toccarsi.

**Tre cose imparate installando, che il report non poteva sapere:**

1. **Il progetto rifiuta di proposito `pip install .`** — il loro
   `pyproject.toml` alza un `RuntimeError`: *«Building wheels or sdists for
   hermes-agent is not supported. Hermes is distributed via the shell
   installer, Docker image, or Nix»*, e indica l'**editable install** per lo
   sviluppo. Che è esattamente il nostro caso: `pip install -e .` funziona, ed
   è anche la forma giusta per iterare su un plugin.
2. **62 dipendenze entrate, nessuna pesante** — niente torch, niente
   transformers, niente numpy obbligatorio. Le uniche con codice compilato
   sono `Pillow`, `cryptography`, `pydantic-core`, `uvloop`.
3. **`/opt/hermes-agent-study` non è più solo uno studio**: l'editable install
   punta lì, quindi quella directory *è* l'installazione. Il nome resta per
   ora ma va ricordato: aggiornare quel clone aggiorna Momo.

Nota sulla CLI: il flag per una domanda non interattiva è **`-z`** (non `-q`),
e `hermes model` **pretende un terminale vero** — non è usabile da script.

### Fase 2 — Momo ha la memoria ✅ **FATTA E VERIFICATA (2026-07-30)**

Plugin in `scripts/momo/sovereign/` (installato in
`$HERMES_HOME/plugins/sovereign/`), attivato con `memory.provider: sovereign`.

**Non reimplementa niente**: importa lo stesso `hermes_memory.MemoryStore` che
usa l'Hermes vivo, e la stessa tabella `TOOLS`. Due copie di una memoria
divergerebbero, e la divergenza sarebbe invisibile finché una delle due non
perde qualcosa.

La corrispondenza con il vocabolario di hermes-agent è quasi uno a uno:

| Nostro | Loro | Cosa succede |
|---|---|---|
| briefing della memoria | `system_prompt_block()` | ultimi 12 fatti + impegni, a ogni turno |
| `ricorda_cerca` automatico | `prefetch(query)` | ricerca semantica **prima** di ogni risposta, senza che il modello debba pensarci |
| i 10 strumenti di memoria | `get_tool_schemas()` + `handle_tool_call()` | ricorda/cerca/dimentica, agenda, procedure, rubrica |
| — | `sync_turn()` | **volutamente vuoto**: qui la memoria è *dichiarata*, non raccolta. Salvare ogni turno di nascosto la renderebbe non verificabile e romperebbe la promessa che `dimentica` dimentica davvero |

**La prova che conta** (non «funziona», ma «è la stessa memoria»): un fatto
salvato **attraverso Momo** è stato riletto **dall'Hermes attuale**, processo
separato, e poi dimenticato da Momo. Un solo Postgres dietro entrambi.

Stato reale al momento della verifica: Postgres ✅ · Qdrant ✅ 1829 punti ·
Valkey ✅ · embedding ✅ · 10 strumenti esposti · ricerca semantica nel vault
Obsidian che ritrova le note su Data Guard.

**Una trappola pagata**: il venv di Momo non vedeva `psycopg2` (che su LXC 102
viene da apt, non da pip — è l'eccezione dichiarata alla regola «sola libreria
standard»). Risolto con un **symlink mirato** al solo `psycopg2` invece di
`--system-site-packages`: quest'ultimo avrebbe fatto vedere al venv tutte le
librerie di sistema, scavalcando le versioni pinnate di hermes-agent — che
sono pinnate esatte apposta, per motivi di sicurezza della catena di
fornitura.

### Fase 3 — Momo ha le mani
I 23 strumenti come plugin (`ctx.register_tool`): vault, stato dell'impianto,
accessi, rubrica, email, web, procedure.
*Verifica*: legge una nota del vault, riferisce lo stato reale di un servizio,
manda una mail a un contatto in rubrica.

### Fase 4 — Momo ha le guardie
La parte che non si delega, in ordine di rischio:
- **filtro privato/non privato**: ✅ **fatto e verificato (contato dal vivo,
  2026-07-31)** — `sovereign_tools` registra 11 strumenti con `check_fn`
  per-tool (9 privati + 2 pubblici, web) e ripete il controllo dentro
  `pre_tool_call` (belt and braces); i 10 strumenti di memoria arrivano da
  `SovereignMemoryProvider` per una strada diversa (§2, "i costi veri"), gated
  allo stesso modo dal 2026-07-31. **Contato, non ricordato**: un motore di
  casa vede **21** strumenti (11+10), un motore esterno **2** (solo web, zero
  memoria) — `scripts/momo/tests/test_tool_visibility.py`;
- **filtro per ruolo della persona**: ancora sulla divergenza #1 (l'identità
  non arriva a `pre_tool_call`) — non fatto;
- **guardie anti-bugia (il Guardrail)**: ✅ **fatto e verificato (2026-07-31)**,
  vedi [PIANO_MOMO_DIGITAL_TWIN](PIANO_MOMO_DIGITAL_TWIN.md) §2 e
  [momo-guardrail.md](../04_apps/momo-guardrail.md) per il dettaglio tecnico.
  Agganciato a `pre_llm_call` (apre il turno, esegue in codice un ordine
  esplicito), `post_tool_call` (registra ogni esito, non solo il nome del
  tool) e `transform_llm_output` (attacca la nota in fondo alla risposta).
  **`pre_verify` NON è quello che il piano immaginava**: letto il codice
  (`agent/conversation_loop.py`), è gated su
  `agent._turn_file_mutation_paths` — scatta solo quando il turno ha
  **modificato file**, mai su una chat ordinaria. Il Guardrail di Momo quindi
  **dichiara** la bugia invece di rimandare indietro il modello con
  l'evidenza per un secondo tentativo, che è quello che fa l'Hermes attuale.
  È un round di verifica in meno, scritto qui perché non sparisca;
- **MASTER**: azioni come dati, divieto assoluto compilato nel plugin,
  armamento a scadenza, registro. Il gate di approvazione umano di
  hermes-agent è già fail-closed e si aggancia con
  `{"action":"approve","rule_key":...}`. Non fatto.
*Verifica*: **le stesse prove passate dall'Hermes attuale**, tutte, nessuna
esclusa. Un motore non privato deve ricevere 2 strumenti su N e non vedere che
MASTER esiste. `qm stop 110` deve essere rifiutato.

### Fase 5 — Momo esce di casa
Telegram (`plugins/platforms/telegram/`, il bot `@dn_momo_bot` e il token sono
già pronti dal 2026-07-30), poi voce, poi il passaggio del testimone su
`hermes.internal` — solo dopo che le fasi 2-4 sono verificate.

## 4-bis. I dieci repository del proprietario dentro Obsidian

Richiesta del 2026-07-30: *«ho vari repositori su github non solo il sovereign
e mi serve che momo sappia tutti i miei progetti, preferisco portarli tutti su
obsidian completamente»*, e *«mi interessano solo i loro main, non altri
branch»*.

**La misura, fatta prima di promettere qualcosa** (`gh` autenticato come
`Mohamed-DN`, cloni `--depth 1`, poi cancellati):

| | |
|---|---|
| Repository | **10** (7 pubblici, 3 privati) |
| Peso totale dei cloni | 360 MB |
| **Testo utile a Momo** | **12,7 MB in 2 683 file** |
| Non testo (immagini, binari, PDF) | ~236 MB — da non copiare |

I due numeri che cambiano il disegno: il "mega repo" **DBAdmin** pesa 62 MB su
GitHub e 214 MB di binari una volta clonato, ma ha **solo 92 file di testo**;
il grosso del contenuto vero è `dba_oracle_lab` (1 445 file, 6,2 MB). Quindi
portare *tutto il testo* è fattibile — 12,7 MB — mentre portare *tutto* non lo
sarebbe.

**Decisioni prese dal proprietario:**
- destinazione **`07 Notes/Hermes/repos/<repo>/`**: dentro la zona che Hermes
  già possiede, così la guardia sul vault resta intatta e un errore è confinato
  lì invece di poter toccare i suoi appunti;
- **prima una prova con un repository solo**, poi gli altri nove.

### Il problema vero, e l'idea del proprietario

2 683 file nuovi non sono 12,7 MB per un dispositivo: sono **2 683 documenti
che LiveSync replica su ogni telefono e ogni PC**. Il vault oggi ne ha 125. È
lo stesso difetto già annotato nel [PIANO_MASTER](PIANO_MASTER.md) §4 per i
36 MB di immagini in `06 Templates/Images`, moltiplicato.

Il proprietario ha proposto la soluzione giusta: *«sistemare il problema della
dimensione sul sync, e al massimo crei tu un nuovo plugin che si basa sui
nostri super db e che resiste»*.

**Il disegno che ne segue** (da fare, non ancora iniziato), precisato dal
proprietario il 2026-07-30: *«io devo collegare tutti i miei dispositivi a
questi plugin, ed è come se tutto fosse sui db e io da qualsiasi posto posso
vedere e leggere e collegarmi, se sono dentro la rete o vpn»*.

Non è «un plugin che scarica i file su ogni dispositivo». È il modello
opposto, ed è quello giusto:

```
        i dati stanno QUI, una volta sola
        ┌──────────────────────────────────┐
        │  LXC 102   Postgres · Qdrant     │
        │            i 2 683 file, indicizzati
        └──────────────┬───────────────────┘
                       │  si legge dal vivo, non si replica
      ┌────────────────┼────────────────┬─────────────┐
   PC Windows      iPhone           iPad          altro
   (Obsidian)      (Obsidian)       (Obsidian)    (browser)
        └── tutti dentro la rete di casa o sulla VPN ──┘
```

Il telefono non scarica 2 683 note: ne chiede **una** quando la apri. Il peso
della sincronizzazione sparisce perché sparisce la sincronizzazione — e
LiveSync continua a fare il suo mestiere solo sugli appunti scritti a mano,
che sono pochi e piccoli.

**Il compromesso, dichiarato**: quello che si legge dai database **richiede la
rete o la VPN**. Fuori dalla VPN, le note scritte a mano restano leggibili
offline (LiveSync le ha già copiate), i repository no. Il proprietario ha
accettato questo vincolo esplicitamente («se sono dentro la rete o vpn»), ed è
lo stesso patto che vale già per tutto il resto dell'impianto: per entrare
bisogna prima essere sulla VPN.

**Due cose da verificare prima di scrivere il plugin** (non ancora fatte):
1. Un plugin Obsidian può fare richieste HTTP anche su iOS (`requestUrl` esiste
   nella loro API, ma va provato su un iPhone vero, non dato per buono).
2. `.obsidian` **non si sincronizza** (`syncInternalFiles = false`, vedi
   [PIANO_MASTER](PIANO_MASTER.md) §4): il plugin va installato **a mano su
   ogni dispositivo**, oppure si accende la sincronizzazione dei file nascosti
   — che è una decisione a parte, con i suoi rischi.

Momo ha comunque memoria completa di tutto il codice a prescindere da questo
plugin: l'indice semantico vive in Qdrant ed è indipendente da Obsidian.

### Il vincolo che decide tutto, e la divisione scelta

Il proprietario ha aggiunto: *«se scrivo qualcosa dai dispositivi i db devono
aggiornarsi in tempo record e tutti i plugin devono poter funzionare»*.

La prima metà si fa: scrittura dal telefono → HTTP al server → Postgres, in
millisecondi su LAN o VPN.

**La seconda metà è in conflitto con l'architettura sui database, e non per
colpa del nostro disegno.** I plugin di Obsidian (Dataview, Templater, Time
Garden) leggono attraverso la *Vault API*: vedono **solo i file che esistono
davvero nel vault**. Un contenuto che vive su Postgres, per Dataview non
esiste. Non si aggira con un plugin — servirebbe un filesystem virtuale, che
su iOS non è possibile.

| | File nel vault (LiveSync) | Dati sui database |
|---|---|---|
| Peso sul telefono | 2 683 documenti | zero |
| Dataview, Templater, gli altri | ✅ funzionano | ❌ non li vedono |
| Offline | ✅ | ❌ serve la VPN |
| Scrittura | qualche secondo | immediata |

**Decisione del proprietario: dividere per tipo, non per tecnologia.**

- **Documentazione, README, note** (poche centinaia di file, leggeri) →
  **nel vault** via LiveSync: tutti i plugin funzionano, l'offline funziona,
  ed è la roba che si legge davvero da telefono.
- **Codice sorgente** (le migliaia di file pesanti) → **sui database**,
  cercabile da Momo e da una vista dedicata. Su un file `.py` Dataview non
  serve comunque.

È la divisione che dà a ogni tipo di contenuto lo strumento adatto, invece di
far pagare a tutto il vault il peso di una parte sola.

## 5. Cosa si guadagna e cosa si perde, senza abbellimenti

**Si guadagna**: 21 canali di messaggistica, 33 provider di modelli, un gateway
always-on, una dashboard web, l'ecosistema MCP intero (ogni server MCP diventa
uno strumento senza scrivere codice), un gate di approvazione già fail-closed,
sotto-agenti senza tetto dichiarato, e una comunità che mantiene tutto questo.

**Si perde**: il pregio di poter leggere l'intero assistente in un pomeriggio.
Oggi il nostro Hermes è **un file da ~3 000 righe di sola libreria standard**;
Momo sarà un plugin nostro dentro 352 000 righe con 32 dipendenze diritte.
Nessuna di quelle dipendenze è pesante e sono tutte pinnate, ma la superficie
da fidarsi cresce di due ordini di grandezza. È il prezzo dichiarato della
fusione, e va riletto ogni volta che si aggiorna.

**Non verificato**, e da confermare provando: il middleware
(`register_middleware`) come quarta via di intercettazione; se la sessione OIDC
della dashboard risalga fino al runtime dell'agente; il comportamento a runtime
(nulla è stato ancora avviato).

## 6. Sorgenti

- Codice studiato: clone in `/opt/hermes-agent-study` su LXC 102 (isolato, non tocca nulla di vivo)
- `AGENTS.md`, `hermes_cli/plugins.py`, `agent/memory_provider.py`, `tools/delegate_tool.py`, `tools/mcp_tool.py`, `gateway/authz_mixin.py`, `plugins/dashboard_auth/self_hosted/`, `pyproject.toml`
- <https://github.com/NousResearch/hermes-agent> · <https://hermes-agent.nousresearch.com/>
