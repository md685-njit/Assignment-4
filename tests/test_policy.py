"""Part 2: gates and stop rules. GIVEN CODE. Do not change it."""

from agent.core import Limits
from agent.policy import TESTS_RULE, budget_stop, gate_for, is_stuck


def test_read_only_tools_are_allowed():
    for name in ("list_files", "read_file", "run_tests"):
        assert gate_for(name, {}) == ("allow", "")


def test_edits_ask_a_person():
    assert gate_for("edit_file", {"path": "discounts.py", "old_text": "a", "new_text": "b"}) == ("ask", "")


def test_unknown_tools_are_denied():
    assert gate_for("delete_file", {"path": "discounts.py"}) == ("deny", "delete_file is not one of this agent's tools.")


def test_edits_to_tests_are_denied():
    for path in ("tests/test_discounts.py", "./tests/test_discounts.py"):
        assert gate_for("edit_file", {"path": path, "old_text": "a", "new_text": "b"}) == ("deny", TESTS_RULE)


def test_a_name_that_only_starts_with_tests_is_not_in_tests():
    assert gate_for("edit_file", {"path": "testsuite.py", "old_text": "a", "new_text": "b"}) == ("ask", "")


def test_budget_stop():
    limits = Limits(max_steps=5, max_tokens=1000)
    assert budget_stop(4, 999, limits) is None
    assert budget_stop(5, 0, limits) == "step budget reached: 5 of 5 model calls"
    assert budget_stop(1, 1000, limits) == "token budget reached: 1000 of 1000 tokens"
    assert budget_stop(5, 5000, limits).startswith("step budget")


def test_is_stuck():
    fail = "FAILED: 1 of 4 tests did not pass.\nERROR test_x: ValueError: boom"
    assert is_stuck(fail, fail, 1) is True
    assert is_stuck(fail, fail, 0) is False
    assert is_stuck(fail, fail.replace("boom", "bang"), 1) is False
    assert is_stuck("PASSED: 4 of 4 tests passed.", "PASSED: 4 of 4 tests passed.", 1) is False
