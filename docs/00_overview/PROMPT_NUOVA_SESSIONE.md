# Prompt per una sessione nuova

> Aggiornato il **2026-08-04**. **Copia il blocco del §1 come primo messaggio
> della nuova sessione.** Il §2 spiega perché il prompt dice quelle cose, il §3
> è l'impianto com'è oggi, il §4 la fila del lavoro, il §5 l'indice dei file.
>
> **Nota anti-conflitto**: se apri più sessioni sullo stesso checkout
> (`c:\DBA\Sovereign-Homelab`), fai `git status` e `git log --oneline -5` prima
> di committare. Il 31 luglio due sessioni ci hanno scritto in parallelo senza
> danno, ma è stato l'ordine delle operazioni, non un meccanismo.

---

## 1. Il blocco da copiare

```text
Lavoriamo sul Sovereign Homelab, la mia infrastruttura di casa.
Repository: c:\DBA\Sovereign-Homelab (git, branch main).
Su GitHub: https://github.com/Mohamed-DN/Sovereign-Homelab
Committa quando finisci una cosa. Il PUSH è una pubblicazione: chiedimelo,
o fallo solo se te lo dico.

LEGGI IN QUEST'ORDINE, prima di toccare qualunque cosa:
 1. docs/00_overview/PIANO_MASTER.md  <- DA QUI SI COMINCIA. La sezione 2-bis
    "COSA MANCA" è un elenco solo, 19 voci, ordinate non per difficoltà ma per
    QUANTO COSTA NON AVERLE. È la risposta a "da dove comincio".
 2. docs/00_overview/VISIONE_COMPLETA.md  <- il perché di tutto, i tre principi
    e le TRAPPOLE GIÀ PAGATE (§6). Ripagarle costa ore: leggile PRIMA.
 3. docs/00_overview/PIANO_GENERALE.md  <- la fila lunga: punti 1-21, più
    18-bis (Momo cerca dentro Nextcloud) e 18-ter (Headroom).
 4. docs/00_overview/PIANO_AGENT_MOMO.md  <- come il nostro codice sta dentro
    hermes-agent di NousResearch, con il registro delle divergenze: ogni
    divergenza si ripaga a ogni aggiornamento loro.
 5. docs/00_overview/PIANO_TESTIMONE_HERMES_MOMO.md  <- il passaggio Hermes →
    Momo. Tappe 1-4 FATTE (hermes.internal non esiste più dal 2026-08-03),
    resta la tappa 5: fermare il servizio vecchio.
 6. docs/00_overview/ARCHITECTURE_AND_DATA_FLOWS.md  <- i flussi veri, e come
    funziona la voce (ascolto e parlato).
 7. docs/00_overview/PIANO_MOMO_PROGRAMMATORE.md  <- il lavoro grosso in
    arrivo: far programmare Momo. La scoperta del 4 agosto è che il motore
    c'è già ed è SPENTO (code_execution, terminal, skills, delegation,
    cronjob, browser, sette ambienti sandbox), quindi non si costruisce: si
    accende, dentro una gabbia costruita prima. Onde P1-P10.
 8. docs/00_overview/PIANO_MOMO_DIGITAL_TWIN.md  <- il documento del
    proprietario (Sinker a 4 fasi, Automation Library, sandbox). Il suo
    punteggio §4 è SUPERATO: il conto vero sta nel file 7.

PER RAGGIUNGERE L'INFRASTRUTTURA (la chiave è permanente, provala per prima
cosa e NON rifare il bootstrap con la password):

  ssh -i /c/DBA/sovereign_homelab_audit_ed25519 \
      -o UserKnownHostsFile=/c/DBA/sovereign_known_hosts \
      -o StrictHostKeyChecking=no root@192.168.1.150

Da lì: pct exec <id> -- bash -lc '<comando>'   (il "bash -lc" NON è opzionale:
senza, una stringa multiriga si spezza e la seconda riga gira sull'host Proxmox
invece che nel container). Per le VM: qm guest exec <id> -- ...

  LXC 100 = .50   AdGuard / NPM / Headscale / Headplane / CrowdSec
  LXC 101 = .51   Authentik / Uptime Kuma / Beszel / Dozzle / step-ca / relay
  LXC 102 = .52   MOMO (/opt/momo) · Ollama + GPU T600 · Vaultwarden ·
                  SearXNG · Forgejo · Jellyfin · RustDesk · CouchDB ·
                  Postgres/Qdrant/Valkey (solo loopback) · ~19 app
  LXC 103 = .53   NetAlertX / Scrutiny / ntfy
  VM 110 Immich · VM 120 Nextcloud AIO · VM 130 Home Assistant · VM 140 PBS
  Il mio PC è .100, Windows, RTX 5070 Ti 16 GB, Ollama in ascolto.

Io sono mohamed, proprietario e amministratore: accesso completo a tutto per
principio, non chiedere il permesso. I segreti stanno in
/root/sovereign-secrets/ (0600, root) sia sull'host Proxmox sia dentro LXC 102,
e NON entrano mai nel repository: nei documenti si scrive DOVE si legge una
chiave, mai il suo valore, perché il repo è pubblico.

COME VOGLIO CHE LAVORI — non sono formalità, ognuna viene da un errore vero:
- VERIFICA SUL VIVO, non dedurre. Non dirmi "fatto" se non l'hai provato.
  Uno strumento che sbaglia non dà errore: racconta una bugia sicura di sé.
- SE NON L'HAI MISURATO, DILLO. Una stima presentata come misura è il modo più
  veloce per farmi perdere fiducia in tutti gli altri numeri.
- Dimmi quello che non funziona, anche se è colpa tua.
- PRIMA DI CANCELLARE: copia in /root/sovereign-secrets/backups/, e verifica
  che funzioni ancora IL RESTO, non solo la cosa che hai toccato.
- GLI SCRIPT CHE MANIPOLANO BACKSLASH O STRINGHE non si passano a una shell
  dentro un heredoc: si scrivono su file e si eseguono. Mi ha rotto due volte
  in un giorno (i diagrammi mermaid, e una stringa Python).
- OGNI CONTROLLO CHE SCRIVI, PROVALO SU UN CASO SANO: tre volte in un giorno
  una verifica mia ha accusato roba che stava benissimo.
- Il JavaScript dentro una stringa Python va verificato con node --check, non
  a occhio: py_compile valida il Python e lascia passare uno <script> rotto.
- scripts/validate-repository.ps1 deve passare prima di ogni commit.
- Documenta nel repository: un runbook nuovo in docs/04_apps/ rispetta il
  contratto (scopo, sizing, DNS, NPM, Homepage, Kuma, backup, restore,
  rollback, troubleshooting, edge cases, sorgenti).
- Python di sola libreria standard (unica eccezione: python3-psycopg2 da apt).
- Open source per principio, non per dogma: se un'alternativa non leggera è la
  migliore del settore va bene (criterio suo: "non lightweight ma the best").

PARLAMI IN ITALIANO. Commenti del codice e documenti in italiano quando
spiegano una decisione; i nomi tecnici restano quelli veri.

DECISIONI GIÀ PRESE, non ridiscuterle:
- MASTER: applicazione automatica dopo la validazione, ma il DIVIETO ASSOLUTO
  resta (Immich, distruzione dati, disattivare le guardie).
- LangChain NO (hermes-agent fa già quel lavoro), Langfuse SÌ, Pinecone NO
  (i vettori sono le mie note: non escono di casa), Qdrant resta.
- Niente ElevenLabs: faster-whisper + Piper/XTTS-v2, tutto in locale.
- Contenuti creati da Momo: niente volti, esseri viventi, musica.
- Il vault vero è C:\Users\Mohamed\Documents\VaultMohamed\VaultMohamed\.
```

