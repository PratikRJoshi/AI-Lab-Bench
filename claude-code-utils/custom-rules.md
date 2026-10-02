# Custom Rules

My own additions, imported by the global `CLAUDE.md`. Make personal rule changes here instead of editing `CLAUDE.md` directly.

### Coding Standards
- **Minimal Comments:** Keep code comments either nonexistent or as short and concise as possible, so they don't blow up the overall code or file.

### Interaction Rules
- **Use dropdown for choice questions:** When a question has a small, well-defined set of answers (yes/no, or 2–4 clear options like commit/push confirmations, "which approach"), present them via `AskUserQuestion` (clickable buttons) instead of asking me to type. Skip only when the answer is truly open-ended or I've explicitly asked to type.
- **PR review-comment replies use `layman`:** Every reply to a PR review comment must use the `layman` skill (plain English, ≤60 words, jargon-free) — even when layman is otherwise off for the session.
- **SFCI plugin / MCP recovery:** If any SFCI plugins or MCP servers hit issues, automatically try to fix them — restart the AI suite as the first step.
- **Auto-review after PR create/update:** After creating a new PR or updating an existing PR, always run the `/review` skill automatically.
- **Evidence/validation tracker pages:** When asked for an HTML page to track testing or validation of a change, start from `templates/evidence-tracker-template.html` in this repo (`~/Salesforce/AI-Lab-Bench/claude-code-utils/`): an overview table with anchor links, one status-colored card per step, checks with short tags, and evidence as short labeled rows with stable IDs (E4.1…). Put on-hold routes in a collapsed `<details>`. Keep updating the same file and reopen it in the browser.
- **Significant-change learning pass:** When significant changes are being reviewed or made to any code, offer to run `/code-walkthrough` and `/mattpocock-skills:grilling` — ask the user if they want to go over both, and run them only on confirmation.
