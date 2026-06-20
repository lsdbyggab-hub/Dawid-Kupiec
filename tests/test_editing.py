import unittest

from wall_pdf_analyzer.editing import change_segment_type, delete_segments, merge_segments
from wall_pdf_analyzer.io import load_project


class EditingTests(unittest.TestCase):
    def test_changes_segment_type(self):
        project = load_project("examples/sample_project.json")

        updated = change_segment_type(project, ["W-001"], "S2")
        segment = next(item for item in updated.wall_segments if item.id == "W-001")

        self.assertEqual(segment.type_code, "S2")
        self.assertEqual(segment.measurement_basis, "manual_correction_type")
        self.assertIn("Zmieniono typ", " ".join(updated.source_metadata["corrections"]))

    def test_deletes_segments(self):
        project = load_project("examples/sample_project.json")

        updated = delete_segments(project, ["W-004"])

        self.assertFalse(any(item.id == "W-004" for item in updated.wall_segments))

    def test_merges_segments(self):
        project = load_project("examples/sample_project.json")

        updated = merge_segments(project, ["W-001", "W-002"])
        merged = next(item for item in updated.wall_segments if item.id.startswith("MERGE-"))

        self.assertEqual(merged.measurement_basis, "manual_correction_merge")
        self.assertIn("W-001", merged.comment)
        self.assertIn("W-002", merged.comment)


if __name__ == "__main__":
    unittest.main()
