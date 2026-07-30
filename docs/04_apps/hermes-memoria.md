# La memoria di Hermes — quello che resta quando il modello cambia

> **Stato (2026-07-30): LIVE e verificata.** Tre archivi su LXC 102, tutti su
> `127.0.0.1`. Il test di accettazione del piano è passato: gli ho detto un
> fatto, ho riavviato il servizio, ho cancellato la conversazione, e se lo
> ricordava ancora.

---

## 1. Architettura: perché tre archivi e non uno — *purpose & architecture*

| Archivio | Cosa tiene | Perché proprio lui |
|---|---|---|
| **PostgreSQL 16** | fatti, agenda, registro, rubrica | I dati sono relazionali e il proprietario è DBA: può interrogarli con SQL senza chiedere niente a nessuno |
| **Qdrant 1.18** | i vettori, cioè il significato | «cosa mi aveva detto Luna sul lavoro?» non si risolve con `LIKE`. È anche la cura del difetto della ricerca nel vault |
| **Valkey 9.1** | cache degli embedding | Ogni ricerca vettorizza la domanda. Sul server quel calcolo costa 18 secondi: rifarlo due volte per la stessa frase è spreco puro |

```
Hermes (systemd, LXC 102)
   │
   ├── 127.0.0.1:5432  Postgres   facts · agenda · memory_log · vector_index · contacts
   ├── 127.0.0.1:6333  Qdrant     collezione "hermes_knowledge" (768 dim, Cosine)
   └── 127.0.0.1:6379  Valkey     emb:<sha256>  → vettore, 30 giorni
                │
                └── embedding: PC 192.168.1.100 (GPU) → server 127.0.0.1 (CPU)
```

Nessuna delle tre porte è raggiungibile dalla rete di casa: Hermes gira sullo
stesso container e gli basta il loopback. Chi ha i dati personali non ha bisogno
di stare in ascolto sulla LAN.

## 2. Che forma ha un ricordo

Ogni voce porta **quando** l'ha imparata e **da dove viene**:

- `source = 'detto'` → l'utente l'ha detto;
- `source = 'dedotto'` → Hermes l'ha capito da solo, e nel prompt compare
  marcato come *non confermato*.

E ogni voce ha un **proprietario**. La casa ha più di un utente: un fatto su
Luna non è un fatto di Mohamed, e la memoria di un utente non è leggibile da un
altro. Il campo `owner` è la chiave di tutto.

> **`dimentica` cancella per davvero.** Il registro conserva che un ricordo è
> stato dimenticato e di chi parlava, **mai il suo contenuto**. Una memoria che
> si può resuscitare non è dimenticata, e dire il contrario sarebbe una bugia.

## 3. Gli strumenti

| Strumento | Chi può usarlo | Cosa fa |
|---|---|---|
| `ricorda` | tutti | Salva un fatto. Accetta soggetto, tipo e origine |
| `ricorda_cerca` | tutti | Cerca per significato fra i propri fatti; per il proprietario anche fra le note Obsidian |
| `dimentica` | tutti | Cancella, senza possibilità di recupero |
| `agenda_aggiungi` | tutti | Un impegno con data e ora |
| `agenda_leggi` | tutti | Gli impegni in arrivo |
| `rubrica_aggiungi` | solo proprietario | Aggiunge o aggiorna una persona (nome, email, nota) — W4 |
| `rubrica_cerca` | solo proprietario | Cerca per nome o email esatta — usata anche da `send_mail` per risolvere un `destinatario` |
| `rubrica_elenco` | solo proprietario | Elenca la rubrica |

Sono tutti in `PRIVATE_TOOLS`: un motore esterno non li vede nemmeno. La
memoria è la cosa più personale che Hermes possiede e non esce di casa.

### La memoria non aspetta di essere interrogata

A ogni messaggio, il prompt di sistema riceve un riassunto: gli ultimi 12 fatti
e gli impegni dei prossimi 10 giorni. Senza questo gli strumenti funzionerebbero
ma la memoria non *sembrerebbe* memoria — il modello dovrebbe pensare di
chiedere. Costa una query.

## 4. Due bugie che il modello raccontava, e come sono state chiuse

Questa è la parte che vale la pena leggere.

### «Ho aggiornato la memoria» — con il database vuoto

Alla frase *«Ricordati che la mia macchina è una Golf grigia targata FT491ZK e
che il mio gatto si chiama Pixel»*, `qwen3.5:9b` ha risposto:

> «Ho salvato: **Macchina**: Golf grigia, targa `FT491ZK`. **Gatto**: Pixel.»

Nel database: **niente**. Il registro d'audit non riportava nessuna chiamata.
Non un errore: una frase convincente. Esattamente il difetto già annotato nel
piano — *uno strumento che sbaglia non dà errore, racconta una bugia sicura di
sé*.

