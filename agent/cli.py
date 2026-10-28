"""The commands you run. GIVEN CODE. Do not change it.

    python -m agent check-setup [--skip-ai]       check Python, packages, .env and one tiny tool call
    python -m agent run NAME [--tools local|mcp] [--judge] [--task TEXT] [--overwrite]
                                                  record one run in runs/NAME/
    python -m agent check-trace NAME              check that a recorded run's files are complete
    python -m agent replay NAME                   re-run a recorded run from its saved replies, no API key
    python -m agent check-mcp                     start server.py over MCP and test it
    python -m agent summary                       print the run table for REPORT.md
    python -m agent fresh NAME                    make runs/NAME/workspace, a clean copy of the project
    python -m agent judge NAME                    run the visible tests and the judge on runs/NAME/workspace

README.md explains each one.
"""

from __future__ import annotations

import argparse
import inspect
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent import FIXTURE_DIR, JUDGE_DIR, NOTES_FILE, ROOT, RUNS_DIR, SERVER_FILE
from agent.core import AIError, Limits, SetupError, ToolCall, ToolSpec
from agent.trace import TraceWriter, read_trace

DEFAULT_TASK = "Make the tests pass."
MAX_ATTEMPTS = 2
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
COMPARE_KEYS = ("kind", "attempt", "step", "thought", "tool", "input", "gate", "approved", "ok", "output", "status",
                "passed", "text")


# --------------------------------------------------------------------------- helpers


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_dir(name: str) -> Path:
    if not NAME_RE.match(name):
        raise SystemExit(f"Run names use letters, digits, - and _ only (got {name!r}).")
    return RUNS_DIR / name


