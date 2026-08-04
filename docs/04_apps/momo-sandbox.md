# La sandbox di Momo — P1+P2 del piano "Momo che programma"

> **Stato (2026-08-04): P1 fatto. P2 provato dal vivo con successo, ma
> NON acceso in modo permanente — vedi §12, è una decisione del
> proprietario, non un lavoro rimasto a metà.** La gabbia esiste, è stata
> attaccata due volte (una manualmente in P1, una attraverso il vero
> strumento `execute_code` in P2) e non ha ceduto — anzi, il secondo
> tentativo ha trovato un bug vero nel codice di hermes-agent (§9) che il
> primo non poteva vedere. Il teardown ha smontato un container vero, creato
> dal vero strumento, senza toccare gli altri 22.

---

## 1. Purpose & architecture

`hermes-agent` 0.19.0 (il motore di Momo) ha già un ambiente sandbox Docker
completo in `tools/environments/docker.py` — verificato leggendo le 1945
righe del file, non le note di rilascio. Il problema non era scriverlo: era
che i suoi **default** non bastano per una LXC che ospita anche Vaultwarden,
Postgres e Qdrant nello stesso demone Docker.

### Cosa dice il codice, non il piano

Letto dal vivo il 2026-08-04, tre cose che il
[PIANO_MOMO_PROGRAMMATORE](../00_overview/PIANO_MOMO_PROGRAMMATORE.md) dava
per scontate e non lo erano:

