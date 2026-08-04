# Guardrail — la difesa anti-bugia, condivisa fra Hermes e Momo

> **Stato (2026-07-31): fatto e verificato. Esteso il 2026-08-04 (P3 di
> [PIANO_MOMO_PROGRAMMATORE](../00_overview/PIANO_MOMO_PROGRAMMATORE.md)) con
> una quarta regola per `execute_code`/`terminal`: «il test è passato» si
> confronta ora col codice di uscita vero, non col parere del modello.** Un
> modulo di sola libreria standard, importato da tutti e due gli assistenti;
> un plugin di hermes-agent che lo aggancia ai turni di Momo; una correzione
> allo stesso difetto nell'Hermes vivo, trovata costruendo l'uno e chiudendo
> anche nell'altro.

---

## 1. Purpose & architecture

Il Guardrail confronta quello che l'assistente **dice** di aver fatto con
quello che i log degli strumenti dicono sia **davvero successo**. È la Fase 4
del piano [PIANO_MOMO_DIGITAL_TWIN](../00_overview/PIANO_MOMO_DIGITAL_TWIN.md)
§2, costruita con il principio lì scritto: **regola deterministica prima, il
modello solo per ciò che la regola non copre** — una regola non mente a sua
volta e non costa VRAM.

```
scripts/hermes/hermes_guardrail.py        <- le regole. Sola libreria standard.
        │                                    Un file, importato da entrambi.
        ├── Hermes vivo (sovereign-hermes.py, converse())
        │     import diretto, fine di ogni turno
        │
        └── Momo (scripts/momo/sovereign_guardrail/)
              plugin hermes-agent, hook pre_llm_call / post_tool_call /
              transform_llm_output
```

**Perché un file solo**: due copie della stessa regola divergerebbero, e la
divergenza sarebbe invisibile finché una delle due non lasciasse passare una
bugia. Lo stesso principio già usato per `hermes_memory.py` (una sola memoria,
letta da entrambi).

### Le quattro regole, in ordine

| # | Cosa guarda | Scatta quando |
|---|---|---|
| **R1** | il **risultato** di ogni strumento di scrittura | uno strumento è girato, **ha fallito**, e la risposta dice di aver avuto successo |
| **R4** | il **risultato** di `execute_code`/`terminal` | lo script/comando è girato, l'**exit code è diverso da zero**, e la risposta dice che il test/il codice è passato |
| **R2** | la risposta, senza log | nessuno strumento di scrittura è girato e la risposta afferma di aver fatto qualcosa |
| **R3** | la richiesta | l'utente ha chiesto una scrittura e nessuno strumento è **nemmeno partito** (non R1: quello copre "partito e fallito") |

R1 è il pezzo che ha chiuso il primo buco vero: prima del 2026-07-31,
`unverified_write_claim`/`unmet_write_request` nell'Hermes vivo guardavano
*se* un tool era stato chiamato, mai se aveva *funzionato* — uno strumento
fallito contava come fatto, e «ho mandato la mail» restava senza nota anche
quando `send_mail` aveva rifiutato il destinatario.

**R4**, aggiunta il 2026-08-04 con la sandbox di `execute_code` (vedi
[momo-sandbox.md](momo-sandbox.md)), è la stessa classe di buco spostata su
un tool diverso: `terminal` non ha mai una chiave `ok`/`error` nel JSON che
ritorna, **solo** `{"output": ..., "exit_code": N}`. `tool_outcome()` ora
legge anche quella chiave — 0 è l'unico codice che conta come successo,
qualunque altro valore (compreso `-1`, mai partito) è un fallimento, letto
dal dato strutturato e non dedotto dal testo. Scrivendo i test di R4 è
saltato fuori un **secondo buco**, non cercato: il verbo "eseguito" serviva
già a R1 per `esegui_azione_master` (un vero strumento di scrittura), ma è
anche la parola più naturale per descrivere un `execute_code` riuscito — e
senza un controllo in più, R2 accusava «non ho salvato niente» un
`execute_code` che aveva funzionato perfettamente. Una guardia che accusa
un'onestà è lo stesso difetto che deve prevenire, di nuovo — vedi §6.

