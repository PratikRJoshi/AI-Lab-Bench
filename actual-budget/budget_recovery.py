#!/usr/bin/env python3
"""Encrypted cold backups and non-destructive restoration of an Actual server."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
TWEAKS_IMAGE = "ghcr.io/aelxxs/abt-sidecar@sha256:a2c6c7cbbbd57f6181a665f6d7f1f45fcc05c710b7d92768b68f7291aedca9d4"
IMAGE_PATTERN = r"(?:actualbudget/actual-server|ghcr.io/actualbudget/actual)@sha256:[0-9a-f]{64}"


class RecoveryError(Exception):
    pass


def run(args, **kwargs):
    result = subprocess.run([str(a) for a in args], text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RecoveryError(f"{args[0]} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def require(*programs):
    for program in programs:
        if shutil.which(program) is None:
            raise RecoveryError(f"Missing {program}; see README.md for installation.")


def config():
    return json.loads((ROOT / "recovery.json").read_text())


def validate_publish_repository(cfg):
    remote = json.loads(run(["gh", "repo", "view", cfg["repository"], "--json", "visibility"]))
    if remote["visibility"] != "PRIVATE" and not cfg.get("allow_public_snapshots", False):
        raise RecoveryError("Public encrypted snapshots require explicit allow_public_snapshots approval in recovery.json.")


def latest_budget_release(cfg):
    # This shared repository can have releases for other projects.
    tags = run(["gh", "api", "--paginate", f"repos/{cfg['repository']}/releases?per_page=100",
                "--jq", ".[] | select(.draft == false and .prerelease == false) | .tag_name"]).splitlines()
    prefix = cfg.get("release_tag_prefix", "backup-")
    matching = [tag for tag in tags if re.fullmatch(re.escape(prefix) + r"\d{8}T\d{12}Z", tag)]
    tag = max(matching, default=None)
    if tag is None:
        raise RecoveryError(f"No published budget snapshot with prefix {prefix!r} was found.")
    return tag


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@contextmanager
def keyring():
    # Never import recovery keys into the user's everyday GPG keyring.
    with tempfile.TemporaryDirectory(prefix="actual-gpg-", dir="/tmp") as folder:
        home = Path(folder)
        home.chmod(0o700)
        try:
            yield ["gpg", "--homedir", str(home), "--batch", "--no-tty"]
        finally:
            subprocess.run(["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def import_key(gpg, path, fingerprint, secret=False):
    run(gpg + ["--import", str(path)])
    listing = run(gpg + ["--with-colons", "--list-secret-keys" if secret else "--list-keys"])
    fingerprints = [line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:")]
    if fingerprint not in fingerprints:
        raise RecoveryError("This recovery key does not match this backup repository.")


def sqlite_check(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        result = db.execute("PRAGMA integrity_check").fetchall()
    if result != [("ok",)]:
        raise RecoveryError(f"SQLite integrity check failed: {path.name}")


def inspect_data(data):
    if not (data / "server-files/account.sqlite").is_file():
        raise RecoveryError("The snapshot has no Actual account database.")
    databases = sorted(data.rglob("*.sqlite"))
    for path in databases:
        sqlite_check(path)
    account = data / "server-files/account.sqlite"
    with sqlite3.connect(account.as_uri() + "?mode=ro", uri=True) as db:
        budgets = db.execute("SELECT id, name, group_id FROM files WHERE deleted = 0").fetchall()
    if not budgets:
        raise RecoveryError("The snapshot has no active budgets.")
    for file_id, _, group_id in budgets:
        if not (data / f"user-files/file-{file_id}.blob").is_file():
            raise RecoveryError("An active budget checkpoint is missing.")
        if not (data / f"user-files/group-{group_id}.sqlite").is_file():
            raise RecoveryError("An active budget sync log is missing.")
    blobs = sorted(data.glob("user-files/*.blob"))
    for path in blobs:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None or "db.sqlite" not in archive.namelist():
                raise RecoveryError(f"Invalid budget checkpoint: {path.name}")
            with tempfile.TemporaryDirectory(prefix="actual-db-") as folder:
                db_path = Path(folder) / "db.sqlite"
                with archive.open("db.sqlite") as source, db_path.open("wb") as dest:
                    shutil.copyfileobj(source, dest)
                sqlite_check(db_path)
    return {"sqlite_databases": len(databases), "budget_checkpoints": len(blobs),
            "active_budgets": [{"id": row[0], "name": row[1]} for row in budgets]}


def file_manifest(folder):
    result = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise RecoveryError("Backup source contains a link or special file.")
        if path.is_file() and path != folder / "manifest.json":
            result[path.relative_to(folder).as_posix()] = {
                "sha256": sha256(path), "size": path.stat().st_size}
    return result


def verify_snapshot(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("format") != 1 or not re.fullmatch(IMAGE_PATTERN, manifest.get("image", "")):
        raise RecoveryError("Unsupported snapshot format or image reference.")
    if file_manifest(folder) != manifest["files"]:
        raise RecoveryError("Snapshot file hashes or file list do not match the manifest.")
    checks = inspect_data(folder / "data")
    if checks != manifest["checks"]:
        raise RecoveryError("Snapshot database checks do not match the manifest.")
    return manifest


def safe_extract(archive_path, destination):
    # Extract regular files ourselves: no links, traversal, device files or duplicate names.
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = set()
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or not name.parts
                    or member.name in names or not (member.isfile() or member.isdir())
                    or name.parts[0] not in ("data", "sources", "manifest.json")):
                raise RecoveryError("Unsafe or unexpected path in snapshot archive.")
            names.add(member.name)
        for member in members:
            path = destination / member.name
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, path.open("xb") as dest:
                    shutil.copyfileobj(source, dest)
                path.chmod(0o600)


def container_info(name):
    return json.loads(run(["docker", "inspect", name]))[0]


def copy_cold_snapshot(name, source, destination):
    # Ctrl-C/SIGTERM during copying must still bring the original server back up.
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(_signum, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, terminate)
    try:
        try:
            run(["docker", "stop", "--time", "30", name])
            if container_info(name)["State"]["Running"]:
                raise RecoveryError("Actual did not stop; refusing an inconsistent copy.")
            shutil.copytree(source, destination, symlinks=True)
        finally:
            run(["docker", "start", name])
    finally:
        signal.signal(signal.SIGTERM, previous)


def backup(args):
    cfg = config()
    require("docker", "gpg", "gpgconf")
    if args.publish:
        require("gh")
        validate_publish_repository(cfg)
    info = container_info(args.container)
    if not info["State"]["Running"]:
        raise RecoveryError("Start the Actual container before taking a backup.")
    mounts = [m for m in info["Mounts"] if m["Destination"] == "/data" and m["Type"] == "bind"]
    if len(mounts) != 1:
        raise RecoveryError("Expected exactly one bind mount at /data.")
    source = Path(mounts[0]["Source"]).resolve()
    images = json.loads(run(["docker", "image", "inspect", info["Image"]]))[0]
    image = next((i for i in images.get("RepoDigests", []) if re.fullmatch(IMAGE_PATTERN, i)), None)
    if image is None:
        raise RecoveryError("The running image has no immutable official registry digest.")
    version = run(["docker", "exec", args.container, "node", "-p", "require('/app/package.json').version"]).strip()
    output_dir = args.output.expanduser().resolve()
    # A backup inside /data could recursively include itself in later snapshots.
    if output_dir == source or source in output_dir.parents:
        raise RecoveryError("The encrypted backup output must be outside the server data folder.")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    tag = cfg.get("release_tag_prefix", "backup-") + stamp
    encrypted = output_dir / f"actual-{stamp}.tar.gz.gpg"
    with tempfile.TemporaryDirectory(prefix="actual-backup-") as folder, keyring() as gpg:
        temp = Path(folder)
        import_key(gpg, ROOT / "recovery-public-key.asc", cfg["key_fingerprint"])
        snapshot = temp / "snapshot"
        snapshot.mkdir()
        print("Stopping Actual briefly to copy a consistent snapshot...", flush=True)
        copy_cold_snapshot(args.container, source, snapshot / "data")
        print("Original Actual server restarted. Checking the snapshot...", flush=True)
        for export in args.source_export:
            export = export.expanduser().resolve()
            extras = snapshot / "sources"
            extras.mkdir(exist_ok=True)
            shutil.copyfile(export, extras / export.name)
        checks = inspect_data(snapshot / "data")
        manifest = {"format": 1, "created_utc": stamp, "image": image, "version": version,
                    "checks": checks, "files": file_manifest(snapshot)}
        (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        verify_snapshot(snapshot)
        archive = temp / "snapshot.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for path in sorted(snapshot.iterdir()):
                tar.add(path, arcname=path.name)
        run(gpg + ["--trust-model", "always", "--recipient", cfg["key_fingerprint"],
                   "--cipher-algo", "AES256", "--compress-algo", "none", "--output",
                   str(encrypted), "--encrypt", str(archive)])
    encrypted.chmod(0o600)
    checksum = encrypted.with_name(encrypted.name + ".sha256")
    checksum.write_text(f"{sha256(encrypted)}  {encrypted.name}\n")
    if args.publish:
        run(["gh", "release", "create", tag, str(encrypted), str(checksum),
             "--repo", cfg["repository"], "--title", f"Encrypted Actual snapshot {stamp}",
             "--notes", "Full encrypted server snapshot. Restore with actual-budget/restore.sh and your separately stored recovery key.",
             "--latest=false"])
        print(f"Uploaded encrypted snapshot: https://github.com/{cfg['repository']}/releases/tag/{tag}")
    print(f"Encrypted backup: {encrypted}")
    print(f"Verified {len(checks['active_budgets'])} active budgets, {checks['sqlite_databases']} SQLite databases and {checks['budget_checkpoints']} budget checkpoints.")


def restore_project_name(target):
    return "actual-recovery-" + hashlib.sha256(str(Path(target).resolve()).encode()).hexdigest()[:12]


def check_target(target, name, port, tweaks_port=None):
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise RecoveryError(f"Refusing to overwrite a nonempty destination: {target}")
    ports = [(port, "--port")]
    names = [name]
    if tweaks_port is not None:
        if tweaks_port == port:
            raise RecoveryError("Actual and Tweaks must use different ports.")
        ports.append((tweaks_port, "--tweaks-port"))
        names.append(name + "-tweaks")
    # Inspect failure can mean daemon/access failure, not an available name.
    run(["docker", "info", "--format", "{{.ServerVersion}}"])
    rows = run(["docker", "ps", "--all", "--format",
                '{{.Names}}\t{{.Label "com.docker.compose.project"}}']).splitlines()
    existing = [row.split("\t", 1)[0] for row in rows]
    project = restore_project_name(target)
    if any(row.partition("\t")[2] == project for row in rows):
        raise RecoveryError(f"Compose project {project} already exists; use a different --target.")
    for container in names:
        if container in existing:
            raise RecoveryError(f"Container {container} already exists; choose a different --container.")
    for number, option in ports:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", number))
            except OSError as error:
                raise RecoveryError(f"Port {number} is already in use; choose {option}.") from error


def compose_env(manifest, target, name, port, tweaks_port=3005, with_tweaks=True):
    return {"ACTUAL_IMAGE": manifest["image"], "ACTUAL_DATA_DIR": str(target / "data"),
            "ACTUAL_CONTAINER": name, "ACTUAL_PORT": str(port),
            "ABT_IMAGE": TWEAKS_IMAGE, "ABT_CONTAINER": name + "-tweaks",
            "ABT_PORT": str(tweaks_port), "COMPOSE_PROFILES": "tweaks" if with_tweaks else "",
            "COMPOSE_PROJECT_NAME": restore_project_name(target)}


def ensure_image(image):
    try:
        run(["docker", "image", "inspect", "--format", "{{.Id}}", image])
    except RecoveryError:
        # A cached image permits offline restoration; an inaccessible daemon does not.
        run(["docker", "info", "--format", "{{.ServerVersion}}"])
        run(["docker", "pull", image])


def verify_restored_services(port, tweaks_port=None):
    def get(url):
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status != 200:
                raise RecoveryError(f"Service returned HTTP {response.status}: {url}")
            return response.headers.get("Content-Type", ""), response.read()

    _, actual_info = get(f"http://127.0.0.1:{port}/info")
    info = json.loads(actual_info)
    if not info.get("build", {}).get("version"):
        raise RecoveryError("Actual did not return server version information.")
    if tweaks_port is not None:
        base = f"http://127.0.0.1:{tweaks_port}"
        _, proxied_info = get(base + "/info")
        if json.loads(proxied_info) != info:
            raise RecoveryError("Tweaks is not proxying the restored Actual instance.")
        content_type, shim = get(base + "/abt/browser-shim.js")
        _, html = get(base + "/")
        if "javascript" not in content_type or not shim or b"/abt/browser-shim.js" not in html:
            raise RecoveryError("Tweaks scripts were not loaded by the restored app.")


def restore(args):
    cfg = config()
    require("docker", "gpg", "gpgconf")
    run(["docker", "compose", "version"])
    target = args.target.expanduser().resolve()
    with_tweaks = not args.no_tweaks
    tweaks_port = args.tweaks_port if with_tweaks else None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.container):
        raise RecoveryError("Invalid container name.")
    check_target(target, args.container, args.port, tweaks_port)
    key = args.key
    if key is None:
        key = Path(input("Path to the recovery key file saved from your password manager: ").strip().strip('\"'))
    key = key.expanduser().resolve()
    if not key.is_file():
        raise RecoveryError("Recovery key file not found.")
    with tempfile.TemporaryDirectory(prefix="actual-restore-") as folder, keyring() as gpg:
        temp = Path(folder)
        import_key(gpg, key, cfg["key_fingerprint"], secret=True)
        if args.archive:
            encrypted = args.archive.expanduser().resolve()
        else:
            require("gh")
            command = ["gh", "release", "download", args.release or latest_budget_release(cfg)]
            command += ["--repo", cfg["repository"], "--pattern", "*.tar.gz.gpg*", "--dir", str(temp)]
            run(command)
            candidates = list(temp.glob("*.tar.gz.gpg"))
            if len(candidates) != 1:
                raise RecoveryError("Expected exactly one encrypted archive in the release.")
            encrypted = candidates[0]
            checksum = encrypted.with_name(encrypted.name + ".sha256")
            if not checksum.is_file() or checksum.read_text().split()[0] != sha256(encrypted):
                raise RecoveryError("Downloaded archive checksum does not match.")
        decrypted = temp / "snapshot.tar.gz"
        run(gpg + ["--output", str(decrypted), "--decrypt", str(encrypted)])
        snapshot = temp / "snapshot"
        snapshot.mkdir()
        safe_extract(decrypted, snapshot)
        manifest = verify_snapshot(snapshot)
        # Obtain the exact server version before writing any restored data.
        ensure_image(manifest["image"])
        if with_tweaks:
            ensure_image(TWEAKS_IMAGE)
        check_target(target, args.container, args.port, tweaks_port)
        target.mkdir(parents=True, exist_ok=True)
        target.chmod(0o700)
        shutil.copytree(snapshot / "data", target / "data")
        if (snapshot / "sources").exists():
            shutil.copytree(snapshot / "sources", target / "sources")
        shutil.copyfile(ROOT / "compose.yaml", target / "compose.yaml")
        env = compose_env(manifest, target, args.container, args.port, args.tweaks_port, with_tweaks)
        # Single-quoted dotenv values keep $ and # in paths literal on future starts.
        def dotenv(value):
            if "\n" in value or "\r" in value:
                raise RecoveryError("Newlines are not supported in the restore destination.")
            return "'" + value.replace("'", "\\'") + "'"
        (target / ".env").write_text("\n".join(f"{k}={dotenv(v)}" for k, v in env.items()) + "\n")
        (target / "RESTORED_FROM.json").write_text(json.dumps(manifest, indent=2) + "\n")
        project_name = env["COMPOSE_PROJECT_NAME"]
        command = ["docker", "compose", "--project-directory", str(target), "--project-name", project_name,
                   "--file", str(target / "compose.yaml"), "up", "--detach", "--wait", "--wait-timeout", "90"]
        try:
            run(command, env={**os.environ, **env})
        except RecoveryError as error:
            raise RecoveryError(f"Data restored to {target}, but service startup failed. "
                                f"Inspect the generated Compose setup before retrying. {error}") from error
    url = f"http://localhost:{tweaks_port if with_tweaks else args.port}"
    deadline = time.monotonic() + 30
    last_error = "not ready"
    while time.monotonic() < deadline:
        try:
            verify_restored_services(args.port, tweaks_port)
            print(f"Restored {len(manifest['checks']['active_budgets'])} budgets to {target}")
            if with_tweaks:
                print(f"Actual Budget Tweaks is ready at {url} (Actual itself: http://localhost:{args.port}).")
            print(f"Open {url} and use your existing Actual server password.")
            print("If asked for a server address, enter the same URL; download your restored budget from its list.")
            if args.open_browser:
                import webbrowser
                webbrowser.open(url)
            return
        except (RecoveryError, urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            last_error = str(error)
        time.sleep(1)
    raise RecoveryError(f"Data restored, but services did not become ready: {last_error}. "
                        f"Inspect the generated Compose setup in {target}.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("backup", help="Copy a consistent server snapshot and encrypt it")
    b.add_argument("--container", default=config()["source_container"])
    b.add_argument("--output", type=Path, default=ROOT / "backups")
    b.add_argument("--source-export", type=Path, action="append", default=[])
    b.add_argument("--publish", action="store_true", help="Upload an encrypted snapshot to a GitHub release")
    b.set_defaults(action=backup)
    r = commands.add_parser("restore", help="Restore into an empty directory and start Actual")
    r.add_argument("--key", type=Path)
    r.add_argument("--archive", type=Path, help="Use a local archive instead of downloading the latest release")
    r.add_argument("--release", help="Restore this release tag instead of latest")
    r.add_argument("--target", type=Path, default=Path.home() / "ActualBudget")
    r.add_argument("--container", default="actual-budget")
    r.add_argument("--port", type=int, choices=range(1, 65536), metavar="PORT", default=5006)
    r.add_argument("--tweaks-port", type=int, choices=range(1, 65536), metavar="PORT", default=3005)
    r.add_argument("--no-tweaks", action="store_true", help="Restore only Actual; skip the optional Tweaks image and port")
    r.add_argument("--open-browser", action="store_true")
    r.set_defaults(action=restore)
    args = parser.parse_args()
    try:
        args.action(args)
    except KeyboardInterrupt:
        print("Interrupted. If copying was in progress, the source server was restarted.", file=sys.stderr)
        return 130
    except (RecoveryError, OSError, ValueError, sqlite3.Error, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