| Assunto nel piano | Cosa fa davvero il codice |
|---|---|
| "l'egress proxy è già acceso" | `_egress_proxy_args_for_docker()` (`docker.py:369-527`) esiste, ma è **spento di default** (`proxy.enabled` assente ⇒ nessuna protezione, silenziosamente) **e** richiede rete attiva verso `host.docker.internal` — cioè è strutturalmente incompatibile con "niente rete": non si può avere "solo il proxy, niente LAN" con questo codice da solo |
| "`reap_orphan_containers()` è il teardown" | tocca **solo** i container `status=exited` (`docker.py:154-156,177`). Ogni sandbox parte con `sleep infinity` e **non termina mai da sola** (`docker.py:1428`, commento esplicito "no fixed lifetime — idle reaper handles cleanup" — quell'"idle reaper" non esiste nei due file). Un tetto di durata per un container *in esecuzione* va scritto da zero |
| "l'etichetta protegge il teardown" | `reap_orphan_containers()` filtra per **label soltanto**, nessun registro incrociato (`_load_json_store` non è mai chiamata in `docker.py`). Senza passare esplicitamente `profile_filter`, spazzerebbe via qualunque container **di qualunque programma sull'host** che abbia per coincidenza `hermes-agent=1` |
| "niente LAN di default" | il costruttore ha `network: bool = True` come default (`docker.py:836`, confermato anche in `code_execution_tool.py:779`, `file_tools.py:1056`, `terminal_tool.py:1584` — tutti e tre leggono `config.get("docker_network", True)`). Con `network=True` **non viene passato nessun flag `--network`**: il container finisce sulla bridge Docker normale, con NAT abilitato verso tutto ciò che l'host raggiunge — LAN 192.168.1.0/24 inclusa |

Una cosa che invece **regge** ed è stata verificata come sicura: i 19+
servizi già su LXC 102 (Vaultwarden, Postgres, Qdrant, Forgejo, ...) vivono
ciascuno sulla propria rete Docker di progetto (`vaultwarden_default`,
`hermes-memory_default`, `forgejo_default`, ...), tutte reti bridge separate.
Una sandbox sulla bridge di default **non li raggiunge per IP di
container** — il buco era solo l'uscita via NAT verso l'host e la LAN, non
i container fratelli.

E `terminal.credential_files` — il meccanismo che monta credenziali dentro
la sandbox (`tools/credential_files.py`) — è **vuoto di default** e ha già
una protezione contro il traversal (`register_credential_file`, righe
64-148: rifiuta path assoluti e `../`, contenimento dentro `HERMES_HOME`).
Non monta mai `/root/sovereign-secrets` per costruzione, perché quel path
non è dentro `HERMES_HOME` (`/opt/momo/home/.hermes`). Resta un punto da
tenere a mente per P4 (skills): un file *dentro* `HERMES_HOME` ma sensibile
(`.env`, `config.yaml`) potrebbe teoricamente essere dichiarato da una skill
come credenziale — per questo P4 richiede revisione umana delle skill prima
dell'attivazione, non fiducia nel containment da solo.

### La gabbia costruita

```
docker network "momo-sandbox"  172.30.0.0/24, icc=false, bridge dedicata
bridge di DEFAULT di Docker    172.17.0.0/16, dove i container finiscono
                                per davvero oggi (vedi §9-bis)
        │
        ├── sovereign-momo-sandbox-firewall.service (systemd, boot)
        │     crea la rete se manca + impone in DOCKER-USER, per ENTRAMBE
        │     le reti sopra: 192.168.1.0/24 = DROP, eccetto porta 53 verso
        │     192.168.1.50 (AdGuard, il resolver DNS di LXC 102)
        │
        └── sovereign-momo-sandbox-reaper.timer (systemd, ogni 5 min)
              smonta (stop+rm) ogni container con ENTRAMBE le label native
              di hermes-agent, hermes-agent=1 + hermes-profile=default,
              oltre il tetto (default 7200s), running o exited
```

Due livelli indipendenti, entrambi **fuori** dal processo di hermes-agent:
se Momo si blocca o ha un difetto, la regola di rete resta nel kernel e il
guardiano continua a girare come timer separato.

### Correzione del 2026-08-04 (P2): `docker_extra_args` non arriva mai al container

Il progetto originale della gabbia (P1) presumeva di poter attaccare i
container di `execute_code` alla rete dedicata `momo-sandbox` e di poterli
etichettare con `sovereign.momo.sandbox=1`, tutto tramite
`docker_extra_args` nella config di hermes-agent. **Provato dal vivo,
questo non succede.**

`tools/code_execution_tool.py:_get_or_create_env()` (e la stessa funzione
gemella in `tools/file_tools.py`) costruiscono a mano un dizionario
`container_config` da passare a `_create_environment()`:

```python
container_config = {
    "container_cpu": config.get("container_cpu", 1),
    "container_memory": config.get("container_memory", 5120),
    "container_disk": config.get("container_disk", 51200),
    "container_persistent": config.get("container_persistent", True),
    "vercel_runtime": config.get("vercel_runtime", ""),
    "docker_volumes": config.get("docker_volumes", []),
    "docker_run_as_host_user": config.get("docker_run_as_host_user", False),
    "docker_network": config.get("docker_network", True),
}
```

**La chiave `docker_extra_args` (e `docker_env`) non c'è.** `_create_environment()`
in `terminal_tool.py` la leggerebbe correttamente (`cc.get("docker_extra_args", [])`),
ma non la vede mai perché il dizionario che gli arriva non la contiene —
cade sul default silenzioso `[]`. Risultato verificato dal vivo: un
container creato da `execute_code` con `TERMINAL_DOCKER_EXTRA_ARGS`
impostato è finito sulla **bridge di Docker normale** (`172.17.0.0/16`),
senza nessuna etichetta `sovereign.momo.sandbox=1`, esattamente come se
quella variabile non fosse mai stata impostata.

Questo è un difetto nel codice di NousResearch, non nella nostra config —
verificato leggendo il codice, non dedotto da un comportamento strano.
**Non l'abbiamo patchato** (sarebbe una divergenza dal loro core, da
ripagare a ogni aggiornamento — vedi [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md)
sul perché si evitano). Lo abbiamo aggirato dal lato infrastruttura: il
firewall blocca **entrambe** le reti (la dedicata E la bridge di default),
e il guardiano cerca le etichette che hermes-agent scrive **davvero**
(`hermes-agent=1` + `hermes-profile=default`), non quella nostra che non
arriva mai. Se un giorno NousResearch corregge il bug e i container
iniziano davvero ad attaccarsi a `momo-sandbox`, il firewall li blocca lo
stesso — nessuna delle due strade lascia un buco.

## 2. Target & sizing

