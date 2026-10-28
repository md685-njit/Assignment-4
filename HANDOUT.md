# Assignment 4: Build Your Own Coding Agent

CS 690, AI-Assisted Software Engineering, Fall 2026, Individual Assignment (100 points).
Setup and commands are in README.md. The grading checklist is in RUBRIC.md.

## What you will build

In this assignment you build a coding agent of your own, use it on a small project with
a bug, and then plug its tools into a real terminal agent. Along the way you make the
choices every agent designer makes: how it decides, which tools it gets, what it
remembers, where it must stop and ask a person, and when a second agent helps.

Everything you need is in this handout and the starter files. Each part opens with a
short background paragraph that explains the idea it uses. The agents lectures cover the
same ideas in more depth and are good background, but you do not need them to do the
work.

Your agent:

1. Talks to the model through the real tool-calling API (Anthropic or OpenAI), the way
   every agent product does.
2. Has four tools you design for the model: list the files, read part of a file, make
   one exact edit, and run the tests. When a tool fails, its error message says what to
   do next.
3. Runs the ReAct loop: think, act, observe, repeat.
4. Asks you before every edit, shows you the diff, and sends your reason back to the
   model when you say no. It refuses some actions outright, and it stops on a step
   budget, a token budget, or the same failure twice.
5. Writes a trace of every step.
6. Checks its work with a judge it cannot see or edit, and after a failure writes a
   lesson to NOTES.md that its next attempt reads first (Reflexion).
7. Gets its tools from inside its own program, or from an MCP server you write.

Then you record two runs on the project, and you move to a vendor's agent, Claude Code or
Antigravity CLI. You connect your MCP server to it, and you define two agents in it with
nothing but a file: a read-only reviewer, and a fixer that you run on the same bug your
own agent fixed, checked by the same judge.

## Why this matters at work

**Every part of this assignment is something teams build, configure, or debug when they
put agents to work.**

| What you build | Where it shows up at work |
| --- | --- |
| A loop on the real tool-calling API (Part 3) | The core of every agent product: Claude Code, Codex, Copilot's agent mode, and the agents teams build into their own apps |
| Tool descriptions and error messages written for the model (Part 1) | The first thing to fix when an agent calls the wrong tool; what every MCP server author writes |
| Approval gates set by how hard an action is to undo (Part 2) | The permission prompts in Claude Code and agy, and the approval step in any agent allowed near production |
| Step budgets, token budgets, and a stuck rule (Part 2) | How teams stop a confused agent from looping and spending money |
| A trace of every step (Parts 3 and 6) | Agent observability: the record you debug from, and the raw material for an audit trail |
| A judge the agent cannot edit, with Reflexion (Part 4) | Verifiers and evals: the check that decides an agent's work is done, kept out of the agent's reach |
| An MCP server (Part 5) | The standard way to give any agent, IDE or chat app access to a tool or service |
| A read-only reviewer helper (Part 7) | The writer and critic pattern, and least-privilege subagents |
| A fixer agent defined in a file, run in a vendor's agent (Part 7) | How most teams use agents day to day: a vendor's agent given a role, instructions and limited tools, with its work still checked by tests |

When you finish, you can say in an interview: "I built a coding agent on the tool-calling
API with approval gates, stop rules, traces and a verifier, exposed its tools as an MCP
server, and configured agents of my own in Claude Code."

## What you need

- Python 3.11 to 3.13, git, and a GitHub account.
- An API key from Anthropic or OpenAI, with a little credit. The key and `.env` from
  Assignment 2 work here. The default models are Claude Haiku 5.5 (`claude-haiku-5-5`)
  and GPT-5.6 Luna (`gpt-5.6-luna`). The two recorded runs should cost well under 10
  cents, and the whole assignment, practice runs included, well under $1. These are
  estimates; `python -m agent summary` prints your real cost from the prices you enter.
- For Part 7 only: Claude Code, or Antigravity CLI (`agy`), which has a free tier. If you
  run Claude Code on an API key instead of a subscription, its own model calls are billed
  to that key.

