# Future-aware preview validation

Validated locally on macOS with Node 24.22.1, Yarn 4.17.1, and Docker Desktop on 2026-11-23.

## Source identity

- Upstream: `actualbudget/actual`, tag `v26.11.0`, commit `1766241e3f4b3c578e424c4fa15f1eb83c0da17d`.
- Feature source head: `9874510c303c179f2d20833c77067eb7a59f961d`.
- Patch SHA-256: `6349cc006f6bdaf66b86e0ee4e56fd0be1e79dde084ad4babe7c63e71ce11351`.
- Local image: `actual-budget-future-aware:26.11.0-6349cc006f6b`.
- The complete patch applies cleanly to a separate index loaded from pinned upstream. The source working tree is clean.

## Checks completed

| Check | Result |
| --- | --- |
| Core budget, API, and sync suites | 295 passed; 2 existing property tests skipped |
| Native hold-menu component tests | 3 passed |
| Python preview safety tests | 15 passed |
| Node TCP gateway integration test | 1 passed with synthetic traffic |
| Root workspace type checking | Passed; unchanged workspace results reused where applicable |
| Source formatting and type-aware lint | Passed, including normal pre-commit checks |
| Production browser and API builds | Passed |
| Pinned patch application | Passed against clean upstream index |
| Copied-budget checks | Three final cases passed: both budgets plus a detached case with a manual hold removed |
| Financial integrity | All 14 protected tables unchanged in every copied case; all November category budgeted/spent/balance amounts match stock |
| Preview containers | Actual, Tweaks, and gateway healthy |
| Preview identity | Both ports serve the final patch marker; HTML isolation headers and Tweaks shim verified |
| Isolation | Actual/Tweaks only on an internal network; gateway has no budget-data mount; host ports bind only to localhost |
| Live installation | Original container IDs and start times unchanged; original image and configuration retained |
| Browser startup | Final build reaches its normal sign-in screen with matching app/server versions |

The primary regression failed on stock behavior before implementation. The menu/API tests also failed before their fixes. Independent review found an additional Hold API edge case; its mixed held/unheld-income regression failed before the correction and now passes in all three cases. Final review has no remaining Critical or Important findings.

## Limits

- Authenticated budget screens still require the user to sign in to the preview. Financial calculations were verified through the real engine/API on detached private copies, rather than by entering the user's password in browser automation.
- The build helper was exercised using its verified-source reuse path. Clean patch application was checked separately; a fresh-Mac installation was not tested.
- This implements future-assignment awareness. It does not promise identical YNAB results for different category allocations, credit-card payment reserve rules, or every future scenario.
- Nothing was deployed over the live installation. See [README.md](README.md) for preview and rollback commands.

Private financial outputs, copied server settings, and budget files are outside this repository.
