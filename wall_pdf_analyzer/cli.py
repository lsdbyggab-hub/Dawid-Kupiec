from __future__ import annotations

import argparse
from pathlib import Path

from wall_pdf_analyzer.analyzer import analyze_project
from wall_pdf_analyzer.exporters import export_control_svg, export_result
from wall_pdf_analyzer.io import load_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze PDF-derived wall geometry and export a report."
    )
    parser.add_argument("input_json", help="Path to recognized project JSON")
    parser.add_argument("output", help="Report path: .xlsx, .csv or .json")
    parser.add_argument(
        "--overlay",
        help="Optional SVG control overlay path with colored wall segments",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project = load_project(args.input_json)
    result = analyze_project(project)
    export_result(result, args.output)
    if args.overlay:
        export_control_svg(project, result, args.overlay)

    print(f"Saved report: {Path(args.output).resolve()}")
    if args.overlay:
        print(f"Saved control overlay: {Path(args.overlay).resolve()}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
