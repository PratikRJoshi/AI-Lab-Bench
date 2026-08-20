# Cursor IDE settings

Snapshot of Cursor user settings so a new machine can match this one.

## Restore on a new Mac

1. Install [Cursor](https://cursor.com).
2. Clone this repo (or pull latest).
3. Run:

```bash
cd ~/AI-Lab-Bench/cursor-ide-settings
chmod +x restore.sh
./restore.sh
```

4. Reload Cursor: **Cmd+Shift+P** → `Developer: Reload Window`.

Existing `settings.json` / `keybindings.json` are copied to `*.bak.<timestamp>` first.

## What is saved

| File | Purpose |
|------|---------|
| `User/settings.json` | Editor, theme, tab colors, terminal |
| `User/keybindings.json` | Custom shortcuts |
| `extensions.txt` | Installed extensions |
| `mcp.json` | MCP server list (tokens replaced with `REPLACE_ME`) |
| `restore.sh` | Copy files + install extensions |

## Not saved (on purpose)

- Real API tokens. After restore, fill every `REPLACE_ME` in `~/.cursor/mcp.json`.
- Workspace storage, history, and crash-reporter IDs (machine-specific).

## After restore, check these paths

`settings.json` has this-machine paths. Edit them if the new Mac differs:

- `java.home`
- `java.jdt.ls.java.home`
- `claudeCode.environmentVariables` → `NODE_EXTRA_CA_CERTS`
- `falconServicesView.activeViewContextFile`

Night theme in `theme-timer` is **Dracula Theme**. If it is missing after restore, install `dracula-theme.theme-dracula`.
