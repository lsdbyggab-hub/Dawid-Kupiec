from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from wall_pdf_analyzer.models import (
    AnalysisInput,
    AnalysisScope,
    Opening,
    Point,
    Scale,
    WallSegment,
    WallType,
)

POINTS_PER_METER_AT_FULL_SCALE = 72.0 / 25.4 * 1000.0
DEFAULT_MIN_SEGMENT_LENGTH_PT = 12.0
DEFAULT_RASTER_MIN_SEGMENT_LENGTH_PT = 24.0
DEFAULT_RASTER_DPI = 200
DEFAULT_RASTER_DARK_THRESHOLD = 190
AXIS_TOLERANCE_PT = 1.5
JOIN_TOLERANCE_PT = 2.0
MIN_OPENING_WIDTH_M = 0.45
MAX_OPENING_WIDTH_M = 2.8
MAX_DOOR_WIDTH_M = 1.25
OPENING_EVIDENCE_TOLERANCE_PT = 14.0
TAG_ASSIGN_RADIUS_M = 1.8
TAG_CONNECTION_TOLERANCE_M = 0.25
TAG_PROPAGATION_RADIUS_M = 4.0
TAG_PROPAGATION_MAX_DEPTH = 3
TAG_MIN_SEGMENT_LENGTH_M = 0.35
TAG_COLOR_OVERRIDES = {
    "IV20": "#4C1D95",
    "IV31": "#DC2626",
    "IV30": "#CA8A04",
    "IV02": "#16A34A",
}
TAG_COLOR_PALETTE = (
    "#2563EB",
    "#7C3AED",
    "#059669",
    "#D97706",
    "#BE123C",
    "#0891B2",
    "#9333EA",
    "#475569",
)


class PdfImportError(ValueError):
    pass


class PdfScaleMissingError(PdfImportError):
    pass


@dataclass(frozen=True)
class _VectorSegment:
    page: int
    start: Point
    end: Point

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)


@dataclass(frozen=True)
class _PageInspection:
    page: int
    kind: str
    vector_segment_count: int
    has_images: bool
    text_length: int


@dataclass(frozen=True)
class _WallCandidate:
    segment: _VectorSegment
    openings: tuple[Opening, ...] = ()
    type_code: str = "PDF"
    tag_distance: float | None = None


@dataclass(frozen=True)
class _WallTag:
    page: int
    code: str
    center: Point
    original: str


