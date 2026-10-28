"""Part 4: the judge and Reflexion. GIVEN CODE. Do not change it."""

from agent.provider import ScriptedProvider, ask_tool, say
from agent.reflexion import LESSON_SYSTEM, judge, reflexion, write_lesson
from agent.toolbox import LocalToolbox
from agent.trace import TraceWriter
from conftest import NEW_CASE, NEW_DATE, OLD_CASE, OLD_DATE, Approvals, apply

TASK = "Make the tests pass."


def test_judge_fails_the_project_as_given(ws):
    passed, report = judge(ws)
    assert passed is False
    assert report.splitlines() == [
        "FAILED: 2 of 6 tests did not pass.",
        "ERROR test_rule_2_codes_ignore_case: ValueError: unknown code: save10",
        "FAIL test_rule_4_code_is_rejected_after_its_last_day: AssertionError: ValueError not raised",
    ]


def test_judge_passes_when_every_rule_holds(ws):
    apply(ws, OLD_CASE, NEW_CASE)
    apply(ws, OLD_DATE, NEW_DATE)
    assert judge(ws) == (True, "PASSED: 6 of 6 tests passed.")


def test_write_lesson():
    provider = ScriptedProvider([say("It never read spec.md.\n  Next time,   read it first.", input_tokens=70, output_tokens=12)])
    history = [{"role": "user", "text": TASK}]
    lesson, tin, tout = write_lesson(provider, TASK, history, "FAILED: 1 of 6 tests did not pass.")
    assert (lesson, tin, tout) == ("It never read spec.md. Next time, read it first.", 70, 12)
    request = provider.requests[0]
    assert request["kind"] == "complete" and request["system"] == LESSON_SYSTEM
    assert TASK in request["prompt"] and "FAILED: 1 of 6 tests did not pass." in request["prompt"]


def test_reflexion_retries_with_the_lesson(ws, tmp_path):
    notes = tmp_path / "NOTES.md"
    notes.write_text("# Notes for the agent\n", encoding="utf-8")
    provider = ScriptedProvider([
        ask_tool("edit_file", {"path": "discounts.py", "old_text": OLD_CASE, "new_text": NEW_CASE}),
        say("Codes ignore case now."),
        say("I never read spec.md. Next time I will read it before editing."),
        ask_tool("edit_file", {"path": "discounts.py", "old_text": OLD_DATE, "new_text": NEW_DATE}),
        say("Expired codes are rejected now."),
    ])
    trace = TraceWriter(None, run="runX")
    result = reflexion(TASK, provider=provider, toolbox=LocalToolbox(ws), approve=Approvals((True, ""), (True, "")),
                       trace=trace, notes_path=notes, max_attempts=2)

    assert (result.passed, result.attempts) == (True, 2)
    assert [r.status for r in result.runs] == ["done", "done"]
    assert result.lessons == ["I never read spec.md. Next time I will read it before editing."]
    assert notes.read_text().splitlines()[-1] == (
        "- Lesson from runX, attempt 1: I never read spec.md. Next time I will read it before editing."
    )
    # The second attempt started with the lesson in its system prompt.
    second_attempt = [r for r in provider.requests if r["kind"] == "turn"][2]
    assert "I never read spec.md. Next time I will read it before editing." in second_attempt["system"]
    assert second_attempt["history"] == [{"role": "user", "text": TASK}]
    kinds = [(e["kind"], e["attempt"]) for e in trace.events]
    assert kinds == [("tool", 1), ("stop", 1), ("judge", 1), ("lesson", 1), ("tool", 2), ("stop", 2), ("judge", 2)]


def test_reflexion_gives_up_after_the_last_attempt(ws, tmp_path):
    notes = tmp_path / "NOTES.md"
    provider = ScriptedProvider([say("done"), say("Lesson one."), say("done again"), say("Lesson two.")])
    trace = TraceWriter(None, run="runY")
    result = reflexion(TASK, provider=provider, toolbox=LocalToolbox(ws), approve=Approvals(),
                       trace=trace, notes_path=notes, max_attempts=2)
    assert (result.passed, result.attempts, result.lessons) == (False, 2, ["Lesson one.", "Lesson two."])
    assert result.report.startswith("FAILED: 2 of 6")
    assert notes.read_text().splitlines() == [
        "- Lesson from runY, attempt 1: Lesson one.",
        "- Lesson from runY, attempt 2: Lesson two.",
    ]
