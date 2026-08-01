#!/usr/bin/env python3
"""The alarm Verifier -- Nexi's A3.

Before the relay sends the first email of an incident, it goes and looks
again: it re-reads the target out of Kuma's own webhook payload and probes it
itself, several times, spaced out. Then it classifies what it saw.

    REAL_CRITICAL   every probe failed          -> send "DOWN", as before
    REAL_WARNING    some failed, some did not   -> send "WARNING" (intermittent)
    FALSE_ALARM     every probe succeeded       -> send nothing, look again later
    UNVERIFIED      the probe could not run     -> send "DOWN", saying so

THE RULE THAT MAKES THIS USEFUL RATHER THAN JUST LOUDER: the probe's own
failure is not the service's failure. A certificate we cannot verify, a name we
cannot resolve, a monitor type we cannot speak -- those say something about the
probe, and they produce UNVERIFIED, which never silences anything. Only
evidence that we REACHED the service and it answered wrongly counts against it.

Standard library only, no state of its own, no LLM: see
docs/04_apps/sovereign-verificatore.md §1.4 for why the model stage of Nexi's
A3 is deliberately not here (an alarm path that depends on the chat service
being up is worse than the false alarm it would cure). `classify()` takes an
optional `second_opinion` so the decision stays reversible.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Iterable

REAL_CRITICAL = "REAL_CRITICAL"
REAL_WARNING = "REAL_WARNING"
FALSE_ALARM = "FALSE_ALARM"
UNVERIFIED = "UNVERIFIED"

# Outcome of a single probe.
OK = "ok"            # reached the service, answer acceptable
FAIL = "fail"        # reached the service, answer unacceptable  -> counts against it
UNKNOWN = "unknown"  # the probe itself could not run             -> counts against US

# The internal CA, in order; the first file that exists wins. See §1.2 of the
# runbook: without it every `.internal` probe fails to verify and the Verifier
# would confirm every alarm -- code that runs, passes its own tests, and checks
# nothing.
CA_CANDIDATES = (
    os.environ.get("ALERT_VERIFY_CA_FILE", ""),
    "/root/sovereign-secrets/ca/sovereign-root-ca.crt",
    # Where it really lives on LXC 101 today: a Docker volume path, so it is
    # the fallback and not the first choice -- it moves if step-ca is redeployed.
    "/var/lib/docker/volumes/internal-ca_step_ca_data/_data/certs/root_ca.crt",
)

USER_AGENT = "sovereign-verifier/1.0"


def ca_file() -> str:
    for candidate in CA_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return ""


def _context(ca_path: str) -> ssl.SSLContext:
    """System trust PLUS our own CA.

    Not `create_default_context(cafile=...)`: that loads ONLY that file, which
    would break the one public monitor (the DuckDNS VPN edge). Loading both
    means the same probe speaks to `.internal` and to the open internet.
    """
    ctx = ssl.create_default_context()
    if ca_path:
        try:
            ctx.load_verify_locations(ca_path)
        except (OSError, ssl.SSLError):
            pass                      # the CA is unusable: probes will say UNVERIFIED
    return ctx


def status_accepted(code: int, accepted: Iterable[Any] | None) -> bool:
    """Kuma's `accepted_statuscodes`, e.g. ["200-399"] or ["200", "201"]."""
    ranges = list(accepted or []) or ["200-299"]
    for entry in ranges:
        text = str(entry).strip()
        if "-" in text:
            low, _, high = text.partition("-")
            try:
                if int(low) <= code <= int(high):
                    return True
            except ValueError:
                continue
        else:
            try:
                if code == int(text):
                    return True
            except ValueError:
                continue
    return False


def _probe_http(monitor: dict[str, Any], timeout: float, ca_path: str) -> tuple[str, str]:
    url = str(monitor.get("url") or "").strip()
    if not url:
        return UNKNOWN, "il monitor non ha un URL: niente da sondare"
    method = str(monitor.get("method") or "GET").upper()
    accepted = monitor.get("accepted_statuscodes")
    keyword = str(monitor.get("keyword") or "")
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    context = _context(ca_path)
    body = ""
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            code = int(response.status)
            if keyword:
                body = response.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # The server answered; a 4xx/5xx can still be inside accepted_statuscodes.
        code = int(exc.code)
        return (OK, f"HTTP {code} (accettato)") if status_accepted(code, accepted) \
            else (FAIL, f"HTTP {code}")
    except urllib.error.URLError as exc:
        return _classify_url_error(exc.reason)
    except (TimeoutError, socket.timeout):
        return FAIL, f"nessuna risposta entro {timeout:g}s"
    except (ssl.SSLError, OSError) as exc:
        return _classify_url_error(exc)
    except Exception as exc:                      # noqa: BLE001 - never crash the relay
        return UNKNOWN, f"sonda fallita: {type(exc).__name__}: {exc}"
    if not status_accepted(code, accepted):
        return FAIL, f"HTTP {code}"
    if keyword and keyword not in body:
        return FAIL, f"HTTP {code} ma la parola «{keyword}» non c'e'"
    return OK, f"HTTP {code}"


