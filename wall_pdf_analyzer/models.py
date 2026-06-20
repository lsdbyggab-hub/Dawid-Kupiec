from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Any


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Point":
        return cls(x=float(data["x"]), y=float(data["y"]))

    def distance_to(self, other: "Point") -> float:
        return hypot(other.x - self.x, other.y - self.y)


@dataclass(frozen=True)
class Scale:
    drawing_units_per_meter: float
    label: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "Scale":
        if not data:
            return cls(drawing_units_per_meter=1.0, label="1 unit = 1 m")
        units = float(data.get("drawing_units_per_meter", 1.0))
        if units <= 0:
            raise ValueError("scale.drawing_units_per_meter must be greater than 0")
        return cls(drawing_units_per_meter=units, label=str(data.get("label", "")))

    def to_meters(self, drawing_units: float) -> float:
        return drawing_units / self.drawing_units_per_meter


@dataclass(frozen=True)
class AnalysisScope:
    pages: tuple[int, ...] = (1,)
    description: str = "Caly rysunek"
    area: dict[str, float] | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "AnalysisScope":
        if not data:
            return cls()
        pages = tuple(int(page) for page in data.get("pages", [1]))
        return cls(
            pages=pages or (1,),
            description=str(data.get("description", "Caly rysunek")),
            area=data.get("area"),
        )

    def label(self) -> str:
        pages = ", ".join(str(page) for page in self.pages)
        return f"{self.description}; strony: {pages}"


@dataclass(frozen=True)
class Opening:
    kind: str
    width: float
    label: str = ""
    offset: float | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Opening":
        return cls(
            kind=str(data.get("kind", "opening")),
            width=float(data["width"]),
            label=str(data.get("label", "")),
            offset=float(data["offset"]) if data.get("offset") is not None else None,
        )


@dataclass(frozen=True)
class WallType:
    code: str
    name: str
    color: str
    include_in_report: bool = True
    exterior: bool = False
    rules: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "WallType":
        code = str(data["code"])
        return cls(
            code=code,
            name=str(data.get("name", code)),
            color=str(data.get("color", "#6B7280")),
            include_in_report=bool(data.get("include_in_report", True)),
            exterior=bool(data.get("exterior", False)),
            rules=dict(data.get("rules", {})),
        )


@dataclass(frozen=True)
class WallSegment:
    id: str
    type_code: str
    start: Point
    end: Point
    page: int = 1
    confidence: float = 1.0
    exterior: bool = False
    comment: str = ""
    measurement_basis: str = "manual_geometry"
    centerline_or_face: str = "unclear"
    openings: tuple[Opening, ...] = ()

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "WallSegment":
        return cls(
            id=str(data["id"]),
            type_code=str(data["type_code"]),
            start=Point.from_mapping(data["start"]),
            end=Point.from_mapping(data["end"]),
            page=int(data.get("page", 1)),
            confidence=float(data.get("confidence", 1.0)),
            exterior=bool(data.get("exterior", False)),
            comment=str(data.get("comment", "")),
            measurement_basis=str(data.get("measurement_basis", "manual_geometry")),
            centerline_or_face=str(data.get("centerline_or_face", "unclear")),
            openings=tuple(Opening.from_mapping(item) for item in data.get("openings", [])),
        )

    @property
    def drawing_length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def drawing_opening_width(self) -> float:
        return sum(opening.width for opening in self.openings)


@dataclass(frozen=True)
class AnalysisInput:
    project_name: str
    scale: Scale
    scope: AnalysisScope
    wall_types: dict[str, WallType]
    wall_segments: tuple[WallSegment, ...]
    source_metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AnalysisInput":
        wall_types = {
            wall_type.code: wall_type
            for wall_type in (
                WallType.from_mapping(item) for item in data.get("wall_types", [])
            )
        }
        if not wall_types:
            raise ValueError("Input must define at least one wall type")
        segments = tuple(
            WallSegment.from_mapping(item) for item in data.get("wall_segments", [])
        )
        if not segments:
            raise ValueError("Input must define at least one wall segment")
        return cls(
            project_name=str(data.get("project_name", "Projekt bez nazwy")),
            scale=Scale.from_mapping(data.get("scale")),
            scope=AnalysisScope.from_mapping(data.get("scope")),
            wall_types=wall_types,
            wall_segments=segments,
            source_metadata=dict(data.get("source_metadata", {})),
        )


@dataclass(frozen=True)
class ReportRow:
    segment_id: str
    wall_type: str
    wall_name: str
    color: str
    page: int
    gross_length_m: float
    openings_m: float
    net_length_m: float
    confidence: float
    exterior: bool
    scope: str
    measurement_basis: str = "manual_geometry"
    centerline_or_face: str = "unclear"
    opening_count: int = 0
    opening_kinds: str = ""
    comment: str = ""


@dataclass(frozen=True)
class SummaryRow:
    wall_type: str
    wall_name: str
    color: str
    segment_count: int
    gross_length_m: float
    openings_m: float
    net_length_m: float
    exterior: bool
    opening_count: int = 0
    opening_kinds: str = ""


@dataclass(frozen=True)
class AnalysisResult:
    project_name: str
    scale_label: str
    scope: str
    rows: tuple[ReportRow, ...]
    summary: tuple[SummaryRow, ...]
    exterior_total_m: float
    warnings: tuple[str, ...] = ()
    source_metadata: dict[str, Any] = field(default_factory=dict)
