"""Part 1: the tools. GIVEN CODE. Do not change it."""

import inspect

import pytest

from agent import tools
from agent.testrunner import Problem, TestReport
from agent.tools import ToolFailure
from conftest import NEW_CASE, OLD_CASE, apply


def test_safe_path_inside(ws):
    assert tools.safe_path("discounts.py") == ws / "discounts.py"
    assert tools.safe_path("tests/test_discounts.py") == ws / "tests" / "test_discounts.py"


def test_safe_path_refuses_parent(ws):
    with pytest.raises(ToolFailure) as err:
        tools.safe_path("../judge/acceptance_test.py")
    assert str(err.value) == "../judge/acceptance_test.py is outside the project folder. Use a path inside it, such as discounts.py."


def test_safe_path_refuses_absolute(ws):
    target = str((ws / "discounts.py").resolve())
    with pytest.raises(ToolFailure):
        tools.safe_path(target)


def test_read_file_header_numbers_and_more_line(ws):
    lines = (ws / "discounts.py").read_text().splitlines()
    out = tools.read_file("discounts.py", start=1, limit=3)
    assert out.splitlines() == [
        f"discounts.py, lines 1 to 3 of {len(lines)}",
        f"   1: {lines[0]}",
        f"   2: {lines[1]}",
        f"   3: {lines[2]}",
        "(more below: call read_file with start=4)",
    ]


def test_read_file_to_the_end_has_no_more_line(ws):
    n = len((ws / "spec.md").read_text().splitlines())
    out = tools.read_file("spec.md").splitlines()
    assert out[0] == f"spec.md, lines 1 to {n} of {n}"
    assert len(out) == n + 1
    assert out[-1].startswith(f"{n:>4}: ")


def test_read_file_missing(ws):
    with pytest.raises(ToolFailure) as err:
        tools.read_file("nope.py")
    assert str(err.value) == "nope.py is not a file in the project. Call list_files to see the files."


def test_edit_file_once(ws):
    out = tools.edit_file("discounts.py", OLD_CASE, NEW_CASE)
    assert out == "Edited discounts.py: replaced 1 match."
    assert NEW_CASE in (ws / "discounts.py").read_text()


def test_edit_file_zero_times_teaches(ws):
    before = (ws / "discounts.py").read_text()
    with pytest.raises(ToolFailure) as err:
        tools.edit_file("discounts.py", "if code not in codes:", "x")
    assert str(err.value) == (
        "old_text appears 0 times in discounts.py. Read the file again with read_file and copy the exact "
        "text, including its spaces, without the line numbers."
    )
    assert (ws / "discounts.py").read_text() == before


def test_edit_file_two_times_teaches(ws):
    before = (ws / "discounts.py").read_text()
    with pytest.raises(ToolFailure) as err:
        tools.edit_file("discounts.py", "return total_cents", "return 0")
    assert str(err.value) == (
        "old_text appears 2 times in discounts.py. Include more of the surrounding lines so that it appears exactly once."
    )
    assert (ws / "discounts.py").read_text() == before


def test_run_tests_on_the_project(ws):
    assert tools.run_tests() == (
        "FAILED: 1 of 4 tests did not pass.\n"
        "ERROR test_lowercase_code_works: ValueError: unknown code: save10"
    )


def test_run_tests_after_a_fix(ws):
    apply(ws, OLD_CASE, NEW_CASE)
    assert tools.run_tests() == "PASSED: 4 of 4 tests passed."


def test_format_report_shows_at_most_ten_problems():
    problems = tuple(Problem("FAIL", f"test_{i:02d}", "AssertionError: 1 != 2") for i in range(12))
    lines = tools.format_report(TestReport(total=20, problems=problems)).splitlines()
    assert lines[0] == "FAILED: 12 of 20 tests did not pass."
    assert lines[1] == "FAIL test_00: AssertionError: 1 != 2"
    assert len(lines) == 12
    assert lines[-1] == "(2 more not shown)"


@pytest.mark.parametrize("fn", tools.TOOLS, ids=lambda f: f.__name__)
def test_every_tool_has_a_real_description(fn):
    doc = inspect.getdoc(fn) or ""
    assert "TODO" not in doc, f"write the description of {fn.__name__}"
    assert len(doc.split()) >= 20, f"the description of {fn.__name__} is too short to guide a model"