Nessun processo permanente pesante. La rete Docker è un oggetto passivo. Il
guardiano (`sovereign-momo-sandbox-reaper.py`) è uno script Python di sola
libreria standard che gira 1 volta ogni 5 minuti, vita di poche centinaia di
millisecondi, chiuso subito (`Type=oneshot`). Il costo vero è quello dei
container sandbox stessi, che P1 non crea se non per i test — P2 deciderà
CPU/memoria per task.

## 3. Install / deployment

```bash
# i tre file dentro LXC 102, in /opt/sovereign-momo-sandbox/
pct push 102 scripts/sovereign-momo-sandbox-firewall.sh \
  /opt/sovereign-momo-sandbox/sovereign-momo-sandbox-firewall.sh
pct push 102 scripts/sovereign-momo-sandbox-reaper.py \
  /opt/sovereign-momo-sandbox/sovereign-momo-sandbox-reaper.py
pct exec 102 -- chmod 750 /opt/sovereign-momo-sandbox/sovereign-momo-sandbox-firewall.sh \
  /opt/sovereign-momo-sandbox/sovereign-momo-sandbox-reaper.py

# le tre unit systemd
pct push 102 scripts/sovereign-momo-sandbox-firewall.service /etc/systemd/system/sovereign-momo-sandbox-firewall.service
pct push 102 scripts/sovereign-momo-sandbox-reaper.service /etc/systemd/system/sovereign-momo-sandbox-reaper.service
pct push 102 scripts/sovereign-momo-sandbox-reaper.timer /etc/systemd/system/sovereign-momo-sandbox-reaper.timer

pct exec 102 -- bash -lc '
  systemctl daemon-reload
  systemctl enable --now sovereign-momo-sandbox-firewall.service
  systemctl enable --now sovereign-momo-sandbox-reaper.timer
'
```

Variabili d'ambiente:

| Variabile | Default | Effetto | Dove |
|---|---|---|---|
| `MOMO_SANDBOX_NETWORK` | `momo-sandbox` | nome della rete Docker dedicata | `sovereign-momo-sandbox-firewall.sh` |
| `MOMO_SANDBOX_SUBNET` | `172.30.0.0/24` | subnet della rete (scelta libera fra quelle non usate: gli altri stack usano `172.18-172.29/16`) | idem |
| `MOMO_SANDBOX_BRIDGE` | `momo-sbx0` | nome dell'interfaccia Linux della rete | idem |
| `MOMO_SANDBOX_LAN` | `192.168.1.0/24` | cosa la sandbox non deve raggiungere | idem |
| `MOMO_SANDBOX_TTL_SECONDS` | `7200` (2h) | tetto di durata, **stimato, non misurato**: nessun task reale di P2 esiste ancora per calibrarlo | `sovereign-momo-sandbox-reaper.service` |

**Correzione**: `docker_network` in hermes-agent è un **booleano**
(`true`/`false`), non il nome di una rete — controlla solo se passare
`--network=none` (isolamento totale, niente Internet) o niente flag
(bridge di Docker, oggi quella di default per il bug di §1). **Non esiste,
in questa versione di hermes-agent, un modo da config.yaml per attaccare
`execute_code` alla rete `momo-sandbox`** — il canale previsto
(`docker_extra_args`) è quello che non arriva mai al container (§1). Per
questo il firewall protegge entrambe le reti, e non serve più nessuna label
custom da iniettare: il guardiano usa le label native di hermes-agent.

**Come si prova `execute_code` oggi, controllato, senza toccare la config
permanente di Momo**: variabili d'ambiente `TERMINAL_*` sul singolo
comando, non su `config.yaml` — così restano scoped al solo processo di
test, e il Momo che risponde su Telegram non le vede mai:
```bash
export HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes
export TERMINAL_ENV=docker
export TERMINAL_DOCKER_IMAGE="nikolaik/python-nodejs:python3.11-nodejs20"
export TERMINAL_DOCKER_VOLUMES='[]'                    # niente segreti
export TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES=false  # isolamento per processo
export TERMINAL_CONTAINER_MEMORY=2048 TERMINAL_CONTAINER_DISK=10240 TERMINAL_CONTAINER_CPU=1
/opt/momo/venv/bin/hermes -z "<compito>" -t code_execution --yolo
```
Perché **non** serve più passare `docker_network`/`docker_extra_args`: dato
che il container finisce comunque sulla bridge di default (il bug di §1),
e quella rete è già bloccata verso la LAN dal firewall host, l'isolamento
regge senza bisogno di nominare la rete dedicata. Il §12 spiega perché
questo NON è ancora acceso in modo permanente per la Momo che risponde su
Telegram/console.

