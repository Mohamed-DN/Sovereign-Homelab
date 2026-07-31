# L'ordine dei lavori — tutto quello che c'è in ballo, e perché in questo ordine

> Scritto il 2026-07-30 su mandato del proprietario: *«metti tutte le idee nel
> flusso, sia le nuove che le vecchie, valuta tu con cosa partire prima e cosa
> dopo, architettale bene e poi parti»*.
>
> Questo documento non aggiunge idee: le **mette in fila**. Il dettaglio di
> ognuna sta nei piani già scritti, linkati riga per riga.

---

## Il criterio

Non «cosa è più bello», ma:

1. **Cosa sblocca cosa.** Un pezzo che rende possibile il resto viene prima,
   anche se è meno vistoso.
2. **Le guardie prima dei poteri.** Dare a un modello la facoltà di distruggere
   ambienti *prima* di poter verificare se mente sull'esito è l'ordine
   sbagliato. Questo impianto ha già pagato tre volte per crederci sulla parola.
3. **A parità, vince l'uso quotidiano.** Una cosa che il proprietario tocca
   ogni giorno batte una che userà una volta al mese.
4. **Misurare prima e dopo.** Ogni voce ha una verifica che si può eseguire,
   non un'opinione.

---

## Stato di partenza (fatto e verificato)

| | |
|---|---|
| Piano esecutivo W1-W5, W7.1 | PWA, catalogo modelli, fornitori+rotte, rubrica, pannello, MASTER con guardia host |
| Momo fase 1 | respira, isolato, sulla GPU del PC |
| Momo fase 2 | **una sola memoria** con l'Hermes vivo, provato |

---

## ONDATA 1 — Le fondamenta

*Senza queste, tutto il resto è più lento, più fragile o più pericoloso.*

### 1.0 · ✅ **FATTO (2026-07-30): 16 → 32 core a LXC 102 — 14 volte più veloce**

Osservazione del proprietario, e aveva ragione: *«se qualcosa soffre sulla CPU
aumenta i core a quel servizio, ci sono un casino di core liberi»*.

**Lo stato di partenza**: 40 core sul nodo, **carico medio 1.00** — il nodo era
praticamente fermo mentre LXC 102 (Hermes, Momo, Ollama, i tre database, 20
app) si strozzava su 16.

**Misurato prima e dopo**, stesso modello, stessa frase, a modello già caricato:

| | embedding sulla CPU del server |
|---|---|
| con 16 core | **3 677 ms** |
| con 32 core | **264 ms** |

**Quattordici volte più veloce.** E il confronto che conta davvero: la GPU del
PC fa lo stesso lavoro in 97 ms, quindi la CPU del server è passata da
**37× più lenta** a **2,7× più lenta**. La «corsia lenta» ha smesso di essere
lenta.

Dettaglio tecnico: `pct set 102 --cores 32` aggiorna il cgroup **a caldo**
(`cpuset.cpus.effective` diventa `2-31,38-39`), ma i processi già avviati
tengono i thread creati quando i core erano 16 — **Ollama va riavviato**,
altrimenti il numero non cambia e sembra che l'intervento non abbia funzionato.
Nei container i core sono condivisi, non riservati come nelle VM: alzarli non
toglie niente a nessuno finché non c'è contesa reale.

*Verificato dopo*: Hermes `active`, `/health` 200, i tre database `healthy`,
2013 vettori, carico del nodo 2.44 su 40 core.

### 1.1 · La GPU del server (T600, 4 GB) ⏱ ~1 ora — **meno urgente di prima**

