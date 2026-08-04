# La sandbox di Momo — P1 del piano "Momo che programma"

> **Stato (2026-08-04): P1 fatto e verificato sul vivo.** La gabbia esiste,
> è stata attaccata e non ha ceduto, il teardown ha smontato un container
> vero senza toccare gli altri 22. `code_execution` resta **spento**: questo
> documento copre solo l'anello 1 (la sandbox), non l'accensione del motore
> che ci gira dentro — quella è [P2](../00_overview/PIANO_MOMO_PROGRAMMATORE.md#7-lordine-dei-lavori).

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
        │
        ├── sovereign-momo-sandbox-firewall.service (systemd, boot)
        │     crea la rete se manca + impone in DOCKER-USER:
        │     172.30.0.0/24 -> 192.168.1.0/24 = DROP
        │
        └── sovereign-momo-sandbox-reaper.timer (systemd, ogni 5 min)
              smonta (stop+rm) ogni container con ENTRAMBE le label
              sovereign.momo.sandbox=1 + hermes-agent=1 oltre il tetto
              (default 7200s), running o exited
```

Due livelli indipendenti, entrambi **fuori** dal processo di hermes-agent:
se Momo si blocca o ha un difetto, la regola di rete resta nel kernel e il
guardiano continua a girare come timer separato.

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

**P2 dovrà impostare**, nella config di hermes-agent (`code_execution:` /
`terminal:` in `config.yaml`):
```yaml
docker_network: momo-sandbox      # NON true/false: il nome della rete dedicata
docker_extra_args:
  - "--label"
  - "sovereign.momo.sandbox=1"    # l'etichetta che il guardiano cerca
```
Senza questa label, il guardiano non vede il container e non lo smonta mai.

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

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Un container sandbox raggiunge comunque la LAN | `docker_network` in `config.yaml` non è impostato a `momo-sandbox` (resta il default `true` → bridge normale) | verificare `docker inspect <container> --format '{{.NetworkSettings.Networks}}'`: deve nominare `momo-sandbox`, non `bridge` |
| Il guardiano non smonta mai un container che dovrebbe essere scaduto | manca la label `sovereign.momo.sandbox=1` (il guardiano cerca **entrambe** le label, non basta `hermes-agent=1`) | `docker inspect <container> --format '{{.Config.Labels}}'`; se manca, aggiungere `docker_extra_args` in config come da §3 |
| Il guardiano smonta un container ancora in uso | il tetto (`MOMO_SANDBOX_TTL_SECONDS`, default 7200s) è troppo basso per il task reale | alzarlo in `sovereign-momo-sandbox-reaper.service`; il numero attuale è una stima, non una misura — va ricalibrato quando esiste un task P2 vero da cronometrare |
| Dopo un riavvio della LXC, la regola firewall è sparita | il servizio `sovereign-momo-sandbox-firewall.service` non è partito, o `network-online.target` non è stato raggiunto in tempo | `systemctl status sovereign-momo-sandbox-firewall.service`; se `enabled` ma non `active`, controllare `journalctl -u sovereign-momo-sandbox-firewall.service -b` |
| Il proxy egress di hermes-agent (P2) non parte insieme alla rete isolata | conflitto strutturale del codice: `--network=none` blocca anche `host.docker.internal`, che il proxy richiede. La rete `momo-sandbox` (bridge dedicata, non `none`) risolve questo perché lascia passare l'uscita (bloccata solo verso la LAN dal firewall host), ma se P2 tenta di usare `docker_network: false` invece del nome della rete, il proxy egress smetterà di funzionare | usare sempre il nome `momo-sandbox`, mai `false`, come valore di `docker_network` |

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
