# Le skill di Momo — P4 del piano "Momo che programma"

> **Stato (2026-08-04): fatto e provato dal vivo.** Il toolset `skills`
> (`skills_list`, `skill_view`, `skill_manage`) è acceso per Momo, con
> l'approvazione umana **obbligatoria** prima che una skill proposta diventi
> attiva. Provato dal vivo: proposta → in attesa → tentativo di
> approvazione respinto per contenuto non valido → scartata. Mai attivata
> senza controllo.

---

## 1. Purpose & architecture

Il piano originale ([PIANO_MOMO_DIGITAL_TWIN](../00_overview/PIANO_MOMO_DIGITAL_TWIN.md))
chiamava questo pezzo "Automation Library": la capacità di Momo di salvare
una procedura riuscita per riusarla. Il codice di hermes-agent ce l'ha già,
ma **letto il codice, non le note**, si è scoperto che il rischio vero non è
quello che il piano immaginava.

### Cosa dice `SECURITY.md` di NousResearch, verificato dal vivo

> *"Skills execute arbitrary Python at import time."* — e girano **con i
> pieni privilegi del processo agente**, senza nessun confinamento dal
> terminal-backend isolation costruito in [P1/P2](momo-sandbox.md). L'unica
> difesa che i loro stessi documenti riconoscono è la **revisione
> dell'operatore prima dell'installazione**.

