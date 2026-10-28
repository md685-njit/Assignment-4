# Assignment 4 Report

Name:
Commit graded:

Answer from your own traces. Give step numbers as `attempt 1, step 4`. Keep to the word
limits; a short answer with the right evidence earns full points.

## 1. The runs

Run `python -m agent summary` and paste its table here exactly as printed.

(paste the table here)

## 2. A rejection is feedback (Run A, at most 100 words)

Which step proposed the edit you rejected, and what was your reason? What did the agent
do next, and at which step? Did it follow your reason?

## 3. The visible tests and the judge (Run A, at most 120 words)

What did the last `run_tests` in runA report, and what did the judge say after the run?
If the judge failed, which rule in `spec.md` did the code break, at which step did the
agent stop, and why did it stop there?

## 4. The lessons (Run B, at most 150 words)

Quote every lesson runB wrote to `NOTES.md`. For each one, say whether it names the real
cause, points at evidence, and says what to do next. Did attempt 2 follow it? Give the
step that shows it. If attempt 1 passed, say which step shows why no lesson was needed.

## 5. Memory grows (Run A, at most 60 words)

Give `input_tokens` from the first and the last tool event in `runs/runA/trace.jsonl`,
with their step numbers. Why does the number grow from step to step?

## 6. MCP (at most 120 words)

Quote one of your tool descriptions exactly as `python -m agent check-mcp` showed it in
the tools/list reply. Then name one risk of installing someone else's MCP server, and say
which part of your agent would stop it, or that nothing in your agent would.

## 7. The reviewer and the judge (at most 100 words)

What did your reviewer find in runB's final `discounts.py`? Did it find anything the
judge did not, or miss anything the judge caught? In the tool you used, was the
reviewer's read-only rule a lock or a request, and how do you know?

## 8. Your agent and a vendor's agent (at most 120 words)

What did the fixer change, and what did `python -m agent judge vendor` report for the
visible tests and for the judge? Did it change anything in `tests/`? Compare this with
runA, where your own agent had the same task on the same project. Then name one thing you
could control in your own agent that the fixer file could not set, and one thing that was
easier with the vendor's agent.
