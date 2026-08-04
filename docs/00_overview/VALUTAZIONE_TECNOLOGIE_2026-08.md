# Le tecnologie passate il 2026-08-04 — cosa serve, cosa c'è già, cosa no

> Elenco portato dal proprietario: *«vedi come possiamo integrarle se servono,
> poi so che tante cose non servono»*. Aveva ragione: **quattro su dodici
> valgono, tre ci sono già, cinque no** — e i «no» sono la parte utile, perché
> una cosa non installata non va mantenuta, non va aggiornata e non può
> rompersi alle tre di notte.
>
> Due nomi non li conoscevo e li ho cercati invece di indovinare: **Headroom** e
> **Ponytail** sono usciti dal nulla nel 2026 e sono i due più interessanti
> della lista. `grafafy` l'ho letto come **Grafana**; se intendevi altro,
> dimmelo.

---

## Il verdetto in una tabella

| | Cosa | Verdetto | Perché |
|---|---|---|---|
| 1 | **Headroom** | **SÌ, il migliore della lista** | comprime il contesto del 60-95% prima che arrivi al modello. Qui il contesto è *il* vincolo: la T600 ha 4 GB e la cache a 32k è ciò che fa traboccare `qwen3.5:4b` sulla CPU |
| 2 | **FastAPI** | **SÌ, quando servirà un'API** | oggi Momo parla via Telegram e pannello. Il giorno che serve un endpoint (il plugin Obsidian del punto 18) è questo |
| 3 | **Ponytail** | **SÌ, ma sul PC, non sul server** | è una *skill* per gli agenti di programmazione — riguarda me che scrivo codice, non Momo |
| 4 | **Grafana** | **forse, e non adesso** | vedi §2 |
| 5 | **Vector database** | **c'è già: Qdrant** | live dal 2026-07, 125 note indicizzate |
| 6 | **Embedding** | **c'è già** | `embeddinggemma`, con cache su Valkey perché sulla CPU costava 18 s |
| 7 | **OpenAI API** | **c'è già, per forma** | tutti gli otto motori parlano il dialetto OpenAI: è già la lingua franca di casa |
| 8 | **Pinecone** | **NO** | è un servizio di qualcun altro. I vettori sono le tue note |
| 9 | **Chroma / Weaviate** | **NO** | sostituirebbero Qdrant, che funziona. Un cambio senza un difetto da chiudere è lavoro senza guadagno |
| 10 | **LangChain** | **NO, già deciso e già scritto** | [PIANO_GENERALE §2.2](PIANO_GENERALE.md) |
| 11 | **PyTorch** | **NO** | Ollama porta già il suo runtime. PyTorch entrerebbe solo per XTTS-v2 (la clonazione voce), e allora entra *lì* |
| 12 | **scikit-learn** | **NO** | non c'è un problema di apprendimento automatico in questa casa. Aggiungerlo «perché è utile» è come tenere un tornio in cucina |
| 13 | **CodeBurn** | **forse, e non è del server** | conta quanto spendi in token con Claude Code. Utile a te, non a Momo |

---

## 1. Headroom — il solo che risolve un vincolo che abbiamo davvero

[headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom), Apache 2.0.
Si mette **in mezzo** fra l'agente e qualunque endpoint compatibile OpenAI e
comprime ciò che passa: output degli strumenti, log, pezzi di RAG, cronologia.
Dichiara 60-95% di token in meno «senza perdita di qualità».

**Perché qui c'entra davvero, e non è entusiasmo.** Il collo di bottiglia di
questa casa è misurato e scritto: a 32k di contesto `qwen3.5:4b` mette 1,71 GB
su 3,78 in VRAM e il resto va su CPU ([ai_ollama §9.0](../04_apps/ai_ollama.md)).
Il contesto non è un dettaglio di costo: è **ciò che decide quale modello ci
sta nella scheda**. Comprimere gli output degli strumenti sposta quel confine.

