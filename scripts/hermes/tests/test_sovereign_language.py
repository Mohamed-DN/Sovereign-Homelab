"""The language layer, case by case. Standard library only, no model, no
network: the whole point of `sovereign_language` is that the decision is
deterministic, so the test is just phrases and expected answers.

The cases that matter most are the LAST two groups: technical sentences (where
"backup", "container" and "Proxmox" are spelled the same in both languages) and
short ones (where forcing a guess would be worse than staying quiet).

Run from anywhere:
    python3 scripts/hermes/tests/test_sovereign_language.py
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes"),
                   os.path.join(_HERE, "..")):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import sovereign_language as L  # noqa: E402

FAILURES: list[str] = []
PASSED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED  # noqa: PLW0603 - one counter, one script
    if condition:
        PASSED += 1
    else:
        FAILURES.append(f"{name}{f' -- {detail}' if detail else ''}")


def expect(text: str, lang: str, *, whisper: str = "", wconf: float = 0.0,
           note: str = "") -> None:
    result = L.detect(text, whisper_language=whisper, whisper_confidence=wconf)
    label = note or (text[:52] + ("…" if len(text) > 52 else ""))
    check(f"«{label}» -> {lang or '(non decisa)'}",
          result["lang"] == lang,
          f"ottenuto {result['lang']!r} conf={result['confidence']:.2f} ({result['reason']})")


# --- arabo: deciso dall'alfabeto, quindi regge anche su testo storpiato ----

expect("مرحبا كيف حالك اليوم", L.ARABIC)
expect("مرحباً أستزموا مجايفة حالك", L.ARABIC,
       note="il vocale VERO di Mohamed, trascritto male da whisper")
expect("السلام عليكم", L.ARABIC)
expect("ما هي حالة الخادم؟", L.ARABIC, note="qual e' lo stato del server (arabo)")
# Mixed: Arabic sentence quoting a Latin technical name stays Arabic.
expect("هل يعمل Proxmox الآن؟", L.ARABIC, note="arabo con dentro un nome tecnico latino")

result = L.detect("مرحبا كيف حالك")
check("l'arabo e' dichiarato CERTO", result["certain"] is True, str(result))


# --- italiano ---------------------------------------------------------------

expect("ciao come stai oggi", L.ITALIAN)
expect("mi puoi dire come sta il server per favore", L.ITALIAN)
expect("vorrei sapere quando è stato fatto l'ultimo backup", L.ITALIAN)
expect("non funziona più niente, cosa è successo?", L.ITALIAN)
expect("qual è la configurazione della macchina virtuale?", L.ITALIAN)


# --- inglese ----------------------------------------------------------------

expect("hello how are you today", L.ENGLISH)
expect("can you tell me what the status of the server is", L.ENGLISH)
expect("I would like to know when the last backup was done", L.ENGLISH)
expect("nothing is working anymore, what happened?", L.ENGLISH)


# --- IL CASO DIFFICILE: frasi tecniche, dove i sostantivi non aiutano -------
# "backup", "container", "server", "Proxmox", "restore" sono identici nelle due
# lingue. Se il riconoscimento guardasse le parole di contenuto, sbaglierebbe.

expect("fai un backup del container Proxmox adesso", L.ITALIAN,
       note="tecnico IT: solo le parole funzione lo distinguono")
expect("do a backup of the Proxmox container now", L.ENGLISH,
       note="tecnico EN: stessa frase, stessi sostantivi")
expect("il restore del database non è andato a buon fine", L.ITALIAN)
expect("the restore of the database did not complete", L.ENGLISH)


# --- quando NON deve decidere: meglio zitto che sbagliato -------------------

expect("ok", L.UNKNOWN, note="troppo corto")
expect("Proxmox", L.UNKNOWN, note="un nome proprio non e' una lingua")
expect("", L.UNKNOWN, note="vuoto")
expect("123 456", L.UNKNOWN, note="solo numeri")
expect(":)", L.UNKNOWN, note="nessuna lettera")

check("una direttiva non viene emessa quando non e' sicuro",
      L.directive(L.detect("ok")) == "",
      "forzare la lingua sbagliata e' peggio che non dire niente")


# --- whisper come secondo parere -------------------------------------------

# Troppo corto da solo, ma whisper ha SENTITO l'audio: gli si crede.
expect("ok", L.ITALIAN, whisper="it", wconf=0.92,
       note="troppo corto, ma whisper ha sentito l'audio")
expect("ok", L.UNKNOWN, whisper="it", wconf=0.40,
       note="troppo corto e whisper insicuro: nessuno decide")

# Accordo: la confidenza sale e diventa 'certo'.
agreement = L.detect("ciao come stai oggi amico mio", whisper_language="it",
                     whisper_confidence=0.9)
check("testo e whisper d'accordo -> certo", agreement["certain"] is True, str(agreement))

# Disaccordo: vincono le lettere, ma nessuno lo chiama certo.
clash = L.detect("mi puoi dire come sta il server per favore",
                 whisper_language="en", whisper_confidence=0.9)
check("disaccordo -> vincono le lettere", clash["lang"] == L.ITALIAN, str(clash))
check("disaccordo -> NON certo", clash["certain"] is False, str(clash))
check("disaccordo -> lo scrive nel motivo", "non concordano" in clash["reason"], str(clash))

# Whisper non deve poter ribaltare l'alfabeto arabo.
override = L.detect("مرحبا كيف حالك اليوم", whisper_language="en", whisper_confidence=0.99)
check("whisper NON puo' ribaltare l'alfabeto arabo", override["lang"] == L.ARABIC,
      "l'alfabeto e' un fatto, non un'opinione")


# --- la direttiva che finisce nel prompt ------------------------------------

line = L.directive(L.detect("مرحبا كيف حالك اليوم"))
check("la direttiva araba nomina l'arabo", "arabo" in line, line)
check("la direttiva e' una constatazione, non una richiesta",
      "ti ha appena parlato" in line, line)
check("la direttiva lascia la porta aperta a un cambio esplicito",
      "esplicitamente" in line, line)
check("la direttiva italiana nomina l'italiano",
      "italiano" in L.directive(L.detect("ciao come stai oggi amico")), "")
check("la direttiva inglese nomina l'inglese",
      "inglese" in L.directive(L.detect("hello how are you today my friend")), "")


print(f"casi passati: {PASSED}")
if FAILURES:
    for failure in FAILURES:
        print(f"FALLITO: {failure}")
    print(f"test_sovereign_language: {len(FAILURES)} caso/i fallito/i")
    raise SystemExit(1)
print("test_sovereign_language OK")
