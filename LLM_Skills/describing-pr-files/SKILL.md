---
name: describing-pr-files
description: Use when the user wants one- or two-sentence per-file descriptions for a pull request, PR body, branch diff, or change summary.
---

# Describing PR Files

## Goal

Explain every file changed by the input pull request in one or two plain-English sentences, laid out so a reviewer can skim large PRs without scrolling.

## Workflow

1. Resolve the pull request from its URL, number, or current branch.
2. Get the authoritative changed-file list from the pull request host. For GitHub or GitHub Enterprise, prefer `gh pr view <PR> --json files`; do not rely on a stale local base branch.
3. Inspect each file's actual patch. Use repository context only when the patch alone cannot explain the change.
4. Group each file into ONE of the following categories, in this order:
   - **Implementation** — production source that changes behavior.
   - **Tests** — anything under `__tests__/`, `*.test.*`, `*_test.*`, `spec/`.
   - **Configuration / Infra** — `.tf`, `.yaml`, `.yml`, `Dockerfile`, CI files, `.github/`, `helm/`, `falcon/`, `resources/`, `.env*`.
   - **Scripts / Tooling** — `.sh`, `.mjs` in `scripts/`, `bin/`, `cli/` when they are entry points (not library code).
   - **Docs** — `.md`, `.rst`, `.adoc`, `README*`, `CHANGELOG*`, `docs/`.
   - **Dependencies** — `package.json`, `package-lock.json`, `go.mod`, `pom.xml`, `Gemfile*`, `requirements*.txt`, `Cargo.*`, `poetry.lock`.
   - **Generated / Other** — snapshots, goldfiles, `.pb.go`, build artifacts, anything that does not fit above.
5. Under each non-empty category, render a Markdown table with three columns: `#`, `File`, `Change (1–2 sentences)`.
6. Account for every changed file exactly once. If a file crosses categories, pick the most useful one for a reviewer and note the crossover in the sentence.
7. Describe what changed and why it matters when the evidence establishes the reason. State uncertainty instead of guessing.

## Output

Start with a one-line header:

```markdown
**PR #<number>** — <total-files> files changed across <count> categories.
```

Then, for each non-empty category, in the order listed under Workflow step 4:

```markdown
### <Category>

| # | File | Change |
|---|------|--------|
| 1 | `path/to/File.java` | One or two plain-English sentences describing this file's PR changes. |
| 2 | `path/to/Other.java` | ... |
```

Rules for the table:

- Number files starting at `1` within each category (not globally).
- Wrap the `File` cell in backticks. Use the full repo-relative path when it is short (≤ ~60 chars); otherwise shorten it so the `Change` column stays readable: drop the shared directory prefix and elide the long common middle with `…` (e.g. `prod/…core_tenant_id-core_prod_00DXXXXXXXXXXXXXXX.yaml`), keeping the distinguishing tail. Add one line under the tables stating the dropped prefix / what `…` stands for.
- Never add a `Category` column; categories are the `###` headings, one small table each.
- Keep each `Change` cell to one or two sentences. No trailing period-less fragments.
- Name the behavior each test proves rather than saying only "adds tests." For example: "Proves that a `limit:0` counter wins selection over a normal counter and returns 429."
- Mention generated, configuration, dependency, or unrelated files accurately — say "renovate bump", "goldfile regeneration", "expiry extension", etc., not "misc change."
- If a single file has both a real code change AND a mechanical (e.g. import re-order, whitespace) change, describe only the real change.

Skip any category that has zero files.

If the pull request cannot be accessed, ask for the PR diff or changed-file list before writing any tables.

## Quality Check

Before responding, verify:

- Every authoritative changed file appears exactly once, in exactly one category.
- Each row's `Change` cell contains one or two sentences.
- Category order in the output matches Workflow step 4.
- Descriptions reflect the patch without unsupported intent.
- Wording is understandable without reading the code.
- No empty categories were rendered.
