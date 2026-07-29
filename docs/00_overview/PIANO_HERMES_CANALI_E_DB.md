# Hermes: motori alternativi, canali di chat, database, controlli

> Deciso il 2026-07-29, dopo le domande del proprietario: *«puoi usare altro,
> non per forza Ollama?»*, *«voglio parlargli da Telegram e WhatsApp»*,
> *«chiedergli di farmi dei controlli»*, *«collegarsi ai db»*.
>
> Una di queste risposte è un no motivato. Le altre tre sono progetti reali.

---

## 1. Ollama non è un vincolo (e non lo è mai stato)

Hermes parla due protocolli: quello nativo di Ollama e **quello di OpenAI**.
Il secondo lo parlano quasi tutti, quindi questi motori funzionano **oggi**,
senza toccare una riga di codice — basta una voce in `backends.json` con
`"type": "openai"`:

| Motore | Quando ha senso qui |
|---|---|
| **vLLM** | Se vuoi spremere la GPU: batching continuo, throughput molto più alto di Ollama con più richieste insieme. È il motore giusto per lo sciame di agenti |
| **llama.cpp** (`llama-server`) | Leggero, GGUF, ottimo se vuoi controllo fine su quantizzazione e offload |
| **LM Studio** | Interfaccia grafica sul PC, espone un endpoint OpenAI con un clic |
| **SGLang / TGI** | Alternative a vLLM, stessa logica |
| **Unsloth** | ⚠️ Non è un server: serve ad **addestrare/affinare** modelli più in fretta. Il modello che produce lo servi poi con vLLM o llama.cpp |

### Perché sul tuo PC resta Ollama, per ora

La 5070 Ti è **Blackwell, compute capability 12.0 (sm_120)**, hardware ancora
recente per l'ecosistema Python: le build stabili di PyTorch spesso non
includono i binari sm_120, e far partire vLLM richiede CUDA 12.8+ e
`TORCH_CUDA_ARCH_LIST='12.0+PTX'`. Si fa, ma è una serata di lavoro.

Ollama invece la riconosce da solo e carica il modello **100% in GPU** (già
verificato). Quindi: Ollama come base che funziona, vLLM come passo successivo
**se** lo sciame diventa l'uso normale — perché è lì che il batching continuo
ripaga davvero.

Da notare: con vLLM il parametro `parallel` del motore può salire parecchio, e
lo sciame smette di essere una divisione solo logica del lavoro.

---

## 2. Telegram: sì, ed è la strada giusta

Bot ufficiale, gratuito, nessuna zona grigia. Il ponte gira **sul server** e
non espone nulla verso internet: è il bot che va a chiedere i messaggi
(long polling), quindi non serve aprire porte né un dominio pubblico.

```
Telegram ──(long polling in uscita)──> ponte su LXC 102 ──> Hermes
```

Il punto delicato è **l'identità**: un ID Telegram non è un utente Authentik.
Regola da implementare, senza scorciatoie:

- una tabella `id-telegram → utente` compilata **a mano** dall'amministratore;
- un ID sconosciuto riceve un rifiuto secco e basta — niente registrazione
  automatica, altrimenti chiunque conosca il nome del bot diventa un utente;
- il ponte chiama Hermes con un token di servizio **dichiarando l'utente**, e
  Hermes applica gli stessi permessi della pagina web: gli strumenti sul vault
  restano solo tuoi.

Così da telefono avresti Hermes ovunque, con il tuo ruolo, senza VPN.

---

## 3. WhatsApp: no, e il motivo è serio

Non esiste un modo pulito di collegare WhatsApp senza rischiare **il tuo numero
personale**.

- Le librerie self-hosted (Baileys, WAHA, Evolution API) usano il protocollo di
  WhatsApp Web **contro i termini di servizio**. Nel 2025 Meta ha intensificato
  il rilevamento automatico: i numeri che le usano vengono tipicamente banditi
  **in modo permanente entro 2-8 settimane**.
- Dal **15 gennaio 2026** i termini vietano **esplicitamente** i chatbot AI di
  terze parti su WhatsApp.
