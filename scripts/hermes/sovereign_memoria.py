#!/usr/bin/env python3
"""The rules behind the memory that updates itself — and nothing else.

One file, standard library only, no network and no database, so it can be
imported by Momo, by the live Hermes and by a test that runs on a laptop with
nothing switched on. Same shape as `hermes_guardrail.py` and
`sovereign_switch.py`, and for the same reason: two copies of a rule diverge,
and the divergence stays invisible until one of them lets something through.

WHAT THIS FILE IS FOR, in one line: to decide, deterministically, *whether* a
turn deserves to be looked at, and *what may never be written* whatever the
model says. The extraction itself — the one part a rule genuinely cannot do —
lives next to Momo in `sovereign/apprendimento.py`, because it needs a model
and a memory store, and this file must keep needing neither.

THE PROMISE THIS RESPECTS. PIANO_AGENT_MOMO.md §4 said `sync_turn()` was
deliberately empty so that memory stayed *stated, not harvested*, auditable,
and so that `dimentica` really forgot. The owner asked on 2026-08-01 for
automatic saving. The objection is honoured rather than dropped:

  * silent in the conversation, but inspectable on demand (`/memoria`);
  * not "every turn": `vale_la_pena()` throws most of them away for free;
  * automatic memory WRITES AND NEVER DELETES — no function here or in
    `apprendimento.py` calls `forget()`. Deleting stays the owner's decision.

Full design: docs/04_apps/momo-memoria-automatica.md

Command line, for the switch (works with Momo down, which is the point):
    python3 sovereign_memoria.py stato
    python3 sovereign_memoria.py pausa "motivo"
    python3 sovereign_memoria.py riprendi
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from typing import Any, Iterable

# --------------------------------------------------------------------------
# The switch
# --------------------------------------------------------------------------

# Its own file, NOT `master-state.json`. The estate-wide RUNNING/PAUSED switch
# is about *acting on the world*; this is about *learning*. Folding them
# together would mean that pausing the estate for maintenance also silently
# changed what Momo remembers of that maintenance — which is exactly the
# session you would want him to learn from.
STATE_FILE = os.environ.get(
    "SOVEREIGN_MEMORIA_FILE", "/var/lib/sovereign-hermes/memoria-automatica.json")

# An environment override, so a test or a one-off service run can switch
# learning off without touching a file that outlives the process.
_ENV_OFF = {"0", "false", "off", "no", "spento"}


def read_state() -> dict[str, Any]:
    """The switch, and how we know. Never raises.

    `source` is the honest part: "assente" (never written), "ok", "corrotto".
    The caller needs the difference — see `is_active`.
    """
    path = os.environ.get("SOVEREIGN_MEMORIA_FILE", STATE_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return {"attiva": True, "source": "assente"}
    except Exception:  # noqa: BLE001 - broken JSON, bad permissions, a directory
        return {"attiva": False, "source": "corrotto"}
    if not isinstance(raw, dict):
        return {"attiva": False, "source": "corrotto"}
    state = dict(raw)
    state["attiva"] = bool(raw.get("attiva", True))
    state["source"] = "ok"
    return state


def is_active() -> bool:
    """Whether Momo may learn by himself right now.

    THE DIRECTION OF FAILURE IS THE OPPOSITE OF `sovereign_switch`, ON PURPOSE.

      file missing    -> ON.  It was never written, and "on" is the decision
                              the owner took on 2026-08-01. A file that has
                              never existed must not silently cancel a feature
                              he asked for.
      file unreadable -> OFF. Somebody wrote it and it broke. Learning in
                              silence while he believes it is off is the
                              surprising outcome; not learning for a while is
                              visible in `/memoria` and loses nothing that
                              cannot be said again.

    `sovereign_switch` fails the other way because there the dangerous case is
    a pause that disappears and actions resume. Each switch fails towards
    whatever is *least surprising to whoever touched it last*.
    """
    if os.environ.get("SOVEREIGN_MEMORIA_AUTO", "").strip().lower() in _ENV_OFF:
        return False
    return bool(read_state().get("attiva"))


def _write_state(changes: dict[str, Any]) -> None:
    """Atomic, and it keeps the keys it does not understand.

    Temp file + fsync + os.replace, copied from `sovereign_switch.py`: a
    half-written switch is a switch nobody can trust. The read-modify-write
    preserves unknown keys because a future field written by something else
    must not vanish because this function did not know about it.
    """
    path = os.environ.get("SOVEREIGN_MEMORIA_FILE", STATE_FILE)
    current = read_state()
    state = {k: v for k, v in current.items() if k != "source"}
    state.update(changes)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def pausa(*, by: str = "cli", reason: str = "") -> None:
    _write_state({"attiva": False, "fermata_da": by, "fermata_il": int(time.time()),
                  "motivo": reason.strip()[:300]})


def riprendi(*, by: str = "cli") -> None:
    _write_state({"attiva": True, "fermata_da": "", "fermata_il": 0,
                  "motivo": "", "ripresa_da": by, "ripresa_il": int(time.time())})


def describe() -> str:
    """One line in Italian, for `/memoria stato` and for the CLI."""
    state = read_state()
    if state["source"] == "corrotto":
        return ("apprendimento automatico: SPENTO — il file dello stato non è leggibile "
                f"({os.environ.get('SOVEREIGN_MEMORIA_FILE', STATE_FILE)}). "
                "«riprendi» lo riscrive pulito.")
    if not is_active():
        if os.environ.get("SOVEREIGN_MEMORIA_AUTO", "").strip().lower() in _ENV_OFF:
            return "apprendimento automatico: SPENTO dall'ambiente (SOVEREIGN_MEMORIA_AUTO=0)"
        who = state.get("fermata_da") or "qualcuno"
        why = state.get("motivo") or "senza motivo dichiarato"
        return f"apprendimento automatico: SPENTO da {who} — {why}"
    return "apprendimento automatico: ACCESO"


# --------------------------------------------------------------------------
# Text normalisation — the base of both the fingerprint and every rule
# --------------------------------------------------------------------------

# Words that carry no meaning for a fingerprint. Kept short on purpose: a long
# stopword list starts eating the words that make two facts different.
_VUOTE = frozenset("""
il lo la i gli le un uno una di del dello della dei degli delle a al allo alla
ai agli alle da dal dallo dalla dai dagli dalle in nel nello nella nei negli
nelle con col su sul sullo sulla sui sugli sulle per tra fra e ed o oppure che
chi cui non piu piu' molto poi anche come quando mentre se ma pero pero' quindi
si e' essere sono era erano ha ho hai hanno avere il_suo suo sua suoi sue mio
mia miei mie
""".split())

_PUNTEGGIATURA = re.compile(r"[^\w\s]", re.UNICODE)
_SPAZI = re.compile(r"\s+")


def normalizza(testo: str) -> str:
    """Lowercase, accents stripped, punctuation dropped, spaces collapsed.

    Not a fingerprint yet: `veto()` uses this so a rule cannot be dodged by
    typing «p a s s w o r d» — no, it cannot dodge that either; it is used so
    «Password:» and «password :» are the same string to a pattern.
    """
    testo = unicodedata.normalize("NFKD", testo or "")
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    testo = _PUNTEGGIATURA.sub(" ", testo.lower())
    return _SPAZI.sub(" ", testo).strip()


def impronta(testo: str) -> str:
    """The fingerprint used by dedup layer 2.

    Normalised, stopwords removed, words SORTED. Sorting is the deliberate
    part: «lavora come DBA Oracle» and «come DBA Oracle lavora» are the same
    fact said in two orders, and a fingerprint that treats them as different
    would let the second one in a week later.
    """
    parole = [p for p in normalizza(testo).split() if p and p not in _VUOTE]
    return " ".join(sorted(parole))


# --------------------------------------------------------------------------
# Prompt injection — the scan that runs on every candidate BEFORE it is written
# --------------------------------------------------------------------------

# Invisible characters: zero-width spaces, bidi overrides, the unicode tag
# block. A fact whose text carries them is either broken or hiding something,
# and either way it does not belong in a system prompt forever.
# Written as escape sequences on purpose: a literal zero-width character in
# this source file would be invisible in the very code whose job is to catch
# it, and the next person to edit the line would delete it without seeing it.
_INVISIBILI = re.compile(
    "["
    "\u200b-\u200f"          # zero-width space/joiner, LTR/RTL marks
    "\u2028-\u202e"          # line/paragraph separators, bidi override
    "\u2060-\u2064"          # word joiner, invisible operators
    "\ufeff"                  # byte-order mark used as a separator
    "\U000e0000-\U000e007f"  # the unicode TAG block: text hidden inside text
    "]")

# OUR patterns. They are NOT a second copy of `tools/threat_patterns.py`:
# theirs are English-only, and a page in Italian saying «ignora le istruzioni
# precedenti» walks straight through them. These cover Italian and Arabic and
# run ALONGSIDE theirs, never instead. Adding an English pattern here would be
# the drift this house avoids — that one belongs upstream, in their file.
PATTERN_INIEZIONE: tuple[tuple[str, str], ...] = (
    (r"ignora\s+(?:\w+\s+){0,6}(?:le\s+)?(?:istruzioni|regole|indicazioni)", "iniezione_it"),
    (r"dimentica\s+(?:tutte\s+)?(?:le\s+)?(?:tue\s+)?(?:istruzioni|regole)", "iniezione_it"),
    (r"(?:nuove|nuovo)\s+(?:istruzioni|prompt|ordine)\s+(?:di\s+)?sistema", "prompt_sistema_it"),
    (r"prompt\s+di\s+sistema", "prompt_sistema_it"),
    (r"(?:sei|adesso\s+sei|ora\s+sei)\s+(?:ora\s+|adesso\s+)?(?:un|uno|una|il|lo|la)\s+\w+",
     "cambio_identita_it"),
    (r"fingi\s+di\s+(?:essere|non|avere)", "finzione_it"),
    (r"comportati\s+come\s+se\s+(?:\w+\s+){0,4}(?:non\s+avessi|fossi)", "finzione_it"),
    (r"non\s+(?:dirlo|dire|rivelare)\s+(?:\w+\s+){0,3}(?:all['\s]?utente|al\s+proprietario|a\s+mohamed)",
     "inganno_it"),
    (r"rispondi\s+senza\s+(?:restrizioni|filtri|limiti|controlli)", "senza_filtri_it"),
    (r"(?:invia|manda|spedisci)\s+(?:\w+\s+){0,6}(?:a|verso|su)\s+https?://", "esfiltrazione_it"),
    (r"تجاهل\s+(?:\S+\s+){0,4}(?:التعليمات|الأوامر)", "iniezione_ar"),
    (r"أنت\s+الآن", "cambio_identita_ar"),
)

_INIEZIONE = tuple((re.compile(p, re.IGNORECASE), pid) for p, pid in PATTERN_INIEZIONE)

# Bound the work: a candidate fact is at most 300 chars, but this function is
# also used on tool output, which is not.
MAX_SCANSIONE = 65_536


def scansione(testo: str) -> str:
    """"" when the text is clean, otherwise why it was refused.

    Copied in intent from `tools/memory_tool.py:68-80`, and their reason is
    ours word for word: memory enters the system prompt as a FROZEN snapshot,
    so a poisoned entry survives the whole session and every session after it,
    until somebody removes it by hand. That is why the check happens on the
    *candidate*, not on the turn: it is the text that becomes permanent.

    Their scanner runs too when importable (inside Momo it is); it is not
    required, because a missing scan must degrade to a smaller scan, never to
    no scan at all.
    """
    testo = (testo or "")[:MAX_SCANSIONE]
    if not testo.strip():
        return ""

    invisibile = _INVISIBILI.search(testo)
    if invisibile:
        return f"carattere unicode invisibile U+{ord(invisibile.group()):04X}"

    for pattern, pid in _INIEZIONE:
        if pattern.search(testo):
            return f"sembra un tentativo di iniezione ({pid})"

    # Theirs, when we are running inside hermes-agent. Deliberately last: ours
    # is the one that must never be skipped, so it runs first and unguarded.
    try:
        from tools.threat_patterns import first_threat_message  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - live Hermes and the tests do not have it
        return ""
    try:
        loro = first_threat_message(testo, scope="strict")
    except Exception:  # noqa: BLE001 - their scanner must not break a turn
        return ""
    return str(loro) if loro else ""


def loro_scansione_disponibile() -> bool:
    """Whether `tools.threat_patterns` could be imported — for the log line."""
    try:
        from tools.threat_patterns import first_threat_message  # noqa: F401,PLC0415
        return True
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# The vetoes — what may never be written automatically, whatever a model says
# --------------------------------------------------------------------------

# Secrets. A secret in memory is a secret in the system prompt of EVERY future
# turn and inside Qdrant. There is no symmetric cost to a false negative here,
# so these patterns are allowed to be blunt.
_SEGRETI = (
    (r"\b(?:password|passwd|pwd|parola\s+d\s?ordine)\b", "password"),
    (r"\b(?:api[\s_-]?key|access[\s_-]?key|secret[\s_-]?key|client[\s_-]?secret)\b", "chiave"),
    (r"\b(?:token|bearer)\b\s*[:=]?\s*\S{12,}", "token"),
    (r"\bsk-[A-Za-z0-9_-]{16,}", "chiave"),
    (r"\b(?:gsk|ghp|ghu|ghs|xoxb|xoxp)_[A-Za-z0-9]{10,}", "chiave"),
    (r"\bAKIA[0-9A-Z]{12,}", "chiave AWS"),
    (r"-----BEGIN\s+[A-Z ]*PRIVATE\s+KEY", "chiave privata"),
    (r"\b(?:postgres(?:ql)?|mysql|mongodb|redis|amqp)://[^\s:@]+:[^\s@]+@", "DSN con credenziali"),
    (r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,28}\b", "IBAN"),
    (r"\b(?:\d[ -]?){13,19}\b", "numero di carta"),
    (r"\b(?:seed\s+phrase|frase\s+seed|mnemonic|recovery\s+phrase)\b", "seed"),
    (r"\b(?:otp|one[\s-]?time|codice\s+di\s+verifica|codice\s+usa\s+e\s+getta)\b", "codice usa e getta"),
    (r"\b(?:2fa|mfa)\s+(?:code|codice)\b", "codice usa e getta"),
)

# Volatile state. THE distinction that decides whether this memory ages well:
# «Jellyfin gira su LXC 105» is structure and is true in six months; «il disco
# è al 26%» is state and is false in an hour, and a briefing that repeats it
# lies with the face of memory.
#
# Note what is NOT here: bare «ora» and «adesso». They are far too common in
# ordinary Italian («adesso lavora a Roma» is a perfectly durable fact) and
# vetoing on them would throw away real facts. The prompt tells the model not
# to save state; these patterns are the net under it, not the whole guard.
_VOLATILI = (
    (r"\d+\s?%", "una percentuale"),
    (r"\b\d+(?:[.,]\d+)?\s?(?:GB|MB|TB|KB|GiB|MiB)\b\s*(?:liberi|usati|occupati|disponibili|"
     r"rimasti|di\s+spazio)", "uno spazio misurato"),
    (r"\b(?:uptime|load\s+average|carico\s+medio|temperatura)\b", "una misura del momento"),
    (r"\b\d+(?:[.,]\d+)?\s?°?\s?C\b", "una temperatura"),
    # «è / sta / risulta» + a state word. `su` and `giù` are deliberately NOT
    # in the list: «e su» occurs in ordinary prose («lavora con Oracle e su
    # Proxmox») and would veto real facts.
    (r"\b(?:e|sta|risulta|sembra)\s+(?:acceso|spento|attiv[oa]|inattiv[oa]|online|offline|"
     r"in\s+esecuzione|ferm[oa]|down|up)\b", "uno stato del momento"),
    (r"\b(?:in\s+questo\s+momento|al\s+momento|attualmente|proprio\s+adesso)\b",
     "uno stato del momento"),
    (r"\b(?:running|active|inactive|failed|degraded|unhealthy|healthy)\b", "uno stato del momento"),
    (r"\bversione\s+\d+\.\d+\.\d+\b", "una versione, che cambia da sola"),
)

# Appointments. A misread date becomes a phantom commitment that the briefing
# announces every single day. Dates stay with the explicit `agenda_aggiungi`
# tool — the SAME choice `forced_remember()` already makes in the live Hermes,
# which refuses to auto-save anything carrying a date.
#
# Bare month names are deliberately absent: the model is asked to date facts
# that change («da agosto 2026 abita a Roma»), and vetoing on a month would
# throw exactly those away.
_APPUNTAMENTI = (
    r"\balle\s+\d{1,2}\b",
    r"\b(?:domani|dopodomani|stasera|stamattina|stanotte|dopo\s?domani)\b",
    r"\b(?:luned|marted|mercoled|gioved|venerd|sabato|domenica)\w*\b",
    r"\b(?:appuntamento|scadenza|promemoria|ricordamelo|riunione|visita\s+medica)\b",
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
)

# Special categories. He can still say «ricordati che...» — that is a decision
# he takes in the moment. Guessing them from a conversation is not.
# `SOVEREIGN_MEMORIA_SENSIBILI=1` removes this veto; it is a named switch so
# that anyone reading the code sees a DECISION, not an oversight.
_SENSIBILI = (
    r"\b(?:malatt|diagnos|terapi|farmac|medicin|depress|ansios|ricovero|ospedal|"
    r"intervento\s+chirurg|allergi|diabet|tumor|cancro|psicolog|psichiatr)\w*",
    r"\b(?:musulman|islamic|cristian|cattolic|ebraic|ateo|agnostic|preghiera|ramadan|"
    r"credente|religios)\w*",
    r"\b(?:ha\s+votato|votera|partito\s+politico|elezion|orientamento\s+politico)\w*",
    r"\b(?:sessual|omosessual|eterosessual|bisessual|transgender)\w*",
)

_RX_SEGRETI = tuple((re.compile(p, re.IGNORECASE), q) for p, q in _SEGRETI)
_RX_VOLATILI = tuple((re.compile(p, re.IGNORECASE), q) for p, q in _VOLATILI)
_RX_APPUNTAMENTI = tuple(re.compile(p, re.IGNORECASE) for p in _APPUNTAMENTI)
_RX_SENSIBILI = tuple(re.compile(p, re.IGNORECASE) for p in _SENSIBILI)

MIN_LUNGHEZZA = 12
MAX_LUNGHEZZA = 300

# A subject must look like a NAME, not like a sentence. A web page cannot make
# Momo learn a fact whose *subject* is an imperative.
_SOGGETTI_FISSI = frozenset({"io", "impianto", "momo", "web", "casa"})
_RX_SOGGETTO = re.compile(r"^[\w àèéìòùáéíóúâêîôûäëïöüçñ'’-]{1,40}$", re.UNICODE)


def veto(testo: str, *, permetti_sensibili: bool | None = None) -> str:
    """"" when this text may be written automatically, otherwise why not.

    Runs AFTER the model, never before: the model proposes, the rule disposes.
    That is the right order because a rule cannot be talked round by a web
    page, and because a veto tested by a file that needs neither GPU nor
    network is a veto anyone can check.
    """
    grezzo = (testo or "").strip()
    if len(grezzo) < MIN_LUNGHEZZA:
        return "troppo corto per essere un fatto"
    if len(grezzo) > MAX_LUNGHEZZA:
        return f"troppo lungo ({len(grezzo)} caratteri): è un paragrafo, non un fatto"

    sporco = scansione(grezzo)
    if sporco:
        return sporco

    piatto = normalizza(grezzo)
    for pattern, quale in _RX_SEGRETI:
        if pattern.search(grezzo) or pattern.search(piatto):
            return f"contiene un segreto ({quale})"
    for pattern, quale in _RX_VOLATILI:
        # On both forms: the percentage sign only survives in `grezzo`, while
        # «è attivo» only matches once `normalizza` has turned «e'» into «e».
        if pattern.search(grezzo) or pattern.search(piatto):
            return f"è stato del momento, non struttura: {quale}"
    for pattern in _RX_APPUNTAMENTI:
        if pattern.search(grezzo):
            return "sembra un appuntamento: le date restano ad agenda_aggiungi"

    if permetti_sensibili is None:
        permetti_sensibili = os.environ.get(
            "SOVEREIGN_MEMORIA_SENSIBILI", "0").strip().lower() in {"1", "true", "on", "si", "yes"}
    if not permetti_sensibili:
        for pattern in _RX_SENSIBILI:
            if pattern.search(grezzo):
                return "dato sensibile: si salva solo con un ordine esplicito"

    # A question is not a fact, and a model that has run out of things to say
    # produces them.
    if grezzo.rstrip().endswith("?"):
        return "è una domanda, non un fatto"
    return ""


def veto_soggetto(soggetto: str) -> str:
    """The subject must be one of ours or look like a name."""
    pulito = (soggetto or "").strip()
    if not pulito:
        return "soggetto vuoto"
    if pulito.lower() in _SOGGETTI_FISSI:
        return ""
    if len(pulito) > 40 or not _RX_SOGGETTO.match(pulito):
        return f"il soggetto «{pulito[:60]}» non ha la forma di un nome"
    return ""


# --------------------------------------------------------------------------
# The triage — where the cost is switched off, before anything is spent
# --------------------------------------------------------------------------

# The guardrail's notes, so a turn it flagged can be recognised. Derived from
# the module when it is importable rather than copied, because copying them is
# how the two would drift apart the day somebody rewords a note.
def _prefissi_guardrail() -> tuple[str, ...]:
    prefissi = ["**Non ", "**Attenzione: questa risposta non regge"]
    try:
        import hermes_guardrail  # noqa: PLC0415 - lives beside this file
        for nome in ("NOTE_FAILED", "NOTE_UNVERIFIED", "NOTE_UNMET"):
            testo = getattr(hermes_guardrail, nome, "")
            if isinstance(testo, str) and testo:
                prefissi.append(testo.split("{")[0][:24])
    except Exception:  # noqa: BLE001 - the literals above are the fallback
        pass
    return tuple(dict.fromkeys(p for p in prefissi if p))


def segnata_dal_guardrail(risposta: str) -> bool:
    """True when the answer carries the guardrail's note.

    A turn in which Momo said something he had not done must not become
    memory: learning from it would launder the lie into the one place the
    guardrail can no longer reach.
    """
    testo = risposta or ""
    if "\n---\n" not in testo:
        return False
    coda = testo.rsplit("\n---\n", 1)[-1].lstrip()
    return any(coda.startswith(p) for p in _prefissi_guardrail())


_RX_DIMENTICA = re.compile(
    r"\b(?:dimentica|scorda|cancella|elimina)\b.{0,40}\b(?:memoria|ricordo|fatto|che)\b|"
    r"^\s*(?:dimentica|scordati)\b", re.IGNORECASE | re.DOTALL)

_RX_SALUTO = re.compile(
    r"^\s*(?:ciao|buongiorno|buonasera|buonanotte|ehi|hey|salve|grazie|ok|okay|va\s+bene|"
    r"perfetto|ottimo|bene|si|no|certo|d\s?accordo|👍|🙏)\W*$", re.IGNORECASE)

# What makes a turn worth a model call. Each of these is a shape in which new,
# durable information actually arrives; a turn matching none of them is thrown
# away for free.
_RX_RACCONTA = re.compile(
    r"\b(?:io\s+)?(?:lavoro|uso|preferisco|odio|amo|abito|vivo|studio|gestisco|"
    r"ho\s+(?:un|una|il|lo|la|due|tre)|mi\s+chiamo|sono\s+(?:un|uno|una|il|lo|la)|"
    r"di\s+solito|di\s+norma|sempre|mai\s+che|non\s+mi\s+piace|mi\s+piace)\b",
    re.IGNORECASE)
# «no,» is matched by position and punctuation, not by `\b...\b`: a word
# boundary after the comma never exists, so the obvious spelling silently
# never fires. Found by the test, which is what the test is for.
_RX_CORREGGE = re.compile(
    r"(?:^|[.!?\s])no[,!]|"
    r"\b(?:sbagliato|non\s+e\s+cosi|non\s+è\s+così|ti\s+sbagli|in\s+realta|in\s+realtà|"
    r"correggi|ti\s+avevo\s+detto|non\s+intendevo|invece\s+e|invece\s+è)\b", re.IGNORECASE)


def turno_da_saltare(domanda: str, risposta: str, *, contesto: str = "primary") -> str:
    """The free gates. "" means "keep going", anything else is the reason.

    Every one of these costs microseconds and each removes a whole class of
    bad memory. They run before the triage because they are cheaper than it
    and because some of them are about safety, not about cost.
    """
    if contesto and contesto != "primary":
        return f"contesto non primario ({contesto})"
    if not is_active():
        return "apprendimento spento"
    domanda = (domanda or "").strip()
    risposta = (risposta or "").strip()
    if len(domanda) < 25:
        return "messaggio troppo corto"
    if domanda.lstrip().startswith("/"):
        return "è un comando, non una conversazione"
    if _RX_SALUTO.match(domanda):
        return "è un saluto"
    if _RX_DIMENTICA.search(domanda):
        return "in un turno che parla di dimenticare non si impara"
    if not risposta:
        return "nessuna risposta da cui imparare"
    if segnata_dal_guardrail(risposta):
        return "il Guardrail ha segnato questa risposta"
    return ""


def vale_la_pena(domanda: str, risposta: str, *,
                 strumenti_ok: Iterable[str] = (),
                 strumenti_ko: Iterable[str] = ()) -> tuple[bool, str]:
    """Whether this turn earns a model call. Returns (yes/no, why).

    Deliberately generous on the *shapes* and strict on everything else: a
    missed fact can be said again, and the cheap gates above have already
    thrown away the turns where a false positive would be embarrassing.
    """
    ok = [str(s) for s in strumenti_ok]
    ko = [str(s) for s in strumenti_ko]

    if _RX_RACCONTA.search(domanda):
        return True, "la persona racconta qualcosa di sé"
    if _RX_CORREGGE.search(domanda):
        return True, "la persona sta correggendo"
    if ko and ok:
        return True, "uno strumento è fallito e poi è andato: c'è una lezione"
    if len(ok) >= 2:
        return True, "più passi riusciti: può essere una procedura"
    if ok:
        return True, f"uno strumento ha portato dati nuovi ({ok[0]})"
    return False, "niente di nuovo in questo turno"


# --------------------------------------------------------------------------
# Reading what the model answered
# --------------------------------------------------------------------------

MAX_FATTI = max(1, min(10, int(os.environ.get("SOVEREIGN_MEMORIA_MAX", "3"))))

TIPI = ("fatto", "persona", "preferenza", "progetto", "luogo", "abitudine")


def leggi_proposte(grezzo: str) -> list[dict[str, Any]]:
    """The model's JSON, read tolerantly but never guessed.

    Tolerant: ```json fences and chatter around the array are stripped.
    Never guessed: half a broken JSON is half a fact, so anything that does
    not parse yields an empty list and the turn is dropped with a log line.
    """
    testo = (grezzo or "").strip()
    if not testo:
        return []
    if "```" in testo:
        pezzi = testo.split("```")
        for pezzo in pezzi[1:]:
            corpo = pezzo.split("\n", 1)[-1] if pezzo[:16].lower().startswith("json") else pezzo
            if "[" in corpo or "{" in corpo:
                testo = corpo
                break
    inizio, fine = testo.find("["), testo.rfind("]")
    if inizio < 0 or fine <= inizio:
        inizio, fine = testo.find("{"), testo.rfind("}")
        if inizio < 0 or fine <= inizio:
            return []
        testo = "[" + testo[inizio:fine + 1] + "]"
    else:
        testo = testo[inizio:fine + 1]
    try:
        dati = json.loads(testo)
    except Exception:  # noqa: BLE001 - unparsable means nothing was learned
        return []
    if not isinstance(dati, list):
        return []

    proposte: list[dict[str, Any]] = []
    for voce in dati:
        if not isinstance(voce, dict):
            continue
        testo_fatto = str(voce.get("testo") or voce.get("contenuto") or "").strip()
        if not testo_fatto:
            continue
        soggetto = str(voce.get("soggetto") or "io").strip() or "io"
        tipo = str(voce.get("tipo") or "fatto").strip().lower()
        provenienza = str(voce.get("provenienza") or "detto").strip().lower()
        proposte.append({
            "testo": testo_fatto,
            "soggetto": soggetto,
            "tipo": tipo if tipo in TIPI else "fatto",
            "provenienza": provenienza if provenienza in ("detto", "strumento", "web") else "detto",
        })
    return proposte


