# Il piano generale — venti punti, tutto quello che c'è in ballo

> Scritto il 2026-07-31 su mandato del proprietario: *«tutti i piani che sono da
> fare o non ancora iniziati mettili e implementali però prima recuperali tutti,
> ri-architetta il tutto poi procedi»*, e *«riorganizzare il mega plan in vari
> punti anche 10 o 20 quanti ne servono»*.
>
> **Questo documento sostituisce [ORDINE_DEI_LAVORI.md](ORDINE_DEI_LAVORI.md)**
> come fila di lavoro. Quello resta valido come ragionamento sul criterio; qui
> c'è la fila completa, con dentro anche ciò che era stato perso per strada.
>
> Come è stato costruito: rilette le **quattro sessioni di lavoro archiviate**
> (130 messaggi del proprietario, dal 2026-07-09 al 2026-07-31), tutti i 19
> documenti di `00_overview/`, i file di memoria, e **verificato sul vivo** ciò
> che si poteva verificare. Dove non ho provato, lo dico.

---

## 0. Cosa ho trovato recuperando, che non era in nessun piano

Queste sono le voci emerse **solo** dalla rilettura delle vecchie sessioni e dei
file di memoria. Non stavano in `PIANO_MASTER.md`, e la regola scritta lì dice
che ciò che non è in tabella è stato dimenticato. Erano dimenticate.

| | Cosa | Da dove viene | Stato reale |
|---|---|---|---|
| R1 | **Repo → vault Obsidian**: la documentazione dentro Obsidian | chiesto il 2026-07-15, ridisegnato in [PIANO_HERMES_ESPANSO](PIANO_HERMES_ESPANSO.md) §6 | **mai costruito** — è la tua domanda di oggi, dettaglio al §1 |
| R2 | **Healthcheck di CouchDB rotto** | trovato **oggi, sul vivo** | **282 giri falliti**: il container è `unhealthy` da giorni |
| R3 | **Deprovisioning a scadenza**: tolto un ruolo, dopo una settimana si cancella il profilo sul servizio | sessione 2026-07-13, msg #47 | da verificare se fatto |
| R4 | **Ruotare la password admin riusata** | memoria `console-and-mirror-inflight`, issue #2 §6b | **aperto** — debito di sicurezza |
| R5 | **Ritirare `headscale-ui`** dopo la validazione di Headplane | stessa fonte | aperto |
| R6 | **Persistere la finestra metriche a 20 minuti** | stessa fonte | aperto |
| R7 | **Primo login OIDC su `headplane.internal` deve essere mohamed** (il primo che entra ne diventa proprietario) | stessa fonte | **aperto, e ha una scadenza implicita** |
| R8 | **Potare lo snapshot VM110 `preimmich_v302`** | stessa fonte | aperto dal 2026-07-14 |
| R9 | **`agent-reach`** per arrivare dove SearXNG non arriva | passato dal proprietario il 2026-07-29 | mai fatto |
| R10 | **SSO Tier 1: Proxmox e PBS** | ROADMAP §1 | Paperless fatto, gli altri due no |
| R11 | **Open WebUI senza admin rivendicato** | trovato il 2026-07-31 | **risolto spegnendolo** — ma il lavoro era rimasto **non committato**: vedi §0-bis |

### 0-bis. Lavoro finito e mai committato: Open WebUI

Trovati **19 file modificati** nel repository, non committati. Letti: sono un
lavoro coerente e concluso — **la rimozione di Open WebUI** dall'impianto.

Verificato sul vivo il 2026-07-31, perché un documento che dice «rimosso» non è
una prova:

| Controllo | Risultato |
|---|---|
| Container `open-webui` | **non esiste più**, nemmeno fermo |
| Porta 3004 | nessuna risposta |
| `ai.internal` in NPM, Homepage, matrici DNS/porte/visibilità | rimosso dai documenti, coerente con il vivo |

Quindi la domanda aperta di ieri — *«creare l'admin o spegnere il servizio?»* —
**è stata decisa e eseguita**: spento. Restava solo da committare. Un impianto
vivo e un repository che non lo racconta è la situazione che questo progetto
evita per principio, e ci mancava un commit.

E una cosa che **era** stata chiesta e che invece **è stata fatta** — la scrivo
perché cercandola non l'avevo trovata nei piani e ho rischiato di rifarla:
l'invito VPN dal pannello IAM, l'auto-aggiornamento di Immich con ritorno
indietro a 24 ore, e i top-3 consumatori nei grafici. Fatti il 2026-07-14, sono
solo nel file di memoria e non in `PIANO_MASTER.md`.

---

## 1. La tua domanda: dove sono i repo dentro Obsidian

**Non ci sono, e non ci sono mai stati.** Non è che si siano persi: quel pezzo
non è mai stato costruito. Te lo dico con la prova, perché è esattamente il
tipo di cosa su cui non voglio farti credere il contrario.

Verificato oggi:

