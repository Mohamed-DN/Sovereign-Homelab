#!/bin/bash
# Registratore delle cadute di Nextcloud - gira DENTRO la VM 120.
#
# PERCHE ESISTE. Da giugno 2026 Nextcloud cade una decina di volte al mese per
# quattro-otto minuti. Uptime Kuma segna DOWN, NPM registra il motivo vero
# ("connect() failed (111: Connection refused)" verso 192.168.1.120:11000) e
# poi tutto torna a posto da solo. L'indagine a posteriori del 2026-08-03 ha
# escluso quasi tutto:
#   * i contenitori NON si riavviano (8 ore di vita durante un episodio);
#   * NON e' il backup: quello gira alle 03:22 e dura 3 minuti, mentre le
#     cadute sono a ore sparse (08:56, 23:25, 15:43, 21:24...);
#   * niente OOM, 1,9 GB usati su 10, Docker mai ricaricato, zero servizi
#     falliti, nessun firewall sulla VM, nessun blocco di CrowdSec.
# Tutto pulito DOPO. Il che vuol dire che serve guardare DURANTE.
#
# LA DOMANDA CHE DECIDE, e a cui questo script risponde: quando la porta
# rifiuta da fuori, risponde ancora da DENTRO la VM?
#   * dentro SI e fuori NO  -> il problema e' la pubblicazione della porta
#     (regole NAT di Docker sparite, docker-proxy morto). Apache sta bene.
#   * dentro NO e fuori NO  -> e' Apache che non ascolta piu'.
# Sono due guasti diversi con due rimedi diversi, e senza questa distinzione
# si tira a indovinare. Per questo si prova PRIMA da dentro e POI da fuori,
# e si scrive sempre l'esito di entrambe.
#
# Non fa NIENTE oltre a guardare e scrivere: non riavvia, non ripara. Un
# rimedio automatico su una causa non ancora capita nasconde le prove.

set -u
PORTA=11000
FUORI=192.168.1.120
DIARIO=/var/log/nextcloud-flap.log
CARTELLA=/var/log/nextcloud-flap.d

mkdir -p "$CARTELLA"

sonda() {  # $1 = indirizzo; stampa il codice HTTP, 000 se non si collega
  curl -s -o /dev/null -m 4 -w '%{http_code}' "http://$1:$PORTA/" 2>/dev/null || echo 000
}

dentro=$(sonda 127.0.0.1)
fuori=$(sonda "$FUORI")

# Entrambe a posto: una riga sola nel diario, e basta. Il diario serve anche a
# dimostrare che il registratore era acceso quando NON e' successo niente --
# senza, un file vuoto e "non e' successo nulla" si somigliano troppo.
if [ "$dentro" != "000" ] && [ "$fuori" != "000" ]; then
  echo "$(date -Is) ok dentro=$dentro fuori=$fuori" >> "$DIARIO"
  exit 0
fi

QUANDO=$(date -u +%Y%m%dT%H%M%SZ)
F="$CARTELLA/$QUANDO.txt"
echo "$(date -Is) CADUTA dentro=$dentro fuori=$fuori -> $F" >> "$DIARIO"

{
  echo "== caduta del $(date -Is)"
  echo "== sonda dentro la VM (127.0.0.1): $dentro"
  echo "== sonda da fuori   ($FUORI): $fuori"
  echo
  echo "== chi ascolta sulla $PORTA (se qui non c'e' niente, non e' Apache che e' morto:"
  echo "==  e' la pubblicazione della porta ad essere sparita)"
  ss -lntp 2>/dev/null | grep -E ":$PORTA|LISTEN" | head -20
  echo
  echo "== regole NAT di Docker per la $PORTA (devono esserci DNAT e MASQUERADE)"
  iptables-save -t nat 2>/dev/null | grep -E "$PORTA" || echo "  NESSUNA REGOLA -- e' questa la causa"
  echo
  echo "== docker-proxy vivo?"
  ps aux 2>/dev/null | grep -E "docker-proxy.*$PORTA" | grep -v grep || echo "  nessun docker-proxy sulla $PORTA"
  echo
  echo "== stato dei contenitori (se sono 'Up' da ore, non si sono riavviati)"
  docker ps -a --format '{{.Names}}|{{.Status}}' 2>/dev/null
  echo
  echo "== ultime righe di Apache"
  docker logs nextcloud-aio-apache --tail 25 2>&1
  echo
  echo "== eventi Docker degli ultimi 10 minuti"
  docker events --since 10m --until 1s --filter type=container \
    --format '{{.Time}} {{.Actor.Attributes.name}} {{.Action}}' 2>/dev/null | tail -40
  echo
  echo "== memoria e carico"
  free -m 2>/dev/null; uptime
  echo
  echo "== kernel (OOM, cadute di rete)"
  dmesg -T 2>/dev/null | tail -25
} > "$F" 2>&1

exit 0
