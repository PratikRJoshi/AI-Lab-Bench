"""Regression checks for failure paths that could expose or overwrite budget data."""
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import budget_recovery as recovery


class RecoveryTests(unittest.TestCase):
    def test_restore_selects_budget_release_in_shared_repository(self):
        cfg = {"repository": "owner/lab", "release_tag_prefix": "actual-budget-backup-"}
        with patch.object(recovery, "run", return_value="unrelated-v9\nactual-budget-backup-20261121T000000000000Z\nactual-budget-backup-20261122T000000000000Z\n"):
            self.assertEqual(recovery.latest_budget_release(cfg), "actual-budget-backup-20261122T000000000000Z")
        with patch.object(recovery, "run", return_value="unrelated-v9\n"):
            with self.assertRaises(recovery.RecoveryError):
                recovery.latest_budget_release(cfg)

    def test_public_upload_requires_explicit_approval(self):
        cfg = {"repository": "owner/lab"}
        with patch.object(recovery, "run", return_value='{"visibility":"PUBLIC"}'):
            with self.assertRaises(recovery.RecoveryError):
                recovery.validate_publish_repository(cfg)
            recovery.validate_publish_repository({**cfg, "allow_public_snapshots": True})
        with patch.object(recovery, "run", return_value='{"visibility":"PRIVATE"}'):
            recovery.validate_publish_repository(cfg)

    def test_cached_image_does_not_require_registry_access(self):
        with patch.object(recovery, "run", return_value="sha256:cached") as run:
            recovery.ensure_image("registry/image@sha256:cached")
            run.assert_called_once_with(["docker", "image", "inspect", "--format", "{{.Id}}", "registry/image@sha256:cached"])

    def test_archive_rejects_traversal_links_and_duplicates(self):
        for unsafe in ("../escape", "/tmp/escape", "data/../../escape", "symlink", "duplicate"):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                archive = root / "bad.tar.gz"
                with tarfile.open(archive, "w:gz") as tar:
                    entry = tarfile.TarInfo("data/link" if unsafe == "symlink" else unsafe)
                    if unsafe == "symlink":
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = "/tmp"
                    elif unsafe == "duplicate":
                        entry.name = "data/account.sqlite"
                        tar.addfile(entry, io.BytesIO())
                    tar.addfile(entry, io.BytesIO())
                dest = root / "restored"
                dest.mkdir()
                with self.assertRaises(recovery.RecoveryError):
                    recovery.safe_extract(archive, dest)
                self.assertEqual(list(dest.iterdir()), [])

    def test_nonempty_target_is_rejected_before_docker_is_called(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sentinel = root / "my-budget"
            sentinel.write_text("keep me")
            with patch.object(recovery, "run") as run:
                with self.assertRaises(recovery.RecoveryError):
                    recovery.check_target(root, "unused", 15006)
                run.assert_not_called()
            self.assertEqual(sentinel.read_text(), "keep me")

    def test_original_container_restarts_after_copy_failure(self):
        calls = []
        with patch.object(recovery, "run", side_effect=lambda args: calls.append(args) or ""), \
                patch.object(recovery, "container_info", return_value={"State": {"Running": False}}), \
                patch.object(recovery.shutil, "copytree", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                recovery.copy_cold_snapshot("original", Path("source"), Path("copy"))
        self.assertEqual(calls[-1], ["docker", "start", "original"])

    def test_original_container_restarts_after_interrupt_during_stop(self):
        calls = []
        def command(args):
            calls.append(args)
            if args[1] == "stop":
                raise KeyboardInterrupt()
            return ""
        with patch.object(recovery, "run", side_effect=command):
            with self.assertRaises(KeyboardInterrupt):
                recovery.copy_cold_snapshot("original", Path("source"), Path("copy"))
        self.assertEqual(calls[-1], ["docker", "start", "original"])

    def test_manifest_detects_modified_missing_and_extra_files(self):
        import json
        for mutation in ("modified", "missing", "extra"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                data = root / "data"
                data.mkdir()
                file = data / "budget.blob"
                file.write_bytes(b"original")
                manifest = {"format": 1, "image": "actualbudget/actual-server@sha256:" + "a" * 64,
                            "files": recovery.file_manifest(root), "checks": {}}
                (root / "manifest.json").write_text(json.dumps(manifest))
                if mutation == "modified":
                    file.write_bytes(b"changed")
                elif mutation == "missing":
                    file.unlink()
                else:
                    (data / "extra").write_bytes(b"extra")
                with self.assertRaisesRegex(recovery.RecoveryError, "hashes or file list"):
                    recovery.verify_snapshot(root)

    def test_public_key_cannot_be_used_in_place_of_recovery_key(self):
        with patch.object(recovery, "run", side_effect=["", "pub:-:3072:1:example\nfpr:::::::::PUBLIC:"]):
            with self.assertRaisesRegex(recovery.RecoveryError, "does not match"):
                recovery.import_key(["gpg"], Path("key.asc"), "SECRET", secret=True)


if __name__ == "__main__":
    unittest.main()
