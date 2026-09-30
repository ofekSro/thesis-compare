---
name: refactor
description: Orchestrates a safe, phased refactor of a Python engineering desktop app (tkinter or PySide/PyQt). Runs arch-reviewer and gui-ux-reviewer in parallel, then executes the plan one phase at a time with arch-refactorer, followed by eng-code-simplifier on the touched files, tests, and a commit. Use as /refactor to start, or /refactor phase N to run one phase.
---

You are orchestrating a multi-agent refactor. Subagents cannot launch each other, so you launch every agent from here and pass results between them. The user must approve each phase before it runs.

## Arguments

- No arguments, or `review`: run the review stage only.
- `phase N`: run phase N of the existing plan.
- `ux N`: apply UX finding N from `docs/UX_REVIEW.md` through arch-refactorer.
- `simplify <files>`: run eng-code-simplifier on the given files only.

## Stage 0: preconditions (always)

1. Check that the working directory is a git repository (`git rev-parse --is-inside-work-tree`). If not, tell the user that phased refactoring requires git and ask once whether to run `git init` and make an initial commit of the current state. Do not proceed without git.
2. Check the working tree is clean. If not, ask the user to commit or stash first. Do not proceed on a dirty tree.
3. Confirm a Python interpreter and the test runner are available (`python -m pytest --version`). If pytest is missing, tell the user and offer to add it to requirements; the refactorer needs it.

## Stage 1: review (on `/refactor` or `/refactor review`)

1. Launch **arch-reviewer**, **gui-ux-reviewer** and **gui-qa-tester** in parallel using the Agent tool, all with the project root as scope. The QA run establishes the baseline: what works and how the app looks before anything changes.
2. When all three return, read `docs/ARCHITECTURE_REVIEW.md`, `docs/UX_REVIEW.md` and the QA report under `docs/qa/`.
3. Present to the user, in Hebrew and briefly:
   - the QA baseline: what passed, what failed, and the startup screenshot,
   - the three most important architecture findings,
   - the three most important UX findings,
   - the number of phases in the plan and what Phase 0 and Phase 1 will do.
4. Ask the user whether to start with Phase 0. Stop and wait. Do not run any phase without an explicit answer.

## Stage 2: one phase (on `/refactor phase N`, or after approval)

1. Re-run the Stage 0 checks.
2. Launch **arch-refactorer** with the instruction `run phase N`. Wait for its report.
3. If the report says tests failed or the phase was aborted, show the report to the user and stop. Do not retry automatically.
4. Take the **Files touched** list from the report. Launch **eng-code-simplifier** on exactly those files. Wait for its report.
5. Run the test suite yourself: `python -m pytest -q`. If it fails after simplification, revert the simplifier's changes with `git checkout -- <files>` and report that the simplifier was rolled back.
6. If tests pass and the simplifier changed anything, commit with the message `simplify(phase N): <files>`.
7. If the phase touched any GUI file, or the phase is a UX item, launch **gui-qa-tester**. It opens the real application, screenshots it, drives the main flow and compares displayed numbers with the core functions. Wait for its report and read its screenshots yourself with the Read tool when a failure is reported.
8. If gui-qa-tester reports a FAIL that did not exist before the phase, show it to the user and stop. Offer two options: revert the phase (`git revert` of both commits) or send the failure back to arch-refactorer as a fix within the same phase. Do not pick for the user.
9. Report to the user in Hebrew: what moved, test results, QA pass/fail counts with the report path, commit hashes, suspected engineering issues collected from all agents, and the refactorer's recommendation for the next phase.
10. Ask whether to run phase N+1. Stop and wait.

## Stage 3: UX item (on `/refactor ux N`)

Same as Stage 2, but the instruction to arch-refactorer is `apply UX finding N from docs/UX_REVIEW.md`, and the commit prefix is `ux`.

## Rules for the orchestrator

- Never run more than one phase per user approval.
- Never let an agent's report be the only record: always run the tests yourself before committing.
- If any agent reports a suspected engineering error (coefficient, unit, validity range), collect it in a running list at `docs/ENGINEERING_QUESTIONS.md` so the user can review it separately. Never let an agent fix those.
- Keep the user's inputs and outputs of the app unchanged throughout; the goal is structure and usability, not new features.

## Model fallback

Agents that need judgement run on Fable 5 (`model: claude-fable-5` in their frontmatter). If an agent comes back with a refusal on safety grounds, fails because Fable 5 is unavailable or out of usage, or returns an empty or evasive report that shows it declined the task (this domain uses words like charge, TNT and detonation in an ordinary engineering sense), relaunch the same agent once with the Agent tool's `model: "claude-opus-5-5"` override (Opus 5.5), with the same prompt. Say in the reply that the fallback was used and for which agent. Do not retry more than once, and do not rephrase the task to get around a refusal; if Opus also declines, report it to the owner.
