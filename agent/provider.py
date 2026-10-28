"""Talk to the model: Anthropic or OpenAI, plus a scripted model for tests.

GIVEN CODE. Do not change it (the grader restores it before grading).

Which provider is used works exactly as in Assignment 2: paste one key into .env and that
provider is used. If you paste both keys, set AI_PROVIDER to anthropic or openai.

Every provider has the same two methods:

    next_turn(system, history, tools) -> ModelTurn    one step of the agent, tools offered
    complete(system, prompt) -> ModelTurn             a plain question, no tools

next_turn is tool calling with the real API. You send the task and the tool list (move 1);
the model replies with a structured tool request instead of prose (move 2); your loop runs
the tool (move 3) and appends the result to the history for the next call (move 4).
Read AnthropicProvider (or OpenAIProvider) below: comments mark moves 1 and 2 in the
real API.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agent import ENV_FILE
from agent.core import AIError, ModelTurn, SetupError, ToolCall, ToolSpec

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-5.6-luna",
}

MAX_OUTPUT_TOKENS = 4096


class Provider(Protocol):
    name: str
    model: str

    def next_turn(self, system: str, history: list[dict[str, Any]], tools: list[ToolSpec]) -> ModelTurn: ...

    def complete(self, system: str, prompt: str) -> ModelTurn: ...


# --------------------------------------------------------------------------- settings


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    api_key: str | None
    price_input_per_mtok: float | None
    price_output_per_mtok: float | None


def _price(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise SetupError(f"{name} in .env must be a number such as 0.10, not {raw!r}.") from exc
    if value < 0:
        raise SetupError(f"{name} in .env cannot be negative.")
    return value


def load_settings(env_file: Path = ENV_FILE) -> Settings:
    """Read .env and work out the provider, model, key and prices."""
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise SetupError("python-dotenv is not installed. Run: pip install -r requirements.txt") from exc
    load_dotenv(env_file, override=False)

    provider = os.getenv("AI_PROVIDER", "").strip().lower()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if provider == "":
        if anthropic_key and not openai_key:
            provider = "anthropic"
        elif openai_key and not anthropic_key:
            provider = "openai"
        elif anthropic_key and openai_key:
            raise SetupError(
                "Both ANTHROPIC_API_KEY and OPENAI_API_KEY are set. "
                "Set AI_PROVIDER in .env to anthropic or openai to choose one."
            )
        else:
            raise SetupError("No API key found. Copy .env.example to .env and paste your Anthropic or OpenAI key into it.")
    elif provider not in DEFAULT_MODELS:
        raise SetupError(f"AI_PROVIDER in .env must be anthropic or openai, not {provider!r}.")

    key = anthropic_key if provider == "anthropic" else openai_key
    model = os.getenv("AI_MODEL", "").strip() or DEFAULT_MODELS[provider]
    return Settings(
        provider=provider,
        model=model,
        api_key=key or None,
        price_input_per_mtok=_price("PRICE_INPUT_PER_MTOK"),
        price_output_per_mtok=_price("PRICE_OUTPUT_PER_MTOK"),
    )


def cost_usd(input_tokens: int, output_tokens: int, settings_or_prices: Any) -> float | None:
    """Dollars for a number of tokens at per-million prices, or None if a price is missing."""
    p_in = getattr(settings_or_prices, "price_input_per_mtok", None)
    p_out = getattr(settings_or_prices, "price_output_per_mtok", None)
    if isinstance(settings_or_prices, dict):
        p_in = settings_or_prices.get("price_input_per_mtok")
        p_out = settings_or_prices.get("price_output_per_mtok")
    if p_in is None or p_out is None:
        return None
    return input_tokens / 1_000_000 * p_in + output_tokens / 1_000_000 * p_out


def make_provider(settings: Settings) -> Provider:
    if not settings.api_key:
        raise SetupError(f"No API key is set in .env for {settings.provider}.")
    if settings.provider == "anthropic":
        return AnthropicProvider(settings.model, settings.api_key)
    return OpenAIProvider(settings.model, settings.api_key)


# --------------------------------------------------------------------------- Anthropic


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str) -> None:
        import anthropic

        self.model = model
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=4)

    def _extra(self) -> dict[str, Any]:
        # Claude Haiku 5.5 thinks before it answers unless told not to. Thinking costs output
        # tokens and adds blocks we would have to send back on every call, so the default
        # model runs with it off. Other models keep their default; their thinking blocks are
        # kept in `raw` and sent back unchanged, as the API requires.
        if self.model.startswith("claude-haiku-5"):
            return {"thinking": {"type": "disabled"}}
        return {}

    def next_turn(self, system: str, history: list[dict[str, Any]], tools: list[ToolSpec]) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": system,
            "messages": to_anthropic_messages(history),
            **self._extra(),
        }
        if tools:
            # Move 1: the tool list goes with every request.
            kwargs["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]
            kwargs["tool_choice"] = {"type": "auto", "disable_parallel_tool_use": True}
        return self._send(kwargs)

    def complete(self, system: str, prompt: str) -> ModelTurn:
        kwargs = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            **self._extra(),
        }
        return self._send(kwargs)

    def _send(self, kwargs: dict[str, Any]) -> ModelTurn:
        a = self._anthropic
        try:
            response = self._client.messages.create(**kwargs)
        except a.AuthenticationError as exc:
            raise AIError("Anthropic rejected your API key. Check ANTHROPIC_API_KEY in .env.") from exc
        except a.PermissionDeniedError as exc:
            raise AIError(f"Anthropic refused the request (permission): {exc}") from exc
        except a.NotFoundError as exc:
            raise AIError(f"Anthropic does not know the model {self.model!r}. Check AI_MODEL in .env.") from exc
        except a.RateLimitError as exc:
            raise AIError("Anthropic rate limit or spend limit reached. Wait a minute and try again.") from exc
        except a.APIConnectionError as exc:
            raise AIError("Could not reach Anthropic. Check your internet connection.") from exc
        except a.APIStatusError as exc:
            raise AIError(f"Anthropic returned an error ({exc.status_code}): {exc}") from exc

        # Move 2: the reply holds text blocks and, when the model wants to act, a tool_use block.
        texts: list[str] = []
        calls: list[ToolCall] = []
        raw: list[dict[str, Any]] = []
        for block in response.content:
            kind = getattr(block, "type", "")
            if kind == "text":
                texts.append(block.text)
                raw.append({"type": "text", "text": block.text})
            elif kind == "tool_use":
                args = dict(block.input) if isinstance(block.input, dict) else {}
                calls.append(ToolCall(id=block.id, name=block.name, args=args))
                raw.append({"type": "tool_use", "id": block.id, "name": block.name, "input": args})
            elif kind in ("thinking", "redacted_thinking"):
                raw.append(block.model_dump(mode="json", exclude_none=True))
        return ModelTurn(
            text="\n".join(t.strip() for t in texts if t.strip()),
            tool_calls=tuple(calls),
            input_tokens=int(response.usage.input_tokens),
            output_tokens=int(response.usage.output_tokens),
            stop_reason=str(response.stop_reason or ""),
            raw=raw,
            provider=self.name,
        )


def to_anthropic_messages(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The history in the Messages API format. Tool results go back as tool_result blocks
    inside a user message, right after the assistant message that asked for them."""
    out: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    def flush() -> None:
        if pending:
            out.append({"role": "user", "content": list(pending)})
            pending.clear()

    for m in history:
        role = m["role"]
        if role == "user":
            pending.append({"type": "text", "text": m["text"]})
        elif role == "tool":
            pending.append(
                {
                    "type": "tool_result",
                    "tool_use_id": m["id"],
                    "content": m["text"] or "(no output)",
                    "is_error": bool(m["is_error"]),
                }
            )
        elif role == "assistant":
            flush()
            if m.get("provider") == "anthropic" and m.get("raw"):
                content = copy.deepcopy(m["raw"])
            else:
                content = []
                if m.get("text"):
                    content.append({"type": "text", "text": m["text"]})
                for c in m.get("tool_calls", []):
                    content.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]})
                if not content:
                    content = [{"type": "text", "text": "(no reply)"}]
            out.append({"role": "assistant", "content": content})
        else:
            raise ValueError(f"unknown history role: {role!r}")
    flush()
    return out


