"""The types and helpers everything in the agent uses.

GIVEN CODE. Read it first; do not change it.

The conversation ("history") is a list of plain dicts in one of three shapes. You never
build the assistant shape yourself: append `turn.message`. Use the two helpers below for
the other two.

    {"role": "user", "text": "Make the tests pass."}
    {"role": "assistant", "text": "...", "tool_calls": [{"id", "name", "args"}], ...}
    {"role": "tool", "id": "<call id>", "name": "run_tests", "text": "...", "is_error": False}

The provider (agent/provider.py) turns this list into whatever format the Anthropic or
OpenAI API expects, so the same loop works with either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class SetupError(RuntimeError):
    """Something in .env or the setup needs fixing."""


class AIError(RuntimeError):
    """The model provider refused or failed a request."""


@dataclass(frozen=True)
class ToolSpec:
    """What the model is told about one tool. These three fields are all it ever sees."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """One tool request from the model: a tool name and its inputs."""

    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    """One reply from the model.

    text        what the model wrote (its "thought" before a tool call, or its final answer)
    tool_calls  the tools it asked for, in order; empty means it is finished
    raw         the provider's own copy of the reply, sent back unchanged on the next call
    """

    text: str
    tool_calls: tuple[ToolCall, ...]
    input_tokens: int
    output_tokens: int
    stop_reason: str = ""
    raw: Any = None
    provider: str = ""

    @property
    def message(self) -> dict[str, Any]:
        """This reply as a history entry. Append it to the history before running any tool."""
        return {
            "role": "assistant",
            "text": self.text,
            "tool_calls": [{"id": c.id, "name": c.name, "args": dict(c.args)} for c in self.tool_calls],
            "raw": self.raw,
            "provider": self.provider,
        }


def user_message(text: str) -> dict[str, Any]:
    """A history entry for something a person says, such as the task."""
    return {"role": "user", "text": text}


def tool_result_message(call: ToolCall, text: str, ok: bool) -> dict[str, Any]:
    """A history entry that reports one tool call's result back to the model."""
    return {"role": "tool", "id": call.id, "name": call.name, "text": text, "is_error": not ok}


@dataclass(frozen=True)
class Limits:
    """The stop rules' numbers. A step is one model call."""

    max_steps: int = 15
    max_tokens: int = 150_000


@dataclass
class RunResult:
    """How one run of the loop ended.

    status is one of: "done" (the model replied without a tool call), "budget" (a limit
    was reached), "stuck" (the same failure after an edit), "error" (the provider failed).
    """

    status: str
    reason: str
    steps: int
    input_tokens: int
    output_tokens: int
    final_text: str
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReflexionResult:
    """How a Reflexion run ended: did the judge pass, after how many attempts."""

    passed: bool
    attempts: int
    runs: list[RunResult]
    lessons: list[str]
    report: str


# An approver is shown one tool call and a preview of what it would change, and answers
# (approved, reason). The reason is sent to the model when the call is rejected.
Approver = Callable[[ToolCall, str], "tuple[bool, str]"]


def summarize_actions(history: list[dict[str, Any]], limit: int = 40) -> str:
    """A short numbered list of the tool calls in a history, with the first line of each result.

    Used to tell a model what an earlier attempt did, without sending the whole history.
    """
    results = {m["id"]: m for m in history if m.get("role") == "tool"}
    lines: list[str] = []
    for m in history:
        if m.get("role") != "assistant":
            continue
        for c in m.get("tool_calls", []):
            res = results.get(c["id"])
            if res is None:
                outcome = "no result"
            else:
                first = (res["text"].strip().splitlines() or [""])[0][:160]
                outcome = ("error: " if res["is_error"] else "") + first
            args = ", ".join(f"{k}={_short(v)}" for k, v in c["args"].items())
            lines.append(f"{len(lines) + 1}. {c['name']}({args}) -> {outcome}")
    if not lines:
        return "(it called no tools)"
    if len(lines) > limit:
        lines = lines[:limit] + [f"({len(lines) - limit} more calls not shown)"]
    return "\n".join(lines)


def _short(value: Any, n: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= n else text[: n - 3] + "..."