## What you write, and what is given

You write five code files and two agent files, and you make two recorded runs. Everything
else is given: read it, but do not change it. The grader restores the given files before
grading, so changes to them do nothing.

| You write | What it does | Part |
| --- | --- | --- |
| `agent/tools.py` | `safe_path`, `read_file`, `edit_file`, `format_report`, `run_tests`, and three tool descriptions | 1 |
| `agent/policy.py` | `gate_for`, `budget_stop`, `is_stuck` | 2 |
| `agent/loop.py` | `build_system_prompt`, `run_agent` | 3 |
| `agent/reflexion.py` | `judge`, `write_lesson`, `reflexion` | 4 |
| `server.py` | Your MCP server | 5 |
| `runs/runA/`, `runs/runB/` | Your two recorded runs, made by the run command | 6 |
| `.claude/agents/reviewer.md` and `.claude/agents/fixer.md` (or the agy versions) | A read-only reviewer and a fixer agent, for the vendor's agent | 7 |
| `runs/vendor/` | The fixer's copy of the project, and its judge result | 7 |
| `REPORT.md`, `LEDGER.md`, `prompts/`, `evidence/` | Your report, ledger, prompts and terminal-agent evidence | 6 to 8 |

Each function you write has a comment above it that gives its exact rules, including the
exact error messages the tests expect. Read `agent/core.py` first: it holds the types
every file uses.

| Given | What it is |
| --- | --- |
| `agent/core.py` | The types and helpers everything uses. Read it first |
| `agent/provider.py` | The Anthropic and OpenAI adapters, plus a scripted model for tests |
| `agent/toolbox.py` | Gets tools from `agent/tools.py`, or from your MCP server over stdio |
| `agent/trace.py` | Writes the trace and prints each step as it happens |
| `agent/testrunner.py` | Runs unittest tests in a separate process with a time limit |
| `agent/cli.py` | The commands in README.md |
| `fixture/` | The small project the agent fixes: `discounts.py`, its tests, and `spec.md` |
| `judge/acceptance_test.py` | The judge, outside every workspace |
| `tests/` | The public tests |

## The rules for AI tools

AI tools are permitted and expected on this assignment. Along with your work you submit a
provenance ledger that records which tools you used, what you asked them, and what you did
to review their output. Submitting AI-generated work you have not reviewed misrepresents
authorship and is an academic-integrity violation under the course syllabus, as is
fabricating ledger entries, traces or results. You are responsible for every line you
submit, including lines you did not type, and you may be asked in class to explain any
part of your submission.

Two rules are specific to this assignment:

1. **The loop is your own code.** A coding assistant may help you write and debug it,
   but `run_agent`, your gates and your stop rules must be plain Python that you can
   explain. Do not use an agent framework (LangGraph, CrewAI, AutoGen, Microsoft Agent
   Framework, smolagents, the Claude Agent SDK, the OpenAI Agents SDK, or similar), and do
   not use an SDK helper that runs the tool loop for you. The given provider makes one
   plain API call per step; that is the only model access the loop needs.
2. **Your agent's runs are AI use too.** Record each of the two runs in the ledger as an
   experiment entry, written from its trace.

### The provenance ledger

Keep `LEDGER.md` as you go, using exactly this schema. It already contains a worked
example; your own entries go below it, under "My entries".

```
## Entry <n>
artifact:  what this entry covers: a file, a commit SHA, a document, or an experiment
tool:      product name, model name, model version, and the date of use
prompts:   one-line summary each; the verbatim prompts live in prompts/ and are
           referenced here by file path
review:    what you read, what you changed, what you rejected, and why
checks:    the commands you ran and their results
evidence:  the requirement, test, or evidence ID this traces to
risk:      what remains unverified after this change

For an experiment, add three fields:
dataset:   task set identifier and its commit SHA or version
result:    metric, N, and the result table or its file path
changed:   what you did differently as a result
```

An entry is written when the work is done, not reconstructed at submission time. A
ledger that is one entry per session rather than one per reviewable change is wrong.

