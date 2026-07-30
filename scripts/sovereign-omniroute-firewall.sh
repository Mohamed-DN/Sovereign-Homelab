#!/usr/bin/env bash
set -euo pipefail

# Restrict the OmniRoute ports on LXC 102 to the hosts that actually need them.
# Run inside LXC 102 (the sovereign-omniroute-firewall.service unit does this at
# every boot, because iptables rules do not survive a restart).
#
# Why this exists. Docker publishes 20128 on 0.0.0.0, so every device on the
# LAN could reach the gateway's own login form over plain HTTP. The dashboard
# password is the estate's shared app password, and the dashboard manages the
# provider API keys - so "anyone on the WiFi who knows the shared password"
# was a real path to the gateway. This is the same hole that Ollama's installer
# left open on the PC, in a different place.
#
# A published Docker port cannot be filtered with a normal INPUT rule: the
# packets are DNAT'ed and traverse FORWARD, so the hook is DOCKER-USER.
# Traffic from this container's own loopback (Hermes -> 127.0.0.1:20128) does
# not pass through DOCKER-USER and stays unaffected.

PORTS="${PORTS:-20128,20132}"
# NPM terminates TLS and carries the SSO gate; the PC is where Claude Code runs;
# the Proxmox host runs the maintenance scripts.
ALLOW="${ALLOW:-192.168.1.50,192.168.1.100,192.168.1.150}"
CHAIN=DOCKER-USER

command -v iptables >/dev/null || { echo "iptables missing" >&2; exit 1; }
iptables -n -L "$CHAIN" >/dev/null 2>&1 || { echo "$CHAIN chain absent - is docker running?" >&2; exit 1; }

# Idempotent: drop any rule this script previously inserted, then re-add.
while iptables -n -L "$CHAIN" --line-numbers | grep -q "omniroute-guard"; do
  line=$(iptables -n -L "$CHAIN" --line-numbers | awk '/omniroute-guard/ {print $1; exit}')
  iptables -D "$CHAIN" "$line"
done

# Order matters: the accepts go in first, then the catch-all drop, and each
# insert at position 1 pushes the previous one down - so the drop is inserted
# first and ends up last.
iptables -I "$CHAIN" 1 -p tcp -m multiport --dports "$PORTS" \
  -m comment --comment "omniroute-guard: deny everyone else" -j DROP

IFS=',' read -ra hosts <<< "$ALLOW"
for host in "${hosts[@]}"; do
  iptables -I "$CHAIN" 1 -p tcp -s "$host" -m multiport --dports "$PORTS" \
    -m comment --comment "omniroute-guard: allow $host" -j RETURN
done

echo "omniroute-guard applied on ports $PORTS for $ALLOW"
iptables -n -L "$CHAIN" --line-numbers | grep omniroute-guard || true
