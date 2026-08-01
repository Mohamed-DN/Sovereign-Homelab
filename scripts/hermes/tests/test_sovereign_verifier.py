"""The Verifier's rules, case by case. No network, no server: the probe is
replaced by a scripted sequence, because what is under test is the
CLASSIFICATION, not urllib.

The one rule these cases exist to protect: a probe that could not run must
never suppress an alarm. Anything that produces UNKNOWN has to come out
UNVERIFIED, which still sends the email.

Run from anywhere:
    python3 scripts/hermes/tests/test_sovereign_verifier.py
"""
from __future__ import annotations

import os
import socket
import ssl
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes"),
                   os.path.join(_HERE, "..")):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import sovereign_verifier as v  # noqa: E402

FAILURES: list[str] = []
PASSED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED  # noqa: PLW0603 - one counter, one script
    if condition:
        PASSED += 1
    else:
        FAILURES.append(f"{name}{f' -- {detail}' if detail else ''}")


def verdict_for(outcomes: list[str]) -> str:
    """Run verify() against a scripted probe sequence."""
    remaining = list(outcomes)
    original = v.probe_once
    try:
        v.probe_once = lambda monitor, timeout=8.0, ca_path=None: (remaining.pop(0), "finto")
        result = v.verify({"type": "http", "url": "https://x.internal"},
                          probes=len(outcomes), spacing=0, sleep=lambda _s: None)
    finally:
        v.probe_once = original
    return result["verdict"]


# --- classification: the whole point --------------------------------------

check("tutte fallite -> REAL_CRITICAL",
      verdict_for([v.FAIL] * 4) == v.REAL_CRITICAL)
check("tutte riuscite -> FALSE_ALARM",
      verdict_for([v.OK] * 4) == v.FALSE_ALARM)
check("una fallita su quattro -> REAL_WARNING (il caso Nextcloud)",
      verdict_for([v.OK, v.OK, v.FAIL, v.OK]) == v.REAL_WARNING)
check("tre fallite su quattro -> REAL_WARNING",
      verdict_for([v.FAIL, v.FAIL, v.FAIL, v.OK]) == v.REAL_WARNING)

# The rule that protects against a useless verifier: a probe that could not
# run must never be counted as evidence about the service.
check("una sonda non eseguibile -> UNVERIFIED anche se le altre sono ok",
      verdict_for([v.OK, v.OK, v.UNKNOWN, v.OK]) == v.UNVERIFIED,
      "prove parziali non devono MAI zittire un allarme")
check("tutte non eseguibili -> UNVERIFIED",
      verdict_for([v.UNKNOWN] * 3) == v.UNVERIFIED)
check("una non eseguibile e le altre fallite -> UNVERIFIED",
      verdict_for([v.UNKNOWN, v.FAIL, v.FAIL]) == v.UNVERIFIED)
check("nessuna sonda -> UNVERIFIED",
      v.classify({v.OK: 0, v.FAIL: 0, v.UNKNOWN: 0}) == v.UNVERIFIED)

# A second opinion may escalate, never silence.
check("second_opinion puo' alzare FALSE_ALARM a REAL_CRITICAL",
      v.classify({v.OK: 4, v.FAIL: 0, v.UNKNOWN: 0},
                 second_opinion=lambda _c: v.REAL_CRITICAL) == v.REAL_CRITICAL)
check("second_opinion NON puo' abbassare REAL_CRITICAL a FALSE_ALARM",
      v.classify({v.OK: 0, v.FAIL: 4, v.UNKNOWN: 0},
                 second_opinion=lambda _c: v.FALSE_ALARM) == v.REAL_CRITICAL,
      "solo la regola puo' decidere di zittire")
check("second_opinion che esplode non cambia il verdetto della regola",
      v.classify({v.OK: 0, v.FAIL: 2, v.UNKNOWN: 0},
                 second_opinion=lambda _c: 1 / 0) == v.REAL_CRITICAL)


# --- accepted_statuscodes, nel formato che manda Kuma ----------------------

