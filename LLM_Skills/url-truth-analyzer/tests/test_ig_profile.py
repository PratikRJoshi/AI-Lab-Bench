#!/usr/bin/env python3
"""Unit tests for ig_carousel_scraper profile helpers. No live network / no Playwright calls.

Run: python3 -m unittest tests.test_ig_profile -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "ig_carousel_scraper",
    str(Path(__file__).resolve().parent.parent / "ig_carousel_scraper.py"))
igs = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(igs)
    _IMPORT_OK = True
except Exception:  # playwright may be absent in CI
    _IMPORT_OK = False


@unittest.skipUnless(_IMPORT_OK, "playwright not importable")
class TestProfileNormalization(unittest.TestCase):
    def test_handle_at(self):
        self.assertEqual(igs.normalize_profile_url("@foo"), "https://www.instagram.com/foo/")

    def test_profile_url(self):
        self.assertEqual(igs.normalize_profile_url("https://www.instagram.com/foo/"),
                         "https://www.instagram.com/foo/")

    def test_post_rejected(self):
        with self.assertRaises(ValueError):
            igs.normalize_profile_url("https://www.instagram.com/p/ABC/")

    def test_reel_rejected(self):
        with self.assertRaises(ValueError):
            igs.normalize_profile_url("https://www.instagram.com/reel/ABC/")

    def test_type_inference(self):
        self.assertEqual(igs._item_type("https://www.instagram.com/reel/ABC/"), "reel")
        self.assertEqual(igs._item_type("https://www.instagram.com/p/ABC/"), "post")
        self.assertEqual(igs._item_type("https://www.instagram.com/tv/ABC/"), "tv")


if __name__ == "__main__":
    unittest.main()