---

## 2. Perché il prompt dice quelle cose

- **«Si comincia da PIANO_MASTER §2-bis»** — prima l'elenco era sparso su nove
  fasi più tre sezioni, e «cosa manca?» richiedeva di leggere tutto. Ora c'è
  una tabella sola, ordinata per costo dell'assenza.
- **«Verifica sul vivo»** — cose scoperte controllando invece di dedurre, in un
  giorno solo: `rustdesk.internal` puntava al proxy sbagliato e **nessun client
  poteva registrarsi**; Uptime Kuma rispondeva `monitorList` e `apiKeyList`
  **senza login** a chiunque sulla LAN; i motori fuori casa **non avevano mai
  funzionato**.
- **«Se non l'hai misurato, dillo»** — ho detto «15-20 secondi» di attesa a PC
  spento come se fosse una misura. Erano 3,1 s misurati più un ritardo
  immaginato. Correzione scritta in §2-bis voce 1.
- **«Prova i tuoi controlli su un caso sano»** — un controllo geometrico ha
  accusato otto pezzi sani (leggeva coordinate relative come assolute); un
  controllo mermaid ne ha accusati quattro (i nodi definiti sulla riga della
  freccia sono validi); una verifica di riparazione ne ha accusati dodici. Un
  controllo che grida al lupo è peggio di nessun controllo.
