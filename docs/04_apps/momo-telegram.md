# Momo su Telegram — l'assistente in tasca, con la porta chiusa a chiave

> **Punto 14 del [PIANO_GENERALE](../00_overview/PIANO_GENERALE.md)**, e il
> primo passo della Fase 5 di [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md).
> Scelto dal proprietario il 2026-08-01 come prima cosa da fare, dopo aver
> constatato che due sessioni di fondamenta non gli avevano dato niente che
> potesse usare.
>
> **Nessun bot scritto a mano**: si usa l'adattatore di `hermes-agent`
> (`plugins/platforms/telegram/`), che è codice mantenuto, provato, e che
> sappiamo leggere.

---

## 1. Purpose & architecture

Momo risponde su Telegram, dal telefono, ovunque — **senza aprire nessuna
porta in casa**. Il bot usa il *long polling*: è Momo che chiama Telegram, non
il contrario. Nessun webhook, nessun host in NPM, nessuna regola di firewall.

```
   iPhone / Telegram
        │
        │  (long polling in uscita: nessuna porta aperta in casa)
        ▼
   api.telegram.org
        ▲
        │
   Momo su LXC 102  ── /opt/momo, servizio systemd
        │
        ├─ allowlist TELEGRAM_ALLOWED_USERS ← il confine vero
        ├─ sovereign-tools    strumenti di casa + filtro privato/pubblico
        ├─ sovereign (memoria) Postgres · Qdrant · Valkey
        ├─ sovereign-guardrail la difesa anti-bugia
        └─ sovereign_switch    l'interruttore RUNNING/PAUSED
```

**Il vincolo che non si tocca**, con le parole del proprietario: *«mappatura
`id Telegram → utente di casa` compilata a mano, sconosciuti rifiutati. Un id
di Telegram non è un'identità.»*

Perciò:

| Variabile | Valore | Perché |
|---|---|---|
| `TELEGRAM_ALLOWED_USERS` | `6805681257` (mohamed) | l'elenco esplicito, uno per uno |
| `TELEGRAM_ALLOW_ALL_USERS` | **`false`**, sempre | è marcata «dev only» dal loro stesso `plugin.yaml`. Se un giorno la si trova a `true`, è un incidente |

### 1.1 Come si ottiene un id, e perché non si indovina

L'id si cattura facendo scrivere la persona al bot e leggendo `getUpdates`:

```bash
T=$(cat /root/sovereign-secrets/hermes-agent/telegram-bot-token)
curl -s "https://api.telegram.org/bot$T/getUpdates" | python3 -m json.tool
#  → result[].message.from.id
```

Fatto così il 2026-08-01 per il proprietario: `6805681257`, username
`Mohamed_DN`. **Non si accetta un id che qualcuno dichiara a voce**: chiunque
può dire di essere chiunque, e l'unico modo onesto è vederlo arrivare.

### 1.2 Quello che Momo NON eredita passando da Telegram

Detto invece che sottinteso, perché è la cosa che si dimentica:

- **Il filtro per ruolo della persona non esiste ancora.** `pre_tool_call` di
  hermes-agent non riceve l'identità di chi parla
  ([PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) §2), quindi Momo
  tratta **chiunque sia nell'allowlist** come il proprietario. Con un solo id
  in lista questo è sicuro; il giorno che se ne aggiunge un secondo, quella
  persona vede il vault e la rubrica. **Non aggiungere id senza chiudere prima
  quella divergenza.**
- Il filtro privato/pubblico **c'è** e vale anche qui: è un hook globale su
  `pre_tool_call`, non dipende dal canale.
- Il Guardrail **c'è** e vale anche qui, stesso motivo.
- L'interruttore RUNNING/PAUSED **c'è** e vale anche qui: in pausa Momo
  continua a rispondere su Telegram ma non manda mail, non scrive sul vault e
  non tocca l'impianto.

## 2. Target & sizing

Momo gira su **LXC 102** come servizio systemd (`momo-gateway.service`). Il
long polling è una connessione HTTPS in uscita tenuta aperta: traffico
trascurabile a riposo. Il costo vero è l'inferenza, che sta altrove — sulla GPU
del PC quando è acceso, sulla CPU del server quando non lo è.

Dipendenze aggiunte il 2026-08-01, entrambe alla versione **pinnata da
hermes-agent** (le pinnano esatte per paura dei worm su PyPI, e non è il caso
di scavalcarle):

| Cosa | Versione | Perché |
|---|---|---|
| `python-telegram-bot[webhooks]` | `22.6` | l'adattatore |
| `ffmpeg` (apt, LXC 102) | 5.1.9 | audio `.ogg`/opus per i vocali |

## 3. Install / deployment

```bash
# 1. le dipendenze
pct exec 102 -- apt-get install -y ffmpeg
pct exec 102 -- /opt/momo/venv/bin/pip install 'python-telegram-bot[webhooks]==22.6'

# 2. il token e l'allowlist, in un file d'ambiente a 0600 (MAI nel repo)
#    /root/sovereign-secrets/hermes-agent/momo-telegram.env
#      TELEGRAM_BOT_TOKEN=<da @BotFather>
#      TELEGRAM_ALLOWED_USERS=6805681257
#      TELEGRAM_ALLOW_ALL_USERS=false

# 3. abilitare il plugin in /opt/momo/home/.hermes/config.yaml
#    plugins:
#      enabled:
#        - telegram-platform

# 4. il servizio
systemctl enable --now momo-gateway
```

## 3-bis. La voce: capire e rispondere, tutto in casa

Aggiunto il 2026-08-01. **Niente di questo è codice nostro**: hermes-agent ha
già l'impianto audio completo, e la scoperta utile è stata proprio quella —
la voce via Telegram costa molto meno della voce nel browser.

```
tu mandi un vocale
   → l'adattatore lo scarica          adapter.py:9013, codice loro
   → faster-whisper lo trascrive      stt.provider: local, codice loro
   → il layer lingue stabilisce       sovereign_language.py, NOSTRO
     in che lingua hai parlato
   → Momo ragiona e risponde
   → Piper genera l'audio             tts.provider: piper, codice loro
   → send_voice, bollicina tonda      adapter.py:6798, codice loro
```

### I quattro difetti trovati accendendola

Sono tutti di **configurazione**, e nessuno dava errore: fallivano in
silenzio, che è il modo peggiore.

