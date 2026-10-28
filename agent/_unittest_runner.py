"""Runs unittest tests in a separate process and prints the result as one JSON line.

GIVEN CODE. Do not change it. agent/testrunner.py starts this file; you never run it
yourself. It uses only the standard library and imports nothing from the agent, because
the code under test was written by a model and runs here, not inside the agent.
"""

import argparse
import io
import json
import os
import sys
import unittest

MARKER = "@@A4-TEST-RESULT@@"
MAX_MESSAGE = 200


def last_line(traceback_text: str) -> str:
    lines = [line.strip() for line in traceback_text.strip().splitlines() if line.strip()]
    text = lines[-1] if lines else "(no message)"
    return text if len(text) <= MAX_MESSAGE else text[: MAX_MESSAGE - 3] + "..."


def test_name(test) -> str:
    name = getattr(test, "_testMethodName", None)
    if name and name != "runTest":
        return name
    return str(test).split(" ")[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--tests", required=True)
    parser.add_argument("--pattern", default="test*.py")
    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace)
    tests = os.path.abspath(args.tests)
    inside = os.path.commonpath([workspace, tests]) == workspace

    real_stdout = sys.stdout
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    os.chdir(workspace)
    sys.path.insert(0, workspace)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=tests, pattern=args.pattern, top_level_dir=workspace if inside else tests)
    result = unittest.TestResult()
    result.buffer = True
    suite.run(result)

    problems = []
    for kind, rows in (("FAIL", result.failures), ("ERROR", result.errors)):
        for test, tb in rows:
            problems.append({"kind": kind, "name": test_name(test), "message": last_line(tb)})
    for test in result.unexpectedSuccesses:
        problems.append({"kind": "FAIL", "name": test_name(test), "message": "unexpected success"})
    problems.sort(key=lambda p: (p["name"], p["kind"]))

    total = max(result.testsRun, len(problems))
    if total == 0:
        problems.append({"kind": "ERROR", "name": "(no tests)", "message": "no tests were found"})
        total = 1
    real_stdout.write(MARKER + json.dumps({"total": total, "problems": problems}) + "\n")
    real_stdout.flush()


if __name__ == "__main__":
    main()