- **«Niente heredoc per gli script che toccano i backslash»** — una conversione
  a mermaid fatta così ha trasformato `\\n` in `\n` e **distrutto tutti i
  diagrammi del repository**; riparati da file e verificati contro l'ultimo
  commit sano.
- **«Il push è una pubblicazione»** — 21 commit sono rimasti fermi in locale
  per un giorno mentre il proprietario guardava GitHub e vedeva il README di un
  mese prima.

### 2.1 Le trappole nuove, imparate il 2026-08-03/04

| Trappola | Come si manifesta |
|---|---|
| **La chiave di un motore esterno non si chiama `CUSTOM_API_KEY`** | `_host_derived_api_key(base_url)` in `hermes_cli/runtime_provider.py` deriva il nome **dall'host**: per `openrouter.ai` cerca `OPENROUTER_API_KEY`. Scrivere `CUSTOM_API_KEY` costruisce il provider con `api_key: ''` → `RuntimeError: No LLM provider configured` a **ogni** messaggio |
| **`nvidia-modprobe` ritorna 0 senza fare niente** | se il driver è già inizializzato non ricrea `/dev/nvidia0`. Solo `nvidia-smi`, che *apre* la scheda, li fa ricreare. Un rimedio costruito sul solo modprobe sembra corretto e non lo è |
| **`bind,optional,create=file` crea file VUOTI** | LXC 102 parte «sano» con dei file regolari al posto dei device, e il solo Ollama resta giù con exit 128 |
| **Un plugin `kind: exclusive` non viene caricato affatto** | `plugins.py:1417` — non può registrare comandi. `/memoria` è dovuto migrare in `sovereign_tools` |
| **I plugin si caricano per file, non come pacchetti** | `import sovereign` da un plugin fratello fallisce: serve `importlib.util.spec_from_file_location` |
| **Telegram ha due tetti al menu** | 100 comandi (documentato) e **~4096 byte di payload (non documentato)**: superarlo **svuota il menu**. 52 comandi = 3376 byte, funziona |
| **Il token del bot sta in `.env`, non in `config.yaml`** | ho misurato sul file sbagliato, ottenuto un 404 e l'ho letto come «menu vuoto» |
| **Un `.env` cambiato non lo vede un processo già avviato** | `load_hermes_dotenv()` copia in `os.environ` all'avvio: per questo cambiare motore richiede il riavvio |
| **La SMIL inserita via `innerHTML` non parte mai** | non entra nella timeline del documento; e il contenuto di `<use>` sta in uno shadow tree che il CSS del documento non raggiunge |

### 2.2 Un difetto noto e NON risolto
Il `REVOKE UPDATE, DELETE` su `master_log` **non morde**: il ruolo `hermes` di
Postgres è superuser e i superuser scavalcano i permessi. La garanzia che regge
oggi è architetturale (nessun percorso nel codice scrive su quella tabella),
non del database. Va detto, non nascosto.

---

## 3. L'impianto oggi (2026-08-04)

Un Proxmox (`pve`, 192.168.1.150), **4 container** e **4 VM**, **31 nomi
privati** dietro una porta pubblica sola, **40 monitor** in Uptime Kuma.

### Momo, l'assistente

Gira su `hermes-agent` 0.19.0 (NousResearch) in LXC 102, con il nostro codice
come divergenza dichiarata. Si raggiunge da `momo.internal` e da Telegram
(`@dn_momo_bot`, allowlist di un id solo).

- **Otto motori**, `/motore <numero>`: **1-3** sul PC del proprietario (RTX
  5070 Ti), **4-6** sulla T600 del server, **7-8** fuori casa (OpenRouter,
  Bedrock). `momo-motore` riscrive `.env` e riavvia; da Telegram il riavvio è
  **differito e staccato** (altrimenti il comando si uccide prima di
  rispondere) e **avvisa quando è tornato**.
  Per una sessione sola, senza riavvio: `/model --provider <nome>`.
- **Gli strumenti seguono il motore**: 20 a un motore di casa, **1** a uno di
  fuori — un motore esterno non vede i dati di casa. Contato dal vivo da
  `scripts/momo/tests/test_tool_visibility.py`.
- **Memoria fuori dal modello**, condivisa con l'Hermes in ritiro: Postgres
  (fatti, procedure, agenda, rubrica) + Qdrant (125 note per significato) +
  Valkey (cache degli embedding: sulla CPU costavano 18 s). **Impara dai turni
  da sola**; si rivede e si cancella con `/memoria`.