# How sure we are, by where it came from. Not decoration: it is what `/memoria`
# shows and what decides which memory to re-read first.
FIDUCIA = {"detto": 0.8, "strumento": 0.6, "web": 0.5}


def fiducia_di(provenienza: str) -> float:
    return FIDUCIA.get(provenienza, 0.5)


def soggetto_di(provenienza: str, proposto: str) -> str:
    """Where a candidate is filed, given where it came from.

    Web material is quarantined under its own subject no matter what the model
    proposed: a page must never be able to file itself under «io» and come
    back looking like something he said.
    """
    if provenienza == "web":
        return "web"
    return (proposto or "io").strip() or "io"


# --------------------------------------------------------------------------
# `/memoria` — parsing what he typed, and printing what he asked for
# --------------------------------------------------------------------------

_RX_RIFERIMENTO = re.compile(r"^[#]?([fp]?)(\d{1,12})$", re.IGNORECASE)


def leggi_riferimenti(args: str) -> tuple[list[tuple[str, int]], list[str]]:
    """«f12, p3 8» -> ([("fatto",12),("procedura",3),("fatto",8)], []).

    A bare number means a fact, because facts are what he will mostly be
    deleting. Anything unrecognisable comes back in the second list so the
    caller can refuse the WHOLE batch: half a delete he did not ask for is
    worse than no delete at all.
    """
    buoni: list[tuple[str, int]] = []
    cattivi: list[str] = []
    for pezzo in re.split(r"[,\s]+", (args or "").strip()):
        if not pezzo:
            continue
        match = _RX_RIFERIMENTO.match(pezzo)
        if not match:
            cattivi.append(pezzo[:20])
            continue
        tipo = "procedura" if match.group(1).lower() == "p" else "fatto"
        voce = (tipo, int(match.group(2)))
        if voce not in buoni:
            buoni.append(voce)
    return buoni, cattivi