def import_pdf_project(
    path: str | Path,
    *,
    scale_denominator: float | None = None,
    calibration_pixels: float | None = None,
    calibration_meters: float | None = None,
    force_raster: bool = False,
    min_segment_length: float = DEFAULT_MIN_SEGMENT_LENGTH_PT,
    raster_dpi: int = DEFAULT_RASTER_DPI,
) -> AnalysisInput:
    """Build an AnalysisInput from vector linework in a PDF.

    The importer follows the measurement rules from the project brief: it never
    invents scale, it labels the measurement basis, and it rejects raster-only
    PDFs instead of returning fabricated real-world lengths.
    """

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on user environment
        raise PdfImportError(
            "Brakuje biblioteki pypdf. Zainstaluj zaleznosci projektu: "
            "python -m pip install -e ."
        ) from exc

    source = Path(path)
    reader = PdfReader(str(source))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover - encrypted PDFs vary
            raise PdfImportError("PDF jest zaszyfrowany i nie mozna go odczytac.") from exc

    raw_segments: list[_VectorSegment] = []
    inspections: list[_PageInspection] = []
    text_by_page: list[str] = []
    for page_index, page in enumerate(reader.pages, start=1):
        page_text = _safe_extract_text(page)
        page_segments = _extract_page_segments(page, page_index)
        has_images = _page_has_images(page)
        text_by_page.append(page_text)
        raw_segments.extend(page_segments)
        inspections.append(
            _PageInspection(
                page=page_index,
                kind=_classify_page(page_segments, has_images),
                vector_segment_count=len(page_segments),
                has_images=has_images,
                text_length=len(page_text.strip()),
            )
        )

    text = "\n".join(text_by_page)
    normalized_text = _normalize_text(text)
    do_not_scale = _contains_do_not_scale_notice(normalized_text)
    if do_not_scale and scale_denominator is None and calibration_pixels is None:
        raise PdfScaleMissingError(
            "PDF zawiera ostrzezenie, ze rysunku nie wolno skalowac. "
            "Podaj znana skale lub wymiar kalibracyjny przed pomiarem."
        )

    denominator = float(scale_denominator) if scale_denominator is not None else _detect_scale_denominator(text)
    calibration_units_per_meter = _calibration_units_per_meter(
        calibration_pixels,
        calibration_meters,
        raster_dpi,
    )
    if not denominator and calibration_units_per_meter is None:
        raise PdfScaleMissingError(
            "Nie znaleziono skali w PDF. Podaj mianownik skali, np. 100 dla 1:100, "
            "albo skalibruj znany odcinek."
        )
    if denominator is not None and denominator <= 0:
        raise PdfImportError("Mianownik skali musi byc wiekszy od zera.")

    pdf_kind = _overall_pdf_kind(inspections)
    use_raster = force_raster or not raw_segments
    method = "raster_image_calibrated" if use_raster else "vector_geometry_pdf_points_scaled"
    coordinate_origin = "image_top_left" if use_raster else "pdf_bottom_left"
    if use_raster:
        raster_min_length = max(min_segment_length, DEFAULT_RASTER_MIN_SEGMENT_LENGTH_PT)
        raw_segments = _extract_raster_segments(
            source,
            dpi=raster_dpi,
            min_segment_length=raster_min_length,
        )
    merged_segments = _merge_segments(
        segment for segment in raw_segments if segment.length >= min_segment_length
    )
    if not merged_segments:
        raise PdfImportError(
            f"Nie znaleziono odcinkow scian w PDF ({pdf_kind}). "
            "Dla skanu podaj wyrazny rzut, znany odcinek kalibracyjny i sprawdz prog wykrywania."
        )

    scale_label = (
        f"kalibracja {calibration_meters:g} m"
        if calibration_units_per_meter is not None
        else _format_scale_label(float(denominator))
    )
    drawing_units_per_meter = (
        calibration_units_per_meter
        if calibration_units_per_meter is not None
        else POINTS_PER_METER_AT_FULL_SCALE / float(denominator)
    )
    wall_candidates, opening_warnings = _detect_openings(
        merged_segments,
        raw_segments,
        drawing_units_per_meter=drawing_units_per_meter,
        use_raster=use_raster,
    )
    wall_tags = _extract_positioned_wall_tags(
        source,
        use_raster_coordinates=use_raster,
    )
    wall_candidates, tag_warnings, tag_filter_info = _apply_wall_tag_guidance(
        wall_candidates,
        wall_tags,
        drawing_units_per_meter=drawing_units_per_meter,
    )
    scale_source = _scale_source(scale_denominator, calibration_units_per_meter)
    warnings = _build_pdf_warnings(pdf_kind, inspections, do_not_scale)
    warnings.extend(opening_warnings)
    warnings.extend(tag_warnings)
    if use_raster:
        warnings.append(
            "Pomiar ze skanu/obrazu jest wnioskowany z pikseli; sprawdz odcinki w overlay przed uzyciem wynikow."
        )
    swedish_context = _build_swedish_context(text, normalized_text, denominator)
    wall_type_legend = _build_swedish_wall_type_legend(swedish_context)
    if swedish_context.get("iv_note"):
        warnings.append(swedish_context["iv_note"])

    exterior_ids = _guess_exterior_segment_ids([candidate.segment for candidate in wall_candidates])
    wall_segments = tuple(
        WallSegment(
            id=f"P{candidate.segment.page:02d}-W-{index:04d}",
            type_code=(
                candidate.type_code
                if candidate.type_code != "PDF"
                else ("EXT" if index in exterior_ids else "PDF")
            ),
            start=candidate.segment.start,
            end=candidate.segment.end,
            page=candidate.segment.page,
            confidence=_segment_confidence(
                use_raster,
                index in exterior_ids,
                candidate.type_code != "PDF",
            ),
            exterior=index in exterior_ids or candidate.type_code.startswith("YV"),
            measurement_basis=method,
            centerline_or_face="unclear",
            openings=candidate.openings,
            comment=_segment_comment(use_raster, candidate),
        )
        for index, candidate in enumerate(wall_candidates, start=1)
    )

    page_numbers = tuple(range(1, len(reader.pages) + 1))
    openings_detected = sum(len(candidate.openings) for candidate in wall_candidates)
    source_metadata: dict[str, Any] = {
        "file": source.name,
        "source_pdf": str(source.resolve()),
        "page_count": len(reader.pages),
        "pdf_kind": pdf_kind,
        "pages": [inspection.__dict__ for inspection in inspections],
        "scale": scale_label,
        "scale_source": scale_source,
        "calibration": _calibration_metadata(calibration_pixels, calibration_meters, raster_dpi),
        "units": "m",
        "method": method,
        "opening_detection_method": "gap_and_symbol_heuristics",
        "openings_detected": openings_detected,
        "wall_tag_detection_method": "positioned_text_nearest_connected_wall_segments",
        "wall_tags_detected": [
            {
                "page": tag.page,
                "code": tag.code,
                "original": tag.original,
                "x": round(tag.center.x, 3),
                "y": round(tag.center.y, 3),
            }
            for tag in wall_tags
        ],
        "tag_guided_filtering": tag_filter_info,
        "coordinate_origin": coordinate_origin,
        "measurement_basis": (
            "raster image line detection after calibration"
            if use_raster
            else "vector geometry from PDF drawing operators"
        ),
        "centerline_or_face": "unclear",
        "assumptions": [
            "Odcinki PDF sa traktowane jako linie scian; program nie rozroznia automatycznie osi, wewnetrznej i zewnetrznej krawedzi.",
            "Gdy PDF zawiera oznaczenia scian typu IV20, YV01 lub BV02, program przypisuje pobliskie polaczone odcinki do tych typow i pomija odcinki bez zwiazku z tagami.",
            "Drzwi i okna z PDF sa wykrywane heurystycznie jako przerwy w scianach z dodatkowymi symbolami lub typowa szerokoscia.",
            "Wyniki nalezy sprawdzic z oryginalnym CAD/BIM, oficjalnymi wymiarami albo pomiarem na miejscu przed zamowieniami, wycena lub wykonaniem prac.",
        ],
        "warnings": warnings,
    }
    if swedish_context:
        source_metadata["swedish_plan_context"] = swedish_context
    if wall_type_legend:
        source_metadata["wall_type_legend"] = wall_type_legend

    return AnalysisInput(
        project_name=source.stem,
        scale=Scale(
            drawing_units_per_meter=drawing_units_per_meter,
            label=scale_label,
        ),
        scope=AnalysisScope(
            pages=page_numbers,
            description="Automatycznie rozpoznane odcinki z PDF wektorowego",
        ),
        wall_types=_build_pdf_wall_types(wall_tags),
        wall_segments=wall_segments,
        source_metadata=source_metadata,
    )


def _safe_extract_text(page: Any) -> str:
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def _detect_scale_denominator(text: str) -> float | None:
    patterns = (
        r"(?:skala|scale)?\s*1\s*[:/]\s*(\d+(?:[.,]\d+)?)",
        r"(?:skala|scale)\s+1\s+(\d+(?:[.,]\d+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _calibration_units_per_meter(
    calibration_pixels: float | None,
    calibration_meters: float | None,
    raster_dpi: int,
) -> float | None:
    if calibration_pixels is None and calibration_meters is None:
        return None
    if calibration_pixels is None or calibration_meters is None:
        raise PdfImportError("Kalibracja wymaga wartosci calibration_pixels i calibration_meters.")
    if calibration_pixels <= 0 or calibration_meters <= 0:
        raise PdfImportError("Kalibracja wymaga dodatniej dlugosci w pikselach i metrach.")
    render_scale = raster_dpi / 72.0
    pdf_points = calibration_pixels / render_scale
    return pdf_points / calibration_meters


def _scale_source(
    scale_denominator: float | None,
    calibration_units_per_meter: float | None,
) -> str:
    if calibration_units_per_meter is not None:
        return "known_segment_calibration"
    if scale_denominator is not None:
        return "user_provided"
    return "pdf_text"


def _calibration_metadata(
    calibration_pixels: float | None,
    calibration_meters: float | None,
    raster_dpi: int,
) -> dict[str, float | int] | None:
    if calibration_pixels is None or calibration_meters is None:
        return None
    return {
        "known_distance_px": round(calibration_pixels, 3),
        "known_distance_m": round(calibration_meters, 3),
        "render_dpi": raster_dpi,
        "pdf_points_per_meter": round(
            _calibration_units_per_meter(calibration_pixels, calibration_meters, raster_dpi) or 0,
            6,
        ),
    }


