# Prompt per una sessione nuova

> Aggiornato il 2026-07-31 (terza revisione, sera). **Copia il blocco del §1
> come primo messaggio della nuova sessione.** Il §2 spiega perché il prompt
> dice quelle cose. **Nota anti-conflitto**: se apri più sessioni sullo stesso
> checkout (`c:\DBA\Sovereign-Homelab`), fai `git status` e `git log --oneline
> -5` prima di committare — oggi due sessioni hanno scritto nello stesso
> repository in parallelo, senza danno perché entrambe hanno verificato prima
> di dichiarare, ma è stato un caso, non una garanzia.

---

## 1. Il blocco da copiare

```text
Lavoriamo sul Sovereign Homelab, la mia infrastruttura di casa.
Repository locale: c:\DBA\Sovereign-Homelab (git, branch main, si committa e si
pusha su main). Su GitHub: https://github.com/Mohamed-DN/Sovereign-Homelab

LEGGI IN QUEST'ORDINE, prima di toccare qualunque cosa:
 1. docs/00_overview/PIANO_GENERALE.md     <- DA QUI SI COMINCIA: venti punti,
    tutto quello che c'è in ballo, con il criterio che decide l'ordine e la
    verifica di ogni voce. SOSTITUISCE ORDINE_DEI_LAVORI.md come fila di
    lavoro (quello resta valido come ragionamento sul criterio).
 2. docs/00_overview/VISIONE_COMPLETA.md   <- il perché di tutto, i tre principi
    e le DICIASETTE TRAPPOLE GIÀ PAGATE (§6). Ripagarle costa ore: leggile.
 3. docs/00_overview/PIANO_MASTER.md       <- l'indice di tutto e lo stato di
    ogni cosa. Regola scritta dentro: se una cosa non è in quella tabella, è
    stata dimenticata.
 4. docs/00_overview/PIANO_AGENT_MOMO.md   <- la fusione del nostro Hermes con
    hermes-agent di NousResearch. Fasi 1-4 fatte e verificate.
 5. docs/00_overview/PIANO_MOMO_DIGITAL_TWIN.md <- cosa Momo deve saper fare:
    Sinker a 4 fasi, Guardrail (FATTO), automation library, sandbox, squadra a
    grafo.
 6. docs/04_apps/hermes.md, docs/04_apps/hermes-memoria.md e
    docs/04_apps/momo-guardrail.md <- i runbook del servizio, della sua
    memoria, e del Guardrail (condiviso fra Hermes e Momo).
Poi quando servono: docs/06_operations_security/ESPOSIZIONE_E_SEGRETI.md
(l'indice dei segreti), docs/00_overview/PIANO_ESECUTIVO_2026-08.md,
docs/00_overview/PIANO_AGGIORNAMENTO_DA_NEXI.md.

PER RAGGIUNGERE L'INFRASTRUTTURA (la chiave è permanente, provala per prima
cosa e NON rifare il bootstrap con la password):

  ssh -i /c/DBA/sovereign_homelab_audit_ed25519 \
      -o UserKnownHostsFile=/c/DBA/sovereign_known_hosts \
      -o StrictHostKeyChecking=no root@192.168.1.150

Da lì: pct exec <id> -- bash -lc '<comando>'   (il "bash -lc" NON è opzionale:
senza, una stringa multiriga si spezza e la seconda riga gira sull'host Proxmox
invece che nel container).

  LXC 100 = .50   NPM / AdGuard / Headscale / Headplane
  LXC 101 = .51   Authentik / Uptime Kuma / step-ca / Homepage / relay email
  LXC 102 = .52   Hermes:8093 · MOMO (/opt/momo) · CouchDB · Ollama (NIENTE
                  Open WebUI, rimosso il 31/7) · Postgres/Qdrant/Valkey (solo
                  loopback) · ~19 app
  LXC 103 = .53   ntfy / Scrutiny
  VM 110 Immich · VM 120 Nextcloud · VM 130 Home Assistant · VM 140 PBS
  Il mio PC è .100, Windows, RTX 5070 Ti 16 GB, Ollama in ascolto.

Io sono mohamed, proprietario e amministratore: accesso completo a tutto per
principio, non chiedere il permesso. Segreti in /root/sovereign-secrets/ (0600)
sia sull'host Proxmox sia dentro LXC 102, mai nel repository.

COME VOGLIO CHE LAVORI:
- Verifica prima di dichiarare. Non dirmi «fatto» se non l'hai provato. Uno
  strumento che sbaglia non dà errore: racconta una bugia sicura di sé.
- Dimmi quello che non funziona, anche se è colpa tua.
- Documenta tutto nel repository e committa.
- Prima di committare, scripts/validate-repository.ps1 deve passare 10 gruppi
  su 10. Un runbook nuovo in docs/04_apps/ deve rispettare il contratto:
  scopo, sizing, DNS, NPM, Homepage, Kuma, backup, restore, rollback,
  troubleshooting, sorgenti, e ora anche Edge Cases (A8 di Nexi): cosa succede
  se un passo va a metà, scritto PRIMA di costruire.
- Non indovinare su cose che posso dirti io: chiedimi.
- Su Authentik: se un provider non va, confronta campo per campo con uno che
  funziona. Non un campo alla volta.
- Commenti in inglese, messaggi a me in italiano, Python di sola libreria
  standard (unica eccezione dichiarata: python3-psycopg2 da apt).
- Il JavaScript scritto dentro una stringa Python va verificato con un parser
  VERO (node --check), non a occhio: py_compile valida solo il Python e lascia
  passare uno <script> rotto. Lo stesso vale per l'XML dei task di Windows:
  schtasks.exe dà un errore criptico che non dice dove, un vero parser XML sì.
- Sono open source per principio, non per dogma: alternative anche non
  lightweight vanno bene se sono le migliori del settore (criterio dato il
  31/7: «non lightweight ma the best»). Langfuse è stato scelto così nonostante
  l'acquisizione ClickHouse, perché resta MIT e self-hostable.
- Se apri più sessioni sullo stesso checkout, occhio ai commit paralleli (vedi
  nota in cima al file).

DOVE SIAMO (sera del 31 luglio 2026):
Hermes è vivo su https://hermes.internal, con memoria fuori dal modello
(Postgres+Qdrant+Valkey) e quattro motori fra cui Groq e AWS Bedrock.
Il piano esecutivo è FINITO: PWA installabile su iPhone, catalogo modelli,
preset fornitori + router per intenti, rubrica email, pannello a schede,
modalità MASTER con guardia sull'host.

AGENT MOMO (fusione con hermes-agent 0.19.0, in /opt/momo su LXC 102):
  fase 1 OK  respira, isolato, sulla GPU del PC
  fase 2 OK  UNA SOLA MEMORIA con l'Hermes vivo
  fasi 3+4 OK  11 strumenti + 10 di memoria, guardia privato/non-privato
             attaccata su ENTRAMBE le vie (contato dal vivo: motore di casa 21
             strumenti, motore esterno 2 — solo web)
  GUARDRAIL OK (31/7)  la difesa anti-bugia, un file di regole condiviso fra
             Hermes e Momo. Trovati e chiusi tre buchi veri costruendolo: uno
             strumento fallito che contava come riuscito (anche nell'Hermes
             vivo), un verbo troppo generico che accusava frasi oneste, gli
             strumenti di memoria visibili (non eseguibili) a un motore
             esterno. Runbook: docs/04_apps/momo-guardrail.md

OGGI (31/7), IN PIÙ:
- Open WebUI SMANTELLATO ovunque: container, volume, host NPM ai.internal,
  applicazione Authentik (c'era, il token del dashboard non aveva i permessi
  per vederla — trovata interrogando il DB), tessera Homepage, monitor Kuma,
  allowlist del control-agent e del dashboard, ~19 documenti. Aveva
  l'iscrizione libera aperta con nessun admin mai rivendicato: chiunque sulla
  VPN sarebbe diventato proprietario di un accesso diretto e senza guardie a
  Ollama.
- PIANO_GENERALE.md scritto da un'altra sessione in parallelo (130 messaggi
  di quattro sessioni archiviate riletti, 19 documenti di 00_overview/
  riletti): venti punti, undici voci trovate perse per strada (R1-R11).
  Punti 1-3 fatti: il vault giusto identificato e un incidente di sicurezza
  reale su CouchDB trovato e chiuso (require_valid_user sparito durante un
  --force-recreate, mai persistito in nessun volume); il debito di sicurezza
  quasi tutto già chiuso (tre voci su quattro erano già fatte); i repo dentro
  Obsidian COSTRUITI (prima volta, mai esistiti prima) — script + task
  programmato, verificato che il task GIRA DAVVERO (LastTaskResult: 0), non
  solo che il file esiste.
- Risposte già date, non ridiscuterle: Langfuse sì (è il migliore, non il più
  leggero); LangChain no (hermes-agent fa già quel lavoro, MCP-da-client è la
  risposta strutturale per farlo estendere a Momo); OmniRoute e OpenRouter
  insieme, ruoli diversi (OmniRoute = commutatore in casa; OpenRouter =
  ripiego del ripiego, mai su dati privati, sa fare fallback su un array di
  modelli da solo).

COSA DEVI FARE: segui docs/00_overview/PIANO_GENERALE.md dal punto 4 (il
Verificatore + interruttore RUNNING/PAUSED — i punti 1-3 sono fatti). Prima
controlla se qualcuno ha già proseguito: git log --oneline -10.
Resta aperto e sospeso, aspetta la mia conferma: R4 (ruotare la password admin
riusata in più posti — serve prima l'elenco di dove è riusata). R12 (Authentik
si riavvia da solo, si autoguarisce, non urgente) resta da investigare quando
c'è tempo.

DECISIONI GIÀ PRESE, non ridiscuterle:
- MASTER: applicazione automatica dopo che la validazione passa, ma il DIVIETO
  ASSOLUTO resta (Immich, distruzione dati, disattivare le guardie). Può creare
  tutto e cancellare le robe che crea lui.
- Repo GitHub in Obsidian: divisione PER TIPO — documentazione e README nel
  vault (fatto per questo repo, 31/7), codice sorgente sui database (non
  ancora fatto — punto 17/18 del piano generale).
- Il vault sui database: i dati stanno sul server una volta sola, ogni
  dispositivo li legge dal vivo dentro rete o VPN. Niente replica.
- Fusione con hermes-agent: fork minimo con registro delle divergenze, non fork
  completo. Se serve toccare altro si tocca, ma ogni riga va scritta.
- Il vault vero e unico è C:\Users\Mohamed\Documents\VaultMohamed\VaultMohamed\
  — l'altra cartella C:\Users\Mohamed\VaultMohamed non è nell'elenco di
  Obsidian, è un residuo, non ci si scrive.
- Niente ElevenLabs: Faster-Whisper + Piper/XTTSv2, tutto in locale.
- Contenuti creati da Momo: niente volti, esseri viventi, musica. Testo, voce
  sintetica, immagini di oggetti/luoghi/diagrammi, montaggio.
```

