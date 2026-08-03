#!/usr/bin/env bash
set -euo pipefail

# Restringe la porta 3001 di Uptime Kuma su LXC 101 a chi ne ha davvero
# bisogno. Gira dentro LXC 101 (lo unit sovereign-kuma-firewall.service lo
# rifà a ogni avvio, perché le regole iptables non sopravvivono a un riavvio).
#
# PERCHÉ ESISTE, e non è teoria. Uptime Kuma qui ha `disableAuth = true`:
# l'autenticazione è delegata al forward-auth di Authentik davanti a
# `status.internal`. Ma Docker pubblica la 3001 su 0.0.0.0, e quel percorso
# NON passa da NPM. Verificato il 2026-08-03 collegandosi col socket nudo
# dall'host: senza fare login sono arrivati subito `monitorList`,
# `apiKeyList`, `notificationList` e `certInfo`. `checkLogin()` pretende
# `socket.userID`, ma con disableAuth il server lo assegna da solo — quindi
# chiunque sulla LAN raggiungesse la 3001 era admin, con lettura E scrittura
# su tutti i monitor.
#
# È lo STESSO buco già trovato due volte in questa casa: l'installer di
# Ollama sul PC, e la porta di OmniRoute su LXC 102 (vedi
# sovereign-omniroute-firewall.sh, da cui questo script è modellato). Tre
# volte lo stesso schema: un servizio che si fida della rete perché "tanto
# c'è il proxy davanti", e una porta pubblicata che il proxy non attraversa.
#
# Una porta pubblicata da Docker non si filtra con una normale regola INPUT:
# i pacchetti sono già stati DNAT-ati e passano da FORWARD, quindi l'aggancio
# è DOCKER-USER.

PORTS="${PORTS:-3001}"
# Chi deve poter entrare, e perché ognuno:
#   192.168.1.50   NPM: termina il TLS e porta il gate SSO. È la via normale.
#   192.168.1.150  l'host Proxmox: ci girano gli script di manutenzione
#                  (sovereign-kuma-monitor.py, dove stanno le credenziali).
#   172.16.0.0/12  le reti Docker di questo container: Homepage legge il
#                  widget come `http://uptime-kuma:3001`, da container a
#                  container. Dimenticarle spegne il riquadro "Fleet Health"
#                  senza che nessuno colleghi le due cose.
ALLOW="${ALLOW:-192.168.1.50,192.168.1.150,172.16.0.0/12}"
CHAIN=DOCKER-USER
MARCA="kuma-guard"

command -v iptables >/dev/null || { echo "iptables mancante" >&2; exit 1; }
iptables -n -L "$CHAIN" >/dev/null 2>&1 || { echo "catena $CHAIN assente: docker è acceso?" >&2; exit 1; }

# Idempotente: prima toglie le regole che questo script ha messo in passato,
# poi le rimette. Senza, ogni riavvio ne aggiungerebbe un altro strato.
while iptables -n -L "$CHAIN" --line-numbers | grep -q "$MARCA"; do
  riga=$(iptables -n -L "$CHAIN" --line-numbers | awk -v m="$MARCA" '$0 ~ m {print $1; exit}')
  iptables -D "$CHAIN" "$riga"
done

# L'ordine conta, ed è al contrario di come si legge: ogni inserimento in
# posizione 1 spinge giù il precedente, quindi il DROP va messo per PRIMO
# per finire per ultimo.
iptables -I "$CHAIN" 1 -p tcp -m multiport --dports "$PORTS" \
  -m comment --comment "$MARCA: nega tutti gli altri" -j DROP

IFS=',' read -ra permessi <<< "$ALLOW"
for h in "${permessi[@]}"; do
  iptables -I "$CHAIN" 1 -p tcp -s "$h" -m multiport --dports "$PORTS" \
    -m comment --comment "$MARCA: permetti $h" -j RETURN
done

echo "porta $PORTS ristretta a: $ALLOW"
iptables -n -L "$CHAIN" --line-numbers | grep "$MARCA" || true