| Difetto | Sintomo | Causa |
|---|---|---|
| `faster-whisper` non installato | il vocale arrivava a Momo **vuoto** (`msg=''` nel log), e lui rispondeva a caso | `stt.provider: local` è il default, ma la libreria si installa a richiesta e nessuno l'aveva installata |
| `stt.language: "en"` | un vocale in arabo veniva trascritto forzando l'**inglese** | è il loro default, e il loro commento lo spiega: l'auto-detect sbaglia sulle clip corte. Giusto per un monolingue, sbagliato qui |
| `tts.provider: "edge"` | la voce sarebbe uscita da **Microsoft** | il loro default. Sostituito con `piper`, locale |
| `voice_compatible: false` | l'audio sarebbe arrivato come **allegato**, non come bollicina vocale | i provider devono dichiararlo; Piper produce mp3 e il gateway converte in Opus solo se glielo si dice |

### La configurazione, per intero

In `/opt/momo/home/.hermes/config.yaml`:

```yaml
stt:
  enabled: true
  language: ""          # riconosci tu la lingua: qui si parlano tre lingue
  echo_transcripts: true
  local:
    model: small        # "base" non regge l'arabo; small è il compromesso su CPU
    language: ""
    vad: true           # il silenzio non arriva a whisper (anti-allucinazione)

tts:
  provider: piper       # locale. Il default loro è "edge" = Microsoft
  piper:
    voice: it_IT-paola-medium
  providers:
    piper:
      voice_compatible: true   # il gateway converte in Opus e manda la bollicina

voice:
  auto_tts: true        # a un vocale si risponde anche a voce
```

Le tre voci stanno in `/opt/momo/home/.hermes/cache/piper-voices/`:
`it_IT-paola-medium`, `ar_JO-kareem-medium`, `en_US-amy-medium` — una per
lingua, perché la regola è «rispondi nella lingua in cui ti ha parlato» e una
risposta araba con voce italiana non la rispetta. **Verificate diverse
davvero** (md5 + metadati): pesavano lo stesso byte per byte, il che sembrava
un errore di scaricamento e non lo era.

Dipendenze: `piper-tts` e `faster-whisper==1.2.1` nel venv di Momo, `ffmpeg`
da apt. Il modello `small` di whisper si scarica al primo uso.

## 3-ter. Il contesto che si perdeva: erano i *topic* di Telegram

Trovato il 2026-08-01, e la causa **non era il modello**. Il proprietario
riferiva che «da domanda a domanda perde il contesto»: chiedeva l'orario di un
negozio e al messaggio dopo Momo non sapeva più di cosa si parlasse.

La prova sta nel magazzino delle sessioni, `sessions/sessions.json`:

```
agent:main:telegram:dm:6805681257:1744
agent:main:telegram:dm:6805681257:1752
agent:main:telegram:dm:6805681257:1756
agent:main:telegram:dm:6805681257:1760      ← otto sessioni, stesso utente
```

L'ultimo numero è il **`thread_id` del topic**. Il bot ha i topic attivi
(`getMe` → `has_topics_enabled: true`, `allows_users_to_create_topics: true`)
e Telegram apre un topic nuovo a ogni messaggio nuovo — l'interfaccia lo dice
persino: *«Type any message to create a new thread»*.

**Ogni topic è una sessione separata.** Quindi Momo non stava perdendo il
filo: non aveva mai avuto lo stesso filo, perché ogni domanda arrivava in una
conversazione nuova, appena nata e vuota.

Sintomo secondario dello stesso fatto, visibile nei log:
`reply_to_id=13 reply_to_text=''` — rispondeva a un messaggio di cui non
possedeva il testo, perché stava in un'altra sessione.

**La cura, in ordine di pulizia:**

1. **Spegnere i topic sul bot** (BotFather → il bot → Bot Settings). È la
   correzione alla radice, zero codice, e riporta tutto in una conversazione
   sola come una normale chat.
2. In alternativa, usare sempre lo stesso topic (il pulsante *Continue Last
   Thread*): funziona, ma dipende dal ricordarsene ogni volta.

**Non** si corregge togliendo il `thread_id` dalla chiave di sessione: quella
chiave è il modo in cui hermes-agent tiene separate le conversazioni, ed è la
cosa giusta per chi i topic li usa davvero. Il difetto è che qui i topic
nascono da soli, non che esistano.

### Il secondo guasto, nato dalla cura del primo

Aggiunto il 2026-08-02, ed è la parte che mancava a questa sezione. Spegnere i
topic in BotFather ha risolto la frammentazione **e rotto la consegna**, perché
un `thread_id` era rimasto **inciso nella configurazione**:

```yaml
platforms.telegram.home_channel:
  thread_id: '1752'      # il topic da cui il canale era stato registrato
```

Quel topic non esisteva più, e Momo rispondeva dentro un contenitore cancellato.
Il sintomo nei log di `momo-gateway`, il 2026-08-01:

```
05:49:09 WARNING gateway.platforms.base: [Telegram] Send failed:
         Message thread not found — trying plain-text fallback
05:49:09 ERROR   gateway.platforms.base: [Telegram] Fallback send also failed:
         Message thread not found
05:49:55 (identico, secondo messaggio)
```

**Quattro righe, due messaggi perduti**, e in mezzo un utente che vede il bot
muto. Il `thread_id` è stato rimosso da `config.yaml` (backup
`config.yaml.bak-thread`, che lo contiene ancora alla riga 25) e il gateway
riavviato alle 05:50:58.

La prova che la consegna è tornata **non è nei log ma nel registro delle
obbligazioni di consegna**, `delivery_obligations` in
`/opt/momo/home/.hermes/state.db`, che è il posto giusto perché registra
l'esito e non solo il tentativo:

| Orario (UTC) | `thread_id` | Stato | Tentativi |
|---|---|---|---|
| 05:49:09 | `1752` | delivered | **1** |
| 05:49:55 | `1752` | delivered | **1** |
| 05:51:29 | `NULL` | delivered | 0 |
| 05:51:59 | `NULL` | delivered | 0 |
| 05:52:24 | `NULL` | delivered | 0 |
| 05:52:46 | `NULL` | delivered | 0 |

Quelle due sono le **uniche** obbligazioni con `attempts > 0` di tutta la
tabella, e dopo il riavvio il `thread_id` è `NULL` e i tentativi tornano a
zero. Non «sembra che funzioni»: è misurato, e la riga che lo dimostra è la
colonna dei tentativi.

### Quello che la cura NON ha ripulito — verificato, e ancora aperto

Due cose sono state annotate come fatte e **non lo sono**. Si scrivono qui
perché un runbook che dichiara pulito ciò che è sporco è peggio di uno che tace.

**1. Il `thread_id` 1752 è ancora vivo altrove.** `config.yaml` non lo ha più
dal 2026-08-01 (verificato su tutti i backup in ordine di tempo), ma
`/opt/momo/home/.hermes/channel_directory.json` elenca ancora **sette canali
fantasma**, uno per topic morto:

