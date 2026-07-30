# La visione completa — dove siamo, dove si va, e come continuare

> Scritto il 2026-07-30. **Questo documento serve a una cosa sola: permettere a
> chiunque (me, un'altra sessione, un'altra persona) di riprendere il lavoro
> senza ricostruire il contesto da zero.** Lo stato puntuale sta nel
> [PIANO_MASTER](PIANO_MASTER.md); qui c'è il *perché*, che è la parte che si
> perde.

---

## 1. Che cosa stiamo costruendo, in una frase

**Un assistente di casa che sa cose vere.** Non una chat: un servizio che
conosce questa infrastruttura, ricorda quello che gli dici, sa dov'è scritta una
procedura, e che il proprietario può usare dal telefono per far fare le cose.

Tutto il resto — Postgres, Qdrant, i gateway, i modelli — è mezzo, non fine.

## 2. I tre principi che decidono ogni dubbio

Quando non si sa cosa scegliere, si torna a questi. Sono la ragione di quasi
tutte le decisioni tecniche prese finora.

### 2.1 La regia sta sul server, la forza bruta dove c'è la GPU
Hermes non fa inferenza: instrada. Il PC di Mohamed ha una RTX 5070 Ti e, quando
è accesa, fa il lavoro; il server ha un modello piccolo che non manca mai. Si
aggiunge una GPU futura con una riga in `backends.json`, senza toccare codice.
**Corollario misurato**: la stessa operazione può costare 97 ms sulla GPU e 18 s
sulla CPU. Progettare come se fossero equivalenti porta a un sistema inusabile.

### 2.2 Verificare prima di dichiarare
Uno strumento che sbaglia **non dà errore: racconta una bugia sicura di sé.**
Questo non è un modo di dire, è la cosa che è successa più volte in questo
progetto:

- il modello ha detto «Ho salvato» con il database vuoto (tre volte, con tre
  frasi diverse);
- lo strumento email ha riferito «invio fallito» su email consegnate;
- io stesso ho concluso «la nota non è stata scritta» perché la mia query a
  CouchDB non codificava le barre nell'`_id`. La nota c'era.

**Da cui la regola**: una cosa è fatta quando la si è *riletta*, non quando il
codice è scritto o l'HTTP ha risposto 201.

### 2.3 Degradare, non mentire
Se un pezzo non c'è, il sistema fa il meno possibile e **lo dice**. La ricerca
per significato cade sulla ricerca a parole, e la risposta dichiara quale delle
due ha usato. La memoria assente non diventa «non ricordo niente», diventa «la
memoria non è disponibile». Un errore onesto è un'informazione; un successo
finto è un danno.

## 3. Com'è fatto adesso

```
                        ┌── PC di Mohamed (.100) ── RTX 5070 Ti
                        │    Ollama: qwen3.5:9b + embeddinggemma
   iPhone / browser     │
        │               │
        ▼               │
   NPM (LXC 100 .50) ───┤  forward-auth Authentik: senza login non si passa
   *.internal + TLS     │
        │               │
        ▼               │
   Hermes (LXC 102 .52 :8093) ── la regia
        │               │
        ├─ motori ──────┘  1. PC (GPU)  2. server (CPU)  3. OmniRoute  4. Bedrock
        │                     ↑ privati ────────────↑    ↑ NON privati ──────↑
        │
        ├─ memoria (loopback, mai sulla LAN)
        │    Postgres  fatti · agenda · PROCEDURE · registro
        │    Qdrant    significato: fatti + vault + runbook + procedure
        │    Valkey    cache degli embedding
        │
        ├─ vault Obsidian via CouchDB
        │    hermes_reader  legge (non può scrivere: validate_doc_update)
        │    hermes_writer  scrive, solo dentro «07 Notes/Hermes/»
        │
        └─ strumenti: stato infrastruttura · accessi · web · email · squadra di 13 agenti
```

**La linea che non si attraversa**: un motore non privato riceve **2** strumenti
(solo web), un motore di casa **16**. La guardia è verificata, non promessa —
vedi §7.

## 4. Le fasi: dove siamo

| Fase | Cosa | Stato |
|---|---|---|
| 0 | Chat, SSO, ruoli, motori intercambiabili, squadra di agenti, web, email, immagini | ✅ |
| 1 | **Memoria fuori dal modello**: Postgres + Qdrant + Valkey, `ricorda`/`cerca`/`dimentica`/agenda | ✅ verificata col riavvio |
| 1-bis | **Procedure** in database relazionale, trovabili per significato | ✅ |
| 4-parziale | **Scrittura sul vault** Obsidian, confinata a una cartella | ✅ verificata end-to-end |
| 5 | Regola `private` + **OmniRoute** + **Bedrock** | ✅ (manca solo un fornitore gratuito con chiave) |
| **2** | **Voce**: registratore nella pagina, Whisper, Piper | ⬜ **la prossima** |
| **3** | **Telegram + PWA**: Hermes in tasca | ⬜ **la prossima** |
| 4 | Mostrare il ragionamento, repo → vault | ⬜ |
| 6 | Modalità master: azioni permesse, conferme, interruttore | ⬜ |
| 7 | `db_query` in sola lettura, controlli programmati | ⬜ |

