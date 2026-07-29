# Hermes — l'assistente della casa

> **Stato (2026-07-29): LIVE.** Raggiungibile su `https://hermes.internal`
> dietro il single sign-on. Servizio `sovereign-hermes` su LXC 102, porta 8093.
> L'inferenza gira sulla RTX 5070 Ti del PC di Mohamed; il server fa da regia.

---

## 1. Che cos'è e perché è fatto così

Hermes è un assistente conversazionale che **conosce questa infrastruttura**.
Non è una chat generica: quando gli chiedi come sta il server va a leggere lo
stato reale, e quando gli chiedi di una cosa che hai scritto va a cercarla nel
vault Obsidian. Ogni informazione arriva da una chiamata a uno strumento, mai
dalla memoria del modello — così le risposte sono verificabili invece che
inventate.

Il principio architetturale è: **il cervello sta sul server, la forza bruta sta
dove c'è la GPU.**

```
Browser ── https://hermes.internal ──> NPM (LXC 100)
              │  forward-auth Authentik: senza login non si passa
              ▼
        Hermes (LXC 102 :8093)          "la regia"
              │
              ├── strumenti ─── dashboard  (stato infrastruttura, ruoli)
              │             └── CouchDB    (vault Obsidian, sola lettura)
              │
              └── inferenza, in ordine di preferenza:
                    1. PC di Mohamed  192.168.1.100:11434   RTX 5070 Ti
                    2. Server         127.0.0.1:11434       CPU, di scorta
                    3. API remota     (spenta di default)
```

Se il PC è spento Hermes non smette di funzionare: passa da solo al motore
successivo. Il passaggio è automatico e visibile nell'intestazione della pagina.

---

## 2. Il modello scelto e perché

La GPU è una **RTX 5070 Ti da 16 GB** (Blackwell, sm_120).

| Modello | Peso | Contesto | Note |
|---|---|---|---|
| **`qwen3.5:9b`** (in uso) | 6,6 GB | 256K | Sta comodo in 16 GB, ~50 token/s, capisce le immagini, chiama gli strumenti in modo affidabile |
| `gpt-oss:20b` | 14 GB | 128K | Più bravo a ragionare, ma riempie quasi tutta la VRAM: poco spazio per il contesto |
| `qwen3.5:27b` | 17 GB | 256K | **Non ci sta**: sfora i 16 GB e finisce in RAM di sistema, crollando di velocità |
| `qwen3.5:4b` (di scorta) | 3,4 GB | 256K | Gira sul server via CPU quando il PC è spento |

### La trappola del "thinking"

`qwen3.5` è un modello di ragionamento: mette il ragionamento in un campo
separato `thinking` e la risposta in `content`. Lasciato libero, alla domanda
banale *"rispondi solo: pronto"* ha prodotto **4080 token di ragionamento, una
risposta vuota** e ha esaurito il contesto (`done_reason: length`), impiegando
40 secondi.

Per questo `backends.json` imposta `"think": false`. Con quella riga la stessa
domanda si risolve in **0,8 secondi** con la risposta al posto giusto. È la
differenza fra un assistente che sembra rotto e uno che funziona.

---

## 3. Che cosa sa fare (gli strumenti)

| Strumento | Chi può usarlo | Cosa fa |
|---|---|---|
| `estate_status` | tutti | Stato reale dei servizi. **Filtrato per ruolo**: il proprietario vede VM, storage, dischi e backup; un utente di casa vede solo quali servizi sono su o giù |
| `vault_search` | solo proprietario | Cerca fra gli appunti Obsidian |
| `vault_read` | solo proprietario | Legge una nota intera |
| `vault_list` | solo proprietario | Elenca i titoli delle note |
| `access_overview` | solo proprietario | Chi ha accesso a quale servizio |