Sono state messe due difese, in serie.

**Prima: gli ordini espliciti li esegue il codice.** Se il messaggio comincia
con «ricordati che», «memorizza», «segnati», «non dimenticare che»… il fatto
viene salvato dal server **prima** che il modello parli, e al modello si dice
che è già fatto. È la stessa scelta già presa per la ricerca web: su
un'istruzione diretta non si lascia decidere a un modello da 9 miliardi di
parametri se eseguirla.

**Seconda: la pretesa viene verificata.** Se la risposta contiene una frase del
tipo «ho salvato / ho segnato / ho aggiornato la memoria» e **nessuno** strumento
di scrittura è stato eseguito in quel giro, Hermes rimanda il modello indietro
con l'evidenza («non hai chiamato niente, il database è vuoto su questo punto»)
e gli dà un altro tentativo. Se anche il secondo giro non chiama nulla, la
risposta arriva all'utente con una nota in chiaro:

> **Non ho salvato niente.** Ho detto di averlo fatto ma non ho usato lo
> strumento della memoria, e me ne sono accorto dopo.

La seconda difesa è nata da un fallimento della prima versione: il rilevatore
cercava «ho salvato» e il modello ha risposto «ho **aggiornato la memoria**»,
passando indenne. Un elenco di frasi è per costruzione incompleto — per questo
la difesa vera è la prima, deterministica, e questa è la rete.

### L'agenda sbagliava di due ore

`pct exec 102 -- date` → **UTC**. Il container non è sul fuso di casa, quindi
«domani alle 10:30» diventava 10:30 UTC, cioè **12:30** per chi l'aveva detto.
Lo stesso difetto colpiva `now_stamp()`: a ogni messaggio Hermes dichiarava al
modello un'ora sbagliata di due ore, da sempre.

Il fuso ora è **dichiarato nel codice** (`Europe/Rome`), non ereditato da dove
il processo gira, e ogni data letta dal database viene riportata in quel fuso
prima di finire sotto gli occhi di qualcuno.

## 4-bis. Cosa c'è dentro l'indice, e perché è spezzato

L'indice non contiene solo i fatti. Tre origini, filtrate per proprietario:

| Origine | Cosa | Chi la vede |
|---|---|---|
| `fatto` | i ricordi salvati con `ricorda` | solo il suo proprietario |
| `vault` | le note Obsidian | solo il proprietario del vault |
| `runbook` | **la documentazione di questo repository** | tutti |

L'origine `runbook` è l'idea presa da Nexi DBA AI, che davanti a un allarme
chiede *«l'abbiamo già visto? qual è la procedura?»*. Qui i runbook esistevano
già ed erano buoni: semplicemente Hermes non li leggeva. Adesso a *«cosa fare se
Immich perde le foto»* risponde con
`docs/05_backup_dr/IMMICH_RECOVERY_RUNBOOK.md` (somiglianza 0.615) e con il
pezzo giusto — quello che dice di non cancellare gli originali dal telefono
finché due ripristini indipendenti non sono riusciti.

Il repository sta su LXC 102 in `/opt/sovereign-repo`, **non** in
`/opt/sovereign-homelab`: là ci sono i file `.env` con i segreti in uso, e un
`git pull` sopra non è una cosa da fare. Il timer notturno aggiorna il clone
prima di indicizzare, così l'indice riflette la procedura di oggi.

### Spezzato, non troncato

La prima versione vettorizzava il documento **troncato a 4000 caratteri**: la
coda di una nota lunga era irraggiungibile. Difetto mio, trovato leggendo il
`TextChunker` del loro repository.

Ora ogni documento viene diviso in pezzi da 1000 caratteri con 200 di
sovrapposizione, tagliando su un separatore (paragrafo, riga, punto, spazio) e
solo in ultima istanza a metà parola. La sovrapposizione serve perché una frase
spezzata fra due pezzi resti cercabile in almeno uno dei due.

| | Documenti | Punti nell'indice |
|---|---|---|
| Vault | 125 note | **601 pezzi** |
| Repository | 102 documenti | **1227 pezzi** |

La ricerca chiede tre volte i risultati che servono e poi accorpa i pezzi dello
stesso documento, tenendo il migliore: altrimenti una nota lunga occuperebbe
tutta la prima pagina con sé stessa. E mostra **il pezzo che ha corrisposto**,
non l'inizio del documento — se la risposta sta a pagina tre, l'intestazione non
serve a nessuno.

> **Attenzione per il futuro**: l'impronta salvata copre il *testo*, non il
> *modo* in cui è stato indicizzato. Cambiando lo spezzettamento i documenti
> risultano invariati e vengono saltati tutti, lasciando nell'indice i punti
> vecchi. Per questo esiste `--force`, ed è la prima cosa da usare quando si
> tocca `chunk_text`.

## 5. La ricerca nel vault, prima e dopo