def _segment_confidence(use_raster: bool, exterior: bool, tagged: bool = False) -> float:
    if tagged and use_raster:
        return 0.66 if exterior else 0.7
    if tagged:
        return 0.84 if exterior else 0.86
    if use_raster:
        return 0.58 if exterior else 0.62
    return 0.76 if exterior else 0.78


def _segment_comment(use_raster: bool, candidate: _WallCandidate) -> str:
    if candidate.type_code != "PDF":
        distance_note = ""
        if candidate.tag_distance is not None:
            distance_note = f" Najblizszy tag w odleglosci {candidate.tag_distance:.1f} jednostek rysunku."
        basis = (
            "Pomiar z obrazu rastrowego po kalibracji."
            if use_raster
            else "Pomiar z geometrii wektorowej PDF."
        )
        return (
            f"{basis} Odcinek powiazany z oznaczeniem sciany {candidate.type_code}; "
            f"krawedz/os wymaga kontroli na overlay.{distance_note}"
        )
    if use_raster:
        return "Pomiar z obrazu rastrowego po kalibracji; typ sciany i krawedz/os wymagaja kontroli."
    return "Pomiar z geometrii wektorowej PDF; typ sciany i krawedz/os wymagaja kontroli na overlay."


def _build_pdf_wall_types(wall_tags: list[_WallTag]) -> dict[str, WallType]:
    wall_types = {
        "PDF": WallType(
            code="PDF",
            name="Sciana z PDF - typ nierozpoznany",
            color="#2563EB",
        ),
        "EXT": WallType(
            code="EXT",
            name="Krawedz zewnetrzna z PDF - heurystyka",
            color="#111827",
            exterior=True,
        ),
    }
    for code in sorted({tag.code for tag in wall_tags}):
        wall_types[code] = WallType(
            code=code,
            name=_wall_type_name_from_tag(code),
            color=_wall_type_color_from_tag(code),
            exterior=code.startswith("YV"),
            rules={"source": "pdf_wall_tag"},
        )
    return wall_types


def _wall_type_name_from_tag(code: str) -> str:
    if code.startswith("IV"):
        return f"Sciana wewnetrzna {code} z PDF"
    if code.startswith("YV"):
        return f"Sciana zewnetrzna {code} z PDF"
    if code.startswith("BV"):
        return f"Sciana nosna {code} z PDF - wymaga potwierdzenia"
    if code.startswith("LV") or code.startswith("LIV"):
        return f"Lekka sciana {code} z PDF - wymaga potwierdzenia"
    return f"Sciana {code} z PDF"


def _wall_type_color_from_tag(code: str) -> str:
    if code in TAG_COLOR_OVERRIDES:
        return TAG_COLOR_OVERRIDES[code]
    slot = sum(ord(character) for character in code) % len(TAG_COLOR_PALETTE)
    return TAG_COLOR_PALETTE[slot]


def _extract_positioned_wall_tags(
    source: Path,
    *,
    use_raster_coordinates: bool,
) -> list[_WallTag]:
    try:
        import fitz  # type: ignore
    except ImportError:  # pragma: no cover - dependency is optional for old installs
        return []

    tags: dict[tuple[int, str, int, int], _WallTag] = {}
    try:
        with fitz.open(str(source)) as document:
            for page_index, page in enumerate(document, start=1):
                words = page.get_text("words") or []
                page_height = float(page.rect.height)
                for index, word in enumerate(words):
                    candidates = [_word_tag_candidate(word)]
                    if index + 1 < len(words) and _words_share_line(word, words[index + 1]):
                        candidates.append(_joined_word_tag_candidate(word, words[index + 1]))
                    for text, rect in candidates:
                        code = _normalize_wall_tag_code(text)
                        if not code:
                            continue
                        center = _tag_center(
                            rect,
                            page_height=page_height,
                            use_raster_coordinates=use_raster_coordinates,
                        )
                        if not _is_isolated_plan_tag(center, words, page_height, use_raster_coordinates):
                            continue
                        key = (page_index, code, round(center.x), round(center.y))
                        tags[key] = _WallTag(
                            page=page_index,
                            code=code,
                            center=center,
                            original=text.strip(),
                        )
    except Exception:
        return []
    return sorted(tags.values(), key=lambda tag: (tag.page, tag.center.y, tag.center.x, tag.code))


def _word_tag_candidate(word: Any) -> tuple[str, tuple[float, float, float, float]]:
    return str(word[4]), (float(word[0]), float(word[1]), float(word[2]), float(word[3]))


def _joined_word_tag_candidate(
    first: Any,
    second: Any,
) -> tuple[str, tuple[float, float, float, float]]:
    text = f"{first[4]} {second[4]}"
    rect = (
        min(float(first[0]), float(second[0])),
        min(float(first[1]), float(second[1])),
        max(float(first[2]), float(second[2])),
        max(float(first[3]), float(second[3])),
    )
    return text, rect


def _words_share_line(first: Any, second: Any) -> bool:
    if len(first) >= 7 and len(second) >= 7:
        return first[5] == second[5] and first[6] == second[6]
    y1 = (float(first[1]) + float(first[3])) / 2
    y2 = (float(second[1]) + float(second[3])) / 2
    return abs(y1 - y2) <= 3.0


