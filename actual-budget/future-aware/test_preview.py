import json
from contextlib import closing
from pathlib import Path
import sqlite3
import socket
import tempfile
import unittest
from unittest.mock import patch

import preview
import build


class PreviewSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'live-data'
        self.source.mkdir()

    def test_rejects_destination_inside_live_data(self):
        with self.assertRaises(ValueError):
            preview.validate_paths(self.source, self.source / 'preview')

    def test_rejects_destination_that_contains_live_data(self):
        with self.assertRaises(ValueError):
            preview.validate_paths(self.source, self.root)

    def test_rejects_symlink_alias_of_live_data(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            preview.validate_paths(self.source, alias)

    def test_refuses_existing_destination_and_keeps_its_files(self):
        destination = self.root / 'existing'
        destination.mkdir()
        sentinel = destination / 'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaises(FileExistsError):
            preview.validate_paths(self.source, destination)
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_accepts_a_new_sibling_destination(self):
        preview.validate_paths(self.source, self.root / 'private-preview')
        self.assertFalse((self.root / 'private-preview').exists())

    def test_rejects_live_or_duplicate_ports(self):
        for pair in [(5006, 13005), (15006, 3005), (3005, 15006), (15006, 5006), (15006, 15006), (0, 13005), (65536, 13005)]:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                preview.validate_ports(*pair)

    def test_accepts_separate_preview_ports(self):
        preview.validate_ports(15006, 13005)

    def test_copies_committed_wal_data_without_changing_the_source(self):
        source_db = self.source / 'budget.sqlite'
        connection = sqlite3.connect(source_db)
        self.addCleanup(connection.close)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE amounts (amount INTEGER)')
        connection.execute('INSERT INTO amounts VALUES (12345)')
        connection.commit()
        (self.source / 'checkpoint.blob').write_bytes(b'synthetic-checkpoint')
        destination = self.root / 'copy'

        preview.copy_snapshot(self.source, destination)

        self.assertTrue((destination / 'budget.sqlite').is_file())
        self.assertFalse((destination / 'budget.sqlite-wal').exists())
        with closing(sqlite3.connect(destination / 'budget.sqlite')) as copied:
            self.assertEqual(copied.execute('SELECT amount FROM amounts').fetchall(), [(12345,)])
            self.assertEqual(copied.execute('PRAGMA quick_check').fetchone(), ('ok',))
        self.assertEqual(connection.execute('SELECT amount FROM amounts').fetchall(), [(12345,)])
        self.assertEqual((destination / 'checkpoint.blob').read_bytes(), b'synthetic-checkpoint')

    def test_refuses_to_copy_a_symlink_outside_the_source(self):
        outside = self.root / 'outside.txt'
        outside.write_text('private')
        (self.source / 'outside-link').symlink_to(outside)
        with self.assertRaises(ValueError):
            preview.copy_snapshot(self.source, self.root / 'copy')

    def test_refuses_forged_stop_state(self):
        destination = self.root / 'preview'
        destination.mkdir()
        (destination / 'state.json').write_text(json.dumps({'project': 'my_actual_budget_from_ynab', 'data_dir': str(self.source)}))
        with self.assertRaises(ValueError):
            preview.load_state(destination)

    def test_refuses_resume_when_private_data_is_missing(self):
        state = {'data_dir': str(self.root / 'missing')}
        with self.assertRaises(ValueError):
            preview.validate_resume_data(state)

    def test_refuses_build_artifacts_overlapping_reused_source(self):
        for work in [self.source, self.source / 'build', self.root]:
            with self.subTest(work=work), self.assertRaises(ValueError):
                build.validate_build_paths(work, self.source)

    def test_refuses_to_adopt_existing_preview_containers(self):
        destination = self.root / 'preview'
        state = {'project': preview.project_name(destination), 'image': 'actual-budget-future-aware:test', 'actual_port': 15006, 'tweaks_port': 13005}
        def docker(arguments, **_kwargs):
            return 'true' if arguments[1:3] == ['image', 'inspect'] else 'existing-container'
        with patch.object(preview, 'run', side_effect=docker), patch.object(preview.socket, 'socket'):
            with self.assertRaises(ValueError):
                preview.preflight(state)
        self.assertFalse(destination.exists())

    def test_refuses_an_image_without_the_preview_label(self):
        state = {'project': 'actual-future-test', 'image': 'actual-budget-future-aware:test', 'actual_port': 15006, 'tweaks_port': 13005}
        with patch.object(preview, 'run', return_value=''), patch.object(preview.socket, 'socket'):
            with self.assertRaises(ValueError):
                preview.preflight(state)

    def test_refuses_a_port_with_an_active_listener(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            port = listener.getsockname()[1]
            state = {'project': 'actual-future-test', 'image': 'actual-budget-future-aware:test', 'actual_port': port, 'tweaks_port': 13005}
            def docker(arguments, **_kwargs):
                return 'true' if arguments[1:3] == ['image', 'inspect'] else ''
            with patch.object(preview, 'run', side_effect=docker):
                with self.assertRaisesRegex(ValueError, 'already in use'):
                    preview.preflight(state)


if __name__ == '__main__':
    unittest.main()