Il piano operativo per fase è in [HERMES_PIANO_A_FASI.md](HERMES_PIANO_A_FASI.md);
quello che viene dai repo Nexi è in
[PIANO_AGGIORNAMENTO_DA_NEXI.md](PIANO_AGGIORNAMENTO_DA_NEXI.md).

## 5. Il prossimo passo, in concreto

Il proprietario ha detto cosa gli interessa: **parlare con Hermes dal cellulare e
fargli fare le cose.** Tradotto in lavoro, in ordine:

1. **PWA** (`manifest.json` + service worker + icone su `hermes.internal`).
   È l'unica cosa che dà Hermes sul telefono **senza dipendere da nessuno**:
   si aggiunge alla schermata home dell'iPhone e funziona sulla VPN. Da fare
   per prima perché non ha prerequisiti.
2. **Registratore nella pagina** (`MediaRecorder` → upload → trascrizione).
   Il pulsante voce oggi *parla* ma non *ascolta*: l'ingresso non è mai stato
   costruito. Non è un bug, è una parte mancante.
3. **Whisper**, e qui c'è una scelta da fare: sul PC con la GPU è 100× più
   veloce ma funziona solo a PC accesso; sul server è sempre disponibile ma
   lento. La risposta coerente col principio 2.1 è **entrambi, PC prima**.
4. **Telegram** (bot ufficiale, long polling, nessuna porta aperta).
   **Bloccato su di lui**: il token si ottiene solo parlando con @BotFather dal
   suo account. Mappatura `id → utente` a mano, sconosciuti rifiutati.
5. **Modalità master** (fase 6), che è quello che rende vera la frase «e lui mi
   fa le robe»: un elenco di azioni permesse come dati, conferma per
   l'irreversibile, interruttore globale. Il disegno da copiare è quello a tre
   strati di Nexi (Direttive → Orchestrazione → Esecuzione).

## 6. Le trappole già pagate — non ripagarle

Ognuna di queste è costata tempo reale. Sono scritte perché non si ripeta.

| Trappola | Come si manifesta | La verità |
|---|---|---|
| `think` di qwen3.5 | risposta vuota, 4080 token di ragionamento | serve `"think": false` sull'API nativa Ollama; nella forma OpenAI **quel campo non esiste**, l'equivalente è `reasoning_effort: "none"` |
| Modelli di ragionamento dietro API OpenAI | `<reasoning>…</reasoning>` dentro il testo della risposta | va rimosso lato server: il ragionamento è roba interna |
| `/models` non è universale | un motore buono compare «non funzionante» | **Bedrock risponde 404 su `/models`**: un 404 significa «non elenca», non «è giù». 401/403 sì |
| ProxyProvider Authentik via ORM | «Redirect URI Error», poi `invalid_request` | nasce senza `redirect_uris`, `property_mappings`, `grant_types`. Si **clona campo per campo** un provider che funziona |
| NPM e il suo database | una riga inserita a mano non produce nessuna configurazione nginx | l'host va creato dalla **sua API** |
| LXC 102 gira su `Etc/UTC` | l'agenda sbaglia di due ore, l'orologio detto al modello è indietro | il fuso si **dichiara** (`HERMES_TZ`), non si eredita |
| L'impronta di un documento indicizzato | cambi lo spezzettamento e non si reindicizza niente | l'impronta copre il *testo*, non il *modo*: serve `--force` |
| `array_to_string` in una colonna generata | «generation expression is not immutable» | è STABLE. E `to_tsvector('italian', …)` vuole `::regconfig` esplicito |
| `_id` con barre in CouchDB | «not_found» su un documento che esiste | le barre vanno codificate `%2F` |
| `curl -o /dev/stdout` sotto `pct exec` | exit 23 | non serve: il corpo va già su stdout |
| `sticky bottom` come ultimo figlio | «manca il pulsante» | sta in fondo al **documento**: per un pulsante sempre visibile serve `fixed` |
| Il pannello impostazioni | i campi messi a mano sparivano al salvataggio | `save_backends` scartava in silenzio `private`, `parallel`, `extra` |
| `*secret*` nel `.gitignore` | uno script citato nei runbook non è nel repo | esclude anche gli script che *generano* i segreti |
| Templater + journals | la nota giornaliera contiene il template grezzo | **corsa all'avvio**: `openOnStartup` crea la nota prima che Templater sia caricato |
| `\n` dentro il JS scritto in una tripla-stringa Python | il pannello sembrava vuoto: nessun motore, nessun modello, nessun fornitore, in silenzio | Python lo trasforma in un vero a-capo **prima** che il browser veda il file: uno `<script>` che fallisce al parse non dà errore visibile, smette solo di fare qualunque cosa. Va scritto `\\n`, e ogni pagina nuova va passata a un parser JS vero (`node --check`), non solo a `python3 -m py_compile` |