For this assignment, write at least five entries, including: entry 1 from Part 0; one
experiment entry for runA and one for runB, written from their traces; one entry for
the fixer session in Part 7; and one for each reviewable change where an AI tool helped write or review your
code. Save the prompts you typed into AI tools in `prompts/`, one file per entry, and name
that file in the entry.

## The steps

The steps take about 6 hours and 40 minutes. Two or three sittings work well, for
example Parts 0 to 3 on one day and Parts 4 to 8 on another. Parts 1 to 5 need no API
key and cost nothing: every test uses a scripted model.

### Part 0. Set up (20 minutes)

1. Follow README.md, "Setup", steps 1 to 5.
2. Look up the current price of your model on your provider's own pricing page and put
   both numbers in `.env` (`PRICE_INPUT_PER_MTOK`, `PRICE_OUTPUT_PER_MTOK`). If you copied
   your `.env` from Assignment 2, update them: the default model has changed. Prices
   change, so do not copy them from anywhere else.
3. Write ledger entry 1: your provider, your model, the two prices, and the page you
   found them on.

Done when: `python -m agent check-setup` prints "All checks passed."

### Part 1. Tools the model can use well (60 minutes)

**Background.** The model never sees your code. It chooses a tool, and the inputs to
send it, only from the tool's name, its description and its list of inputs, so the
description works like a prompt. Tools work best for a model when they show a little at
a time (a window of lines, not a whole file), check every edit before making it, keep
their output short, and answer a failure with a message that says what to do next. Each
tool should also have only the power its job needs: these four can list, read, edit one
file, and run the tests, and nothing else.

1. In `agent/tools.py`, write `safe_path`, `read_file`, `edit_file`, `format_report` and
   `run_tests`, following the comment above each one.
2. Write the docstring of `read_file`, `edit_file` and `run_tests`. Each docstring is
   that tool's description, and it is the only thing the model will ever learn about the
   tool. Say what the tool does, what each input means, what comes back, and its limits.
   `list_files` is an example of the style.
3. Read `fixture/` so you know the project your agent will work on. Do not change it.

Done when: `pytest tests/test_tools.py` passes.

### Part 2. Gates and stop rules (30 minutes)

**Background.** Asking a person to approve every action wears them out, and after the
twentieth prompt they stop reading. So gate each action by how hard it is to undo:
reading files and running tests change nothing and run freely; an edit is shown to a
person as a diff first; anything the agent was not built for is refused. The agent also
needs rules that stop it: a cap on model calls and tokens, so a confused agent cannot
loop forever and spend money, and a stuck rule, so the same test failure after an edit
ends the run and hands it to a person. Telling the agent in its prompt not to do
something is a request it may ignore; a rule in your code that refuses is a lock.

1. In `agent/policy.py`, write `gate_for`, `budget_stop` and `is_stuck`, following the
   comment above each one. `GATES`, the table of which tools run freely and which ask a
   person, is given.
2. Notice the rule that denies edits to `tests/`. The agent is told nothing about it;
   the policy simply refuses. That is the lock, not the request.

Done when: `pytest tests/test_policy.py` passes.

### Part 3. The loop (75 minutes)

**Background.** An agent is a model, some tools, and a loop. Tool calling has four
moves: you send the task with a list of tools; the model replies with a structured
request naming a tool and its inputs, instead of prose; your code runs that tool; and
you send the result back, so the model can decide again. The model never runs anything
itself; your code decides what happens. Repeat the four moves until the model replies
without asking for a tool, and you have an agent. When the model writes a short thought
before each action and then reads the real result, the pattern is called ReAct (reason
plus act).

1. Read `agent/core.py`. Then read the `AnthropicProvider` class in
   `agent/provider.py`, or `OpenAIProvider` if you use OpenAI. Moves 1 and 2 are marked
   in it with comments: this is tool calling with the real API.
2. In `agent/loop.py`, write `build_system_prompt` and `run_agent`, following the
   comments above them. The comment above `run_agent` lists every step in order.
