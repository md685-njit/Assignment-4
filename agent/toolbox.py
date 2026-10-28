"""Where the agent's tools come from: inside this program, or from an MCP server.

GIVEN CODE. Do not change it.

Both toolboxes have the same four methods, so your loop never knows which one it has:

    specs()            the tools to offer the model: name, description, input schema
    call(name, args)   run one tool; returns (ok, text)
    preview(name, args)  what a call would change, for the person approving it
    close()            stop the MCP server, if there is one

LocalToolbox calls the functions in agent/tools.py directly. MCPToolbox starts your
server.py as a separate program and talks to it over MCP (stdio), exactly as Claude Code
or agy would. To the model the two look the same: MCP changes where tools come from,
not how the loop works.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import difflib
import inspect
import json
import sys
import threading
import typing
from pathlib import Path
from typing import Any

from agent import ROOT, SERVER_FILE
from agent.core import ToolSpec

_JSON_TYPES = {str: "string", int: "integer", bool: "boolean", float: "number"}


# --------------------------------------------------------------------------- shared


def preview_call(workspace: Path, name: str, args: dict[str, Any]) -> str | None:
    """What a person sees before approving a call.

    For edit_file this is the diff the edit would make, or None when the edit cannot be
    applied (the tool will refuse it with an error, so there is nothing to approve).
    """
    if name != "edit_file":
        return f"{name} {json.dumps(args, sort_keys=True)}"
    path, old, new = args.get("path"), args.get("old_text"), args.get("new_text")
    if not isinstance(path, str) or not isinstance(old, str) or not isinstance(new, str) or old == "":
        return None
    root = Path(workspace).resolve()
    full = (root / path).resolve()
    if root not in full.parents or not full.is_file():
        return None
    try:
        text = full.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if text.count(old) != 1:
        return None
    after = text.replace(old, new, 1)
    diff = difflib.unified_diff(
        text.splitlines(keepends=True), after.splitlines(keepends=True), f"a/{path}", f"b/{path}", n=2
    )
    return "".join(diff).rstrip("\n") or f"(edit_file would not change {path})"


# --------------------------------------------------------------------------- local


def schema_for(fn: Any) -> dict[str, Any]:
    """A JSON schema for a function's inputs, built from its parameters and type hints."""
    hints = typing.get_type_hints(fn)
    props: dict[str, Any] = {}
    required: list[str] = []
    for pname, param in inspect.signature(fn).parameters.items():
        prop: dict[str, Any] = {"type": _JSON_TYPES.get(hints.get(pname, str), "string")}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["default"] = param.default
        props[pname] = prop
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _check_args(fn: Any, args: dict[str, Any]) -> str | None:
    hints = typing.get_type_hints(fn)
    params = inspect.signature(fn).parameters
    for key in args:
        if key not in params:
            return f"unexpected input {key!r}"
    for pname, param in params.items():
        if pname not in args:
            if param.default is inspect.Parameter.empty:
                return f"missing input {pname!r}"
            continue
        want = hints.get(pname, str)
        value = args[pname]
        good = isinstance(value, want) and not (want is int and isinstance(value, bool))
        if not good:
            return f"input {pname!r} must be {_JSON_TYPES.get(want, 'string')}"
    return None


class LocalToolbox:
    """The tools as plain Python functions inside the agent's own program."""

    def __init__(self, workspace: Path, functions: list[Any] | None = None) -> None:
        from agent import tools

        self.workspace = tools.use_workspace(workspace)
        self._tools = tools
        self.functions = {fn.__name__: fn for fn in (functions if functions is not None else tools.TOOLS)}

    def specs(self) -> list[ToolSpec]:
        return [ToolSpec(n, inspect.getdoc(fn) or "", schema_for(fn)) for n, fn in self.functions.items()]

    def call(self, name: str, args: dict[str, Any]) -> tuple[bool, str]:
        self._tools.use_workspace(self.workspace)
        fn = self.functions.get(name)
        if fn is None:
            return False, f"Unknown tool: {name}"
        problem = _check_args(fn, args)
        if problem:
            return False, f"Error executing tool {name}: {problem}"
        try:
            return True, str(fn(**args))
        except self._tools.ToolFailure as exc:
            return False, f"Error executing tool {name}: {exc}"
        except Exception as exc:  # a crash in your tool: the model sees only that it failed
            print(f"[toolbox] {name} crashed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return False, f"Error executing tool {name}"

    def preview(self, name: str, args: dict[str, Any]) -> str | None:
        return preview_call(self.workspace, name, args)

    def close(self) -> None:
        pass


# --------------------------------------------------------------------------- MCP


class MCPToolbox:
    """The tools from your MCP server, started as a separate program and reached over stdio.

    This object is the MCP host side: it starts the server, asks tools/list, and sends
    tools/call for every call the model makes. The server's own log goes to `log_file`.
    """

    def __init__(self, workspace: Path, server_file: Path = SERVER_FILE, log_file: Path | None = None,
                 timeout: float = 60.0) -> None:
        from mcp import Client, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self.workspace = Path(workspace).resolve()
        self.timeout = timeout
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(server_file).resolve()), "--workspace", str(self.workspace)],
            cwd=str(ROOT),
        )
        self._log = open(log_file, "a", encoding="utf-8") if log_file else open(_devnull(), "w")
        self._loop = asyncio.new_event_loop()
        self._queue: asyncio.Queue | None = None
        self._ready = concurrent.futures.Future()
        self._done = concurrent.futures.Future()

        async def main() -> None:
            self._queue = asyncio.Queue()
            try:
                async with Client(stdio_client(params, errlog=self._log)) as client:
                    self._ready.set_result(True)
                    while True:
                        job = await self._queue.get()
                        if job is None:
                            break
                        future, fn = job
                        try:
                            future.set_result(await fn(client))
                        except BaseException as exc:  # handed back to the caller's thread
                            future.set_exception(exc)
            except BaseException as exc:
                if not self._ready.done():
                    self._ready.set_exception(exc)
            finally:
                if not self._done.done():
                    self._done.set_result(True)

        self._thread = threading.Thread(target=self._run_loop, args=(main(),), daemon=True)
        self._thread.start()
        try:
            self._ready.result(timeout)
        except Exception as exc:
            self.close()
            raise RuntimeError(
                f"Could not start the MCP server {server_file}: {exc}. "
                "Run python -m agent check-mcp to see why."
            ) from exc

    def _run_loop(self, coro: Any) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(coro)

    def _submit(self, fn: Any) -> Any:
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (future, fn))
        return future.result(self.timeout)

    def specs(self) -> list[ToolSpec]:
        result = self._submit(lambda c: c.list_tools())
        return [ToolSpec(t.name, t.description or "", dict(t.input_schema)) for t in result.tools]

    def call(self, name: str, args: dict[str, Any]) -> tuple[bool, str]:
        result = self._submit(lambda c: c.call_tool(name, args))
        text = "\n".join(getattr(part, "text", "") for part in result.content if getattr(part, "type", "") == "text")
        return (not result.is_error), text

    def preview(self, name: str, args: dict[str, Any]) -> str | None:
        return preview_call(self.workspace, name, args)

    def close(self) -> None:
        if self._queue is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
            try:
                self._done.result(10)
            except Exception:
                pass
        self._thread.join(10)
        try:
            self._log.close()
        except Exception:
            pass

    def __enter__(self) -> "MCPToolbox":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _devnull() -> str:
    import os

    return os.devnull
