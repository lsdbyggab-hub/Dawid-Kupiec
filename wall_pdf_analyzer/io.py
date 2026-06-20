from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wall_pdf_analyzer.models import AnalysisInput
from wall_pdf_analyzer.pdf_importer import import_pdf_project


def load_project(path: str | Path) -> AnalysisInput:
    source = Path(path)
    with source.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    return AnalysisInput.from_mapping(data)


def load_input(
    path: str | Path,
    *,
    pdf_scale_denominator: float | None = None,
    pdf_calibration_pixels: float | None = None,
    pdf_calibration_meters: float | None = None,
    pdf_force_raster: bool = False,
    pdf_min_segment_length: float | None = None,
) -> AnalysisInput:
    source = Path(path)
    if source.suffix.lower() == ".pdf":
        options: dict[str, Any] = {
            "scale_denominator": pdf_scale_denominator,
            "calibration_pixels": pdf_calibration_pixels,
            "calibration_meters": pdf_calibration_meters,
            "force_raster": pdf_force_raster,
        }
        if pdf_min_segment_length is not None:
            options["min_segment_length"] = pdf_min_segment_length
        return import_pdf_project(source, **options)
    return load_project(source)
