---
name: code-study
description: >
  Study a codebase, PR, or file end to end and keep the results as interactive HTML
  pages: a line-by-line walkthrough, an end-to-end trace with real values, in-place
  answers to the reader's notes, and a high-level overview for interview prep. Use
  when the user invokes /code-study or wants to learn code deeply and keep notes on it.
disable-model-invocation: true
---

# /code-study

One command for the whole study loop:

1. Read the code → **walkthrough** page.
2. Follow one real run through it → **flow** page.
3. The user writes questions in the notes box beside each section → **answer** them in place.
4. Condense everything into a study sheet → **overview** page that links back to the detail. Walkthrough and flow build this automatically.

Pages land in `~/.claude/rendered-outputs/` and open in the browser. They are rendered by `~/.claude/hooks/render-skill-output.py` (see `claude-code-utils/README.md`), which gives each page:
- a tab title and Source banner built from the input (`PR #4927 · service-llm-gateway — /code-study`, `<repo> — /code-study`)
- light/dark (Monokai) themes and extra code coloring
- a Contents box listing every section, and links from a file list to each file's `###` section
- a notes box beside every section, with Copy and Download buttons

## Modes

| Invocation | What it produces | How it's rendered |
|---|---|---|
| `/code-study <target>` | Walkthrough + interview overview | `--render-md`, then overview |
| `/code-study flow <target>` | End-to-end trace with real values + interview overview | `--render-md`, then overview |
| `/code-study answer <page.html>` | Answers added to an existing page | `--answer`, same file path |
| `/code-study overview <page.html> [more pages]` | Interview overview linking to the pages | `--render-md` |

Add `--no-overview` to a walkthrough or flow invocation to skip the automatic overview.

`<target>` is anything `/code-walkthrough` accepts: a PR URL or number, a file path (optionally `:L120-180`), a module or repo path, or a remote file URL.

## Mode: walkthrough (default)

Follow `~/.claude/skills/code-walkthrough/SKILL.md` in full: inputs, depth modes, output format, large-PR handling, and every rule. In particular, each file section must include:
- **Entry point and callers** with `file:line` and the quoted call
- **Terms** for every library, tool, file format, or team-specific word
- **What / Why / How / Goal alignment** for each block, quoting the code with line numbers first
- an **Example** with concrete inputs and outputs for each important block
- traced origins for settings and decisions, design alternatives, concrete names for helper objects, notes on surprising syntax, and a runnable demo for any code that contradicts its comment

Use the real file paths and section headings `### <filename>` so the page's file links and notes boxes line up.

Then [save the page and build the overview](#save-the-page-and-build-the-overview).

## Mode: flow

Trace one real execution from the entry point to the final output, step by step:

1. Start from how the user actually runs it (Makefile target, CLI, example driver). Show that code.
2. For each step, quote the exact code with line numbers, then show the **actual values** at that point: from run logs, saved outputs, S3/files, or by running the code offline (e.g. call a converter on a fixture row). Redact credentials and API keys.
3. After the happy path, add one `## Case X:` section per real failure or edge path (rejected rows, expired credentials, TLS, size limits, timeouts). For each, show how the error travels: where it is raised, where it is caught or recorded, and where it finally surfaces, with the logged message.
4. Give a short plain-English **What / Why / How** for each step. Never replace code with a conceptual description.
5. Start the page with any local, uncommitted changes in the target repo (`git status`, `git diff`) and explain them. End with a one-table summary of the whole flow and its values.

Use `## Step N.` and `## Case X:` headings so each gets its own notes box.

Then [save the page and build the overview](#save-the-page-and-build-the-overview).

## Save the page and build the overview

Walkthrough and flow end this way unless the user passed `--no-overview`:

1. Write the full page Markdown to `/tmp/code-study-<repo>.md`. Do not paste it as the final reply.
2. Render it: `python3 ~/.claude/hooks/render-skill-output.py --render-md /tmp/code-study-<repo>.md '{"command": "/code-study", "args": "<target>", "cwd": "<target repo path>"}'`. It prints the page path. Because the turn rendered its own page, the Stop hook skips it.
3. Run **Mode: overview** below on that page path. Its relative links point at the page's real file name.
4. Reply with one line per page path, nothing more.

With `--no-overview`, skip all of this and reply with the page Markdown; the Stop hook renders it.

## Mode: answer

When the user has written questions in a page's notes boxes:

1. Read them: `python3 ~/.claude/hooks/render-skill-output.py --read-notes <page.html>`. This prints `{"<heading-id>": "<note>"}` from Firefox's per-file storage. If it returns nothing, ask the user to click **Copy notes** and paste them.
2. Answer every question in each note. Apply the walkthrough rules: quote code with line numbers, real values, runnable examples, and corrections to anything earlier that turns out wrong. Use bold lines instead of Markdown headings inside answers.
3. Write `{"<heading-id>": "<markdown answer>"}` to a JSON file and run `python3 ~/.claude/hooks/render-skill-output.py --answer <page.html> <answers.json>`. This rebuilds the page at the **same path**; Firefox ties notes to the path, so never write answers to a new file.
4. Verify in headless Chrome (`--dump-dom`) that each answer block exists, then tell the user to reload. Answers appear at the end of each section, linked from its notes box.
5. Look at what the questions asked for. If they reveal a gap the walkthrough should have covered by default, propose a new rule for `code-walkthrough/SKILL.md`.

## Mode: overview

A high-level technical study sheet, for example for interview preparation:

1. Read the source pages' embedded Markdown (`<script type="text/markdown" id="src">`) and answers (`<script type="application/json" id="answers">`). Collect their section ids. The id is the heading text lowercased with every run of non-alphanumerics replaced by `-`. An answer's id is `<section-id>-answer`.
2. Build the architecture diagram with the `/archify` skill (type `architecture`, showcase quality). Keep it to one main path and at most about 8 components. Then:
   - Run `validate` until all 9 checks pass with 0 errors and 0 warnings.
   - `deliver` it to `~/.claude/rendered-outputs/<name>-architecture.html`.
   - Run `visual-check`; fix any viewport overflow by compacting vertical spacing.
   - Look at a screenshot yourself before embedding it.
3. Write Markdown with these sections:
   - a 30-second summary
   - the architecture diagram, embedded with `<iframe src="<name>-architecture.html" title="…"></iframe>` plus a link to open it full-screen. The renderer only allows iframes pointing at a local `.html` file in the same folder. If `/archify` isn't available, use an ASCII diagram in a `text` code block.
   - the main stages (where each runs, entry point, classes, output)
   - key components in one line each
   - design decisions with trade-offs
   - reliability, retries, and error codes
   - real numbers from runs
   - findings from reading the code
   - likely interview questions with crisp answers
4. After each point, link to the detail with **relative** links such as `[More](code-walkthrough-….html#job-scheduler-py)`. The page sanitizer strips `file://` links.
5. Render: `python3 ~/.claude/hooks/render-skill-output.py --render-md <file.md> '{"command": "/code-study overview", "args": "<repo path or PR URL>", "label": "Interview overview · <repo>"}'`.
6. Verify every link target exists by loading each linked page in headless Chrome and checking for `id="<anchor>"`.

## Rules

- Prefer real values over invented examples; label anything inferred as `Inferred:`.
- Never paste credentials or keys into a page; redact them from logs.
- Keep each page's headings stable once the user has taken notes on it, since notes are keyed by heading id.
- After creating or updating a PR as a result of a finding, run `/review` on it.