Il difetto annotato: cercando «time garden» uscivano query Oracle piene di
`timestamp`, perché la ricerca contava le occorrenze delle parole.

Verifica dopo l'indicizzazione (125 note):

| Domanda | Prime risposte | Rumore Oracle |
|---|---|---|
| «time garden» | `00 Dashboard/Welcome.md` (0.501), `07 Notes/Extras/A secret garden within the garden.md` (0.438) | **nessuno** |
| «cosa ho scritto su Oracle Data Guard» | `enel_exadata_migration_analysis.md` (0.606), `Migrazione, Cifratura TDE e Configurazione Data Guard.md` (0.594) | pertinente |
| «privacy delle foto di mia sorella» | il fatto su Luna (0.542), che non contiene né «privacy» né «sorella» | — |

L'ultima riga è quella che conta: ha trovato un ricordo **per significato**, con
zero parole in comune con la domanda.

La ricerca a parole non è stata buttata: resta come ripiego quando Qdrant o il
motore degli embedding non rispondono. Una ricerca degradata è meglio di nessuna
ricerca — ma la risposta dice sempre quale delle due ha usato.

## 6. Il costo degli embedding, misurato

Lo stesso modello (`embeddinggemma`, 307M, 768 dimensioni), la stessa frase:

| Dove | A modello caricato |
|---|---|
| PC · RTX 5070 Ti | **97 ms** |
| Server · CPU di LXC 102, con 4 core | 18 000 ms |
| Server · CPU di LXC 102, **con 16 core** | **3 600 ms** |

Non era un errore di misura: tre chiamate consecutive sul server davano 18,4 s ·
18,6 s · 17,7 s. **La causa era il numero di core**: LXC 102 ne aveva 4 su 40
disponibili sull'host, e su quei 4 girano 23 container, Ollama, Hermes e tre
database. Portato a 16, lo stesso embedding costa 3,6 s — cinque volte meno. La
misura completa, da 4 a 20 core, è in
[ANALISI_CARICO_2026-07-30](../01_proxmox_foundation/ANALISI_CARICO_2026-07-30.md) §2.

Le tre decisioni prese quando il numero era 18 secondi restano valide, perché
anche 3,6 s è 37 volte la GPU:

1. Il PC è il primo motore per gli embedding, il server è la corsia lenta che
   però non manca mai.
2. `keep_alive: 24h`, perché un caricamento a freddo costa ~20 s su entrambi e
   il default di 5 minuti lo farebbe pagare quasi a ogni ricerca.
3. La cache Valkey esiste soprattutto per risparmiare la corsia lenta.

Indicizzare 125 note è costato **32 secondi** in tutto, passando dalla GPU; i
102 documenti del repository, 186 secondi.

## 7. Install / deployment

```bash
# sull'host Proxmox, una volta sola: credenziali e file di connessione
/root/sovereign-hermes-memory-secrets.sh

# su LXC 102
cd /opt/sovereign-homelab/stacks/hermes-memory && docker compose up -d
docker exec -i hermes-postgres psql -U hermes -d hermes_memory -v ON_ERROR_STOP=1 \
  -f - < /opt/sovereign-hermes/memory-schema.sql

# il modello degli embedding, su entrambi i motori
docker exec ollama ollama pull embeddinggemma     # server
ollama pull embeddinggemma                        # PC

# il repository, da cui vengono indicizzati i runbook
git clone --depth 1 https://github.com/Mohamed-DN/Sovereign-Homelab.git /opt/sovereign-repo

# prima indicizzazione
cd /opt/sovereign-hermes
python3 sovereign-hermes.py --index-repo      # 102 documenti -> 1227 pezzi, 186 s
python3 sovereign-hermes.py --index-vault     # 125 note      ->  601 pezzi,  92 s
systemctl enable --now sovereign-hermes-index-vault.timer

# quando cambia il MODO di indicizzare (non i documenti)
python3 sovereign-hermes.py --index-vault --force
```

Lo script dei segreti è **idempotente per necessità**: rigenerare la password di
Postgres dopo l'`initdb` chiuderebbe Hermes fuori dalla propria memoria, perché
`POSTGRES_PASSWORD` ha effetto solo su una directory dati vuota.

### Una dipendenza fuori dalla regola, dichiarata

La regola del progetto è «Python di sola libreria standard». Postgres però
richiede un driver, e l'alternativa era implementare a mano il protocollo di rete
di Postgres, autenticazione SCRAM compresa. È stato installato
**`python3-psycopg2` dall'archivio Debian** (non da pip): pacchettizzato,
aggiornato con il sistema operativo, nessun ambiente virtuale.

Tutte le chiamate a Postgres stanno in un solo modulo,
`scripts/hermes/hermes_memory.py`, quindi cambiare idea significa toccare un
file. **Se il proprietario preferisce la regola alla comodità, si dica e si
cambia** — Qdrant e Valkey sono già parlati con la sola libreria standard.

