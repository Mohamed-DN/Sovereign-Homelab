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

### Il costo vero, ed è uno solo

**L'identità della persona non arriva al filtro degli strumenti.**
`invoke_hook("pre_tool_call", ...)` passa `tool_name, args, task_id,
session_id, tool_call_id, turn_id, api_request_id, middleware_trace` —
nessun `user_id`. hermes-agent sa *se* uno è autorizzato (allowlist binaria per
piattaforma, `gateway/authz_mixin.py`), non *chi è*. I ruoli esistono solo per
gli slash command (`gateway/slash_access.py`, due livelli) e come booleano
Discord.

Il nostro doppio filtro — *cosa il ruolo della persona permette* × *cosa il
motore è degno di vedere* — ha bisogno di quel dato nel punto esatto in cui
oggi non c'è.

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

### Fase 2 — Momo ha la memoria
Il nostro Postgres + Qdrant + Valkey come `MemoryProvider`
(`plugins/memory/sovereign/`). I nostri strumenti di memoria entrano da
`get_tool_schemas()`, non come tool sciolti.
*Verifica*: gli si dice un fatto, si riavvia, se lo ricorda ancora — lo stesso
test di accettazione già usato per la memoria attuale.

### Fase 3 — Momo ha le mani
I 23 strumenti come plugin (`ctx.register_tool`): vault, stato dell'impianto,
accessi, rubrica, email, web, procedure.
*Verifica*: legge una nota del vault, riferisce lo stato reale di un servizio,
manda una mail a un contatto in rubrica.

### Fase 4 — Momo ha le guardie
La parte che non si delega, in ordine di rischio:
- **filtro privato/non privato**: via `check_fn` per-tool e `pre_tool_call` →
  `{"action":"block"}`;
- **filtro per ruolo della persona**: qui serve la divergenza #1;
- **guardie anti-bugia**: `post_tool_call` + `pre_verify` (`{"action":"continue"}`
  rimanda indietro il modello) + `transform_llm_output` (sostituisce il testo
  della risposta — è esattamente il nostro «Non ho salvato niente»);
- **MASTER**: azioni come dati, divieto assoluto compilato nel plugin,
  armamento a scadenza, registro. Il gate di approvazione umano di
  hermes-agent è già fail-closed e si aggancia con
  `{"action":"approve","rule_key":...}`.
*Verifica*: **le stesse prove passate dall'Hermes attuale**, tutte, nessuna
esclusa. Un motore non privato deve ricevere 2 strumenti su N e non vedere che
MASTER esiste. `qm stop 110` deve essere rifiutato.

### Fase 5 — Momo esce di casa
Telegram (`plugins/platforms/telegram/`, il bot `@dn_momo_bot` e il token sono
già pronti dal 2026-07-30), poi voce, poi il passaggio del testimone su
`hermes.internal` — solo dopo che le fasi 2-4 sono verificate.

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
