#!/usr/bin/env python3
"""Crea o aggiorna un monitor di Uptime Kuma. Gira sull'HOST Proxmox.

PERCHE ESISTE, e perche' non esisteva prima. Uptime Kuma non ha una API REST:
si parla solo in socket.io. Fino al 2026-07-31 questo lavoro era segnato «da
fare a mano» in PIANO_MASTER §4 perche' su LXC 101 mancava l'uscita verso
internet e il client Python non si poteva nemmeno installare. Il 2026-08-03
quell'uscita c'e' (pypi risponde 200) e il blocco e' caduto.

PERCHE NON USA `uptime-kuma-api`. Quel client copre la serie 1.x; qui gira
Uptime Kuma 2.4.0, che ha riscritto l'API, e il suo `login()` va in timeout.
Gli EVENTI pero' sono rimasti gli stessi -- verificato leggendo il loro codice
(`server.js`: `socket.on("login")`, `socket.on("add")`) e provandoli sul vivo.
Quindi si parla direttamente in socket.io con quegli eventi, invece di
aspettare che il client si aggiorni.

PERCHE SULL'HOST E NON SU LXC 101, dove Kuma gira. Le credenziali stanno in
/root/sovereign-secrets, che e' sull'host e NON e' montato nei container: e'
esattamente il senso di quella cartella. Farlo girare dentro 101 avrebbe
richiesto di far uscire la password dal posto dove sta al sicuro, per pura
comodita'. L'host raggiunge Kuma sulla 3001 ed e' fra gli indirizzi ammessi
dalla protezione (`sovereign-kuma-firewall.sh`).

NON SI SCRIVE MAI NEL DATABASE. Un monitor inserito a mano nel SQLite non
viene preso in carico dallo scheduler finche' il processo non riparte, e nel
frattempo il pannello lo mostra come se fosse vivo: si crederebbe di essere
sorvegliati senza esserlo, che e' peggio di non avere il monitor. Stessa
trappola gia' pagata con NPM.

IDEMPOTENTE: se un monitor con quel nome c'e' gia', lo AGGIORNA. Due monitor
sullo stesso indirizzo mandano due allarmi per lo stesso guasto, e chi li
riceve impara a ignorarli entrambi.

  /opt/kuma-venv/bin/python sovereign-kuma-monitor.py \
      --nome "Momo" --url https://momo.internal/ --tentativi 2
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

KUMA = "http://192.168.1.51:3001"     # Kuma vive su LXC 101; questo gira sull'host
UTENTE = "admin"
SEGRETO = Path("/root/sovereign-secrets/common-app-password")
ATTESA = 25                            # secondi entro cui il server deve rispondere


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nome", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--descrizione", default="")
    p.add_argument("--intervallo", type=int, default=60)
    p.add_argument("--tentativi", type=int, default=2,
                   help="fallimenti di fila prima di dichiarare DOWN (2)")
    p.add_argument("--attesi", default="200-399")
    p.add_argument("--prova", action="store_true",
                   help="dice cosa farebbe, senza toccare niente")
    a = p.parse_args()

    try:
        import socketio
    except ImportError:
        print("manca il client: /opt/kuma-venv/bin/pip install 'python-socketio[client]'",
              file=sys.stderr)
        return 1

    if not SEGRETO.is_file():
        print(f"password non trovata in {SEGRETO}", file=sys.stderr)
        return 1
    password = SEGRETO.read_text(encoding="utf-8").strip()

    # I campi sono copiati dalla forma di un monitor HTTP che gia' funziona
    # (il 44, Nextcloud), non inventati: Kuma 2.x rifiuta un payload
    # incompleto con un errore che non dice quale campo manca.
    monitor = {
        "type": "http",
        "name": a.nome,
        "url": a.url,
        "description": a.descrizione or None,
        "method": "GET",
        "interval": a.intervallo,
        "retryInterval": a.intervallo,
        "maxretries": a.tentativi,
        "maxredirects": 10,
        "timeout": 48,
        "accepted_statuscodes": [a.attesi],
        # Il certificato e' della CA di casa. `ignoreTls` resta ACCESO come su
        # tutti gli altri monitor interni: un controllo che fallisce per la
        # catena dei certificati direbbe «servizio giu» mentre il servizio sta
        # benissimo, e un allarme falso e' peggio di un controllo mancante.
        "ignoreTls": True,
        "upsideDown": False,
        "expiryNotification": False,
        "active": True,
        "weight": 2000,
        "notificationIDList": {},
        "conditions": [],
        "kafkaProducerBrokers": [],
        "kafkaProducerSaslOptions": {},
        "rabbitmqNodes": [],
    }

    if a.prova:
        print("creerei o aggiornerei", a.nome, "->", a.url)
        for k, v in monitor.items():
            print(f"   {k}: {v!r}")
        return 0

    sio = socketio.Client(reconnection=False)
    elenco: dict = {}
    esito: dict = {}

    @sio.on("monitorList")
    def _lista(dati):
        if isinstance(dati, dict):
            elenco.clear()
            elenco.update(dati)

    def risposta(dati):
        esito.clear()
        esito.update(dati if isinstance(dati, dict) else {"risposta": dati})

    def attendi() -> dict:
        for _ in range(ATTESA * 4):
            if esito:
                return dict(esito)
            time.sleep(0.25)
        return {}

    try:
        sio.connect(KUMA, transports=["websocket"], wait_timeout=15)
    except Exception as exc:  # noqa: BLE001
        print(f"non riesco a collegarmi a {KUMA}: {exc}", file=sys.stderr)
        print("se e' un timeout: la 3001 e' ristretta, e questo host deve stare "
              "fra quelli ammessi in sovereign-kuma-firewall.sh", file=sys.stderr)
        return 1

    try:
        # Kuma manda una raffica di eventi appena ci si collega (monitorList,
        # apiKeyList, info, certInfo...). Emettere il login mentre li sta
        # ancora spedendo fa cadere la risposta: la prima versione di questo
        # script falliva con «nessuna risposta» proprio qui, mentre la stessa
        # sequenza con due secondi di pausa funzionava. Si aspetta che abbia
        # finito di parlare prima di parlargli.
        time.sleep(2.5)
        sio.emit("login", {"username": UTENTE, "password": password, "token": ""},
                 callback=risposta)
        r = attendi()
        if not r.get("ok"):
            print(f"login rifiutato: {r or 'nessuna risposta'}", file=sys.stderr)
            return 1

        time.sleep(1.5)   # il server manda monitorList subito dopo il login
        gia = next((m for m in elenco.values() if m.get("name") == a.nome), None)

        esito.clear()
        if gia:
            monitor["id"] = gia["id"]
            sio.emit("editMonitor", monitor, callback=risposta)
            verbo = "aggiornato"
        else:
            sio.emit("add", monitor, callback=risposta)
            verbo = "creato"
        r = attendi()
        if not r.get("ok"):
            print(f"{verbo} NON riuscito: {r or 'nessuna risposta'}", file=sys.stderr)
            return 1
        mid = r.get("monitorID") or (gia or {}).get("id")
        print(f"{verbo}: «{a.nome}» (id {mid}) -> {a.url}")

        # La prova non e' «l'ho creato» ma «sta guardando davvero»: si rilegge
        # dal server, non dalla risposta della chiamata.
        elenco.clear()
        sio.emit("getMonitorList")
        for _ in range(40):
            if elenco:
                break
            time.sleep(0.25)
        letto = elenco.get(str(mid)) or elenco.get(mid)
        if not letto:
            print("creato ma non rileggibile: controllare il pannello", file=sys.stderr)
            return 1
        print(f"riletto dal server: attivo={bool(letto.get('active'))} "
              f"intervallo={letto.get('interval')}s tentativi={letto.get('maxretries')}")
        return 0
    finally:
        try:
            sio.disconnect()
        except Exception:  # noqa: BLE001 - non deve mascherare l'esito
            pass


if __name__ == "__main__":
    raise SystemExit(main())
