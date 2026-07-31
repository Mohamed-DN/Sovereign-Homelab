"""The guardrail plugin, driven with the same kwargs hermes-agent passes.

Deploy-time test, not a unit test: it needs the real memory store (Postgres
reachable, `psycopg2` from apt) because `pre_llm_call` really executes an
explicit "ricordati che ..." order — that IS the first defence, and faking it
out would test something else. Run on LXC 102 as:

    HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes \
    /opt/momo/venv/bin/python scripts/momo/sovereign_guardrail/tests/test_plugin_wiring.py

`HERMES_VAULT_OWNER` is forced to a throwaway name so a run of this script
never lands rows under Mohamed's real memory with `source='detto'` when
nothing was really said by him — a test's own leftovers claiming to be
something the owner said would be exactly the kind of lie this module exists
to catch.
"""
from __future__ import annotations

import os
import sys

os.environ["HERMES_VAULT_OWNER"] = "guardrail-test"
sys.path.insert(0, os.environ.get("HERMES_HOME", "/opt/momo/home/.hermes") + "/plugins")
sys.path.insert(0, os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes"))

import sovereign_guardrail as G  # noqa: E402

FAIL = 0


def turn(name: str, session: str, question: str,
         tool_log: list[tuple[str, str]], answer: str,
         expect_rule: str | None, sender: str = "") -> None:
    """One whole turn, hook by hook, exactly in hermes-agent's order."""
    global FAIL
    G.on_pre_llm_call(session_id=session, user_message=question, sender_id=sender,
                      task_id="t", turn_id="1", conversation_history=[],
                      is_first_turn=True, model="qwen3.5:9b", platform="cli",
                      parent_session_id="")
    for tool_name, result in tool_log:
        G.on_post_tool_call(tool_name=tool_name, args={}, result=result,
                            session_id=session, task_id="t", turn_id="1",
                            tool_call_id="c1", api_request_id="", duration_ms=1,
                            status="success", error_type=None, error_message=None,
                            middleware_trace=[])
    out = G.on_transform_llm_output(response_text=answer, session_id=session,
                                    model="qwen3.5:9b", platform="cli")
    fired = None
    if out:
        if "Non è andata come ho detto" in out:
            fired = "claim_over_failed_tool"
        elif "Non ho salvato niente" in out:
            fired = "unverified_write_claim"
        elif "Non l'ho fatto" in out:
            fired = "unmet_write_request"
        else:
            fired = "?"
    ok = fired == expect_rule
    FAIL += 0 if ok else 1
    print(f"{'OK ' if ok else 'NO '} {name}")
    if not ok:
        print(f"     atteso={expect_rule} ottenuto={fired}")
        print(f"     risposta finale: {out[:220]!r}")


turn("pretesa senza nessuno strumento", "s1",
     "la mia macchina è una Golf grigia",
     [],
     "Ho salvato: Macchina Golf grigia.",
     "unverified_write_claim")

turn("send_mail ha girato ed è fallito, ma dice di aver mandato", "s2",
     "manda una mail a giulia",
     [("send_mail", "Non trovo «giulia» in rubrica. Aggiungilo alla rubrica e poi chiedimelo di nuovo.")],
     "Ho inviato la mail a Giulia.",
     "claim_over_failed_tool")

turn("ordine di scrivere mai eseguito", "s3",
     "scrivi nel vault che devo chiamare l'idraulico",
     [],
     "Ecco il testo che potresti annotare.",
     "unmet_write_request")

turn("scrittura riuscita davvero: nessuna nota", "s4",
     # Deliberatamente NON un ordine esplicito ("il gatto si chiama Pixel,
     # salvalo" non comincia con un verbo di comando): _REMEMBER_ORDER non lo
     # intercetta, quindi il tool loggato sotto e' l'unica scrittura simulata.
     # Trovato il contrario per errore il 2026-07-31: la prima versione di
     # questo caso usava "ricorda che...", che il codice esegue DAVVERO in
     # pre_llm_call, e la pulizia in fondo a questo file non copriva quella
     # frase -- ha lasciato un fatto vero (sotto "guardrail-test", non
     # "mohamed", ma comunque un residuo) per due run consecutive.
     "il gatto si chiama Pixel, salvalo",
     [("ricorda", '{"ok": true, "id": 99}')],
     "Ho salvato: il tuo gatto si chiama Pixel.",
     None)

# Verified, not assumed: s4's question must NOT have triggered a real write.
# `facts_recent` for the throwaway owner should still be empty at this point.
try:
    import hermes_memory
    _pre_check = hermes_memory.MemoryStore().facts_recent("guardrail-test", limit=10)
    _bad = [f for f in _pre_check if "pixel" in f["testo"].lower()]
    if _bad:
        FAIL += 1
        print(f"NO  s4 ha scritto DAVVERO in memoria (non doveva): {_bad}")
    else:
        print("OK  s4 non ha scritto niente in memoria (verificato, non assunto)")
except Exception as exc:  # noqa: BLE001
    print("controllo pre-s5 non eseguito:", exc)

# THE FIRST DEFENCE. An explicit order is carried out by CODE in
# `pre_llm_call`, before the model speaks. So the model claiming to have saved
# it is telling the truth even though it called nothing, and the guard must
# stay quiet — otherwise the guard itself becomes the liar. This case really
# writes to (and then cleans up from) `guardrail-test`'s memory.
turn("ordine esplicito eseguito dal codice: nessuna accusa", "s5",
     "ricordati che la prova del guardrail è passata",
     [],
     "Ho salvato quello che mi hai detto.",
     None)

turn("le sessioni non si mescolano: s6 non eredita il log di s2", "s6",
     "che ore sono?",
     [],
     "Sono le 14:30.",
     None)

# The hermes-agent status field must beat the result text: a tool that raised
# is not a tool that worked, however friendly its output looks.
G.on_pre_llm_call(session_id="s7", user_message="manda una mail al proprietario",
                  sender_id="", task_id="t", turn_id="1", conversation_history=[],
                  is_first_turn=True, model="m", platform="cli", parent_session_id="")
G.on_post_tool_call(tool_name="send_mail", args={}, result="Email inviata a mohamed.",
                    session_id="s7", status="error", error_message="connection reset",
                    task_id="t", turn_id="1", tool_call_id="c", api_request_id="",
                    duration_ms=1, error_type="IOError", middleware_trace=[])
out = G.on_transform_llm_output(response_text="Ho inviato la mail.", session_id="s7",
                               model="m", platform="cli")
ok = bool(out) and "Non ho salvato niente" in out
FAIL += 0 if ok else 1
print(f"{'OK ' if ok else 'NO '} status=error batte il testo del risultato")
if not ok:
    print(f"     risposta finale: {out[:220]!r}")

# The identity that pre_tool_call never sees, captured where it does arrive.
G.on_pre_llm_call(session_id="s8", user_message="ciao", sender_id="mohamed",
                  task_id="t", turn_id="1", conversation_history=[], is_first_turn=True,
                  model="m", platform="telegram", parent_session_id="")
got = G.session_sender("s8")
ok = got == "mohamed"
FAIL += 0 if ok else 1
print(f"{'OK ' if ok else 'NO '} sender_id catturato dalla sessione (={got!r})")

# Take back what the first-defence case (s5) really wrote.
try:
    import hermes_memory
    store = hermes_memory.MemoryStore()
    print("pulizia:", store.forget("guardrail-test", "la prova del guardrail è passata"))
except Exception as exc:  # noqa: BLE001
    print("PULIZIA NON RIUSCITA, controlla a mano:", exc)
    FAIL += 1

print(f"\n{'TUTTO PASSATO' if not FAIL else str(FAIL) + ' CASI FALLITI'}")
sys.exit(1 if FAIL else 0)
