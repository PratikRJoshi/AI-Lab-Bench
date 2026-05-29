---
name: coplan
description: Dual-model parallel planning — Claude and GPT-5.5 (1M context, extra-high reasoning) independently plan the same task, self-verify against extracted requirements, merge plans, then cross-review iteratively until both models sign off. Use when the user says "coplan", "plan with GPT", "dual plan", "parallel plan", or is starting a multi-file feature that warrants two perspectives.
user-invocable: true
argument-hint: "[task description or spec path] [--model <id>] [--review-model <id>] [--review-fallback-model <id>]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Agent
---

# /coplan — Dual-Model Parallel Planning

Two AI models tackle the same planning problem independently, verify their own work against numbered requirements, reconcile the strongest elements from each, then cross-review until the plan passes muster. Claude retains final authority throughout.

**Models:**
- Claude (this session) — deep codebase familiarity, convention awareness, sub-agent spawning
- GPT-5.5 Extra High via `cursor-agent` — 1M token context, agentic file exploration, systematic completeness

**Output folder:** `coplans/<slug>-<id>/` (per-run subfolder; durable, gitted)

---

## When to Use

- `/coplan <task description>` — plan any non-trivial implementation
- `/coplan <path/to/spec.md>` — plan from an existing spec
- `/coplan` — prompt for what to plan

## Model Selection (Max Mode supported)

Default planning model: `gpt-5.5-extra-high` (1M context, max reasoning). Default review model: `claude-opus-4-8-thinking-xhigh` (Opus 4.8 1M, extra-high thinking) — cross-provider review by default.

Override per run:
- `/coplan <task> --model <id>` — change both planning and review model
- `/coplan <task> --model <id> --review-model <id>` — separate models for plan vs review
- `/coplan <task> --review-fallback-model <id>` — use a different provider for review if the primary review model fails (recommended: pick a different family — e.g. Gemini if review-model is GPT, Opus if review-model is Gemini)

**Why provider diversity matters in review:** A different model in r2+ has no investment in the r1 critique — surfaces blind spots both Claude and the r1 reviewer share. By default the planner (`gpt-5.5-extra-high`) and reviewer (`claude-opus-4-8-thinking-xhigh`) are already cross-provider. If the Opus reviewer fails, the auto-fallback is `gpt-5.5-extra-high`; pass `--review-fallback-model gemini-3.1-pro` for a third provider.

**Common Max-mode picks** (from `cursor-agent --list-models`):
- `gpt-5.5-extra-high` — default planner. GPT-5.5, 1M context, max reasoning
- `gpt-5.5-extra-high-fast` — same model, faster scheduler
- `claude-opus-4-8-thinking-xhigh` — default reviewer. Opus 4.8 1M, extra-high thinking
- `gemini-3.1-pro` — Gemini 3.1 Pro
- `grok-4.3` — Grok 4.3, 1M

To see the live list: `cursor-agent --list-models`.

**Validation:** Before launching, validate the requested model against `cursor-agent --list-models`. If unknown, print the list and ask the user to pick.

## When NOT to Use

- Single-file changes, quick bug fixes, anything under 3 steps
- Pure code review (use `/review` or a review skill)
- Writing a product spec from scratch (use `/prd` first, then `/coplan`)

---

## Phase 1: INTAKE

### Step 1: Parse Input

If `$ARGUMENTS` is a file path → read it. If a description → use directly. If empty:

```
What should I plan? Provide:
- A task description
- A path to a spec file (e.g., docs/Releases/NNN/feature/spec.md)
- A reference to something discussed in this conversation
```

### Step 2: Parse Flags and Resolve Models

Extract `--model` and `--review-model` from `$ARGUMENTS`. Whatever remains is the task description / spec path.

