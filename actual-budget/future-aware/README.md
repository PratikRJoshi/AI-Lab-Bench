# Future-aware To Budget preview

This branch automatically reserves currently available money that is already assigned in later months. It keeps Actual's existing category assignments, balances, transactions, targets, and saved holds unchanged. There is no initial in-app toggle; use the separate preview build to try the behavior.

The preview runs alongside the stock installation. **Keep using `http://localhost:3005` for real budgeting.** The preview at `http://localhost:13005` has its own private data copy. Edits in the preview do not update the live installation.

## What changes

- Envelope budgets reserve the uncovered portion of future commitments automatically.
- Existing manual and income holds overlap rather than double-count the reservation.
- Removing a future assignment releases its automatic reservation.
- Future shortfalls remain visible in the month that lacks funding. Future income does not become current money.
- The native UI, API, and Tweaks use the same effective To Budget and hold values.
- Tracking budgets and the database schema remain unchanged.

The implementation changes future-assignment awareness. It does not recreate YNAB's separate credit-card payment reserves or change differing saved category plans.

## Build

Requirements: Docker Desktop running, Git, Python 3, and Node.js 24 (Node 22.18+ is supported by the pinned upstream release). The build uses vendored Yarn 4.17.1 and the immutable upstream dependency lockfile.

From the AI-Lab-Bench repository root, choose a **new** build directory:

```bash
bash actual-budget/future-aware/build.sh --work-dir "$HOME/ActualBudget/future-aware-build"
```

The script downloads the exact source commit in `upstream.json`, applies `actual.patch`, runs workspace type checking, builds the browser application, and overlays only its built frontend on the pinned stock server image. It never reads budget data. The image name and patch hash are saved in the build directory's `build-result.json`.

For development, `--source-dir /absolute/path/to/actual-checkout` reuses a checkout only when its complete diff matches the tracked patch and it has no untracked files.

## Start a private preview

From the repository root:

```bash
actual_preview_image="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$HOME/ActualBudget/future-aware-build/build-result.json")"
python3 actual-budget/future-aware/preview.py start \
  --source-data "$HOME/ActualBudget/data" \
  --destination "$HOME/ActualBudget/future-aware-preview" \
  --image "$actual_preview_image"
```

Open `http://localhost:13005` and sign in with the existing Actual server password. Enter it only in the browser; the scripts do not request it or read credentials. The direct preview server is at `http://localhost:15006`.

The helper refuses the live ports, overlapping data paths, existing destinations, and occupied preview projects. It copies committed SQLite state through SQLite's backup API, includes WAL transactions, checks database integrity, and retries if the source changes during copying. The copy is private local plaintext, like the live data directory; do not publish it or add it to Git.

The copied Actual server and Tweaks run only on an internal Docker network. A separate gateway, with no budget-data mount, forwards the two localhost ports to fixed destinations. Copied server settings cannot initiate external bank sync from the preview server. The live containers are not stopped, recreated, or reconfigured.

## Stop, inspect, or resume

```bash
python3 actual-budget/future-aware/preview.py status --destination "$HOME/ActualBudget/future-aware-preview"
python3 actual-budget/future-aware/preview.py stop --destination "$HOME/ActualBudget/future-aware-preview"
python3 actual-budget/future-aware/preview.py resume --destination "$HOME/ActualBudget/future-aware-preview"
```

Stopping retains the private data copy. If startup fails after containers were created, run `stop` before `resume`. Use a new destination to take a fresh snapshot.

## Rollback

For this isolated preview, rollback is simply the `stop` command above and returning to `http://localhost:3005`. The stock installation, restore defaults, and live data were never replaced.

If this patch is later deployed over the live application, restore the original image recorded in `upstream.json` and use **Settings → Reset budget cache** after reopening each budget. Stock spreadsheet cache keys do not encode calculation-code versions; resetting avoids retaining calculated preview totals after switching versions. A Git branch switch alone does not change a running Docker container.

## Validation

See [VALIDATION.md](VALIDATION.md) for the tested source/image identity, completed checks, and remaining limits.

Run the preview safety tests:

```bash
python3 -m unittest discover -s actual-budget/future-aware -p 'test_*.py' -v
node --test actual-budget/future-aware/test_gateway.cjs
```

The patch includes real spreadsheet tests for future assignments, multiple months, year transitions, overlapping/manual/income holds, negative assignments, overspending, future income, cache rehydration, and distant assignments arriving through sync. It also tests the API reservation and native menu behavior. Private copied-budget checks compare both stock and modified engines and verify protected financial tables and category amounts remain identical.

No financial exports, credentials, private keys, copied server data, or financial test results belong in this directory. Keep those outside Git.