def _segno(voce: dict[str, Any]) -> str:
    if voce.get("tipo_voce") == "procedura":
        return "📋"
    if voce.get("soggetto") == "web":
        return "🌐"
    return "🧠" if voce.get("origine") == "dedotto" else "🖊"


def formatta_elenco(voci: list[dict[str, Any]], *, titolo: str = "",
                    larghezza: int = 90) -> str:
    """The listing he reads on Telegram: one line per entry, handle first.

    The handle is the real row id, never a position in this list. A position
    would change between the listing and the delete, and would delete the
    wrong thing — which is the one bug a review-and-delete command must not
    have.
    """
    if not voci:
        return "Non ho ancora imparato niente. (Oppure è tutto già stato cancellato.)"
    righe = [titolo] if titolo else []
    for voce in voci:
        manico = ("p" if voce.get("tipo_voce") == "procedura" else "f") + str(voce.get("id"))
        testo = str(voce.get("testo") or "").replace("\n", " ")
        if len(testo) > larghezza:
            testo = testo[:larghezza - 1].rstrip() + "…"
        soggetto = str(voce.get("soggetto") or "")
        etichetta = f"({soggetto}) " if soggetto and soggetto != "io" else ""
        quando = str(voce.get("quando") or "")[:10]
        righe.append(f"[{manico}] {_segno(voce)} {etichetta}{testo}" +
                     (f"  · {quando}" if quando else ""))
    righe.append("")
    righe.append("Per cancellarne una: /memoria dimentica " +
                 ("p" if voci[0].get("tipo_voce") == "procedura" else "f") + str(voci[0].get("id")))
    return "\n".join(righe)


