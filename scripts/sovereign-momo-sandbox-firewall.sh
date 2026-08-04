#!/usr/bin/env bash
set -euo pipefail

# La gabbia di rete per la sandbox di Momo (P1 del PIANO_MOMO_PROGRAMMATORE).
# Gira dentro LXC 102. Esegue due cose, entrambe idempotenti:
#   1. crea la rete Docker dedicata "momo-sandbox" (se manca)
#   2. impone in DOCKER-USER il divieto di uscita verso la LAN di casa
#
# Perche' non basta "docker network create" da solo. hermes-agent/tools/
# environments/docker.py, quando il parametro network e' True (il default),
# non passa NESSUN flag --network al comando "docker run": il container
# finisce sulla bridge di Docker, con com.docker.network.bridge.
# enable_ip_masquerade=true. Questo significa NAT verso qualunque cosa
# l'host raggiunga, LAN 192.168.1.0/24 inclusa - anche se i servizi sensibili
# (Vaultwarden, Postgres, Qdrant, Forgejo) stanno su reti Docker separate
# (vaultwarden_default, hermes-memory_default, forgejo_default, ognuna un
# /16 diverso) e quindi NON sono raggiungibili container-a-container dalla
# bridge di default: quella parte e' gia' sicura per costruzione. Il buco
# e' l'uscita verso l'host e la LAN via NAT, non i container fratelli.
#
# Come per omniroute (sovereign-omniroute-firewall.sh): una porta pubblicata
# da Docker o un pacchetto in uscita da un container attraversano FORWARD,
# non INPUT, e la regola va in DOCKER-USER. Le regole iptables non
# sopravvivono al riavvio: il servizio sovereign-momo-sandbox-firewall.service
# le riapplica a ogni boot.
#
# Cosa resta FUORI da questo script, per costruzione:
#   - nessun mount di segreti: quello lo decide la config di hermes-agent
#     (terminal.credential_files), non la rete. Di default e' vuota.
#   - il tetto di durata dei container: lo fa sovereign-momo-sandbox-
#     reaper.py, perche' reap_orphan_containers() di hermes-agent non tocca
#     mai un container "running" (vedi il piano).
#
# CORREZIONE del 2026-08-04, trovata provando P2 dal vivo: il piano
# presumeva che bastasse "docker_extra_args: [--network, momo-sandbox]" in
# config.yaml per attaccare i container alla rete dedicata. NON e' vero.
# tools/code_execution_tool.py:_get_or_create_env() (e la stessa funzione
# in file_tools.py) ricostruiscono un dizionario "container_config" a mano
# e DIMENTICANO la chiave docker_extra_args (e docker_env) - anche se
# _create_environment() la legge correttamente, non arriva mai li' perche'
# il dizionario che gliela dovrebbe passare non ce l'ha. Verificato dal
# vivo: un container creato da execute_code con TERMINAL_DOCKER_EXTRA_ARGS
# impostato e' finito sulla bridge di Docker normale, non su momo-sandbox,
# senza nessuna etichetta sovereign.momo.sandbox=1.
#
# Quindi questo script blocca la LAN per DUE reti, non una: quella dedicata
# (nel caso venga corretto il bug, o per chi la usa via docker run diretto)
# E la bridge di default di Docker (dove finiscono per davvero, oggi, i
# container di execute_code/terminal). La bridge di default non ha nessun
# altro container sopra (verificato: tutti gli altri 22 servizi della LXC
# stanno ciascuno sulla propria rete di progetto docker-compose) quindi
# bloccarla non rompe nulla.

