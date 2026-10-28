"""The trace: one JSON line per event, written as the run happens.

GIVEN CODE. Do not change it.

Your loop calls trace.tool(...) after every tool call and trace.stop(...) once when it
stops. Your reflexion calls trace.judge(...) and trace.lesson(...). Each method writes one
line to trace.jsonl and, with echo on, prints it so you can watch the run.

Event kinds and their fields (every event also has run, kind, time):

    tool    attempt, step, thought, tool, input, gate, approved, reason, ok, output,
            input_tokens, output_tokens
    stop    attempt, step, status, reason, final_text, input_tokens, output_tokens
    judge   attempt, passed, report
    lesson  attempt, text, input_tokens, output_tokens

The trace is the raw material for your provenance ledger (Part 8).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_TEXT = 2000


def _clip(text: str) -> str:
    text = text or ""
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 20] + "\n(clipped in trace)"


class TraceWriter:
    def __init__(self, path: Path | None, run: str = "test", echo: bool = False) -> None:
        self.path = Path(path) if path is not None else None
        self.run = run
        self.echo = echo
        self.events: list[dict[str, Any]] = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def _write(self, kind: str, fields: dict[str, Any]) -> None:
        event = {"run": self.run, "kind": kind, "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        event.update(fields)
        self.events.append(event)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
        if self.echo:
            print(render(event), flush=True)

    def tool(self, *, attempt: int, step: int, thought: str, tool: str, input: dict[str, Any], gate: str,
             approved: bool | None, reason: str, ok: bool, output: str, input_tokens: int,
             output_tokens: int) -> None:
        self._write("tool", {
            "attempt": int(attempt), "step": int(step), "thought": _clip(thought), "tool": tool,
            "input": input, "gate": gate, "approved": approved, "reason": reason, "ok": bool(ok),
            "output": _clip(output), "input_tokens": int(input_tokens), "output_tokens": int(output_tokens),
        })

    def stop(self, *, attempt: int, step: int, status: str, reason: str, final_text: str, input_tokens: int,
             output_tokens: int) -> None:
        self._write("stop", {
            "attempt": int(attempt), "step": int(step), "status": status, "reason": reason,
            "final_text": _clip(final_text), "input_tokens": int(input_tokens), "output_tokens": int(output_tokens),
        })

    def judge(self, *, attempt: int, passed: bool, report: str) -> None:
        self._write("judge", {"attempt": int(attempt), "passed": bool(passed), "report": _clip(report)})

    def lesson(self, *, attempt: int, text: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self._write("lesson", {
            "attempt": int(attempt), "text": _clip(text),
            "input_tokens": int(input_tokens), "output_tokens": int(output_tokens),
        })


def read_trace(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def render(event: dict[str, Any]) -> str:
    """One event as a few readable lines, for the console."""
    kind = event.get("kind")
    if kind == "tool":
        head = f"[attempt {event['attempt']}, step {event['step']}]"
        lines = []
        if event.get("thought"):
            lines.append(f"{head} Thought: {event['thought']}")
            head = " " * len(head)
        gate = event["gate"]
        note = ""
        if gate == "deny":
            note = "  (refused by policy)"
        elif event.get("approved") is False:
            note = f"  (rejected: {event.get('reason', '')})"
        elif event.get("approved") is True:
            note = "  (approved)"
        lines.append(f"{head} Action: {event['tool']} {json.dumps(event['input'], sort_keys=True)[:200]}{note}")
        out = (event.get("output") or "").strip().splitlines()
        shown = out[:6]
        lines.append(f"{' ' * len(head)} Observation{'' if event['ok'] else ' (error)'}: " + (shown[0] if shown else ""))
        for extra in shown[1:]:
            lines.append(f"{' ' * len(head)}   {extra}")
        if len(out) > 6:
            lines.append(f"{' ' * len(head)}   ({len(out) - 6} more lines in the trace)")
        return "\n".join(lines)
    if kind == "stop":
        text = f"[attempt {event['attempt']}] Stopped: {event['status']} ({event['reason']}) after {event['step']} model calls"
        if event.get("final_text"):
            text += f"\n  Final answer: {event['final_text']}"
        return text
    if kind == "judge":
        return f"[attempt {event['attempt']}] Judge: {'PASS' if event['passed'] else 'FAIL'}\n  " + event["report"].replace("\n", "\n  ")
    if kind == "lesson":
        return f"[attempt {event['attempt']}] Lesson saved to NOTES.md: {event['text']}"
    return json.dumps(event)
