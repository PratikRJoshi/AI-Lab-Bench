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

The owner explicitly approved publicly storing the encrypted snapshots in AI-Lab-Bench. The project is under `actual-budget/`; snapshots use the `actual-budget-backup-` release prefix. The existing recovery key and ciphertext are unchanged. A fresh sparse checkout from AI-Lab-Bench selected and downloaded the namespaced release, decrypted it and restored both active budgets on port **15008**. All **16 file hashes** matched, and both the restored server and original server returned HTTP 200. The test container and plaintext test data were removed. Old-repository deletion is awaiting GitHub delete_repo authorization.

## Actual Budget Tweaks — 2026-11-23

- Tweaks **0.1.111** is pinned to `ghcr.io/aelxxs/abt-sidecar@sha256:a2c6c7cbbbd57f6181a665f6d7f1f45fcc05c710b7d92768b68f7291aedca9d4`; the downloaded image reports that version and runs as the unprivileged `node` user.
- The Docker Compose configuration validates. The running sidecar is healthy, restarts automatically with Docker, and binds port **3005** only to **127.0.0.1**. It has no host-directory, budget-data or Docker-socket mounts.
- The six Tweaks scripts/styles are injected once and return HTTP 200. Actual’s public `/info` and `/account/needs-bootstrap` responses match through the proxy. Cross-origin isolation headers are preserved and the service worker receives the updated shell revision.
- The browser reaches the normal Actual login page at `http://localhost:3005/login`, showing app/server version **26.11.0**, with no browser console errors. Signed-in budget features were not exercised during this installation check.
- The existing Actual container retained its ID, image and start time. A read-only budget check confirmed the previously verified November funding totals were preserved.

The sidecar is an optional service; the existing recovery command starts Actual only. Start Tweaks separately using `tweaks/README.md` after restoring. These checks cover the existing Docker Desktop setup, not a factory-fresh Mac.
