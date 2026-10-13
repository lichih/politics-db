import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "fetch_threads.py"
SPEC = importlib.util.spec_from_file_location("fetch_threads", MODULE_PATH)
assert SPEC and SPEC.loader
fetch_threads = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fetch_threads
SPEC.loader.exec_module(fetch_threads)


class ParseThreadsUrlTests(unittest.TestCase):
    def test_share_url(self):
        target = fetch_threads.parse_threads_url(
            "https://www.threads.com/share/BBtkG8GXY7/"
        )
        self.assertEqual(target.kind, "share")
        self.assertEqual(target.identifier, "BBtkG8GXY7")

    def test_canonical_post_url(self):
        target = fetch_threads.parse_threads_url(
            "https://www.threads.com/@alice/post/ABC123?xmt=foo"
        )
        self.assertEqual(target.kind, "post")
        self.assertEqual(target.identifier, "ABC123")

    def test_threads_net_is_supported(self):
        target = fetch_threads.parse_threads_url(
            "https://threads.net/@alice/post/XYZ789"
        )
        self.assertEqual(target.kind, "post")
        self.assertEqual(target.identifier, "XYZ789")

    def test_non_threads_url_rejected(self):
        with self.assertRaises(ValueError):
            fetch_threads.parse_threads_url("https://example.com/share/ABC")


class BootstrapTests(unittest.TestCase):
    def test_find_and_normalize_post(self):
        raw = {
            "payload": {
                "thread_items": [
                    {
                        "post": {
                            "code": "POST1",
                            "caption": {"text": "hello"},
                            "user": {
                                "username": "alice",
                                "full_name": "Alice",
                                "profile_pic_url": "https://example.com/a.jpg",
                            },
                            "like_count": 4,
                            "taken_at": 123,
                            "text_post_app_info": {
                                "direct_reply_count": 2,
                                "repost_count": 1,
                                "reshare_count": 3,
                            },
                        }
                    }
                ]
            }
        }
        post = fetch_threads.find_threads_post(raw, "POST1")
        self.assertIsNotNone(post)
        normalized = fetch_threads.normalize_threads_post(post)
        self.assertEqual(normalized["content"], "hello")
        self.assertEqual(normalized["author"]["username"], "alice")
        self.assertEqual(
            normalized["url"],
            "https://www.threads.com/@alice/post/POST1",
        )
        self.assertEqual(normalized["stats"]["comments"], 2)


class BuildRecordTests(unittest.TestCase):
    def test_transport_is_not_promoted_to_source(self):
        target = fetch_threads.ThreadsTarget(
            "https://www.threads.com/share/ABC", "share", "ABC"
        )
        normalized = {
            "id": "POST1",
            "url": "https://www.threads.com/@alice/post/POST1",
            "content": "hello",
            "author": {"username": "alice", "full_name": "Alice"},
            "medias": [],
            "stats": {"likes": 1, "comments": 0, "reposts": 0, "shares": 0},
            "timestamp": 1,
        }
        record = fetch_threads.build_record(
            target,
            normalized,
            transport="Playwright/Chromium direct Threads browser",
            final_url="https://www.threads.com/@alice/post/POST1?xmt=foo",
        )
        self.assertEqual(record["source"]["platform"], "Threads")
        self.assertEqual(record["source"]["source_type"], "primary")
        self.assertEqual(
            record["retrieval"]["transport_role"],
            "retrieval mechanism only",
        )
        self.assertEqual(
            record["source"]["canonical_url"],
            "https://www.threads.com/@alice/post/POST1",
        )


if __name__ == "__main__":
    unittest.main()