> **Rivalutato il 2026-07-30 dopo §1.0.** Con l'embedding sceso a 264 ms sulla
> CPU, questa voce **non è più una fondamenta: è un miglioramento**. Restava
> prima in classifica quando la corsia lenta costava 3,7 secondi; ora che ne
> costa 0,26 il guadagno atteso è molto minore, e il costo (driver sul nodo,
> passthrough, rischio su un hypervisor che regge otto macchine) è lo stesso.
> **Spostata dopo l'ondata 2.** Un dato misurato batte una priorità scritta il
> giorno prima.
**Perché prima di tutto**: è l'unica voce che rende **ogni altra cosa migliore**
senza dipendere da niente. Oggi, a PC spento, ogni risposta e ogni embedding
vanno sulla CPU (misurato: 18 s contro 97 ms). Con la T600 la corsia lenta
sparisce, e la domanda «uso API esterne quando il PC è spento?» perde quasi
tutta la sua urgenza.
**Scoperta il 2026-07-30**: la scheda c'è, `nvidia-smi` non è nemmeno
installato — **non la usa niente**.
*Verifica*: `qwen3.5:4b` risponde dalla GPU del server, misurato prima e dopo.
→ [PIANO_MOMO_DIGITAL_TWIN](PIANO_MOMO_DIGITAL_TWIN.md) §3-bis

### 1.2 · Momo, le mani (fase 3) ⏱ ~2 ore
I 23 strumenti come plugin: vault Obsidian (lettura **e scrittura**), stato
dell'impianto, accessi, email, web, procedure.
**Perché qui**: fino a questo punto Momo sa e ricorda, ma non *fa*.
*Verifica*: legge una nota, riferisce lo stato reale di un servizio, manda una
mail a un contatto in rubrica.
→ [PIANO_AGENT_MOMO](PIANO_AGENT_MOMO.md) §4

### 1.3 · Momo, le guardie (fase 4) + il **Guardrail** ⏱ ~3 ore
Filtro privato/non-privato, filtro per ruolo, le due guardie anti-bugia, e
MASTER con il divieto assoluto. Più il **Guardrail** del documento nuovo: il
testo generato confrontato con i **log veri**.
**Perché immediatamente dopo le mani, e prima di ogni altra cosa**: è il pezzo
che questo progetto ha imparato a proprie spese. Oggi stesso Hermes ha prodotto
un report tecnico dettagliato su una mail mai inviata.
**Regola prima, modello poi**: «il testo dice *ho mandato* ma nessun tool di
invio è stato chiamato» è deterministico, non costa VRAM e **non può mentire a
sua volta**. L'LLM interviene solo su ciò che la regola non copre.
*Verifica*: le stesse prove passate dall'Hermes attuale, tutte. Un motore non
privato riceve 2 strumenti su N e non sa che MASTER esiste. `qm stop 110`
rifiutato.
→ [PIANO_AGENT_MOMO](PIANO_AGENT_MOMO.md) §4 · [PIANO_MOMO_DIGITAL_TWIN](PIANO_MOMO_DIGITAL_TWIN.md) §2

---

## ONDATA 2 — Quello che si usa ogni giorno

### 2.1 · Più conversazioni, una sola memoria ⏱ ~2 ore
Difetto trovato dal proprietario provando: *«valutava solo la nuova domanda
scordandosi del filo logico»*. La cronologia esiste ma è **una sola per
persona**, quindi argomenti diversi si contaminano.
**Perché qui**: si tocca ogni volta che si apre una chat, ed è il primo
difetto che il proprietario ha notato da solo.
**Perché è facile adesso**: hermes-agent ha già le sessioni, e il nostro
`MemoryProvider` riceve già `session_id`.
*Verifica*: due chat aperte su argomenti diversi non si mescolano, ma un fatto
detto in una lo sa anche l'altra.

### 2.2 · Telegram ⏱ ~2 ore
Bot `@dn_momo_bot` e token già pronti dal 2026-07-30. Oggi non risponde perché
**non è collegato a niente**: un bot è una casella vuota finché un programma
non ascolta.
**Il vincolo che non si tocca**: mappatura `id Telegram → utente di casa`
compilata a mano, sconosciuti rifiutati. Un id di Telegram non è un'identità.
*Verifica*: da un id mappato arriva la risposta di Momo con i **suoi**
permessi; da uno sconosciuto, un rifiuto.