```json
{ "id": "6805681257:1752", "name": "… / topic 1752", "thread_id": "1752" }
```

Conseguenza misurata: **allo spegnimento del gateway il messaggio di commiato
viene ancora indirizzato al topic 1752**, e l'ultima occorrenza è di **oggi**,
2026-08-02 alle 11:32:53:

```
[Telegram] Thread 1752 not found, retrying once with same thread_id
[Telegram] Thread 1752 not found, retrying without message_thread_id
```

Stavolta **non è un guasto**: l'adattatore di Telegram ha una sua ricaduta
(`retrying without message_thread_id`) e il messaggio parte lo stesso — è il
percorso `gateway.platforms.base` del 1° agosto a non averla avuta. Ma è
rumore permanente in un log, e un avviso che si ripete a ogni riavvio è
esattamente il tipo di allarme che addestra a ignorare gli allarmi. **Da
ripulire**, con attenzione: `channel_directory.json` è stato riscritto oggi
alle 11:33:09, quindi il gateway lo rigenera e cancellarlo a mano potrebbe non
bastare. Non è stato tentato.

**2. Le sessioni orfane non sono archiviate.** Erano state annotate come
«archiviate»; nella tabella `sessions` di `state.db` hanno tutte
`archived = 0`, e le sette chiavi con `thread_id` sono ancora sia in
`sessions/sessions.json` sia in `gateway_routing`:

| Sessione | Messaggi | `archived` |
|---|---|---|
| `…:1744` `…:1756` `…:1760` `…:1765` `…:1768` `…:1775` | 3–7 ciascuna | `0` |
| `…:1752` | 21 | `0` |
| `…` (senza thread, dal 05:51:24) | 34 | `0` |

Non fa danno — sono conversazioni morte che nessuno riaprirà, e la memoria vera
è altrove (Postgres/Qdrant) — ma **«archiviate» era una parola sbagliata**:
sono semplicemente *inattive*. La sessione senza `thread_id` è quella viva, ed è
l'unica che cresce.

### Le due memorie, che restano due anche dopo

Richiesta del proprietario: *«ci sono 2 memorie: memoria a sessione per non
perdere il contesto […] e un'altra memoria a livello di tutto, quella deve
aggiornarla da sola con nuovi dati»*. È esattamente il disegno già in piedi:

| Livello | Cosa contiene | Ambito | Dove |
|---|---|---|---|
| **Sessione** | il filo del discorso, le domande che dipendono dalla precedente | una conversazione | `sessions/` di hermes-agent |
| **Memoria** | fatti, agenda, procedure, rubrica, vault, runbook | **tutte** le conversazioni, tutti i dispositivi | Postgres + Qdrant + Valkey, condivisi con Hermes |

Il pezzo **ancora da fare** è la seconda metà della sua frase: *«deve
aggiornarla da solo con nuovi dati»*. Oggi la memoria si aggiorna quando
glielo si dice; l'aggiornamento automatico è una scelta con un costo — vedi
[PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) §4 Fase 2, dove
`sync_turn()` è **volutamente vuoto**: salvare ogni turno di nascosto rende la
memoria non verificabile e rompe la promessa che `dimentica` dimentichi
davvero. Va progettato, non acceso di slancio.

## 3-quater. Quando manda l'audio, e quando no

Tre modalità, **per chat**, in `gateway_voice_mode.json`:

| Modalità | Comportamento | Comando |
|---|---|---|
| `all` | audio **sempre**, anche sui messaggi scritti | `/voice tts` |
| `voice_only` | audio **solo** se l'ingresso era un vocale | `/voice on` |
| `off` | mai | `/voice off` |

`voice.auto_tts: true` in `config.yaml` equivale ad `all`, ed era la
configurazione sbagliata messa qui il 2026-08-01: mandava un vocale anche
quando il proprietario scriveva. Corretta in `auto_tts: false` più
`{"telegram:<chat_id>": "voice_only"}` nel file delle modalità, che è quello
che era stato chiesto: *«non solo se mando l'audio o gli chiedo di mandare
audio»*.

## 3-quinquies. MASTER dentro Momo: c'era già, e nessuno lo sapeva

Verificato il 2026-08-01, mentre si stava per costruirlo. **Momo aveva già
MASTER completo**, e la ragione è la stessa scelta di disegno che regge tutto
il resto: `sovereign_tools` registra in Momo **ogni** strumento di
`hermes.TOOLS`, saltando solo quelli della memoria. `master_azioni_elenco` e
`esegui_azione_master` non erano nell'elenco dei salti, quindi erano già lì
dalla Fase 3.

Non solo gli strumenti: **è condiviso tutto lo strato di sicurezza**, perché è
lo stesso codice e lo stesso file di stato.

| Pezzo | Dove sta | Chi lo usa |
|---|---|---|
| Catalogo delle azioni | `actions.json` (8 azioni) | Hermes **e** Momo |
| Divieto assoluto | `master_forbidden()`, compilato nel codice | Hermes **e** Momo |
| Armamento a 30 minuti | `master-state.json` | Hermes **e** Momo |
| Interruttore RUNNING/PAUSED | stesso file | Hermes **e** Momo |
| Registro di audit | Postgres, `memory_master_log` | Hermes **e** Momo |
| Chiave SSH per l'host | `/root/sovereign-secrets/hermes/master-ssh-key` | Hermes **e** Momo |

**Conseguenza pratica che vale la pena sapere**: armare MASTER dal pannello di
Hermes **arma anche Momo**, perché il file di stato è uno solo. Non è un
effetto collaterale, è il disegno: una sola verità sullo stato.

### La verifica, fatta sul vivo

```
armato dal pannello di Hermes        -> {"ok": true, "azioni": 8}
Momo vede MASTER armato              -> True
Momo esegue "spazio_disco" su LXC 102 -> Riuscita, output vero via SSH sull'host
il registro ha inciso l'azione       -> 07:38 · spazio_disco · riuscita · mohamed
```

E la prova che conta di più, **il divieto assoluto interrogato da Momo mentre
era armato**:

| Comando | Esito |
|---|---|
| `qm stop 110` (fermare Immich) | **RIFIUTATO** — nessuna azione su VM 110, in nessuna forma |
| `qm destroy 110` | **RIFIUTATO** |
| `zfs destroy ssd_pool/...` | **RIFIUTATO** — nessuna distruzione di dati |
| `rm -rf /opt` | **RIFIUTATO** |
| fermare PBS | **RIFIUTATO** — nessuna azione sul backup |
| leggere/scrivere `actions.json` | **RIFIUTATO** — non si tocca il divieto stesso |
| `df -h` | permesso ✓ |

