# Prompt per una sessione nuova

> Aggiornato il 2026-07-31. **Copia il blocco del §1 come primo messaggio della
> nuova sessione.** Il §2 spiega perché il prompt dice quelle cose.

---

## 1. Il blocco da copiare

```text
Lavoriamo sul Sovereign Homelab, la mia infrastruttura di casa.
Repository locale: c:\DBA\Sovereign-Homelab (git, branch main, si committa e si
pusha su main). Su GitHub: https://github.com/Mohamed-DN/Sovereign-Homelab

LEGGI IN QUEST'ORDINE, prima di toccare qualunque cosa:
 1. docs/00_overview/ORDINE_DEI_LAVORI.md  <- DA QUI SI COMINCIA: tutto quello
    che c'è in ballo, in fila, con il criterio che decide l'ordine e la verifica
    di ogni voce.
 2. docs/00_overview/VISIONE_COMPLETA.md   <- il perché di tutto, i tre principi
    e le QUINDICI TRAPPOLE GIÀ PAGATE (§6). Ripagarle costa ore: leggile.
 3. docs/00_overview/PIANO_MASTER.md       <- l'indice di tutto e lo stato di
    ogni cosa. Regola scritta dentro: se una cosa non è in quella tabella, è
    stata dimenticata.
 4. docs/00_overview/PIANO_AGENT_MOMO.md   <- la fusione del nostro Hermes con
    hermes-agent di NousResearch. Fasi 1-4 fatte e verificate.
 5. docs/00_overview/PIANO_MOMO_DIGITAL_TWIN.md <- cosa Momo deve saper fare:
    Sinker a 4 fasi, Guardrail, automation library, sandbox, squadra a grafo.
 6. docs/04_apps/hermes.md e docs/04_apps/hermes-memoria.md <- i runbook del
    servizio e della sua memoria.
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
  LXC 102 = .52   Hermes:8093 · MOMO (/opt/momo) · CouchDB · Ollama ·
                  OmniRoute · Postgres/Qdrant/Valkey (solo loopback) · 20 app
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
  troubleshooting, sorgenti.
- Non indovinare su cose che posso dirti io: chiedimi.
- Su Authentik: se un provider non va, confronta campo per campo con uno che
  funziona. Non un campo alla volta.
- Commenti in inglese, messaggi a me in italiano, Python di sola libreria
  standard (unica eccezione dichiarata: python3-psycopg2 da apt).
- Il JavaScript scritto dentro una stringa Python va verificato con un parser
  VERO (node --check), non a occhio: py_compile valida solo il Python e lascia
  passare uno <script> rotto. È già costato un pannello vuoto in produzione.

DOVE SIAMO (31 luglio 2026):
Hermes è vivo su https://hermes.internal, con memoria fuori dal modello
(Postgres+Qdrant+Valkey), 2013 vettori fra vault Obsidian e runbook, e quattro
motori fra cui Groq e AWS Bedrock.
Il piano esecutivo è FINITO: PWA installabile su iPhone, catalogo modelli
scaricabili dal pannello, preset fornitori + router per intenti, rubrica email,
pannello a schede, modalità MASTER con chiave SSH dedicata e guardia sull'host
(29 casi di sicurezza verificati uno per uno).
AGENT MOMO (fusione con hermes-agent 0.19.0, in /opt/momo su LXC 102):
  fase 1 OK  respira, isolato, sulla GPU del PC
  fase 2 OK  UNA SOLA MEMORIA con l'Hermes vivo: provato che un fatto salvato
             da Momo lo rilegge Hermes
  fasi 3+4 OK  11 strumenti con la guardia privato/non-privato attaccata:
             provato che con Groq riceve 2 strumenti su 11 e i privati sono
             bloccati anche invocandoli a forza
Prestazioni: LXC 102 portato da 16 a 32 core, l'embedding sulla CPU del server
è passato da 3677 ms a 264 ms (14 volte).

COSA DEVI FARE: segui docs/00_overview/ORDINE_DEI_LAVORI.md.
Il prossimo passo è il GUARDRAIL: la difesa anti-bugia dentro Momo, con la
regola deterministica prima e il modello solo per ciò che la regola non copre —
una regola non mente a sua volta e non costa VRAM.
Poi: più chat con memoria centrale (oggi la cronologia è UNA SOLA per persona e
gli argomenti si mescolano), Telegram (bot @dn_momo_bot e token già pronti, non
ancora collegati), voce TUTTA in locale (Faster-Whisper + XTTSv2, NIENTE
ElevenLabs: la mia voce non esce di casa).

DECISIONI GIÀ PRESE, non ridiscuterle:
- MASTER: applicazione automatica dopo che la validazione passa, ma il DIVIETO
  ASSOLUTO resta (Immich, distruzione dati, disattivare le guardie). Può creare
  tutto e cancellare le robe che crea lui.
- Repo GitHub in Obsidian: divisione PER TIPO — documentazione e README nel
  vault (leggeri, tutti i plugin Obsidian funzionano), codice sorgente sui
  database (nessun peso sul telefono). Misurati: 12,7 MB di testo, 2683 file,
  10 repo.
- Il vault sui database: i dati stanno sul server una volta sola, ogni
  dispositivo li legge dal vivo dentro rete o VPN. Niente replica.
- Fusione con hermes-agent: fork minimo con registro delle divergenze, non fork
  completo. Se serve toccare altro si tocca, ma ogni riga va scritta.
```

