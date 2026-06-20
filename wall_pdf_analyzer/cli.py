from __future__ import annotations

import argparse
from pathlib import Path

from wall_pdf_analyzer.analyzer import analyze_project
from wall_pdf_analyzer.exporters import export_control_pdf, export_control_svg, export_result
from wall_pdf_analyzer.io import load_input


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze wall geometry from JSON or vector PDF and export a report."
    )
    parser.add_argument("input", help="Path to project JSON or vector PDF")
    parser.add_argument("output", help="Report path: .xlsx, .csv or .json")
    parser.add_argument(
        "--overlay",
        help="Optional SVG control overlay path with colored wall segments",
    )
    parser.add_argument(
        "--overlay-pdf",
        help="Optional PDF control overlay path with colored wall segments",
    )
    parser.add_argument(
        "--pdf-scale",
        type=float,
        help="PDF scale denominator, for example 100 for 1:100. "
        "Used when scale cannot be read from PDF text.",
    )
    parser.add_argument(
        "--pdf-min-line",
        type=float,
        default=None,
        help="Minimum vector line length in PDF points to treat as a wall candidate.",
    )
    parser.add_argument(
        "--calibration-pixels",
        type=float,
        help="Known calibration segment length measured in rendered pixels.",
    )
    parser.add_argument(
        "--calibration-meters",
        type=float,
        help="Real known calibration segment length in meters.",
    )
    parser.add_argument(
        "--raster",
        action="store_true",
        help="Force raster/image line detection instead of vector extraction.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project = load_input(
        args.input,
        pdf_scale_denominator=args.pdf_scale,
        pdf_calibration_pixels=args.calibration_pixels,
        pdf_calibration_meters=args.calibration_meters,
        pdf_force_raster=args.raster,
        pdf_min_segment_length=args.pdf_min_line,
    )
    result = analyze_project(project)
    export_result(result, args.output)
    if args.overlay:
        export_control_svg(project, result, args.overlay)
    if args.overlay_pdf:
        export_control_pdf(project, result, args.overlay_pdf)

    print(f"Saved report: {Path(args.output).resolve()}")
    if args.overlay:
        print(f"Saved control overlay: {Path(args.overlay).resolve()}")
    if args.overlay_pdf:
        print(f"Saved PDF control overlay: {Path(args.overlay_pdf).resolve()}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