---

## 2. Perché il prompt dice queste cose

### 2.1 L'ordine di lettura è cambiato di nuovo
`PIANO_GENERALE.md` ha preso il posto di `ORDINE_DEI_LAVORI.md` come fila di
lavoro perché quest'ultimo, pur corretto nel criterio, non conteneva undici
voci reali trovate rileggendo quattro sessioni archiviate e i file di memoria.
La regola del progetto — «se non è in tabella, è dimenticato» — vale anche per
i documenti che la scrivono.

### 2.2 Perché la nota anti-conflitto in cima
Il 31 luglio due sessioni hanno lavorato sullo stesso checkout in parallelo:
una ha costruito il Guardrail e smantellato Open WebUI (poi lasciato non
committato per un momento), l'altra ha trovato quel lavoro non committato, lo
ha **verificato sul vivo prima di fidarsi** ("un documento che dice rimosso
non è una prova"), lo ha committato, e ha proseguito con `PIANO_GENERALE.md`.
Nessun danno, ma è stato un colpo di fortuna nell'ordine delle operazioni, non
un meccanismo che lo garantisce. Chi apre una sessione nuova sullo stesso
percorso deve saperlo.

### 2.3 I difetti chiusi il 31 luglio, che il prompt nomina apposta

| Difetto | Perché è nel prompt |
|---|---|
| Uno strumento di scrittura **fallito contava come riuscito** | «ho mandato la mail» restava senza nota anche quando lo strumento aveva rifiutato — nell'Hermes vivo, non solo in Momo |
| Un verbo troppo generico (`registrat`) nella guardia anti-bugia | accusava frasi oneste di una bugia mai detta, trovato dal vivo su `/api/chat`, non nei test scritti a tavolino |
| Gli strumenti di memoria di Momo bypassavano il filtro privato/pubblico | visibili (non eseguibili) a un motore esterno — `hermes-agent` non passa gli strumenti del `MemoryProvider` dallo stesso `check_fn` degli altri |
| Open WebUI con iscrizione libera aperta | trovato valutando se il servizio serviva ancora — nessun admin mai rivendicato, chiunque sulla VPN poteva diventarlo |
| `require_valid_user` di CouchDB sparito durante un `--force-recreate` | non era persistito in nessun volume né in git: vive nel layer scrivibile e sparisce in silenzio. Il container ripartiva `healthy` e sembrava tutto a posto |
| Un task di Windows che sembrava registrato e non lo era | il file XML esisteva, il documento diceva «attivo», ma `Get-ScheduledTask` non lo trovava. Causa: un `--` proibito in un commento XML, più `schtasks.exe`/`Register-ScheduledTask -Xml` ostili sull'encoding anche dopo la correzione |

### 2.4 Un difetto noto e NON risolto, che va detto a chi riprende
Il `REVOKE UPDATE, DELETE` su `master_log` **non morde**: il ruolo `hermes` di
Postgres è superuser e i superuser scavalcano i permessi. La garanzia che
regge oggi è architetturale (nessun percorso nel codice che scriva su quella
tabella), non del database. Non risolto, va detto e non nascosto.

### 2.5 Cosa NON mettere nel prompt
- Nessun segreto: né chiavi API, né token, né password. L'indice dei percorsi
  sta in `ESPOSIZIONE_E_SEGRETI.md` §4, e i valori restano su disco a 0600.
- Nessuna promessa non verificata: se una cosa è «da fare», il prompt lo dice.
  Il proprietario ha chiesto esplicitamente di sapere quello che non
  funziona, «anche se è colpa tua».
