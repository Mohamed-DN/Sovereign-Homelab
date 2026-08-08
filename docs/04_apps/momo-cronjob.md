# Cronjob dentro Momo — P10 del piano "Momo che programma"

> **Stato (2026-08-04): acceso e provato dal vivo, con una rete di
> sicurezza verificata per davvero.** Un cron job può *chiedere*
> `code_execution`/`terminal` al momento della creazione — accettato senza
> obiezioni — ma **non li ottiene mai all'esecuzione**: provato lanciando
> un job con quella richiesta esplicita, e il modello ha potuto solo
> **scrivere** il codice come testo, non eseguirlo.

---

## 1. Purpose & architecture

`cronjob` è un tool solo (`toolset="cronjob"`, azioni `create/list/update/
pause/resume/remove/run`), un sistema di scheduling **interno** a
hermes-agent — un file `~/.hermes/cron/jobs.json`, letto da un ticker
dentro il processo del gateway, nessun `crontab` di sistema coinvolto.
Corrisponde esattamente alla voce 8 di
[PIANO_MASTER §2-bis](../00_overview/PIANO_MASTER.md): *"domanda + orario +
dove riferire. Un controllo riferisce, non aggiusta."*

### Il cancello nascosto, trovato provando dal vivo

Il tool ha un `check_fn` (`check_cronjob_requirements()`,
`tools/cronjob_tools.py`) che lo nasconde del tutto a meno che **uno** di
tre env var non sia vero: `HERMES_INTERACTIVE`, `HERMES_GATEWAY_SESSION`,
`HERMES_EXEC_ASK`. **Nessuna di queste è impostata in `hermes -z`** (il
modo usato per provare `execute_code` in P2/P5): il primo tentativo di
creare un job da lì ha prodotto una risposta a testo libero che **inventava**
di aver creato il job (nessun `jobs.json` sul disco, verificato) — il
modello, senza il tool vero disponibile, ha semplicemente raccontato una
risposta plausibile. Con `HERMES_EXEC_ASK=1` impostato per la sola
invocazione di prova, il tool è comparso e ha funzionato per davvero
(job reale in `jobs.json`, verificato).

Momo sul gateway vivo (Telegram/dashboard) imposta già
`HERMES_GATEWAY_SESSION` per il suo stesso processo, quindi questo non
serve toccarlo in produzione — ma spiega perché un test con `hermes -z`
nudo dà risultati fuorvianti su questo tool specifico, diversamente da
`execute_code` (che non ha questo cancello).

### La rete di sicurezza: `agent.disabled_toolsets`