3. Follow the rules for AI tools above: no framework, and no SDK helper that runs the
   loop.

Done when: `pytest tests/test_loop.py` passes.

### Part 4. The judge and Reflexion (45 minutes)

**Background.** Visible tests rarely check every rule, so a change can pass all of them
and still break the spec. A set of acceptance tests the agent can neither read nor edit,
called the judge here, gives the final verdict. If the agent could edit the judge, the
quickest way to pass would be to change the test. Reflexion puts the judge in a loop: the
agent attempts the task, the judge says pass or fail, and after a fail the model writes a
short lesson that is saved to a file, NOTES.md, and read at the start of the next
attempt. Nothing about the model changes; only what it reads first. A lesson is a claim,
not a fact, so a person should read it, and the number of attempts is capped.

1. Read `judge/acceptance_test.py` next to `fixture/tests/test_discounts.py` and
   `fixture/spec.md`. Which rules do the visible tests check, and which only the judge?
   Your agent will never see the judge, so it cannot know.
2. In `agent/reflexion.py`, write `judge`, `write_lesson` and `reflexion`, following the
   comments above them.

Done when: `pytest tests/test_reflexion.py` passes.

### Part 5. Your tools as an MCP server (30 minutes)

**Background.** MCP, the Model Context Protocol, is an open standard for packaging tools
so that any agent can use them. A server is a separate program that offers tools. A
host, such as Claude Code, agy or your own agent, starts the server and talks to it
through a client. The host asks the server `tools/list` to learn each tool's name,
description and inputs, offers those tools to its model, and sends `tools/call` when the
model asks for one. To the model, an MCP tool looks exactly like a tool written inside
the agent. With the official Python SDK, a function you register with the server becomes
a tool: its name is the tool's name, its docstring is the description, and its
parameters are the inputs.

Installing someone else's MCP server means running their code with access to whatever
you connect it to, and putting their tool descriptions in front of your model on every
request. A description or a tool result can hide instructions meant to steer the agent,
for example to read a file of secrets and pass its contents to the server. This is called
prompt injection. The defenses are to install few servers, from sources you trust, to
read their tool descriptions, and to keep approvals on so you see a call's inputs before
it runs.

1. Write `server.py`, following its docstring. It is about 15 lines.
2. Run `python -m agent check-mcp`. It starts your server as a separate program, the
   way Claude Code would, and prints the tools/list reply. That reply is everything the
   model will know about your tools. Read it.
3. Run the whole test suite: `pytest`.

Done when: `pytest` passes and `python -m agent check-mcp` prints "all checks passed".

### Part 6. Two recorded runs (40 minutes)

**Background.** Now you see every piece working with a real model. When you reject an
edit, your reason goes back to the model as that tool's result, so a good reason improves
its next try. The trace records each step; it is what you debug from, and what your
ledger entries are written from. Run B gets the same tools from your MCP server instead
of from inside the agent; the loop does not change.

**Before you record.** Commit your code. Practice as much as you like with other run
names, such as `python -m agent run try1`; only runA and runB are graded. Before each
recorded run, make sure `NOTES.md` is empty (practice runs with `--judge` add lessons to
it): `git checkout NOTES.md` restores it.

**Run A: local tools, judge after the run.**

    python -m agent run runA

1. When the agent asks you to approve its first edit, answer `n` and give a reason. Any
   reasonable request works, for example: "Add a comment that names the spec rule you
   are following."
2. After that, approve an edit only after you have read its diff. If an edit is wrong,
   reject it and say why.
3. When the agent stops, the command runs the judge once. The agent never sees it.

**Run B: tools from your MCP server, with Reflexion.**

    python -m agent run runB --tools mcp --judge

Approve or reject each edit the same way. If the judge fails attempt 1, a lesson is
written to `NOTES.md` and attempt 2 starts by reading it. There are at most two attempts.