def _classify_url_error(reason: Any) -> tuple[str, str]:
    """Who is at fault, the service or us. §1.1 of the runbook."""
    if isinstance(reason, ssl.SSLCertVerificationError):
        # Our trust store, not their service.
        # `verify_message` is set by the SSL layer but not by a hand-built
        # instance: getattr, so the classifier never crashes on the very error
        # it exists to classify.
        return UNKNOWN, f"certificato non verificabile: {getattr(reason, 'verify_message', None) or reason}"
    if isinstance(reason, ssl.SSLError):
        # NPM answering "unrecognized_name" IS the service talking: that vhost
        # does not exist. Any other TLS error at this point is theirs too.
        return FAIL, f"TLS rifiutato dal server: {getattr(reason, 'reason', '') or reason}"
    if isinstance(reason, socket.gaierror):
        # Ambiguous (AdGuard itself could be down): never suppress on this.
        return UNKNOWN, f"nome non risolto: {reason}"
    if isinstance(reason, (ConnectionRefusedError, ConnectionResetError)):
        return FAIL, f"connessione rifiutata: {reason}"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return FAIL, "nessuna risposta entro il tempo massimo"
    if isinstance(reason, OSError):
        return FAIL, f"rete: {reason}"
    return UNKNOWN, f"sonda fallita: {reason}"


