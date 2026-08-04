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
#   - l'immagine e l'etichetta dei container: le mette la config di
#     hermes-agent (docker_network=momo-sandbox, docker_extra_args con
#     --label sovereign.momo.sandbox=1), non questo script.

NETWORK="${MOMO_SANDBOX_NETWORK:-momo-sandbox}"
SUBNET="${MOMO_SANDBOX_SUBNET:-172.30.0.0/24}"
BRIDGE_IFACE="${MOMO_SANDBOX_BRIDGE:-momo-sbx0}"
LAN="${MOMO_SANDBOX_LAN:-192.168.1.0/24}"
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

# Un solo verso basta: il traffico di ritorno di una connessione mai aperta
# non esiste. Chi e' sulla LAN e vuole entrare nella sandbox non ha comunque
# una rotta (172.30.0.0/24 non e' instradata da nessun altro host di casa).
iptables -I "$CHAIN" 1 -s "$SUBNET" -d "$LAN" \
  -m comment --comment "momo-sandbox-guard: niente LAN dalla sandbox" -j DROP

echo "momo-sandbox-guard applicato: $SUBNET non raggiunge $LAN"
iptables -n -L "$CHAIN" --line-numbers | grep momo-sandbox-guard || true
