# Actual Budget recovery

Encrypted backups of the complete Actual server, with a one-command restore that starts Actual and Actual Budget Tweaks together on a new Mac.

This project lives in `AI-Lab-Bench/actual-budget/`. The repository and encrypted release assets are **public**, as explicitly chosen by the owner; keep the private recovery key separately in your password manager. Budget contents remain inside the encrypted archive.

## Keep this recovery key separately

Save **actual-budget-recovery-key.asc** as a file attachment in your password manager, accessible on another device. It is deliberately **absent from this repository**. Anyone with that file and an encrypted snapshot can decrypt the snapshot; the file itself has no additional passphrase. The public key in this repository can only encrypt new backups.

Keep your existing **Actual server password** too: the restored server uses the same login. GitHub CLI access and the recovery key are needed for the command below; the command signs in interactively when necessary. A downloaded encrypted snapshot can also be restored offline without GitHub.

## Restore on a new Mac: one terminal command

Copy the command below into Terminal. It installs missing tools, asks you to sign in to GitHub if needed, clones the `actual-budget/` folder of AI-Lab-Bench into a new checkout, and starts the restore. When asked, supply the path to the recovery key file exported from your password manager.

```bash
/bin/bash -c 'set -e; export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"; command -v brew >/dev/null || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; command -v gh >/dev/null || brew install gh; gh auth status --hostname github.com >/dev/null 2>&1 || gh auth login --hostname github.com --web --git-protocol https; d="$(mktemp -d "$HOME/ActualBudget-Recovery.XXXXXX")"; gh repo clone PratikRJoshi/AI-Lab-Bench "$d" -- --depth 1 --filter=blob:none --sparse; git -C "$d" sparse-checkout set actual-budget; exec /bin/bash "$d/actual-budget/restore.sh" --install-deps --open-browser'
```

Use a GitHub account for the CLI download; **PratikRJoshi** is required when publishing new backups. First-time Homebrew or Docker Desktop setup can ask for administrator approval, command line tools, or acceptance in the Docker window; this is one command with interactive setup, not an unattended installation. Docker Desktop must be supported by the new Mac's macOS version.

The default destination is `~/ActualBudget`. The command starts the `actual-budget` server and the `actual-budget-tweaks` sidecar, then opens **http://localhost:3005**. Open that URL, enter the same server address if asked, log in with the existing Actual password, and download either restored budget from its list. Actual itself remains available at **http://localhost:5006**. Both services restart automatically whenever Docker Desktop is running; enable Docker Desktop's start-at-login option if desired.

If you have already cloned the repository, open its `actual-budget/` folder and double-click **Restore Actual Budget.command**, or run:

```bash
./restore.sh --install-deps --open-browser
```

The restore refuses a nonempty destination, either existing container name, an existing Compose project for that destination, or either occupied port. To test safely alongside an existing installation:

```bash
./restore.sh --key /path/to/actual-budget-recovery-key.asc --target "$HOME/ActualBudgetTest" --container actual-budget-test --port 15006 --tweaks-port 15005
```

Use `--tweaks-port PORT` to choose a different Tweaks port. If you need Actual without Tweaks, add `--no-tweaks`; this skips the Tweaks image and port entirely and opens Actual’s own URL. By default, both pinned images must be available before restored data is written.

To use an older release, add `--release actual-budget-backup-TIMESTAMP`; to use a downloaded file, add `--archive /path/to/actual-TIMESTAMP.tar.gz.gpg`. Local restore still needs Docker, Python 3.9+ and GnuPG 2, and initially needs registry access unless the required pinned Docker images are already cached.

## Back up changes later

Before backing up, open each budget you have changed and wait for **Synced**. Browser-only changes that have not reached the server cannot be included.

On the original Mac, from the `actual-budget/` folder:

```bash
./backup.sh --publish
```

After restoring onto a new Mac, use its new container name:

```bash
./backup.sh --container actual-budget --publish
```

