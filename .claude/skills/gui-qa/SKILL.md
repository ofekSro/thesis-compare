---
name: gui-qa
description: Runs a real render-and-drive QA pass on the project's tkinter or PySide/PyQt GUI using the gui-qa-tester agent, then shows the user the screenshots and failures. Use as /gui-qa after any GUI change, or /gui-qa <entry.py> to point at a specific entry file.
---

Run a real GUI test of this project and show the user the evidence.

1. Determine the entry point: the argument if given, otherwise look for `main.py`, `app.py`, `__main__.py`, or a file that creates `QApplication` / `tk.Tk()`. If several candidates exist, ask the user which one.
2. Launch the **gui-qa-tester** agent with the entry point and the project root. Wait for its report.
3. Read the QA report it names and open, with the Read tool, at least the startup screenshot and every screenshot attached to a FAIL. Look at them yourself. Do not rely only on the agent's text.
4. Report to the user in Hebrew:
   - pass/fail/skipped counts,
   - each failure in one or two sentences with the screenshot path,
   - visual findings worth fixing, with screenshot paths,
   - the displayed-vs-core numbers table if the agent produced one,
   - the report path.
5. Do not fix anything. If the user wants fixes, they run `/refactor ux N` or ask directly.

Notes:
- tkinter apps will open a real window on the desktop during the run. Tell the user not to click on it while the test runs.
- If the agent reports that `pillow` is missing, offer to install it, since tkinter screenshots need it.

## Model fallback

Agents that need judgement run on Fable 5 (`model: claude-fable-5` in their frontmatter). If an agent comes back with a refusal on safety grounds, fails because Fable 5 is unavailable or out of usage, or returns an empty or evasive report that shows it declined the task (this domain uses words like charge, TNT and detonation in an ordinary engineering sense), relaunch the same agent once with the Agent tool's `model: "claude-opus-5-5"` override (Opus 5.5), with the same prompt. Say in the reply that the fallback was used and for which agent. Do not retry more than once, and do not rephrase the task to get around a refusal; if Opus also declines, report it to the owner.
