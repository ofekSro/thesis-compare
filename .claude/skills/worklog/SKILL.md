---
name: worklog
description: Appends a dated Hebrew entry to WORKLOG.md describing what was asked, done, found and decided in the current conversation, only when the owner runs /worklog. Also /worklog show [N] to read the last entries and /worklog draft to see the entry without writing it. Never runs automatically.
---

You are writing the owner's research diary. The owner writes the thesis from it, so an entry must let them reconstruct, weeks later, what happened in this conversation and why. It is written by you, the main session, because only you saw the conversation. No agent is launched.

Language: Hebrew, with technical terms, file names, function names and commands left in English exactly as they appear.

## `/worklog` (or `/worklog add [title]`)

1. Locate `WORKLOG.md` at the repo root. If it does not exist, create it with the single line `# יומן עבודה` and nothing else, then append.
2. Compose the entry from the whole conversation since the last `/worklog` in it (or from its start). Use this shape, and the format in the project `CLAUDE.md` if it differs:

   ```
   ## <YYYY-MM-DD> - <כותרת קצרה>
   **מה ביקשתי:** מה המשימה או השאלה שפתחה את השיחה, במילים של הבעלים.
   **מה עשינו:** פעולות לפי סדר. קבצים שנקראו או שונו, פקודות שהורצו, agents שהופעלו, commits עם hash.
   **מה מצאנו:** הממצאים. מספרים מדויקים כפי שהודפסו, לא מהזיכרון. לפני ואחרי כשמשהו השתנה.
   **החלטות:** מה הוחלט, למה, ומה נדחה ולמה. מי החליט (הבעלים).
   **שאלות פתוחות:** מה נשאר לא פתור, ומה צריך כדי לפתור.
   **לתזה:** לאיזה פרק או סעיף זה שייך, ומשפט או שניים שאפשר לכתוב שם ישירות.
   ```

3. Rules for the content:
   - Numbers are copied from tool output that appeared in the conversation. If a number is not in the conversation, write "לא נמדד" rather than a guess.
   - Decisions are attributed: "הבעלים החליט" versus "הוצע ולא הוחלט".
   - A change that was proposed and rejected is recorded as rejected, with the reason.
   - A decision is referenced by its D number from `docs/DECISIONS.md` when one exists.
   - Findings from `/verify` are referenced by id and file (`algorithm-3`, `docs/audit/2026-09-27/algorithm.md`), not copied in full.
   - Do not summarise the conversation's chit-chat. Only what matters for the research.
   - Length: as long as the session deserves. A five-minute question is four lines. A day of auditing may be forty.
4. Append the entry to the end of `WORKLOG.md`. Never modify earlier entries. Show the owner the entry as written and the file path.
5. Do not commit. If the owner wants the log committed, they say so.

## `/worklog draft`

Compose the entry as above and show it, without writing. The owner may then say `/worklog` to write it, possibly with corrections.

## `/worklog show [N]`

Print the last N entries (default 3) of `WORKLOG.md`.

## Never

- Never write an entry without the owner running `/worklog`.
- Never write from a hook, a subagent, or at the end of a session on your own initiative. If you think a session deserves an entry, say so in one line and leave the decision to the owner.
