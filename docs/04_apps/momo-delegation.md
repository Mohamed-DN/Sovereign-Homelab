# Delegazione a grafo fra i 13 ruoli — P9 del piano "Momo che programma"

> **Stato (2026-08-08): acceso e provato dal vivo, con i tre freni
> verificati in modo deterministico.** Un nuovo strumento
> (`delegate_to_role`) sopra il primitivo nativo di hermes-agent
> (`delegate_task`, che conosce solo leaf/orchestrator, un permesso — non
> una persona). Provato: una delega singola reale attraverso il vero
> strumento, e poi ciclo/tetto verificati chiamando direttamente la
> funzione, non sperando che il modello si comporti bene da solo.

---

## 1. Purpose & architecture

Richiesta del proprietario, scritta in
[PIANO_MOMO_DIGITAL_TWIN](../00_overview/PIANO_MOMO_DIGITAL_TWIN.md) §3.6:
*«la squadra di agenti può consegnare ad altri componenti... un dev può
riparlare in alto o passare a un altro CEO, a un altro cyber, o allo
stesso — valuta lui»*. Un **grafo** (instradamento deciso dagli agenti),
non lo sciame **lineare** di oggi (dividi → assegna → ricuci,
[hermes.md](hermes.md) §7-ter).

Tre cose nel disegno **prima** di scrivere una riga (§3.6, non
negoziabili):
1. un tetto di salti — e cosa succede quando lo si raggiunge: si
   risponde con quello che si ha, dicendolo;
2. il rilevamento dei cicli — A manda a B che rimanda ad A;
3. un catalogo di ruoli nostro, perché `delegate_task` di hermes-agent
   conosce solo due ruoli (`leaf`/`orchestrator`, un **permesso** — può o
   non può delegare oltre — non una **persona**).

### Cosa dice il codice, letto per intero prima di scrivere