È esattamente il patto chiesto dal proprietario: *«un pulsante master per
autorizzarlo a fare tutto tutto tutto tranne toccare Immich e quella piccola
lista»*. La lista è compilata **a codice**, non in un file: un file si
modifica, un divieto no.

### Cosa manca ancora

- **Armare da Telegram** (T9): oggi si arma dal pannello di Hermes o via API.
  Da Telegram non ancora, ed è una decisione di sicurezza da prendere con
  calma — chi arma MASTER autorizza azioni sull'impianto, e un canale va
  valutato per quanto è difficile impersonarlo, non per quanto è comodo.
- **Il catalogo è di 8 azioni**, tutte a basso rischio (riavvii, letture). Il
  «tutto tutto tutto» chiesto significa allargarlo: ogni azione nuova si
  aggiunge come **dato** in `actions.json`, con i suoi parametri vincolati da
  enum o regex, mai come shell libera. È il disegno A5 di Nexi, e regge
  proprio perché il modello sceglie da un elenco invece di comporre comandi.

## 3-sexies. La finestra di contesto di Ollama, e il prefisso fisso del prompt

Trovato il 2026-08-01. Tre sintomi che sembravano tre guasti diversi — Momo
non ricordava la domanda precedente, non chiamava **mai** uno strumento, e si
presentava come «Hermes AI» invece che come Momo — erano **un guasto solo**, e
non stava nel modello.

### 3-sexies.1 La causa: un prompt più grande della finestra

Ollama sul PC (`192.168.1.100`) serviva `qwen3.5:9b` con **4.096 token** di
finestra. Il solo prompt di sistema di Momo ne occupava **6.694**: il prefisso
non ci stava nemmeno da solo, prima ancora che l'utente scrivesse una parola.

Quando il prompt eccede `num_ctx`, Ollama **non dà errore e non tronca dal
fondo**: tiene il messaggio di sistema e scarta il resto. Il resto, qui, erano
le due cose che rendono Momo un assistente invece di una chat.

| Sintomo | Perché |
|---|---|
| non ricorda la domanda precedente | la **cronologia** veniva scartata |
| non chiama mai uno strumento | gli **schemi degli strumenti** venivano scartati: non sapeva che esistessero |
| si presenta come «Hermes AI» | anche il prompt di sistema arrivava tagliato, e sotto restava l'identità di serie del pacchetto |

Nessuno dei tre dà un errore, ed è il motivo per cui è costato una giornata:
è la stessa classe di guasto del §2.2 della
[visione](../00_overview/VISIONE_COMPLETA.md) — il sistema non mente, **tace**,
e il silenzio si legge come incapacità del modello. Si è cercato a lungo dalla
parte sbagliata (il prompt, la persona, il plugin degli strumenti) perché tutte
e tre le ipotesi sbagliate spiegavano *un* sintomo, e nessuno guardava i tre
insieme.

Attenzione all'ordine causale, perché è controintuitivo: **non è il modello che
ignora gli strumenti, è il server che non glieli manda.** Un modello che non
riceve gli schemi si comporta esattamente come un modello troppo piccolo per
usarli, e le due cose si distinguono solo guardando il server.

### 3-sexies.2 Perché la protezione che c'era non è scattata

hermes-agent il problema lo aveva previsto. Non ha funzionato per **due**
ragioni indipendenti, e vanno sapute entrambe perché la seconda vale per
qualunque Ollama servito dietro un endpoint in forma OpenAI.

**1. `options` viene ignorato in silenzio sull'endpoint `/v1`.** La catena è
corretta fino all'ultimo passo:

```
agent/model_metadata.py:1595          query_ollama_num_ctx() interroga /api/show
                                      e legge 262.144 (il massimo del GGUF)
        ↓
agent/agent_init.py:2583-2585         il valore finisce in agent._ollama_num_ctx
        ↓
plugins/model-providers/custom/__init__.py:34-38
                                      lo mette in extra_body.options.num_ctx
        ↓
POST http://192.168.1.100:11434/v1/chat/completions
                                      ← QUI il campo cade nel vuoto
```

Verificato provando le due strade sulla stessa macchina: con `options.num_ctx`
nel corpo di una richiesta a **`/v1`** il contesto caricato resta **4.096**;
la stessa richiesta all'endpoint nativo **`/api/chat`** lo onora. Il campo
`options` è di Ollama, il percorso `/v1` è il guscio di compatibilità OpenAI,
e quel guscio scarta ciò che non riconosce senza dirlo. **Non è un difetto di
hermes-agent**: è un'incompatibilità fra due API dello stesso server, e chiunque
passi `num_ctx` in un corpo OpenAI la incontrerà.

**2. L'allarme legge il valore dichiarato, non quello caricato.**
`_ollama_context_limit_error()`
(`agent/conversation_loop.py:226-247`, chiamato a `:1770`) confronta
`agent._ollama_num_ctx` con `MINIMUM_CONTEXT_LENGTH = 64_000`
(`agent/model_metadata.py:279`) e, se il contesto è troppo piccolo, avvisa
l'utente. Ma `agent._ollama_num_ctx` è il numero **dichiarato** da `/api/show`,
cioè il massimo che il GGUF sopporta — 262.144 — non quello con cui il modello
è **davvero caricato** — 4.096. `262144 >= 64000`, quindi la guardia restituisce
`None` e non scatta mai. È il caso peggiore: una protezione che esiste, sembra
attiva, e misura la cosa sbagliata.

La differenza fra i due numeri si vede solo su `/api/ps`, che è l'unico
endpoint che dice cosa è stato **caricato**. `/api/show` dice cosa il modello
*potrebbe* reggere.

### 3-sexies.3 La cura, e la trappola dentro la trappola

Il contesto si impone **sul server Ollama**, non nella richiesta. Sul PC
Windows:

```powershell
OLLAMA_CONTEXT_LENGTH = 32768   # la finestra vera per ogni modello caricato
OLLAMA_NUM_PARALLEL   = 1       # una richiesta per volta: la KV cache non si divide
# poi Ollama va RIAVVIATO, e va riavviato da una shell nuova
```

**La trappola dentro la trappola, che è costata il primo tentativo**: impostare
la variabile con `[Environment]::SetEnvironmentVariable(...,'User')` **non
basta** se poi si lancia Ollama da una shell che aveva già catturato l'ambiente
vecchio. Un processo eredita l'ambiente alla nascita e non lo rilegge mai più.
La prima prova è fallita esattamente così, e il sintomo era il peggiore
possibile: nessun errore, nessun cambiamento, e la sensazione che la diagnosi
fosse sbagliata. **La variabile si verifica nel processo che la deve usare, non
nel registro dove è stata scritta.**

