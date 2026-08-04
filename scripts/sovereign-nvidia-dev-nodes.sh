#!/usr/bin/env bash
# Crea /dev/nvidia* sull'host Proxmox, RIPROVANDO finche' la scheda non c'e'.
# Chiamato da nvidia-dev-nodes.service prima che partano i container.
#
# PERCHE ESISTE. Il driver NVIDIA non crea i nodi al boot: li crea quando il
# primo processo apre la scheda. LXC 102 pero' li monta con
# `bind,optional,create=file`, e `optional` significa «se la sorgente non c'e,
# non fallire»: il container parte con dei FILE VUOTI al posto dei device, il
# modificatore CDI di Docker non inizializza NVML, e il solo Ollama resta giu'
# con exit 128 mentre tutto il resto sembra sano.
#
# PERCHE NON BASTAVA LA PRIMA VERSIONE, che era due righe dentro lo unit.
# Al riavvio del 2026-08-03 19:20 il modulo si e' caricato alle 19:20:32 e il
# servizio e' partito alle 19:20:35, fallendo con exit 1. La prova sta nelle
# date dei nodi: /dev/nvidia-uvm porta le 19:20 (l'opzione -u era riuscita),
# /dev/nvidia0 e /dev/nvidiactl no. Tre secondi dopo il caricamento del modulo
# la GPU non era ancora enumerata -- l'enumerazione e' asincrona, e un comando
# solo la prende o la manca a seconda di com'e' andata quella volta.
# Risultato: Ollama giu' per nove ore, e il difetto ha AVVISATO (Kuma, il
# Verificatore con 4 sonde su 4, la mail) ma nessuno era li' a leggerlo.
#
# Quindi si riprova, con un tetto. Un rimedio che funziona solo se il momento
# e' quello giusto non e' un rimedio: e' una coincidenza ripetibile.

set -uo pipefail

TENTATIVI="${TENTATIVI:-30}"     # 30 x 2s = un minuto buono
PAUSA="${PAUSA:-2}"

pronti() {
  [ -c /dev/nvidiactl ] && [ -c /dev/nvidia0 ]
}

for i in $(seq 1 "$TENTATIVI"); do
  # DUE STRUMENTI, e servono tutti e due.
  #   nvidia-modprobe -c 0 -u  carica i moduli e crea i nodi UVM. MA non
  #     ricrea /dev/nvidia0 e /dev/nvidiactl se il driver e' gia'
  #     inizializzato: li' ritorna 0 senza fare niente. Misurato il
  #     2026-08-04 cancellando i nodi a mano: sessanta secondi di tentativi,
  #     sempre successo, e i nodi mai ricomparsi.
  #   nvidia-smi  APRE la scheda, e l'apertura e' cio' che fa creare i nodi
  #     al driver. E' il motivo per cui ieri mattina sono ricomparsi con
  #     l'orario esatto del nvidia-smi che avevo lanciato per diagnosticare.
  # Un rimedio costruito sul solo nvidia-modprobe sembra corretto e non lo e':
  # ritorna successo e non fa il lavoro.
  /usr/bin/nvidia-modprobe -c 0 -u >/dev/null 2>&1 || true
  pronti || /usr/bin/nvidia-smi -L >/dev/null 2>&1 || true
  if pronti; then
    echo "nodi NVIDIA pronti al tentativo $i"
    ls -l /dev/nvidia0 /dev/nvidiactl
    exit 0
  fi
  sleep "$PAUSA"
done

# Si esce in errore, e si dice cosa guardare: un servizio che fallisce in
# silenzio lascia scoprire il guasto nove ore dopo, da un altro sintomo.
echo "NODI NVIDIA ASSENTI dopo $((TENTATIVI * PAUSA))s." >&2
echo "La scheda si vede?  lspci | grep -i nvidia" >&2
echo "Il modulo e' su?    lsmod | grep nvidia" >&2
echo "Cosa dice il kernel: dmesg | grep -i nvrm" >&2
echo "Senza questi nodi LXC 102 parte con file vuoti al loro posto e Ollama" >&2
echo "non si avvia (exit 128)." >&2
exit 1