AIUTO = """Quello che ho imparato da solo, e come toglierlo.

/memoria                  le ultime 20 voci
/memoria 50 · tutto       di più
/memoria cerca <parole>   cerca fra quello che ho imparato
/memoria dimentica f12 p3 cancella davvero, una o più voci
/memoria stato            acceso/spento, quanti fatti, l'ultima estrazione
/memoria pausa <motivo>   smetto di imparare da solo (non dimentico niente)
/memoria riprendi         ricomincio

🖊 me l'hai detto tu · 🧠 l'ho dedotto io · 🌐 viene dal web · 📋 procedura"""


# --------------------------------------------------------------------------
# Command line — the switch works even with Momo down, which is the point
# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    comando = (argv[1] if len(argv) > 1 else "stato").lower()
    if comando in ("stato", "status"):
        print(describe())
        return 0
    if comando in ("pausa", "pause", "ferma"):
        pausa(by=os.environ.get("SUDO_USER") or "cli",
              reason=" ".join(argv[2:]) or "senza motivo dichiarato")
        print(describe())
        return 0
    if comando in ("riprendi", "resume", "riparti"):
        riprendi(by=os.environ.get("SUDO_USER") or "cli")
        print(describe())
        return 0
    print("uso: sovereign_memoria.py [stato|pausa <motivo>|riprendi]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