## 4. DNS / domain names / alias

Nessuno. La rete `momo-sandbox` non è raggiungibile dalla LAN per
costruzione (è proprio il suo scopo) e non pubblica porte verso l'esterno.

## 5. Nginx Proxy Manager (NPM)

Nessun host. Non è un servizio con un frontend.

## 6. Homepage & Uptime Kuma

- **Homepage**: nessuna tessera.
- **Uptime Kuma**: nessun monitor dedicato per ora. Il segnale da guardare
  sono i log di systemd: `journalctl -u sovereign-momo-sandbox-reaper.service`
  (un ciclo ogni 5 minuti, silenzioso se non c'è niente da smontare) e
  `journalctl -u sovereign-momo-sandbox-firewall.service` (una riga sola, ad
  ogni boot). Da considerare per P10 (cronjob): un controllo giornaliero che
  la regola DOCKER-USER sia ancora presente.

## 7. Backup & restore

Nessuno stato proprio da salvare: la rete Docker e le regole iptables si
ricreano dagli script (idempotenti) in meno di un secondo. Gli script stessi
sono nel repository Git, come tutto il resto.

## 8. Rollback

```bash
pct exec 102 -- bash -lc '
  systemctl disable --now sovereign-momo-sandbox-reaper.timer
  systemctl disable --now sovereign-momo-sandbox-firewall.service
  # la regola iptables muore con il servizio disabilitato solo al prossimo
  # riavvio di dockerd/della LXC; per toglierla subito:
  iptables -D DOCKER-USER -s 172.30.0.0/24 -d 192.168.1.0/24 \
    -m comment --comment "momo-sandbox-guard: niente LAN dalla sandbox" -j DROP
  docker network rm momo-sandbox   # solo se nessun container la usa ancora
'
```
Nessun impatto sui 22 servizi esistenti: nessuno di loro usa la rete
`momo-sandbox` o le label del guardiano.

## 9. Verifica di funzionamento

Provato dal vivo il 2026-08-04, non dedotto:

```bash
# 1. la rete esiste, isolamento inter-container attivo
pct exec 102 -- docker network inspect momo-sandbox \
  --format 'subnet={{range .IPAM.Config}}{{.Subnet}}{{end}} icc={{index .Options "com.docker.network.bridge.enable_icc"}}'
# atteso: subnet=172.30.0.0/24 icc=false

# 2. la regola firewall è al suo posto
pct exec 102 -- iptables -n -L DOCKER-USER --line-numbers | grep momo-sandbox-guard

# 3. tentativo di evasione vero, container di prova sulla rete dedicata
pct exec 102 -- docker run -d --rm --name momo-sbx-test --network momo-sandbox \
  --label hermes-agent=1 --label sovereign.momo.sandbox=1 \
  nikolaik/python-nodejs:python3.11-nodejs20 sleep 300

# verso la LAN (host Proxmox, LXC 101, il PC): deve fare timeout
pct exec 102 -- docker exec momo-sbx-test curl -sS --max-time 4 http://192.168.1.150 -o /dev/null -w '%{http_code}\n'
# atteso: 000 (connection timed out)

# verso Internet: deve riuscire (serve a pip/npm/apt in P2)
pct exec 102 -- docker exec momo-sbx-test curl -sS --max-time 6 https://pypi.org -o /dev/null -w '%{http_code}\n'
# atteso: 200

# docker.sock e segreti: devono essere assenti
pct exec 102 -- docker exec momo-sbx-test ls /var/run/docker.sock /root/sovereign-secrets
# atteso: "No such file or directory" per entrambi

pct exec 102 -- docker rm -f momo-sbx-test

# 4. il teardown, su un caso vero (non un dry-run)
pct exec 102 -- bash -lc 'MOMO_SANDBOX_TTL_SECONDS=1 python3 /opt/sovereign-momo-sandbox/sovereign-momo-sandbox-reaper.py'
# atteso: "SCADUTO" poi "smontato" per il container di test, "fatto: 1 container smontati"
# e il conteggio totale dei container attivi torna a quello di prima (nessun altro toccato)
```

Risultato del 2026-08-04: **tutti e quattro i controlli passati**. Quattro
bersagli LAN (host Proxmox `.150`, la LXC stessa via IP `.52`, Authentik
`.51`, il PC `.100`) tutti in timeout; Internet raggiunto (`200`); nessun
mount di `docker.sock` né di `/root/sovereign-secrets`; il guardiano ha
smontato esattamente 1 container su 23 totali, gli altri 22 (Vaultwarden,
Forgejo, Postgres compresi) intatti dopo.

**Non ancora provato** (richiede una LXC riavviata per davvero, non solo
`systemctl restart docker`): che la regola sopravviva a un riavvio completo
della LXC 102. Il servizio usa lo stesso schema (`After=docker.service`,
`WantedBy=multi-user.target`) di `sovereign-omniroute-firewall.service`, già
in produzione da giorni con quello schema — ma "stesso schema" non è "stesso
test", e va scritto qui finché non viene misurato al prossimo riavvio vero.

## 9-bis. Verifica P2: lo stesso controllo, attraverso il vero strumento

Il §9 prova la gabbia da fuori (un container lanciato a mano). Il 2026-08-04
è stata provata anche da **dentro il vero percorso**: un messaggio vero a
`hermes -z`, il modello vero che chiama `execute_code`, uno script Python
vero che il modello ha scritto lui stesso per sondare la rete.

```bash
export HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes
export TERMINAL_ENV=docker
export TERMINAL_DOCKER_IMAGE="nikolaik/python-nodejs:python3.11-nodejs20"
export TERMINAL_DOCKER_VOLUMES='[]'
export TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES=false
/opt/momo/venv/bin/hermes -z "Usa execute_code per provare a raggiungere 192.168.1.51, 192.168.1.150, 192.168.1.52:8093 e https://pypi.org, e riportami i codici HTTP" -t code_execution --yolo
```

Primo tentativo (prima della correzione di §1): il container è finito sulla
bridge di default **senza** la rete dedicata. Il bersaglio LAN scelto per il
primo test (porta 80 sul Proxmox host) ha dato un rifiuto immediato — non un
timeout — perché **nessun servizio ascolta lì**, non perché il firewall
bloccasse qualcosa. Una prova che sembra passare per il motivo sbagliato è
peggio di una prova che fallisce chiaramente: è quella che ha portato a
scoprire il bug di `docker_extra_args`.

Rifatta con bersagli che rispondono davvero (Authentik 443, il backend di
Momo stesso su 8093) dopo aver corretto il firewall per coprire anche la
bridge di default:

| Bersaglio | Servizio reale | Risultato |
|---|---|---|
| `https://192.168.1.51` | Authentik (LXC 101), TLS attivo | timeout (28) |
| `https://192.168.1.150` | host Proxmox | timeout (28) |
| `http://192.168.1.52:8093` | il backend di Momo stesso | timeout (28) |
| `https://pypi.org` | Internet | **200** |

Il primo giro di questo test ha anche rivelato che la risoluzione DNS si
rompeva insieme al blocco LAN — `/etc/resolv.conf` di LXC 102 punta a
`192.168.1.50` (AdGuard), dentro la stessa LAN bloccata. Corretto con
un'eccezione mirata (solo porta 53, solo verso quell'indirizzo) prima delle
regole di blocco generali — vedi il firewall script.