NETWORK="${MOMO_SANDBOX_NETWORK:-momo-sandbox}"
SUBNET="${MOMO_SANDBOX_SUBNET:-172.30.0.0/24}"
BRIDGE_IFACE="${MOMO_SANDBOX_BRIDGE:-momo-sbx0}"
LAN="${MOMO_SANDBOX_LAN:-192.168.1.0/24}"
DEFAULT_BRIDGE_SUBNET="${MOMO_SANDBOX_DEFAULT_BRIDGE_SUBNET:-172.17.0.0/16}"
# /etc/resolv.conf di LXC 102 punta ad AdGuard (LXC 100), dentro la stessa
# LAN che blocchiamo. Senza un'eccezione la sandbox non risolve piu' nessun
# nome - trovato provando P2 dal vivo (pypi.org e' andato in timeout di
# risoluzione, non solo di connessione). Solo la porta 53, solo verso li'.
DNS_SERVER="${MOMO_SANDBOX_DNS_SERVER:-192.168.1.50}"
CHAIN=DOCKER-USER

command -v docker >/dev/null || { echo "docker mancante" >&2; exit 1; }
command -v iptables >/dev/null || { echo "iptables mancante" >&2; exit 1; }
iptables -n -L "$CHAIN" >/dev/null 2>&1 || { echo "catena $CHAIN assente - Docker gira?" >&2; exit 1; }

# --- 1. la rete dedicata, creata una volta, idempotente ---
if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  docker network create \
    --driver bridge \
    --subnet "$SUBNET" \
    --opt "com.docker.network.bridge.name=$BRIDGE_IFACE" \
    --opt "com.docker.network.bridge.enable_icc=false" \
    --label "sovereign.momo.sandbox.network=1" \
    "$NETWORK"
  echo "rete $NETWORK creata su $SUBNET (interfaccia $BRIDGE_IFACE, icc disattivato)"
else
  echo "rete $NETWORK gia' presente, non ricreata"
fi

# --- 2. il divieto verso la LAN, riapplicato a ogni boot ---
# Idempotente: toglie ogni regola con il tag momo-sandbox-guard, poi la
# rimette. Stesso schema di sovereign-omniroute-firewall.sh.
while iptables -n -L "$CHAIN" --line-numbers | grep -q "momo-sandbox-guard"; do
  line=$(iptables -n -L "$CHAIN" --line-numbers | awk '/momo-sandbox-guard/ {print $1; exit}')
  iptables -D "$CHAIN" "$line"
done

# Ordine (ricreato ogni volta togliendo e rimettendo, quindi l'ordine di
# inserimento qui sotto e' l'ordine finale nella catena): prima le eccezioni
# DNS, poi il divieto generale. -I "$CHAIN" 1 mette sempre in testa, quindi
# si inserisce PRIMA il DROP e POI le ACCEPT/RETURN del DNS, cosi' il DNS
# finisce sopra al DROP.
iptables -I "$CHAIN" 1 -s "$SUBNET" -d "$LAN" \
  -m comment --comment "momo-sandbox-guard: niente LAN dalla sandbox" -j DROP

# La stessa regola per la bridge di default: e' li' che i container di
# execute_code/terminal finiscono per davvero, per il bug descritto sopra.
iptables -I "$CHAIN" 1 -s "$DEFAULT_BRIDGE_SUBNET" -d "$LAN" \
  -m comment --comment "momo-sandbox-guard: niente LAN dalla bridge di default" -j DROP

# Eccezione DNS, per entrambe le reti: solo porta 53 verso AdGuard, niente
# altro. Inserita per ultima cosi' finisce sopra ai due DROP.
for subnet in "$SUBNET" "$DEFAULT_BRIDGE_SUBNET"; do
  for proto in udp tcp; do
    iptables -I "$CHAIN" 1 -s "$subnet" -d "$DNS_SERVER" -p "$proto" --dport 53 \
      -m comment --comment "momo-sandbox-guard: DNS verso $DNS_SERVER" -j RETURN
  done
done

echo "momo-sandbox-guard applicato: $SUBNET e $DEFAULT_BRIDGE_SUBNET non raggiungono $LAN (DNS verso $DNS_SERVER escluso)"
iptables -n -L "$CHAIN" --line-numbers | grep momo-sandbox-guard || true