Il vault contiene gli appunti personali del proprietario: **nessun altro utente
può raggiungerlo tramite Hermes**, nemmeno chiedendolo con insistenza al
modello. Il controllo è doppio: gli strumenti riservati non vengono nemmeno
offerti al modello (`tools_for`), e se il modello li invocasse lo stesso
`run_tool` li rifiuta.

---

## 4. Identità e permessi

Hermes usa lo **stesso modello di fiducia della dashboard**:

- `127.0.0.1` → console di emergenza, sempre amministratore (funziona anche con
  Authentik giù).
- Richieste da **192.168.1.50** (NPM) → l'identità arriva
  nell'header `X-authentik-username`, che solo NPM può impostare perché ha già
  fatto il login forward-auth.
- Qualunque altra origine → nessuna identità, 401.

I ruoli **non** si leggono dagli header: Hermes li chiede alla dashboard
(`/api/iam-read`). Un utente sconosciuto viene trattato come utente semplice,
mai come amministratore.

### Perché Hermes non ha credenziali Authentik

Il primo disegno prevedeva un account di servizio `svc-hermes` con permessi di
sola lettura su utenti e gruppi. In authentik 2026.5.3 l'assegnazione dei
permessi al ruolo non è andata a buon fine (`assign_perms` non produce effetti),
e un token senza permessi sarebbe stato solo una credenziale in più da
proteggere. Poiché la dashboard **calcola già** ruoli e concessioni, Hermes le
legge da lì: un solo segreto invece di due, e una superficie in meno.
L'account `svc-hermes` creato durante il tentativo è stato rimosso.

---

## 5. Accesso al vault Obsidian: in sola lettura, per davvero

Hermes legge le note direttamente da CouchDB. LiveSync salva un documento per
nota con l'elenco dei pezzi (`children`), e il testo sta nei pezzi (`h:...`).

Il vault **non ha la cifratura end-to-end attiva** (`encrypt: false` nella
configurazione del plugin), quindi il server può leggere il testo in chiaro.
È questa la ragione per cui Hermes può cercare fra gli appunti.

> **Il compromesso da conoscere.** Se un giorno attivi la cifratura end-to-end
> su LiveSync, CouchDB conterrà solo testo cifrato e **Hermes diventerà cieco
> sul vault**. Le due cose si escludono: o il server può leggere gli appunti
> (e quindi Hermes li cerca), o non può (e allora nemmeno Hermes).

L'account CouchDB `hermes_reader` è membro del solo database `obsidiandb` e
**non può scrivere**: un `validate_doc_update` nel design document
`_design/hermes_readonly` rifiuta ogni scrittura di quell'utente.

Verificato al momento dell'installazione:

```
hermes PUO leggere:        True (HTTP 200)
hermes NON puo scrivere:   True (HTTP 403)
client LiveSync scrive:    True (HTTP 201)   <- la sincronizzazione non si tocca
```

L'ultima riga è la più importante: la guardia riguarda solo `hermes_reader`, i
client Obsidian continuano a sincronizzare normalmente.

---

## 6. La GPU del PC, esposta senza aprirla a tutti

