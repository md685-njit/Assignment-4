"""CS 690 Assignment 4: a coding agent you build yourself.

GIVEN CODE. Do not change it.

These paths are used everywhere. They are absolute, so every command works from the
top folder of the repository.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "fixture"    # the small project the agent fixes; never edited
JUDGE_DIR = ROOT / "judge"        # the acceptance tests; outside every workspace
RUNS_DIR = ROOT / "runs"          # one folder per recorded run
NOTES_FILE = ROOT / "NOTES.md"    # the agent's long-term memory
ENV_FILE = ROOT / ".env"          # your key and settings; never commit it
SERVER_FILE = ROOT / "server.py"  # your MCP server (Part 5)