- **Voce**, in tutti e due i sensi: `faster-whisper medium` capisce i vocali e
  riconosce la lingua da solo, Piper risponde. Tutto in casa.
- **Reti di sicurezza**: interruttore globale RUNNING/PAUSED, Guardrail
  (anti-bugia), Verificatore degli allarmi (un allarme si conferma sondando,
  non credendo), modalità MASTER con divieto assoluto compilato a codice.

### Cosa è stato chiuso il 2026-08-03/04

| | |
|---|---|
| **Motori fuori casa** | **non avevano mai funzionato**: nome della variabile sbagliato (vedi §2.1). Ogni messaggio rispondeva «Sorry, I encountered an unexpected error». I motori di casa lo nascondevano perché Ollama non vuole chiavi |
| **GPU T600** | i nodi `/dev/nvidia*` non esistono al boot: servizio con ritentativi (`scripts/sovereign-nvidia-dev-nodes.sh`). Ollama era giù da nove ore e **il guasto aveva avvisato** — Kuma, Verificatore, mail — ma nessuno era lì a leggere |
| **Ripiego a PC spento** | era `qwen3.5:4b`, il solo modello che **non** entra nella T600. Ora `qwen2.5:3b` → `granite4:micro` → OpenRouter, e `api_max_retries` da 3 a 2 |
| **Uptime Kuma** | `disableAuth=true` e porta 3001 su `0.0.0.0`: **senza login da tutta la LAN**. Ristretta via `DOCKER-USER` (le porte pubblicate da Docker scavalcano `INPUT`) |
| **Il monitor di Momo** | non esisteva. Creato (id 49). Kuma 2.x non ha REST: si passa da `scripts/sovereign-kuma-monitor.py`, socket.io |
| **`rustdesk.internal`** | puntava a NPM, ma RustDesk è TCP grezzo: nessun client poteva registrarsi. Rewrite specifica in AdGuard |
| **Memoria automatica** | scritta a luglio, **mai installata**. Ora gira, provata dal vivo (un fatto scritto, e un veto scattato correttamente) |
| **`web_search`** | il nostro rubava il nome a quello più forte di hermes-agent. Escluso il nostro, il loro punta alla SearXNG di casa. Verificato dal vivo |
| **`hermes.internal`** | rimosso da NPM, Authentik e certificato, con copia salvata (tappa 4 del testimone) |

---

## 4. La fila del lavoro

L'elenco autorevole è **[PIANO_MASTER §2-bis](PIANO_MASTER.md)**, 19 voci. I
primi da prendere, e il perché:

| | Cosa | Perché è in cima |
|---:|---|---|
| 1 | **Quanto si aspetta a PC spento** | non è più un difetto ma un **numero mancante**: si legge alla prossima assenza vera con `journalctl -u momo-gateway \| grep 'trying fallback'` |
| 2 | **Voce per lingua** | una risposta in arabo viene letta dalla voce italiana. Le tre voci ci sono, ma `tts.piper.voice` accetta un nome solo: serve una divergenza dichiarata |
| 3 | **Momo cerca dentro Nextcloud** ([18-bis](PIANO_GENERALE.md)) | fra `vault_search` e `web_search` non c'è niente, e lì stanno i file pesanti |
| 4 | **Tappa 5**: fermare `sovereign-hermes` | il nome è uscito, resta il processo. Condizione: giorni di pannello usato davvero |
| 5 | **Perché Nextcloud cade** | il registratore è installato sulla VM 120 e aspetta il prossimo episodio. Sonda **dentro e fuori** la VM, per distinguere «Apache morto» da «pubblicazione della porta sparita» |
| 6 | **`db_query` in sola lettura** | il proprietario è DBA e non può interrogare i propri database da Momo |
| 19 | **Momo che programma** ([piano](PIANO_MOMO_PROGRAMMATORE.md)) | il lavoro grosso. Il motore c'è già ed è spento: si accende, dentro una gabbia costruita prima |
| 20 | **Headroom** ([18-ter](PIANO_GENERALE.md)) | comprime il contesto del 60-95%: qui il contesto **è** il vincolo, perché decide quali modelli entrano in 4 GB di T600 |

**Aspettano lui, non noi**: armare MASTER da Telegram (decisione di sicurezza),
le registrazioni della sua voce per XTTS-v2 (copione pronto in tre lingue),
Ente Photos per la sorella, Ceph acceso a vuoto sull'host.