`tools/delegate_tool.py` (3974 righe): nessun parametro per dare a un
figlio un prompt/identità personalizzati. Il `role` normalizza solo a
`leaf`/`orchestrator`. C'è già, però, un **tetto di annidamento nativo**
(`delegation.max_spawn_depth`, default 1 — "flat: parent (0) -> child (1);
grandchild rejected") pensato per alberi parent→child→grandchild, non per
un grafo di 13 persone che si passano la palla — troppo basso per una
catena di 6+ salti, dove ogni salto richiede che il nodo corrente possa
*a sua volta* delegare (quindi conta come un livello di annidamento dal
loro punto di vista).

### I 13 ruoli — non reinventati, riusati

Sono quelli **già vivi** nello sciame lineare dell'Hermes originale:
[`scripts/hermes/roles.json`](../../scripts/hermes/roles.json) (13 voci,
verificato **identico** al file live su `/opt/sovereign-hermes/`), ognuno
con `id`, `titolo`, `quando` (quando viene chiamato), `prompt` (la sua
identità), `tools` (i suoi strumenti tipici) — documentati in
[hermes.md](hermes.md) §7-ter: Direttore (CEO), Architetto (CTO),
Sistemista (SRE), Sicurezza (CISO), Ricercatore, Archivista, Sviluppatore,
Debugger, Revisore, Qualità (QA), DBA, Documentalista, Generalista.

### L'architettura costruita

```
delegate_to_role(role_id, task, chain_id?)
        │
        ▼
  ruolo valido? (13 id, da roles.json)
        │ no → errore con l'elenco valido
        ▼ sì
  chain_id nuovo o esistente (registro in memoria di processo,
  scaduto dopo 1h — NON un file, NON fidato al modello: lo stesso
  principio del registro dell'orchestratore per il teardown della
  sandbox, P1)
        │
        ▼
  FRENO 1 — ciclo: role_id già in "visited"?
        │ sì → BLOCCATO, messaggio esplicito, MAI raggiunge delegate_task
        ▼ no
  FRENO 2 — tetto: hops >= MAX_HOPS (default 6)?
        │ sì → BLOCCATO, messaggio esplicito, MAI raggiunge delegate_task
        ▼ no
  hops += 1, visited.append(role_id)
        │
        ▼
  costruisce il compito del figlio: prompt del ruolo + strumenti tipici
  (guida, non vincolo tecnico) + stato della catena (passo N/6, percorso
  finora, chain_id per continuare) + il compito vero
        │
        ▼
  delegate_task(goal=<sopra>, role="orchestrator", parent_agent=...)
  — "orchestrator" perché il figlio deve poter richiamare
    delegate_to_role a sua volta, per continuare la catena
```

`delegation.max_spawn_depth` alzato a 8 in config.yaml — oltre il nostro
`MAX_HOPS` (6) — così il tetto grezzo di hermes-agent non scatta PRIMA
del nostro, che ha un messaggio pensato apposta ("rispondi con quello che
hai, dicendolo", non un errore tecnico).

## 2. Target & sizing

Nessun processo proprio: gira dentro il processo di Momo, come gli altri
plugin. Il registro delle catene è un dizionario Python in memoria, non
un file — costo trascurabile, e sparisce da solo (nessuna persistenza fra
riavvii, per costruzione: una catena interrotta da un riavvio ricomincia,
non riprende in uno stato a metà).

## 3. Install / deployment

```bash
mkdir -p /opt/momo/home/.hermes/plugins/sovereign_delegation
# __init__.py, plugin.yaml da scripts/momo/sovereign_delegation/

# config.yaml, modifica strutturale:
#   plugins.enabled: [..., sovereign-delegation]
#   delegation.max_spawn_depth: 8
#   toolsets / platform_toolsets.{telegram,cli}: [..., delegation, sovereign-delegation]

systemctl restart momo-gateway
```

Variabili d'ambiente:

| Variabile | Default | Effetto |
|---|---|---|
| `SOVEREIGN_ROLES_FILE` | `/opt/sovereign-hermes/roles.json` | dove leggere il catalogo dei 13 ruoli |
| `SOVEREIGN_DELEGATION_MAX_HOPS` | `6` | il tetto di salti |

## 4. DNS / domain names / alias

Nessuno.

## 5. Nginx Proxy Manager (NPM)

Nessun host.

## 6. Homepage & Uptime Kuma

Nessuno.

## 7. Backup & restore

Nessuno stato persistente: il registro delle catene è in memoria, sparisce
a ogni riavvio del gateway (per costruzione, non un difetto).

## 8. Rollback

```bash
# togliere "sovereign-delegation" da plugins.enabled e dai toolset, poi
systemctl restart momo-gateway
```
`delegation.max_spawn_depth: 8` può restare: alza solo il tetto nativo per
i cari che usano `delegate_task` direttamente, non introduce un rischio
nuovo (il tetto nativo comunque un limite, solo più alto).

## 9. Verifica di funzionamento

Provato dal vivo il 2026-08-08, in due modi — attraverso il vero
strumento, e in modo deterministico chiamando la funzione:

```bash
# 1. una delega vera, attraverso il vero strumento
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes /opt/momo/venv/bin/hermes -z \
  'Chiama lo strumento delegate_to_role con role_id=sicurezza, task="in una frase, quali sono i principi di sicurezza di questa casa?". Riportami la risposta ricevuta.' \
  --yolo -t sovereign-delegation,delegation
```
Risultato: una risposta reale, in voce da persona di sicurezza ("minimo
privilegio, separazione delle responsabilità, validazione rigorosa degli
input...") — non un'eco del compito, una risposta generata dal
sotto-agente vero.

**Nota di metodo**: senza il flag esplicito `-t sovereign-delegation,
delegation`, `hermes -z` non risolveva correttamente il toolset e il
modello rispondeva di non riuscire a chiamare lo strumento — pur essendo
il toolset presente in `platform_toolsets.cli` (verificato con un
diagnostico diretto: `_get_platform_tools` lo includeva, `delegate_to_role`
risultava registrato). Sospetto: `-z` senza `-t` esplicito non passa dalla
stessa risoluzione di toolset della piattaforma `cli`. Non approfondito
oltre — il gateway vivo (Telegram) non ha questo problema, come già visto
per `execute_code` in P2.

```python
# 2. i due freni, in modo deterministico (chiamando la funzione vera,
# non sperando che il modello incateni le chiamate da solo)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "sovereign_delegation", ".../plugins/sovereign_delegation/__init__.py")
sd = importlib.util.module_from_spec(spec); spec.loader.exec_module(sd)

# ciclo: sviluppatore -> sicurezza -> sviluppatore
sd.delegate_to_role("sviluppatore", "test")           # hops=1, visited=[sviluppatore]
sd.delegate_to_role("sicurezza", "test", chain_id)     # hops=2, visited=[sviluppatore, sicurezza]
sd.delegate_to_role("sviluppatore", "test", chain_id)  # BLOCCATO: ciclo_rilevato
```

Risultato: **entrambi i freni scattano esattamente al punto giusto**.
Il ciclo (sviluppatore rivisitato) bloccato al 3° salto, senza mai
raggiungere `delegate_task`. Il tetto (7 ruoli diversi, `MAX_HOPS=6`)
bloccato al 7° salto, con `visited` fermo a 6 voci — il tentativo respinto
non contamina lo stato. I salti leciti (1-6, o 1-2 nel test del ciclo)
procedono correttamente fino al vero `delegate_task` (che fallisce per un
motivo diverso e atteso nel test isolato: nessun `parent_agent` reale —
prova che il freno non ha bloccato per errore un salto legittimo).

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Il modello dice di non poter chiamare `delegate_to_role` | `hermes -z` senza `-t` esplicito non risolve il toolset correttamente (vedi §9) | aggiungere `-t sovereign-delegation,delegation` esplicitamente, o testare dal gateway vivo (Telegram) |
| Una catena si blocca subito con "ciclo" al primo salto verso un ruolo mai visto | il `chain_id` passato appartiene a una catena scaduta/inesistente ma coincide per caso con un ruolo già visitato in un'altra catena | verificare che il `chain_id` sia quello restituito dalla delega precedente, non inventato |
| Il tetto scatta prima di 6 salti veri | ogni salto conta, compresi i tentativi poi falliti per altri motivi (es. `parent_agent` mancante in un test isolato) — nel gateway vivo questo non succede, `parent_agent` c'è sempre | verificare `MAX_HOPS`/`SOVEREIGN_DELEGATION_MAX_HOPS` |
| Lo scoping degli strumenti per ruolo non sembra rispettato | **limite noto, non un bug**: il campo `tools` di `roles.json` è oggi solo una guida nel prompt del figlio, non un vincolo tecnico — `delegate_task` non ha un parametro per restringere gli strumenti di un figlio per ruolo | da chiudere in un giro successivo se misurato come problema reale |

## 11. Official Sources

- Codice letto per intero il 2026-08-08: `/opt/hermes-agent-study/tools/delegate_tool.py`
  (3974 righe, in particolare `delegate_task()`, `_normalize_role()`,
  `_get_max_spawn_depth()`), `agent/delegation_context.py`
- [scripts/hermes/roles.json](../../scripts/hermes/roles.json) — i 13 ruoli, già vivi nello sciame lineare
- [hermes.md](hermes.md) §7-ter — lo sciame lineare di oggi, la tabella dei 13 ruoli
- [PIANO_MOMO_DIGITAL_TWIN](../00_overview/PIANO_MOMO_DIGITAL_TWIN.md) §3.6 — la richiesta del proprietario, i tre freni
- [PIANO_MOMO_PROGRAMMATORE](../00_overview/PIANO_MOMO_PROGRAMMATORE.md) — l'ordine P1-P10