# --------------------------------------------------------------------------- OpenAI


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, api_key: str) -> None:
        import openai

        self.model = model
        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, max_retries=4)

    def _extra(self) -> dict[str, Any]:
        # GPT-5.6 models reject function tools in Chat Completions unless reasoning is off.
        if self.model.startswith("gpt-5.6"):
            return {"reasoning_effort": "none"}
        return {}

    def next_turn(self, system: str, history: list[dict[str, Any]], tools: list[ToolSpec]) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(system, history),
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
            **self._extra(),
        }
        if tools:
            # Move 1: the tool list goes with every request.
            kwargs["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
                for t in tools
            ]
        return self._send(kwargs)

    def complete(self, system: str, prompt: str) -> ModelTurn:
        kwargs = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
            **self._extra(),
        }
        return self._send(kwargs)

    def _send(self, kwargs: dict[str, Any]) -> ModelTurn:
        o = self._openai
        try:
            response = self._client.chat.completions.create(**kwargs)
        except o.AuthenticationError as exc:
            raise AIError("OpenAI rejected your API key. Check OPENAI_API_KEY in .env.") from exc
        except o.PermissionDeniedError as exc:
            raise AIError(f"OpenAI refused the request (permission): {exc}") from exc
        except o.NotFoundError as exc:
            raise AIError(f"OpenAI does not know the model {self.model!r}. Check AI_MODEL in .env.") from exc
        except o.RateLimitError as exc:
            raise AIError("OpenAI rate limit or quota reached. Wait a minute; check that your account has credit.") from exc
        except o.APIConnectionError as exc:
            raise AIError("Could not reach OpenAI. Check your internet connection.") from exc
        except o.APIStatusError as exc:
            raise AIError(f"OpenAI returned an error ({exc.status_code}): {exc}") from exc

        # Move 2: the reply holds text and, when the model wants to act, tool_calls.
        choice = response.choices[0]
        msg = choice.message
        calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            try:
                args = json.loads(fn.arguments or "{}")
                if not isinstance(args, dict):
                    args = {"_not_an_object": args}
            except json.JSONDecodeError:
                args = {"_invalid_json": fn.arguments}
            calls.append(ToolCall(id=tc.id, name=fn.name, args=args))
        usage = response.usage
        return ModelTurn(
            text=(msg.content or "").strip(),
            tool_calls=tuple(calls),
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            stop_reason=str(choice.finish_reason or ""),
            raw=None,
            provider=self.name,
        )


