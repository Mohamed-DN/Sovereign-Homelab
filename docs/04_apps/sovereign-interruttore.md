# L'interruttore globale RUNNING/PAUSED — il freno di tutto ciò che agisce

> **A4 di Nexi**, punto 4 del [PIANO_GENERALE](../00_overview/PIANO_GENERALE.md).
> Un file solo, `scripts/hermes/sovereign_switch.py`, di sola libreria standard,
> importato da Hermes, da Momo e dall'agente di controllo delle app — stesso
> disegno del [Guardrail](momo-guardrail.md): due copie della stessa regola
> divergono, e la divergenza è invisibile finché una delle due non lascia
> passare qualcosa.

---

## 1. Purpose & architecture

Uno stato `RUNNING`/`PAUSED` che **ogni agente controlla prima di agire**. In
pausa l'assistente **dorme, non muore**: la chat continua a rispondere, la
memoria continua a ricordare, ma nulla che cambi il mondo fuori dalla chat
parte. È più utile di `systemctl stop`, che spegne anche la possibilità di
capire cosa stava succedendo.

```
                       /var/lib/sovereign-hermes/master-state.json
                       { "running": bool, "paused_by", "paused_at",
                         "paused_reason", "armed_until" }
                                    ▲
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
   sovereign-hermes.py      Momo (plugin              sovereign-app-
   run_tool()  ← strozzatura  sovereign_tools)        control-agent.py
   unica di ogni strumento    pre_tool_call +          POST /control
   + master_execute()         _make_handler
             │
             └── pannello: /api/master/status · /api/master/pause · /resume
                 CLI:      python3 sovereign_switch.py pause "motivo" | resume | status
```

**Perché lo stesso file di MASTER e non uno nuovo.** `master-state.json` porta
già la chiave `running` da W5, e già la legge `master_execute`. Un secondo file
avrebbe creato due verità sullo stesso stato: l'errore che questo progetto ha
già pagato altrove. L'interruttore **estende** quel file, non lo sostituisce, e
`armed_until` resta intatto perché è una cosa diversa (l'armamento a 30 minuti
di MASTER).

### 1.1 Che cosa la pausa ferma, e che cosa no

Questa tabella **è** il disegno: senza di essa «in pausa» è una parola.

| | In pausa |
|---|---|
| Chat, ricerca web, lettura del vault, stato dell'impianto, accessi | **continua** |
| Memoria: `ricorda`, `dimentica`, `agenda_*`, `rubrica_*`, `procedura_*` | **continua** — è lo stato della conversazione, ed è reversibile |
| `esegui_azione_master` — riavvii, comandi sull'impianto | **fermo** |
| `send_mail` — parte e non torna indietro | **fermo** |
| `vault_scrivi` — via LiveSync arriva su tutti i dispositivi | **fermo** |
| `sovereign-app-control-agent` — start/stop dei container | **fermo** |
| Allarmi (relay Kuma, ops-alerts) | **continuano** |

La regola in una riga: **la pausa ferma ciò che cambia il mondo fuori dalla
chat; non ferma il parlare, il leggere, né il ricordare.**

Gli **allarmi non si fermano di proposito**. Un allarme è informazione, non
azione: un impianto messo in pausa perché qualcosa sta andando storto è
esattamente quello in cui si vuole continuare a essere avvisati. Chi mette in
pausa vuole fermare le mani, non gli occhi.

### 1.2 La direzione in cui si sbaglia

| Stato del file | Verdetto | Perché |
|---|---|---|
| **manca** | `RUNNING` | non è mai stato scritto: un file assente non deve spegnere in silenzio tutto l'impianto |
| **presente e leggibile** | quello che dice | — |
| **presente e illeggibile** | `PAUSED` | qualcuno *ha* scritto, e si è rotto. Una pausa che sparisce da sola è il caso pericoloso: le azioni ripartirebbero mentre il proprietario le crede ferme |

Sono due direzioni opposte **di proposito**, e la differenza fra «mai scritto» e
«scritto e rotto» è l'unica cosa che le separa. La scrittura è **atomica**
(file temporaneo + `os.replace` + `fsync`) proprio perché il terzo caso non
debba quasi mai capitare.

### 1.3 Dove il controllo non arriva, detto invece che sottinteso

- La guardia sull'host (`hermes-master-guard.py`) **non** legge l'interruttore,
  e non deve: è un divieto assoluto, sempre attivo, indipendente da qualunque
  stato. Il controllo dell'interruttore avviene in Hermes **prima** del salto
  SSH verso l'host.