```bash
# Defaults
MODEL="gpt-5.5-extra-high"
REVIEW_MODEL=""           # defaults to claude-opus-4-8-thinking-xhigh if unset
REVIEW_FALLBACK_MODEL=""  # used if review model fails mid-loop; empty = no fallback

# Pseudo-parse (skill executor handles the actual extraction):
# /coplan "build dashboard" --model claude-opus-4-8-thinking-xhigh
# /coplan spec.md --model gpt-5.5-extra-high --review-model claude-opus-4-8-thinking-xhigh
# /coplan spec.md --review-fallback-model gemini-3.1-pro
#   → MODEL/REVIEW_MODEL/REVIEW_FALLBACK_MODEL extracted accordingly.

REVIEW_MODEL="${REVIEW_MODEL:-claude-opus-4-8-thinking-xhigh}"

# If no fallback specified, pick a different-provider default to maximize
# r2 diversity. Heuristic: if review model is GPT, fall back to Gemini;
# if Claude or Gemini, fall back to GPT.
if [[ -z "$REVIEW_FALLBACK_MODEL" ]]; then
  case "$REVIEW_MODEL" in
    gpt-*)         REVIEW_FALLBACK_MODEL="gemini-3.1-pro" ;;
    claude-*)      REVIEW_FALLBACK_MODEL="gpt-5.5-extra-high" ;;
    gemini-*)      REVIEW_FALLBACK_MODEL="gpt-5.5-extra-high" ;;
    grok-*)        REVIEW_FALLBACK_MODEL="gpt-5.5-extra-high" ;;
    *)             REVIEW_FALLBACK_MODEL="" ;;
  esac
fi
```

Validate both models against the live list:

```bash
AVAILABLE=$(cursor-agent --list-models 2>/dev/null | awk '{print $1}')
echo "$AVAILABLE" | grep -qx "$MODEL" || { echo "Unknown model: $MODEL"; echo "$AVAILABLE"; exit 1; }
echo "$AVAILABLE" | grep -qx "$REVIEW_MODEL" || { echo "Unknown review model: $REVIEW_MODEL"; echo "$AVAILABLE"; exit 1; }
if [[ -n "$REVIEW_FALLBACK_MODEL" ]]; then
  echo "$AVAILABLE" | grep -qx "$REVIEW_FALLBACK_MODEL" || { echo "Unknown fallback model: $REVIEW_FALLBACK_MODEL"; echo "$AVAILABLE"; exit 1; }
fi
```

### Step 3: Generate Session ID and Slug

```bash
COPLAN_ID=$(uuidgen | tr '[:upper:]' '[:lower:]' | head -c 8)
SLUG=$(echo "<task-name>" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-' | head -c 40)
COPLAN_DIR="coplans/${SLUG}-${COPLAN_ID}"
mkdir -p "$COPLAN_DIR"
echo "Created: $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${COPLAN_DIR}/run.meta"
echo "Plan model: $MODEL" >> "${COPLAN_DIR}/run.meta"
echo "Review model: $REVIEW_MODEL" >> "${COPLAN_DIR}/run.meta"
[[ -n "$REVIEW_FALLBACK_MODEL" ]] && echo "Review fallback model: $REVIEW_FALLBACK_MODEL" >> "${COPLAN_DIR}/run.meta"
```

### Step 4: Extract Requirements

Read the task or spec. Pull every distinct requirement, feature, acceptance criterion, and constraint into a numbered checklist (R1, R2, R3...). This is the objective verification target for every gap analysis that follows.

Write to `${COPLAN_DIR}/requirements.md`.

If the task references a spec, also read linked files (VISION.md, DATA-MODEL.md, related PRDs, etc.).

---

## Phase 2: PARALLEL PLANNING

The two models work the same problem simultaneously. Claude plans in the foreground while `cursor-agent` runs GPT-5.5 in the background.

### Step 5: Launch Background Planner

`cursor-agent` is an agentic CLI — the planning model (`$MODEL`) will read files, grep, and explore on its own using the workspace. No need to pre-load context the way the original skill design assumed.

Build the prompt and write it to disk first (avoids shell escaping issues with multi-line content):

