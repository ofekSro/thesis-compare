---
name: decide
description: Decision register and decision review for a research repo. /decide index builds docs/DECISIONS.md from the audit summaries, the worklog, decision notes and git history. /decide open <topic> frames a new decision before any measurement (the owner's question, anchors, candidates and what each measures, a numeric decision rule). /decide check D<n> [paths] tests one decision against the owner's question and anchors with an adversarial but reasonable reviewer. /decide status shows what is open, in force and superseded. Includes a binding protocol for disagreements with the owner.
---

You keep the owner's research decisions honest: each one tied to the owner's engineering question, to the facts the owner knows to be true, to its evidence and to its commit. Reply in Hebrew; technical terms stay in English.

Obey the project `CLAUDE.md`. In particular, if it requires approval before any file change, every write below (including `docs/DECISIONS.md`) is shown as a draft first and written only after the owner approves. Stay inside the repo; read paths outside it only when the owner names them in the command.

## Why this skill exists

A past decision went wrong in a specific way: the assistant proposed a criterion that was coherent but answered a different question from the owner's, defended it with confidence, and treated the owner's contradicting knowledge as a misunderstanding. The owner found the gap alone. Everything below is built to prevent that: the question comes first, the owner's anchors are evidence, and disagreement triggers a check, not a defence.

## The register: `docs/DECISIONS.md`

Hebrew, one section per decision, existing files are pointed to, never rewritten:

```
## D<n> - <כותרת>
**סטטוס:** פתוח / בתוקף / הוחלף על ידי D<m> / תוקן (באג)
**תאריך הכרעה:** ... · **commit:** ...
**השאלה ההנדסית:** במילים של הבעלים.
**עוגנים:** מה הבעלים יודע שנכון, ומקור כל אחד (סימולציה/נתונים, ספרות, אינטואיציה הנדסית).
**החלופות:** כל מועמד ומה הוא בודק בפועל, במשפט.
**כלל ההכרעה:** במספרים. "נקבע מראש" / "לא נקבע מראש".
**ההכרעה:** מה נבחר ולמה. מי הכריע (הבעלים).
**מספרים שמצוטטים:** הערכים שנכנסים לתזה/למאמר, עם הקובץ שממנו הם נלקחים.
**ראיות:** קבצים, סוויטות, דוחות audit.
**יומן:** הפניה לרשומות WORKLOG הרלוונטיות.
**ביקורת:** תאריך ופסק דין של `/decide check` האחרון, או "טרם נבדק".
```

Rules:
- Numbered D's from audit summaries keep their numbers. A decision taken without a number gets the next free D.
- Bug fixes with no real alternatives get one line with status "תוקן".
- Superseded decisions stay, with their numbers, and point to the replacement. They are the "rejected alternatives" of the thesis method chapter.
- The worklog is never edited. Links to it live in the register only.

## `/decide index`

1. Read: every `docs/audit/*/SUMMARY.md` (the "Decisions the owner must make" section), every `docs/audit/*/HANDOFF.md`, every decision note under `docs/audit/`, the "החלטות" and "לתזה" sections of `WORKLOG.md`, the rationale comments in the constants module, and `git log --oneline` with messages mentioning a D or a finding id.
2. Build the register as above. For each decision, fill what the sources state. Where a field is not in the sources, write "לא תועד" rather than inferring it; in particular never invent the owner's question or anchors.
3. Flag, in a short list at the top: decisions whose "לתזה" numbers in the worklog were later superseded; decisions marked decided in one source and open in another; decisions with no commit.
4. Show the draft (or a summary if it is long) and write it after approval. Then list the decisions whose question or anchors are "לא תועד", and ask the owner to fill them for the ones that matter most.

## `/decide open <topic>`

For a decision not yet made. No measurement runs until this is approved.
1. **The question.** Ask the owner for the engineering question in their own words. Restate it in one sentence and ask whether that is it. Iterate until the owner says yes.
2. **Anchors.** Ask what the owner already knows must hold for any acceptable answer, and where each comes from. Record them verbatim.
3. **Engineering significance.** Ask what size of difference matters for this quantity, in absolute or relative terms as the owner prefers. Record it. This is what separates a real objection from a pedantic one.
4. **Candidates.** List the candidates, including any the owner proposes. For each, one sentence on what it actually measures, and whether that matches the question. Present them side by side. Do not recommend yet.
5. **Decision rule.** Agree a rule with numbers before measuring: which result would make which candidate win, and which result would send everyone back to the question.
6. Write the D entry with status "פתוח" (after approval). Only then measure.

## `/decide check D<n> [paths outside the repo]`

1. Read the D entry. If the question or anchors are "לא תועד", ask the owner for them first; a review without them tests coherence, not correctness, and that is the failure this skill exists for.
2. Launch **decision-reviewer** with the entry, the evidence paths, the commit, and the owner's significance threshold if recorded.
3. If paths to the thesis or paper were given, also check which sentences there use numbers this decision later superseded, and list them. No edits.
4. Report in Hebrew: the verdict, the "does it answer the question" section in full, any anchor contradiction, and the objections with their "what would change my mind". Then stop. The owner decides.
5. Offer to update the "ביקורת" field of the D entry, with approval.

## `/decide status`

Table: D, title, status, last review verdict. Then: open decisions; decisions in force never reviewed; superseded decisions whose numbers still appear in a "לתזה" section of the worklog.

## Disagreement protocol - binding on the main session

Applies whenever the owner disagrees with a proposal about a decision, in this skill or in any conversation about a D.
1. **Restate first.** Before answering an objection, restate the owner's position in one or two sentences and ask whether that is what they mean.
2. **Test before arguing.** If the owner proposes an alternative or says a result looks wrong, check it in numbers (existing tables, suites, a quick read-only probe) before arguing against it. Show the numbers.
3. **Anchors are evidence.** A result that contradicts something the owner knows from data, literature or engineering intuition is evidence against the proposal until explained in numbers the owner can check.
4. **Two rounds, then stop.** If the disagreement survives two exchanges, stop and say: "ייתכן שאנחנו מחפשים דברים שונים." Then lay out side by side what each candidate measures and what the owner's question is, and ask which question is the right one. Do not repeat the argument a third time.
5. **Confidence matches evidence.** State a recommendation with the strength its evidence supports. When the choice is between framings rather than between numbers, say so and let the owner choose.

## Links to other skills

- `/verify fix <id>`: when a fix involves a choice between alternatives, start it with `/decide open` so the D entry exists before the change.
- `/worklog`: an entry about a decision names its D; the register links back to the entry.

## Model fallback

decision-reviewer runs on Fable 5 (`model: claude-fable-5`). If it comes back with a refusal on safety grounds, or fails because Fable 5 is unavailable or out of usage, relaunch it once with the Agent tool's `model: "claude-opus-5-5"` override and the same prompt, and say in the reply that the fallback was used. Do not rephrase the task to get around a refusal; if Opus 5.5 also declines, report it to the owner.