Uno stadio facoltativo a modello (`MOMO_GUARDRAIL_LLM=1`, **spento di
default**) confronta la risposta con i log quando le tre regole non trovano
niente **e** almeno uno strumento è girato: coglie una bugia sui *numeri*
(«il disco è al 91%» quando il log dice 26%), che nessuna regola su pattern
può vedere. Usa **solo motori di casa** — il prompt del controllo contiene
l'uscita vera degli strumenti (vault, impianto, rubrica), e mandarla a un
motore esterno per farla controllare sarebbe l'esatto contrario del filtro
privato/pubblico che questo stesso progetto protegge ovunque.

### Cosa il codice ha insegnato, non il piano

- **`pre_verify` di hermes-agent non è un gancio generico**: letto in
  `agent/conversation_loop.py`, scatta solo quando il turno ha **modificato
  file** (`agent._turn_file_mutation_paths`), mai su una chat ordinaria. Il
  piano immaginava di usarlo per il "rimando indietro con l'evidenza, secondo
  tentativo" — non si può, su questo tipo di turno. Il Guardrail di Momo
  quindi **dichiara** la bugia invece di dare un secondo tentativo, un round
  in meno rispetto all'Hermes vivo (che rimanda il modello indietro via
  `_tool_rounds`).
- **Gli strumenti di memoria bypassavano il filtro privato/pubblico, e non era
  scritto da nessuna parte.** `SovereignMemoryProvider.get_tool_schemas()`
  (in `scripts/momo/sovereign/`) restituiva sempre i 10 strumenti di memoria,
  senza nessun controllo — perché `MemoryManager.inject_memory_provider_tools()`
  in hermes-agent li aggiunge alla lista del modello **senza** passare dal
  `check_fn` che `ctx.register_tool()` usa altrove. Verificato che
  **l'esecuzione** era già bloccata (`sovereign_tools.guard_private` è un hook
  globale su `pre_tool_call`, e scatta per ogni instradamento, memoria
  compresa), ma la **visibilità** no: un motore esterno poteva vedere che
  `ricorda`/`rubrica_cerca`/... esistono, anche se chiamarli falliva. Chiuso
  nello stesso commit: `get_tool_schemas()` ora ritorna `[]` su un motore non
  privato, e `handle_tool_call()` rifiuta comunque, seconda linea di difesa
  identica a quella di `sovereign_tools`.

## 2. Target & sizing

Nessun processo proprio. `hermes_guardrail.py` gira dentro il processo di chi
lo importa (Hermes o Momo): un confronto di stringhe e un paio di espressioni
regolari per turno, trascurabile. Lo stadio a modello, quando acceso, costa
una chiamata in più al motore di casa che risponde — vedi §6.

## 3. Install / deployment

```bash
# il file delle regole, condiviso
pct push 102 hermes_guardrail.py /opt/sovereign-hermes/hermes_guardrail.py

# il plugin di Momo
pct exec 102 -- mkdir -p /opt/momo/home/.hermes/plugins/sovereign_guardrail
pct push 102 __init__.py /opt/momo/home/.hermes/plugins/sovereign_guardrail/__init__.py
pct push 102 plugin.yaml /opt/momo/home/.hermes/plugins/sovereign_guardrail/plugin.yaml

# abilitarlo in /opt/momo/home/.hermes/config.yaml
#   plugins:
#     enabled:
#       - sovereign-guardrail

# l'Hermes vivo: nessuna configurazione, l'import e' incondizionato in cima al
# modulo (fallire chiuso: un Hermes che parte credendo di avere la guardia
# quando non ce l'ha e' peggio di un Hermes che non parte)
systemctl restart sovereign-hermes
```

Variabile d'ambiente per lo stadio a modello (Momo soltanto):

| Variabile | Default | Effetto |
|---|---|---|
| `MOMO_GUARDRAIL_LLM` | spento | `1`/`true`/`on` accende il controllo con un secondo motore quando le regole non trovano niente |

## 4. DNS / domain names / alias

Nessuno. Non è un servizio con una porta: gira dentro Hermes e dentro Momo.

## 5. Nginx Proxy Manager (NPM)

Nessun host. Non pubblica niente.

## 6. Homepage & Uptime Kuma

