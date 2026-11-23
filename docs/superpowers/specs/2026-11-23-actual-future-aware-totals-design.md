# Future-aware Actual Budget totals

## Intent and agreed approach

The user approved a separate feature branch and preview build on 2026-11-23, after discussing a YNAB-like total that accounts for assignments in later months. The current Docker image must remain available for rollback. There is no in-app toggle in the initial branch. The preview must not use the live server's data directory or write to either live budget.

This document records that approved approach and the implementation choices below. It does not authorize deployment over the live instance or publication of budget data.

## Scope

- Start from Actual v26.11.0, the installed application version.
- Automatically reserve current available money that is already committed in later months of an envelope budget.
- Keep account balances, transactions, category assignments, category balances, targets, and persisted hold values unchanged.
- Use Actual's existing effective-hold and To Budget calculations so the native UI, API, mobile view, and Actual Budget Tweaks consume consistent totals.
- Keep tracking budgets unchanged. No database schema changes or migrations.
- Test a separate build with synthetic cases and private copies of Mocha Bear and Milk Bear.
- Track the source patch, reproducible preview build, verification, and rollback instructions in AI-Lab-Bench on `codex/actual-future-aware-totals`.

## Approaches considered

1. **Manual Hold for next month:** existing supported behavior, but requires manual updates as assignments change.
2. **Replace the displayed number only:** small patch, but would leave templates, menus, and the API using a different amount. Rejected for inconsistent behavior.
3. **Derived automatic future reservation:** selected implementation. Extend the existing hold calculation without storing new allocations or replacing the accounting ledger. The separate branch provides the initial version boundary instead of a feature toggle.

This implements future-assignment awareness, not every YNAB rule. YNAB's separate credit-card payment reserves and differences between the two budgets' saved category plans are outside scope.

## Calculation

Keep the existing monthly accounting chain:

`available before hold = income + prior month To Budget + prior month effective hold - prior overspending - current assignments`

The current month must reserve enough for the peak commitment in later months, without counting future income as money available now. Later negative assignments may release category money; an earlier commitment must still be funded before that release happens.

For each month, build a backwards-only `future-commitments` dependency:

`future commitment = max(0, next month assignments + max(next month manual hold, next month future commitment))`

The backward link includes only a later month’s persisted manual hold. It excludes later income-based holds (which belong to that future income) and this new future-assignment hold, avoiding a circular dependency with the forward accounting chain. In the current month, **existing hold** retains the original manual-or-income selection.

The final month in the calculated range has no future commitment. When the range extends, recreate the backwards links so the old final month sees the new assignments. Calculated budget bounds must include all saved future assignments.

`extra needed = max(future commitment - max(existing hold, 0), 0)`

`extra available = max(available before hold - existing hold, 0)`

`future hold = min(extra needed, extra available)`

`effective hold = existing hold + future hold`

This equals taking the maximum of the existing hold and the affordable future reservation for ordinary positive holds, while preserving negative income holds after reversals. Only the uncovered portion is added, so holds are not double counted. Use this effective hold in the existing To Budget and next-month carry calculations.

If commitments exceed money available, reserve only the available money. The shortfall then appears as a negative To Budget in the first month that cannot fund its assignments. Do not make future income inflate today's available amount. Existing manual-hold overbudgeting must remain visible.

## User-visible behavior

Example: November has 100 available and December has 100 assigned. November shows 0 To Budget and 100 held for the next month; December still shows 0. Removing December's assignment releases November's reservation automatically. No saved budget amount changes.

The explicit Hold action must add its requested amount above the current effective reservation, so an additional hold is not swallowed by an overlapping automatic reservation.

The native hold menu must not offer to disable an income-based automatic hold when the reservation is solely from future assignments. The existing effective hold summary must reflect the derived amount. API `forNextMonth` must report the effective reservation consistently with the UI.

Actual Budget Tweaks already reads `to-budget` and `buffered-selected` directly. Retaining those effective cells avoids a second calculation in the sidecar.

## Verification

- Current and multiple later-month assignments; January/year transitions.
- Unassigning later money, negative later assignments, and extending the budget horizon.
- Manual and income-based holds, including partial and overlapping holds.
- Current and future overspending, insufficient funds, and future-dated income.
- Cold and cached loads, editing later assignments, and sync-driven invalidation.
- Native UI/menu/API and Tweaks totals agree; tracking budgets are unchanged.
- Copied Mocha November is 0 after reserving its existing December assignments; category balances and stored records remain identical.
- Compare copied Milk results against its own saved future plan rather than assuming it has the same allocations.
- Run repository-required type checking and appropriate tests; build the production frontend and Docker image.

## Preview and rollback

Build a versioned custom image from the pinned upstream source and tracked patch. Run it on separate localhost ports with a private copied data directory and a separate Tweaks container. Never mount the live data directory into the preview.

Do not overwrite the existing stock image, live Compose configuration, or restore defaults. Provide one-command preview start/stop and explicit stock-image rollback instructions. A Git branch switch alone does not switch a running Docker container. The preview uses a separate browser origin, so its browser cache is independent from the live app. If a custom image is ever deployed on the live origin and later rolled back, use Settings → Reset budget cache after restoring the stock image; stock cache keys do not encode calculation-version changes.

A future rollout can update restore defaults after preview validation. Private budget copies and financial test results stay outside Git; only synthetic fixtures, source code, scripts, and nonfinancial validation metadata may be committed.