Il guardiano TTL è stato provato sullo **stesso container reale**: visto
"vivo" con il tetto normale (dry-run), poi smontato per davvero forzando un
tetto di 1 secondo, tornando esattamente al conteggio di container di
prima. Nessuna label custom coinvolta: ha funzionato sulle sole label native
`hermes-agent=1` + `hermes-profile=default`.

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Un container sandbox raggiunge comunque la LAN | la regola firewall manca su UNA delle due reti (dedicata o bridge di default) — controllare quale rete usa davvero il container, per via del bug di §1 | `docker inspect <container> --format '{{.NetworkSettings.Networks}}'` per sapere la rete, poi `iptables -n -L DOCKER-USER \| grep momo-sandbox-guard` per confermare che quella subnet ha una regola DROP |
| Il guardiano non smonta mai un container che dovrebbe essere scaduto | il profilo non è `default` (raro, ma possibile se la config di hermes-agent cambia) | `docker inspect <container> --format '{{.Config.Labels}}'`, guardare `hermes-profile`; se diverso da `default`, impostare `MOMO_SANDBOX_PROFILE` nel servizio del guardiano |
| Il guardiano smonta un container ancora in uso | il tetto (`MOMO_SANDBOX_TTL_SECONDS`, default 7200s) è troppo basso per il task reale | alzarlo in `sovereign-momo-sandbox-reaper.service`; il numero attuale è una stima, non una misura — va ricalibrato quando esiste un task reale da cronometrare |
| Dopo un riavvio della LXC, la regola firewall è sparita | il servizio `sovereign-momo-sandbox-firewall.service` non è partito, o `network-online.target` non è stato raggiunto in tempo | `systemctl status sovereign-momo-sandbox-firewall.service`; se `enabled` ma non `active`, controllare `journalctl -u sovereign-momo-sandbox-firewall.service -b` |
| Il proxy egress di hermes-agent non parte insieme alla rete isolata | conflitto strutturale del codice: `--network=none` blocca anche `host.docker.internal`, che il proxy richiede | non impostare mai `docker_network: false` se serve il proxy — ma dato che `docker_extra_args` non funziona comunque (§1), oggi il proxy egress e la rete dedicata sono entrambi fuori uso: l'isolamento regge solo grazie al firewall sulla bridge di default |
| La risoluzione DNS fallisce dentro la sandbox (`Resolving timed out`) | la regola generale blocca anche la porta 53 verso il resolver DNS di LXC 102 (AdGuard, `192.168.1.50`), che sta dentro la LAN bloccata | verificare che le 4 regole `RETURN ... dpt:53` esistano E siano SOPRA le regole `DROP` in `iptables -n -L DOCKER-USER --line-numbers \| grep momo-sandbox-guard` (l'ordine conta: l'ultima inserita finisce in cima) |
| Un container di test resta in piedi più a lungo del previsto anche con `TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES=false` | osservato dal vivo il 2026-08-04: il container non viene rimosso immediatamente all'uscita del processo `hermes -z` come il commento del codice lascia intendere | non fidarsi di quel flag come unico meccanismo di pulizia — il guardiano TTL resta il livello di sicurezza autoritativo, non un backup |

