---
name: code-walkthrough
description: >
  Teach code line by line, file by file, and important block by important
  block for a pull request, file, or module (local or remote). Use when the
  user wants to learn what code does, why it does it, how it tries, and how
  it achieves the overall change goal — or invokes /code-walkthrough.
disable-model-invocation: true
---

## Purpose (author's intent)

Given a pull request, a particular file, or a module in a GitHub repository or codebase (either remote or locally), I would like to learn line by line, file by file, and important code block by important code block for the code that is present, to understand:
- what it does
- why it does what it does
- how it tries to do it
- how it achieves the overall goal of the change

Every walkthrough response must land these four lenses on every non-trivial block.

## Inputs

The skill accepts one of the following as the target:

* **PR URL or PR number** — for GitHub.com, use `gh pr view <n>` + `gh pr diff <n>`. For internal GitHub Enterprise (`git.soma.salesforce.com`, `github.com`-EMU), prefix with `GH_HOST=<host> gh ...`. Prefer the git-soma / git-emu MCP tools when available.
* **Single file path** — local absolute path or a `https://...blob/...` URL. Use `Read` for local, `WebFetch` for public raw URLs, `mcp__plugin_git-soma__get_file_contents` / `mcp__plugin_git-emu__get_file_contents` for internal Enterprise URLs.
* **Module / directory path** — enumerate with `Glob` or `ls`; walk files individually in significance order.
* **Line range** — `path/file.py:L120-180` — read only that slice via `Read` with `offset` / `limit`.

For repositories the current working directory does not belong to, prefer `WebFetch` or the appropriate MCP tool over cloning.

## Depth Modes

Explicit mode selection: `/code-walkthrough [mode] <target>`.

* `line-by-line` (default) — every non-trivial line explained.
* `block-by-block` — logical chunks (function, if-branch, config block) explained.
* `overview` — file-level summary only, no line-level detail.

If the user does not specify a mode and the target is > 300 changed lines or > 15 changed files, default to `block-by-block` and say so.

## Output Format

Always in this order:

1. **Overall goal** — one paragraph. What the PR / file / module is trying to achieve. For PRs, quote the PR title + one sentence from the description; do not invent motive not present in the source.
2. **File-by-file table of contents** (only for PRs and modules) — one line per file:
   `path/to/file — <one-sentence purpose>`
   Skipped files listed here with the reason (`skipped: lockfile`, `skipped: generated`, `skipped: binary`, `skipped: minified`).
3. **Per-file walkthrough** — each file gets:
   * A `### <filename>` header.
   * A one-line "what this file exists for".
   * Block-by-block explanations. Each block is a fenced code excerpt **with line numbers**, followed by four short paragraphs:
     * **What** — literal behavior of the code.
     * **Why** — reason from PR description, commit message, or nearby comments. If not present, mark as "inferred".
     * **How** — mechanism (data structures, control flow, library APIs used).
     * **Goal alignment** — how this block advances the overall goal from section 1.
4. **Cross-cutting notes** — patterns, invariants, gotchas spanning multiple files.
5. **Open questions / follow-ups** — anything the walkthrough surfaced that the reader should verify with the author.

### Large-PR handling

If the PR has > 15 changed files: default to top-N-by-significance (`N = 10`). Rank by (a) non-generated + non-lockfile, (b) domain code over config, (c) net line-count churn. List the deferred files under the TOC with `[deferred — request with /code-walkthrough <file>]`. Continue with `/code-walkthrough continue` to walk the next batch.

## Rules

* **Quote-before-explain.** Always paste the fenced excerpt with line numbers first, then the four-lens paragraphs. No paraphrase-only explanations.
* **No fabricated intent.** If the "why" is not in the code, commit message, PR description, or a nearby comment, prefix it with `Inferred:`.
* **No silent skips.** Every file the walkthrough does not cover is listed in the TOC with an explicit reason.
* **PR walkthroughs use the diff.** Give context lines only when the reader needs them to understand a change. Do not walk unchanged files unless the user asks.
* **Cite external types / library APIs** by canonical docs URL when the API's behavior matters (e.g. Spring `@ServiceActivator`, React `useEffect`).
* **Generated / binary / minified / lockfile handling.** Name the file. Add `skipped: <reason>`. Do not attempt line-by-line.
* **Language-agnostic.** The four-lens pattern applies across Python, Java, TypeScript, Go, Rust, Terraform, YAML. The example below is Python for brevity; the shape is the same.

## Non-Goals

* Not a code reviewer — defer bug / security / style critique to `/review`.
* Not a test generator.
* Not a refactor tool.
* Not a bug hunter — the walkthrough may surface an oddity, but it does not propose a fix.

## Persistence

Active every response once triggered. Do NOT revert to default style after a long turn, a tool result, or a follow-up ("go deeper on the auth block", "explain the loop again"). Stay active until the user says `stop walkthrough`, `disable walkthrough`, `normal mode`, or `resume default`. Re-enable with `/code-walkthrough` or "walk me through".

## Instruction Priority

1. **User's explicit instructions** — highest priority.
2. **Repo-local guidance** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`).
3. **This skill's rules.**
4. **Default assistant style.**

Example: if the repo's `CLAUDE.md` forbids reading generated / vendored files, respect that — list them as `skipped: policy` in the TOC and do not open them.

## Example

**Target:** the following 12-line function.

````python
# src/lib/rate_limit.py
 12  def allow(bucket: str, cost: int = 1) -> bool:
 13      now = time.monotonic()
 14      state = _buckets.setdefault(bucket, {"tokens": MAX, "ts": now})
 15      elapsed = now - state["ts"]
 16      state["tokens"] = min(MAX, state["tokens"] + elapsed * REFILL_PER_SEC)
 17      state["ts"] = now
 18      if state["tokens"] < cost:
 19          return False
 20      state["tokens"] -= cost
 21      return True
````

**What.** Token-bucket admission check for a named `bucket`. Returns `True` when the caller has enough tokens for `cost`, `False` otherwise. Mutates in-place.

**Why.** PR description: "Add per-tenant rate limiting to the ingestion endpoint." The choice of token bucket over fixed-window is stated in the design doc linked in the PR.

**How.** Lazy state init on first hit (line 14). Refill formula on lines 15–16: elapsed seconds × per-second refill rate, capped at `MAX`. Check-then-decrement on lines 18–20 avoids allowing a request that would overdraw the bucket.

**Goal alignment.** This is the core admission primitive the PR's overall goal depends on. The endpoint decorator higher up calls `allow(tenant_id)` before doing any work.

The same shape applies to a Java `@RestController` handler or a TS React hook — quote the excerpt, then What / Why / How / Goal alignment.
