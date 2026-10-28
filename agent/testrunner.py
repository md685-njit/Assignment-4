"""Run a folder of unittest tests against a workspace, in a separate process.

GIVEN CODE. Do not change it. You call run_unittests() from run_tests (Part 1) and from
judge (Part 4), and turn its TestReport into text with your format_report.

The tests run in their own Python process with a time limit, so code the model wrote
cannot hang or crash the agent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RUNNER = Path(__file__).resolve().parent / "_unittest_runner.py"
MARKER = "@@A4-TEST-RESULT@@"


@dataclass(frozen=True)
class Problem:
    """One test that did not pass.

    kind     "FAIL" (an assertion failed) or "ERROR" (the test raised an exception,
             or the test file could not even be imported)
    name     the test method name, for example "test_lowercase_code_works"
    message  the last line of the error, for example "ValueError: unknown code: save10"
    """

    kind: str
    name: str
    message: str


@dataclass(frozen=True)
class TestReport:
    """The result of one test run. `problems` is empty when every test passed."""

    __test__ = False  # tells pytest this is not a test class

    total: int
    problems: tuple[Problem, ...]
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return not self.timed_out and not self.problems and self.total > 0


def run_unittests(
    workspace: Path,
    tests_dir: Path | None = None,
    timeout: float = 20.0,
    pattern: str = "test*.py",
) -> TestReport:
    """Run the test files matching `pattern` in tests_dir (default: workspace/tests).

    The code under test is imported from `workspace`. Returns TestReport(timed_out=True)
    if the tests take longer than `timeout` seconds.
    """
    workspace = Path(workspace).resolve()
    tests_dir = Path(tests_dir).resolve() if tests_dir is not None else workspace / "tests"
    cmd = [sys.executable, "-I", "-B", str(RUNNER), "--workspace", str(workspace), "--tests", str(tests_dir), "--pattern", pattern]
    try:
        proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return TestReport(total=0, problems=(), timed_out=True)

    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARKER):
            data = json.loads(line[len(MARKER):])
            problems = tuple(Problem(p["kind"], p["name"], p["message"]) for p in data["problems"])
            return TestReport(total=int(data["total"]), problems=problems)

    detail = (proc.stderr.strip().splitlines() or ["no output"])[-1][:200]
    return TestReport(
        total=1,
        problems=(Problem("ERROR", "(test run)", f"the test process stopped before reporting: {detail}"),),
    )