- L'unica via sanzionata è la **WhatsApp Business API**: a pagamento, richiede
  un'identità aziendale verificata, e non è pensata per l'uso personale.

Tradotto: per collegare Hermes a WhatsApp metteresti a rischio permanente il
numero che usi tutti i giorni, per avere una cosa che Telegram fa gratis e senza
rischi. **Non lo consiglio e non lo costruisco** se non me lo chiedi di nuovo
sapendo questo.

Se il punto è «voglio Hermes dal telefono»: Telegram lo risolve. Se il punto è
«voglio proprio WhatsApp», l'unica strada onesta è la Business API con un numero
**diverso** da quello personale.

---

## 4. Collegarsi ai database

Qui il proprietario è un DBA Oracle, quindi lo strumento va progettato con la
diffidenza che merita: un assistente che scrive su un database è un incidente
che aspetta di succedere.

Disegno dello strumento `db_query`:

| Vincolo | Perché |
|---|---|
| **Solo SELECT**, verificato prima di eseguire (niente `;`, niente DML/DDL) | un LLM non deve poter scrivere, mai |
| Connessioni **dichiarate a mano** in un file di configurazione, mai costruite dal modello | altrimenti il modello sceglie a chi connettersi |
| Utente di database **in sola lettura**, creato apposta | la difesa vera sta nei permessi, non nel filtro |
| Tetto sulle righe (es. 200) e timeout | una query storta non deve piegare il database |
| **Solo amministratore** | i dati dei database non sono roba da utenti di casa |
| Ogni query **registrata** | serve poter rispondere a «cosa ha chiesto» |

Con Oracle serve `oracledb` (thin mode, niente client Oracle da installare);
per Postgres/MySQL i driver corrispondenti. È l'unica parte del progetto che
introduce dipendenze Python fuori dalla libreria standard: va valutato se
tenerla in un servizio separato per non appesantire Hermes.

Uso realistico: *«quante sessioni attive ci sono su momoog21?»*,
*«fammi vedere gli ultimi errori nella heartbeat table»*.

---

## 5. «Fammi dei controlli»

Controlli salvati che Hermes esegue da solo e riferisce. Non serve un motore di
workflow: bastano una lista di controlli e un orario.

```
controllo = { nome, domanda o query, quando, dove riferire }
```

- **quando**: ogni giorno / ogni ora / a richiesta;
- **dove**: email (il relay c'è già), ntfy (c'è già), Telegram (punto 2);
- **cosa**: una domanda a Hermes con gli strumenti attivi, oppure una query.

Il valore vero non è «Hermes che chatta», è **Hermes che ti avvisa prima che
tu debba chiedere**: «lo spazio su pbs-p710 è passato dal 40% al 78% in una
settimana», «il backup di Immich non gira da 3 giorni».

Regola: un controllo **riferisce**, non aggiusta. Le azioni restano tue, dalla
dashboard.

---

## 6. Ordine consigliato

| # | Cosa | Perché in questa posizione |
|---|---|---|
| 1 | **Voce in ingresso** (Whisper sul PC) | è la richiesta più vecchia ancora aperta |
| 2 | **Telegram** | ti dà Hermes fuori casa, e serve da canale per i controlli |
| 3 | **Controlli salvati** | è il punto in cui Hermes inizia a essere utile senza che tu lo apra |
| 4 | **`db_query` in sola lettura** | alto valore per te, ma va fatto con calma |
| 5 | **vLLM sul PC** | solo se lo sciame diventa l'uso normale |
| — | **WhatsApp** | non pianificato, vedi §3 |

---

## 7. Fonti

- vLLM su Blackwell sm_120 — <https://github.com/vllm-project/vllm/issues/41614>
- llama.cpp su sm_120 — <https://github.com/ggml-org/llama.cpp/issues/22696>
- Rischio ban con le API WhatsApp non ufficiali — <https://sporesec.com/en/blog/whatsapp-unofficial-api-ban-risk>
- Divieto dei chatbot di terze parti su WhatsApp (gennaio 2026) — <https://chatboq.com/blogs/third-party-ai-chatbots-ban>