def _fresh_workspace(target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FIXTURE_DIR, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def _make_toolbox(mode: str, workspace: Path, log_file: Path | None = None) -> Any:
    from agent.toolbox import LocalToolbox, MCPToolbox

    if mode == "mcp":
        return MCPToolbox(workspace, log_file=log_file)
    return LocalToolbox(workspace)


def console_approve(call: ToolCall, preview: str) -> tuple[bool, str]:
    """Ask the person at the keyboard. A rejection's reason is sent to the model."""
    print()
    print(f"The agent wants to run {call.name}. This is what it would change:")
    print(preview)
    try:
        answer = input(f"Approve this {call.name}? [y/n] ").strip().lower()
        while answer not in ("y", "n"):
            answer = input("Please type y or n: ").strip().lower()
        if answer == "y":
            return True, ""
        reason = input("Reason (this is sent to the agent): ").strip()
    except EOFError:
        return False, "No person was available to approve this."
    return False, reason or "No reason given."


def _execute(meta: dict[str, Any], provider: Any, toolbox: Any, approve: Any, trace: TraceWriter,
             notes_path: Path) -> dict[str, Any]:
    """Run the agent the way meta says, and return a short result record."""
    from agent.loop import run_agent
    from agent.reflexion import judge, reflexion

    limits = Limits(**meta["limits"])
    if meta["judge_mode"] == "reflexion":
        res = reflexion(meta["task"], provider=provider, toolbox=toolbox, approve=approve, trace=trace,
                        notes_path=notes_path, limits=limits, max_attempts=meta["max_attempts"])
        return {"passed": res.passed, "attempts": res.attempts, "statuses": [r.status for r in res.runs],
                "lessons": res.lessons}
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    result = run_agent(meta["task"], provider=provider, toolbox=toolbox, approve=approve, trace=trace,
                       limits=limits, notes=notes, attempt=1)
    passed, report = judge(toolbox.workspace)
    trace.judge(attempt=1, passed=passed, report=report)
    return {"passed": passed, "attempts": 1, "statuses": [result.status], "lessons": []}


# --------------------------------------------------------------------------- run


def cmd_run(args: argparse.Namespace) -> int:
    from agent.provider import RecordingProvider, load_settings, make_provider

    run_dir = _run_dir(args.name)
    if run_dir.exists() and not args.overwrite:
        print(f"runs/{args.name} already exists. Pick a new name, or add --overwrite to replace it.")
        return 1
    try:
        settings = load_settings()
        inner = make_provider(settings)
    except SetupError as exc:
        print(f"Setup problem: {exc}")
        return 1

    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    workspace = _fresh_workspace(run_dir / "workspace")
    notes_at_start = NOTES_FILE.read_text(encoding="utf-8") if NOTES_FILE.exists() else ""
    meta: dict[str, Any] = {
        "name": args.name,
        "tools": args.tools,
        "judge_mode": "reflexion" if args.judge else "after",
        "max_attempts": MAX_ATTEMPTS if args.judge else 1,
        "task": args.task,
        "provider": settings.provider,
        "model": settings.model,
        "price_input_per_mtok": settings.price_input_per_mtok,
        "price_output_per_mtok": settings.price_output_per_mtok,
        "limits": {"max_steps": Limits().max_steps, "max_tokens": Limits().max_tokens},
        "notes_at_start": notes_at_start,
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "started": _now(),
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    provider = RecordingProvider(inner, run_dir / "replies.jsonl")
    trace = TraceWriter(run_dir / "trace.jsonl", run=args.name, echo=True)
    print(f"Run {args.name}: {settings.provider} {settings.model}, tools from {args.tools}, "
          f"judge {'with Reflexion' if args.judge else 'after the run'}.")
    print(f"Task: {args.task}\n")
    toolbox = None
    try:
        toolbox = _make_toolbox(args.tools, workspace, run_dir / "server.log")
        meta["result"] = _execute(meta, provider, toolbox, console_approve, trace, NOTES_FILE)
    except KeyboardInterrupt:
        meta["result"] = {"interrupted": True}
        print("\nInterrupted. This run is incomplete; record a new one before you submit.")
    finally:
        if toolbox is not None:
            toolbox.close()
    meta["finished"] = _now()
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print()
    _print_summary([run_dir])
    print(f"\nSaved in runs/{args.name}/. Next: python -m agent check-trace {args.name}")
    return 0


# --------------------------------------------------------------------------- replay


def cmd_replay(args: argparse.Namespace) -> int:
    from agent.provider import ReplayProvider

    run_dir = _run_dir(args.name)
    try:
        meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        recorded = read_trace(run_dir / "trace.jsonl")
    except FileNotFoundError as exc:
        print(f"Missing file: {exc.filename}")
        return 1
    if "result" not in meta or meta["result"].get("interrupted"):
        print(f"runs/{args.name} did not finish, so it cannot be replayed.")
        return 1

    answers = iter([(e["approved"], e.get("reason", "")) for e in recorded
                    if e["kind"] == "tool" and e["gate"] == "ask" and e["approved"] is not None])

    def approve(call: ToolCall, preview: str) -> tuple[bool, str]:
        try:
            return next(answers)
        except StopIteration:
            return False, "replay: the recorded run has no answer here"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        workspace = _fresh_workspace(tmp_path / "workspace")
        notes = tmp_path / "NOTES.md"
        notes.write_text(meta.get("notes_at_start", ""), encoding="utf-8")
        trace = TraceWriter(None, run=meta["name"])
        provider = ReplayProvider(run_dir / "replies.jsonl", name=meta["provider"], model=meta["model"])
        toolbox = _make_toolbox(meta["tools"], workspace)
        try:
            _execute(meta, provider, toolbox, approve, trace, notes)
        finally:
            toolbox.close()
        replayed = trace.events

    problems = _compare(recorded, replayed)
    if problems:
        print(f"Replay of runs/{args.name} does NOT match its trace:")
        for p in problems[:10]:
            print("  " + p)
        print("Either the trace was edited, or your code changed after the run. Record the run again.")
        return 1
    print(f"Replay of runs/{args.name} matches its trace: {len(recorded)} events.")
    return 0


def _comparable(event: dict[str, Any], key: str) -> Any:
    """The value replay compares. Test output is compared by its summary line only, and
    library version numbers are ignored, so a replay on another Python or library
    version still matches when the agent's behaviour is the same."""
    value = event.get(key)
    if key == "output" and isinstance(value, str):
        value = re.sub(r"errors\.pydantic\.dev/[\d.]+/", "errors.pydantic.dev/", value)
        if event.get("tool") == "run_tests" and event.get("ok"):
            value = value.splitlines()[0] if value else value
    return value


def _compare(recorded: list[dict[str, Any]], replayed: list[dict[str, Any]]) -> list[str]:
    problems = []
    for i, (a, b) in enumerate(zip(recorded, replayed), start=1):
        for key in COMPARE_KEYS:
            if _comparable(a, key) != _comparable(b, key):
                problems.append(f"event {i} ({a.get('kind')}): {key} was {a.get(key)!r} in the trace, "
                                f"{b.get(key)!r} in the replay")
                break
    if len(recorded) != len(replayed):
        problems.append(f"the trace has {len(recorded)} events; the replay produced {len(replayed)}")
    return problems


# --------------------------------------------------------------------------- check-trace


TOOL_FIELDS = {"attempt": int, "step": int, "thought": str, "tool": str, "input": dict, "gate": str,
               "reason": str, "ok": bool, "output": str, "input_tokens": int, "output_tokens": int}
STOP_FIELDS = {"attempt": int, "step": int, "status": str, "reason": str, "final_text": str,
               "input_tokens": int, "output_tokens": int}
JUDGE_FIELDS = {"attempt": int, "passed": bool, "report": str}
LESSON_FIELDS = {"attempt": int, "text": str, "input_tokens": int, "output_tokens": int}
FIELDS = {"tool": TOOL_FIELDS, "stop": STOP_FIELDS, "judge": JUDGE_FIELDS, "lesson": LESSON_FIELDS}


def check_run(run_dir: Path) -> list[str]:
    """Every problem with a recorded run's files. An empty list means it is complete."""
    problems: list[str] = []
    for fname in ("run.json", "trace.jsonl", "replies.jsonl"):
        if not (run_dir / fname).is_file():
            problems.append(f"{fname} is missing")
    if problems:
        return problems
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if "result" not in meta or meta["result"].get("interrupted"):
        problems.append("run.json has no result: the run did not finish")
    try:
        events = read_trace(run_dir / "trace.jsonl")
    except json.JSONDecodeError as exc:
        return [f"trace.jsonl is not valid JSON lines: {exc}"]
    replies = [json.loads(x) for x in (run_dir / "replies.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]

    for i, e in enumerate(events, start=1):
        kind = e.get("kind")
        if kind not in FIELDS:
            problems.append(f"event {i}: unknown kind {kind!r}")
            continue
        for key in ("run", "time"):
            if not isinstance(e.get(key), str):
                problems.append(f"event {i}: missing {key}")
        for key, typ in FIELDS[kind].items():
            if key not in e or not isinstance(e[key], typ) or (typ is int and isinstance(e[key], bool)):
                problems.append(f"event {i} ({kind}): field {key} is missing or not {typ.__name__}")
        if kind == "tool":
            if e.get("gate") not in ("allow", "ask", "deny"):
                problems.append(f"event {i}: gate must be allow, ask or deny")
            if e.get("gate") != "ask" and e.get("approved") is not None:
                problems.append(f"event {i}: approved must be null unless gate is ask")
            if e.get("approved") not in (True, False, None):
                problems.append(f"event {i}: approved must be true, false or null")
        if kind == "stop" and e.get("status") not in ("done", "budget", "stuck", "error"):
            problems.append(f"event {i}: status must be done, budget, stuck or error")

    attempts = sorted({e["attempt"] for e in events if isinstance(e.get("attempt"), int)})
    expected_attempts = meta.get("result", {}).get("attempts")
    if expected_attempts is not None and attempts and attempts != list(range(1, expected_attempts + 1)):
        problems.append(f"attempts in the trace are {attempts}, but run.json says {expected_attempts}")
    total_steps = 0
    for a in attempts:
        stops = [e for e in events if e.get("kind") == "stop" and e.get("attempt") == a]
        tools_ = [e for e in events if e.get("kind") == "tool" and e.get("attempt") == a]
        if len(stops) != 1:
            problems.append(f"attempt {a}: needs exactly one stop event, found {len(stops)}")
            continue
        stop = stops[0]
        total_steps += stop.get("step", 0)
        steps = [e.get("step", 0) for e in tools_]
        if steps != sorted(steps) or any(s < 1 or s > stop.get("step", 0) for s in steps):
            problems.append(f"attempt {a}: tool event steps must rise from 1 to the stop step")
        if meta.get("judge_mode") == "reflexion" or a == 1:
            if stop.get("status") != "error" and not any(e.get("kind") == "judge" and e.get("attempt") == a for e in events):
                problems.append(f"attempt {a}: no judge event")
    turn_replies = [r for r in replies if r.get("kind") == "turn" and "turn" in r]
    if len(turn_replies) != total_steps:
        problems.append(f"replies.jsonl has {len(turn_replies)} model replies, but the trace counts {total_steps} model calls")
    lessons = [e for e in events if e.get("kind") == "lesson"]
    completes = [r for r in replies if r.get("kind") == "complete" and "turn" in r]
    if len(lessons) != len(completes):
        problems.append(f"the trace has {len(lessons)} lessons, but replies.jsonl has {len(completes)} lesson replies")
    return problems


def cmd_check_trace(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.name)
    problems = check_run(run_dir)
    if problems:
        print(f"runs/{args.name}: {len(problems)} problem(s)")
        for p in problems:
            print("  " + p)
        return 1
    events = read_trace(run_dir / "trace.jsonl")
    print(f"runs/{args.name}: complete. {len(events)} events, "
          f"{sum(1 for e in events if e['kind'] == 'tool')} tool calls.")
    return 0


# --------------------------------------------------------------------------- summary


def _run_rows(run_dirs: list[Path]) -> list[dict[str, Any]]:
    from agent.provider import cost_usd

    rows = []
    for d in run_dirs:
        try:
            meta = json.loads((d / "run.json").read_text(encoding="utf-8"))
            events = read_trace(d / "trace.jsonl")
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        stops = [e for e in events if e["kind"] == "stop"]
        judges = [e for e in events if e["kind"] == "judge"]
        lessons = [e for e in events if e["kind"] == "lesson"]
        tin = sum(e["input_tokens"] for e in stops) + sum(e["input_tokens"] for e in lessons)
        tout = sum(e["output_tokens"] for e in stops) + sum(e["output_tokens"] for e in lessons)
        cost = cost_usd(tin, tout, meta)
        rows.append({
            "run": meta["name"],
            "tools": meta["tools"],
            "judge": meta["judge_mode"],
            "status": ", ".join(f"{e['attempt']}: {e['status']}" for e in stops) or "-",
            "calls": sum(e["step"] for e in stops) + len(lessons),
            "tool_calls": sum(1 for e in events if e["kind"] == "tool"),
            "input_tokens": tin,
            "output_tokens": tout,
            "cost": "-" if cost is None else f"${cost:.4f}",
            "verdicts": ", ".join(f"{e['attempt']}: {'PASS' if e['passed'] else 'FAIL'}" for e in judges) or "-",
        })
    return rows


def _print_summary(run_dirs: list[Path]) -> None:
    rows = _run_rows(run_dirs)
    print("| Run | Tools | Judge | Stopped (per attempt) | Model calls | Tool calls | Input tokens | Output tokens | Cost | Judge verdict |")
    print("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for r in rows:
        print(f"| {r['run']} | {r['tools']} | {r['judge']} | {r['status']} | {r['calls']} | {r['tool_calls']} | "
              f"{r['input_tokens']} | {r['output_tokens']} | {r['cost']} | {r['verdicts']} |")


def cmd_summary(args: argparse.Namespace) -> int:
    dirs = sorted([d for d in RUNS_DIR.iterdir() if (d / "run.json").is_file()], key=lambda d: (d.name not in ("runA", "runB"), d.name)) if RUNS_DIR.is_dir() else []
    if not dirs:
        print("No recorded runs yet. See HANDOUT.md Part 6.")
        return 1
    _print_summary(dirs)
    return 0


# --------------------------------------------------------------------------- check-mcp


def cmd_check_mcp(args: argparse.Namespace) -> int:
    from agent import tools
    from agent.toolbox import MCPToolbox

    failures = 0

    def report(ok: bool, label: str, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {label}{': ' + detail if detail else ''}")

    with tempfile.TemporaryDirectory() as tmp:
        workspace = _fresh_workspace(Path(tmp) / "workspace")
        log = Path(tmp) / "server.log"
        try:
            box = MCPToolbox(workspace, log_file=log, timeout=30)
        except Exception as exc:
            report(False, "start server.py over stdio", str(exc))
            print("\nThe server's own error output:")
            print(log.read_text(encoding="utf-8")[-3000:] if log.exists() else "(none)")
            return 1
        try:
            report(True, "start server.py over stdio and connect")
            specs = box.specs()
            print("\ntools/list returned (this is all the model ever sees of each tool):")
            print(json.dumps([{"name": s.name, "description": s.description, "inputSchema": s.input_schema} for s in specs], indent=2))
            print()
            names = [s.name for s in specs]
            expected = [fn.__name__ for fn in tools.TOOLS]
            report(names == expected, "the server offers the four tools, in order", ", ".join(names))
            for fn in tools.TOOLS:
                spec = next((s for s in specs if s.name == fn.__name__), None)
                same = spec is not None and " ".join(spec.description.split()) == " ".join((inspect.getdoc(fn) or "").split())
                report(same, f"{fn.__name__}: description matches its docstring in agent/tools.py")
            ok, text = box.call("list_files", {})
            report(ok and "discounts.py" in text, "tools/call list_files", text.replace("\n", ", "))
            ok, text = box.call("run_tests", {})
            report(ok and text.startswith("FAILED"), "tools/call run_tests", text.splitlines()[0] if text else "(empty)")
            ok, text = box.call("edit_file", {"path": "discounts.py", "old_text": "no such text", "new_text": "x"})
            report(not ok and "appears 0 times" in text, "a refused edit comes back with isError true and your message", text[:120])
            ok, text = box.call("read_file", {"path": "../judge/acceptance_test.py"})
            report(not ok and "outside the project folder" in text, "the server refuses a path outside the project", text[:120])
        finally:
            box.close()
    print()
    print("check-mcp: all checks passed." if failures == 0 else f"check-mcp: {failures} check(s) failed.")
    return 0 if failures == 0 else 1


# --------------------------------------------------------------------------- check-setup


def cmd_check_setup(args: argparse.Namespace) -> int:
    import importlib
    import hashlib

    failures = 0

    def report(ok: bool, label: str, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {label}{': ' + detail if detail else ''}")

    v = sys.version_info
    report((3, 11) <= v[:2] <= (3, 13), "Python 3.11 to 3.13", f"you have {v.major}.{v.minor}.{v.micro}")
    for module, label in (("anthropic", "anthropic"), ("openai", "openai"), ("mcp", "mcp"), ("dotenv", "python-dotenv"), ("pytest", "pytest")):
        try:
            importlib.import_module(module)
            from importlib.metadata import version

            report(True, f"package {label}", version(label))
        except Exception:
            report(False, f"package {label}", "not installed; run: pip install -r requirements.txt")

    digest = hashlib.sha256()
    for p in sorted(list(FIXTURE_DIR.rglob("*")) + list(JUDGE_DIR.rglob("*"))):
        if p.is_file() and "__pycache__" not in p.parts:
            digest.update(p.relative_to(ROOT).as_posix().encode())
            digest.update(p.read_bytes().replace(b"\r\n", b"\n"))
    report(digest.hexdigest()[:16] == FIXTURE_DIGEST, "fixture/ and judge/ are unchanged", digest.hexdigest()[:16])

    from agent.provider import load_settings, make_provider

    settings = None
    try:
        settings = load_settings()
        masked = (settings.api_key[:7] + "...") if settings.api_key else "(none)"
        report(settings.api_key is not None, ".env", f"provider {settings.provider}, model {settings.model}, key {masked}")
        if settings.price_input_per_mtok is None or settings.price_output_per_mtok is None:
            print("NOTE  prices: PRICE_INPUT_PER_MTOK and PRICE_OUTPUT_PER_MTOK are not set yet; set them before Part 6")
        else:
            print(f"NOTE  prices: ${settings.price_input_per_mtok} in and ${settings.price_output_per_mtok} out per million tokens")
    except SetupError as exc:
        report(False, ".env", str(exc))

    if not args.skip_ai and settings is not None and settings.api_key:
        try:
            provider = make_provider(settings)
            ping = ToolSpec("ping", "Call this tool once to show that tool calling works. Takes no inputs.",
                            {"type": "object", "properties": {}})
            turn = provider.next_turn("Call the ping tool once, and nothing else.",
                                      [{"role": "user", "text": "Please call ping."}], [ping])
            called = [c.name for c in turn.tool_calls]
            if called:
                report(called == ["ping"], "tool calling works with your key and model",
                       f"the model asked for {called}; {turn.input_tokens} tokens in, {turn.output_tokens} out")
            else:
                print("NOTE  tool calling: the request worked, but the model answered in text instead of calling "
                      "ping. That happens now and then; a practice run will show whether tools work.")
        except (AIError, SetupError) as exc:
            report(False, "tool calling works with your key and model", str(exc))
    print()
    print("All checks passed." if failures == 0 else f"{failures} check(s) failed. See README.md, Troubleshooting.")
    return 0 if failures == 0 else 1


FIXTURE_DIGEST = "8aaab9373de615a5"


# --------------------------------------------------------------------------- fresh


def cmd_fresh(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.name)
    target = run_dir / "workspace"
    if target.exists() and not args.overwrite:
        print(f"runs/{args.name}/workspace already exists. Add --overwrite to replace it.")
        return 1
    run_dir.mkdir(parents=True, exist_ok=True)
    _fresh_workspace(target)
    print(f"Made runs/{args.name}/workspace, a clean copy of the project.")
    return 0


# --------------------------------------------------------------------------- judge


def _report_text(report: Any) -> str:
    """A TestReport as short text, in the same format as format_report in Part 1."""
    if report.timed_out:
        return "FAILED: the tests did not finish within 20 seconds."
    if not report.problems:
        return f"PASSED: {report.total} of {report.total} tests passed."
    lines = [f"FAILED: {len(report.problems)} of {report.total} tests did not pass."]
    lines += [f"{p.kind} {p.name}: {p.message}" for p in report.problems[:10]]
    if len(report.problems) > 10:
        lines.append(f"({len(report.problems) - 10} more not shown)")
    return "\n".join(lines)


def _changes(workspace: Path) -> tuple[list[str], str]:
    """Files that differ from fixture/, and a unified diff of them."""
    import difflib

    def files(root: Path) -> dict[str, Path]:
        return {p.relative_to(root).as_posix(): p for p in root.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}

    before, after = files(FIXTURE_DIR), files(workspace)
    changed, diff = [], []
    for rel in sorted(set(before) | set(after)):
        a = before[rel].read_text(encoding="utf-8", errors="replace") if rel in before else ""
        b = after[rel].read_text(encoding="utf-8", errors="replace") if rel in after else ""
        if a.replace("\r\n", "\n") == b.replace("\r\n", "\n"):
            continue
        state = "added" if rel not in before else "deleted" if rel not in after else "changed"
        changed.append(f"{rel} ({state})")
        diff += difflib.unified_diff(a.splitlines(keepends=True), b.splitlines(keepends=True), f"fixture/{rel}", f"workspace/{rel}", n=1)
    return changed, "".join(diff).rstrip("\n")


def judge_text(name: str) -> str | None:
    """The judge command's report for runs/NAME/workspace, or None if it does not exist."""
    from agent.testrunner import run_unittests

    workspace = _run_dir(name) / "workspace"
    if not workspace.is_dir():
        return None
    visible = run_unittests(workspace, timeout=20)
    judged = run_unittests(workspace, tests_dir=JUDGE_DIR, timeout=20, pattern="*_test.py")
    changed, diff = _changes(workspace)
    lines = [
        f"Results for runs/{name}/workspace",
        "",
        "Visible tests (the workspace's tests/ folder):",
        _report_text(visible),
        "",
        "Judge (judge/acceptance_test.py):",
        _report_text(judged),
        "",
        "Files that differ from fixture/: " + (", ".join(changed) if changed else "none"),
    ]
    if diff:
        diff_lines = diff.splitlines()
        lines += ["", *diff_lines[:80]]
        if len(diff_lines) > 80:
            lines.append(f"({len(diff_lines) - 80} more diff lines not shown)")
    return "\n".join(lines)


def cmd_judge(args: argparse.Namespace) -> int:
    text = judge_text(args.name)
    if text is None:
        print(f"runs/{args.name}/workspace does not exist. Make it with: python -m agent fresh {args.name}")
        return 1
    print(text)
    (_run_dir(args.name) / "judge.txt").write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved in runs/{args.name}/judge.txt.")
    return 0


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check-setup", help="check Python, packages, .env and one tiny tool call")
    p.add_argument("--skip-ai", action="store_true", help="do not call the model")
    p.set_defaults(fn=cmd_check_setup)

    p = sub.add_parser("run", help="record one run in runs/NAME/")
    p.add_argument("name")
    p.add_argument("--tools", choices=("local", "mcp"), default="local")
    p.add_argument("--judge", action="store_true", help="Reflexion: retry with a lesson when the judge fails")
    p.add_argument("--task", default=DEFAULT_TASK)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(fn=cmd_run)

    for cmd, fn, text in (("check-trace", cmd_check_trace, "check a recorded run"),
                          ("replay", cmd_replay, "re-run a recorded run from its saved replies")):
        p = sub.add_parser(cmd, help=text)
        p.add_argument("name")
        p.set_defaults(fn=fn)

    p = sub.add_parser("check-mcp", help="start server.py over MCP and test it")
    p.set_defaults(fn=cmd_check_mcp)
    p = sub.add_parser("summary", help="print the run table for REPORT.md")
    p.set_defaults(fn=cmd_summary)
    p = sub.add_parser("fresh", help="make runs/NAME/workspace, a clean copy of the project")
    p.add_argument("name")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(fn=cmd_fresh)
    p = sub.add_parser("judge", help="run the visible tests and the judge on runs/NAME/workspace")
    p.add_argument("name")
    p.set_defaults(fn=cmd_judge)

    args = parser.parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except NotImplementedError as exc:
        print(f"Not written yet: {exc}")
        return 1