```bash
cat > "${COPLAN_DIR}/gpt-prompt.txt" <<EOF
You are a senior software architect creating an implementation plan.

TASK:
${TASK_DESCRIPTION}

REQUIREMENTS (every item must appear in your plan):
$(cat ${COPLAN_DIR}/requirements.md)

You have full filesystem access via your tools. Read CLAUDE.md, the project tree, and any files referenced in the task. Explore convention patterns (look at 2-3 similar existing features) before planning.

Create a detailed implementation plan that:
1. Lists EVERY file to create or modify, with specific changes
2. Orders steps by dependency (what must exist before what)
3. Groups related changes into logical phases
4. Covers ALL numbered requirements (R1, R2, R3...) — missing even one is a failure
5. Includes verification steps after each phase
6. Notes risks, edge cases, and rollback strategies
7. Specifies which changes can be parallelized

After writing the plan, perform a SELF-VERIFICATION:
- Walk through each requirement (R1, R2, ...) one by one
- For each, identify which plan step(s) address it
- If any requirement lacks a corresponding step, ADD it now
- Append your verification results at the end as a "Requirements Coverage" table

Output the plan as structured Markdown. Output ONLY the plan — no preamble.
EOF
```

Then launch in the background:

```bash
cursor-agent -p \
  --model "$MODEL" \
  --output-format text \
  --force \
  --workspace "${PWD}" \
  "$(cat ${COPLAN_DIR}/gpt-prompt.txt)" \
  > "${COPLAN_DIR}/gpt-plan.md" 2> "${COPLAN_DIR}/gpt-stderr.log" &

GPT_PID=$!
echo "$GPT_PID" > "${COPLAN_DIR}/gpt.pid"
```

Use `run_in_background: true` and `timeout: 600000` on the Bash call.

### Step 6: Claude Plans (Foreground)

Plan in execution mode — read files, spawn sub-agents, explore the codebase, think through edge cases. No plan-mode constraints.

Write to `${COPLAN_DIR}/claude-plan.md` using this structure:

```markdown
# Implementation Plan: [Task Name]

## Overview
[1-3 sentences]

## Phases

### Phase N: [Name]
**Files:**
- `path/to/file.ts` — [create|modify] — [what changes]

**Steps:**
1. [Specific action]
2. [Specific action]

**Verify:** [How to confirm this phase is correct]

**Depends on:** [Phase N-1 | none]

## Requirements Coverage
- R1: [requirement] → Phase N, Step M
- R2: [requirement] → Phase N, Step M
[Every requirement must map. If any is uncovered, add a phase.]

## Risks & Edge Cases
- [risk] → [mitigation]

## Parallelization Notes
[Which phases/steps can run concurrently]
```

### Step 7: Self-Verification (Claude's Plan)

Re-read `${COPLAN_DIR}/requirements.md`. Check each Rn against the plan. Add missing work. Update the Requirements Coverage section. **Not optional** — this single pass produces most of the quality uplift.

---

## Phase 3: RECONCILIATION

### Step 8: Collect Background Plan

```bash
wait $(cat "${COPLAN_DIR}/gpt.pid") 2>/dev/null
```

If the file is empty or stderr shows an error, fall back to Claude-only with double verification (see Rule 7).

### Step 9: Merge Plans

Read both plans side-by-side and produce a unified version at `${COPLAN_DIR}/unified-plan.md`.

**Merge rules:**
- Both agree → keep (high confidence)
- Different approaches → prefer Claude's (knows the codebase)
- GPT-5.5 covers a requirement Claude missed → add it
- GPT-5.5 identifies a risk Claude missed → add it
- Conflicts with project CLAUDE.md → Claude's approach wins

### Step 10: Post-Merge Verification

Re-read `requirements.md`. Confirm every Rn has coverage in the unified plan. Fix any gaps introduced during the merge.

Print to terminal:

```
## Collaborative Plan — Summary

**Claude contributed:** [N phases, key decisions]
**GPT-5.5 contributed:** [items Claude missed, additional risks found]
**Requirements coverage:** [X/Y — should be Y/Y]

[Path to unified plan]
```

---

## Phase 4: CROSS-REVIEW (Iterative GPT-5.5 Refinement)

This is the inline replacement for `/GPT-review`. Up to 3 rounds of GPT-5.5 reviewing the unified plan against the requirements, with Claude addressing feedback each round.

### Step 11: Review Loop

For round in 1..3:

```bash
ROUND=1
cat > "${COPLAN_DIR}/review-prompt-r${ROUND}.txt" <<EOF
You are reviewing an implementation plan for completeness, correctness, and risk.

REQUIREMENTS (must all be covered):
$(cat ${COPLAN_DIR}/requirements.md)

PLAN:
$(cat ${COPLAN_DIR}/unified-plan.md)

Validate against the actual filesystem (read referenced files to confirm they exist or that paths make sense in this codebase).

Output a structured review:
1. VERDICT: PASS or REVISE
2. REQUIREMENTS GAPS: any Rn not adequately covered (cite step numbers)
3. CORRECTNESS ISSUES: incorrect file paths, wrong dependencies, missing imports
4. RISK GAPS: edge cases or rollback paths not addressed
5. CONCRETE SUGGESTIONS: specific changes the plan should adopt
6. CONFIDENCE: 0-100

If VERDICT is PASS with confidence ≥ 85, the plan is approved.
EOF

cursor-agent -p \
  --model "$REVIEW_MODEL" \
  --output-format text \
  --force \
  --workspace "${PWD}" \
  "$(cat ${COPLAN_DIR}/review-prompt-r${ROUND}.txt)" \
  > "${COPLAN_DIR}/review-r${ROUND}.md" 2>&1

# Detect cursor-agent failures. NOTE: cursor-agent writes connection errors
# to STDOUT (mixed with normal output), not stderr — exit code is still 0.
# Grep stdout for known failure signatures.
if grep -qE 'Connection lost|\[unavailable\] Error|Retry attempt 3' "${COPLAN_DIR}/review-r${ROUND}.md"; then
  echo "Review model $REVIEW_MODEL failed (connection/availability error)."
  if [[ -n "$REVIEW_FALLBACK_MODEL" ]] && [[ "$REVIEW_FALLBACK_MODEL" != "$REVIEW_MODEL" ]]; then
    echo "Retrying with --review-fallback-model: $REVIEW_FALLBACK_MODEL"
    cursor-agent -p \
      --model "$REVIEW_FALLBACK_MODEL" \
      --output-format text \
      --force \
      --workspace "${PWD}" \
      "$(cat ${COPLAN_DIR}/review-prompt-r${ROUND}.txt)" \
      > "${COPLAN_DIR}/review-r${ROUND}.md" 2>&1
    # Record the actual model that produced this round's review
    echo "Round ${ROUND} review model: $REVIEW_FALLBACK_MODEL (fallback)" >> "${COPLAN_DIR}/run.meta"
  else
    echo "No fallback model configured. Skipping round ${ROUND}; declaring last good plan as final."
    break
  fi
fi
```

After each round:

1. Read `review-r${ROUND}.md`
2. If VERDICT is PASS and confidence ≥ 85 → exit loop
3. Otherwise, Claude updates `unified-plan.md` to address each suggestion **unless** it conflicts with:
   - Explicit user requirements
   - Project CLAUDE.md conventions
   - An architectural decision already justified in the plan
4. Note skipped suggestions with rationale in `${COPLAN_DIR}/skipped-suggestions.md`
5. Increment ROUND, repeat

After max rounds (3), proceed even if not approved — note the unresolved items in the final summary.

**Claude's veto power:** GPT-5.5 advises, it does not decide. Skip any suggestion that contradicts user requirements or project conventions. Document why.

---

## Phase 5: OUTPUT

### Step 12: Save Final Plan

Copy the approved unified plan to a final, permanent location:

```bash
cp "${COPLAN_DIR}/unified-plan.md" "${COPLAN_DIR}/PLAN.md"
```

Optionally also write to a project-canonical location if the task references a spec:
- If spec lives at `docs/Releases/NNN/feature/spec.md` → also write `docs/Releases/NNN/feature/plan.md`
- Otherwise leave the plan in `coplans/${SLUG}-${COPLAN_ID}/PLAN.md` only

Print:

```
## Plan Approved

**Rounds:** 1 parallel + N review
**Models:** Claude + GPT-5.5 Extra High (plan) / Opus 4.8 1M xHigh Thinking (review)
**Requirements coverage:** X/X (100%)
**GPT-5.5 verdict:** PASS (confidence: N%)

Plan: coplans/<slug>-<id>/PLAN.md

Ready to implement. Suggested next: spawn an implementation agent or break into tasks.
```