| Controllo | Risultato |
|---|---|
| Il vault vero | `C:\Users\Mohamed\Documents\VaultMohamed\VaultMohamed\` |
| Contiene una cartella `Sovereign-Homelab`? | **no** — ci sono `00 Dashboard`, `01 Daily` … `07 Notes`, `Broway`, `Excalidraw`, `Reply` |
| Esiste uno script che copia `docs/` nel vault? | **no**, in tutto il repository |
| Lo stato dichiarato nei piani | `PIANO_MASTER.md` §3 Fase 4: *«Repo → vault: la documentazione dentro Obsidian — **da fare**»* |

Quindi il piano era giusto e scritto ([PIANO_HERMES_ESPANSO](PIANO_HERMES_ESPANSO.md)
§6, con il verso `repo docs/ → script sul PC → vault → LiveSync → CouchDB`), ma
nessuno l'ha mai eseguito. È il **punto 3** di questa fila, e non è tre ore: è
uno script e un timer.

Nel cercarlo ho trovato altre due cose che ti riguardano:

- **Due cartelle `VaultMohamed`**, una in `Documents\VaultMohamed\VaultMohamed`
  (quella vera, con `.obsidian`) e una in `C:\Users\Mohamed\VaultMohamed` che
  contiene solo `Reply`. Più due backup di configurazione del 30 luglio. Da
  chiarire quale sia autorevole prima di scriverci dentro: sbagliare cartella
  qui significa scrivere note in un posto che nessuno sincronizza.
- **CouchDB risulta `unhealthy` da 282 controlli** — ma il servizio **è vivo**.
  L'healthcheck interroga `/` senza credenziali e CouchDB risponde `401`. È un
  falso allarme, però è la stessa classe di problema del `HEALTH_WARN` di Ceph:
  un allarme sempre acceso maschera il prossimo allarme vero.

---

## 2. Le tre valutazioni che mi hai chiesto

Criterio che mi hai dato, e che seguo: **il migliore, non il più leggero.**
*«non lightweight ma the best if not use langh»*.

### 2.1 Langfuse — **sì, ed è la scelta giusta**

Serve a un difetto documentato e tuo: *«gli strumenti dei sotto-agenti non sono
visibili in pagina»* — vedi il piano, non le singole chiamate. Era già in coda
come **A7** in [PIANO_AGGIORNAMENTO_DA_NEXI](PIANO_AGGIORNAMENTO_DA_NEXI.md), e
lo stesso Nexi lo usa.

È il capofila dichiarato del settore (31,5k stelle, licenza MIT, self-hosting
senza limitazioni). Due cose da sapere prima di dire sì:

- **ClickHouse ha acquisito Langfuse il 16 gennaio 2026.** Resta MIT e resta
  self-hostable, ma la proprietà è cambiata: per un progetto che sceglie
  l'open source per sovranità, è un fatto da mettere agli atti, non da
  scoprire dopo. La difesa è la solita di questa casa: gira in casa, i dati non
  escono, e se un giorno la licenza cambia si esporta e si sostituisce.
- **Costa in servizi**: la versione self-hosted vuole Postgres, ClickHouse,
  Redis e un archivio compatibile S3. Postgres e Valkey ci sono già; ClickHouse
  e MinIO sono nuovi. **Oggi è sostenibile**: dopo il passaggio a 32 core LXC
  102 gira con il nodo a 2,44 di carico su 40.

Le alternative che ho valutato e **scartato** per questo caso: *Arize Phoenix*
(più leggero e OTel-nativo, ma meno completo su prompt e valutazioni), *Opik*
(Apache 2.0, buono, comunità minore), *OpenObserve* (AGPL, ottimo come
telemetria generale, non specializzato sugli agenti). Se il criterio fosse
stato «il più leggero» avrei detto Phoenix. Il criterio è «il migliore», e su
tracce di agenti il migliore è Langfuse.

### 2.2 LangChain — **no, e non è una questione di peso**

Qui la risposta non cambia rispetto a quella già scritta nel piano di Nexi, e il
tuo criterio la rafforza invece di ribaltarla.

Il motivo non è che LangChain sia pesante: è che **il lavoro che farebbe è già
fatto meglio**. Momo gira su `hermes-agent` di NousResearch, che ha già
sessioni, plugin, strumenti, orchestratore di sotto-agenti e sette adattatori
di messaggistica. Mettere LangChain accanto significa avere **due** astrazioni
per la stessa cosa, e la nostra conosce questa casa — ruoli, filtro
privato/non privato, Guardrail — mentre LangChain no. Non è un aggiornamento,
è un secondo strato da tenere allineato.

**La cosa migliore per «Momo crea funzioni e flussi nuovi» esiste e non è
LangChain: è MCP** (`Model Context Protocol`), già in coda come **W6.4** nel
[piano esecutivo](PIANO_ESECUTIVO_2026-08.md). `hermes-agent` ha già
`mcp_serve.py`. Se il *nostro* Hermes impara a parlare MCP **da client**, ogni
server MCP che esiste al mondo diventa uno strumento senza scrivere una riga di
codice nostro. È la risposta strutturale a «poche opzioni», ed è lo standard
che l'industria ha scelto. Un flusso nuovo poi si salva nell'**Automation
Library** (punto 8), che è il pezzo che ti fa dire a Momo «l'hai già fatto una
volta, rifallo».

### 2.3 OpenRouter e OmniRoute — **tutti e due, con ruoli diversi**

Non sono in concorrenza:

| | Cos'è | Ruolo |
|---|---|---|
| **OmniRoute** | il gateway **in casa**, già installato su LXC 102, dietro SSO e con chiave API | il commutatore locale: sceglie fra la GPU del PC, quella del server e i fornitori |
| **OpenRouter** | un servizio **esterno**, già presente come preset in `providers-presets.json` | il ripiego del ripiego, e solo per lavoro non privato |

La cosa utile che OpenRouter sa fare e che va sfruttata: si passa un **array
`models`** in ordine di preferenza e lui scende da solo al successivo quando il
primo è giù, a corto di contesto o rifiuta. Cioè il *fallback* non lo devi
scrivere tu. Attenzione a un dettaglio dell'API: `models` e il campo `fallbacks`
**non si possono combinare** — insieme danno errore 400.

**Il vincolo che non si tocca**: la rotta `privato` non può cadere su un motore
non privato, nemmeno se è l'unico acceso. Vale già ed è verificata contro un
tentativo esplicito di forzarla. OpenRouter è un motore non privato: vault,
memoria, impianto e rubrica non lo vedono mai.

---

## 3. La fila — venti punti

Il criterio dell'ordine è quello di sempre: **cosa sblocca cosa**, le **guardie
prima dei poteri**, a parità vince **l'uso quotidiano**, e ogni voce ha una
**verifica eseguibile**.

### ONDATA A — Chiudere quello che è aperto (prima di aggiungere)

*Nessuna di queste è nuova. Sono buchi trovati oggi o rimasti indietro, e
lasciarli aperti mentre si costruisce sopra è il modo di pagarli due volte.*

---

#### **1 · Obsidian: il vault giusto, e un incidente trovato e chiuso** ⏱ fatto, con un residuo

Il prerequisito del punto 3: prima di scrivere nel vault bisogna sapere **quale**
vault. **Risolto senza ambiguità**: Obsidian stesso registra un solo vault
(`obsidian.json`) — `Documents\VaultMohamed\VaultMohamed`, 309 file, aperto di
recente. L'altra cartella (`C:\Users\Mohamed\VaultMohamed`) ha un file solo e
**non è nemmeno nell'elenco di Obsidian**: è un residuo, non un vault attivo,
non tocca nulla del sync. Confermato anche che LiveSync sincronizza davvero:
`obsidiandb` a `update_seq` 3452, 54 MB di dati reali.

**Il falso allarme sull'healthcheck era un sintomo di qualcosa di più grosso.**
Investigandolo è emerso che l'intera configurazione di CouchDB (§3 del runbook
Obsidian — `require_valid_user`, CORS, dimensioni massime) **non è persistita
in nessun volume né in git**: vive solo nel layer scrivibile del container, e
sparisce in silenzio a ogni `--force-recreate`. È successo qui, dal vivo,
tentando la correzione: il ricreare il container per applicare un healthcheck
diverso ha **cancellato `require_valid_user`**, il confine di sicurezza reale
del sync secondo lo stesso runbook. Il container è ripartito `healthy`,
`/_up` rispondeva `200` — **e sembrava tutto a posto**. Nessun dato del vault
è stato esposto (`_all_dbs`/`obsidiandb` restavano protetti anche così), ma il
confine dichiarato era comunque sparito senza che nulla lo segnalasse.

**Ripristinato e verificato** rieseguendo la sequenza esatta del runbook
(`require_valid_user` vero su `chttpd` e `chttpd_auth`, CORS, dimensioni) e
controllando gli stessi test che il runbook stesso documenta: `_all_dbs` senza
credenziali → `401`, con credenziali → `200`.

**Residuo, deliberatamente non chiuso oggi**: l'healthcheck di Docker torna a
dire `unhealthy` — cosmetico (nulla nell'impianto reagisce a quel campo; il
monitor Kuma separato tollera già il 401 correttamente) — ma la correzione
vera richiede modificare `docker-compose.yml`, il che vuol dire un altro
`recreate` sullo **stesso container vivo** che ha appena perso una config
critica per lo stesso motivo. Non lo rifaccio oggi. Prima serve testarlo su un
CouchDB usa-e-getta, non sul vault vero — dettagli e avviso permanente in
[obsidian.md](../04_apps/obsidian.md), sezione Troubleshooting.

*Verifica fatta*: `require_valid_user` letto `"true"` su entrambe le chiavi;
`_all_dbs` 401/200 coerenti con il runbook; dati intatti (`update_seq` 3452
invariato).

---

#### **2 · Il debito di sicurezza rimasto aperto** ⏱ ~1 ora (due voci su quattro erano già chiuse)

Verificato sul vivo il 2026-07-31, **prima di toccare niente**:

- ~~R7 — primo login Headplane~~ — **già fatto**: il commento nel
  `docker-compose.yml` di `core-network` lo conferma, datato 2026-07-14.
  La nota di memoria che lo dava per aperto era stata scritta a metà lavoro.
- ~~R5 — ritirare `headscale-ui`~~ — **già fatto**: nessun container in
  nessun LXC. `headscale.internal` fa 302 verso Headplane.

Resta aperto, e verificandolo è emerso un difetto nuovo:

- **R4 — ruotare la password admin riusata.** È la stessa password usata in più
  posti (`password-try-first`), il che la rende un punto singolo di rottura.
  **Non eseguita qui senza conferma**: tocca il login su più servizi alla
  volta, e sbagliare la sequenza vuol dire restarne fuori. Serve prima
  l'elenco di dove è riusata (Proxmox root, Authentik/LDAP, i break-glass) e
  poi la conferma tua sul quando farla — non è un'azione da un rigo.
- ~~R6 — persistere la finestra metriche~~ — **già fatto**: `metrics-long.jsonl`
  esiste ed è popolato, **25 985 campioni** (~18 giorni a 1/minuto), caricati
  all'avvio da `load_long_history()`. Solo l'anello dei 20 minuti "adesso"
  riparte da zero al riavvio — per costruzione, è la vista dell'istante.
- ~~R8 — potare lo snapshot VM110 `preimmich_v302`~~ — **non esiste più**,
  verificato con `qm listsnapshot 110`. Al suo posto c'è
  `preimmich_auto_1785405203` (30 luglio, rollback automatico
  dell'aggiornamento v3.0.3→v3.1.0), **ancora dentro la sua finestra di 24
  ore**: è lì apposta, non si tocca. Immich verificato sano (`/api/server/ping`
  → 200) prima di guardare anche solo l'elenco.
- **R12 (nuovo, trovato oggi) — `authentik-server` fa ripartire gunicorn da
  solo**, non a orario fisso (due volte il 30/7 a 55 minuti di distanza, una
  il 31/7 dopo ~21 ore). Ogni volta un **503 transitorio** sulla discovery
  OIDC, che Headplane logga come errore ma si autorisolve in ~20s. **Indagato
  parzialmente**: `docker inspect` dice `RestartCount=0` — quindi **non** è
  Docker a far ripartire il container, non c'è stato un OOM-kill (`OOMKilled:
  false`, 6,2 GB liberi su 8), e non c'è un cron/timer su LXC 101 che lo
  tocchi. Il riavvio è interno al processo (probabile ciclo del suo stesso
  entrypoint/supervisore), non ancora causa-radice. Resta aperto: **si
  autoguarisce, quindi non è urgente**, ma un processo che si riavvia senza
  una causa nota è un sintomo da chiudere, non da archiviare.

**Bilancio**: delle quattro voci ereditate, tre erano già chiuse (R5, R6, R7)
e una era già superata dai fatti (R8). Restano solo R4 (password, serve la tua
conferma) e R12 (i riavvii di Authentik, appena scoperto).

*Verifica*: la vecchia password non apre più niente su nessun servizio; il
riavvio di `authentik-server` ha una causa identificata e documentata.

---

#### **3 · Repo → vault: la documentazione dentro Obsidian** ✅ fatto (2026-07-31), un residuo

**La tua richiesta di oggi.** Costruito ed eseguito, non solo pianificato:

```
repo docs/ ──(script sul PC, Task Scheduler)──> vault\Sovereign-Homelab\ ──(LiveSync, ad Obsidian aperto)──> CouchDB ──> Hermes/Momo
```

- `scripts/windows/Sync-DocsToVault.ps1` — `robocopy /MIR` fra `docs/` e
  `Sovereign-Homelab/` **dentro** il vault, mai la radice, mai
  `07 Notes/Hermes/` (l'area di scrittura di Hermes, separata apposta). Due
  guardie prima di toccare qualunque cosa: rifiuta se la destinazione non
  finisce esattamente in `\Sovereign-Homelab`, rifiuta se manca `.obsidian`
  nel vault di destinazione (segno che non è il vault vero).
- **Direzione unica**: repo → vault, mai il contrario — scrivere in CouchDB
  da fuori Obsidian corromperebbe le note a pezzi di LiveSync. Stessa ragione
  per cui `vault_scrivi` di Hermes resta confinato alla sua cartella.
- `scripts/windows/SyncDocsToVault.Task.xml` — al logon e ogni 30 minuti.
- Solo `*.md`/`*.png`/`*.jpg`/`*.svg`: documentazione, non codice (punto 17).

**Verificato dal vivo**: prima esecuzione manuale, 98 file / 1,06 MB copiati
con successo; `Sovereign-Homelab\00_overview\PIANO_GENERALE.md` confermato
sul disco del vault con lo stesso contenuto del repo.

**Il task è ora registrato davvero (2026-07-31, sessione successiva)**: non lo
era. Verificato con `Get-ScheduledTask` — assente — nonostante il file XML
esistesse e il documento dicesse «al logon e ogni 30 minuti». Causa, trovata
con un parser XML vero invece di fidarsi del messaggio criptico di
`schtasks.exe` («XML attività non valido», senza dire dove): un commento XML
conteneva `--` (*"the PC is on -- so..."*), che lo standard XML vieta dentro
ai commenti — la stessa classe di difetto della trappola già in
[VISIONE_COMPLETA](VISIONE_COMPLETA.md) §6 sul JS in una stringa Python,
stavolta in XML. Anche dopo la correzione, `schtasks /Create /XML` e
`Register-ScheduledTask -Xml` restavano ostili sull'encoding dichiarato;
registrato con successo costruendo il task con i cmdlet nativi
(`New-ScheduledTaskTrigger`/`-Action`/`-Principal`), bypassando del tutto
l'importer XML. **Provato per davvero**: `Start-ScheduledTask` a mano,
`LastTaskResult: 0`, `NextRunTime` in coda.

**Residuo, non un difetto**: LiveSync sincronizza verso CouchDB solo mentre
**Obsidian è aperto** (è un plugin dentro l'app). I file arrivano sul disco
ad ogni esecuzione del task (ora automatica); la propagazione a CouchDB — e
quindi la verifica dal telefono — aspetta la prossima apertura di Obsidian su
questo PC.

*Verifica ancora tua da fare*: apri Obsidian su questo PC una volta, poi dal
telefono trova `Sovereign-Homelab/00_overview/PIANO_GENERALE.md` — questo
file. Poi chiedi a Hermes «come si ripara Nextcloud» e verifica che citi il
runbook.

---

#### **4 · Il Verificatore e l'interruttore globale** ✅ fatto (2026-08-01)

Sono **A3** e **A4** di Nexi.

- **A4 — interruttore `RUNNING`/`PAUSED`**: `scripts/hermes/sovereign_switch.py`,
  sola libreria standard, importato da Hermes (`run_tool()`, la strozzatura
  unica di ogni strumento, più `master_execute` come seconda linea), da Momo
  (due punti indipendenti: `_make_handler` e l'hook `pre_tool_call`, perché
  Momo chiama `tool["run"]` diretto e non passa da `run_tool()`) e
  dall'agente di controllo delle app (`sovereign-app-control-agent.py`, 423
  in pausa). Stesso file di stato di MASTER (`master-state.json`): non un
  secondo file, non una seconda verità. Ferma `esegui_azione_master`,
  `send_mail`, `vault_scrivi`; chat, lettura e memoria continuano — la tabella
  completa e il perché di ogni riga sono in
  [sovereign-interruttore.md](../04_apps/sovereign-interruttore.md) §1.1.
  Nome `sovereign_` e non `hermes_`, deciso: vedi punto 21.
- **A3 — il Verificatore**: `scripts/hermes/sovereign_verifier.py`, dentro il
  relay su LXC 101. Prima della prima email, riprova da solo (di default 4
  sonde, 3s di distanza) e classifica `REAL_CRITICAL` / `REAL_WARNING` /
  `FALSE_ALARM` / `UNVERIFIED`. **Trovato costruendolo**: LXC 101 non si
  fidava della CA interna (verificato: `CERTIFICATE_VERIFY_FAILED` su
  `hermes.internal`) — senza risolverlo il Verificatore avrebbe confermato
  ogni allarme come vero, perché ogni sonda `.internal` sarebbe fallita.
  Risolto con una copia stabile della CA su LXC 101
  (`/root/sovereign-secrets/ca/sovereign-root-ca.crt`). Solo la regola, senza
  stadio a modello (divergenza dichiarata da A3 di Nexi, motivata in
  [sovereign-verificatore.md](../04_apps/sovereign-verificatore.md) §1.4): un
  allarme che tace perché il servizio di chat è giù sarebbe il difetto
  peggiore possibile. Due tetti (3 falsi allarmi consecutivi, 15 minuti)
  garantiscono che il peggio che può fare è ritardare un allarme vero, mai
  cancellarlo.

*Verifica fatta, sul vivo*: messo in `PAUSED` da CLI su LXC 102 —
`esegui_azione_master` rifiutato con motivo («prova dal vivo»), la chat ha
risposto comunque (`{"answer":"pronto"}`), l'agente app ha dato `423` su
start/stop, `/api/master/status` ha mostrato `running:false` con chi/quando/
perché. Ripreso: tutto tornato a `running:true`, `armed_until` di MASTER
intatto. Il Verificatore sondato sul vivo: `files.internal` sano → 3/3
`FALSE_ALARM`; un host inesistente → `REAL_CRITICAL` con `TLSV1_UNRECOGNIZED_NAME`
riconosciuto come colpa del servizio, non della sonda. 102 casi di test
(41+38+23, quest'ultimo il Guardrail invariato) passano tutti; il conteggio
21 strumenti su motore di casa / 2 su motore esterno resta identico dopo il
cambio dell'hook di Momo.

---

### ONDATA B — Vedere, e industrializzare

*Prima di dare più potere a Momo, bisogna poter vedere cosa fa. E prima di
aggiungere il ventitreesimo servizio, conviene smettere di aggiungerli a mano.*

---

#### **5 · Langfuse: vedere cosa fanno davvero gli agenti** ⏱ ~4 ore

Il punto 2.1 spiega perché lui e non altri. Cosa comporta:

- Stack nuovo su LXC 102: Langfuse + ClickHouse + MinIO, riusando il Postgres e
  il Valkey che già ci sono.
- Strumentare `sovereign-hermes.py` e i plugin di Momo: ogni chiamata di
  strumento, ogni passaggio dello sciame, ogni verdetto del Guardrail diventa
  una traccia.
- In pagina: dalla risposta si arriva alle **singole chiamate**, non solo al
  piano. Chiude il difetto noto.
- Le tracce contengono l'uscita vera degli strumenti — quindi **restano in
  casa**, dietro SSO, e valgono le regole di `PRIVATE_TOOLS`.

*Verifica*: fai una domanda che accende lo sciame e in Langfuse vedi l'albero
completo con i tempi; una bugia presa dal Guardrail si ritrova nella traccia
con il motivo.

---

#### **6 · Aggiungere un servizio con un comando** ⏱ ~4 ore

**La tua richiesta**, con le tue parole: *«le cose comuni le automatizziamo, le
cose che possono cambiare le manteniamo separate ma censite»*. È esattamente il
disegno giusto, e il repository è già a metà strada: c'è `deploy.sh <service>`,
c'è `common_docker_app_pattern.md` con il contratto, c'è la checklist di
accettazione. Quello che manca è **il censimento** e **l'esecutore**.

La parte **variabile e censita** — un manifesto per servizio, `services/<nome>.yaml`:

```yaml
nome: mealie
immagine: ghcr.io/mealie-recipes/mealie:v3.0.2   # sempre appuntata, mai :latest
host_interno: mealie.internal
lxc: 102
porta: 9925
sso: authentik-oidc          # oppure: forward-auth | nessuno
dati:
  - /opt/sovereign-homelab/data/mealie
