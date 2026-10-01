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

### Setup

```zsh
./install-render-hook.sh
```

This symlinks `hooks/render-skill-output.py` into `~/.claude/hooks/` and adds the Stop hook to `~/.claude/settings.json`. Running it again does nothing. Requires `jq` and `python3`.

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
