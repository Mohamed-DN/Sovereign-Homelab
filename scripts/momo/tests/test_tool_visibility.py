"""How many tools does Momo actually offer, split by engine — counted, not
remembered. Two independent sources, gated by two independent plugins:

  sovereign_tools  ctx.register_tool() + check_fn, 11 tools (9 private + 2
                   public web tools) — the household's estate/vault/mail/MASTER
  sovereign        MemoryProvider.get_tool_schemas(), 10 memory tools
                   (ricorda, dimentica, agenda, procedure, rubrica)

The two mechanisms are NOT the same code path in hermes-agent: a memory
provider's schemas bypass `check_fn` entirely (see the module docstring in
`scripts/momo/sovereign/__init__.py` for what that cost, found 2026-07-31).
This script is the number that backs the "21 su motore di casa, 2 su motore
esterno" claim in PIANO_AGENT_MOMO.md §4 — rerun it after touching either
plugin rather than trusting memory of what it used to say.

Run on LXC 102:
    HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes \
    /opt/momo/venv/bin/python scripts/momo/tests/test_tool_visibility.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.environ.get("HERMES_HOME", "/opt/momo/home/.hermes") + "/plugins")
sys.path.insert(0, os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes"))

import sovereign as mem_plugin  # noqa: E402
import sovereign_tools as st  # noqa: E402

h = st._hermes()

# --- sovereign_tools: what register() actually registers -------------------
registered = [n for n in h.TOOLS if n not in st._MEMORY_TOOLS]
private_st = [n for n in registered if n in h.PRIVATE_TOOLS]
public_st = [n for n in registered if n not in h.PRIVATE_TOOLS]

# --- sovereign: the memory provider, gated as of 2026-07-31 -----------------
provider = mem_plugin.SovereignMemoryProvider()
mem_home = provider.get_tool_schemas()
_orig = mem_plugin.SovereignMemoryProvider._engine_is_private
mem_plugin.SovereignMemoryProvider._engine_is_private = staticmethod(lambda: False)
try:
    mem_ext = provider.get_tool_schemas()
finally:
    mem_plugin.SovereignMemoryProvider._engine_is_private = _orig

home_total = len(registered) + len(mem_home)
ext_total = len(public_st) + len(mem_ext)

print("sovereign_tools:", len(registered), "totali —",
     len(private_st), "privati,", len(public_st), "pubblici", sorted(public_st))
print("sovereign (memoria):", len(mem_home), "su motore di casa,", len(mem_ext), "su motore esterno")
print(f"\nmotore DI CASA : {home_total} strumenti")
print(f"motore ESTERNO : {ext_total} strumenti")

# The invariant that must never regress: an external engine sees web tools
# only, and NOTHING from the household (estate, vault, mail, MASTER, memory).
bad = []
if mem_ext:
    bad.append(f"la memoria e' visibile a un motore esterno: {mem_ext!r}")
if set(public_st) - {"web_fetch", "web_search"}:
    bad.append(f"uno strumento non-web e' pubblico: {set(public_st) - {'web_fetch', 'web_search'}}")

if bad:
    print("\nFALLITO:")
    for b in bad:
        print(" -", b)
    sys.exit(1)
print("\nOK: un motore esterno vede solo web, zero dati di casa.")