def _normalize_wall_tag_code(text: str) -> str | None:
    clean = unicodedata.normalize("NFKC", text).upper()
    clean = clean.replace("\u2010", "-").replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    clean = re.sub(r"[^A-Z0-9 -]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    match = re.fullmatch(r"(LIV|IV|YV|BV|LV)\s*-?\s*(\d{1,3})", clean)
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


def _tag_center(
    rect: tuple[float, float, float, float],
    *,
    page_height: float,
    use_raster_coordinates: bool,
) -> Point:
    x = (rect[0] + rect[2]) / 2
    y_from_top = (rect[1] + rect[3]) / 2
    y = y_from_top if use_raster_coordinates else page_height - y_from_top
    return Point(x, y)


def _is_isolated_plan_tag(
    center: Point,
    words: list[Any],
    page_height: float,
    use_raster_coordinates: bool,
) -> bool:
    nearby_words = 0
    for word in words:
        _, rect = _word_tag_candidate(word)
        word_center = _tag_center(
            rect,
            page_height=page_height,
            use_raster_coordinates=use_raster_coordinates,
        )
        if center.distance_to(word_center) <= 26.0:
            nearby_words += 1
    return nearby_words <= 4


def _apply_wall_tag_guidance(
    candidates: list[_WallCandidate],
    wall_tags: list[_WallTag],
    *,
    drawing_units_per_meter: float,
) -> tuple[list[_WallCandidate], list[str], dict[str, Any]]:
    info: dict[str, Any] = {
        "enabled": False,
        "tag_count": len(wall_tags),
        "direct_matches": 0,
        "kept_segments": len(candidates),
        "skipped_segments": 0,
    }
    if not candidates or not wall_tags or drawing_units_per_meter <= 0:
        return candidates, [], info

    direct_radius = max(24.0, drawing_units_per_meter * TAG_ASSIGN_RADIUS_M)
    connection_tolerance = max(AXIS_TOLERANCE_PT * 3, drawing_units_per_meter * TAG_CONNECTION_TOLERANCE_M)
    propagation_radius = max(direct_radius, drawing_units_per_meter * TAG_PROPAGATION_RADIUS_M)
    min_wall_length = max(DEFAULT_MIN_SEGMENT_LENGTH_PT, drawing_units_per_meter * TAG_MIN_SEGMENT_LENGTH_M)

    direct_assignments: dict[int, tuple[_WallTag, float]] = {}
    for tag in wall_tags:
        nearest = _nearest_candidate_for_tag(
            tag,
            candidates,
            max_distance=direct_radius,
            min_wall_length=min_wall_length,
        )
        if nearest is None:
            continue
        index, distance = nearest
        current = direct_assignments.get(index)
        if current is None or distance < current[1]:
            direct_assignments[index] = (tag, distance)

    info["direct_matches"] = len(direct_assignments)
    if not direct_assignments:
        return candidates, [
            "Znaleziono oznaczenia typow scian, ale nie lezaly wystarczajaco blisko odcinkow scian; nie wlaczono filtrowania po tagach."
        ], info

    assignments = _propagate_tag_assignments(
        candidates,
        direct_assignments,
        connection_tolerance=connection_tolerance,
        propagation_radius=propagation_radius,
        min_wall_length=min_wall_length,
    )
    if not assignments:
        return candidates, [], info

    filtered: list[_WallCandidate] = []
    for index, candidate in enumerate(candidates):
        assignment = assignments.get(index)
        if assignment is None:
            continue
        tag, distance = assignment
        filtered.append(
            _WallCandidate(
                segment=candidate.segment,
                openings=candidate.openings,
                type_code=tag.code,
                tag_distance=distance,
            )
        )

    if not filtered:
        return candidates, [], info

    skipped = len(candidates) - len(filtered)
    info.update(
        {
            "enabled": True,
            "kept_segments": len(filtered),
            "skipped_segments": skipped,
            "tag_codes": sorted({tag.code for tag in wall_tags}),
        }
    )
    warnings: list[str] = []
    if skipped:
        warnings.append(
            "Zastosowano filtrowanie po oznaczeniach scian "
            f"({', '.join(info['tag_codes'])}): zachowano {len(filtered)} odcinkow, "
            f"pominieto {skipped} odcinkow bez zwiazku z tagami, np. schody, meble lub armature."
        )
    else:
        warnings.append(
            "Zastosowano przypisanie odcinkow do oznaczen scian "
            f"({', '.join(info['tag_codes'])})."
        )
    return filtered, warnings, info


def _nearest_candidate_for_tag(
    tag: _WallTag,
    candidates: list[_WallCandidate],
    *,
    max_distance: float,
    min_wall_length: float,
) -> tuple[int, float] | None:
    best: tuple[int, float] | None = None
    for index, candidate in enumerate(candidates):
        segment = candidate.segment
        if segment.page != tag.page or not _is_wall_tag_candidate_segment(segment, min_wall_length):
            continue
        distance = _point_to_segment_distance(tag.center, segment)
        if distance > max_distance:
            continue
        if best is None or distance < best[1]:
            best = (index, distance)
    return best


def _propagate_tag_assignments(
    candidates: list[_WallCandidate],
    direct_assignments: dict[int, tuple[_WallTag, float]],
    *,
    connection_tolerance: float,
    propagation_radius: float,
    min_wall_length: float,
) -> dict[int, tuple[_WallTag, float]]:
    assignments = dict(direct_assignments)
    for start_index, (tag, _distance) in direct_assignments.items():
        queue: list[tuple[int, int]] = [(start_index, 0)]
        visited = {start_index}
        while queue:
            current_index, depth = queue.pop(0)
            if depth >= TAG_PROPAGATION_MAX_DEPTH:
                continue
            current_segment = candidates[current_index].segment
            for next_index, candidate in enumerate(candidates):
                if next_index in visited or next_index in assignments:
                    continue
                next_segment = candidate.segment
                if next_segment.page != tag.page:
                    continue
                if not _is_wall_tag_candidate_segment(next_segment, min_wall_length):
                    continue
                distance = _point_to_segment_distance(tag.center, next_segment)
                if distance > propagation_radius:
                    continue
                if not _segments_connected(current_segment, next_segment, connection_tolerance):
                    continue
                assignments[next_index] = (tag, distance)
                visited.add(next_index)
                queue.append((next_index, depth + 1))
    return assignments


def _is_wall_tag_candidate_segment(segment: _VectorSegment, min_wall_length: float) -> bool:
    return segment.length >= min_wall_length and _axis(segment) is not None


def _segments_connected(first: _VectorSegment, second: _VectorSegment, tolerance: float) -> bool:
    if first.page != second.page:
        return False
    first_points = (first.start, first.end)
    second_points = (second.start, second.end)
    return any(a.distance_to(b) <= tolerance for a in first_points for b in second_points)


def _point_to_segment_distance(point: Point, segment: _VectorSegment) -> float:
    ax = segment.start.x
    ay = segment.start.y
    bx = segment.end.x
    by = segment.end.y
    dx = bx - ax
    dy = by - ay
    length_squared = dx * dx + dy * dy
    if length_squared <= 0:
        return point.distance_to(segment.start)
    t = ((point.x - ax) * dx + (point.y - ay) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    projection = Point(ax + t * dx, ay + t * dy)
    return point.distance_to(projection)


def _detect_openings(
    segments: list[_VectorSegment],
    evidence_segments: list[_VectorSegment],
    *,
    drawing_units_per_meter: float,
    use_raster: bool,
) -> tuple[list[_WallCandidate], list[str]]:
    grouped: dict[tuple[int, str, int], list[tuple[float, float, _VectorSegment]]] = {}
    candidates: list[_WallCandidate] = []
    auxiliary_keys: set[tuple[Any, ...]] = set()
    opening_count = 0

    for segment in segments:
        axis = _axis(segment)
        if axis is None:
            candidates.append(_WallCandidate(segment))
            continue
        fixed = _fixed_coordinate(segment, axis)
        start, end = _axis_interval(segment, axis)
        grouped.setdefault(
            (segment.page, axis, round(fixed / AXIS_TOLERANCE_PT)),
            [],
        ).append((start, end, segment))

    for (page, axis, fixed_key), intervals in grouped.items():
        fixed = fixed_key * AXIS_TOLERANCE_PT
        intervals.sort(key=lambda item: item[0])
        if not intervals:
            continue

        current_start, current_end, first_segment = intervals[0]
        current_openings: list[Opening] = []
        for next_start, next_end, _next_segment in intervals[1:]:
            gap_width = next_start - current_end
            opening = _classify_opening_gap(
                page=page,
                axis=axis,
                fixed=fixed,
                gap_start=current_end,
                gap_end=next_start,
                evidence_segments=evidence_segments,
                drawing_units_per_meter=drawing_units_per_meter,
                use_raster=use_raster,
            )
            if opening is not None and gap_width > JOIN_TOLERANCE_PT:
                kind, evidence_keys = opening
                opening_count += 1
                current_openings.append(
                    Opening(
                        kind=kind,
                        width=gap_width,
                        label=f"{kind.upper()}-{opening_count:03d}",
                        offset=((current_end + next_start) / 2) - current_start,
                    )
                )
                auxiliary_keys.update(evidence_keys)
                current_end = max(current_end, next_end)
            elif gap_width <= JOIN_TOLERANCE_PT:
                current_end = max(current_end, next_end)
            else:
                candidate_segment = _segment_from_axis_interval(
                    page,
                    axis,
                    fixed,
                    current_start,
                    current_end,
                )
                candidates.append(_WallCandidate(candidate_segment, tuple(current_openings)))
                current_start, current_end = next_start, next_end
                current_openings = []

        candidate_segment = _segment_from_axis_interval(
            page,
            axis,
            fixed,
            current_start,
            current_end,
        )
        candidates.append(_WallCandidate(candidate_segment, tuple(current_openings)))

    filtered = [
        candidate
        for candidate in candidates
        if _segment_key(candidate.segment) not in auxiliary_keys
    ]
    warnings = []
    if opening_count:
        warnings.append(
            f"Wykryto heurystycznie otwory drzwiowe/okienne: {opening_count}. Sprawdz je na overlay przed uzyciem netto."
        )
    return sorted(
        filtered,
        key=lambda item: (
            item.segment.page,
            round(item.segment.start.y, 2),
            round(item.segment.start.x, 2),
        ),
    ), warnings


def _classify_opening_gap(
    *,
    page: int,
    axis: str,
    fixed: float,
    gap_start: float,
    gap_end: float,
    evidence_segments: list[_VectorSegment],
    drawing_units_per_meter: float,
    use_raster: bool,
) -> tuple[str, set[tuple[Any, ...]]] | None:
    gap_width = gap_end - gap_start
    if gap_width <= 0 or drawing_units_per_meter <= 0:
        return None
    gap_m = gap_width / drawing_units_per_meter
    if gap_m < MIN_OPENING_WIDTH_M or gap_m > MAX_OPENING_WIDTH_M:
        return None

    window_evidence = _parallel_opening_evidence(
        page=page,
        axis=axis,
        fixed=fixed,
        gap_start=gap_start,
        gap_end=gap_end,
        evidence_segments=evidence_segments,
    )
    if window_evidence:
        return "window", window_evidence

    door_evidence = _door_swing_evidence(
        page=page,
        axis=axis,
        fixed=fixed,
        gap_start=gap_start,
        gap_end=gap_end,
        evidence_segments=evidence_segments,
    )
    if door_evidence:
        return "door", door_evidence

    if gap_m <= MAX_DOOR_WIDTH_M:
        return "door", set()
    if use_raster:
        return "window", set()
    return "opening", set()


def _parallel_opening_evidence(
    *,
    page: int,
    axis: str,
    fixed: float,
    gap_start: float,
    gap_end: float,
    evidence_segments: list[_VectorSegment],
) -> set[tuple[Any, ...]]:
    evidence: set[tuple[Any, ...]] = set()
    gap_width = gap_end - gap_start
    for segment in evidence_segments:
        if segment.page != page or _axis(segment) != axis:
            continue
        evidence_fixed = _fixed_coordinate(segment, axis)
        distance = abs(evidence_fixed - fixed)
        if distance <= AXIS_TOLERANCE_PT or distance > OPENING_EVIDENCE_TOLERANCE_PT:
            continue
        start, end = _axis_interval(segment, axis)
        overlap = min(end, gap_end) - max(start, gap_start)
        if overlap >= gap_width * 0.45:
            evidence.add(_segment_key(segment))
    return evidence


def _door_swing_evidence(
    *,
    page: int,
    axis: str,
    fixed: float,
    gap_start: float,
    gap_end: float,
    evidence_segments: list[_VectorSegment],
) -> set[tuple[Any, ...]]:
    evidence: set[tuple[Any, ...]] = set()
    gap_width = gap_end - gap_start
    anchors = _gap_anchor_points(axis, fixed, gap_start, gap_end)
    for segment in evidence_segments:
        if segment.page != page or _axis(segment) == axis:
            continue
        length = segment.length
        if length < gap_width * 0.45 or length > gap_width * 1.6:
            continue
        endpoints = (segment.start, segment.end)
        if any(point.distance_to(anchor) <= OPENING_EVIDENCE_TOLERANCE_PT for point in endpoints for anchor in anchors):
            evidence.add(_segment_key(segment))
    return evidence


def _gap_anchor_points(axis: str, fixed: float, gap_start: float, gap_end: float) -> tuple[Point, Point]:
    if axis == "h":
        return Point(gap_start, fixed), Point(gap_end, fixed)
    return Point(fixed, gap_start), Point(fixed, gap_end)


def _axis(segment: _VectorSegment) -> str | None:
    dx = abs(segment.end.x - segment.start.x)
    dy = abs(segment.end.y - segment.start.y)
    if dy <= AXIS_TOLERANCE_PT and dx > AXIS_TOLERANCE_PT:
        return "h"
    if dx <= AXIS_TOLERANCE_PT and dy > AXIS_TOLERANCE_PT:
        return "v"
    return None


def _fixed_coordinate(segment: _VectorSegment, axis: str) -> float:
    if axis == "h":
        return (segment.start.y + segment.end.y) / 2
    return (segment.start.x + segment.end.x) / 2


def _axis_interval(segment: _VectorSegment, axis: str) -> tuple[float, float]:
    if axis == "h":
        return tuple(sorted((segment.start.x, segment.end.x)))
    return tuple(sorted((segment.start.y, segment.end.y)))


def _segment_from_axis_interval(
    page: int,
    axis: str,
    fixed: float,
    start: float,
    end: float,
) -> _VectorSegment:
    if axis == "h":
        return _VectorSegment(page, Point(start, fixed), Point(end, fixed))
    return _VectorSegment(page, Point(fixed, start), Point(fixed, end))


def _segment_key(segment: _VectorSegment) -> tuple[Any, ...]:
    axis = _axis(segment)
    if axis == "h":
        fixed = round(((segment.start.y + segment.end.y) / 2) / AXIS_TOLERANCE_PT) * AXIS_TOLERANCE_PT
        x1, x2 = sorted((segment.start.x, segment.end.x))
        start = (round(x1, 2), round(fixed, 2))
        end = (round(x2, 2), round(fixed, 2))
    elif axis == "v":
        fixed = round(((segment.start.x + segment.end.x) / 2) / AXIS_TOLERANCE_PT) * AXIS_TOLERANCE_PT
        y1, y2 = sorted((segment.start.y, segment.end.y))
        start = (round(fixed, 2), round(y1, 2))
        end = (round(fixed, 2), round(y2, 2))
    else:
        start = (round(segment.start.x, 2), round(segment.start.y, 2))
        end = (round(segment.end.x, 2), round(segment.end.y, 2))
    a, b = sorted((start, end))
    return segment.page, a, b


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower())


def _contains_do_not_scale_notice(normalized_text: str) -> bool:
    terms = (
        "not to scale",
        "do not scale",
        "ej skalenlig",
        "matt far ej skalas",
        "matt far ej tas fran ritning",
        "matt kontrolleras pa plats",
    )
    return any(term in normalized_text for term in terms)


def _format_scale_label(denominator: float) -> str:
    denominator = float(denominator)
    if denominator.is_integer():
        return f"1:{int(denominator)}"
    return f"1:{denominator:g}"


def _extract_page_segments(page: Any, page_number: int) -> list[_VectorSegment]:
    try:
        from pypdf.generic import ContentStream
    except ImportError as exc:  # pragma: no cover
        raise PdfImportError("Brakuje biblioteki pypdf.") from exc

    contents = page.get_contents()
    if contents is None:
        return []

    stream = ContentStream(contents, page.pdf)
    segments: list[_VectorSegment] = []
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    stack: list[tuple[float, float, float, float, float, float]] = []
    current: Point | None = None
    subpath_start: Point | None = None
    path_segments: list[_VectorSegment] = []

    for operands, operator in stream.operations:
        op = _operator_name(operator)

        if op == "q":
            stack.append(ctm)
        elif op == "Q":
            ctm = stack.pop() if stack else ctm
        elif op == "cm" and len(operands) == 6:
            ctm = _multiply_matrix(ctm, tuple(float(value) for value in operands))
        elif op == "m" and len(operands) >= 2:
            current = _transform_point(float(operands[0]), float(operands[1]), ctm)
            subpath_start = current
        elif op == "l" and len(operands) >= 2:
            next_point = _transform_point(float(operands[0]), float(operands[1]), ctm)
            if current is not None:
                path_segments.append(_VectorSegment(page_number, current, next_point))
            current = next_point
        elif op == "re" and len(operands) >= 4:
            path_segments.extend(_rectangle_segments(operands, ctm, page_number))
            current = None
            subpath_start = None
        elif op == "h":
            if current is not None and subpath_start is not None:
                path_segments.append(_VectorSegment(page_number, current, subpath_start))
                current = subpath_start
        elif op in {"S", "s", "B", "B*", "b", "b*"}:
            if op in {"s", "b", "b*"} and current is not None and subpath_start is not None:
                path_segments.append(_VectorSegment(page_number, current, subpath_start))
            segments.extend(path_segments)
            path_segments = []
            current = None
            subpath_start = None
        elif op in {"n", "f", "F", "f*", "W", "W*"}:
            path_segments = []
            current = None
            subpath_start = None

    return segments


def _extract_raster_segments(
    source: Path,
    *,
    dpi: int,
    min_segment_length: float,
) -> list[_VectorSegment]:
    try:
        import fitz  # type: ignore
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on user environment
        raise PdfImportError(
            "Do rozpoznawania skanow potrzebne sa biblioteki PyMuPDF i numpy."
        ) from exc

    render_scale = dpi / 72.0
    min_run_px = max(int(min_segment_length * render_scale), 24)
    segments: list[_VectorSegment] = []
    with fitz.open(str(source)) as document:
        for page_index, page in enumerate(document, start=1):
            matrix = fitz.Matrix(render_scale, render_scale)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
            image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height,
                pixmap.width,
                pixmap.n,
            )
            gray = image[:, :, :3].mean(axis=2)
            dark = gray < DEFAULT_RASTER_DARK_THRESHOLD
            segments.extend(
                _segments_from_raster_mask(
                    dark,
                    page_index=page_index,
                    render_scale=render_scale,
                    min_run_px=min_run_px,
                )
            )
    return segments