---

## 2. Perché il prompt dice queste cose

### 2.1 L'ordine di lettura è cambiato
Prima si partiva da `VISIONE_COMPLETA`. Ora si parte da `ORDINE_DEI_LAVORI`,
perché i piani sono diventati cinque e senza una fila davanti si finisce a
scegliere il pezzo più vistoso invece di quello che sblocca il resto.

### 2.2 I difetti chiusi il 2026-07-30, che il prompt nomina apposta

| Difetto | Perché è nel prompt |
|---|---|
| `\n` nel JS dentro una tripla-stringa Python | il pannello sembrava **vuoto**, in silenzio: uno `<script>` che fallisce al parse non dà errore. Trovato dal proprietario, non dai miei controlli |
| Guardia anti-bugia **spenta nello sciame** | `tools=[]` per la sintesi azzerava anche la variabile che la guardia leggeva. Causa di un report tecnico dettagliato su una mail mai inviata |
| `rm -rf` che passava | `run_action_command` mandava via SSH solo `pct`/`qm`: tutto il resto girava localmente **senza** guardia. Chiuso spostando il controllo *dentro* l'esecutore |
| Provider sotto `model.provider` | leggendo la chiave sbagliata la guardia falliva **chiuso**: vault protetto ma ogni strumento di casa spariva, e la causa era invisibile |
| `pct set --cores` non basta | il cgroup si aggiorna a caldo, ma i processi già avviati tengono i vecchi thread: **Ollama va riavviato** |

### 2.3 Un difetto noto e NON risolto, che va detto a chi riprende

Il `REVOKE UPDATE, DELETE` su `master_log` **non morde**: il ruolo `hermes` di
Postgres è superuser (`rolsuper = t`), e i superuser scavalcano i permessi.
Verificato: un `UPDATE` sul registro riesce.

La garanzia che regge oggi è **architetturale**, non del database: nel codice
non esiste **nessun percorso** che aggiorni o cancelli quella tabella, nemmeno
uno protetto da un flag. Sistemarlo davvero richiede un ruolo Postgres separato
e non superuser per l'applicazione — lavoro non fatto, e va detto invece di
lasciar credere che il `REVOKE` protegga.

### 2.4 Cosa NON mettere nel prompt
- Nessun segreto: né chiavi API, né token, né password. L'indice dei percorsi
  sta in `ESPOSIZIONE_E_SEGRETI.md` §4, e i valori restano su disco a 0600.
- Nessuna promessa non verificata: se una cosa è «da fare», il prompt lo dice.
  Il proprietario ha chiesto esplicitamente di sapere quello che non funziona,
  «anche se è colpa tua».
