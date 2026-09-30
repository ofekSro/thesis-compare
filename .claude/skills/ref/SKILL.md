---
name: ref
description: Registers reference documents (manuals, standards, papers, e.g. the blastFoam user guide or UFC 3-340-02) so every agent bases its work on them. Keeps docs/references/INDEX.md, extracts searchable text from PDFs, and answers "which reference covers X". Use as /ref add <file> "<what it covers>", /ref list, /ref find <topic>, or /ref check.
---

You maintain the project's reference library under `docs/references/`. All agents in this toolkit read `docs/references/INDEX.md` before working on a task, so the index is the single place that tells them which document to consult for what.

## Layout

```
docs/references/
  INDEX.md                       the catalogue, one entry per document
  blastFoam_UserGuide_v6.pdf     the original file
  blastFoam_UserGuide_v6.txt     extracted text, so agents can Grep it
```

## `/ref add <path> "<what it covers>"`

1. If `docs/references/` does not exist, create it and an `INDEX.md` with the header below.
2. Copy the file into `docs/references/` (keep the original name, replace spaces with underscores). If the path is a URL, tell the user to download it first; do not fetch it.
3. If it is a PDF, extract text next to it with the same base name and `.txt`:
   - try `pdftotext -layout <pdf> <txt>`;
   - if that is missing, use Python: `import fitz; open(txt,"w",encoding="utf-8").write("\n".join(f"\n=== page {i+1} ===\n"+p.get_text() for i,p in enumerate(fitz.open(pdf))))`;
   - if `fitz` is missing, use `pypdf` the same way;
   - if none is available, say so and register the PDF without a text sidecar (the Read tool can still open PDF pages).
   Insert `=== page N ===` markers so agents can cite page numbers.
4. Skim the document (table of contents, first pages) and write the index entry. Ask the user nothing; use the description they gave plus what you saw.
5. Append to `INDEX.md`:

   ```
   ## <short id, e.g. blastfoam-guide>
   - File: blastFoam_UserGuide_v6.pdf (text: blastFoam_UserGuide_v6.txt)
   - Covers: <what the user said, plus the main chapters you saw>
   - Use for: <the kinds of tasks that must consult it, e.g. "any task that writes or edits a blastFoam case, chooses a solver, EOS or boundary condition, or post-processes blastFoam output">
   - Cite as: <how to reference it in code comments, e.g. "blastFoam User Guide v6, sec. 4.2">
   - Keywords: <10 to 20 words agents would grep for>
   ```

6. Tell the user the entry was added and which agents will now pick it up.

## `/ref list`

Print the index entries in one line each: id, file, covers.

## `/ref find <topic>`

Grep the `.txt` sidecars (and `.md` references) for the topic, show the matching document, page marker and a few lines of context. Use this when the user asks "where does the manual say X".

## `/ref check`

Verify every file named in `INDEX.md` exists, every PDF has a `.txt` sidecar, and report missing ones. Offer to extract missing sidecars.

## How agents use the index

Agents do not load whole manuals. They read `INDEX.md`, pick the entries whose "Use for" or keywords match the task, Grep the `.txt` for the relevant section, and read only those pages. When the user writes `ref: <id>` or `ref: <file>` on a task line in `TODO.md`, the planner attaches that document to the task and the implementer must consult it before writing code. Code comments cite the document and section as written in "Cite as".

## INDEX.md header

```
# Reference documents

Agents: read this file before any task. Match the task against "Use for" and "Keywords", then Grep the .txt sidecar and read only the relevant pages. Cite the document in code comments as given in "Cite as". If code and document disagree, report it; do not guess.
```