## 11. Official Sources

- Codice letto per intero il 2026-08-04, non le note di rilascio:
  `/opt/hermes-agent-study/tools/environments/docker.py` (1945 righe),
  `tools/environments/base.py` (1187 righe), `tools/credential_files.py`
  (525 righe) — tutti su LXC 102
- Riferimenti agli stessi default in `tools/code_execution_tool.py:779`,
  `tools/file_tools.py:1056`, `tools/terminal_tool.py:1418,1490,1584`
- `scripts/sovereign-omniroute-firewall.sh` — lo schema di firewall
  DOCKER-USER riusato qui, già in produzione
- [PIANO_MOMO_PROGRAMMATORE](../00_overview/PIANO_MOMO_PROGRAMMATORE.md) —
  l'architettura a quattro anelli e l'ordine P1-P10
- [PIANO_MASTER](../00_overview/PIANO_MASTER.md) §2-bis voce 19

## 12. Perché `code_execution` non è ancora acceso in modo permanente

Questo è il motivo per cui P2 è "provato" ma non "acceso": non è rimasto a
metà per mancanza di tempo, è una decisione che serve al proprietario prima
di proseguire, perché tocca una cosa che Momo usa **già, oggi, per davvero**.

### Il conflitto, trovato leggendo il codice

`tools/file_tools.py` registra `read_file`, `write_file`, `patch`,
`search_files` sotto **`toolset="file"`** — lo stesso toolset già acceso
nella config di Momo (`toolsets: [sovereign, file, memory, clarify, todo,
vision]`), verificato in uso in almeno 7 sessioni reali salvate su disco
(`grep` sui `session dump` in `/opt/momo/home/.hermes/sessions/`).

