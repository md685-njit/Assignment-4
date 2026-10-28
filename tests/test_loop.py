"""Part 3: the loop. GIVEN CODE. Do not change it.

These tests use a scripted model (no API key, no cost) and a person played by Approvals.
"""

from agent.core import AIError, Limits
from agent.loop import BASE_SYSTEM, NOTES_HEADER, build_system_prompt, run_agent
from agent.provider import ScriptedProvider, ask_tool, say
from agent.toolbox import LocalToolbox
from agent.trace import TraceWriter
from conftest import NEW_CASE, OLD_CASE, Approvals

TASK = "Make the tests pass."


def run(ws, replies, approvals=None, limits=Limits(), notes=""):
    provider = ScriptedProvider(replies)
    trace = TraceWriter(None, run="test")
    approve = approvals if approvals is not None else Approvals()
    result = run_agent(TASK, provider=provider, toolbox=LocalToolbox(ws), approve=approve, trace=trace,
                       limits=limits, notes=notes)
    return result, provider, trace


def test_build_system_prompt():
    assert build_system_prompt("") == BASE_SYSTEM
    assert build_system_prompt("  \n") == BASE_SYSTEM
    assert build_system_prompt("\n- read spec.md first\n") == BASE_SYSTEM + "\n\n" + NOTES_HEADER + "\n- read spec.md first"


def test_happy_path(ws):
    approvals = Approvals((True, ""))
    result, provider, trace = run(ws, [
        ask_tool("run_tests", {}, "I will run the tests.", input_tokens=100, output_tokens=10),
        ask_tool("read_file", {"path": "discounts.py"}, "I will read the code.", input_tokens=200, output_tokens=10),
        ask_tool("edit_file", {"path": "discounts.py", "old_text": OLD_CASE, "new_text": NEW_CASE}, "Fix case.",
                 input_tokens=300, output_tokens=30),
        ask_tool("run_tests", {}, "Check again.", input_tokens=400, output_tokens=10),
        say("Codes now ignore case.", input_tokens=500, output_tokens=10),
    ], approvals)

    assert (result.status, result.steps) == ("done", 5)
    assert (result.input_tokens, result.output_tokens) == (1500, 70)
    assert result.final_text == "Codes now ignore case."
    assert NEW_CASE in (ws / "discounts.py").read_text()

    # The model was offered the four tools, and saw each result before its next decision.
    assert [t.name for t in provider.requests[0]["tools"]] == ["list_files", "read_file", "edit_file", "run_tests"]
    assert provider.requests[0]["system"] == BASE_SYSTEM
    second = provider.requests[1]["history"]
    assert [m["role"] for m in second] == ["user", "assistant", "tool"]
    assert second[-1]["text"].startswith("FAILED: 1 of 4")

    # The person saw a diff before the edit was made.
    assert len(approvals.seen) == 1
    assert "+    code = code.upper()" in approvals.seen[0][1]

    kinds = [e["kind"] for e in trace.events]
    assert kinds == ["tool", "tool", "tool", "tool", "stop"]
    edit = trace.events[2]
    assert (edit["step"], edit["tool"], edit["gate"], edit["approved"], edit["ok"]) == (3, "edit_file", "ask", True, True)
    assert trace.events[0]["approved"] is None
    stop = trace.events[-1]
    assert (stop["status"], stop["step"], stop["input_tokens"], stop["output_tokens"]) == ("done", 5, 1500, 70)


def test_a_rejection_goes_back_to_the_model(ws):
    before = (ws / "discounts.py").read_text()
    result, provider, trace = run(ws, [
        ask_tool("edit_file", {"path": "discounts.py", "old_text": OLD_CASE, "new_text": NEW_CASE}),
        say("I will stop."),
    ], Approvals((False, "Add a comment that names the spec rule.")))

    assert (ws / "discounts.py").read_text() == before
    reply = provider.requests[1]["history"][-1]
    assert reply["role"] == "tool" and reply["is_error"] is True
    assert reply["text"] == "A person rejected this edit_file call. Reason: Add a comment that names the spec rule."
    event = trace.events[0]
    assert (event["approved"], event["reason"], event["ok"]) == (False, "Add a comment that names the spec rule.", False)


def test_a_denied_call_never_runs_and_nobody_is_asked(ws):
    before = (ws / "tests" / "test_discounts.py").read_text()
    result, provider, trace = run(ws, [
        ask_tool("edit_file", {"path": "tests/test_discounts.py", "old_text": "1800", "new_text": "0"}),
        say("I will stop."),
    ], Approvals())  # no answers: asking would fail the test

    assert (ws / "tests" / "test_discounts.py").read_text() == before
    reply = provider.requests[1]["history"][-1]
    assert reply["text"].startswith("Refused by policy: ")
    assert trace.events[0]["gate"] == "deny"


def test_an_edit_that_cannot_apply_is_not_sent_for_approval(ws):
    result, provider, trace = run(ws, [
        ask_tool("edit_file", {"path": "discounts.py", "old_text": "not in the file", "new_text": "x"}),
        say("I will stop."),
    ], Approvals())

    reply = provider.requests[1]["history"][-1]
    assert reply["is_error"] is True and "appears 0 times" in reply["text"]
    assert trace.events[0]["approved"] is None


def test_the_step_budget_stops_before_another_model_call(ws):
    result, provider, trace = run(ws, [ask_tool("list_files") for _ in range(5)], limits=Limits(max_steps=2))
    assert (result.status, result.steps) == ("budget", 2)
    assert len(provider.requests) == 2
    assert result.reason == "step budget reached: 2 of 2 model calls"
    assert trace.events[-1]["kind"] == "stop"


def test_the_same_failure_after_an_edit_is_stuck(ws):
    comment = ("    if code == \"\":\n", "    # first try\n    if code == \"\":\n")
    again = ("    # first try\n", "    # second try\n")
    result, provider, trace = run(ws, [
        ask_tool("run_tests"),
        ask_tool("edit_file", {"path": "discounts.py", "old_text": comment[0], "new_text": comment[1]}),
        ask_tool("run_tests"),
        ask_tool("edit_file", {"path": "discounts.py", "old_text": again[0], "new_text": again[1]}),
        ask_tool("run_tests"),
        say("never reached"),
    ], Approvals((True, ""), (True, "")))
    assert result.status == "stuck"
    assert result.steps == 3
    assert result.reason == "the same tests failed the same way after an edit"


def test_a_provider_error_stops_the_run(ws):
    result, provider, trace = run(ws, [AIError("Anthropic rejected your API key.")])
    assert (result.status, result.reason, result.steps) == ("error", "Anthropic rejected your API key.", 0)
    assert [e["kind"] for e in trace.events] == ["stop"]


def test_notes_go_into_the_system_prompt(ws):
    result, provider, trace = run(ws, [say("ok")], notes="- read spec.md before editing")
    assert provider.requests[0]["system"].endswith(NOTES_HEADER + "\n- read spec.md before editing")