**The rules for recorded runs.** Record each one once. Do not record a run again to get
a better result: a run that fails, gets stuck or runs out of budget earns the same points
as one that passes, when your report says honestly what happened. If a run breaks for a
reason outside your agent, such as a network error or no credit left, record it again and
say so in the ledger.

**After the runs.**

1. Check them: `python -m agent check-trace runA`, `python -m agent check-trace runB`,
   `python -m agent replay runA`, `python -m agent replay runB`. Replay runs your
   committed code again on the saved model replies, with no API key, and checks that it
   makes exactly the same calls. The grader does the same.
2. Read `NOTES.md` and each `trace.jsonl`. You need them for the report.
3. Commit `runs/runA`, `runs/runB` and `NOTES.md`. Do not change your agent code after
   this. If you do, record both runs again, because replay checks the committed code.

Done when: check-trace and replay pass for both runs.

### Part 7. Use a vendor's agent: your tools, a reviewer and a fixer (60 minutes)

**Background.** Terminal agents such as Claude Code and agy are MCP hosts, so the server
you wrote works in them unchanged. In Claude Code, `claude mcp add --scope project`
saves the server in a `.mcp.json` file you can commit, and Claude Code asks you to
approve a project's servers before it starts them; `/mcp` shows each server and its
tools. Both tools can also run a helper agent defined in a file: a name, a description,
and instructions. In Claude Code the file's header can also list the only tools the
helper may use. That list is a lock: a helper limited to Read, Grep and Glob cannot edit
or run anything, whatever it is asked. Writing "never edit" in the instructions is only a
request, and an agy helper file has nothing stronger. A reviewer that did not write the
code, and cannot change it, is a useful second check.

Giving a vendor's agent a new role takes only such a file. The vendor's own loop does the
rest: you choose the instructions and the tools, but you do not control how it decides it
is finished, and it never runs your judge unless something tells it to. Most teams use
agents this way day to day, and write their own loop only when they need a control the
vendor does not offer. In this part you do both on the same bug and compare.

**A. Your tools in a vendor's agent**

1. Make a clean copy of the project for this part: `python -m agent fresh terminal`.
2. Register your server, from the top folder of the repository.

   Claude Code on macOS or Linux:

       claude mcp add --scope project --transport stdio a4-tools -- "$PWD/.venv/bin/python" "$PWD/server.py" --workspace runs/terminal/workspace

   Claude Code on Windows (PowerShell):

       claude mcp add --scope project --transport stdio a4-tools -- "$PWD\.venv\Scripts\python.exe" "$PWD\server.py" --workspace runs/terminal/workspace

   This writes `.mcp.json`. The full path to the virtual environment's Python matters:
   it is the Python that has the `mcp` package.

   Antigravity CLI: create `.agents/mcp_config.json` with the same command and arguments,
   using the full paths for your machine:

       {
         "mcpServers": {
           "a4-tools": {
             "command": "/full/path/to/Assignment-4/.venv/bin/python",
             "args": ["/full/path/to/Assignment-4/server.py", "--workspace", "runs/terminal/workspace"]
           }
         }
       }

   On Windows, use `.venv/Scripts/python.exe`, and write the paths with forward slashes,
   for example `C:/Users/you/Assignment-4/server.py`.

3. Start `claude` (or `agy`) in the same folder. Approve the a4-tools server when asked,
   and check with `/mcp` that it is connected with four tools.
4. Give it this prompt, and approve its calls to your tools:
   "Use the a4-tools MCP server: call its run_tests tool, then its read_file tool on
   discounts.py, and tell me why the failing test fails. Do not change any files."
   Copy the conversation, including the tool calls and their results, into
   `evidence/terminal_mcp.md`.
**B. A read-only reviewer**

5. Write a reviewer helper that can only read. In Claude Code, create
   `.claude/agents/reviewer.md`. It starts with a header between two `---` lines, then
   the instructions in plain words. You may use this one as it is or improve the
   instructions:

       ---
       name: reviewer
       description: Reviews a changed Python file against spec.md. Never edits anything.
       tools: Read, Grep, Glob
       ---
       You are a code reviewer. Read spec.md, then read the file you are asked to
       review. For each rule in spec.md, say whether the code follows it. For each
       problem, give the file, the line, the rule it breaks, and why it matters.
       If every rule is followed, say so.

   In agy, put the same file in `.agents/agents/reviewer/agent.md`, without the tools
   line. If this is the first agent file in the project, restart the tool.