backup: pbs                  # oppure: restic | nessuno
sacro: false                 # true = non si tocca, mai
```

La parte **comune e automatica** — `sovereign-service.py new <nome>`, che dal
manifesto fa da sé, in ordine, tutto il contratto: stack da modello, DNS in
AdGuard, host proxy in NPM **via API** (mai file scritti a mano — è una trappola
già pagata), provider Authentik, tessera su Homepage, monitor su Kuma, copertura
di backup, e lo scheletro del runbook in `docs/04_apps/`.

*Verifica*: un servizio nuovo di prova entra in produzione con un comando e
`validate-repository.ps1` passa 10 gruppi su 10 senza ritocchi a mano.

---

#### **7 · Toglierlo con un comando, e pulito** ⏱ ~2 ore

*«per rimuoverle c'è sempre script di drop pulito»*. Sì, ed è la metà che di
solito nessuno scrive — motivo per cui gli impianti si sporcano.

`sovereign-service.py drop <nome>` legge lo **stesso** manifesto e disfa in
ordine inverso: monitor, tessera, provider SSO, host proxy, DNS, container,
volumi. Con tre regole che non si negoziano:

1. **I dati non si toccano di default.** Il drop ferma e rimuove il servizio;
   cancellare i dati richiede `--purge-data` e una conferma esplicita, con il
   percorso scritto sotto gli occhi.
2. **La lista sacra è compilata a codice**: Immich, Vaultwarden, NPM, AdGuard,
   Headscale, PBS, Authentik. Sono già esclusi dai controlli della dashboard;
   qui vale lo stesso, e `sacro: true` nel manifesto non basta — deve essere
   nel codice, perché un file si modifica e il divieto no.
3. **Prima si prova a vuoto**: `--dry-run` stampa cosa toccherebbe.

Questo punto è anche il prerequisito pulito del **punto 9** (le sandbox): un
teardown che sa disfare solo ciò che un manifesto dichiara è la stessa forma del
teardown che può distruggere solo ciò che ha creato.

*Verifica*: metti su un servizio finto, toglilo, e l'impianto torna identico a
prima — nessun host proxy orfano, nessun monitor in rosso, nessuna voce in
Homepage, e i dati ancora lì finché non chiedi tu di cancellarli.

---

### ONDATA C — Momo che fa

---

#### **8 · Automation Library + MCP: come Momo impara funzioni nuove** ⏱ ~5 ore

È la risposta vera a *«facilitare a Momo di creare nuove funzioni e flussi»*.
Due pezzi che si tengono:

- **MCP da client** (W6.4): ogni server MCP esistente diventa uno strumento
  senza codice nostro. Va **dopo** MASTER, perché uno strumento MCP è codice di
  qualcun altro dentro il nostro processo, e passa dalla stessa guardia
  privato/non privato.
- **Automation Library**: **Qdrant** per cercare *lo scopo* di uno script
  («deploy database vettoriale»), **Postgres `JSONB`** per il *payload* vero
  (bash, Compose, Ansible). Stessa divisione già usata per le procedure — i
  vettori per trovare, il relazionale per l'esattezza, perché una procedura si
  esegue passo per passo e deve tornare **esatta**, non somigliante.
  Con il **riciclo** (prima di scrivere, cerca se sa già farlo) e
  l'**auto-salvataggio** (se il test passa, si salva da solo).

*Verifica*: chiedi due volte la stessa cosa a distanza di giorni; la seconda
volta la ritrova invece di riscriverla, e lo dice.

---

#### **9 · Sandbox con ciclo di vita** ⏱ ~4 ore

Creare, testare, **distruggere**. Dopo il Guardrail (fatto) e dopo il punto 7,
mai prima.

La regola che concilia con il divieto assoluto, con le tue parole — *«può
cancellare le robe che lui crea»*: l'orchestratore Python tiene il **registro di
ciò che ha creato** e passa al teardown **solo identificatori presi da lì**, mai
un nome costruito dal modello. La guardia sull'host resta l'ultima parola:
`qm destroy`, `zfs destroy`, `rm -rf` restano vietati comunque, sandbox o no.

---

#### **10 · Tool statistici (ARIMA e simili)** ⏱ ~2 ore

**Un LLM non calcola, stima** — e una stima presentata come calcolo è una bugia
con i decimali. Microservizi Python per previsioni e regressioni. Chiude anche
**A6** di Nexi: «`ssd_pool` piena fra 40 giorni» vale più di «al 26%».

Piccolo, isolato, non può rompere niente.

---

#### **11 · La squadra a grafo** ⏱ ~3 ore

Il flusso scende e risale: uno sviluppatore che trova un problema di sicurezza
passa al CISO, che può rimandare all'architetto. Oggi lo sciame è lineare.

**Tre freni obbligatori prima di scrivere una riga**, perché un grafo senza
freni non termina: tetto ai salti (e cosa si risponde quando lo si raggiunge),
rilevamento dei cicli, e i nostri **13 ruoli** mantenuti nel plugin —
`delegate_task` di hermes-agent ne conosce due.

---

#### **12 · Il Sinker completo a 4 fasi** ⏱ ~4 ore

Sink → Compute → Surface → Guardrail. La fase 4 è già fatta. Va **dopo il punto
19** (la GPU del server), perché tre chiamate a un modello sulla CPU sono
inusabili — con la via breve che degrada a Surface + Guardrail quando la GPU non
c'è, invece di farti aspettare un minuto.

---

### ONDATA D — Quello che usi ogni giorno

---

#### **13 · Più conversazioni, una sola memoria** ⏱ ~2 ore

Il difetto che hai trovato tu provando: *«valutava solo la nuova domanda
scordandosi del filo logico»*. La cronologia esiste ma è **una sola per
persona**, quindi argomenti diversi si contaminano.

| Livello | Contiene | Ambito |
|---|---|---|
| **Conversazione** | il filo del discorso | una chat |
| **Memoria** | fatti, agenda, procedure, rubrica, vault, runbook | **tutte** le chat, tutti i dispositivi |

È facile adesso: hermes-agent ha già le sessioni e il nostro `MemoryProvider`
riceve già `session_id`.

---

#### **14 · Telegram** ✅ fatto e verificato (2026-08-01)

Bot `@dn_momo_bot` e token pronti dal 30 luglio. Usato l'adattatore di
hermes-agent, non un bot scritto a mano.

**Il vincolo che non si tocca, rispettato**: mappatura `id Telegram → utente
di casa` compilata a mano (`TELEGRAM_ALLOWED_USERS=6805681257`),
`TELEGRAM_ALLOW_ALL_USERS=false`. Un id di Telegram non è un'identità, e l'id
è stato **catturato** da `getUpdates` facendolo scrivere al bot, non accettato
a voce.

**Il pezzo che mancava davvero non era Telegram: era che Momo non fosse un
servizio.** Girava solo da riga di comando. Ora è `momo-gateway.service` su
LXC 102 (`scripts/momo/momo-gateway.service`), e questo è anche un prerequisito
del punto 21.

*Verifica fatta, dai log del vivo*: `Connected to Telegram (polling mode)`,
poi `inbound message: platform=telegram user=... chat=6805681257` →
`response ready: time=12.1s api_calls=1` → `Sending response to 6805681257`.
Due giri completi. Con Momo arrivano **tutte le guardie** senza codice in più:
filtro privato/pubblico, Guardrail, interruttore RUNNING/PAUSED, e la memoria
condivisa con Hermes.

Runbook: [momo-telegram.md](../04_apps/momo-telegram.md). Nessuna porta
aperta: long polling, quindi niente host in NPM e niente firewall da toccare.

---

#### **15 · La voce, tutta in casa** ⏱ ~5 ore

Il pulsante voce oggi *parla* ma non *ascolta*: l'ingresso non è mai stato
costruito. Registratore in pagina → **Faster-Whisper** sul PC → **Piper** sul
server per la risposta parlata (funziona anche a PC spento) → **XTTSv2** per la
tua voce.

**Deciso il 30 luglio: niente ElevenLabs.** La tua voce non esce dall'impianto.

---

#### **16 · Momo che crea contenuti al posto tuo** ⏱ ~4 ore

**La tua richiesta di oggi**, e il vincolo che avevi posto e che resta: niente
volti, niente esseri viventi, niente musica. Restano testo, voce sintetica,
immagini di oggetti/luoghi/diagrammi/astratto, e il montaggio.

| Pezzo | Strumento | Dove |
|---|---|---|
| Testo | Momo, con la sua persona | server |
| Voce narrante | Piper | server |
| Trascrizione di partenza | Faster-Whisper | PC (GPU) |
| Immagini | ComfyUI | PC (GPU) — **solo se avanza VRAM** |
| Montaggio | `ffmpeg` | server |

Nessun servizio a pagamento. Il pezzo pesante è ComfyUI: contende la VRAM ai
modelli, quindi va per ultimo e si accende a richiesta.

---

### ONDATA E — La conoscenza

---

#### **17 · I dieci repository** ⏱ ~3 ore

Misurati: **12,7 MB di testo in 2 683 file**. Divisione già decisa:
documentazione e README **nel vault** (leggeri, tutti i plugin funzionano,
funziona offline); codice sorgente **sui database** (nessun peso sul telefono).
Si appoggia al punto 3.

---

#### **18 · Il plugin Obsidian che legge dai database** ⏱ ~5 ore

I dati stanno sul server una volta sola, ogni dispositivo li legge dal vivo — la
cosa che chiedevi il 30 luglio: *«io da qualsiasi posto posso vedere e leggere e
collegarmi se sono dentro la rete o vpn»*.

**Due verifiche aperte prima di scrivere una riga**: `requestUrl` su Obsidian
iOS, e il fatto che `.obsidian` non si sincronizza (LiveSync ha
`syncInternalFiles = false`) — quindi il plugin va installato a mano su ogni
dispositivo, o si accende la sincronizzazione dei file nascosti.

---

#### **19 · `agent-reach` e gli agenti di Ruflo** ⏱ ~4 ore

- **agent-reach** (R9): arrivare dove SearXNG non arriva — YouTube, Reddit, X,
  GitHub, RSS. Partendo dai canali che non richiedono chiave. Passa dalle
  guardie esistenti di `web_fetch` (rifiuto degli indirizzi interni, difesa
  SSRF).
- **Gli agenti di Ruflo**: da studiare con lo stesso metodo usato per
  hermes-agent — **leggere il codice, non le note di rilascio**, e riferire
  cosa regge davvero. Da Ruflo sono già venuti il router per intenti e le
  strategie di scelta, entrambi fatti.
- **Google Calendar**: appuntamenti sul calendario vero, non solo nell'agenda
  interna. Serve OAuth.

---

### ONDATA F — La potenza

---

#### **20 · La GPU del server (T600, 4 GB)** ⏱ ~1 ora

La scheda c'è e **non la usa niente**: `nvidia-smi` non è nemmeno installato. In
4 GB ci sta `qwen3.5:4b`, che è esattamente il modello di scorta che oggi
arranca sulla CPU.

**Declassata di proposito** dal primo posto: dopo il passaggio a 32 core
l'embedding sulla CPU è sceso da 3 677 ms a **264 ms**, e il guadagno atteso è
molto minore di quando la corsia lenta costava 3,7 secondi. Resta però il
prerequisito del punto 12 (il Sinker completo).

*Verifica*: `qwen3.5:4b` risponde dalla GPU del server, misurato prima e dopo —
un numero misurato vale più di una promessa.

---

### ONDATA G — Il passaggio del testimone

---

#### **21 · Momo prende il posto di Hermes** ⏱ da stimare quando si arriva

**Trovata mentre si scriveva il punto 4, e non era in questa fila.** Il
proprietario ha chiesto tre volte di fondere i due Hermes
([PIANO_AGENT_MOMO](PIANO_AGENT_MOMO.md) §1), e alla fine ha detto: *«Momo
sostituirà Hermes»*. È implicito nella **Fase 5** di quel piano — *«Momo esce
di casa […] poi il passaggio del testimone su `hermes.internal`, solo dopo
che le fasi 2-4 sono verificate»* — ma non era mai stato messo in questa fila
con i suoi prerequisiti veri. La regola del [PIANO_MASTER](PIANO_MASTER.md) è
che ciò che non è in tabella è stato dimenticato: questo lo era.

**Non è una rinomina.** Rileggendo la Fase 4 del piano di fusione, oggi
mancano due cose prima che Momo possa fare quello che fa Hermes:

- **MASTER dentro Momo**: azioni come dati, divieto assoluto compilato nel
  plugin, armamento a scadenza, registro. Oggi Momo non ha nessuna di queste
  guardie — solo il filtro privato/pubblico e il Guardrail.
- **Il filtro per ruolo della persona**: bloccato su una divergenza dal
  codice di `hermes-agent` ancora aperta (`pre_tool_call` non riceve
  l'identità di chi sta parlando — [PIANO_AGENT_MOMO](PIANO_AGENT_MOMO.md) §2,
  «il primo costo vero»). Finché non è chiusa, Momo tratta chiunque lo
  interroghi come il proprietario.

Spostare `hermes.internal` su Momo prima di questi due punti significherebbe
dargli le chiavi dell'impianto senza le due guardie che oggi lo tengono al
sicuro.

**Cosa succede ai nomi, deciso il 2026-08-01**: i moduli condivisi scritti
*dopo* questa data (`sovereign_switch.py`, `sovereign_verifier.py`) nascono
già con un nome neutro, che non dovrà cambiare al passaggio del testimone.
Quelli scritti *prima* (`hermes_memory.py`, `hermes_guardrail.py`), la
directory `scripts/hermes/` e il percorso `/opt/sovereign-hermes/` restano
com'è **fino a questo punto**, e si rinominano tutti insieme in
un'operazione sola, verificabile con lo stesso test che verifica tutto il
resto — non uno alla volta, perché un impianto in cui metà dei nomi mente per
settimane è peggio di un impianto che aspetta.

**Cosa comporta, in ordine**:
1. Chiudere Fase 4 (MASTER in Momo, filtro per ruolo — sopra);
2. La rinomina dei moduli condivisi e dei percorsi, in un commit solo;
3. Il cambio di servizio dietro `hermes.internal` (NPM, Homepage, Kuma, i
   documenti che oggi descrivono "l'Hermes vivo" come `sovereign-hermes.py`);
4. Un periodo di convivenza verificata — la stessa regola della Fase 1 della
   fusione: *«l'Hermes attuale resta acceso e intatto finché Momo non ha
   passato le verifiche. Nessun giorno senza assistente.»*

*Verifica*: le stesse sette prove che oggi passa `sovereign-hermes.py` in
modalità MASTER, tutte, su Momo; `qm stop 110` rifiutato; un motore non
privato riceve 2 strumenti e non sa che MASTER esiste; e — la prova che
conta di più — un giorno intero di uso normale dal telefono senza che nessuno
si accorga del cambio.

---

## 4. L'ordine, e cosa dipende da cosa

```
1 Obsidian sano ─────> 3 repo→vault ─────> 17 i dieci repo ──> 18 plugin dai DB
2 debito sicurezza
4 verificatore+pausa ──┬──> 9 sandbox
   ✅ fatto             └──> tutto ciò che agisce (compreso il 21)
