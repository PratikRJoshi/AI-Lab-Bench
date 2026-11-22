# Recovery validation

Validated on the source Mac on 2026-11-22, using Actual 26.11.0 and an immutable multi-architecture Docker image.

- Full cold snapshot passed all checks: **2 active budgets**, **7 server/sync SQLite databases**, **6 ZIP budget checkpoints** and their embedded SQLite databases.
- Decryption and restoration into a separate folder and container on port **15006** succeeded. The source container on port **5006** also returned HTTP 200 afterward and retained its existing configuration.
- The isolated restored server returned HTTP 200 and listed both expected active budgets in its account database. Every checkpoint and incremental sync-log file remained byte-identical to the snapshot after startup.
- Real incorrect-key and corrupted-ciphertext restore attempts failed before creating destination data.
- All **9 unit tests** passed, covering unsafe archives, changed/missing/extra snapshot files, nonempty destinations, source restart on copy/interrupt failure, key mismatch and cached-image recovery; all shell scripts passed syntax checks.
- Real stopped-container mount inspection confirmed that spaces, dollar signs, apostrophes, # and backslashes in restore paths are preserved correctly.
- A separate read-only code review found no remaining Critical or Important issues after the cached-image and path fixes.
- The remote payload was audited to contain only intended code, documentation, configuration and the **public** encryption key. The private key is a separate local file with mode 0600.
- A fresh GitHub clone successfully downloaded the latest encrypted release, verified its checksum, decrypted it and started a second isolated restore on port **15007**. All **16 manifest file hashes** matched after startup, including the server authentication database and both archived import files. Both active budgets were present, and the live source and restored server each returned HTTP 200.
- Both temporary test containers and their plaintext restored data were removed after validation; the original server remains running. The encrypted archive and checksum are available in the [encrypted release](https://github.com/PratikRJoshi/AI-Lab-Bench/releases/tag/actual-budget-backup-20261122T040031874465Z).

The clean-macOS Homebrew/Docker first-run installation has not been exercised on a factory-fresh Mac; it can require administrator and Docker first-run prompts. Browser-local display preferences are outside the server snapshot. No claim is made that browser changes which have not synced to the server are included.

## Repository move

The owner explicitly approved publicly storing the encrypted snapshots in AI-Lab-Bench. The project is under `actual-budget/`; snapshots use the `actual-budget-backup-` release prefix. The existing recovery key and ciphertext are unchanged. The standalone repository will be deleted only after verification of the destination.
