#!/usr/bin/env python3
"""Unit tests for channel_enumerator parsing + detection (Phase 1) and YouTube
URL helpers (Phase 2). No live network: enumeration itself is not exercised here.

Run:  python3 -m unittest discover -s tests -v
   or python3 -m unittest tests.test_channel_enumerator -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import channel_enumerator as ce  # noqa: E402


class TestDirectiveParsing(unittest.TestCase):
    def test_channel_bare(self):
        d = ce.parse_directives("channel")
        self.assertTrue(d["channel_mode"])
        self.assertIsNone(d["n"])

    def test_channel_n(self):
        d = ce.parse_directives("channel:10")
        self.assertTrue(d["channel_mode"])
        self.assertEqual(d["n"], 10)

    def test_top_n(self):
        d = ce.parse_directives("top:7")
        self.assertEqual(d["top_n"], 7)

    def test_channel_and_top_equiv(self):
        d = ce.parse_directives("channel top:10")
        self.assertTrue(d["channel_mode"])
        self.assertEqual(d["top_n"], 10)

    def test_platform_and_include(self):
        d = ce.parse_directives("channel:5 platform:youtube include:videos,shorts")
        self.assertEqual(d["platform"], "youtube")
        self.assertEqual(d["include"], ["videos", "shorts"])

    def test_inherited_directives(self):
        d = ce.parse_directives("channel:5 transcript-only display-only")
        self.assertIn("transcript-only", d["inherited"])
        self.assertIn("display-only", d["inherited"])

    def test_bad_int(self):
        d = ce.parse_directives("channel:abc")
        self.assertTrue(any("integer" in e for e in d["errors"]))


class TestResolveN(unittest.TestCase):
    def test_default(self):
        n, errs = ce.resolve_n({"n": None, "top_n": None}, None)
        self.assertEqual(n, ce.DEFAULT_N)
        self.assertEqual(errs, [])

    def test_conflict(self):
        n, errs = ce.resolve_n({"n": 5, "top_n": 10}, None)
        self.assertIsNone(n)
        self.assertTrue(any("conflicting" in e for e in errs))

    def test_cli_override(self):
        n, errs = ce.resolve_n({"n": 5, "top_n": None}, 3)
        self.assertEqual(n, 3)

    def test_cap(self):
        n, errs = ce.resolve_n({"n": 999, "top_n": None}, None)
        self.assertEqual(n, ce.MAX_N)


class TestDetection(unittest.TestCase):
    def _kind(self, line, **kw):
        return ce.parse_entry(line, **kw)

    def test_youtube_channel_handle(self):
        p = self._kind("https://www.youtube.com/@veritasium [channel:5]")
        self.assertEqual(p["entry_kind"], "channel")
        self.assertEqual(p["platform"], "youtube")

    def test_youtube_channel_id(self):
        p = self._kind("https://www.youtube.com/channel/UCvQECJukTDE2i6aCoMnS-Vg")
        self.assertEqual(p["entry_kind"], "channel")

    def test_youtube_c_and_user(self):
        self.assertEqual(self._kind("https://www.youtube.com/c/Vsauce")["entry_kind"], "channel")
        self.assertEqual(self._kind("https://www.youtube.com/user/Vsauce")["entry_kind"], "channel")

    def test_youtube_single_video_no_channel(self):
        p = self._kind("https://www.youtube.com/watch?v=abc123")
        self.assertEqual(p["entry_kind"], "single-url")

    def test_youtube_shorts_single(self):
        p = self._kind("https://www.youtube.com/shorts/abc123")
        self.assertEqual(p["entry_kind"], "single-url")

    def test_youtu_be_single(self):
        p = self._kind("https://youtu.be/abc123")
        self.assertEqual(p["entry_kind"], "single-url")

    def test_instagram_profile(self):
        p = self._kind("https://www.instagram.com/nasa/ [channel:5]")
        self.assertEqual(p["entry_kind"], "channel")
        self.assertEqual(p["platform"], "instagram")

    def test_instagram_post_single(self):
        p = self._kind("https://www.instagram.com/p/ABC123/")
        self.assertEqual(p["entry_kind"], "single-url")

    def test_instagram_reel_single(self):
        p = self._kind("https://www.instagram.com/reel/ABC123/")
        self.assertEqual(p["entry_kind"], "single-url")

    def test_bare_handle_needs_platform(self):
        p = self._kind("@hubermanlab [channel:5]")
        self.assertTrue(any("platform hint" in e for e in p["errors"]))

    def test_bare_handle_with_platform(self):
        p = self._kind("@hubermanlab [channel:5 platform:instagram]")
        self.assertEqual(p["entry_kind"], "channel")
        self.assertEqual(p["platform"], "instagram")
        self.assertEqual(p["errors"], [])

    def test_local_folder(self):
        p = self._kind("/Users/me/Downloads/carousel [title: x]")
        self.assertEqual(p["entry_kind"], "local-folder")

    def test_generic_needs_directive(self):
        self.assertEqual(self._kind("https://example.com/")["entry_kind"], "single-url")
        self.assertEqual(self._kind("https://example.com/ [channel:5]")["entry_kind"], "channel")

    def test_directive_propagation(self):
        p = self._kind("https://www.youtube.com/@x [channel:3 transcript-only]")
        self.assertIn("transcript-only", p["inherited_directives"])
        self.assertEqual(p["n"], 3)


class TestYouTubeHelpers(unittest.TestCase):
    def test_canonicalize_strips_tab(self):
        self.assertEqual(
            ce.canonicalize_youtube("https://www.youtube.com/@x/videos"),
            "https://www.youtube.com/@x")

    def test_canonicalize_channel_id(self):
        self.assertEqual(
            ce.canonicalize_youtube("https://www.youtube.com/channel/UCabc/streams"),
            "https://www.youtube.com/channel/UCabc")

    def test_canonicalize_bare_handle(self):
        self.assertEqual(
            ce.canonicalize_youtube("@x"),
            "https://www.youtube.com/@x")

    def test_normalize_permalink_video(self):
        url, typ = ce._normalize_yt_permalink({"id": "vid1"}, "videos")
        self.assertEqual(url, "https://www.youtube.com/watch?v=vid1")
        self.assertEqual(typ, "video")

    def test_normalize_permalink_short(self):
        url, typ = ce._normalize_yt_permalink({"id": "s1"}, "shorts")
        self.assertEqual(url, "https://www.youtube.com/shorts/s1")
        self.assertEqual(typ, "short")


if __name__ == "__main__":
    unittest.main()