Su questa casa, questo pesa doppio: **Momo gira come `root`**, direttamente
su LXC 102, la stessa macchina di Vaultwarden, Postgres e
`/root/sovereign-secrets/` (verificato: `systemctl show momo-gateway -p
User` non ritorna niente → nessun `User=` nel file di servizio → root di
default; `ps aux` conferma `root ... /opt/momo/venv/bin/python3 ...
hermes`). `SECURITY.md` §4 dice esplicitamente: *"Run the agent as a
non-root user. The supplied container image does this by default."* — il
nostro impianto attuale è **esplicitamente fuori** da quella raccomandazione
minima, indipendentemente da qualunque cosa si faccia con le skill. Questo
non è un problema nuovo introdotto da P4: è un fatto preesistente su cui P4
ha acceso una luce. La soluzione vera è containerizzare l'intero processo di
Momo — la stessa direzione già scritta in
[PIANO_MOMO_PROGRAMMATORE §7-bis](../00_overview/PIANO_MOMO_PROGRAMMATORE.md#7-bis-il-whole-process-wrapping-trovato-cercando-la-risposta-ufficiale)
per un altro motivo (whole-process wrapping). Finché non è fatta, l'unico
argine reale per le skill resta il controllo umano descritto qui sotto.

### Cosa fa DAVVERO `skill_manage` (letto il codice, non dedotto)

Buona notizia, verificata leggendo per intero `tools/skill_manager_tool.py`,
`tools/skills_tool.py`, `agent/skill_commands.py`, `agent/skill_bundles.py`,
`agent/skill_utils.py`: **nessuno di questi file chiama `exec`/`eval`/
`import_module`/`__import__`**. Quando Momo chiama `skill_manage(action=
"create", ...)`, scrive un file `SKILL.md` — **testo**, markdown con
frontmatter — in `~/.hermes/skills/<nome>/`. Non è l'esecuzione di Python
"all'importazione" di cui parla `SECURITY.md` in generale: quella si
riferisce alle skill che **includono script** (vedi sotto), non al
meccanismo di scrittura in sé.

**Il rischio vero, verificato sul disco**: `~/.hermes/skills/` conteneva
già, prima di questo lavoro, **13 categorie di skill ufficiali** spedite con
hermes-agent stesso (`productivity/powerpoint`, `github/github-pr-workflow`,
`research/arxiv`, `creative/comfyui`, ...), **con script Python veri** dentro
cartelle `scripts/` (es. `productivity/powerpoint/scripts/thumbnail.py`,
`productivity/powerpoint/scripts/office/helpers/pptx_chart.py`). Erano già
sul disco, semplicemente **invisibili** a Momo perché il toolset `skills`
era spento. Accendendolo, Momo ora le VEDE (`skills_list`/`skill_view`) — ma
**non può eseguirle**, perché `terminal`/`code_execution` restano fuori dai
suoi toolset per la decisione di [P2](momo-sandbox.md#12-perché-code_execution-non-è-ancora-acceso-in-modo-permanente).
Nessuna chiamata a uno script di una skill può partire senza un tool che
esegua comandi — e Momo, nella chat normale, non ne ha uno. Questo è
verificato per costruzione (guardando quali toolset sono accesi), non
sperato.

### Il cancello: `skills.write_approval`

Esiste già nel codice, spento di default. Acceso qui:

```
skill_manage(action="create", ...)
        │
        ▼
  skills.write_approval: true?
        │
   ┌────┴────┐
   │ no       │ sì
   ▼          ▼
scrive     STAGING in
subito     <HERMES_HOME>/pending/skills/<id>.json
in         (mai in ~/.hermes/skills/)
~/.hermes/         │
skills/            ▼
           un umano: /skills approve <id>  o  /skills reject <id>
                   │
                   ▼
        approve: skill_manage() rigiocato IDENTICO, RI-VALIDATO
        (provato dal vivo: un contenuto diventato non valido nel
        frattempo viene respinto anche in approvazione, non solo
        alla creazione)
```

`skills.guard_agent_created: true` (acceso anche questo) aggiunge una
scansione regex (`tools/skills_guard.py`, pattern di exfiltrazione,
injection, distruzione, persistenza, rete, offuscamento) anche sulle skill
create da Momo stesso — spenta di default upstream ("l'agente può già fare
lo stesso via `terminal()` senza controllo", `skill_manager_tool.py:109-112`)
ma accesa qui per difesa in profondità, visto che è comunque testo, non
codice, e non costa niente.

## 2. Target & sizing

Nessun processo proprio. Il toolset aggiunge tre funzioni al processo di
Momo già in esecuzione. Le skill in pending sono file JSON piccoli
(`<HERMES_HOME>/pending/skills/*.json`), il costo di storage è trascurabile.

## 3. Install / deployment

Modifica strutturale di `config.yaml` (mai come testo — regola di casa dopo
il troncamento dell'83% del 2026-08-01), con
[`scripts/momo/momo-abilita-skills.py`](../../scripts/momo/momo-abilita-skills.py)
(`yaml.safe_load` → modifica dell'oggetto → `yaml.safe_dump`, idempotente):

```yaml
skills:
  write_approval: true       # il cancello: niente diventa attivo senza /skills approve
  guard_agent_created: true  # scansione regex anche sulle skill che Momo crea da solo
toolsets:
  - ...
  - skills                   # espande a skills_list, skill_view, skill_manage
platform_toolsets:
  telegram:
    - ...
    - skills
  cli:
    - ...
    - skills
```

```bash
pct push 102 scripts/momo/momo-abilita-skills.py /tmp/momo-abilita-skills.py
pct exec 102 -- /opt/momo/venv/bin/python3 /tmp/momo-abilita-skills.py
pct exec 102 -- systemctl restart momo-gateway
```

**Deliberatamente NON impostato**: `skills.external_dirs` (skill da fonti
esterne/hub). Quelle passano già obbligatoriamente per
`skills_guard.scan_skill()` all'installazione — un controllo automatico
reale, non opzionale come `guard_agent_created` — ma restano comunque codice
di terze parti da leggere di persona prima di installarle, per lo stesso
principio di `SECURITY.md` §2.4: *"Reviewing a skill means reading its
Python code and scripts, not just its SKILL.md description."* Non è stata
installata nessuna skill esterna in questo lavoro.

## 4. DNS / domain names / alias

Nessuno.

## 5. Nginx Proxy Manager (NPM)

Nessun host.

## 6. Homepage & Uptime Kuma

- **Homepage**: nessuna tessera.
- **Uptime Kuma**: nessun monitor. Il segnale da guardare è la coda di
  approvazione: `pending_count("skills")` (`tools/write_approval.py:192`)
  o, più semplicemente, `/skills pending` dalla console/Telegram (non da
  `hermes -z`, che tratta l'input come un messaggio normale e non intercetta
  gli slash-comandi — verificato dal vivo, vedi §9). Da considerare per P10
  (cronjob): un controllo che avvisi se una proposta resta in coda troppo a
  lungo.

## 7. Backup & restore

Stato in due posti: `~/.hermes/skills/` (skill attive) e
`~/.hermes/pending/skills/` (proposte in attesa). Nessuno dei due ha un
backup dedicato oggi — da valutare insieme al backup generale di
`HERMES_HOME`, fuori dallo scope di questo lavoro.

## 8. Rollback

```bash
# disattivazione semplice: il toolset esce, skill_manage/skills_list/
# skill_view spariscono dallo schema che Momo vede. Le skill gia' attive
# restano sul disco (innocue: solo testo, senza il toolset nessuno le legge)
pct exec 102 -- bash -lc '
  cp /opt/momo/home/.hermes/config.yaml.bak-p4-skills /opt/momo/home/.hermes/config.yaml
  systemctl restart momo-gateway
'
```
Nessun impatto su altri toolset: `sovereign`/`file`/`memory`/`clarify`/
`todo`/`vision` restano quello che erano.

## 9. Verifica di funzionamento

Provato dal vivo il 2026-08-04, attraverso il vero strumento, non un bypass:

```bash
# 1. proposta di una skill di prova
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes /opt/momo/venv/bin/hermes -z \
  "Crea una skill di prova chiamata prova-p4-skill che spiega come controllare
   lo spazio disco con df -h. Usa lo strumento skill_manage." --yolo
# atteso: la risposta dice "salvato in staging", con un pending_id e le
# istruzioni per /skills approve <id> — NON scritto in ~/.hermes/skills/
```

Risultato: esattamente questo. `~/.hermes/skills/prova-p4-skill/` **non è
mai stata creata**; è comparsa una riga in
`~/.hermes/pending/skills/0efdaea4.json`.

```python
# 2. il percorso di approvazione, chiamando le stesse funzioni che
# /skills approve userebbe (write_approval.py, skill_manager_tool.py)
from tools import write_approval as wa
from tools.skill_manager_tool import apply_skill_pending

pending = wa.list_pending("skills")          # 1 trovata
result = apply_skill_pending(pending[0]["payload"])
```

Risultato: **respinta anche in approvazione** — `{"success": false, "error":
"Description is 69 chars — new skills must fit the 60-char system-prompt
budget..."}`. La skill di prova aveva una descrizione troppo lunga: il
sistema **ri-valida al momento dell'approvazione**, non si fida di quello
che era stato controllato alla creazione. Restata in pending dopo il
tentativo fallito (non consumata).

```python
# 3. il percorso di rifiuto
ok = wa.discard_pending("skills", pending[0]["id"])   # -> True
```

Risultato: rimossa dalla coda. `~/.hermes/skills/prova-p4-skill/` conferma
**mai esistita** — verificato con `ls`, non assunto.

```bash
# 4. il toolset funziona anche per il lato di lettura
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes /opt/momo/venv/bin/hermes -z \
  "Elenca le categorie di skill disponibili, in breve."
# atteso: le 12-13 categorie preesistenti (productivity, github, research, ...)
```
Risultato: elencate correttamente.

**Non provato**: l'invocazione di `/skills approve`/`/skills pending` come
slash-comando reale da Telegram o dalla console interattiva — `hermes -z`
tratta quel testo come un messaggio normale al modello (che ha
allucinato una risposta plausibile ma inventata, invece di eseguire il
comando: vedi §10). Il meccanismo *sotto* al comando è provato (punto 2-3
sopra); l'interfaccia slash-comando andrebbe verificata la prima volta che
Mohamed la usa per davvero da Telegram.

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Una skill proposta risulta subito attiva, senza passare da pending | `skills.write_approval` non è `true`, o `momo-gateway` non è stato riavviato dopo la modifica | `hermes config get skills.write_approval`; se `false`, ripetere §3 |
| `/skills approve <id>` "non trova" niente quando digitato in `hermes -z` | **atteso**: `-z` (one-shot) non intercetta gli slash-comandi, li passa al modello come testo normale, che può allucinare una risposta plausibile ma falsa (verificato dal vivo: ha risposto "nessuna skill in attesa" quando ce n'era una) | usare Telegram o `hermes console` (REPL interattivo) per i comandi `/skills`, non `-z` |
| Un'approvazione fallisce con un errore di validazione | corretto per costruzione: `apply_skill_pending()` rigioca `skill_manage()` per intero, che ri-valida (lunghezza descrizione, frontmatter, dimensione) — non è un bug, è la ri-validazione voluta | correggere il contenuto proposto e ricreare la skill, oppure scartarla con `/skills reject <id>` |
| Momo dice di aver eseguito lo script di una skill (es. `powerpoint/scripts/thumbnail.py`) | non dovrebbe poter succedere: `terminal`/`code_execution` non sono nei suoi toolset. Se succede, è un difetto grave da investigare subito — verificare `platform_toolsets` in config.yaml | `hermes config get platform_toolsets.telegram` — non deve contenere `terminal` né `code_execution` |
| Vuoi installare una skill da fonte esterna (hub) | passa comunque per `skills_guard.scan_skill()` all'installazione (automatico, diverso da `guard_agent_created`) ma resta codice di terze parti | leggerla di persona prima (`hermes skills audit --deep` per un controllo statico aggiuntivo, non un blocco) |

## 11. Official Sources

- Codice letto per intero il 2026-08-04, non le note di rilascio:
  `/opt/hermes-agent-study/tools/skill_manager_tool.py` (1768 righe),
  `tools/skills_tool.py` (1828 righe), `tools/skills_guard.py`,
  `tools/skills_ast_audit.py`, `tools/skill_provenance.py`,
  `tools/write_approval.py`, `toolsets.py` (voce `"skills"`)
- [NousResearch/hermes-agent SECURITY.md](https://github.com/NousResearch/hermes-agent/blob/main/SECURITY.md) —
  §2.1 (skill loading non confinato), §2.4 (Skills Guard è "review aid, non
  un confine"), §2.5 (stesso principio per i plugin), §4 (raccomandazione di
  girare come utente non-root, non seguita oggi su questa LXC)
- [momo-sandbox.md](momo-sandbox.md) §12 — perché `terminal`/`code_execution`
  restano fuori dai toolset di Momo, e perché questo protegge anche le 13
  categorie di skill preesistenti con script veri
- [PIANO_MOMO_PROGRAMMATORE](../00_overview/PIANO_MOMO_PROGRAMMATORE.md) §7-bis —
  il whole-process wrapping che risolverebbe anche il problema "Momo gira
  come root", non solo l'isolamento del backend comandi
