"""Part 5: the MCP server. GIVEN CODE. Do not change it.

These tests connect an MCP client to your server inside the same Python process. The
command `python -m agent check-mcp` starts it as a separate program instead, the way
Claude Code or agy would.
"""

import asyncio
import inspect

from mcp import Client

from agent import tools


def connect_and(fn):
    import server

    assert server.mcp is not None, "server.py must create an MCPServer named mcp (Part 5)"

    async def main():
        async with Client(server.mcp) as client:
            return await fn(client)

    return asyncio.run(main())


def same(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def test_server_offers_the_four_tools_with_their_docstrings(ws):
    result = connect_and(lambda c: c.list_tools())
    names = [t.name for t in result.tools]
    assert names == ["list_files", "read_file", "edit_file", "run_tests"]
    for t in result.tools:
        fn = next(f for f in tools.TOOLS if f.__name__ == t.name)
        assert same(t.description or "", inspect.getdoc(fn) or ""), f"{t.name}: description is not its docstring"
    read = next(t for t in result.tools if t.name == "read_file")
    assert read.input_schema["required"] == ["path"]


def test_server_runs_a_tool(ws):
    result = connect_and(lambda c: c.call_tool("list_files", {}))
    assert result.is_error is False
    assert "discounts.py" in result.content[0].text


def test_server_passes_on_a_teaching_error(ws):
    result = connect_and(lambda c: c.call_tool("read_file", {"path": "../judge/acceptance_test.py"}))
    assert result.is_error is True
    assert "../judge/acceptance_test.py is outside the project folder" in result.content[0].text