### Step 13: Model Assessment

Print to terminal only (do NOT write to PLAN.md). 6-8 lines, specific, no inflation.

```
## Model Assessment

**Claude strengths on this task:** [specific examples from this run]
**Claude gaps:** [specific examples]

**GPT-5.5 strengths on this task:** [specific examples]
**GPT-5.5 gaps:** [specific examples]

**Where they agreed / diverged:** [key disagreements + which won + why]

**Net value of collaboration:** [one honest sentence — did GPT-5.5 materially improve the plan?]
```

### Step 14: Cleanup (Optional)

Keep the run folder by default — it's the audit trail. Offer to clean if user asks:

```bash
# rm -rf "${COPLAN_DIR}"  # only if user explicitly requests
```

The `coplans/` folder should be gitignored at the repo root so individual runs don't pollute commits, but PLAN.md copies in `docs/` are tracked.

---

## Rules

1. **Never use plan mode.** Plan in execution mode — Claude reads files, spawns sub-agents, explores freely.

2. **Self-verification is mandatory** after every planning phase. Re-read `requirements.md` from disk, not from memory.

3. **Model defaults:** planner `gpt-5.5-extra-high` (1M context, max reasoning); reviewer `claude-opus-4-8-thinking-xhigh` (Opus 4.8 1M, extra-high thinking) for cross-provider review. User can override either with `--model <id>` and `--review-model <id>`. Validate against `cursor-agent --list-models` before launching. Max-mode-class options include `gpt-5.5-extra-high`, `claude-opus-4-8-thinking-xhigh`, `gemini-3.1-pro`, `grok-4.3`.

4. **Claude has veto power.** GPT-5.5 advises. Skip its suggestions when they conflict with user requirements or project CLAUDE.md.

5. **Per-run folder under `coplans/`** is durable. Each run gets `coplans/<slug>-<id>/` with prompts, both plans, reviews, and final PLAN.md. This is the audit trail.

6. **Output feeds downstream.** Use the structured phase / file-list / dependency / verification format so the plan can be split into executable tasks later.

7. **If `cursor-agent` is unavailable or auth fails**, fall back to Claude-only planning with two verification passes. Notify the user:
   ```
   GPT-5.5 unreachable. Run `cursor-agent login` to enable dual-model planning.
   Continuing with Claude-only (double-verified).
   ```

8. **If the task is trivial** (< 3 files, < 3 steps), tell the user `/coplan` is overkill and plan inline.

9. **Show your work.** The user sees both plans, the merge summary, and each review round. Transparency builds trust.

10. **Persist `requirements.md`** as the source of truth. Every gap analysis reads it from disk.

11. **Provider-diversity for review.** When a review round fails (connection / unavailable / rate-limit), retry with `$REVIEW_FALLBACK_MODEL` from a different provider family. A different-family fallback also serves as adversarial diversity in r2+ — the second reviewer has no investment in the first critique. Recommended pairings: GPT ↔ Gemini, Claude ↔ GPT.

12. **Failure detection via stdout, not stderr.** `cursor-agent` writes `Connection lost`, `[unavailable] Error`, and `Retry attempt N` to **stdout** (mixed with normal output) while exiting 0. Detect failures with `grep -qE 'Connection lost|\[unavailable\] Error|Retry attempt 3'` on the output file — never trust empty stderr or the exit code as proof of success.

---

## Files Produced (per run)

```
coplans/<slug>-<id>/
├── run.meta              # Created timestamp + plan/review/fallback models used
├── requirements.md       # numbered requirements (R1, R2, ...)
├── gpt-prompt.txt        # the prompt sent to the background planner
├── gpt-plan.md           # background model's plan
├── gpt-stderr.log        # cursor-agent stderr (often empty — failures land in gpt-plan.md)
├── claude-plan.md        # Claude's plan
├── unified-plan.md       # merged plan (working copy through review rounds)
├── review-prompt-r1.txt  # review prompts per round
├── review-r1.md          # review verdicts per round (may use fallback model)
├── skipped-suggestions.md  # vetoed review suggestions + reasons
└── PLAN.md               # final approved plan
```