**Verificato il 2026-08-02** da LXC 102 — il PC risponde sulla LAN, quindi
questo controllo si può rifare senza toccare il PC:

```bash
pct exec 102 -- curl -s http://192.168.1.100:11434/api/ps
```

| Modello | `context_length` caricato | `size_vram` |
|---|---|---|
| `qwen3.5:9b` | **32.768** | 6.735.779.593 B (**6,27 GiB**) |
| `embeddinggemma:latest` | 2.048 | 681.417.113 B (0,63 GiB) |

Due cose da leggere in questa tabella. La prima: la cura **tiene ancora**, a un
giorno di distanza e attraverso un riavvio del gateway. La seconda:
`embeddinggemma` è rimasto a **2.048**, e va bene così —
`OLLAMA_CONTEXT_LENGTH` alza il *default*, non forza ogni modello oltre il
massimo del suo GGUF. Un modello di embedding non ha bisogno di 32k e
occuperebbe VRAM per niente.

> **Numero che non torna, dichiarato invece che nascosto**: il 2026-08-01, subito
> dopo il riavvio, la VRAM del modello era stata annotata come cresciuta da
> **5,25 a 6,16 GB**. Oggi la misura è **6.735.779.593 B**, cioè 6,27 GiB (6,74 GB
> decimali): il verso è quello giusto — più contesto, più KV cache, più VRAM — ma
> il valore assoluto **non si riproduce**, e il «prima» non è più misurabile
> perché il modello a 4.096 non esiste più. Si scrive il numero di oggi, misurato;
> il 6,16 GB resta come annotazione del momento, non come fatto verificato.

`OLLAMA_NUM_PARALLEL=1` **non è verificabile da qui**: `/api/ps` non lo espone
e il PC non è interrogabile in altro modo dal server. Resta dichiarato, non
confermato.

### 3-sexies.4 Il prefisso fisso, misurato e dimezzato

Alzare la finestra risolve il sintomo; **ridurre quello che ci si mette dentro**
è la parte che vale nel tempo, perché ogni byte del prefisso è pagato a **ogni
singolo turno**, per sempre, prima che l'utente abbia scritto qualcosa.

Lo strumento è loro e gira **offline, senza inferenza** — si può eseguire su un
impianto vivo senza disturbarlo:

```bash
pct exec 102 -- bash -lc 'HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes \
  /opt/momo/venv/bin/hermes prompt-size'
```

| Blocco | Prima (1 ago) | Dopo (rimisurato il 2 ago) |
|---|---|---|
| prompt di sistema | 26.552 B | **17.047 B** |
| — di cui **solo indice delle skill** | 6.732 B | **0 B** |
| schemi degli strumenti | 31.520 B (13 strumenti) | **13.483 B (8 strumenti)** |
| **prefisso fisso totale** | **~58 KB** | **~30,5 KB** |

Il pezzo più assurdo era l'indice delle skill: **6.732 byte spesi a ogni turno**
per elencare le skill di serie di hermes-agent — `p5js`, `powerpoint`,
`comfyui`, `humanizer`, `claude-code` e decine di altre — che in questa casa
**non si useranno mai**. Non erano caricate: era il solo *elenco*, che il modello
doveva leggere ogni volta per poi ignorarlo.

Le due mosse, entrambe in `/opt/momo/home/.hermes/config.yaml`:

```yaml
toolsets:            # la CLI risolveva 55 strumenti: troppi per un 9B,
- file               # che a quel punto smette di chiamarli del tutto
- web
- memory
- clarify
- todo
- vision

platform_toolsets:
  telegram: [file, web, memory, clarify, todo, vision, tts, stt]

skills:
  enabled: false     # l'indice sparisce, non si accorcia
```

**Perché ridurre gli strumenti e non solo allargare il contesto**: un modello da
9B con 55 schemi davanti sceglie peggio che con 8. Il contesto è una condizione
necessaria, il campo ristretto è quella che fa scegliere bene. Sono due
correzioni allo stesso sintomo, e servono tutte e due.

**Tre onestà su questi numeri:**

- La misura del «dopo» è **17.047 B**, non 17.049 come annotato il giorno prima.
  La differenza sono 2 byte del blocco volatile (77 B: memoria, profilo,
  marcatempo), che cambia a ogni esecuzione. Il numero non è stabile all'unità e
  non deve esserlo.
- Il **`web` è in `toolsets` ma contribuisce zero strumenti**: `check_web_api_key`
  ritorna `False` (nessuna chiave), e i log lo dicono a ogni turno — *«dependent
  tools will be unavailable this turn»*. Gli 8 strumenti misurati sono
  `file` (4), `memory` (1), `clarify` (1), `todo` (1), `vision` (1). È il motivo
  per cui la riga «web» non compare nella ripartizione di `prompt-size`.
- I **valori del «prima» non sono più riproducibili**: la configurazione è
  cambiata, e per rimisurarli bisognerebbe riaccendere `skills.enabled` e i
  toolset larghi sull'impianto vivo. Non è stato fatto. Restano come annotati il
  2026-08-01. Nota di contorno: le skill di serie oggi presenti in
  `/opt/momo/home/.hermes/skills` sono **70** (`SKILL.md` contati), non 64 come
  annotato — l'indice ne contava 64, e la differenza non è stata indagata.

### 3-sexies.5 L'errore fatto qui, scritto perché non si ripeta

Modificando `config.yaml` per ridurre i toolset ho usato **espressioni regolari
su testo YAML**, e ho **troncato il file**. Momo è rimasto senza modello
configurato: *«No inference provider configured»*. Il rottame è ancora sul
server come `/opt/momo/home/.hermes/config.yaml.rotto` — **330 byte** contro i
1.984 del backup, cioè l'83% del file sparito.