5 Langfuse (vedere)  ──────> serve a controllare 8..12
6 add servizio ──> 7 drop pulito ──> 9 sandbox
8 Automation Library + MCP ──> 11 grafo
20 GPU server ──> 12 Sinker completo
13/14/15/16  indipendenti: si possono fare in qualunque momento
21 testimone Momo/Hermes ──> richiede: Fase 4 di PIANO_AGENT_MOMO (MASTER in
   Momo + filtro per ruolo), che a sua volta si appoggia al 4 (fatto)
```

**Da dove si comincia**: dal punto **2**, e dentro il 2 dal primo login di
Headplane — è l'unica voce di tutta la fila che ha una porta aperta adesso.
Poi 1, poi 3: in mezza giornata hai chiuso i buchi e hai i repo dentro Obsidian.
Il **4 è già fatto** (2026-08-01): l'interruttore e il Verificatore sono la
base sotto tutto ciò che agisce, incluso il passaggio del testimone del
punto 21.

## 5. Regole che valgono per ogni punto

- **Verifica prima di dichiarare.** Un passo è finito quando la verifica passa,
  non quando il codice è scritto.
- Si committa solo con `scripts/validate-repository.ps1` che passa **10 gruppi
  su 10**.
- Un runbook nuovo in `docs/04_apps/` rispetta il contratto: scopo, sizing, DNS,
  NPM, Homepage, Kuma, backup, restore, rollback, troubleshooting, sorgenti —
  più la sezione **Edge Cases** (A8 di Nexi): «cosa succede se va a metà»,
  scritto *prima*.
- Gli host proxy in NPM si aggiungono **via API**, mai scrivendo file di conf.
- Commenti in inglese, messaggi all'utente in italiano, Python di sola libreria
  standard dove possibile.

## 6. Sorgenti

- Le quattro sessioni archiviate, 2026-07-09 → 2026-07-31 (130 messaggi del proprietario)
- [ORDINE_DEI_LAVORI.md](ORDINE_DEI_LAVORI.md) · [PIANO_MASTER.md](PIANO_MASTER.md) · [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md)
- [PIANO_ESECUTIVO_2026-08.md](PIANO_ESECUTIVO_2026-08.md) · [PIANO_AGENT_MOMO.md](PIANO_AGENT_MOMO.md) · [PIANO_MOMO_DIGITAL_TWIN.md](PIANO_MOMO_DIGITAL_TWIN.md)
- [PIANO_AGGIORNAMENTO_DA_NEXI.md](PIANO_AGGIORNAMENTO_DA_NEXI.md) · [PIANO_HERMES_ESPANSO.md](PIANO_HERMES_ESPANSO.md)
- Langfuse, licenza e self-hosting — <https://langfuse.com> · acquisizione ClickHouse del 2026-01-16
- Alternative valutate — <https://openobserve.ai/blog/langfuse-alternatives/> · <https://www.firecrawl.dev/blog/best-llm-observability-tools>
- OpenRouter, fallback fra modelli — <https://openrouter.ai/docs/guides/routing/model-fallbacks>
- Alternative a LangChain, panorama 2026 — <https://www.firecrawl.dev/blog/best-open-source-agent-frameworks>