E si incastra senza torsioni: gli otto motori sono tutti `provider: custom` con
un `base_url` compatibile OpenAI, quindi Headroom si infila cambiando **un
indirizzo**, che è esattamente ciò che `momo-motore` già sa fare.

**Da verificare prima di crederci**, e nessuna è banale:
- la compressione è **lossy**: va provata sul Guardrail e sulla memoria
  automatica, dove un output tagliato male diventa un fatto sbagliato scritto
  per sempre;
- aggiunge un salto in mezzo alla catena: **un pezzo in più che può cadere**, e
  se cade cade *ogni* motore insieme;
- i numeri li dichiara il progetto. Il banco di casa esiste già
  (`scripts/momo/tests/`): si misura qui.

**Proposta**: punto nuovo in [PIANO_GENERALE](PIANO_GENERALE.md), onda F,
~4 ore, dopo la ricerca in Nextcloud.

## 2. Grafana — la domanda giusta è «cosa non vedi oggi?»

Qui ci sono già **Uptime Kuma** (40 monitor: su/giù), **Beszel** (CPU, RAM,
dischi), **Scrutiny** (SMART), **Homepage** e la **dashboard master**.

Grafana aggiungerebbe *le serie storiche interrogabili*: «la RAM di LXC 102
com'è andata nell'ultimo mese?». Oggi quella risposta non c'è — c'è
`metrics-long.jsonl`, 26 000 campioni, che nessuno interroga.

**Ma costa**: Grafana da solo non basta, vuole un database di serie temporali
(Prometheus o VictoriaMetrics) e degli esportatori. Sono tre servizi nuovi da
mantenere, monitorare e salvare, per rispondere a una domanda che **finora non
hai mai fatto**.

**Verdetto**: non adesso. Si riapre il giorno che ti serve rispondere a una
domanda storica e non puoi — e quel giorno la domanda sarà concreta, il che
renderà anche ovvio cosa misurare.

## 3. Ponytail — utile, ma non a Momo

[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail). È una
*skill* che fa scrivere **meno codice** agli agenti di programmazione (Claude
Code, Cursor, Codex). 44 000 stelle in nove giorni; i risparmi reali misurati
da terzi sono «un quarto o metà» di quelli dichiarati — che resta molto.

Riguarda **il PC**, non il server: agisce su chi scrive il codice di questa
casa, non su Momo che la gestisce. Vale la prova, e la prova è a costo zero:
si installa, si guarda una settimana, si tiene o si toglie.

## 4. Perché i «no» sono la parte importante

Ogni cosa installata va **mantenuta, aggiornata, monitorata, salvata e
ripristinata** — è la regola scritta nel README di questa casa. Un servizio in
più che non chiude un difetto vero è debito, non capacità.

- **Pinecone** è ospitato da altri. Il punto di questa casa è che i dati
  restano qui: mandare fuori i vettori delle proprie note è mandare fuori le
  note, in un'altra forma.
- **Chroma e Weaviate** farebbero quello che Qdrant fa già. Sostituire una cosa
  che funziona con una equivalente è lavoro senza guadagno.
- **PyTorch e scikit-learn** sono mattoni per *costruire* modelli. Qui i modelli
  si *usano*, e chi li esegue (Ollama) si porta già il suo runtime. PyTorch
  rientrerà per XTTS-v2, come dipendenza di quello e non come scelta a sé.
- **LangChain** era già stato valutato e scartato, con la motivazione scritta:
  aggiunge un livello fra noi e i modelli proprio dove serve vedere cosa
  succede.

---

## Sorgenti

- [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) — la compressione del contesto
- [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) — la skill che fa scrivere meno codice
- [getagentseal/codeburn](https://github.com/getagentseal/codeburn) — il contatore di token locale
- [PIANO_GENERALE §2.2](PIANO_GENERALE.md) — perché LangChain no
- [ai_ollama.md §9.0](../04_apps/ai_ollama.md) — cosa entra davvero in 4 GB, misurato
