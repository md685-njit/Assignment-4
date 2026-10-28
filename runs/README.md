# Recorded runs

`python -m agent run NAME` saves each run in its own folder here:

- `run.json`: the settings of the run and how it ended
- `trace.jsonl`: one line per event, written as the run happened
- `replies.jsonl`: every model reply, so the run can be replayed with no API key
- `workspace/`: the project as the agent left it
- `server.log`: your MCP server's own log, for runs with `--tools mcp`

`python -m agent fresh NAME` makes only `runs/NAME/workspace`, a clean copy of the
project, for Part 7: `terminal` for your MCP server and `vendor` for the fixer agent.
`python -m agent judge vendor` adds `runs/vendor/judge.txt`.

Commit `runA`, `runB` and `vendor`. Practice runs may stay or go; they are not graded.
