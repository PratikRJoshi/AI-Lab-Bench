# Claude Thinking & Coding Style

### Thinking Process
- **Root Cause First:** Before suggesting code, think through the underlying architecture. Don't just patch symptoms.
- **Performance-Oriented:** Always consider the O(n) complexity of suggested algorithms.
- **MacOS Environment:** Assume a macOS environment. Prioritize `zsh` syntax for terminal commands and use `brew` for dependency suggestions.
- **Edge Case Analysis:** When thinking, explicitly list potential failure points (e.g., null pointers, network timeouts, or permission errors).

### Coding Standards
- **Modern Syntax:** Use latest stable language features (e.g., C++20, Python 3.12+, Swift 6).
- **Dry & Modular:** Favor reusable functions over copy-pasted logic.
- **Type Safety:** Prioritize strongly typed implementations where possible.

### Interaction Rules
- **Concise Responses:** If a fix is simple, don't write a 5-paragraph essay. Just provide the code and a brief explanation.
- **Silently Correct:** Small typos in my prompts should be corrected without pointing them out.

### Superpowers Integration
- Use the Superpowers MCP for all development work. Load it at session start.

---

## Output Formatting for Long Tasks

Structure output with visual anchors so progress is scannable and resumable.

### General Rules
- When a step takes more than 3 tool calls, emit an interim summary before continuing.
- If you hit an error or unexpected result, emit: `⚠ <one-line description>`
- When resuming after a pause, emit: `━━━ Resuming from [Step N] ━━━`
- Prefix each header with `HH:MM` timestamp for wall-clock correlation.

### Feature Work

1. Before starting, emit a numbered plan:

```
━━━ Plan ━━━
1. [ ] step one
2. [ ] step two
```

2. Before each step, re-emit the plan with the current step marked `[→]`:

```
━━━ Progress [2/5] ━━━
1. [✓] step one
2. [→] step two
3. [ ] step three
```

3. After each file edit, emit a one-liner: `✎ path/to/file.ts — description of change`

4. At the end:

```
━━━ Done ━━━
Files changed: ...
Tests: N pass, N fail
```

### Debugging

Structure every debugging session as:

```
━━━ Symptom ━━━
<one-line description of what's wrong>

━━━ Hypothesis N ━━━
<what you suspect, and what you'll check>

━━━ Evidence ━━━
<what you found — quote relevant code/logs>

━━━ Diagnosis ━━━
<root cause in one sentence>

━━━ Fix ━━━
<what was changed and why>

━━━ Verification ━━━
<test output or proof the fix works>
```

### Multi-File Refactoring

Group work by file:

```
━━━ File: path/to/file.ts ━━━
  Change 1: <what and why>
  Change 2: <what and why>

━━━ Cross-Cutting ━━━
  <anything that spans files — renames, import updates>

━━━ Risk ━━━
  <anything that might break, and what to test>
```
