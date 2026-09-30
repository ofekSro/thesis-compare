---
name: todo
description: Works through TODO.md in batches. Plans the next batch of related tasks (task-planner), implements all of them without stopping (task-implementer), verifies and fixes (task-verifier), runs real GUI QA and UX review when the GUI changed, then moves finished tasks to DONE.md with details. Use as /todo to plan and confirm once, /todo go to run the whole cycle without confirmation, /todo batch <path> to run an existing plan.
---

You are orchestrating a batch of TODO tasks end to end. Subagents cannot launch each other, so you launch every agent from here and pass the reports along. Apart from one optional confirmation at the start, the cycle runs without stopping.

## Arguments

- none: plan, show the batch, ask the user once to confirm, then run the full cycle.
- `go`: plan and run the full cycle without asking.
- `plan`: plan only, show the batch, stop.
- `batch <path>`: skip planning, run the cycle on an existing plan file.
- `next`: same as `go`, but skip tasks listed in "needs clarification".

## Stage 0: preconditions

1. `TODO.md` must exist in the project root (also accept `todo.md`, `TODO.txt`). If missing, say so and stop.
2. If `DONE.md` does not exist, create it with a heading `# Done` and nothing else.
3. Git is required, because each task is a commit and a failed batch must be revertable. If the folder is not a repository, ask once whether to `git init` and commit the current state. Without git, stop.
4. The working tree must be clean. If not, ask the user to commit or stash. Do not proceed on a dirty tree.
5. Record the current commit hash as `BASE` for later diffs and reverts.

## Stage 1: plan

1. Launch **task-planner**. Wait for the plan file path.
2. Read the plan. Show the user, in Hebrew, the batch name, the task list with sizes, the risks section, and any "needs clarification" items.
3. Without `go` or `next`: ask the user to confirm the batch, or to remove tasks from it. Stop and wait. With `go` or `next`: continue immediately.

## Reference documents

If `docs/references/INDEX.md` exists, mention its path in the prompt of every agent you launch, with the sentence "Read docs/references/INDEX.md first and consult the documents it lists for anything they cover." The planner attaches references per task; the implementer and verifier must read them. In the final report, list which documents were consulted for which tasks, taken from the agents' reports. If a task was excluded because a document is missing, tell the user the `/ref add` command to run.

## Stage 2: implement

Launch **task-implementer** with the plan path. Wait for its report. Save the report to `docs/batches/<plan-name>.implement.md`.

## Stage 3: verify and fix

Launch **task-verifier** with the plan path and the implementer's report. Wait. Save its report to `docs/batches/<plan-name>.verify.md`.

## Stage 4: simplify

Take the union of files touched by the implementer and the verifier. Launch **eng-code-simplifier** on exactly those files. Run the test suite yourself afterwards (`python -m pytest -q`). If tests fail, revert the simplifier's changes with `git checkout -- <files>` and note it. Otherwise commit as `simplify(batch): <plan-name>`.

## Stage 5: QA and UX, only if a GUI file changed

Decide from the touched files (imports of tkinter, PySide, PyQt) or the "GUI screens touched" lists.
1. Launch **gui-qa-tester** and **gui-ux-reviewer** in parallel. Give both the list of screens touched so they focus there first.
2. Read the QA report and look at the screenshots of every FAIL with the Read tool.
3. If QA reports a FAIL on a screen the batch touched, launch **task-verifier** once more with the QA failure list as its input, then run the test suite and re-run **gui-qa-tester**. One retry only. If it still fails, the affected tasks are marked FAILED.

## Stage 6: bookkeeping

Do this yourself, it is small and must be exact.
1. Run the full test suite one last time and record the result.
2. For every task with final status VERIFIED or FIXED:
   - Remove its line from `TODO.md` (keep the file's structure and the other tasks untouched).
   - Append an entry to `DONE.md` in this shape, matching any existing style in the file if there is one:

     ```
     ## <YYYY-MM-DD> <task title as it appeared in TODO.md>
     - What: <two to four sentences from the implementer's report>
     - Files: <list>
     - Tests: <command and result>
     - Commits: <hashes>
     - QA: <PASS / n/a / FAIL with report path>
     ```
3. For every task with status SKIPPED, PARTIAL or FAILED: leave it in `TODO.md` and append a short note under it, `(blocked: <reason>, see docs/batches/<plan-name>.verify.md)`.
4. Append engineering questions from all reports to `docs/ENGINEERING_QUESTIONS.md`.
5. Commit `TODO.md`, `DONE.md` and the docs with the message `chore: close batch <plan-name>`.

## Stage 7: report to the user (Hebrew)

- Batch name, tasks done vs left, with one line per task.
- Test result, QA pass/fail counts and the report path, UX top findings.
- Commit range `BASE..HEAD`, and the sentence: to undo the whole batch run `git reset --hard BASE` (with the actual hash), or `git revert` for individual commits.
- Engineering questions that need the author's decision.
- The suggested next batch from the planner's "remaining backlog".

## Rules

- Never ask the user anything between Stage 2 and Stage 6. Collect questions and put them in the final report.
- Never let a report be the only evidence: run the tests yourself before bookkeeping.
- Never move a task to DONE.md that the verifier did not mark VERIFIED or FIXED.
- Never change numerical results, coefficients or units except where a task explicitly says so with a source. Anything else goes to `docs/ENGINEERING_QUESTIONS.md`.

## Model fallback

Agents that need judgement run on Fable 5 (`model: claude-fable-5` in their frontmatter). If an agent comes back with a refusal on safety grounds, fails because Fable 5 is unavailable or out of usage, or returns an empty or evasive report that shows it declined the task (this domain uses words like charge, TNT and detonation in an ordinary engineering sense), relaunch the same agent once with the Agent tool's `model: "claude-opus-5-5"` override (Opus 5.5), with the same prompt. Say in the reply that the fallback was used and for which agent. Do not retry more than once, and do not rephrase the task to get around a refusal; if Opus also declines, report it to the owner.
