from __future__ import annotations

from collections import defaultdict

from wall_pdf_analyzer.models import AnalysisInput, AnalysisResult, ReportRow, SummaryRow

EXTERIOR_CONTROL_COLOR = "#FF00FF"
LOW_CONFIDENCE_THRESHOLD = 0.75


def analyze_project(project: AnalysisInput) -> AnalysisResult:
    rows: list[ReportRow] = []
    warnings: list[str] = []
    scope_label = project.scope.label()

    for segment in project.wall_segments:
        wall_type = project.wall_types.get(segment.type_code)
        if wall_type is None:
            warnings.append(
                f"Segment {segment.id} uses unknown wall type {segment.type_code}"
            )
            continue
        if not wall_type.include_in_report:
            continue

        is_exterior = segment.exterior or wall_type.exterior
        color = EXTERIOR_CONTROL_COLOR if is_exterior else wall_type.color
        gross_length_m = project.scale.to_meters(segment.drawing_length)
        openings_m = project.scale.to_meters(segment.drawing_opening_width)
        net_length_m = max(gross_length_m - openings_m, 0.0)

        if segment.confidence < LOW_CONFIDENCE_THRESHOLD:
            warnings.append(
                f"Segment {segment.id} has low recognition confidence "
                f"({segment.confidence:.0%})"
            )
        if openings_m > gross_length_m:
            warnings.append(
                f"Segment {segment.id} has openings wider than its gross length"
            )

        rows.append(
            ReportRow(
                segment_id=segment.id,
                wall_type=wall_type.code,
                wall_name=wall_type.name,
                color=color,
                page=segment.page,
                gross_length_m=round(gross_length_m, 3),
                openings_m=round(openings_m, 3),
                net_length_m=round(net_length_m, 3),
                confidence=segment.confidence,
                exterior=is_exterior,
                scope=scope_label,
                comment=segment.comment,
            )
        )

    summary = _build_summary(rows)
    exterior_total_m = round(
        sum(row.gross_length_m for row in rows if row.exterior),
        3,
    )
    return AnalysisResult(
        project_name=project.project_name,
        scale_label=project.scale.label,
        scope=scope_label,
        rows=tuple(rows),
        summary=tuple(summary),
        exterior_total_m=exterior_total_m,
        warnings=tuple(warnings),
    )


def _build_summary(rows: list[ReportRow]) -> list[SummaryRow]:
    grouped: dict[tuple[str, bool], list[ReportRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.wall_type, row.exterior)].append(row)

    summary: list[SummaryRow] = []
    for (_, _), group_rows in sorted(
        grouped.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        first = group_rows[0]
        summary.append(
            SummaryRow(
                wall_type=first.wall_type,
                wall_name=first.wall_name,
                color=first.color,
                segment_count=len(group_rows),
                gross_length_m=round(sum(row.gross_length_m for row in group_rows), 3),
                openings_m=round(sum(row.openings_m for row in group_rows), 3),
                net_length_m=round(sum(row.net_length_m for row in group_rows), 3),
                exterior=first.exterior,
            )
        )
    return summary