def _segments_from_raster_mask(
    dark_mask: Any,
    *,
    page_index: int,
    render_scale: float,
    min_run_px: int,
) -> list[_VectorSegment]:
    segments: list[_VectorSegment] = []
    segments.extend(
        _runs_to_segments(
            _detect_runs(dark_mask, min_run_px=min_run_px, horizontal=True),
            page_index=page_index,
            render_scale=render_scale,
            horizontal=True,
        )
    )
    segments.extend(
        _runs_to_segments(
            _detect_runs(dark_mask, min_run_px=min_run_px, horizontal=False),
            page_index=page_index,
            render_scale=render_scale,
            horizontal=False,
        )
    )
    return segments


def _detect_runs(
    mask: Any,
    *,
    min_run_px: int,
    horizontal: bool,
) -> list[tuple[int, int, int]]:
    import numpy as np

    source = mask if horizontal else mask.T
    runs: list[tuple[int, int, int]] = []
    for fixed, values in enumerate(source):
        padded = np.concatenate(([False], values.astype(bool), [False]))
        changes = np.flatnonzero(padded[1:] != padded[:-1])
        for start, end in zip(changes[0::2], changes[1::2]):
            if end - start >= min_run_px:
                runs.append((fixed, int(start), int(end)))
    return _merge_pixel_runs(runs, tolerance_px=12)


