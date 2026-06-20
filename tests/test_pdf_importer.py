import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from wall_pdf_analyzer.analyzer import analyze_project
from wall_pdf_analyzer.models import Point
from wall_pdf_analyzer.pdf_importer import (
    PdfScaleMissingError,
    _WallCandidate,
    _WallTag,
    _VectorSegment,
    _apply_wall_tag_guidance,
    import_pdf_project,
)


class PdfImporterTests(unittest.TestCase):
    def test_imports_vector_pdf_lines_as_wall_segments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "plan.pdf"
            _write_vector_pdf(
                pdf_path,
                b"10 10 m 95.0394 10 l S\n"
                b"95.0394 10 m 95.0394 66.6929 l S\n",
            )

            project = import_pdf_project(pdf_path, scale_denominator=100)
            result = analyze_project(project)

        self.assertEqual(project.project_name, "plan")
        self.assertEqual(project.source_metadata["pdf_kind"], "vector")
        self.assertEqual(
            project.wall_segments[0].measurement_basis,
            "vector_geometry_pdf_points_scaled",
        )
        self.assertEqual(len(project.wall_segments), 2)
        lengths = sorted(row.gross_length_m for row in result.rows)
        self.assertAlmostEqual(lengths[0], 2.0, places=2)
        self.assertAlmostEqual(lengths[1], 3.0, places=2)

    def test_detects_vector_window_opening_from_gap_and_parallel_symbol(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "window.pdf"
            _write_vector_pdf(
                pdf_path,
                b"10 10 m 50 10 l S\n"
                b"80 10 m 130 10 l S\n"
                b"50 14 m 80 14 l S\n",
            )

            project = import_pdf_project(pdf_path, scale_denominator=100)
            result = analyze_project(project)

        self.assertEqual(len(project.wall_segments), 1)
        self.assertEqual(len(project.wall_segments[0].openings), 1)
        self.assertEqual(project.wall_segments[0].openings[0].kind, "window")
        self.assertAlmostEqual(result.rows[0].openings_m, 1.06, places=2)
        self.assertLess(result.rows[0].net_length_m, result.rows[0].gross_length_m)

    def test_requires_scale_when_pdf_text_has_no_scale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "plan.pdf"
            _write_vector_pdf(pdf_path, b"10 10 m 95.0394 10 l S\n")

            with self.assertRaises(PdfScaleMissingError):
                import_pdf_project(pdf_path)

    def test_imports_raster_pdf_after_known_segment_calibration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "scan.pdf"
            _write_raster_pdf(pdf_path)

            project = import_pdf_project(
                pdf_path,
                calibration_pixels=100 * 200 / 72,
                calibration_meters=3.0,
                force_raster=True,
                min_segment_length=20,
            )
            result = analyze_project(project)

        self.assertEqual(project.source_metadata["method"], "raster_image_calibrated")
        self.assertEqual(project.source_metadata["scale_source"], "known_segment_calibration")
        self.assertTrue(result.rows)
        self.assertAlmostEqual(result.rows[0].gross_length_m, 3.0, places=1)

    def test_wall_type_tags_filter_furniture_and_stairs(self):
        candidates = [
            _WallCandidate(_VectorSegment(1, Point(10, 10), Point(80, 10))),
            _WallCandidate(_VectorSegment(1, Point(80, 10), Point(80, 70))),
            _WallCandidate(_VectorSegment(1, Point(120, 50), Point(155, 50))),
            _WallCandidate(_VectorSegment(1, Point(112, 34), Point(112, 70))),
            _WallCandidate(_VectorSegment(1, Point(10, 105), Point(95, 105))),
        ]
        tags = [
            _WallTag(1, "IV20", Point(28, 13), "IV20"),
            _WallTag(1, "IV31", Point(135, 54), "IV31"),
        ]

        filtered, warnings, info = _apply_wall_tag_guidance(
            candidates,
            tags,
            drawing_units_per_meter=28.346,
        )

        self.assertTrue(info["enabled"])
        self.assertEqual(info["skipped_segments"], 2)
        self.assertEqual(len(filtered), 3)
        self.assertEqual([candidate.type_code for candidate in filtered], ["IV20", "IV20", "IV31"])
        self.assertTrue(any("schody, meble lub armature" in warning for warning in warnings))


def _write_vector_pdf(path: Path, content: bytes) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=120)
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject("/Contents")] = stream
    with path.open("wb") as file:
        writer.write(file)


def _write_raster_pdf(path: Path) -> None:
    import fitz  # type: ignore
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (200, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.line((20, 60, 120, 60), fill="black", width=3)
    image_path = path.with_suffix(".png")
    image.save(image_path)
    document = fitz.open()
    page = document.new_page(width=200, height=120)
    page.insert_image(fitz.Rect(0, 0, 200, 120), filename=str(image_path))
    document.save(str(path))
    document.close()


if __name__ == "__main__":
    unittest.main()
