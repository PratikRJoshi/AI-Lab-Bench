# claude-code-utils

Utilities for managing [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration across multiple projects.

## claude-merge

Merges project-level `.claude/settings.json` permission allowlists up into the global `~/.claude/settings.json`, then deletes the project-level file. This prevents approval prompts from accumulating per-project and ensures all approvals centralize to the global settings file over time.

### Setup

Add to your `~/.zshrc`:

```zsh
source /path/to/claude-code-utils/claude-merge.sh
```

Or copy the `claude-merge()` function body directly into your `~/.zshrc`.

### Usage

Run from any project root after a Claude Code session:

```zsh
$ claude-merge
```

### Example output

```
Found project settings: /your/project/.claude/settings.json
  Adding to allow: Bash(make *)
  Adding to allow: Bash(docker *)
  Skipping (exists): Bash(git *)
  Adding to allowedTools: Bash(helm *)
  Deleting /your/project/.claude/settings.json
Done. Global settings updated: /Users/yourname/.claude/settings.json
```

### Requirements

- `jq` — install via `brew install jq`
- `zsh`

## render-skill-output (Stop hook)

When a turn runs `/review`, `/code-walkthrough`, or `/describing-pr-files`, this hook takes Claude's final answer, renders it as a colored HTML page, and opens it in your browser. Pages are saved to `~/.claude/rendered-outputs/`.

The page renders Markdown in the browser with [marked](https://marked.js.org/), sanitizes it with [DOMPurify](https://github.com/cure53/DOMPurify), and uses GitHub styling plus color-coded severity headings and risk badges. These libraries load from the jsDelivr CDN; the content itself never leaves your machine.

Each page also has:

- **Light/dark themes** that follow your system setting (Monokai in dark mode), with extra code coloring for function calls, attributes, class names, and operators.
- **File links**: a file list at the top links to each file's `###` section, and each section links back.
- **Notes beside every section**: type notes or follow-up questions in the side box. They save in your browser per page. **Copy notes** puts them on the clipboard as Markdown grouped by section; **Download** saves a `.md` file.

### Answering notes in place

```zsh
# print the notes saved for a page (reads Firefox's per-file storage)
python3 ~/.claude/hooks/render-skill-output.py --read-notes ~/.claude/rendered-outputs/<page>.html

# add answers ({"<heading-id>": "<markdown>"}) to the same page
python3 ~/.claude/hooks/render-skill-output.py --answer ~/.claude/rendered-outputs/<page>.html answers.json
```

`--answer` rebuilds the page under the same path, because Firefox ties saved notes to the file path. Answers appear at the end of each section, linked from its notes box.

To render any transcript turn manually, pipe `{"transcript_path": "...", "force": true, "label": "<name>"}` into the script.

### Setup

```zsh
./install-render-hook.sh
```

This symlinks `hooks/render-skill-output.py` into `~/.claude/hooks/` and adds the Stop hook to `~/.claude/settings.json`. Running it again does nothing. Requires `jq` and `python3`.

## code-walkthrough skill

`skills/code-walkthrough/SKILL.md` is the `/code-walkthrough` skill: line-by-line or block-by-block explanations of a PR, file, or module, with what/why/how/goal for each block, plus entry points and callers, term definitions, worked examples, and the notes-answering workflow above.

```zsh
ln -s "$PWD/skills/code-walkthrough" ~/.claude/skills/code-walkthrough
```

## CLAUDE.md

A reference `CLAUDE.md` for `~/.claude/CLAUDE.md` that configures Claude Code's thinking style, coding standards, and — most notably — **output formatting with visual anchors** for long-running tasks.

The output formatting section structures Claude's responses with scannable `━━━` dividers so you can:

- **Track progress in real-time** — a `[→]` marker shows which step is active
- **Resume reading easily** — timestamped headers let you find where you left off
- **Scan quickly** — each section header describes what happened, no need to re-read content between them

Includes workflow-specific templates for feature work, debugging, and multi-file refactoring.

### Setup

Copy to your home directory:

```zsh
cp CLAUDE.md ~/.claude/CLAUDE.md
```

Or merge the sections you want into your existing `~/.claude/CLAUDE.md`.