## 7. Come si verifica che è tutto in piedi

Il comando più utile è il primo: dice tutto in una riga per componente.

```bash
# la memoria, con i conteggi e il tempo di un embedding
pct exec 102 -- bash -lc 'cd /opt/sovereign-hermes && python3 sovereign-hermes.py --memory-status'

# i motori: chi risponde, chi ha una chiave, chi è privato
pct exec 102 -- curl -s http://127.0.0.1:8093/api/backends

# LA PROPRIETÀ CHE CONTA: un motore non privato non deve vedere strumenti di casa
#   atteso: motori locali 16 strumenti, esterni 2
pct exec 102 -- python3 /tmp/test_guard.py

# i gate SSO
curl -sk -o /dev/null -w '%{http_code}\n' https://hermes.internal/      # 302
curl -sk -o /dev/null -w '%{http_code}\n' https://omniroute.internal/   # 302
curl -sk https://hermes.internal/health                                 # 200

# le porte dei database NON devono rispondere dalla rete
pct exec 101 -- curl -s -m 5 http://192.168.1.52:6333/collections       # deve fallire
```

Il test di accettazione della memoria, per intero: dire un fatto → riavviare il
servizio → cancellare la conversazione → chiedere. Se lo sa ancora, la memoria
è fuori dal modello per davvero.

## 8. Le decisioni che aspettano il proprietario

Queste non le prendo io, e senza risposta restano ferme.

1. **Ceph** gira a vuoto sull'host: 0 OSD, 0 pool, 0 dati, ~770 MB e un
   `HEALTH_WARN` permanente che maschererà il prossimo avviso vero. Fermarlo, o
   tenerlo per un secondo nodo futuro?
2. **`python3-psycopg2` da apt** rompe la regola «solo libreria standard».
   L'alternativa era scrivere a mano il protocollo di Postgres. Tutte le
   chiamate stanno in un modulo: si cambia quando vuole.
3. **Il token Telegram** da @BotFather: solo lui può ottenerlo.
4. **Una chiave di un fornitore gratuito** (Groq, Cerebras, NVIDIA NIM,
   Cloudflare AI) per dare benzina a OmniRoute.
5. **Open WebUI**: la raccomandazione è tenerli separati.
6. **Ente Photos** per la sorella, o restare com'è.
7. **SSH alla VM 120** per chiudere il 502 di Nextcloud. *(Nota: esiste già una
   chiave in `/root/sovereign-secrets/vm120-nextcloud-ssh` sull'host — mai
   provata.)*

## 9. Dove sono le cose

| Cosa | Dove |
|---|---|
| Codice di Hermes | `scripts/sovereign-hermes.py` (un file), memoria in `scripts/hermes/hermes_memory.py` |
| Configurazione viva | LXC 102 `/opt/sovereign-hermes/` — `backends.json`, `roles.json`, `persona.md` |
| Segreti | host Proxmox `/root/sovereign-secrets/`, **e** LXC 102 `/root/sovereign-secrets/hermes/` (0600, mai nel repo) |
| Stack Docker | `stacks/<nome>/` nel repo, copiati in LXC 102 `/opt/sovereign-homelab/stacks/` con il loro `.env` |
| Copia del repo per l'indicizzazione | LXC 102 `/opt/sovereign-repo` (**non** `/opt/sovereign-homelab`: là ci sono i `.env` in uso) |
| Runbook per servizio | `docs/04_apps/` — ognuno con troubleshooting, rollback e sorgenti |
| Accesso | `ssh -i /c/DBA/sovereign_homelab_audit_ed25519 -o UserKnownHostsFile=/c/DBA/sovereign_known_hosts root@192.168.1.150` |

Prima di committare: `scripts/validate-repository.ps1` deve passare **10 gruppi
su 10**. Fra i controlli c'è il contratto dei runbook: ogni documento in
`docs/04_apps/` deve avere scopo, sizing, DNS, NPM, Homepage, Kuma, backup,
restore, rollback, troubleshooting e sorgenti.

## 10. Come lavorare qui

Dal proprietario, e vale più di qualunque scelta tecnica:

- **Verifica prima di dichiarare.** Non dire «fatto» se non l'hai provato.
- **Dimmi quello che non funziona, anche se è colpa tua.**
- Documenta tutto nel repository e committa.
- Non indovinare su cose che può dirti lui: **chiedi**.
- Su Authentik: se un provider non va, **diffa** campo per campo con uno che
  funziona. Non un campo alla volta.
- Commenti in inglese, messaggi all'utente in italiano, Python di sola libreria
  standard (con l'eccezione dichiarata al §8.2).
