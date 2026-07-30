# Cosa prendere da Nexi DBA AI, e cosa lasciare lì

> Scritto il 2026-07-30, dopo aver letto
> [ThomasNexi/Nexi_DB_AI](https://github.com/ThomasNexi/Nexi_DB_AI) (branch `DN`,
> privato) e [Mohamed-DN/DB-AI](https://github.com/Mohamed-DN/DB-AI).
>
> **I due repository sono lo stesso sistema**: a parte due cartelle di scarto
> (`__pycache__`, `ops/logs`) la struttura è identica. `Nexi_DB_AI@DN` è la
> versione corrente — l'ultimo commit è *«Complete System Architecture: Auth DB,
> Grafana, Prophet, Langfuse, Sentinel Flow»*. Tutto quello che segue viene da
> lì; `DB-AI` non aggiunge niente.

---

## 1. Cos'è Nexi, in una riga

Un amministratore di database autonomo per una flotta Oracle/Postgres, costruito
su tre strati dichiarati: **Direttive** (le regole, scritte da persone) →
**Orchestrazione** (gli agenti che decidono *quando* agire) → **Esecuzione**
(script Python deterministici e API strette che toccano l'infrastruttura).

Quella separazione è la cosa più preziosa del repository, ed è esattamente il
disegno che manca alla **modalità master** di Hermes.

## 2. Da prendere — in ordine di quanto rendono

| # | Cosa | Perché qui | Costo | Stato |
|---|---|---|---|---|
| **A1** | **Spezzare i testi in pezzi sovrapposti** prima di vettorizzarli (`TextChunker`: 1000 caratteri, 200 di sovrapposizione, taglio su separatore) | Il mio indicizzatore vettorizza la nota **troncata a 4000 caratteri**: la coda di una nota lunga oggi è irraggiungibile. Difetto mio, trovato leggendo il loro codice | piccolo | ✅ fatto |
| **A2** | **RAG sui runbook**: indicizzare la documentazione del repository, non solo il vault | Il loro sistema, davanti a un allarme, chiede *«l'abbiamo già visto? qual è la procedura?»*. Qui i runbook esistono già e sono buoni: Hermes non li legge. Con questo, a «come si ripara Nextcloud» risponde citando il file | piccolo | ✅ fatto |
| **A3** | **Il Verificatore**: prima di allarmare, un secondo passaggio che confronta la previsione con lo stato reale e classifica `REAL_CRITICAL` / `REAL_WARNING` / `FALSE_ALARM` — **con una regola deterministica di riserva** quando l'LLM non risponde o risponde male | È la cura del 502 di Nextcloud che colora tutto di rosso una volta su quattro. E la regola di riserva è lo stesso principio già usato in casa: degradare, non mentire | medio | da fare |
| **A4** | **Interruttore globale**: uno stato `RUNNING` / `PAUSED` che **ogni** agente controlla prima di ogni giro. In pausa dorme, non muore | La Fase 6 chiede un «interruttore d'emergenza». Questo è più utile di `systemctl stop`: ferma le azioni lasciando vivo il servizio e la chat | piccolo | da fare |
| **A5** | **Elenco di azioni permesse** come dati, non come codice: ogni azione dichiara nome, comando, se è reversibile, se richiede conferma | È la Fase 6 per intero. Il loro strato «Esecuzione» è fatto così e funziona: l'LLM non compone comandi, **scelgli** da un elenco | medio | da fare |
| **A6** | **Previsione con Prophet/ARIMA** e punteggio di confidenza, soglie configurabili | Qui servirebbe per il riempimento dei dischi e la crescita dei backup: «`ssd_pool` piena fra 40 giorni» vale più di «`ssd_pool` al 26%». `ssd_pool` è al 26% con 1,29 TB liberi, quindi non è urgente — ma la crescita di Immich non è lineare | medio | valutare |
| **A7** | **Langfuse** per le tracce degli agenti | Difetto noto: «gli strumenti dei sotto-agenti non sono visibili in pagina». Questo lo risolve davvero, e per un servizio che sbaglia di nascosto vedere le chiamate è la differenza fra fidarsi e sperare | medio | da fare |
| **A8** | **Una sezione «Edge Cases» in ogni runbook** (nelle loro `docs/directives`, ogni capacità ha Goal / Inputs / Outputs / Tools / Edge Cases / API) | I nostri runbook hanno già Troubleshooting e Rollback. Manca la domanda «cosa succede se va a metà» scritta *prima* | piccolo | da fare |
| **A9** | **Code degli eventi su Valkey**: gli agenti scrivono in coda, dei worker consumano | Valkey adesso c'è. Serve solo quando ci saranno i controlli programmati (Fase 7): oggi sarebbe complessità senza carico | — | dopo la Fase 7 |

## 3. Da lasciare lì, e perché

Queste non sono critiche al loro sistema: sono scelte giuste **là** e sbagliate
**qui**, perché i vincoli sono diversi.

| Cosa | Perché no |
|---|---|
| **Code-as-Data**: gli script operativi nel database, versionati là, eseguiti «senza dipendere dal filesystem» | Qui la fonte di verità è git, e lo è per scelta. Eseguire codice preso da un database significa che chi scrive nel database esegue codice come root: è un peggioramento della sicurezza in cambio di comodità. In una flotta aziendale con decine di nodi il ragionamento cambia; in una casa con un server, no |
| **MongoDB come CMDB** | Ci sono già Postgres e lo stato calcolato dalla dashboard. Un terzo motore di database per lo stesso lavoro è costo di manutenzione senza guadagno. La loro ragione — inventario sincronizzato con CheckMK e OEM — qui non esiste |
| **LangGraph + Celery** per l'orchestrazione | Lo sciame di agenti di Hermes fa già dividere-assegnare-ricucire in un centinaio di righe di sola libreria standard. Portarsi dietro LangChain per rifare la stessa cosa non è un aggiornamento |
| **VictoriaMetrics + Grafana** | Vale, ma non ora: è un progetto suo. Oggi ci sono Beszel per le metriche di base, Kuma per il su/giù, Homepage per le tessere. Se un giorno serve la serie storica vera — e per A6 servirebbe — si riapre questa voce, e la risposta probabilmente è sì |
| **Prompt «RALPH LOOP» con `STATELESSNESS`** | Interessante, ma è la loro disciplina di prompt per un modello che deve decidere su un database di produzione. Hermes ha una persona e una casa, non una flotta |

## 4. Una cosa che loro fanno meglio, e che qui era un difetto

Il loro `VerifierAgent` ha `_rule_based_classification`: se l'LLM non risponde,
o risponde qualcosa che non si riesce a interpretare, **decide una regola
deterministica** invece di lasciar cadere l'allarme.

È lo stesso principio con cui qui si è chiusa la bugia «ho salvato»: quando il
modello non è affidabile, il codice deve avere una risposta propria. Da tenere
come regola generale, non come dettaglio di implementazione.

## 5. I task, nell'ordine in cui conviene farli

1. ✅ **A1** — chunking del testo prima dell'embedding *(fatto: 125 note → 227 pezzi)*
2. ✅ **A2** — indicizzare i runbook del repository, con citazione del file *(fatto: 74 documenti)*
3. **A4** — interruttore globale `RUNNING`/`PAUSED`, letto da Hermes e dagli script
4. **A5** — elenco delle azioni permesse come file di dati + conferma per l'irreversibile *(= Fase 6)*
5. **A3** — il Verificatore davanti agli allarmi, con regola di riserva
6. **A7** — Langfuse, e la vista delle chiamate degli agenti in pagina
7. **A8** — «Edge Cases» nei runbook, a partire da quelli di Hermes
8. **A6** — previsione del riempimento dischi *(dopo aver deciso su VictoriaMetrics)*

Le fasi già in coda nel [PIANO_MASTER](PIANO_MASTER.md) — voce, Telegram, PWA —
restano davanti a questa lista: sono cose che il proprietario usa ogni giorno,
mentre queste rendono il sistema più solido.
