# Future-aware Actual Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make the branch's envelope-budget To Budget include future commitments automatically, with an isolated preview and a stock-image rollback path.

**Architecture:** Extend the existing effective hold with a derived, backwards-only future commitment. The original forward accounting chain releases that effective hold next month as it does today. Keep persisted financial records unchanged and keep the preview on private copied data.

**Tech Stack:** Actual v26.11.0, TypeScript, Vitest, Yarn 4.17.1, Node 24, Docker Compose, Python standard library for preview orchestration.

**Spec:** `docs/superpowers/specs/2026-11-23-actual-future-aware-totals-design.md`

## Global Constraints

- No in-app toggle in the initial branch.
- No live budget, container, Compose configuration, restore-default, or database-schema changes.
- Current Docker image remains the rollback image.
- No financial data, credentials, private snapshots, or private keys in Git or published artifacts.
- Run Yarn commands from the upstream source root; run `yarn typecheck` before committing the source patch.

## Review Focus

- A saved manual/income hold overlaps a future assignment: reserve once, not twice (Task 1).
- A future month exceeds present cash: preserve the future deficit and do not count future income as current cash (Task 1).
- The previously final budget month gains a successor or a category is regrouped: refresh existing backwards dependencies (Task 1).
- Cached stock-version cells load into the preview: recalculate the new reservation and preserve all financial records (Task 2).
- A preview path, port, or Compose project points at the live installation: refuse startup before copying data or creating containers (Task 3).

## Task 1: Future reservation calculation

**Upstream files:**
- Modify `packages/loot-core/src/server/budget/envelope.ts` and `base.ts`.
- Modify `packages/loot-core/src/server/api.ts` to report the effective hold.
- Create `packages/loot-core/src/server/budget/future-assignments.test.ts`.

**Interfaces:** `existing-buffered-selected`, `future-commitments`, and `future-buffered` are calculated cells. Existing consumers retain `to-budget` and `buffered-selected`.

- [x] Write an integration test with 10,000 cents November income and 10,000 cents December assignment; assert both months To Budget are 0, November effective hold is 10,000, and stored budget rows are unchanged.
- [x] Run it against stock source and observe the expected 10,000-vs-0 failure.
- [x] Implement the backwards commitment graph and effective-hold maximum from the spec, rebuilding links over all created months when the horizon changes.
- [x] Add tests for releasing/changing future assignments, multiple later months/year transition, negative assignments, manual and income holds, insufficient money, future income, current/future overspending, and horizon extension.
- [x] Run focused tests and existing budget suites; explain and update only assertions intentionally changed by the new behavior.

## Task 2: Consumers, copied-budget checks, production build

**Upstream files:**
- Modify `packages/desktop-client/src/components/budget/envelope/budgetsummary/ToBudgetMenu.tsx`.
- Add a targeted menu test following existing component test conventions.
- Add a local verification harness outside Git for private copied-budget comparisons.

**Interfaces:** UI/API/Tweaks consume the same effective cells from Task 1; existing manual and income hold controls retain their original scope.

- [x] Write a failing menu test: a future-only effective hold must not offer Disable current auto hold; income-based automatic holds still offer it.
- [x] Restrict that control to actual income-based holds; leave unrelated UI layout unchanged.
- [x] Verify cache reload and sync/edit invalidation; API effective `forNextMonth` equals the UI reservation.
- [x] On private copies of Mocha and Milk, compare stock and modified outputs and hashes of protected financial tables. Verify Mocha November becomes 0 with its existing December assignments; do not copy YNAB's differing allocations.
- [x] Run required type checking, focused lint/tests, and production browser/API builds.
- [x] Commit the upstream source branch with the required `[AI]` prefix and export a pinned patch into Task 3's tracking directory.

## Task 3: Reproducible preview and rollback

**Tracking files:** Create `actual-budget/future-aware/{README.md,build.sh,preview.py,compose.yaml,Dockerfile,actual.patch,upstream.json,test_preview.py}`. Private build directories, source checkouts and copied data stay outside Git.

**Interfaces:** Build produces a named local custom image from the pinned release and patch. Preview accepts a separate private destination, binds localhost 15006/13005 by default, and uses a distinct Compose project/internal network.

- [x] Write failing preview guard tests for live/overlapping data paths, live/colliding ports, and occupied container/project identities.
- [x] Implement pinned-source build and copy/start/stop commands. Copy SQLite databases through the backup API; check source file stability during the copy. Never stop the live containers.
- [x] Keep preview networking internal so copied server settings cannot initiate external bank sync. Publish only localhost ports.
- [x] Build the custom image; start the private preview with a separate Tweaks container. Verify health, assets, source-version marker, and the copy identities.
- [x] Inspect the preview through supported browser tools and verify the intended total using copied/synthetic budgets as available.
- [x] Document exact preview, stop and original-image rollback commands; record limitations and nonfinancial validation results.
- [x] Run a fresh whole-branch code review, fix important findings, rerun affected checks, and commit the tracking branch. Leave the live version unchanged for the user's preview.
