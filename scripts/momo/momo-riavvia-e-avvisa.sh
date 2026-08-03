#!/usr/bin/env bash
# Riavvia momo-gateway e AVVISA quando e' tornato. Gira su LXC 102, chiamato
# da un timer transitorio che il comando /motore programma prima di rispondere.
#
# PERCHE ESISTE. Cambiare motore richiede di riavviare il gateway, e il
# comando /motore gira dentro quel gateway: se riavviasse subito ucciderebbe
# la propria risposta. Quindi risponde «mi riavvio», e questo script fa il
# resto. Mancava pero' la seconda meta': l'avviso di RITORNO. Mohamed il
# 2026-08-03: «mi da' l'avviso di shutting down ma non quello di riapertura».
# Un servizio che dice «torno subito» e poi non dice piu' niente lascia chi
# aspetta a indovinare se e' tornato o se e' morto -- e la prova, ogni volta,
# e' scrivergli e vedere se risponde.
#
# `hermes send` parla a Telegram con il token del bot, SENZA passare
# dall'agente e senza bisogno che il gateway sia acceso: e' esattamente cio'
# che serve qui, perche' il messaggio nasce mentre il gateway non c'e' ancora.

set -uo pipefail

SERVIZIO="${SERVIZIO:-momo-gateway}"
HERMES="${HERMES:-/opt/momo/venv/bin/hermes}"
ATTESA_MAX="${ATTESA_MAX:-90}"

# IMPOSTATI, non messi come valore di riserva. Con `${HOME:-...}` un HOME gia'
# presente vince -- e quando systemd esegue questo script HOME e' /root, dove
# non c'e' nessuna configurazione di Momo: `hermes send` non trovava il token e
# l'avviso non partiva. Il valore di riserva sembra prudente e qui e' il difetto.
export HOME=/opt/momo/home
export HERMES_HOME=/opt/momo/home/.hermes

systemctl restart "$SERVIZIO"

# Non basta che systemd lo dia per «active»: il gateway si collega a Telegram
# dopo, e un messaggio mandato prima arriverebbe mentre lui non ascolta
# ancora.
#
# COME SI CAPISCE CHE E' PRONTO, dopo due tentativi sbagliati:
#   1. «Started momo-gateway.service» -> e' systemd, compare all'istante:
#      l'attesa finiva in 0 secondi. Un'attesa che non aspetta e' peggio di
#      nessuna attesa, perche' dal risultato sembra che abbia funzionato;
#   2. «Connected to Telegram» nei log -> quella riga NON ESISTE a questo
#      livello: il gateway registra solo i WARNING, e l'ultimo che scrive e'
#      «Connecting… (attempt 1/8)». L'attesa arrivava al tetto ogni volta.
# Il segnale vero non e' nei log ma nelle CONNESSIONI: quando il gateway
# ascolta, il suo processo tiene una connessione stabilita verso la 443 di
# Telegram (149.154.x). Questo e' un fatto osservabile, non una riga di testo
# che puo' cambiare con la prossima versione o con il livello di log.
inizio=$(date +%s)
collegato=0
while [ $(( $(date +%s) - inizio )) -lt "$ATTESA_MAX" ]; do
  pid=$(systemctl show "$SERVIZIO" -p MainPID --value 2>/dev/null)
  # Due filtri in fila, e non uno solo: nella riga di `ss` la porta remota
  # viene PRIMA del campo con il pid
  #   192.168.1.52:34418  149.154.166.110:443  users:(("hermes",pid=1207633,...
  # quindi un pattern "pid=...:443" non puo' combaciare. Sbagliato al primo
  # tentativo, e l'attesa arrivava al tetto ogni volta.
  if [ -n "$pid" ] && [ "$pid" != "0" ] \
     && ss -tnp state established 2>/dev/null \
        | grep ":443 " | grep -q "pid=$pid,"; then
    collegato=1
    break
  fi
  sleep 2
done
secondi=$(( $(date +%s) - inizio ))

motore=$(/usr/local/bin/momo-motore 2>/dev/null | sed -n '1s/^motore attuale *: *//p')
: "${motore:=sconosciuto}"

if [ "$collegato" = "1" ]; then
  testo="✅ Sono tornato. Motore: ${motore} (ripartito in ${secondi}s)"
else
  # Si avvisa lo stesso, e si dice che non e' sicuro: un silenzio qui
  # sarebbe indistinguibile da un servizio morto.
  testo="⚠️ Riavviato, ma non ho visto il collegamento a Telegram entro ${ATTESA_MAX}s. Motore: ${motore}. Se non rispondo, guarda: systemctl status ${SERVIZIO}"
fi

# `--to` e' obbligatorio: senza, `hermes send` stampa l'aiuto ed esce con
# errore -- ed e' il motivo per cui il primo avviso non e' mai arrivato.
# `telegram` da solo significa "canale di casa", cioe' la conversazione
# principale: cosi' non si scrive qui nessun id, che sarebbe un dato in piu'
# da tenere allineato e che cambierebbe da solo.
"$HERMES" send --to telegram "$testo" >/dev/null 2>&1 || \
  logger -t momo-riavvia "avviso NON inviato: $testo"
