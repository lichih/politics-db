from pathlib import Path
import unittest

from renderer.render import EvidenceDocument, sort_indexed_documents


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
            "proposals", "2026-10-15-new", "2026-10-15", "2026-10-15"
        )

        ordered = sort_indexed_documents([older_session, newer_proposal])

        self.assertEqual(ordered[0][1]["session"]["id"], "2026-10-15-new")

    def test_started_at_breaks_equal_updated_at(self):
        earlier = self.item(
            "sessions", "earlier", "2026-10-10", "2026-10-15"
        )
        later = self.item(
            "sessions", "later", "2026-10-12", "2026-10-15"
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