---

## 5. I file, in ordine di utilità

**Da leggere per primi**
- [PIANO_MASTER.md](PIANO_MASTER.md) — l'indice di tutto, lo stato, e §2-bis «cosa manca»
- [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md) — i principi e le trappole già pagate
- [PIANO_GENERALE.md](PIANO_GENERALE.md) — la fila lunga, punti 1-21 + 18-bis + 18-ter
- [ARCHITECTURE_AND_DATA_FLOWS.md](ARCHITECTURE_AND_DATA_FLOWS.md) — i flussi e la voce
- [../../README.md](../../README.md) — la porta d'ingresso, con i due schemi

**Momo**
- [PIANO_MOMO_PROGRAMMATORE.md](PIANO_MOMO_PROGRAMMATORE.md) — far programmare Momo: cosa c'è già acceso e spento, la sandbox, il router del codice, Forgejo come uscita, i verdetti su Ruflo/Ponytail/RooFlow/Claude
- [PIANO_MOMO_DIGITAL_TWIN.md](PIANO_MOMO_DIGITAL_TWIN.md) — il documento del proprietario, e le richieste T1-T12
- [PIANO_AGENT_MOMO.md](PIANO_AGENT_MOMO.md) — le divergenze dal codice di NousResearch
- [PIANO_TESTIMONE_HERMES_MOMO.md](PIANO_TESTIMONE_HERMES_MOMO.md) — il passaggio, tappa 5 aperta
- [../04_apps/momo-telegram.md](../04_apps/momo-telegram.md) — canale, motori, menu, voce
- [../04_apps/momo-memoria-automatica.md](../04_apps/momo-memoria-automatica.md) — cosa impara e come si cancella
- [../04_apps/momo-guardrail.md](../04_apps/momo-guardrail.md) — la difesa anti-bugia
- [../04_apps/sovereign-interruttore.md](../04_apps/sovereign-interruttore.md) — RUNNING/PAUSED
- [../04_apps/sovereign-verificatore.md](../04_apps/sovereign-verificatore.md) — gli allarmi si sondano

**Infrastruttura**
- [../04_apps/ai_ollama.md](../04_apps/ai_ollama.md) — §9.0 cosa entra davvero in 4 GB, §9.1 la trappola dei nodi GPU
- [../03_platform_services/IAM_LDAP_SSO_PLAN.md](../03_platform_services/IAM_LDAP_SSO_PLAN.md) — le integrazioni SSO
- [../04_apps/nextcloud.md](../04_apps/nextcloud.md) — §7.1 il 502 intermittente
- [../04_apps/rustdesk.md](../04_apps/rustdesk.md) — Mac → PC Windows
- [../99_reference/SERVICE_VISIBILITY_MATRIX.md](../99_reference/SERVICE_VISIBILITY_MATRIX.md) — dove sta ogni servizio
- [../06_operations_security/ESPOSIZIONE_E_SEGRETI.md](../06_operations_security/ESPOSIZIONE_E_SEGRETI.md) — l'indice dei segreti (i percorsi, non i valori)

**Valutazioni**
- [VALUTAZIONE_TECNOLOGIE_2026-08.md](VALUTAZIONE_TECNOLOGIE_2026-08.md) — tredici tecnologie: cosa vale, cosa c'è già, cosa no e perché

**Strumenti che si riusano**
- `scripts/momo/momo-motore.py` — il commutatore degli otto motori
- `scripts/momo/tests/test_tool_visibility.py` — conta gli strumenti per motore
- `scripts/sovereign-kuma-monitor.py` — creare monitor (Kuma 2.x parla solo socket.io)
- `scripts/sovereign-npm-proxy-host.py` — host NPM via API (**mai** dal database)
- `scripts/sovereign-smonta-hermes-internal.py` — dismettere un nome, con copia
- `scripts/sovereign-nvidia-dev-nodes.sh` — i nodi GPU, con ritentativi
- `scripts/validate-repository.ps1` — deve passare prima di ogni commit

---

## 6. Cosa NON mettere nel prompt
- Nessun segreto: né chiavi, né token, né password. I percorsi stanno in
  `ESPOSIZIONE_E_SEGRETI.md` §4, i valori su disco a 0600. Il repo è pubblico.
- Nessuna promessa non verificata: se una cosa è «da fare», il prompt lo dice.
  Il proprietario ha chiesto esplicitamente di sapere cosa non funziona,
  «anche se è colpa tua».
