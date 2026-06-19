from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wall_pdf_analyzer.models import AnalysisInput


def load_project(path: str | Path) -> AnalysisInput:
    source = Path(path)
    with source.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    return AnalysisInput.from_mapping(data)