## 8. Target & sizing

| Voce | Valore |
|---|---|
| **Target host** | LXC 102 (`apps-light`, 192.168.1.52) |
| **Postgres** | ~30 MB a riposo. I fatti sono testo: mille ricordi stanno in pochi MB |
| **Qdrant** | ~120 MB con 125 punti. Un vettore da 768 float pesa ~3 KB |
| **Valkey** | tetto a 256 MB, politica `allkeys-lru`: quando è pieno butta il più vecchio invece di rifiutare scritture |
| **Modello embedding** | 680 MB in RAM sul server, residente per 24h |

## 9. DNS / domain names / alias

Nessuno. I tre archivi sono raggiungibili solo dal loopback di LXC 102 e non
hanno interfaccia web da pubblicare. Se un giorno servisse la console di Qdrant,
va pubblicata come `qdrant.internal` dietro SSO — non aprendo la porta.

## 10. Nginx Proxy Manager (NPM)

Nessun host. Volutamente: vedi sopra.

## 11. Homepage & Uptime Kuma

- **Homepage**: niente tessera, non sono servizi con una pagina.
- **Uptime Kuma**: il monitor utile non è sulle porte ma sullo stato che Hermes
  già espone. `https://hermes.internal/health` copre il servizio; per la memoria
  il controllo è `python3 sovereign-hermes.py --memory-status`, che risponde con
  Postgres, Qdrant, Valkey, embedding e i conteggi.

## 12. Backup & restore

| Elemento | Dove | Come si ripristina (*restore*) |
|---|---|---|
| Fatti e agenda | volume `hermes-memory_hermes_pg_data` | coperto dal backup PBS di LXC 102. Per un dump applicativo: `docker exec hermes-postgres pg_dump -U hermes hermes_memory` |
| Vettori | volume `hermes-memory_hermes_qdrant_data` | **ricostruibili**: sono derivati. `--index-vault` li rifà, i fatti li reindicizza `ricorda` |
| Cache | volume `hermes-memory_hermes_valkey_data` | da buttare senza pensarci: è una cache |
| Credenziali | `/root/sovereign-secrets/hermes-memory/` sull'host Proxmox | **non rigenerare**: la password di Postgres è quella dell'initdb |

La distinzione che conta: **Postgres è la verità, Qdrant è un indice.** Perdere
Qdrant costa 32 secondi di ricalcolo; perdere Postgres perde i ricordi.

## 13. Verifica di funzionamento

```bash
# i tre archivi
pct exec 102 -- docker ps --filter name=hermes- --format '{{.Names}} {{.Status}}'

# lo stato completo, con i conteggi e il tempo di un embedding
pct exec 102 -- bash -lc 'cd /opt/sovereign-hermes && python3 sovereign-hermes.py --memory-status'

# le porte NON devono rispondere dalla rete
pct exec 101 -- curl -s -m 5 http://192.168.1.52:6333/collections   # deve fallire

# il test di accettazione, per intero
#  1. «ricordati che ...»   2. systemctl restart sovereign-hermes
#  3. rm /var/lib/sovereign-hermes/chats/<utente>.json
#  4. «cosa ti avevo detto?»  -> deve saperlo
```

## 14. Troubleshooting e Rollback

| Problema | Rimedio |
|---|---|
| «La memoria non è disponibile» | manca `/root/sovereign-secrets/hermes/memory-postgres-dsn`, o Postgres è giù: `docker ps --filter name=hermes-postgres` |
| La ricerca risponde «modo: parole» | Qdrant o l'embedding non rispondono. Con il PC spento la prima ricerca può metterci ~20 s per caricare il modello sul server |
| Una ricerca ci mette qualche secondo | è la corsia lenta: il PC è spento e sta calcolando sulla CPU del server. Vedi §6 |
| Hermes dice di aver salvato e non l'ha fatto | la guardia deve aggiungere la nota «Non ho salvato niente». Se non compare, la frase usata dal modello non è fra quelle riconosciute: va aggiunta a `_CLAIM_PATTERNS` |
| Un impegno è all'ora sbagliata | controlla `HERMES_TZ` (default `Europe/Rome`) — il container gira su UTC |
| **Rollback** — togliere la memoria | `cd /opt/sovereign-homelab/stacks/hermes-memory && docker compose down`. Hermes riparte senza memoria e lo dice, non finge |

## 15. Official Sources

- PostgreSQL 16 — <https://www.postgresql.org/docs/16/>
- Qdrant — <https://qdrant.tech/documentation/>
- Valkey — <https://valkey.io/docs/>
- EmbeddingGemma — <https://ollama.com/library/embeddinggemma>
- API embed di Ollama — <https://docs.ollama.com/api#generate-embeddings>
