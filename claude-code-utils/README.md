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
