from __future__ import annotations

from collections import defaultdict
from typing import Any

from .model import AnalysisResult, Opening, WallSegment, WallTypeRule

EXTERNAL_WALL_TYPE = "EXTERNAL"


def load_analysis(payload: dict[str, Any]) -> AnalysisResult:
    rules = tuple(
        WallTypeRule(
            code=item["code"],
            label=item.get("label", item["code"]),
            color_hex=item.get("color_hex", "#999999"),
            count_in_totals=item.get("count_in_totals", True),
            highlight=item.get("highlight", True),
        )
        for item in payload.get("rules", [])
    )
    walls = tuple(_load_wall(item) for item in payload.get("walls", []))
    return AnalysisResult(
        scale=payload.get("scale", "unknown"),
        source_pdf=payload.get("source_pdf", "unknown.pdf"),
        analyzed_scope=payload.get("analyzed_scope", "all pages"),
        rules=rules,
        walls=walls,
    )


def analyze_project(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate gross wall lengths grouped for Excel-like reporting."""

    result = load_analysis(payload)
    by_type: dict[str, float] = defaultdict(float)
    external_total = 0.0
    rows: list[dict[str, Any]] = []

    for wall in result.walls_for_totals():
        rule = result.rule_for(wall.wall_type)
        color = "#FF00FF" if wall.is_external else (rule.color_hex if rule else "#999999")
        label = "Ściana zewnętrzna" if wall.is_external else (rule.label if rule else wall.wall_type)
        by_type[wall.wall_type] += wall.gross_length_m
        if wall.is_external:
            external_total += wall.gross_length_m
        rows.append(
            {
                "id": wall.identifier,
                "type": wall.wall_type,
                "label": label,
                "color": color,
                "page": wall.page,
                "gross_length_m": round(wall.gross_length_m, 3),
                "openings_width_m": round(wall.openings_width_m, 3),
                "optional_net_length_m": round(wall.optional_net_length_m, 3),
                "confidence": round(wall.confidence, 3),
                "external": wall.is_external,
            }
        )

    return {
        "source_pdf": result.source_pdf,
        "scale": result.scale,
        "analyzed_scope": result.analyzed_scope,
        "totals_by_type": {key: round(value, 3) for key, value in sorted(by_type.items())},
        "external_total_m": round(external_total, 3),
        "rows": rows,
    }


def _load_wall(item: dict[str, Any]) -> WallSegment:
    openings = tuple(
        Opening(
            identifier=opening["identifier"],
            kind=opening.get("kind", "opening"),
            width_m=float(opening["width_m"]),
            position_m=opening.get("position_m"),
        )
        for opening in item.get("openings", [])
    )
    return WallSegment(
        identifier=item["identifier"],
        wall_type=item["wall_type"],
        length_m=float(item["length_m"]),
        page=int(item.get("page", 1)),
        is_external=bool(item.get("is_external", False)),
        confidence=float(item.get("confidence", 1.0)),
        openings=openings,
    )