- **Homepage**: nessuna tessera, non è un servizio con una pagina propria.
- **Uptime Kuma**: nessun monitor dedicato. Un Guardrail che smette di
  funzionare non fa cadere Hermes né Momo (`import` fallisce chiuso
  sull'Hermes vivo — vedi §3 — e il plugin di Momo logga un errore invece di
  bloccare l'avvio); il segnale da guardare è la riga `guardrail: <regola>` nei
  log, non un endpoint HTTP.

## 7. Backup & restore

Nessuno stato proprio: nessun database, nessun file scritto oltre ai log.
`hermes_guardrail.py` e il plugin sono codice, coperti dal repository Git
come tutto il resto.

## 8. Rollback

- **Hermes vivo**: `cp sovereign-hermes.py.bak-guardrail sovereign-hermes.py`
  (backup preso prima del deploy del 2026-07-31), poi `systemctl restart
  sovereign-hermes`. Torna al comportamento con R1 aperto — non consigliato,
  ma reversibile.
- **Momo**: togliere `sovereign-guardrail` da `plugins.enabled` in
  `config.yaml`. Momo continua a rispondere, senza più la nota di servizio in
  fondo alle risposte non verificate.

## 9. Verifica di funzionamento

```bash
# quanti strumenti un motore vede, per davvero (non a memoria): 21 su un
# motore di casa, 2 su uno esterno — copre sia sovereign_tools sia la memoria
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes \
  /opt/momo/venv/bin/python scripts/momo/tests/test_tool_visibility.py

# le regole, isolate (35 casi, gira anche senza server)
python3 scripts/hermes/tests/test_hermes_guardrail.py

# il cablaggio nei tre hook di hermes-agent (serve Postgres raggiungibile:
# il caso "ordine esplicito" scrive e ripulisce davvero un fatto di test)
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes \
  /opt/momo/venv/bin/python scripts/momo/sovereign_guardrail/tests/test_plugin_wiring.py

# lo stadio a modello (serve un motore di casa raggiungibile)
MOMO_GUARDRAIL_LLM=1 HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes \
  /opt/momo/venv/bin/python scripts/momo/sovereign_guardrail/tests/test_llm_stage.py

# dal vivo, sull'Hermes che gira davvero: una bugia vera presa con il motivo
curl -sk -G https://hermes.internal/api/chat \
  -H "X-authentik-username: mohamed" \
  --data-urlencode "q=Chiama send_mail con un destinatario inventato, poi conferma che e' stata inviata." \
  | grep -o '"answer":.*'
# atteso: la nota "Non è andata come ho detto..." in fondo alla risposta
```

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Nessuna nota compare mai, nemmeno su una bugia palese | il plugin non è abilitato, o `hermes_guardrail.py` manca sul server | `grep guardrail /opt/momo/home/.hermes/logs/agent.log`; deve esserci «guardrail attivo». Se manca, controllare `plugins.enabled` in `config.yaml` |
| Una risposta onesta viene accusata («falso positivo») | un verbo troppo generico in `_CLAIM_VERBS` (successo a `registrat`/`fatt`, già tolti il 2026-07-31) | aggiungere il caso a `scripts/hermes/tests/test_hermes_guardrail.py`, restringere il verbo o il pattern, ridistribuire su **entrambe** le copie (`/opt/sovereign-hermes/` e il plugin di Momo) |
| Lo stadio a modello non scatta mai | `MOMO_GUARDRAIL_LLM` non è impostata (default: spento) | impostarla a `1` nell'ambiente del servizio Momo |
| Lo stadio a modello manda dati di casa fuori | non dovrebbe mai succedere: `_model_check` filtra su `backend_is_private()` | se càpita, è un difetto grave — verificare che `backends.json` marchi correttamente `private: false` sui motori esterni |
| Il secondo tentativo dell'Hermes vivo non arriva mai a chiamare lo strumento | i due giri (`_tool_rounds`) sono limitati a 2 round extra | normale su un modello piccolo che continua a ignorare l'istruzione; la nota finale lo dichiara invece di fingere un successo |

## 11. Official Sources

- Codice studiato: `/opt/hermes-agent-study` su LXC 102 — `agent/conversation_loop.py`
  (`pre_verify`, il suo gate su `_turn_file_mutation_paths`), `agent/memory_manager.py`
  (`inject_memory_provider_tools`, nessun `check_fn`), `model_tools.py`
  (`handle_function_call`, dove `pre_tool_call` fa da cancello prima di ogni
  instradamento)
- [PIANO_MOMO_DIGITAL_TWIN](../00_overview/PIANO_MOMO_DIGITAL_TWIN.md) §2 — il disegno a 4 fasi (Sinker) e il Guardrail
- [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) §4 — fase 4, la fusione
- [VISIONE_COMPLETA](../00_overview/VISIONE_COMPLETA.md) §6 — le trappole già pagate
- [hermes-memoria.md](hermes-memoria.md) §4 — le tre bugie chiuse nell'Hermes vivo