def _merge_pixel_runs(
    runs: list[tuple[int, int, int]],
    *,
    tolerance_px: int,
) -> list[tuple[int, int, int]]:
    groups: list[tuple[int, int, int, int]] = []
    for fixed, start, end in runs:
        matched = False
        for index, (group_fixed, group_start, group_end, count) in enumerate(groups):
            overlaps = start <= group_end + tolerance_px and end >= group_start - tolerance_px
            close = abs(fixed - group_fixed) <= tolerance_px
            if close and overlaps:
                new_count = count + 1
                groups[index] = (
                    round((group_fixed * count + fixed) / new_count),
                    min(group_start, start),
                    max(group_end, end),
                    new_count,
                )
                matched = True
                break
        if not matched:
            groups.append((fixed, start, end, 1))
    return [(fixed, start, end) for fixed, start, end, _ in groups]


def _runs_to_segments(
    runs: list[tuple[int, int, int]],
    *,
    page_index: int,
    render_scale: float,
    horizontal: bool,
) -> list[_VectorSegment]:
    segments: list[_VectorSegment] = []
    for fixed, start, end in runs:
        if horizontal:
            start_point = Point(start / render_scale, fixed / render_scale)
            end_point = Point(end / render_scale, fixed / render_scale)
        else:
            start_point = Point(fixed / render_scale, start / render_scale)
            end_point = Point(fixed / render_scale, end / render_scale)
        segments.append(_VectorSegment(page_index, start_point, end_point))
    return segments