def _probe_port(monitor: dict[str, Any], timeout: float) -> tuple[str, str]:
    host = str(monitor.get("hostname") or "").strip()
    try:
        port = int(monitor.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    if not host or not port:
        return UNKNOWN, "il monitor non ha host e porta: niente da sondare"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return OK, f"{host}:{port} accetta connessioni"
    except socket.gaierror as exc:
        return UNKNOWN, f"nome non risolto: {exc}"
    except (TimeoutError, socket.timeout):
        return FAIL, f"{host}:{port} non risponde entro {timeout:g}s"
    except OSError as exc:
        return FAIL, f"{host}:{port} rifiuta: {exc}"


def probe_once(monitor: dict[str, Any], timeout: float = 8.0,
               ca_path: str | None = None) -> tuple[str, str]:
    kind = str(monitor.get("type") or "").lower()
    if kind in {"http", "keyword", "json-query", "json_query", ""} and monitor.get("url"):
        return _probe_http(monitor, timeout, ca_path if ca_path is not None else ca_file())
    if kind in {"port", "tcp"}:
        return _probe_port(monitor, timeout)
    if kind == "dns":
        # One monitor out of 44. Writing a DNS client by hand would be more
        # untested code than value; the "AdGuard DNS TCP" port monitor already
        # covers reachability.
        return UNKNOWN, "monitor di tipo dns: non sondabile da qui"
    return UNKNOWN, f"tipo di monitor non sondabile: {kind or 'sconosciuto'}"


def classify(counts: dict[str, int],
             second_opinion: Callable[[dict[str, int]], str | None] | None = None) -> str:
    """The deterministic rule. Always decides; a second opinion may only be
    consulted when the rule has evidence, and may never turn evidence of a
    real failure into silence."""
    unknown = counts.get(UNKNOWN, 0)
    ok = counts.get(OK, 0)
    fail = counts.get(FAIL, 0)
    if unknown or (ok == 0 and fail == 0):
        # Partial or absent evidence: never suppress. UNVERIFIED still alerts.
        return UNVERIFIED
    if ok == 0:
        verdict = REAL_CRITICAL
    elif fail == 0:
        verdict = FALSE_ALARM
    else:
        verdict = REAL_WARNING
    if second_opinion is not None:
        try:
            other = second_opinion(counts)
        except Exception:                        # noqa: BLE001 - the rule stands alone
            other = None
        if other in {REAL_CRITICAL, REAL_WARNING} and verdict == FALSE_ALARM:
            return other                          # may escalate, never silence
    return verdict


def verify(monitor: dict[str, Any], probes: int = 4, spacing: float = 3.0,
           timeout: float = 8.0, ca_path: str | None = None,
           second_opinion: Callable[[dict[str, int]], str | None] | None = None,
           sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Probe `probes` times, spaced by `spacing` seconds, and classify."""
    probes = max(1, int(probes))
    resolved_ca = ca_path if ca_path is not None else ca_file()
    counts = {OK: 0, FAIL: 0, UNKNOWN: 0}
    attempts: list[str] = []
    for index in range(probes):
        if index:
            sleep(spacing)
        outcome, detail = probe_once(monitor, timeout=timeout, ca_path=resolved_ca)
        counts[outcome] = counts.get(outcome, 0) + 1
        attempts.append(f"{index + 1}. {outcome}: {detail}")
    verdict = classify(counts, second_opinion)
    return {
        "verdict": verdict,
        "ok": counts[OK], "fail": counts[FAIL], "unknown": counts[UNKNOWN],
        "probes": probes,
        "attempts": attempts,
        "ca": resolved_ca or "(nessuna CA interna trovata)",
        "detail": summary(verdict, counts, probes),
    }


def summary(verdict: str, counts: dict[str, int], probes: int) -> str:
    ok, fail, unknown = counts.get(OK, 0), counts.get(FAIL, 0), counts.get(UNKNOWN, 0)
    if verdict == FALSE_ALARM:
        return (f"Controllo indipendente: {ok} sonde su {probes} sono andate a buon fine. "
                f"Il guasto non si riproduce.")
    if verdict == REAL_WARNING:
        return (f"Controllo indipendente: {ok} sonde su {probes} riuscite, {fail} fallite. "
                f"Il servizio risponde a intermittenza.")
    if verdict == REAL_CRITICAL:
        return f"Controllo indipendente: {fail} sonde su {probes} fallite. Il guasto è confermato."
    return (f"Controllo indipendente NON riuscito ({unknown} sonde su {probes} non hanno "
            f"potuto misurare nulla): questo allarme non è stato verificato.")


def monitor_of(payload: dict[str, Any]) -> dict[str, Any]:
    monitor = payload.get("monitor")
    return monitor if isinstance(monitor, dict) else {}


def probeable(monitor: dict[str, Any]) -> bool:
    """Whether it is worth probing at all.

    Without this, a monitor with nothing to probe would still cost `probes ×
    spacing` seconds of sleeping to reach the same UNVERIFIED it could have
    reached immediately.
    """
    kind = str(monitor.get("type") or "").lower()
    if kind in {"port", "tcp"}:
        return bool(monitor.get("hostname")) and bool(monitor.get("port"))
    if kind in {"http", "keyword", "json-query", "json_query", ""}:
        return bool(str(monitor.get("url") or "").strip())
    return False


def unverifiable(why: str) -> dict[str, Any]:
    """The result for something we never even tried to probe."""
    return {"verdict": UNVERIFIED, "ok": 0, "fail": 0, "unknown": 0, "probes": 0,
            "attempts": [], "ca": "",
            "detail": f"Controllo indipendente non eseguito: {why}. "
                      f"Questo allarme non è stato verificato."}


def main(argv: list[str]) -> int:
    """CLI, so the probe can be pointed at anything by hand from LXC 101."""
    args = {"--url": "", "--type": "", "--host": "", "--port": "",
            "--probes": "4", "--spacing": "1", "--timeout": "8"}
    index = 1
    while index < len(argv) - 1:
        if argv[index] in args:
            args[argv[index]] = argv[index + 1]
            index += 2
        else:
            index += 1
    if not args["--url"] and not args["--host"]:
        print(f"uso: {os.path.basename(argv[0])} --url https://x.internal [--probes 4] "
              f"[--spacing 1]\n     {os.path.basename(argv[0])} --host 192.168.1.52 --port 11434",
              file=sys.stderr)
        return 2
    monitor = {
        "type": args["--type"] or ("port" if args["--host"] else "http"),
        "url": args["--url"], "hostname": args["--host"],
        "port": args["--port"], "accepted_statuscodes": ["200-399"],
    }
    result = verify(monitor, probes=int(args["--probes"]), spacing=float(args["--spacing"]),
                    timeout=float(args["--timeout"]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
