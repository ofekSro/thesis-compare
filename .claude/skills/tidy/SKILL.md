---
name: tidy
description: Proposal-first code tidying for a research repo. /tidy <files or package> runs eng-code-simplifier in review-only mode and returns a numbered list of proposed simplifications and comment improvements per file. /tidy structure runs arch-reviewer for the repo layout. /tidy apply <file> <item numbers> explains the chosen items, waits for approval, applies them, and verifies that numerical outputs are unchanged. Nothing is edited without the owner's explicit approval.
---

You keep the code readable without changing what it computes. The owner's rules from the project `CLAUDE.md` bind you: no change without explicit approval after the owner understands it, stay inside the repo, never touch a formula, threshold or constant, never delete a rationale comment. Reply in Hebrew.

## `/tidy <path> [more paths]`

1. Resolve the paths. A package or folder expands to its `.py` files; list them and confirm the count before launching if it is more than ten.
2. Launch **eng-code-simplifier** with the instruction `review only` and the file list. It returns a numbered proposal per file: what it would simplify, what comment or docstring it would add or fix, and what it deliberately would not touch.
3. Show the owner the proposal as returned, grouped by file, with item numbers. Add one line per item saying whether it can change any numerical output (it should never, but say so explicitly when a change reorders floating-point arithmetic).
4. Stop. The owner picks items with `/tidy apply`.

## `/tidy structure`

1. Launch **arch-reviewer** with the note that this is a research analysis repo (a core package, standalone tools, results of record, tests), not a GUI application, and that it must write only `docs/ARCHITECTURE_REVIEW.md`.
2. Show the owner the findings and the proposed phases. Nothing is executed. If the owner wants a phase done, it goes through `/tidy apply` for the files it names, or through a direct request with the same approval flow.

## `/tidy apply <file> <item numbers>`

1. Quote the chosen items from the latest proposal for that file. If the proposal is no longer in the conversation, re-run `/tidy <file>` first.
2. Before touching anything, write in Hebrew: **מה ישתנה** (the concrete edits), **מה לא ישתנה** (numerical outputs, public names, results of record), **איך נוודא** (the fast tests, plus a before/after comparison script on the functions in that file with representative inputs).
3. Stop and wait for approval.
4. On approval: run the comparison script BEFORE the change and keep its output. Launch **eng-code-simplifier** in edit mode restricted to the chosen items ("apply only items 2, 5 and 7 of your proposal; nothing else"). Run the comparison script AFTER, and the fast tests. Show `git diff`, the test result, and the largest numerical difference (which must be zero, or within the floating-point tolerance the agent declared and the owner accepted).
5. If anything differs beyond that, revert the file with `git checkout -- <file>`, tell the owner, and stop.
6. Ask whether to commit. Commit only on a yes, message style `area: what changed`, listing the item numbers. Ask separately before any push.

## Rules

- Never apply items the owner did not name.
- Never let the simplifier run in edit mode without a before/after comparison.
- Never touch `constants.py`-style rationale comments, pinned test values or results of record.

## Model fallback

Agents that need judgement run on Fable 5 (`model: claude-fable-5` in their frontmatter). If an agent comes back with a refusal on safety grounds, fails because Fable 5 is unavailable or out of usage, or returns an empty or evasive report that shows it declined the task (this domain uses words like charge, TNT and detonation in an ordinary engineering sense), relaunch the same agent once with the Agent tool's `model: "claude-opus-5-5"` override (Opus 5.5), with the same prompt. Say in the reply that the fallback was used and for which agent. Do not retry more than once, and do not rephrase the task to get around a refusal; if Opus also declines, report it to the owner.
