from datetime import timedelta
from pathlib import Path
import unittest

from renderer.render import (
    EvidenceDocument,
    parse_session_timestamp,
    sort_indexed_documents,
    validate_session_timestamps,
)


class SessionTimestampTests(unittest.TestCase):
    def test_parses_canonical_timestamp_with_timezone(self):
        parsed = parse_session_timestamp("2026-10-15T19:10:00+08:00")

        self.assertEqual(parsed.precision, "time")
        self.assertEqual(parsed.precision_rank, 1)
        self.assertIsNotNone(parsed.instant.tzinfo)

    def test_parses_legacy_date_as_day_precision(self):
        parsed = parse_session_timestamp("2026-10-15")

        self.assertEqual(parsed.precision, "day")
        self.assertEqual(parsed.precision_rank, 0)
        self.assertEqual(parsed.instant.hour, 0)
        self.assertEqual(parsed.instant.utcoffset(), timedelta(hours=8))

    def test_parses_legacy_date_with_offset_as_day_precision(self):
        parsed = parse_session_timestamp("2026-10-08+08:00")

        self.assertEqual(parsed.precision, "day")
        self.assertEqual(parsed.instant.hour, 0)
        self.assertEqual(parsed.instant.utcoffset().total_seconds(), 8 * 3600)

    def test_rejects_timestamp_without_timezone(self):
        with self.assertRaises(ValueError):
            parse_session_timestamp("2026-10-15T19:10:00")

    def test_rejects_invalid_calendar_date(self):
        with self.assertRaises(ValueError):
            parse_session_timestamp("2026-13-40")


class SessionTimestampCompatibilityTests(unittest.TestCase):
    @staticmethod
    def document(value: str):
        rel_dir = Path("sessions") / "legacy-example"
        return EvidenceDocument(
            path=rel_dir / "evidence.yaml",
            rel_dir=rel_dir,
            data={
                "session": {
                    "started_at": value,
                    "updated_at": value,
                }
            },
        )

    def test_unregistered_legacy_value_fails_validation(self):
        errors = validate_session_timestamps(
            self.document("2026-10-15"),
            legacy_values={},
        )

        self.assertEqual(len(errors), 2)
        self.assertTrue(all("compatibility-only" in error for error in errors))

    def test_frozen_legacy_value_remains_valid(self):
        document = self.document("2026-10-15")
        legacy_values = {
            "sessions/legacy-example/evidence.yaml": {
                "started_at": "2026-10-15",
                "updated_at": "2026-10-15",
            }
        }

        self.assertEqual(
            validate_session_timestamps(document, legacy_values),
            [],
        )

    def test_canonical_value_needs_no_compatibility_entry(self):
        document = self.document("2026-10-15T19:10:00+08:00")

        self.assertEqual(
            validate_session_timestamps(document, legacy_values={}),
            [],
        )


class RendererIndexSortTests(unittest.TestCase):
    @staticmethod
    def item(area: str, session_id: str, started_at: str, updated_at: str):
        rel_dir = Path(area) / session_id
        doc = EvidenceDocument(
            path=rel_dir / "evidence.yaml",
            rel_dir=rel_dir,
            data={},
        )
        data = {
            "session": {
                "id": session_id,
                "started_at": started_at,
                "updated_at": updated_at,
            }
        }
        return doc, data

    def test_updated_at_beats_storage_area(self):
        older_session = self.item(
            "sessions", "2026-10-14-old", "2026-10-14", "2026-10-14"
        )
        newer_proposal = self.item(
            "proposals",
            "2026-10-15-new",
            "2026-10-15T09:00:00+08:00",
            "2026-10-15T09:00:00+08:00",
        )

        ordered = sort_indexed_documents([older_session, newer_proposal])

        self.assertEqual(ordered[0][1]["session"]["id"], "2026-10-15-new")

    def test_full_timestamps_order_within_same_day(self):
        morning = self.item(
            "sessions",
            "morning",
            "2026-10-15T08:00:00+08:00",
            "2026-10-15T08:00:00+08:00",
        )
        evening = self.item(
            "sessions",
            "evening",
            "2026-10-15T18:00:00+08:00",
            "2026-10-15T18:00:00+08:00",
        )

        ordered = sort_indexed_documents([morning, evening])

        self.assertEqual(ordered[0][1]["session"]["id"], "evening")

    def test_precise_same_day_timestamp_ranks_after_legacy_floor(self):
        legacy = self.item(
            "sessions", "legacy", "2026-10-15", "2026-10-15"
        )
        precise = self.item(
            "sessions",
            "precise",
            "2026-10-15T00:00:01+08:00",
            "2026-10-15T00:00:01+08:00",
        )

        ordered = sort_indexed_documents([legacy, precise])

        self.assertEqual(ordered[0][1]["session"]["id"], "precise")

    def test_precision_breaks_exact_midnight_tie(self):
        legacy = self.item(
            "sessions", "legacy", "2026-10-15", "2026-10-15"
        )
        precise = self.item(
            "sessions",
            "precise",
            "2026-10-15T00:00:00+08:00",
            "2026-10-15T00:00:00+08:00",
        )

        ordered = sort_indexed_documents([legacy, precise])

        self.assertEqual(ordered[0][1]["session"]["id"], "precise")

    def test_started_at_breaks_equal_updated_at(self):
        earlier = self.item(
            "sessions",
            "earlier",
            "2026-10-10",
            "2026-10-15",
        )
        later = self.item(
            "sessions",
            "later",
            "2026-10-12T12:00:00+08:00",
            "2026-10-15",
        )

        ordered = sort_indexed_documents([earlier, later])

        self.assertEqual(ordered[0][1]["session"]["id"], "later")

    def test_timezone_offsets_compare_actual_instants(self):
        earlier = self.item(
            "sessions",
            "earlier",
            "2026-10-15T09:00:00+08:00",
            "2026-10-15T09:00:00+08:00",
        )
        later = self.item(
            "sessions",
            "later",
            "2026-10-15T02:00:00+00:00",
            "2026-10-15T02:00:00+00:00",
        )

        ordered = sort_indexed_documents([earlier, later])

        self.assertEqual(ordered[0][1]["session"]["id"], "later")

    def test_id_and_path_make_equal_timestamps_deterministic(self):
        z_item = self.item("sessions", "z-item", "2026-10-15", "2026-10-15")
        a_item = self.item("research", "a-item", "2026-10-15", "2026-10-15")

        ordered = sort_indexed_documents([z_item, a_item])

        self.assertEqual(
            [item[1]["session"]["id"] for item in ordered],
            ["a-item", "z-item"],
        )


if __name__ == "__main__":
    unittest.main()
