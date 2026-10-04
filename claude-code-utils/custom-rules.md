# Custom Rules

My own additions, imported by the global `CLAUDE.md`. Make personal rule changes here instead of editing `CLAUDE.md` directly.

### Prerequisite Skills
Install these before relying on the rules below.

| Skill | Used by | Source / install |
|---|---|---|
| `layman` | PR review-comment replies, debugging responses | This repo: symlink `skills/layman` → `~/.claude/skills/layman` |
| `code-walkthrough` | Significant-change learning pass | This repo: symlink `skills/code-walkthrough` → `~/.claude/skills/code-walkthrough` |
| `review` | Auto-review after PR create/update | Local clone of `mattpocock-skills`: symlink `skills/in-progress/review` → `~/.claude/skills/review` |
| `mattpocock-skills:grilling` | Significant-change learning pass | `/plugin install mattpocock-skills@claude-plugins-official` |
| `i-have-adhd:i-have-adhd` | Debugging responses (next steps) | `/plugin marketplace add ayghri/i-have-adhd`, then `/plugin install i-have-adhd@i-have-adhd`. User-invoked only. |

### Coding Standards
- **Minimal Comments:** Keep code comments either nonexistent or as short and concise as possible, so they don't blow up the overall code or file.

### Interaction Rules
- **Use dropdown for choice questions:** When a question has a small, well-defined set of answers (yes/no, or 2–4 clear options like commit/push confirmations, "which approach"), present them via `AskUserQuestion` (clickable buttons) instead of asking me to type. Skip only when the answer is truly open-ended or I've explicitly asked to type.
- **PR review-comment replies use `layman`:** Every reply to a PR review comment must use the `layman` skill (plain English, ≤60 words, jargon-free) — even when layman is otherwise off for the session.
- **SFCI plugin / MCP recovery:** If any SFCI plugins or MCP servers hit issues, automatically try to fix them — restart the AI suite as the first step.
- **Auto-review after PR create/update:** After creating a new PR or updating an existing PR, always run the `/review` skill automatically.
- **Evidence/validation tracker pages:** When asked for an HTML page to track testing or validation of a change, start from `templates/evidence-tracker-template.html` in this repo (`~/Salesforce/AI-Lab-Bench/claude-code-utils/`): an overview table with anchor links, one status-colored card per step, checks with short tags, and evidence as short labeled rows with stable IDs (E4.1…). Put on-hold routes in a collapsed `<details>`. Keep updating the same file and reopen it in the browser.
- **Debugging error responses:** Whenever I share an error message, stack trace, Splunk logs, or PagerDuty/Slack messages to debug an error, structure the reply in this order:
  1. **What the error is** — plain-English explanation using the `layman` skill.
  2. **Root cause** — the actual underlying cause, not the symptom.
  3. **Relevant stack trace lines** — quote only the lines from the logs that matter.
  4. **Next steps / possible fixes** — only after 1–3, written using the `i-have-adhd:i-have-adhd` skill.
- **Significant-change learning pass:** When significant changes are being reviewed or made to any code, offer to run `/code-walkthrough` and `/mattpocock-skills:grilling` — ask the user if they want to go over both, and run them only on confirmation.