Ripristinato da `config.yaml.bak-toolsets` e rifatto caricando e riscrivendo la
**struttura** (`yaml.safe_load` → modifica dell'oggetto → `yaml.safe_dump`).

La lezione, che vale ovunque e non solo qui: **un file YAML si modifica come
struttura, non come testo.** Una regex non conosce l'indentazione, che in YAML
*è* la sintassi; e — la parte velenosa — **un YAML tagliato a metà resta
sintatticamente valido**. Nessun parser protesta, nessun errore compare al
salvataggio: il guasto si manifesta molto dopo, come una funzione mancante,
lontano dalla causa. Un JSON troncato almeno dà errore subito.

### 3-sexies.6 Cosa resta APERTO

**Momo via hermes-agent ancora non chiama gli strumenti.** Il contesto era una
causa reale, ed è stata rimossa; non era l'unica.

La prova che separa le due cose: chiamando **direttamente l'API** del PC con
`system = SOUL.md` e 35 strumenti dichiarati, il modello risponde con
`tool_calls` su `write_file`. Quindi:

- il modello **è capace** di chiamare strumenti;
- il contesto **basta** per contenere prompt e schemi;
- ma **attraverso hermes-agent** non succede.

Resta perciò qualcosa nella loro catena — fra la costruzione della richiesta e
il parsing della risposta — che non è la finestra di contesto. **Non ancora
diagnosticato**, e non va scritto come risolto: le tre cure di questa sezione
sono vere e misurate, il risultato finale no.

Il sospetto da verificare per primo, non ancora provato: che il gateway usi un
percorso di richiesta diverso da quello provato a mano (`api_mode:
chat_completions` è quello registrato in `state.db`), e che gli strumenti vadano
persi lì. Da confrontare catturando la richiesta vera — i `request_dump_*.json`
in `/opt/momo/home/.hermes/sessions/` sono già quello, e sono il posto da cui
ripartire.

## 3-septies. Il ragionamento acceso, e la catena che cadeva in silenzio

Trovato il 2026-08-02. È la **prima trappola** dell'elenco in
[VISIONE_COMPLETA](../00_overview/VISIONE_COMPLETA.md) §6, tornata da una
porta diversa: su Momo nessuno l'aveva configurata.

**Il sintomo**: `hermes -z "ciao"` usciva con **codice 2 e nessun output**.
Niente in `errors.log`. Sembrava un guasto di rete.

**La misura che ha chiuso il caso**: interrogando l'Ollama del server
direttamente, `qwen3.5:4b` risponde in **17,7 secondi con contenuto vuoto**.
Non è lento: ragiona e non conclude. Quello è il **ripiego** della catena,
quindi quando il primario falliva si finiva lì, e lì non c'era risposta.

**Perché il rimedio non era attivo.** Il commento nel loro
`plugins/model-providers/custom/__init__.py` dice, parola per parola, la
stessa cosa che sta nella nostra tabella delle trappole:

> Ollama's `/v1/chat/completions` silently ignores `extra_body.think` (only
> `/api/chat` honours it — ollama#14820) but respects the top-level
> `reasoning_effort` field.

Il provider **sa già** emettere `reasoning_effort: "none"`, ma solo se
qualcuno imposta `agent.reasoning_effort` — e non era impostata. Il rimedio
c'era, spento.

```yaml
# /opt/momo/home/.hermes/config.yaml
agent:
  reasoning_effort: none
```

**Il risultato, misurato e non promesso**: la chiamata agli strumenti passa da
**1 a 2 volte su 6**. Un miglioramento dentro il rumore, **non una cura**: il
collo di bottiglia resta il modello. Scritto così perché nessuno lo riprovi
credendo che basti.

### Lo stato di Bedrock: ristretto, ma aperto

Chiave fornita dal proprietario il 2026-08-02
(`/root/sovereign-secrets/hermes/key-bedrock`, 0600, mai nel repository).

| Prova | Esito |
|---|---|
| Chiave valida, `gpt-oss-20b`, persona di Momo, 19 strumenti | **6 chiamate su 6** |
| Lo stesso attraverso hermes-agent | uscita 2, nessun output |
| La richiesta **esatta** di hermes-agent, rigiocata a mano contro Bedrock | **accettata** |
| `extra_body.options.num_ctx` e `max_tokens: 65536` verso Bedrock | accettati |

Quindi **non è il payload e non è la chiave**. Resta da capire come
hermes-agent tratta la risposta. Aperto, e scritto come aperto.

Per il confronto: `qwen3.5:9b` sul PC fa **1-2 su 6** dove Bedrock fa **6 su
6**. È la differenza fra un assistente che agisce e uno che descrive, ed è la
ragione per cui vale la pena chiudere quel caso.

## 3-octies. Cambiare motore: `momo-motore`

```bash
momo-motore                 # quale motore risponde adesso, e cosa costa
momo-motore pc              # PC di Mohamed, RTX 5070 Ti (a PC acceso)
momo-motore server          # CPU di LXC 102: sempre lì, lenta
momo-motore bedrock         # AWS: bravo con gli strumenti, NON in casa
momo-motore --elenco        # tutti, con la nota di ognuno
```

Esiste perché `hermes model` **disegna un menu e pretende un terminale vero**:
non è usabile da script, da cron, né da `pct exec`. Questo tocca le stesse
chiavi che tocca il loro menu (`model.default`, `model.provider`,
`CUSTOM_BASE_URL`, `CUSTOM_API_KEY`) e riavvia il servizio.

Due cose che fa di proposito:

- **non scrive mai una chiave passata a mano**: le chiavi stanno in
  `/root/sovereign-secrets/` a 0600 e si citano per percorso. Uno script che
  prende un segreto sulla riga di comando lo lascia nella cronologia della
  shell di chi lo lancia;
- **riscrive `config.yaml` come struttura, mai come testo**: modificarlo con
  espressioni regolari lo ha troncato una volta, il 2026-08-02, lasciando
  Momo senza modello.

Ogni motore dichiara **accanto al proprio indirizzo** se è di casa, invece di
lasciarlo dedurre da un URL scritto altrove, e passando a uno esterno lo dice
in faccia.

## 4. DNS / domain names / alias

**Nessuno, e volutamente.** Telegram si raggiunge in uscita; non c'è niente da
pubblicare. È il motivo per cui questo canale è più sicuro della PWA: non
aggiunge nessuna superficie esposta.

## 5. Nginx Proxy Manager (NPM)

**Nessun host proxy.** Il long polling non richiede un endpoint pubblico. Se un
giorno si passasse ai webhook servirebbe un host in NPM e una porta esposta:
**non farlo** senza una ragione forte — il polling costa qualche secondo di
latenza e toglie un intero problema di sicurezza.

## 6. Homepage & Uptime Kuma

- **Homepage**: nessuna tessera — non è una pagina web da aprire. Il "link" è
  la chat di Telegram sul telefono.
- **Uptime Kuma**: un monitor **push** o di processo, non HTTP: non c'è un
  endpoint da interrogare. Il segnale utile è che `momo-gateway.service` sia
  `active`. Da creare a mano (Kuma non ha API REST — vincolo noto).

## 7. Backup & restore

- **Il token**: sta in `/root/sovereign-secrets/hermes-agent/`, coperto dal
  backup dei segreti, mai nel repository. Se si perde, se ne genera un altro da
  @BotFather e il vecchio smette di funzionare — nessun dato perso.
- **Le conversazioni**: le sessioni di hermes-agent stanno in
  `/opt/momo/home/.hermes/`. La **memoria** vera (fatti, agenda, rubrica) è in
  Postgres/Qdrant e ha il suo backup: è quella che conta, ed è condivisa con
  Hermes.
- **L'allowlist**: una riga in un file d'ambiente. Va riscritta a mano dopo un
  ripristino, e questo è un bene: nessun automatismo deve poter allargare chi
  parla con Momo.

## 8. Rollback

```bash
# spegnere il canale lasciando Momo vivo da CLI
systemctl disable --now momo-gateway

# oppure togliere il plugin da config.yaml (plugins.enabled) e riavviare
```

Il bot smette di rispondere immediatamente. Nessuno stato da ripulire: Telegram
accoda i messaggi non consegnati per 24 ore e poi li scarta.

## 9. Edge Cases — cosa succede se un passo va a metà

> Scritti **prima** di accendere (A8).

| Caso | Cosa succede | Perché così |
|---|---|---|
| **Uno sconosciuto scrive al bot** | ignorato dall'allowlist, nessuna risposta | non un «non sei autorizzato»: rispondere conferma che il bot esiste ed è vivo |
| **L'allowlist è vuota o la variabile manca** | il plugin non deve rispondere a nessuno. Da **verificare provandolo**, non da dare per buono | se il default fosse "aperto a tutti" sarebbe la stessa classe di difetto di Open WebUI con l'iscrizione libera (S8) |
| **`TELEGRAM_ALLOW_ALL_USERS=true` per errore** | chiunque su Telegram parla con Momo, che ha il vault e la rubrica | è la riga più pericolosa di tutto il file. Resta `false` |
| **Il servizio muore mentre un messaggio è in volo** | Telegram lo riconsegna al riavvio (il polling non conferma finché non elabora) | nessun messaggio perso |
| **Due istanze di Momo in polling insieme** | Telegram dà `409 Conflict` e una delle due si rompe | mai avviare `momo-gateway` mentre gira un `hermes` interattivo collegato a Telegram. Il servizio è uno solo |
| **Il PC di Mohamed è spento** | il modello di casa sulla CPU risponde, più lento | il ripiego esiste già in `backends.json`. È il motivo per cui la GPU del server (punto 20) conta |
| **Impianto in PAUSA** | Momo risponde in chat ma rifiuta mail, vault, azioni | l'interruttore è un hook globale, non dipende dal canale ([sovereign-interruttore.md](sovereign-interruttore.md)) |
| **Un vocale più lungo del limite** | l'adattatore ha già un controllo di dimensione (`_telegram_media_size_allowed`) e lo salta dicendolo | codice loro, non nostro |
| **Momo scrive qualcosa di lungo** | l'adattatore spezza e fa streaming a modifiche successive | gestito da loro (hanno un piano dedicato al problema dell'overflow) |
| **Il token finisce in un log** | non deve mai: sta in un `EnvironmentFile` a 0600 e `systemd` non lo stampa | stessa regola di tutti i segreti di questa casa |
| **Telegram è irraggiungibile** | il polling riprova da solo; Momo resta usabile da CLI | un canale giù non è un assistente giù |

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Il bot non risponde a niente | il servizio non gira, o il plugin non è in `plugins.enabled` | `systemctl status momo-gateway`; `journalctl -u momo-gateway -n 50` |
| Il bot ignora **me** | il mio id non è in `TELEGRAM_ALLOWED_USERS` | ricatturarlo con `getUpdates` (§1.1) — non fidarsi di quello che si ricorda |
| `409 Conflict` nei log | due processi in polling sullo stesso token | fermarne uno; vedi §9 |
| Risponde ma non sa niente di casa | il motore che risponde non è privato, quindi gli strumenti sono nascosti | `grep provider /opt/momo/home/.hermes/config.yaml`; deve essere `custom`/`ollama`/`local` |
| Risponde lentissimo | PC spento, si sta usando la CPU del server | atteso; vedi punto 20 del piano generale |
| I vocali non vengono trascritti | `ffmpeg` assente o STT non configurato | `pct exec 102 -- which ffmpeg` |
| **Non ricorda la domanda prima, non chiama mai uno strumento, e si presenta col nome sbagliato** | i tre insieme sono **un sintomo solo**: la finestra di Ollama è più piccola del prefisso del prompt | `curl -s http://192.168.1.100:11434/api/ps` e guardare `context_length` — è il **caricato**, non il dichiarato. Sotto ~16k con gli strumenti attivi è troppo poco. Si corregge con `OLLAMA_CONTEXT_LENGTH` **sul server Ollama**, non nella richiesta (§3-sexies) |
| Ho impostato `OLLAMA_CONTEXT_LENGTH` e non cambia niente | Ollama è stato lanciato da una shell che aveva già l'ambiente vecchio, oppure si sta passando `num_ctx` nel corpo verso `/v1` | riavviare Ollama **da una shell nuova**; verificare su `/api/ps`, non nel registro di Windows. `options.num_ctx` su `/v1` viene ignorato in silenzio (§3-sexies.2) |
| «No inference provider configured» | `config.yaml` corrotto o troncato | ripristinare dal `config.yaml.bak-*` più recente e rifare l'edit con `yaml.safe_load`/`safe_dump`, mai con regex (§3-sexies.5) |
| `Message thread not found` nei log | un `thread_id` di un topic cancellato è rimasto inciso in `home_channel` o in `channel_directory.json` | togliere `thread_id` da `config.yaml`; se compare solo allo spegnimento è il residuo noto in `channel_directory.json`, rumore e non guasto (§3-ter) |
| Il prefisso del prompt è cresciuto senza motivo | skill o toolset riattivati | `hermes prompt-size` — gira **offline**, si può eseguire sull'impianto vivo |
| **`/motore` non si trova nel menu dei comandi** | c'è, ma è sepolto: il menu ha un tetto e hermes-agent porta ~50 comandi di serie | §10.1 — si mette in cima con `platforms.telegram.extra.command_menu.priority` |
| Il menu dei comandi è **completamente vuoto** dopo aver alzato il tetto | oltre ~4096 byte Telegram rifiuta l'elenco **intero**, non lo tronca | riabbassare `max_commands`; §10.1 per il conto |