Perché Hermes possa usarla, Ollama sul PC deve ascoltare sulla rete e non solo
su `localhost`:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST","0.0.0.0","User")
[Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE","30m","User")
```

> **Attenzione**: l'app desktop eredita le variabili all'avvio. Dopo averle
> impostate va riavviata, altrimenti continua ad ascoltare su 127.0.0.1.

### Il buco che l'installer lascia aperto

L'installer di Ollama crea **due regole firewall in ingresso per `ollama.exe`
con "qualsiasi indirizzo remoto", attive anche sul profilo Public** — e su
questo PC la scheda WiFi è classificata **Public**. Tradotto: su una rete
pubblica qualunque, chiunque avrebbe potuto usare la GPU, perché Ollama non ha
autenticazione.

Le regole permissive sono state **disattivate** e sostituite da una sola regola
esplicita:

```powershell
New-NetFirewallRule -DisplayName "Ollama - solo server Sovereign" `
  -Direction Inbound -Protocol TCP -LocalPort 11434 `
  -RemoteAddress 192.168.1.52,192.168.1.150 -Action Allow -Profile Any
```

Verifica eseguita dopo la modifica:

| Da | Esito atteso | Esito reale |
|---|---|---|
| LXC 102 (Hermes, .52) | passa | HTTP 200 |
| LXC 101 (.51) | bloccato | bloccato |
| LXC 100 (.50) | bloccato | bloccato |

---

## 7. Aggiungere un motore (GPU futura, o una API)

### Dal pannello, senza toccare file — `https://hermes.internal/impostazioni`

Visibile **solo all'amministratore** (un altro utente riceve 403 sia sulla
pagina sia sull'API, verificato). Da lì si può:

- aggiungere, togliere e **riordinare** i motori (l'ordine è la preferenza);
- cambiare modello scegliendolo da un menu con **i modelli davvero presenti**
  su quel backend, letti da `/api/tags`;
- attivare o disattivare un motore senza cancellarlo;
- accendere o spegnere il `think` per motore;
- incollare una **chiave API**.

La chiave non finisce mai nel JSON: viene scritta in
`/root/sovereign-secrets/hermes/key-<nome>`, creata direttamente con permessi
`0600` (aperta con `os.open(..., 0o600)`, non scritta e poi corretta: altrimenti
esisterebbe un istante in cui è leggibile da tutti). Il pannello mostra soltanto
*se* una chiave c'è, mai il suo valore. Il percorso è derivato dal nome del
motore, quindi chi invia la richiesta non può scegliere dove scrivere.

Il pannello mostra anche una tabella dei **modelli consigliati per la 5070 Ti**,
con il peso e se ci stanno nei 16 GB.

> **Nota sull'irrigidimento systemd**: l'unità usa `ProtectHome=read-only`, che
> rende `/root` di sola lettura — il primo tentativo di salvare una chiave è
> fallito con *Read-only file system*. Servono le righe `ReadWritePaths` per
> `/root/sovereign-secrets/hermes` e `/opt/sovereign-hermes`, e nient'altro.

### A mano

Si modifica `/opt/sovereign-hermes/backends.json`. L'ordine dell'elenco è
l'ordine di preferenza; il primo che risponde viene usato.

```json
{
  "name": "muletto-gpu",
  "label": "Secondo PC · RTX 4090",
  "type": "ollama",
  "url": "http://192.168.1.101:11434",
  "model": "qwen3.5:27b",
  "think": false,
  "enabled": true
}
```

Per una API remota (`"type": "openai"`, compatibile con OpenRouter, OpenAI,
vLLM, LM Studio) basta scrivere la chiave nel file indicato da `api_key_file` e
mettere `enabled: true`. Di default è **spenta**: nessun dato esce da casa se
non lo decidi tu.

Dopo la modifica: `systemctl restart sovereign-hermes` su LXC 102.

---

## 7-bis. Il pulsante nella dashboard

L'orb dell'assistente in `dash.internal` non mostra più l'onda sonora ma una
**testa di robot pixel in oro e argento, senza occhi**: solo una visiera scura
con una barra che scandaglia, animata al posto dell'equalizzatore (e ferma se il
sistema chiede meno animazioni).

Nella bolla restano le risposte pronte — istantanee e valide anche con Hermes
spento — e sotto compaiono due strade verso Hermes:

- **Chiedi a Hermes**, che apre la chat;
- un campo di testo: quello che scrivi arriva a Hermes già pronto, tramite
  `hermes.internal/?q=…`, e parte da solo.

Perché passare dall'URL invece di chiamare Hermes via XHR dalla dashboard: sono
due host diversi, quindi servirebbe CORS **e** un modo per far credere a Hermes
l'identità asserita dalla dashboard. Aprire la pagina non aggiunge nessuna
relazione di fiducia nuova: ci pensa il solito login unico.

## 7-ter. Lo sciame di agenti

Con la casella **«sciame di agenti»** Hermes smette di rispondere da solo:

1. **divide** la richiesta in sotto-compiti indipendenti (al massimo 3);
2. **assegna** ogni sotto-compito a un agente separato, che ha i suoi strumenti
   e vede solo il proprio pezzo;
3. **ricuce** i risultati in una risposta unica — e in quella fase gli strumenti
   sono disattivati, così la sintesi non può inventare fatti nuovi.

Prova reale: *«Dimmi come sta il server, e separatamente cosa ho scritto negli
appunti su Oracle»* → piano in due compiti, un agente sullo stato e uno sul
vault, sintesi con dati veri di entrambi.

### La squadra (ispirata a ChatDev / MetaGPT)

Gli agenti non sono anonimi: sono **ruoli**, definiti in
`/opt/sovereign-hermes/roles.json`. Il coordinatore legge l'elenco, spezza la
richiesta e assegna ogni pezzo al ruolo più adatto.

| Ruolo | Quando viene chiamato |
|---|---|
| Direttore (CEO) | decisioni, priorità, se una cosa vale la pena |
| Architetto (CTO) | come è fatto o come andrebbe fatto, compromessi, rischi |
| Sistemista (SRE) | stato dei servizi, guasti, backup, spazio disco |
| Sicurezza (CISO) | permessi, accessi, esposizioni, privacy |
| Ricercatore | informazioni attuali: prezzi, versioni, notizie |
| Archivista | cosa ha scritto il proprietario nel vault |
| Sviluppatore | codice, script, configurazioni, query |
| Debugger | un errore, un log, una causa da trovare |
| Revisore | rileggere e trovare i problemi |
| Qualità (QA) | come si dimostra che una cosa funziona |
| DBA | Oracle, RAC, Data Guard, GoldenGate, prestazioni |
| Documentalista | scrivere o sistemare documentazione |
| Generalista | ripiego, quando nulla calza |

Ogni ruolo ha **il suo prompt e i suoi strumenti**: il Ricercatore vede solo il
web, l'Archivista solo il vault, il Sistemista solo lo stato. Non è estetica —
un agente con meno strumenti sbaglia meno bersaglio.

Prova reale, *«il monitor di Nextcloud va rosso col 502 ma il servizio
funziona: trova la causa, dimmi come verificarla e scrivimi il controllo»* →
squadra assemblata da sola: **Sistemista + Debugger + Sviluppatore**.

Per cambiare la squadra si modifica `roles.json` e si riavvia il servizio.
Aggiungere un ruolo è aggiungere un oggetto: nessun codice da toccare.

### «Accesso completo», e cosa vuol dire davvero

La casella **accesso completo** compare **solo all'amministratore** e toglie la
restrizione per ruolo: ogni agente può usare tutti gli strumenti, non solo
quelli del suo mestiere. Ogni attivazione finisce nel log del servizio.

Quello che **non** fa, ed è deliberato: non concede niente che l'utente non
abbia già. Le due barriere sono in serie —

```
tools_for(utente)   ->  cosa il RUOLO DELLA PERSONA permette   (sempre attiva)
role_tools(agente)  ->  cosa il MESTIERE dell'agente permette  (questa si toglie)
```

Se `sole` spuntasse la casella (non le compare nemmeno) non otterrebbe il vault:
la prima barriera resta. E "accesso completo" **non** significa eseguire comandi
sul server: Hermes resta in sola lettura. Dare a un modello la possibilità di
eseguire comandi è una decisione separata, che va progettata con un elenco di
azioni permesse e una conferma umana — non con un interruttore.

### Quanto è davvero parallelo

Qui l'onestà conta più dell'effetto: **Ollama serve una richiesta alla volta**
salvo alzare `OLLAMA_NUM_PARALLEL`. Con il valore di default gli agenti si
mettono in coda e lo sciame è solo una divisione logica del lavoro, non un
guadagno di tempo. Sul PC la variabile è stata portata a 2, e ogni motore
dichiara il proprio limite in `backends.json`:

| Motore | `parallel` | Perché |
|---|---|---|
| PC · RTX 5070 Ti | 2 | due contesti da 16K stanno nella VRAM insieme al modello |
| Server · CPU | 1 | è già lento con una richiesta sola |
| API remota | 3 | il parallelismo non costa nulla di locale |

Alzare `parallel` oltre quello che la GPU regge non rende più veloce: fa
scambiare memoria e rallenta tutto.

### Quando usarlo (e quando no)

Su una domanda secca lo sciame **costa solo tempo**: c'è un giro in più per
pianificare e uno per ricucire. Serve su richieste larghe, che contengono
davvero più domande. Per questo è una casella, spenta di default, e non il
comportamento normale.

## 8. La personalità e la memoria

`/opt/sovereign-hermes/persona.md` contiene chi è Mohamed, com'è fatta la casa e
come Hermes deve comportarsi. È un file di testo: si modifica e si riavvia il
servizio. La copia di riferimento sta nel repo in `scripts/hermes/persona.md`.

Le conversazioni sono salvate per utente in `/var/lib/sovereign-hermes/chats/`
(file a permessi `600`), limitate agli ultimi 20 scambi.

---

## 9. Target & sizing, DNS, NPM

| Voce | Valore |
|---|---|
| **Target host** | LXC 102 (`apps-light`, 192.168.1.52) — accanto a CouchDB e Ollama |
| **Sizing** | il servizio è leggero (solo regia, nessuna inferenza): ~60 MB di RAM. Il carico vero sta sulla GPU del PC |
| **DNS / domain names / alias** | `hermes.internal`, coperto dal rewrite jolly `*.internal` di AdGuard Home. L'alias `hermes` è stato aggiunto a `sovereign-renew-npm-internal-certs.sh` e il certificato rigenerato |
| **Nginx Proxy Manager (NPM)** | proxy host verso `192.168.1.52:8093`, certificato interno, con lo snippet forward-auth di Authentik. In più `proxy_buffering off` e `proxy_read_timeout 900s`, indispensabili perché le risposte arrivano in streaming |

> **Nota su NPM**: una riga inserita a mano nel database SQLite **non** produce
> alcuna configurazione nginx — NPM la genera solo quando l'host passa dalla sua
> API. L'host è quindi stato creato via `POST /api/nginx/proxy-hosts`.

## 10. Homepage & Uptime Kuma

- **Homepage**: da aggiungere in `stacks/observability/homepage/services.yaml`
  quando si vuole la tessera anche lì; la dashboard principale ha già la sua.
- **Uptime Kuma**: monitor **da creare a mano** (Kuma non espone API REST per
  crearli, e `python-socketio` non è installabile su LXC 101 perché non ha
  uscita verso internet). Impostazioni: tipo `HTTP(s)`, URL
  `https://hermes.internal/health`, intervallo 60s, codici accettati `200-299`.
  L'endpoint `/health` è volutamente fuori dal gate SSO proprio per questo.

## 11. Backup & restore

Hermes non custodisce dati originali: il vault vive in CouchDB (già coperto dal
backup di LXC 102) e la configurazione sta nel repository.

| Elemento | Dove | Come si ripristina (*restore*) |
|---|---|---|
| Codice, persona, backends | repo `scripts/` | ricopia i file e `systemctl restart sovereign-hermes` |
| Token di lettura | `/root/sovereign-secrets/hermes/estate-token` | rigenerare su pve e ridistribuire (vedi §4) |
| Password CouchDB | `/root/sovereign-secrets/hermes/couchdb-password` | rieseguire la creazione dell'utente `hermes_reader` |
| Conversazioni | `/var/lib/sovereign-hermes/chats/` | non critiche: si possono perdere senza conseguenze |

## 12. Verifica di funzionamento

```bash
# il servizio risponde
pct exec 102 -- curl -s http://127.0.0.1:8093/api/state | python3 -m json.tool

# il gate SSO è attivo (302 verso il login)
curl -sk -o /dev/null -w '%{http_code}\n' https://hermes.internal

# /health resta pubblico, per il monitoraggio
curl -sk https://hermes.internal/health
```

Esito atteso di `/api/state`: entrambi i motori `healthy: true` e
`vault_notes` maggiore di zero (al momento dell'installazione: **33 note**).

---

## 13. Cosa manca ancora

- **Monitor su Uptime Kuma**: da creare a mano (Kuma non ha API REST per
  crearli e `python-socketio` non è installabile su LXC 101, che non ha uscita
  verso internet). Impostazioni: tipo HTTP, URL `https://hermes.internal/health`,
  intervallo 60s, codici accettati `200-299`.
- **Voce**: trascrizione vocale (Whisper) non ancora integrata.
- **Scrittura sul vault**: volutamente assente. Scrivere nel formato a pezzi di
  LiveSync su un vault vivo può corrompere la sincronizzazione; finché non è
  testato a fondo Hermes resta in sola lettura.

---

## 13-bis. Un ProxyProvider creato via ORM nasce incompleto

Creando il provider con `ProxyProvider.objects.get_or_create(...)` la pagina
rispondeva **"Redirect URI Error"**. Tre campi che l'interfaccia grafica
compila da sola restano vuoti quando si passa dall'ORM:

| Campo | Se manca | Sintomo |
|---|---|---|
| `redirect_uris` | l'outpost non ha un callback valido | *Redirect URI Error* |
| `property_mappings` | la richiesta parte **senza `scope`** | `invalid_request` |
| `grant_types` | `authorization_code` non è permesso | `invalid_request`, "The request is otherwise malformed" |

I primi due sono stati corretti uno alla volta senza risolvere; il problema è
stato chiuso solo **confrontando campo per campo con il provider della
dashboard**, che funziona. È la stessa lezione già imparata con Obsidian: di
fronte a un provider che non va, non si indovina un campo alla volta — si fa il
diff con uno che funziona.

Valori corretti (identici a `Sovereign Dashboard forward-auth`):

```python
redirect_uris   = ["https://hermes.internal/outpost.goauthentik.io/callback?X-authentik-auth-callback=true",
                   "https://hermes.internal?X-authentik-auth-callback=true"]   # entrambi STRICT
property_mappings = le 5 mappature di default (openid, email, profile, proxy outpost, entitlements)
grant_types     = ["authorization_code", "client_credentials", "password"]
```

Dopo ogni modifica va risalvato l'outpost incorporato, che rilegge la
configurazione.

**Verifica finale eseguita**: login reale come `mohamed` attraverso il flow
executor, poi `GET https://hermes.internal/` → **HTTP 200** con la pagina di
Hermes, e `/api/state` che risponde `is_admin: true`.

## 14. Troubleshooting e Rollback

| Problema | Rimedio |
|---|---|
| Hermes non risponde | `pct exec 102 -- systemctl restart sovereign-hermes` |
| "Nessun motore AI raggiungibile" | Il PC è spento o Ollama non è avviato. Il motore di scorta sul server dovrebbe comunque rispondere: se non lo fa, `pct exec 102 -- docker restart ollama` |
| Risposte vuote | Controlla che `"think": false` sia presente nel backend in uso |
| Vault non leggibile | Verifica `hermes_reader` in `_security` di `obsidiandb` e la password in `/root/sovereign-secrets/hermes/couchdb-password` |
| **Rollback** — rimuovere Hermes | `pct exec 102 -- systemctl disable --now sovereign-hermes`, poi elimina l'host `hermes.internal` da NPM |

---

## 15. Official Sources

- Libreria modelli Ollama — <https://ollama.com/library>
- `qwen3.5` (dimensioni e contesto) — <https://ollama.com/library/qwen3.5>
- `gpt-oss` — <https://ollama.com/library/gpt-oss>
