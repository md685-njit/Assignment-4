"""The agent loop: decide, act, observe, repeat. Part 3 of HANDOUT.md.

YOU WRITE: build_system_prompt, run_agent.
GIVEN (do not change): BASE_SYSTEM, NOTES_HEADER.

run_agent is the ReAct loop, written against a real tool-calling API. It
must be your own code: no agent framework, and no SDK helper that runs the loop for you.
"""

from __future__ import annotations

from typing import Any

from agent.core import (
    AIError,
    Approver,
    Limits,
    RunResult,
    ToolSpec,
    tool_result_message,
    user_message,
)
from agent.policy import budget_stop, gate_for, is_stuck
from agent.trace import TraceWriter

BASE_SYSTEM = """You are a careful coding agent working in a small Python project.
You can see and change the project only through the tools you are given.
Before each tool call, write one short sentence that says what you will do and why.
Change only what the task needs, one edit at a time.
A person reviews every edit. If they reject one, read their reason and follow it.
When you are finished, reply without calling a tool, in one or two sentences that say what you changed."""

NOTES_HEADER = "Notes from earlier runs. Read them before you start:"


# build_system_prompt(notes) returns the system prompt for one attempt.
#   - If notes is empty or only whitespace: return BASE_SYSTEM.
#   - Otherwise: BASE_SYSTEM, a blank line, NOTES_HEADER, a newline, then notes.strip().
#     That is: BASE_SYSTEM + "\n\n" + NOTES_HEADER + "\n" + notes.strip()
#   This is long-term memory: the text of NOTES.md, put in front of the model at every start.
def build_system_prompt(notes: str) -> str:
    raise NotImplementedError("Part 3: write build_system_prompt in agent/loop.py")


# run_agent(...) runs one attempt at the task and returns a RunResult.
#
# Before the loop:
#   - system = build_system_prompt(notes); history = [user_message(task)]
#   - Offer the model only the tools your policy does not deny:
#     every spec in toolbox.specs() for which gate_for(spec.name, {})[0] != "deny".
#   - Keep counters: steps (model calls), input and output tokens, the last run_tests
#     output, and the number of successful edits since the last run_tests.
#
# Each time around the loop:
#   1. reason = budget_stop(steps, input + output tokens, limits). If there is a reason,
#      stop with status "budget" and that reason, without calling the model.
#   2. turn = provider.next_turn(system, history, specs). If it raises AIError, stop with
#      status "error" and str(error) as the reason. Otherwise add 1 to steps, add the
#      turn's tokens, and append turn.message to the history.
#   3. If turn.tool_calls is empty, the model is finished: stop with status "done", reason
#      "the model replied without a tool call", and turn.text as the final text.
#   4. For every call in turn.tool_calls, in order:
#        decision, why = gate_for(call.name, call.args)
#        deny:  do not run it. ok is False; text is f"Refused by policy: {why}"
#        ask:   preview = toolbox.preview(call.name, call.args)
#               If preview is None, the call cannot succeed, so run it without asking
#               (the tool returns its own error). Otherwise approved, reason = approve(call, preview).
#               Rejected: do not run it. ok is False; text is
#                   f"A person rejected this {call.name} call. Reason: {reason}"
#               Approved: ok, text = toolbox.call(call.name, call.args)
#        allow: ok, text = toolbox.call(call.name, call.args)
#      Then append tool_result_message(call, text, ok) to the history, and write one
#      trace.tool(...) event: attempt, step (the current steps count), thought (turn.text),
#      tool, input (call.args), gate (the decision), approved (True or False if a person
#      was asked, otherwise None), reason (the person's reason when rejected, otherwise ""),
#      ok, output (text), and the turn's input_tokens and output_tokens.
#      Bookkeeping: a successful edit_file adds 1 to the edits count. After a successful
#      run_tests, check is_stuck(last_output, text, edits); then remember text as the last
#      output and set the edits count back to 0.
#   5. If is_stuck was True for any run_tests in this turn, stop with status "stuck" and
#      reason "the same tests failed the same way after an edit".
#
# Every way of stopping writes exactly one trace.stop(...) event (attempt, step = steps,
# status, reason, final_text, and the attempt's total input_tokens and output_tokens) and
# returns RunResult(status, reason, steps, input_tokens, output_tokens, final_text, history).
def run_agent(
    task: str,
    *,
    provider: Any,
    toolbox: Any,
    approve: Approver,
    trace: TraceWriter,
    limits: Limits = Limits(),
    notes: str = "",
    attempt: int = 1,
) -> RunResult:
    raise NotImplementedError("Part 3: write run_agent in agent/loop.py")
