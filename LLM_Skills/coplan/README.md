# /coplan — Dual-Model Parallel Planning

Two AI models plan the same problem independently, verify against numbered requirements, reconcile, then cross-review iteratively until both sign off. Claude has final authority.

## Why

- **Execution-mode planning** beats Claude Code's plan mode by ~15 points on internal benchmarks
- **Mandatory self-verification** against a numbered requirements checklist closes most remaining gaps
- **Two models in parallel** catches things one model alone would miss (different architectures see different blind spots)
- **Iterative cross-review** converges on a stronger plan than either model produces solo

## How It Works

```
Phase 1  INTAKE          → parse args, extract requirements (R1, R2, R3...)
Phase 2  PARALLEL PLAN   → GPT-5.5 (background) + Claude (foreground), both self-verify
Phase 3  RECONCILIATION  → merge plans, post-merge gap check
Phase 4  CROSS-REVIEW    → up to 3 GPT review rounds with Claude addressing feedback
Phase 5  OUTPUT          → save final PLAN.md + model assessment
```

Each run produces a per-run audit folder under `coplans/<slug>-<id>/` with both plans, all review rounds, vetoed suggestions, and the final approved PLAN.md.

## Usage

```bash
# Default (gpt-5.5-extra-high for both planning and review)
/coplan "build inventory allocation dashboard"
/coplan docs/Releases/260/inventory-allocation/spec.md

# Override the model — both phases
/coplan "task" --model claude-4.6-opus-max-thinking

# Different model for plan vs review (diversity check)
/coplan "task" --model gpt-5.5-extra-high --review-model claude-4.6-opus-max

# Provider-failover for review rounds (recommended for resilience)
/coplan "task" --review-fallback-model gemini-3.1-pro
```

## Provider Failover (review)

If the review model hits a connection or availability error mid-loop, the skill auto-retries r{N} with `--review-fallback-model`. By default this is set to a different provider family (GPT ↔ Gemini, Claude ↔ GPT) for two reasons:

1. **Resilience.** When one provider is rate-limited or down, the loop survives.
2. **Adversarial diversity.** A fresh-eyes reviewer in r2+ has no investment in the r1 critique — surfaces blind spots both Claude and r1 share. (Validated in this skill's own smoke test: r1 GPT-5.5 found two real bugs Claude missed; r2 Gemini 3.1 Pro independently confirmed the fixes with PASS confidence 95.)

**Failure detection:** `cursor-agent` writes connection errors to **stdout** (mixed with normal output) while exiting 0. The skill greps for `Connection lost`, `[unavailable] Error`, and `Retry attempt 3` to detect failures — never trusts empty stderr or the exit code.

## Models (Max Mode supported)

Default: `gpt-5.5-extra-high` (1M context, max reasoning).

Common Max-mode picks (live list: `cursor-agent --list-models`):

| Model | Context | Notes |
|-------|---------|-------|
| `gpt-5.5-extra-high` | 1M | default; max reasoning |
| `gpt-5.5-extra-high-fast` | 1M | same model, faster scheduler |
| `gemini-3.1-pro` | 1M | Gemini 3.1 Pro |
| `grok-4.3` | 1M | Grok 4.3 |

**Validation:** the skill checks the requested model against the live list before launching. If unknown, it prints the list and stops.

## When to Use

- Multi-file features (3+ files, 3+ steps)
- Implementations crossing architectural layers
- Spec-driven work where coverage of every requirement matters
- Anytime you want a second perspective before committing to an approach

## When NOT to Use

- Single-file changes or quick bug fixes (overkill)
- Pure code review (use `/review`)
- Writing a PRD from scratch (use `/prd` first, then `/coplan`)

## Output (per run)

```
coplans/<slug>-<id>/
├── run.meta              # Created timestamp + plan/review/fallback model used
├── requirements.md       # numbered requirements (R1, R2, ...)
├── gpt-prompt.txt        # prompt sent to background planner
├── gpt-plan.md           # background model's plan
├── gpt-stderr.log        # errors (if any)
├── claude-plan.md        # Claude's plan
├── unified-plan.md       # merged plan (working copy through review)
├── review-prompt-r1.txt  # review prompts per round
├── review-r1.md          # review verdicts per round
├── skipped-suggestions.md  # vetoed suggestions + rationale
└── PLAN.md               # final approved plan
```

`coplans/*/` is gitignored — only `coplans/.gitkeep` is tracked. Final plans get copied to `docs/...` if the source was a spec there.

## Claude's Veto Power

GPT-5.5 (or whichever review model) advises. It does not decide. Claude skips suggestions that contradict:
- Explicit user requirements
- Project CLAUDE.md conventions
- An architectural decision already justified in the plan

Vetoes are logged in `skipped-suggestions.md` with the rationale.

## Requirements

- `cursor-agent` installed and authenticated (`cursor-agent login`). The skill validates this and falls back to Claude-only with double verification if `cursor-agent` is unreachable.
- No API keys needed — `cursor-agent` uses your Cursor SSO session.

## Implementation Notes

The skill uses `cursor-agent -p` (non-interactive) which is itself an agent — the model reads files, greps, and explores the workspace on its own. We don't pre-load context the way the original design assumed; the 1M window is filled by the model's own exploration, scoped to whatever the prompt + requirements direct it to read.

Background launches use `run_in_background: true` with `timeout: 600000` so Claude can plan in parallel without blocking.
