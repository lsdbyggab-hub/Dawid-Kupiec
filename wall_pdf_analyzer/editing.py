from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from typing import Iterable

from wall_pdf_analyzer.models import AnalysisInput, Point, WallSegment


def change_segment_type(
    project: AnalysisInput,
    segment_ids: Iterable[str],
    type_code: str,
) -> AnalysisInput:
    if type_code not in project.wall_types:
        raise ValueError(f"Unknown wall type: {type_code}")
    selected = set(segment_ids)
    wall_type = project.wall_types[type_code]
    segments = tuple(
        replace(
            segment,
            type_code=type_code,
            exterior=wall_type.exterior,
            measurement_basis="manual_correction_type",
            comment=_append_comment(segment.comment, f"Typ zmieniony recznie na {type_code}."),
        )
        if segment.id in selected
        else segment
        for segment in project.wall_segments
    )
    return _replace_segments(project, segments, f"Zmieniono typ odcinkow: {', '.join(sorted(selected))}.")


def delete_segments(project: AnalysisInput, segment_ids: Iterable[str]) -> AnalysisInput:
    selected = set(segment_ids)
    segments = tuple(segment for segment in project.wall_segments if segment.id not in selected)
    if len(segments) == len(project.wall_segments):
        raise ValueError("No selected segments were found.")
    if not segments:
        raise ValueError("Project must keep at least one wall segment.")
    return _replace_segments(project, segments, f"Usunieto odcinki: {', '.join(sorted(selected))}.")


def merge_segments(project: AnalysisInput, segment_ids: Iterable[str]) -> AnalysisInput:
    selected = set(segment_ids)
    source_segments = [segment for segment in project.wall_segments if segment.id in selected]
    if len(source_segments) < 2:
        raise ValueError("Select at least two segments to merge.")
    pages = {segment.page for segment in source_segments}
    if len(pages) != 1:
        raise ValueError("Can merge only segments from the same page.")

    points = [point for segment in source_segments for point in (segment.start, segment.end)]
    start, end = _farthest_points(points)
    first = source_segments[0]
    merged = WallSegment(
        id=_next_merged_id(project),
        type_code=first.type_code,
        start=start,
        end=end,
        page=first.page,
        confidence=min(segment.confidence for segment in source_segments),
        exterior=any(segment.exterior for segment in source_segments),
        comment=f"Scalone recznie z: {', '.join(segment.id for segment in source_segments)}.",
        measurement_basis="manual_correction_merge",
        centerline_or_face=first.centerline_or_face,
        openings=tuple(opening for segment in source_segments for opening in segment.openings),
    )
    segments = tuple(segment for segment in project.wall_segments if segment.id not in selected) + (merged,)
    return _replace_segments(project, segments, merged.comment)


def _farthest_points(points: list[Point]) -> tuple[Point, Point]:
    if len(points) < 2:
        raise ValueError("Need at least two points.")
    return max(combinations(points, 2), key=lambda pair: pair[0].distance_to(pair[1]))


def _next_merged_id(project: AnalysisInput) -> str:
    existing = {segment.id for segment in project.wall_segments}
    index = 1
    while True:
        candidate = f"MERGE-{index:04d}"
        if candidate not in existing:
            return candidate
        index += 1


def _replace_segments(
    project: AnalysisInput,
    segments: tuple[WallSegment, ...],
    history_entry: str,
) -> AnalysisInput:
    metadata = dict(project.source_metadata)
    history = list(metadata.get("corrections", []))
    history.append(history_entry)
    metadata["corrections"] = history
    return replace(project, wall_segments=segments, source_metadata=metadata)


def _append_comment(current: str, addition: str) -> str:
    return f"{current} {addition}".strip()
