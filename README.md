# CS 690 Assignment 4: Build Your Own Coding Agent

This repository is the starter code for Assignment 4. The assignment itself, what to do
and why, is in **HANDOUT.md**. This file covers setup and the commands you will run.

## What you need

- Python 3.11, 3.12 or 3.13 (3.12 recommended). Check with `python --version`
  (on macOS and Linux it may be `python3 --version`).
- git
- An API key from Anthropic (platform.claude.com) or OpenAI (platform.openai.com), with a
  little credit. A chat subscription is not an API key. Your Assignment 2 key works.
- For Part 7 only: Claude Code or Antigravity CLI (`agy`).

## Setup

**1. Get the code.** Clone the repository and go into it:

    git clone <the repository URL from Canvas>
    cd Assignment-4

**2. Make a virtual environment and turn it on.**

macOS and Linux:

    python3 -m venv .venv
    source .venv/bin/activate

Windows (PowerShell):

    py -m venv .venv
    .venv\Scripts\Activate.ps1

Your prompt now starts with `(.venv)`. Turn it on again in every new terminal.

**3. Install the packages.**

    pip install -r requirements.txt

**4. Add your key.** Copy the settings file:

    cp .env.example .env          (macOS and Linux)
    copy .env.example .env        (Windows)

Open `.env` and paste your key after `ANTHROPIC_API_KEY=` or after `OPENAI_API_KEY=`.
Paste only one; the code uses whichever you paste. Leave `AI_MODEL` blank to use the
default model. You may copy your `.env` from Assignment 2 instead, but update the two
prices in Part 0: the default model has changed.

**5. Check everything.**

    python -m agent check-setup

This checks your Python, the packages, that `fixture/` and `judge/` are unchanged, your
`.env`, and one tiny tool-calling request to your model (a fraction of a cent). You are
ready when it prints "All checks passed." Add `--skip-ai` to skip the request.

## Commands

All commands run from the top folder of the repository, with the virtual environment on.

Check your code, one part at a time. These use a scripted model: no key, no cost.

    pytest tests/test_tools.py         Part 1
    pytest tests/test_policy.py        Part 2
    pytest tests/test_loop.py          Part 3
    pytest tests/test_reflexion.py     Part 4
    pytest tests/test_server.py        Part 5
    pytest                             everything

Check your MCP server the way a host would see it (Part 5):

    python -m agent check-mcp

Record and check runs (Part 6). Each run is saved in `runs/NAME/`:

| Command | What it does | Cost |
| --- | --- | --- |
| `python -m agent run try1` | A practice run, with any name you like | about a cent or less |
| `python -m agent run runA` | Recorded Run A: tools inside your agent, judge after the run | about a cent or less |
| `python -m agent run runB --tools mcp --judge` | Recorded Run B: tools from your MCP server, Reflexion | about two cents or less |
| `python -m agent check-trace runA` | Checks that a run's files are complete | free |
| `python -m agent replay runA` | Re-runs your committed code on the saved replies and compares | free |
| `python -m agent summary` | Prints the table for REPORT.md Section 1 | free |

The costs are estimates for the default models. `summary` prints your real cost from the
prices in `.env`. Add `--task "Add a docstring to apply_discount."` (or any task) to a practice run to try
another task; recorded runs use the default task, "Make the tests pass." A name that is already used is refused;
add `--overwrite` to replace a practice run.

During a run, every step is printed as it happens. Before each edit you see its diff and
answer `y` or `n`; after `n` you type a reason, which is sent to the agent.

Part 7 uses two clean copies of the project, and checks the fixer's work:

    python -m agent fresh terminal     the copy your MCP server works on in the vendor's agent
    python -m agent fresh vendor       the copy the fixer agent works on
    python -m agent judge vendor       runs the visible tests and the judge on runs/vendor/workspace,
                                       lists the changed files, and saves runs/vendor/judge.txt

## What is in this repository

| Path | What it is |
| --- | --- |
| HANDOUT.md | The assignment: what, why, every part, how it is graded |
| RUBRIC.md | The grading checklist |
| REPORT.md | Your report; fill it in during Part 8 |
| LEDGER.md | Your provenance ledger |
| NOTES.md | The agent's long-term memory; Reflexion adds lessons here |
| prompts/ | The prompts you gave AI tools, one file per ledger entry |
| evidence/ | Your Part 7 transcripts: MCP calls, the review, the fixer session |
| agent/core.py | Given: the types and helpers everything uses. Read it first |
| agent/tools.py, policy.py, loop.py, reflexion.py | Yours to write (Parts 1 to 4) |
| server.py | Yours to write (Part 5) |
| agent/provider.py, toolbox.py, trace.py, testrunner.py, cli.py | Given; do not change |
| fixture/ | The project the agent works on; given, do not change |
| judge/ | The acceptance tests, outside every workspace; given, do not change |
| tests/ | Public tests; do not change |
| runs/ | Your recorded runs (commit runA and runB) and the Part 7 copies (commit vendor) |
| .env | Your key and settings; never commit it |

## Troubleshooting

**`NotImplementedError: Part 3: write run_agent in agent/loop.py`**
That part is not written yet. The message names the function and the file.

**`No API key found`**
You have not created `.env`, or the key line is empty. See Setup step 4.

**`Both ANTHROPIC_API_KEY and OPENAI_API_KEY are set`**
Set `AI_PROVIDER=anthropic` or `AI_PROVIDER=openai` in `.env`. A key exported in your
terminal counts too.

**`rejected your API key`**
The key was mistyped or revoked. Paste it again, with no quotes and no spaces.

**`rate limit or spend limit reached`**, or a quota message
Wait a minute and try again. New API accounts start with low limits. If it keeps
failing, check that your account has credit.

**`does not know the model`**
Leave `AI_MODEL` blank to use the default, or check the name on your provider's models
page. If you choose another model, check that it supports tool calling.

**OpenAI says function tools are not supported with reasoning_effort**
Use the default model, `gpt-5.6-luna`, which the code already sends with reasoning off.

**`Could not start the MCP server`**
Run `python -m agent check-mcp`; it prints the server's own error. The usual causes are
a mistake in `server.py`, or importing it starting the server (keep `mcp.run` inside
`if __name__ == "__main__":`).

**Claude Code shows a4-tools as failed, or agy cannot connect**
The command must be the full path to `.venv`'s Python, which has the `mcp` package. Run
the same command yourself, for example
`.venv/bin/python server.py --workspace runs/terminal/workspace`: it should wait
silently for input (press Ctrl+C to stop it). An error there is the problem.

**`Replay of runs/runA does NOT match its trace`**
Your code changed after the run, or a run file was edited. Record the run again with
your final code.

**Claude Code does not run the fixer agent**
Check that the file is `.claude/agents/fixer.md`, that its header starts and ends with a
`---` line, and that it says `name: fixer`. Start `claude` from the top folder of the
repository. If this was the first file in `.claude/agents/`, start a new session.

**PowerShell says running scripts is disabled** when you activate the environment
Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again.