Without `--publish`, backups stay in the ignored `backups/` folder. With `--publish`, a new encrypted file and SHA-256 checksum are uploaded as a GitHub release; prior snapshots remain available. Restore selects the newest matching budget release and ignores releases for other projects. **This is a manual snapshot, not an automatic ongoing backup.** Only the public encryption key is required to create new snapshots. If a future backup fails, the previous release remains intact.

Actual pauses briefly while the full data folder is copied, and restarts before checking/encryption/upload. Do not edit a budget during that pause. Ordinary interruption and copy failure restart the source server; a machine crash or forced kill during the pause may require `docker start my_actual_budget_from_ynab` (or the restored container name).

## Actual Budget Tweaks is restored automatically

The one-command restore starts [Tweaks](https://github.com/aelxxs/actual-budget-tweaks) automatically. It uses the pinned Tweaks image in this repository, connects directly to Actual over the private Docker network, and publishes its port only to localhost. The sidecar has no budget-data or Docker-socket mounts. Existing backup archives remain compatible.

The command waits for both services to become healthy, then checks the proxy API and injected Tweaks scripts before reporting success. `--open-browser` opens the Tweaks address. The generated configuration remembers both image versions, container names, ports, and the Compose project name.

To manage a restored setup later, open its destination folder (normally `~/ActualBudget`):

```bash
docker compose up -d --wait
```

Use `docker compose ps` to check both services and `docker compose down` to stop them. Synced Tweaks preferences are restored with each budget. Optional visual features can be selected in Tweaks settings.

The standalone [tweaks/](./tweaks/) configuration remains available for adding Tweaks to an Actual server that is already managed separately, such as the original source Mac. It is not needed after the automatic restore.

## What is preserved

- Both active budgets, accounts, transactions, reconciled states, categories, rules, goals, saved reports, synced preferences and experimental feature flags.
- Complete server data: budget checkpoint files **and** newer incremental sync logs, server login/authentication settings, and older soft-deleted server copies.
- The exact running Actual image, recorded by immutable registry digest; the initial snapshot is Actual **26.11.0**, supporting both Apple Silicon and Intel Docker hosts. Tweaks is restored using the separately pinned image in this repository.
- Optional original import files passed with `--source-export FILE`; these are archival sources, not the current budget. They restore under `sources/`.

Actual’s built-in theme, sidebar folding and some display choices are stored only in the browser and may need to be reapplied. Tweaks saves its synced preferences with each budget; the restore starts its sidecar automatically. New device URLs, HTTPS/reverse proxies, external bank-provider accounts, Docker Desktop preferences, and the rest of your Mac are not reconstructed. The current server has a direct local Docker setup; the restored service binds only to localhost.

## Verification and recovery details

Each snapshot includes an encrypted manifest with per-file hashes, Actual version/image digest, and the active budget inventory. The tools check all SQLite databases, ZIP integrity and embedded budget databases, and require every active budget checkpoint and sync log. GnuPG protects the archive; downloaded release checksums are verified before decryption, then the manifest is checked before restoring data.

The recovery key is imported only into a temporary isolated keyring. Plaintext snapshots are held in private temporary folders and removed on normal completion or failure; deletion is not a guarantee of forensic erasure on an SSD. Keys and unencrypted data are excluded by `.gitignore`; publish only the intended code files and public key. Encrypted snapshots are publicly downloadable in this repository; the owner approved that visibility. Keep the recovery key private. Publication to a public repository requires `allow_public_snapshots: true` in `recovery.json`, which is enabled for this destination. No unencrypted financial data or private key belongs in Git.

If startup fails after data is copied, the restored files remain in the destination for diagnosis; inspect `docker logs actual-budget` and start the generated Compose setup there, rather than rerunning a restore over that directory. The source installation is never replaced by the restore tool.

Upstream documentation: [Docker installation](https://actualbudget.org/docs/install/docker/), [backup](https://actualbudget.org/docs/backup-restore/backup/), [restore](https://actualbudget.org/docs/backup-restore/restore/).
