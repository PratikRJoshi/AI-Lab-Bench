# cursor-skills-status

Cursor extension that shows the agent skills used for the current prompt in the status bar (Cursor's counterpart to `statusline-skills.py`). It reads the newest transcript under `~/.cursor/projects/<workspace>/agent-transcripts/` and detects skills that are inlined into the prompt (`Skill Name: …`) or that the agent reads (`…/skills/<name>/SKILL.md`).

Install:

```bash
cursor --install-extension cursor-skills-status-0.1.0.vsix --force
```

Then run **Developer: Reload Window**.