Questi strumenti e `execute_code` **condividono lo stesso meccanismo di
scelta dell'ambiente** (`_get_env_config()`/`env_type`, la stessa funzione
per entrambi) e **lo stesso identificatore di sessione**: l'agente di primo
livello (quello che risponde su Telegram/console) passa sempre
`task_id=None`, che `_resolve_container_task_id()` collassa sempre su
`"default"` — per costruzione, per far condividere una sola shell alle
chiamate di una stessa conversazione. Non esiste, in questa versione di
hermes-agent, un modo per dire "`file` resta locale, `execute_code` va nella
sandbox" nella STESSA sessione: sono la stessa cosa vista da due strumenti.

**Conseguenza verificata leggendo `_resolve_path_for_task()`**: se si
imposta `terminal.backend: docker` in modo permanente (invece che solo per
il singolo comando di test, come in §9-bis), ogni chiamata a `read_file`
con un percorso assoluto dell'host (es. `/opt/momo/home/.hermes/SOUL.md`,
o un file del vault) verrebbe risolta e letta **dentro il container**, che
non ha quei percorsi montati per costruzione (§1: niente segreti). Il
risultato sarebbe "file non trovato" su richieste che oggi funzionano.

Ho verificato anche le strade per evitarlo, e nessuna regge senza altro
lavoro:
- il hook `pre_tool_call` (quello che il plugin `sovereign_tools` usa per
  `guard_private`) è un **cancello**, non un traduttore: può solo permettere
  o bloccare una chiamata (`model_tools.py:1245-1268`,
  `resolve_pre_tool_block()` ritorna un messaggio di blocco oppure `None`),
  non può cambiare il `task_id` prima che il vero strumento parta;
- `register_task_env_overrides(task_id, {...})` esiste, ma è pensato per gli
  ambienti di RL/benchmark (Atropos), che passano un `task_id` proprio
  PRIMA che l'agente parta. Registrarlo su `"default"` non isola niente,
  perché `"default"` resta lo stesso contenitore condiviso da tutte le
  chiamate della sessione.

### Le tre strade, con il costo vero di ciascuna

| Strada | Cosa costa | Cosa si ottiene |
|---|---|---|
| **A. Accendere `terminal.backend: docker` in modo permanente**, e montare in sola lettura dentro la sandbox le SOLE cartelle che `file` usa oggi per davvero (da misurare quali, guardando le sessioni salvate) | rompe la separazione netta di P1 ("niente segreti") quel poco che serve a far funzionare `read_file`; se si sbaglia la lista delle cartelle, si rompe qualcosa che oggi funziona | Momo può mescolare liberamente chat, memoria e scrittura di codice nella stessa conversazione, come chiede il piano originale |
| **B. Un contesto di codice separato**: `execute_code` acceso SOLO in un flusso dedicato (un comando apposito, non la chat normale), mai insieme a `file`/`memory` nella stessa sessione | Momo non può, a metà chat, decidere da solo di scrivere ed eseguire uno script — serve un comando esplicito che apra "una sessione di programmazione" | zero rischio per la memoria/vault di oggi, zero lavoro aggiuntivo su hermes-agent |
| **C. Un correttivo scritto da noi** (un plugin che aggiunge quello che manca: `docker_extra_args` nel `container_config` di `code_execution_tool.py`, e un vero meccanismo di isolamento per `task_id`) | è una divergenza vera dal loro core, da ripagare ad ogni aggiornamento di NousResearch — la stessa categoria di costo descritta in [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) | l'unica strada che risolve il problema invece di aggirarlo, ma è settimane di lavoro, non ore |

Fino a una decisione, `code_execution` resta **utilizzabile solo nel modo
provato in §9-bis**: un comando `hermes -z` a parte, con le variabili
`TERMINAL_*` sul singolo comando, mai nella config permanente che serve la
Momo di Telegram. Questo di per sé è già un risultato reale — un operatore
umano (o uno script futuro, es. la pipeline Forgejo di P6) può invocarlo in
sicurezza oggi — ma non è ciò che il piano intende con "Momo che programma"
dentro la conversazione normale.
