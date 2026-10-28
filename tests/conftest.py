"""Shared test setup. GIVEN CODE. Do not change it."""

import shutil
from pathlib import Path

import pytest

from agent import FIXTURE_DIR
from agent import tools

OLD_CASE = "    if code not in CODES:\n"
NEW_CASE = "    code = code.upper()\n    if code not in CODES:\n"
OLD_DATE = "    percent, last_day = CODES[code]\n"
NEW_DATE = '    percent, last_day = CODES[code]\n    if today > last_day:\n        raise ValueError("code expired")\n'


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    """A fresh copy of the project, with the tools pointed at it."""
    target = tmp_path / "workspace"
    shutil.copytree(FIXTURE_DIR, target, ignore=shutil.ignore_patterns("__pycache__"))
    tools.use_workspace(target)
    return target.resolve()


def apply(ws: Path, old: str, new: str) -> None:
    """Edit a workspace file directly, without the agent's tools."""
    path = ws / "discounts.py"
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class Approvals:
    """A scripted person: answers approvals in order and remembers what it was shown."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.seen = []

    def __call__(self, call, preview):
        self.seen.append((call, preview))
        if not self.answers:
            raise AssertionError(f"the loop asked for an approval nobody expected: {call.name}")
        return self.answers.pop(0)
