"""Where a person must approve, and when the agent must stop. Part 2 of HANDOUT.md.

YOU WRITE: gate_for, budget_stop, is_stuck.
GIVEN (do not change): GATES, TESTS_RULE.

These are plain functions with no model calls, so they are easy to test, and your loop
(Part 3) calls them at the right moments.
"""

from __future__ import annotations

import posixpath
from typing import Any

from agent.core import Limits

# Gate each action by how hard it is to undo:
#   allow  nothing to undo: let it run
#   ask    a person sees what would change and approves or rejects it first
#   deny   never run it
GATES = {
    "list_files": "allow",
    "read_file": "allow",
    "run_tests": "allow",
    "edit_file": "ask",
}

TESTS_RULE = "The tests check the spec, so this agent may not edit files in tests/. Change the code instead."


# gate_for(tool_name, args) returns (decision, reason), where decision is "allow", "ask" or "deny".
#   - A tool that is not in GATES: ("deny", f"{tool_name} is not one of this agent's tools.")
#   - edit_file whose path is inside the tests/ folder: ("deny", TESTS_RULE).
#     Inside tests/ means: after replacing every "\" with "/" and normalizing the path with
#     posixpath.normpath, it is "tests" or starts with "tests/". So "tests/x.py",
#     "./tests/x.py", "tests\x.py" and "src/../tests/x.py" are all inside.
#     A path that is missing or not a string is not inside tests/.
#   - Anything else: (GATES[tool_name], "")
def gate_for(tool_name: str, args: dict[str, Any]) -> tuple[str, str]:
    raise NotImplementedError("Part 2: write gate_for in agent/policy.py")


# budget_stop(steps, tokens, limits) is checked before every model call.
#   steps is how many model calls this attempt has made; tokens is its input plus output tokens.
#   - steps >= limits.max_steps:   return f"step budget reached: {steps} of {limits.max_steps} model calls"
#   - tokens >= limits.max_tokens: return f"token budget reached: {tokens} of {limits.max_tokens} tokens"
#   - otherwise return None. Check the step budget first.
def budget_stop(steps: int, tokens: int, limits: Limits) -> str | None:
    raise NotImplementedError("Part 2: write budget_stop in agent/policy.py")


# is_stuck(last_output, output, edits_since_last_run) is checked after every run_tests call.
#   last_output is the previous run_tests output in this attempt (None if there was none);
#   output is this one; edits_since_last_run is how many edits succeeded in between.
#   Return True only if all three hold:
#     - output starts with "FAILED",
#     - output is exactly the same text as last_output,
#     - edits_since_last_run is at least 1 (the agent changed something, and nothing changed).
#   This is the "same failure twice" rule, made safe for an agent that simply runs the
#   tests twice in a row.
def is_stuck(last_output: str | None, output: str, edits_since_last_run: int) -> bool:
    raise NotImplementedError("Part 2: write is_stuck in agent/policy.py")
