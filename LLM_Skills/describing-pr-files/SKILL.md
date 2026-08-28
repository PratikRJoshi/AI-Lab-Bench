---
name: describing-pr-files
description: Use when the user wants one- or two-sentence per-file descriptions for a pull request, PR body, branch diff, or change summary.
---

# Describing PR Files

## Goal

Explain every file changed by the input pull request in one or two plain-English sentences.

## Workflow

1. Resolve the pull request from its URL, number, or current branch.
2. Get the authoritative changed-file list from the pull request host. For GitHub or GitHub Enterprise, prefer `gh pr view <PR> --json files`; do not rely on a stale local base branch.
3. Inspect each file's actual patch. Use repository context only when the patch alone cannot explain the change.
4. Account for every changed file exactly once.
5. Describe what changed and why it matters when the evidence establishes the reason. State uncertainty instead of guessing.

## Output

Return only one bullet per changed file:

```markdown
- `path/to/File.java`: One or two plain-English sentences describing this file's PR changes.
```

Keep implementation and test files separate. Name the behavior each test proves rather than saying only “adds tests.” Mention generated, configuration, dependency, or unrelated files accurately.

If the pull request cannot be accessed, ask for the PR diff or changed-file list.

## Quality Check

Before responding, verify:

- Every authoritative changed file appears once.
- Each bullet contains one or two sentences.
- Descriptions reflect the patch without unsupported intent.
- Wording is understandable without reading the code.
