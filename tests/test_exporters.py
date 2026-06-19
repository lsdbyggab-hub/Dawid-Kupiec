import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from wall_pdf_analyzer.analyzer import analyze_project
from wall_pdf_analyzer.exporters import export_control_svg, export_result
from wall_pdf_analyzer.io import load_project


class ExporterTests(unittest.TestCase):
    def test_exports_json_xlsx_and_svg(self):
        project = load_project("examples/sample_project.json")
        result = analyze_project(project)

        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            json_path = base / "report.json"
            xlsx_path = base / "report.xlsx"
            svg_path = base / "overlay.svg"

            export_result(result, json_path)
            export_result(result, xlsx_path)
            export_control_svg(project, result, svg_path)

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            workbook = load_workbook(xlsx_path)
            svg = svg_path.read_text(encoding="utf-8")

        self.assertEqual(payload["project_name"], result.project_name)
        self.assertIn("Podsumowanie", workbook.sheetnames)
        self.assertIn("Odcinki", workbook.sheetnames)
        self.assertIn("#FF00FF", svg)


if __name__ == "__main__":
    unittest.main()