def _page_has_images(page: Any) -> bool:
    resources = _resolve_pdf_object(page.get("/Resources"))
    return _resources_have_images(resources, set())


def _resources_have_images(resources: Any, seen: set[int]) -> bool:
    resources = _resolve_pdf_object(resources)
    if not resources:
        return False
    object_id = id(resources)
    if object_id in seen:
        return False
    seen.add(object_id)
    xobjects = _resolve_pdf_object(resources.get("/XObject", {}))
    if not xobjects:
        return False
    for xobject in xobjects.values():
        resolved = _resolve_pdf_object(xobject)
        subtype = str(resolved.get("/Subtype", ""))
        if subtype == "/Image":
            return True
        if subtype == "/Form" and _resources_have_images(resolved.get("/Resources"), seen):
            return True
    return False


def _resolve_pdf_object(value: Any) -> Any:
    try:
        return value.get_object()
    except Exception:
        return value


def _classify_page(segments: list[_VectorSegment], has_images: bool) -> str:
    has_vectors = bool(segments)
    if has_vectors and has_images:
        return "mixed"
    if has_vectors:
        return "vector"
    if has_images:
        return "raster"
    return "empty"


def _overall_pdf_kind(inspections: list[_PageInspection]) -> str:
    kinds = {inspection.kind for inspection in inspections}
    if not kinds:
        return "empty"
    if kinds == {"vector"}:
        return "vector"
    if kinds <= {"raster", "empty"} and "raster" in kinds:
        return "raster"
    if kinds == {"empty"}:
        return "empty"
    return "mixed"


def _build_pdf_warnings(
    pdf_kind: str,
    inspections: list[_PageInspection],
    do_not_scale: bool,
) -> list[str]:
    warnings: list[str] = []
    if pdf_kind == "mixed":
        warnings.append(
            "PDF jest mieszany: zmierzono tylko odcinki wektorowe, a elementy rastrowe/skanowane wymagaja osobnej kontroli."
        )
    if do_not_scale:
        warnings.append(
            "PDF zawiera ostrzezenie dotyczace skalowania; pomiar wykonano tylko dlatego, ze podano skale z zewnatrz."
        )
    raster_pages = [str(item.page) for item in inspections if item.kind == "raster"]
    if raster_pages:
        warnings.append(
            "Strony rastrowe/skanowane bez pomiaru wektorowego: " + ", ".join(raster_pages)
        )
    return warnings


def _build_swedish_context(
    text: str,
    normalized_text: str,
    denominator: float | None,
) -> dict[str, Any]:
    tags = _extract_swedish_wall_tags(text)
    swedish_terms = (
        "planritning",
        "bygghandling",
        "a-ritning",
        "k-ritning",
        "ritningsnummer",
        "forklaringar",
        "vaggtyper",
        "typvaggar",
        "brand",
        "ljud",
        "rivning",
        "befintligt",
        "nytt",
        "alla matt i mm",
    )
    if not tags and not any(term in normalized_text for term in swedish_terms):
        return {}

    legend_terms = ("forklaringar", "vaggtyper", "typvaggar", "materialforklaring")
    legend_found = any(term in normalized_text for term in legend_terms)
    unit_note = "Alla matt i mm" if "alla matt i mm" in normalized_text else ""
    iv_tags = [tag for tag in tags if _normalize_tag(tag).startswith("IV")]
    context: dict[str, Any] = {
        "drawing_type": _guess_swedish_drawing_type(normalized_text),
        "scale": _format_scale_label(denominator) if denominator else "calibrated",
        "units": "mm noted on drawing" if unit_note else "unknown",
        "unit_note": unit_note,
        "status": _guess_swedish_status(normalized_text),
        "legend_found": legend_found,
        "wall_tags": tags,
        "do_not_scale_note_found": _contains_do_not_scale_notice(normalized_text),
    }
    if iv_tags and not legend_found:
        context["iv_note"] = "IV nie zostalo jednoznacznie zdefiniowane w legendzie tego PDF."
    return context


def _extract_swedish_wall_tags(text: str) -> list[str]:
    matches = re.findall(
        r"\b(?:IV|YV|BV|EI\s*\d{2,3}|REI\s*\d{2,3})(?:\s*[-]?\s*\d{0,3})?\b",
        text,
        flags=re.IGNORECASE,
    )
    return sorted({re.sub(r"\s+", " ", match.strip().upper()) for match in matches})


def _normalize_tag(tag: str) -> str:
    return re.sub(r"[\s-]+", "", tag.upper())


def _guess_swedish_drawing_type(normalized_text: str) -> str:
    if "planritning" in normalized_text:
        return "planritning"
    if "a-ritning" in normalized_text:
        return "A-ritning"
    if "k-ritning" in normalized_text:
        return "K-ritning"
    return "unknown"


def _guess_swedish_status(normalized_text: str) -> str:
    for status in ("bygghandling", "relationshandling", "forfragningsunderlag"):
        if status in normalized_text:
            return status
    return "unknown"