def to_openai_messages(system: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The history in the Chat Completions format: tool results are role "tool" messages."""
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in history:
        role = m["role"]
        if role == "user":
            out.append({"role": "user", "content": m["text"]})
        elif role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": m.get("text") or None}
            if m.get("tool_calls"):
                entry["tool_calls"] = [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
                    for c in m["tool_calls"]
                ]
            elif not entry["content"]:
                entry["content"] = "(no reply)"
            out.append(entry)
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": m["id"], "content": m["text"] or "(no output)"})
        else:
            raise ValueError(f"unknown history role: {role!r}")
    return out


# --------------------------------------------------------------------------- scripted, recorded, replayed


def turn_to_json(turn: ModelTurn) -> dict[str, Any]:
    return {
        "text": turn.text,
        "tool_calls": [{"id": c.id, "name": c.name, "args": c.args} for c in turn.tool_calls],
        "input_tokens": turn.input_tokens,
        "output_tokens": turn.output_tokens,
        "stop_reason": turn.stop_reason,
        "raw": turn.raw,
        "provider": turn.provider,
    }


def turn_from_json(data: dict[str, Any]) -> ModelTurn:
    return ModelTurn(
        text=data.get("text", ""),
        tool_calls=tuple(ToolCall(c["id"], c["name"], dict(c["args"])) for c in data.get("tool_calls", [])),
        input_tokens=int(data.get("input_tokens", 0)),
        output_tokens=int(data.get("output_tokens", 0)),
        stop_reason=data.get("stop_reason", ""),
        raw=data.get("raw"),
        provider=data.get("provider", ""),
    )


def say(text: str, input_tokens: int = 100, output_tokens: int = 20) -> ModelTurn:
    """A scripted reply with no tool call: the model is finished."""
    return ModelTurn(text=text, tool_calls=(), input_tokens=input_tokens, output_tokens=output_tokens, stop_reason="end_turn")


_scripted_ids = iter(range(1, 10**9))


def ask_tool(name: str, args: dict[str, Any] | None = None, text: str = "", *, call_id: str | None = None,
             input_tokens: int = 100, output_tokens: int = 20) -> ModelTurn:
    """A scripted reply that asks for one tool."""
    call = ToolCall(id=call_id or f"call_{next(_scripted_ids)}", name=name, args=dict(args or {}))
    return ModelTurn(text=text, tool_calls=(call,), input_tokens=input_tokens, output_tokens=output_tokens, stop_reason="tool_use")


class ScriptedProvider:
    """Plays back a fixed list of replies, for tests and offline practice. Costs nothing.

    Each item is a ModelTurn (see say and ask_tool) or an exception to raise. Every request
    is kept in .requests so a test can check what the loop sent.
    """

    name = "scripted"
    model = "scripted"

    def __init__(self, replies: list[ModelTurn | Exception]) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    def next_turn(self, system: str, history: list[dict[str, Any]], tools: list[ToolSpec]) -> ModelTurn:
        self.requests.append({"kind": "turn", "system": system, "history": copy.deepcopy(history), "tools": list(tools)})
        return self._next()

    def complete(self, system: str, prompt: str) -> ModelTurn:
        self.requests.append({"kind": "complete", "system": system, "prompt": prompt})
        return self._next()

    def _next(self) -> ModelTurn:
        if not self.replies:
            raise AIError("the scripted provider has no more replies")
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class RecordingProvider:
    """Wraps a real provider and saves every reply, in order, to replies.jsonl."""

    def __init__(self, inner: Provider, path: Path) -> None:
        self.inner = inner
        self.name = inner.name
        self.model = inner.model
        self.path = Path(path)
        self.path.write_text("", encoding="utf-8")

    def _save(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def next_turn(self, system: str, history: list[dict[str, Any]], tools: list[ToolSpec]) -> ModelTurn:
        return self._call("turn", lambda: self.inner.next_turn(system, history, tools))

    def complete(self, system: str, prompt: str) -> ModelTurn:
        return self._call("complete", lambda: self.inner.complete(system, prompt))

    def _call(self, kind: str, fn: Any) -> ModelTurn:
        try:
            turn = fn()
        except AIError as exc:
            self._save({"kind": kind, "error": str(exc)})
            raise
        self._save({"kind": kind, "turn": turn_to_json(turn)})
        return turn


class ReplayProvider:
    """Plays back a replies.jsonl file, so a recorded run can be checked with no API key."""

    def __init__(self, path: Path, name: str = "replay", model: str = "replay") -> None:
        self.name = name
        self.model = model
        self.records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

    def next_turn(self, system: str, history: list[dict[str, Any]], tools: list[ToolSpec]) -> ModelTurn:
        return self._next("turn")

    def complete(self, system: str, prompt: str) -> ModelTurn:
        return self._next("complete")

    def _next(self, kind: str) -> ModelTurn:
        if not self.records:
            raise AIError("replay: the recorded run has no more replies here")
        record = self.records.pop(0)
        if record.get("kind") != kind:
            raise AIError(f"replay: the code asked for a {kind} call where the recorded run made a {record.get('kind')} call")
        if "error" in record:
            raise AIError(record["error"])
        return turn_from_json(record["turn"])