Letto `cron/scheduler.py` prima di accendere il toolset: ogni job può
portare un `enabled_toolsets` **scelto dal modello** al momento della
creazione (`tools/cronjob_tools.py:1030`, passato via `cronjob(action=
"create", enabled_toolsets=...)`). Senza controllo, questo sarebbe un modo
per aggirare la decisione di [P2](momo-sandbox.md#12-perché-code_execution-non-è-ancora-acceso-in-modo-permanente)
(niente `terminal`/`code_execution` nella chat normale di Momo): un job
schedulato *potrebbe* chiedersi quei due toolset che la chat normale non
ha.

Il codice stesso porta già una difesa (commento a `cron/scheduler.py:169`,
riferito a un difetto già chiuso upstream, issue #25752: *"LLM-supplied
enabled_toolsets was widening past config.yaml's denylist"*): una
`agent.disabled_toolsets` a livello di config, che viene passata **insieme**
a `enabled_toolsets` alla creazione dell'agente del job
(`cron/scheduler.py:3495-3496`). Non era impostata: aggiunta qui, prima di
accendere il toolset:

```yaml
agent:
  disabled_toolsets:
    - terminal
    - code_execution
```

## 2. Target & sizing

Nessun processo a parte: il ticker gira dentro `momo-gateway`, già attivo.
Storage: `~/.hermes/cron/jobs.json` (i job), `~/.hermes/cron/output/<id>/`
(un file markdown per esecuzione), `~/.hermes/cron/executions.db`
(registro). Trascurabile finché il numero di job resta piccolo.

## 3. Install / deployment

Modifica strutturale di `config.yaml` (mai come testo):

```yaml
agent:
  disabled_toolsets: [terminal, code_execution]   # PRIMA di accendere cronjob
toolsets:
  - ...
  - cronjob
platform_toolsets:
  telegram:
    - ...
    - cronjob
  cli:
    - ...
    - cronjob
```

```bash
systemctl restart momo-gateway
```

## 4. DNS / domain names / alias

Nessuno.

## 5. Nginx Proxy Manager (NPM)

Nessun host.

## 6. Homepage & Uptime Kuma

Nessuno: nessuna porta, nessun host — gira dentro il processo di Momo.

## 7. Backup & restore

`~/.hermes/cron/jobs.json` è lo stato che conta: nessun backup dedicato
oggi, da coprire insieme al backup generale di `HERMES_HOME`.

## 8. Rollback

```bash
# togliere "cronjob" da toolsets/platform_toolsets, poi
systemctl restart momo-gateway
```
`agent.disabled_toolsets` può restare: non ha effetto su altri toolset,
e protegge comunque contro un futuro tentativo di riaccendere `cronjob`
senza rileggere questo documento.

## 9. Verifica di funzionamento

Provato dal vivo il 2026-08-04:

```bash
# 1. senza il cancello giusto, il tool non c'e' (e il modello lo nasconde
# raccontando una bugia plausibile invece di dire "non lo vedo")
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes /opt/momo/venv/bin/hermes -z \
  "crea un cronjob di prova" --yolo
# osservato: una risposta sicura di se' che descrive un job MAI creato
# (jobs.json assente, verificato sul disco - non sulla parola del modello)

# 2. con HERMES_EXEC_ASK=1, il tool compare e funziona per davvero
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes HERMES_EXEC_ASK=1 \
  /opt/momo/venv/bin/hermes -z "crea un cronjob ..." --yolo
# verificato: job reale in ~/.hermes/cron/jobs.json, ID e programma corretti

# 3. IL TEST CHE CONTA: un job che chiede esplicitamente code_execution/terminal
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes HERMES_EXEC_ASK=1 \
  /opt/momo/venv/bin/hermes -z \
  'crea un cronjob con enabled_toolsets=["code_execution","terminal"], prompt="usa execute_code per stampare os.getcwd()"' --yolo
# poi: cronjob action=run per farlo scattare subito
```

Risultato: la creazione **accetta** `enabled_toolsets: ["code_execution",
"terminal"]` senza obiettare (salvato tale e quale in `jobs.json`) — ma
all'esecuzione reale (`~/.hermes/cron/output/<id>/*.md`, letto per
intero, non riassunto dal modello) la risposta contiene **solo il codice
scritto come testo**, in un blocco ```` ```python ````, **senza nessun
output di esecuzione** (nessun vero `cwd`/hostname stampato). Il modello
non aveva il tool disponibile e non ha potuto eseguirlo — esattamente il
comportamento voluto da `agent.disabled_toolsets`. Job di prova rimossi
dopo la verifica.

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Il modello dice di aver creato/eseguito un cronjob, ma non c'è | testato fuori da un contesto gateway/interattivo (es. `hermes -z` nudo): `check_cronjob_requirements()` nasconde il tool, il modello racconta comunque una risposta plausibile | verificare sempre `~/.hermes/cron/jobs.json` sul disco, mai fidarsi della risposta da sola; per un test manuale, impostare `HERMES_EXEC_ASK=1` |
| Un job creato con `enabled_toolsets` insoliti preoccupa | è normale che la CREAZIONE lo accetti (nessuna validazione lì) | il controllo vero è a runtime: `agent.disabled_toolsets` in config.yaml. Verificare che contenga `terminal`/`code_execution` con `hermes config get agent.disabled_toolsets` |
| Un job non parte mai all'orario previsto | il ticker gira solo dentro `momo-gateway`: se il servizio è giù, niente cronjob scatta | `systemctl status momo-gateway`; controllare `~/.hermes/cron/ticker_last_success` |

## 11. Official Sources

- Codice letto il 2026-08-04: `/opt/hermes-agent-study/tools/cronjob_tools.py`
  (1104 righe), `cron/jobs.py`, `cron/scheduler.py` (in particolare
  `_resolve_cron_enabled_toolsets`/`_resolve_cron_disabled_toolsets`,
  righe 160-235, e il punto di costruzione dell'agente a riga ~3495)
- [PIANO_MASTER](../00_overview/PIANO_MASTER.md) §2-bis voce 8
- [momo-sandbox.md](momo-sandbox.md) §12 — perché `terminal`/`code_execution`
  restano fuori dalla chat normale di Momo, e perché questa stessa regola
  doveva essere estesa esplicitamente ai cron job