def _build_swedish_wall_type_legend(
    swedish_context: dict[str, Any],
) -> list[dict[str, Any]]:
    tags = swedish_context.get("wall_tags", [])
    if not tags:
        return []
    legend_found = bool(swedish_context.get("legend_found"))
    legend: list[dict[str, Any]] = []
    for tag in tags:
        normalized = _normalize_tag(tag)
        thickness_match = re.search(r"(\d{2,3})$", normalized)
        thickness_mm = int(thickness_match.group(1)) if thickness_match else None
        if normalized.startswith("IV"):
            meaning = "sciana wewnetrzna, jezeli potwierdza to legenda"
            swedish_term = "innervagg"
        elif normalized.startswith("YV"):
            meaning = "sciana zewnetrzna, jezeli potwierdza to legenda"
            swedish_term = "yttervagg"
        elif normalized.startswith("BV"):
            meaning = "sciana nosna tylko po potwierdzeniu legenda lub rysunkiem K"
            swedish_term = "barande vagg"
        else:
            meaning = "klasa ogniowa lub oznaczenie wydajnosci, nie sam typ sciany"
            swedish_term = "performance tag"
        legend.append(
            {
                "tag_original": tag,
                "tag_normalized": normalized,
                "swedish_term": swedish_term,
                "meaning_pl": meaning,
                "thickness_mm": thickness_mm if legend_found else None,
                "status": "unconfirmed" if not legend_found else "from_text",
                "confidence": "medium" if legend_found else "low",
            }
        )
    return legend


def _operator_name(operator: Any) -> str:
    if isinstance(operator, bytes):
        return operator.decode("latin1")
    return str(operator)


def _transform_point(
    x: float,
    y: float,
    matrix: tuple[float, float, float, float, float, float],
) -> Point:
    a, b, c, d, e, f = matrix
    return Point(x=a * x + c * y + e, y=b * x + d * y + f)


def _multiply_matrix(
    left: tuple[float, float, float, float, float, float],
    right: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _rectangle_segments(
    operands: list[Any],
    matrix: tuple[float, float, float, float, float, float],
    page_number: int,
) -> list[_VectorSegment]:
    x, y, width, height = (float(value) for value in operands[:4])
    p1 = _transform_point(x, y, matrix)
    p2 = _transform_point(x + width, y, matrix)
    p3 = _transform_point(x + width, y + height, matrix)
    p4 = _transform_point(x, y + height, matrix)
    return [
        _VectorSegment(page_number, p1, p2),
        _VectorSegment(page_number, p2, p3),
        _VectorSegment(page_number, p3, p4),
        _VectorSegment(page_number, p4, p1),
    ]


def _merge_segments(segments: Iterable[_VectorSegment]) -> list[_VectorSegment]:
    horizontal: dict[tuple[int, int], list[tuple[float, float]]] = {}
    vertical: dict[tuple[int, int], list[tuple[float, float]]] = {}
    other: list[_VectorSegment] = []

    for segment in _deduplicate_segments(segments):
        dx = abs(segment.end.x - segment.start.x)
        dy = abs(segment.end.y - segment.start.y)
        if dy <= AXIS_TOLERANCE_PT:
            y = round(((segment.start.y + segment.end.y) / 2) / AXIS_TOLERANCE_PT)
            x1, x2 = sorted((segment.start.x, segment.end.x))
            horizontal.setdefault((segment.page, y), []).append((x1, x2))
        elif dx <= AXIS_TOLERANCE_PT:
            x = round(((segment.start.x + segment.end.x) / 2) / AXIS_TOLERANCE_PT)
            y1, y2 = sorted((segment.start.y, segment.end.y))
            vertical.setdefault((segment.page, x), []).append((y1, y2))
        else:
            other.append(segment)

    merged: list[_VectorSegment] = []
    for (page, y_key), intervals in horizontal.items():
        y = y_key * AXIS_TOLERANCE_PT
        for x1, x2 in _merge_intervals(intervals):
            merged.append(_VectorSegment(page, Point(x1, y), Point(x2, y)))
    for (page, x_key), intervals in vertical.items():
        x = x_key * AXIS_TOLERANCE_PT
        for y1, y2 in _merge_intervals(intervals):
            merged.append(_VectorSegment(page, Point(x, y1), Point(x, y2)))

    merged.extend(other)
    return sorted(
        merged,
        key=lambda item: (item.page, round(item.start.y, 2), round(item.start.x, 2)),
    )


def _deduplicate_segments(segments: Iterable[_VectorSegment]) -> list[_VectorSegment]:
    unique: dict[tuple[Any, ...], _VectorSegment] = {}
    for segment in segments:
        start = (round(segment.start.x, 2), round(segment.start.y, 2))
        end = (round(segment.end.x, 2), round(segment.end.y, 2))
        a, b = sorted((start, end))
        unique[(segment.page, a, b)] = segment
    return list(unique.values())


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + JOIN_TOLERANCE_PT:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _guess_exterior_segment_ids(segments: list[_VectorSegment]) -> set[int]:
    exterior: set[int] = set()
    by_page: dict[int, list[tuple[int, _VectorSegment]]] = {}
    for index, segment in enumerate(segments, start=1):
        by_page.setdefault(segment.page, []).append((index, segment))

    for page_segments in by_page.values():
        min_x = min(min(segment.start.x, segment.end.x) for _, segment in page_segments)
        max_x = max(max(segment.start.x, segment.end.x) for _, segment in page_segments)
        min_y = min(min(segment.start.y, segment.end.y) for _, segment in page_segments)
        max_y = max(max(segment.start.y, segment.end.y) for _, segment in page_segments)
        width = max(max_x - min_x, 1.0)
        height = max(max_y - min_y, 1.0)
        min_outer_length = min(width, height) * 0.2
        tolerance = max(AXIS_TOLERANCE_PT * 2, min(width, height) * 0.01)

        for index, segment in page_segments:
            is_horizontal = abs(segment.start.y - segment.end.y) <= AXIS_TOLERANCE_PT
            is_vertical = abs(segment.start.x - segment.end.x) <= AXIS_TOLERANCE_PT
            if segment.length < min_outer_length:
                continue
            if is_horizontal and (
                math.isclose(segment.start.y, min_y, abs_tol=tolerance)
                or math.isclose(segment.start.y, max_y, abs_tol=tolerance)
            ):
                exterior.add(index)
            elif is_vertical and (
                math.isclose(segment.start.x, min_x, abs_tol=tolerance)
                or math.isclose(segment.start.x, max_x, abs_tol=tolerance)
            ):
                exterior.add(index)

    return exterior