- Il file vive su **LXC 102**. Gli agenti che agiscono stanno tutti lì (Hermes,
  Momo, l'agente app). Un agente futuro su un altro host **non** leggerebbe
  questo file: dovrà interrogare `GET /api/master/status`. Oggi non esiste, e
  non ho scritto codice per un caso che non esiste — un percorso non provato è
  peggio di un percorso assente.
- L'interruttore **non** è una difesa contro un attaccante che ha già root su
  LXC 102: chi può scrivere il file può rimetterlo su `RUNNING`. È un freno
  operativo, non un controllo di sicurezza. Le difese di sicurezza sono altre
  (divieto assoluto compilato a codice, filtro privato/non privato).

## 2. Target & sizing

Nessun processo proprio, nessuna porta. Una lettura di file JSON da poche
centinaia di byte per ogni chiamata di strumento: microsecondi, e il file sta
nella cache del sistema operativo. Vive dentro il processo di chi lo importa.

## 3. Install / deployment

```bash
# il modulo condiviso, accanto al Guardrail
pct push 102 sovereign_switch.py /opt/sovereign-hermes/sovereign_switch.py

# Hermes: nessuna configurazione, l'import e' incondizionato in cima al modulo
# (fallire chiuso: un Hermes che parte credendo di avere il freno quando non
# ce l'ha e' peggio di un Hermes che non parte)
pct exec 102 -- systemctl restart sovereign-hermes

# l'agente app: legge lo stesso file, nessuna configurazione
pct exec 102 -- systemctl restart sovereign-app-control-agent

# Momo: il plugin sovereign_tools lo importa da SOVEREIGN_HERMES_DIR
```

| Variabile | Default | Effetto |
|---|---|---|
| `SOVEREIGN_SWITCH_FILE` | `/var/lib/sovereign-hermes/master-state.json` | dove sta lo stato |
| `HERMES_MASTER_STATE_FILE` | come sopra | il nome storico di W5, letto se il primo non è impostato |

### 3.1 Perché il file si chiama `sovereign_` e non `hermes_`

Deciso dal proprietario il 2026-07-31: **Momo sostituirà Hermes** (fase 5 di
[PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md), punto 21 del
[PIANO_GENERALE](../00_overview/PIANO_GENERALE.md)). I moduli nuovi nascono con
un nome che non dovrà essere cambiato al passaggio del testimone.

I vecchi — `hermes_memory.py`, `hermes_guardrail.py` — restano come sono
**fino a quel punto**, e si rinominano tutti insieme in un'operazione sola:
rinominarne uno alla volta significa avere per settimane un impianto in cui
metà dei nomi mente. La directory `scripts/hermes/` e il percorso di
installazione `/opt/sovereign-hermes/` sono nella stessa condizione, e per lo
stesso motivo.

## 4. DNS / domain names / alias

Nessuno. Non è un servizio con un indirizzo: è un file e una funzione.

## 5. Nginx Proxy Manager (NPM)

Nessun host proxy. Si comanda dal pannello di Hermes, che è già dietro
`hermes.internal` e quindi dietro il forward-auth di Authentik, e dalla riga di
comando su LXC 102.

## 6. Homepage & Uptime Kuma

- **Homepage**: nessuna tessera propria.
- **Uptime Kuma**: **nessun monitor, e volutamente.** Un monitor che diventasse
  rosso quando l'impianto è in pausa trasformerebbe una decisione del
  proprietario in un allarme, che è l'esatto contrario dello scopo. Lo stato si
  vede nel pannello di Hermes (`interruttore: RUNNING/PAUSED`, con chi e perché)
  e da `GET /api/master/status`.

## 7. Backup & restore

Lo stato è una decisione operativa del momento, non un dato: **non si fa il
backup e non si ripristina.** Dopo un ripristino di LXC 102 il file può
mancare, e per il §1.2 questo significa `RUNNING` — cioè lo stato normale, che
è la scelta giusta quando si riparte da zero.

Il **codice** è coperto da git come tutto il resto.

## 8. Rollback

```bash
# togliere il freno lasciando il codice al suo posto
pct exec 102 -- python3 /opt/sovereign-hermes/sovereign_switch.py resume

# togliere proprio il modulo (sconsigliato: Hermes non parte piu', per
# scelta -- vedi §3)
pct exec 102 -- cp /opt/sovereign-hermes/sovereign-hermes.py.bak-switch \
                   /opt/sovereign-hermes/sovereign-hermes.py
pct exec 102 -- systemctl restart sovereign-hermes
```

## 9. Edge Cases — cosa succede se un passo va a metà

> Scritto **prima** di costruire, come chiede A8. Ognuno di questi è un caso
> che il codice deve gestire, non una possibilità teorica.

| Caso | Cosa succede | Perché così |
|---|---|---|
| **Il file si corrompe a metà scrittura** | non può: si scrive un `.tmp`, si fa `fsync`, poi `os.replace` (atomico). Se malgrado tutto risulta illeggibile → `PAUSED` | una pausa che sparisce da sola è il danno peggiore |
| **Pausa durante un'azione MASTER già partita** | l'azione in corso **finisce**: il controllo è all'ingresso, non un'interruzione. La successiva è rifiutata | uccidere un comando a metà lascia l'impianto in uno stato che nessuno ha progettato |
| **Pausa mentre `send_mail` sta parlando col server SMTP** | la mail parte. Nessun annullamento | una mail consegnata non torna indietro: fingere di averla fermata sarebbe la bugia che il Guardrail esiste per prevenire |
| **Due processi mettono in pausa insieme** | `os.replace` è atomico: vince l'ultimo, nessun file misto. Le chiavi sconosciute (`armed_until`) sono rilette e riscritte, mai perse | il pattern leggi-modifica-scrivi ingenuo cancellerebbe l'armamento di MASTER |
| **Hermes è morto e serve la pausa** | la CLI scrive il file senza Hermes: `python3 sovereign_switch.py pause "motivo"` | un freno che funziona solo se il servizio è vivo non è un freno |
| **Riavvio del servizio mentre è in pausa** | resta in pausa: lo stato è su disco, non in memoria | — |
| **Ripristino di LXC 102 da backup, file assente** | `RUNNING` (§1.2) | ripartire da zero significa ripartire acceso |
| **Momo chiama uno strumento aggirando `run_tool()`** | rifiutato lo stesso: il controllo è in **due** punti indipendenti (hook `pre_tool_call` e `_make_handler`), come già il filtro privato/pubblico | Momo chiama `tool["run"]` diretto: un controllo in un punto solo sarebbe stato aggirato senza che nessuno se ne accorgesse |
| **Uno strumento nuovo viene aggiunto e nessuno lo mette nell'elenco** | **gira anche in pausa**. È il limite dichiarato di un elenco per nome | l'alternativa (bloccare tutto tranne un elenco di permessi) fermerebbe anche la chat, che deve continuare. Chi aggiunge uno strumento che agisce fuori dalla chat lo aggiunge a `PAUSED_TOOLS`, ed è scritto nel test |
| **La pausa viene messa da chi non è il proprietario** | impossibile dal pannello (`is_admin`); dalla CLI serve root su LXC 102 | — |

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Uno strumento viene rifiutato e non si capisce perché | l'impianto è in pausa | `python3 /opt/sovereign-hermes/sovereign_switch.py status` — dice chi ha messo in pausa, quando e perché |
| «in pausa» ma le azioni partono lo stesso | lo strumento non è in `PAUSED_TOOLS` (vedi §9, ultimo caso) | aggiungerlo all'insieme in `sovereign_switch.py` e il caso al test |
| Lo stato dice `PAUSED` e nessuno l'ha messo | file illeggibile → `PAUSED` per progetto (§1.2) | `cat` del file: se è JSON rotto, `resume` lo riscrive pulito. Se capita più di una volta, è un difetto grave: il disco o la scrittura atomica |
| `resume` non ha effetto | si sta guardando il file sbagliato (`HERMES_SWITCH_FILE` impostata nell'ambiente del servizio ma non nella shell) | `systemctl show sovereign-hermes -p Environment` |
| `armed_until` di MASTER sparito dopo una pausa | difetto: il modulo deve preservare le chiavi che non conosce | vedi §9, caso «due processi» — e il test `test_preserva_chiavi_sconosciute` |

## 11. Verifica di funzionamento

```bash
# le regole, isolate (gira ovunque, non serve il server)
python3 scripts/hermes/tests/test_sovereign_switch.py

# dal vivo: in pausa un'azione MASTER e' rifiutata E la chat risponde ancora
pct exec 102 -- python3 /opt/sovereign-hermes/sovereign_switch.py pause "prova"
curl -sk -G https://hermes.internal/api/chat -H "X-authentik-username: mohamed" \
  --data-urlencode "q=Che ore sono?"                      # deve rispondere
pct exec 102 -- curl -s localhost:8093/api/master/status  # running:false
pct exec 102 -- python3 /opt/sovereign-hermes/sovereign_switch.py resume

# l'agente app rifiuta in pausa, con 423
pct exec 102 -- python3 /opt/sovereign-hermes/sovereign_switch.py pause "prova"
pct exec 102 -- curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  localhost:8097/control -H "Authorization: Bearer $(cat /root/sovereign-secrets/app-control-agent-token)" \
  -d '{"service":"jellyfin","action":"stop","actor":"prova"}'   # atteso: 423
pct exec 102 -- python3 /opt/sovereign-hermes/sovereign_switch.py resume
```

## 12. Official Sources

- [PIANO_GENERALE](../00_overview/PIANO_GENERALE.md) punto 4 — la fila e il criterio
- [PIANO_AGGIORNAMENTO_DA_NEXI](../00_overview/PIANO_AGGIORNAMENTO_DA_NEXI.md) A4 — l'interruttore globale, e §4 sul degradare invece di mentire
- [hermes.md](hermes.md) §7-novies — la modalità MASTER, che ha introdotto `master-state.json`
- [momo-guardrail.md](momo-guardrail.md) — il modulo condiviso da cui questo copia la forma
- [sovereign-verificatore.md](sovereign-verificatore.md) — l'altra metà del punto 4
- [VISIONE_COMPLETA](../00_overview/VISIONE_COMPLETA.md) §2.3 — degradare, non mentire
