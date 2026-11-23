# Actual Budget Tweaks — optional local sidecar

Open **http://localhost:3005** for Actual with Tweaks. The existing Actual server continues on port 5006. Tweaks uses the same server, login and budgets. Enter your existing Actual password in the browser if this new address asks you to sign in.

The sidecar uses the container name `actual-budget-tweaks`, runs as the image’s `node` user, restarts automatically when Docker is running, and publishes port 3005 only on this Mac’s loopback address. It has no budget-data, host-directory or Docker-socket mounts. It reaches the already-running server through Docker Desktop’s `host.docker.internal:5006` address.

Use Tweaks’ settings within the app to choose optional themes and features. This installation does not enable optional financial actions or change budget allocations. Use the sidecar address without also enabling the Tweaks browser extension for that address, as the project recommends.

The image is pinned to an immutable digest for the release installed on 23 November 2026:

```
ghcr.io/aelxxs/abt-sidecar@sha256:a2c6c7cbbbd57f6181a665f6d7f1f45fcc05c710b7d92768b68f7291aedca9d4
```

Actual is managed separately; this compose file starts only Tweaks. This setup was verified with Actual 26.11.0 and Tweaks 0.1.111 on Docker Desktop for Apple Silicon macOS. The recovery tools in the parent folder restore Actual and Tweaks together by default. This standalone file is only for adding Tweaks to an existing, separately managed Actual server; use the generated root Compose setup after a restore.

## Start, check, stop

Start Actual on the Mac’s port 5006 first. From this folder:

```bash
docker compose up -d
docker compose ps
docker compose logs --tail 30
docker compose down
```

Stopping or removing this sidecar leaves the Actual server available at http://localhost:5006. Restart the sidecar with `docker compose up -d`.

The compose file needs a running Actual server on the Mac’s port 5006. If you change that port later, update `ACTUAL_ORIGIN` in `compose.yaml` and recreate only the sidecar. To update Tweaks, choose a release, pull its official image, record its immutable digest in `compose.yaml`, then run `docker compose up -d` again.

Upstream instructions: https://github.com/aelxxs/actual-budget-tweaks#installation and https://abt.alexis.lol/self-hosting/.