### 10.0 Cambiare l'AI: per sempre, o solo per questa chiacchierata

Due comandi, due mestieri diversi. La confusione fra i due non è del
proprietario: sembrano la stessa cosa e non lo sono.

| Voglio… | Comando | Cosa tocca |
|---|---|---|
| cambiare l'AI **per tutti, da adesso** | `/motore 3` oppure `/motore pc-qwen` | scrive `config.yaml`: vale per ogni sessione, anche future |
| cambiarla **solo qui, adesso** | `/model --provider pc-qwen` | solo questa sessione; il default resta |
| **un turno solo** | `/model --provider server --once` | il turno dopo, poi torna al default |
| vedere le scelte, con i numeri | `/motore` (breve) o `/motore list` (con le note e i tempi) | niente |
| farla restare anche dopo | aggiungere `--global` | scrive `config.yaml` |

**Perché `/model` da solo non basta, e perché ora funziona.** `/model
qwen3.5:9b` cambia il **nome** del modello e lascia l'**indirizzo** dov'era:
Momo continua a parlare col PC chiedendogli un modello che il PC non ha, e
ogni turno dopo fallisce. In questa casa il modello e la macchina che lo
serve sono **una cosa sola**.

Il pezzo che mancava era `--provider`. Dal 2026-08-03 `momo-motore` dichiara
ogni motore come provider con un nome nella sezione `providers:` del
`config.yaml`, generandoli **da `ENGINES`** a ogni cambio — una sola fonte di
verità, così l'elenco che `/motore` stampa e i nomi che `/model --provider`
accetta non possono divergere. Con quelli dichiarati, `--provider pc-qwen`
cambia nome **e** indirizzo insieme.