check("200 dentro 200-399", v.status_accepted(200, ["200-399"]) is True)
check("399 dentro 200-399", v.status_accepted(399, ["200-399"]) is True)
check("404 fuori da 200-399", v.status_accepted(404, ["200-399"]) is False)
check("codice esatto", v.status_accepted(201, ["201"]) is True)
check("elenco misto", v.status_accepted(302, ["200-299", "302"]) is True)
check("default sensato quando l'elenco manca", v.status_accepted(200, None) is True)
check("default sensato: 500 non passa", v.status_accepted(500, None) is False)
check("voce spazzatura ignorata invece di far esplodere",
      v.status_accepted(200, ["abc", "200-299"]) is True)


# --- di chi e' la colpa: la distinzione che regge tutto --------------------

outcome, _ = v._classify_url_error(ssl.SSLCertVerificationError("verify failed"))
check("certificato non verificabile -> colpa NOSTRA (UNKNOWN)", outcome == v.UNKNOWN,
      "senza questo, ogni monitor .internal verrebbe confermato per un difetto della sonda")

error = ssl.SSLError("unrecognized name")
error.reason = "TLSV1_UNRECOGNIZED_NAME"
outcome, _ = v._classify_url_error(error)
check("TLS unrecognized_name -> colpa DEL SERVIZIO (FAIL)", outcome == v.FAIL,
      "e' NPM che risponde «quel vhost non esiste»")

outcome, _ = v._classify_url_error(socket.gaierror("Name or service not known"))
check("nome non risolto -> UNKNOWN (ambiguo: potrebbe essere AdGuard)", outcome == v.UNKNOWN)
outcome, _ = v._classify_url_error(ConnectionRefusedError("refused"))
check("connessione rifiutata -> FAIL", outcome == v.FAIL)
outcome, _ = v._classify_url_error(TimeoutError())
check("timeout -> FAIL (e' quello che vede l'utente)", outcome == v.FAIL)


# --- cosa vale la pena sondare --------------------------------------------

check("http con url -> sondabile", v.probeable({"type": "http", "url": "https://x.internal"}))
check("http senza url -> no", not v.probeable({"type": "http", "url": ""}))
check("port con host e porta -> sondabile",
      v.probeable({"type": "port", "hostname": "192.168.1.52", "port": 11434}))
check("port senza porta -> no", not v.probeable({"type": "port", "hostname": "x"}))
check("dns -> no (uno solo su 44)", not v.probeable({"type": "dns", "hostname": "dash.internal"}))
check("tipo sconosciuto -> no", not v.probeable({"type": "gamedig"}))

result = v.unverifiable("il monitor non è sondabile")
check("unverifiable() dice UNVERIFIED", result["verdict"] == v.UNVERIFIED)
check("unverifiable() non costa sonde", result["probes"] == 0)
check("unverifiable() lo scrive in chiaro", "non è stato verificato" in result["detail"])


# --- il testo che finisce nella mail --------------------------------------

check("il riassunto di FALSE_ALARM dice che non si riproduce",
      "non si riproduce" in v.summary(v.FALSE_ALARM, {v.OK: 4, v.FAIL: 0, v.UNKNOWN: 0}, 4))
check("il riassunto di REAL_CRITICAL dice confermato",
      "confermato" in v.summary(v.REAL_CRITICAL, {v.OK: 0, v.FAIL: 4, v.UNKNOWN: 0}, 4))
check("il riassunto di UNVERIFIED ammette di non aver verificato",
      "non è stato verificato" in v.summary(v.UNVERIFIED, {v.OK: 0, v.FAIL: 0, v.UNKNOWN: 4}, 4))

check("monitor_of legge il payload di Kuma",
      v.monitor_of({"monitor": {"id": 44, "url": "https://files.internal"}})["id"] == 44)
check("monitor_of su un payload storto non esplode", v.monitor_of({"monitor": "boh"}) == {})


print(f"casi passati: {PASSED}")
if FAILURES:
    for failure in FAILURES:
        print(f"FALLITO: {failure}")
    print(f"test_sovereign_verifier: {len(FAILURES)} caso/i fallito/i")
    raise SystemExit(1)
print("test_sovereign_verifier OK")