6. Ask: "Use the reviewer subagent to review runs/runB/workspace/discounts.py against
   runs/runB/workspace/spec.md." Save its review in `evidence/review.md`.

**C. A fixer agent on the same bug**

7. Make another clean copy of the project: `python -m agent fresh vendor`.
8. Write a fixer agent. In Claude Code, create `.claude/agents/fixer.md`:

       ---
       name: fixer
       description: Fixes failing unit tests in runs/vendor/workspace with the smallest change.
       tools: Read, Edit, Bash
       ---
       You fix failing unit tests in the project in runs/vendor/workspace.
       Work only inside that folder.
       1. Run the tests with: cd runs/vendor/workspace && python -m unittest
       2. Read the code behind each failure.
       3. Make the smallest change that fixes it. Do not change anything in tests/.
       4. Run the tests again. Stop when every test passes, and say what you changed.

   Use it as it is, so the comparison with your own agent is fair: neither one is told
   about `spec.md`. In agy, put the same file, without the tools line, in
   `.agents/agents/fixer/agent.md`.
9. Run it from the top folder of the repository, in a terminal where the virtual
   environment is on.

   Claude Code:

       claude --agent fixer "Make the tests pass in runs/vendor/workspace."

   agy: start `agy`, open `/agents`, choose fixer, and give it the same task. If fixer is
   not in the list, ask agy to use the fixer agent by name.

   Approve each edit and each command only after you have read it, as you did with your
   own agent. When it stops, copy the session, including its edits, commands and your
   answers, into `evidence/fixer.md`.
10. Run `python -m agent judge vendor`. It runs the visible tests and the judge on
    `runs/vendor/workspace`, lists the files that differ from the original project, and
    saves all of this in `runs/vendor/judge.txt`.
11. Commit `.mcp.json` (or `.agents/mcp_config.json`), both agent files, `evidence/`, and
    `runs/vendor/`.

Done when: the three evidence files hold real output and `runs/vendor/judge.txt` exists.

### Part 8. Write the report and finish the ledger (40 minutes)

1. Run `python -m agent summary` and paste its table into REPORT.md Section 1 exactly as
   printed. The grader runs the same command and compares.
2. Fill in Sections 2 to 8 of REPORT.md. Each asks for specific evidence from your own
   traces and files, with step numbers where they apply.
3. Finish LEDGER.md, and check that every prompts file it names exists in `prompts/`.
4. Commit and push.

## What to submit

Push your repository to GitHub and submit its link on Canvas. The instructor must be able
to open it. It must contain:

- your five code files: `agent/tools.py`, `agent/policy.py`, `agent/loop.py`,
  `agent/reflexion.py`, `server.py`
- `runs/runA/` and `runs/runB/`, each with `run.json`, `trace.jsonl`, `replies.jsonl`
  and `workspace/`, and `NOTES.md` as Run B left it
- `.mcp.json` or `.agents/mcp_config.json`, and your two agent files (reviewer and fixer)
- `runs/vendor/`, with `workspace/` and `judge.txt`
- `evidence/terminal_mcp.md`, `evidence/review.md` and `evidence/fixer.md`
- `REPORT.md`, `LEDGER.md` and `prompts/`

Never commit `.env`; it holds your key. The `.gitignore` you created in README.md,
"Setup", step 4, leaves it out.

## How it is graded

RUBRIC.md has every item. In short: your code, checked by public and hidden tests, is 50
points; your recorded runs and terminal-agent files, checked by script, are 24 points;
your report, evidence and ledger, read by the instructor, are 26 points. The hidden tests
check the same written rules as the public tests, on more cases. No points are given for
extra runs, larger models, extra features or extra spending.