Per rigenerarli senza cambiare motore: `momo-motore provider`.

**Solo le chiavi che il loro schema conosce** (`base_url`, `default_model`).
Il primo tentativo aggiungeva anche `enabled`, `label` e `api_key_file`:
vengono ignorate, ma stampano *«unknown config keys ignored»* per ogni
provider a ogni caricamento — otto righe di rumore in un log dove poi si
cercano i guasti veri. L'etichetta leggibile vive in `/motore elenco`, che è
il posto dove la si legge davvero.

### 10.1 Il menu dei comandi di Telegram: due tetti, e uno non è documentato

Segnalato da Mohamed il 2026-08-03: *«da Telegram voglio poter lanciare un
comando per cambiare l'AI, e non ci riesco»*.

`/motore` **era già pubblicato** — verificato con `getMyCommands`, non
supposto. Era solo in fondo a un elenco di 60: hermes-agent ne porta una
cinquantina di serie e i comandi dei plugin finiscono in coda.

I due tetti:

- **100 comandi**, che è il limite delle API di Telegram;
- **~4096 byte di payload**, che *non è documentato* e che si incontra molto
  prima. Superandolo Telegram rifiuta l'elenco **intero**: il menu non si
  tronca, si **svuota**.

Misurato su questo impianto: 100 comandi = **6285 byte** → menu vuoto.
52 comandi = **3376 byte** → funziona. Il conto si rifà così, senza indovinare:

```bash
cd /opt/hermes-agent-study && HERMES_HOME=/opt/momo/home/.hermes \
  /opt/momo/venv/bin/python -c "
from hermes_cli.commands import telegram_menu_commands, telegram_menu_max_commands
c,_ = telegram_menu_commands(max_commands=telegram_menu_max_commands())
print(len(c), sum(len(a)+len(b)+8 for a,b in c), 'byte')"
```

La configurazione, in `config.yaml`:

```yaml
platforms:
  telegram:
    extra:
      command_menu:
        max_commands: 52          # 3376 byte, sotto il tetto non documentato
        priority_mode: prepend
        priority: [motore, slmix, new, model, status, help, stop, sessions]
```

**Il token non sta in `config.yaml`, sta in `.env`.** Detto qui perché mi è
costato: cercandolo con `grep` nel solo `config.yaml` si ottiene una stringa
vuota, `https://api.telegram.org/bot/getMyCommands` risponde **404**, e un 404
letto di fretta sembra «il menu è vuoto». Ho quasi riparato un guasto che non
esisteva. Quando la misura dà un risultato assurdo, il primo sospettato è lo
strumento di misura.

## 11. Verifica di funzionamento

```bash
# il bot esiste ed è il nostro
T=$(cat /root/sovereign-secrets/hermes-agent/telegram-bot-token)
curl -s "https://api.telegram.org/bot$T/getMe"
# atteso: "username":"dn_momo_bot"

# il servizio è vivo
pct exec 102 -- systemctl is-active momo-gateway

# LA PROVA CHE CONTA, e va fatta dal telefono vero:
#  1. scrivo "ciao" a @dn_momo_bot           -> risponde
#  2. gli chiedo un fatto che sa solo la memoria di casa
#     ("cosa ti ho detto su ...")            -> lo sa (memoria condivisa con Hermes)
#  3. metto l'impianto in PAUSA e gli chiedo di mandare una mail
#                                            -> rifiuta, ma continua a parlare
```

## 12. Official Sources

- Codice letto: `/opt/hermes-agent-study/plugins/platforms/telegram/` — `adapter.py` (`send_voice` a riga 6734, download dei vocali a 9013), `plugin.yaml` (le variabili d'ambiente)
- `pyproject.toml` di hermes-agent — il pin `python-telegram-bot[webhooks]==22.6`
- [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) §4 Fase 5
- [PIANO_MOMO_DIGITAL_TWIN](../00_overview/PIANO_MOMO_DIGITAL_TWIN.md) §4 — il punteggio delle undici voci
- [sovereign-interruttore.md](sovereign-interruttore.md) · [momo-guardrail.md](momo-guardrail.md) — le guardie che valgono anche qui
- Telegram Bot API, long polling e `getUpdates` — <https://core.telegram.org/bots/api>
- Codice letto per §3-sexies, tutto in `/opt/hermes-agent-study/`:
  `agent/model_metadata.py:1595` (`query_ollama_num_ctx`, legge `/api/show`) e
  `:279` (`MINIMUM_CONTEXT_LENGTH = 64_000`);
  `agent/agent_init.py:2583-2585` (dove il valore diventa `agent._ollama_num_ctx`);
  `plugins/model-providers/custom/__init__.py:34-38` (`extra_body.options.num_ctx`);
  `agent/conversation_loop.py:226-247` (l'allarme che non scatta, chiamato a `:1770`)
- Stato vivo consultato in sola lettura il 2026-08-02: `/opt/momo/home/.hermes/`
  — `config.yaml` e i suoi `*.bak-*`, `channel_directory.json`,
  `sessions/sessions.json`, e le tabelle `sessions`, `gateway_routing`,
  `delivery_obligations` di `state.db`
- `OLLAMA_CONTEXT_LENGTH` / `OLLAMA_NUM_PARALLEL` — variabili del server Ollama,
  non parametri di richiesta: <https://github.com/ollama/ollama/blob/main/docs/faq.md>