### 2.3 · La voce, tutta in casa ⏱ ~4 ore
Registratore in pagina, **Faster-Whisper** per capire, **XTTSv2** per parlare
con la voce del proprietario. **Deciso il 2026-07-30: niente ElevenLabs**, la
sua voce non esce dall'impianto.
*Verifica*: dall'iPhone, dall'icona sulla home, tenere premuto, parlare, e
ricevere una risposta letta ad alta voce.

---

## ONDATA 3 — La potenza (dopo che le guardie reggono)

### 3.1 · Tool statistici (ARIMA e simili) ⏱ ~2 ore
I numeri non li fa il modello: **un LLM non calcola, stima**, e una stima
presentata come calcolo è una bugia con i decimali. Chiude anche A6 di Nexi
(previsione del riempimento dischi).
**Perché prima della libreria e delle sandbox**: è piccolo, isolato, e non può
rompere niente.

### 3.2 · Automation Library ⏱ ~3 ore
Qdrant per cercare **lo scopo** di uno script, Postgres `JSONB` per il
**payload** vero. Stessa divisione già usata per le procedure.

### 3.3 · Sandbox con ciclo di vita ⏱ ~4 ore
Creare, testare, **distruggere**. Non prima del Guardrail: distruggere
ambienti senza poter verificare l'esito di un test è il momento sbagliato per
scoprire una bugia.
**La regola che concilia con il divieto assoluto**, dalle parole del
proprietario (*«può cancellare le robe che lui crea»*): l'orchestratore Python
tiene il **registro di ciò che ha creato** e passa al teardown solo
identificatori presi da lì, mai un nome costruito dal modello. La guardia
sull'host resta l'ultima parola.

### 3.4 · Squadra a grafo ⏱ ~3 ore
Il flusso scende e risale: un dev può rimandare in alto, o passare a un altro
ruolo, e decide lui.
**Tre freni obbligatori prima di scrivere una riga**: tetto ai salti,
rilevamento dei cicli, e i 13 ruoli mantenuti nel nostro plugin
(`delegate_task` di hermes-agent ne conosce due).

### 3.5 · Il Sinker completo (4 fasi) ⏱ ~4 ore
Sink → Compute → Surface → Guardrail. Da fare **dopo** la GPU del server
(§1.1), perché tre chiamate LLM su CPU sono inusabili.
**Con la via breve**: quando la GPU non c'è, si degrada a Surface + Guardrail
invece di far aspettare un minuto.

---

## ONDATA 4 — La conoscenza

### 4.1 · I dieci repository ⏱ ~3 ore
Misurati: 12,7 MB di testo in 2 683 file. **Divisione decisa**: documentazione
e README **nel vault** (leggeri, tutti i plugin Obsidian funzionano, offline
funziona); codice sorgente **sui database** (nessun peso sul telefono).

### 4.2 · Il plugin Obsidian che legge dai database ⏱ ~5 ore
I dati stanno sul server una volta sola, ogni dispositivo li legge dal vivo.
**Due verifiche aperte prima di scrivere**: `requestUrl` su Obsidian iOS, e il
fatto che `.obsidian` non si sincronizza (plugin da installare a mano su ogni
dispositivo).

### 4.3 · Google Calendar ⏱ ~3 ore
Appuntamenti sul calendario vero, non solo nell'agenda interna. Serve OAuth.

### 4.4 · Studiare gli agenti di Ruflo ⏱ ~2 ore
Con lo stesso metodo usato per hermes-agent: **leggere il codice**, non le note
di rilascio, e riferire cosa regge davvero.

---

## Quello che non è in nessuna ondata, e perché

- **Apprendimento continuo (download automatico)**: da far passare dalle stesse
  guardie di `web_fetch` (rifiuto degli indirizzi interni, difesa SSRF). Va
  dopo il Guardrail, non prima.
- **Doppio RAG (astrazione in JSON)**: è dentro il Sinker (§3.5), non separato.
- **Ceph che gira a vuoto sull'host**: decisione ancora del proprietario
  ([VISIONE_COMPLETA](VISIONE_COMPLETA.md) §8.1), non un lavoro.

---

## Si comincia da 1.1

La GPU del server: un'ora, e ogni cosa dopo gira meglio.
