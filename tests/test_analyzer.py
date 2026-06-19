import unittest

from wall_pdf_analyzer.analyzer import EXTERIOR_CONTROL_COLOR, analyze_project
from wall_pdf_analyzer.io import load_project


class AnalyzerTests(unittest.TestCase):
    def test_openings_do_not_reduce_gross_wall_length(self):
        project = load_project("examples/sample_project.json")
        result = analyze_project(project)

        row = next(item for item in result.rows if item.segment_id == "W-001")

        self.assertEqual(row.gross_length_m, 3.3)
        self.assertEqual(row.openings_m, 0.9)
        self.assertEqual(row.net_length_m, 2.4)

    def test_exterior_walls_are_totaled_and_colored_separately(self):
        project = load_project("examples/sample_project.json")
        result = analyze_project(project)

        exterior_rows = [row for row in result.rows if row.exterior]

        self.assertEqual(result.exterior_total_m, 8.1)
        self.assertTrue(exterior_rows)
        self.assertTrue(
            all(row.color == EXTERIOR_CONTROL_COLOR for row in exterior_rows)
        )

    def test_low_confidence_segment_creates_warning(self):
        project = load_project("examples/sample_project.json")
        result = analyze_project(project)

        self.assertTrue(
            any("W-004" in warning for warning in result.warnings),
            result.warnings,
        )


if __name__ == "__main__":
    unittest.main()
