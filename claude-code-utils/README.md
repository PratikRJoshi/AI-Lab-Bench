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
