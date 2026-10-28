# Assignment 4 Rubric: Build Your Own Coding Agent

100 points. Every item can be checked on its own. Where an item says "in proportion",
the points are the share of tests passed, rounded to the nearest whole point.

Before grading, the grader restores the official given files and public tests, so
editing them changes nothing. The grader also runs a set of hidden tests that check the
same written rules as the public tests, on more cases. The grader needs no API key:
recorded runs are checked by replaying their saved model replies.

## A. Your code, checked by tests (50 points)

| Item | Points | How it is checked |
| --- | --- | --- |
| A1 | 6 | `pytest tests/test_tools.py` passes; in proportion |
| A2 | 4 | `pytest tests/test_policy.py` passes; in proportion |
| A3 | 8 | `pytest tests/test_loop.py` passes; in proportion |
| A4 | 5 | `pytest tests/test_reflexion.py` passes; in proportion |
| A5 | 4 | `pytest tests/test_server.py` passes; in proportion |
| A6 | 23 | Hidden tests pass, in proportion within each group: tools 6, policy 3, loop 8, Reflexion 4, server over stdio 2 |

## B. Your runs and terminal-agent files, checked by script (24 points)

| Item | Points | How it is checked |
| --- | --- | --- |
| B1 | 4 | `python -m agent check-trace runA` and `python -m agent check-trace runB` pass; 2 points each |
| B2 | 6 | `python -m agent replay runA` and `python -m agent replay runB` match their traces; 3 points each |
| B3 | 3 | runA used local tools and no Reflexion, and the first edit you were asked to approve was rejected with a reason |
| B4 | 4 | 2 points: runB used MCP tools and Reflexion. 1 point: the trace has a judge verdict for every attempt. 1 point: if attempt 1 failed, its lesson is in the committed NOTES.md (given if attempt 1 passed) |
| B5 | 2 | `python -m agent check-mcp` passes |
| B6 | 3 | 2 points: `.mcp.json` or `.agents/mcp_config.json` registers a server that runs your `server.py`. 1 point: a reviewer helper file exists; in Claude Code, its tools line lists only Read, Grep and Glob |
| B7 | 2 | 1 point: a fixer agent file exists (`.claude/agents/fixer.md` or `.agents/agents/fixer/agent.md`) with a name, a description and instructions. 1 point: `runs/vendor/workspace/discounts.py` differs from the original project, and `runs/vendor/judge.txt` and `evidence/fixer.md` exist |

## C. Your report, evidence and ledger, read by the instructor (26 points)

| Item | Points | How it is checked |
| --- | --- | --- |
| C1 | 3 | Section 1 of REPORT.md matches the output of `python -m agent summary`, row for row |
| C2 | 3 | Section 2 gives the step of the edit you rejected, your reason, and what the agent did next with its step number, and all three match runA's trace |
| C3 | 3 | Section 3 gives runA's last visible test result and the judge's verdict; if the judge failed, it names the spec rule and the step where the agent stopped, with one sentence on why it stopped there |
| C4 | 4 | Section 4 quotes every lesson runB wrote and judges each one by the three tests listed in REPORT.md (names the real cause, points at evidence, says what to do next), and says with a step number whether attempt 2 followed it. If attempt 1 passed, it names the step that shows why no lesson was needed |
| C5 | 1 | Section 5 gives `input_tokens` and the step of runA's first and last tool events, matching the trace, and explains why the number grows |
| C6 | 3 | Section 6 quotes one tool description exactly as tools/list showed it, and names one risk of installing someone else's MCP server and which part of your agent does or does not stop it |
| C7 | 3 | 2 points: `evidence/terminal_mcp.md` shows the vendor's agent calling at least two of your server's tools, with their results. 1 point: `evidence/review.md` holds the reviewer's review, and Section 7 compares it with the judge and says whether the read-only rule was a lock or a request in your tool |
| C8 | 4 | 1 point: at least five ledger entries with all seven fields. 2 points: experiment entries for runA and runB whose dataset, result and changed fields come from their traces. 1 point: every prompts file the ledger names exists in `prompts/` |
| C9 | 2 | Section 8 gives what the fixer changed and the visible-test and judge results from `runs/vendor/judge.txt`, compares them with runA, and names one control your own agent had that the fixer file could not set and one thing that was easier with the vendor's agent |

## Deductions outside the points

Submitting unreviewed AI output, fabricated ledger entries, or fabricated or edited
traces is an academic integrity violation under the course syllabus, not a points
question. So is a loop built on an agent framework instead of your own code.
