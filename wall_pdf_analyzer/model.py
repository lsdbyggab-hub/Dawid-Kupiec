from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Opening:
    """Window or door located inside a wall segment."""

    identifier: str
    kind: str
    width_m: float
    position_m: float | None = None


@dataclass(frozen=True)
class WallTypeRule:
    """Presentation and reporting rule for one wall type."""

    code: str
    label: str
    color_hex: str
    count_in_totals: bool = True
    highlight: bool = True


@dataclass(frozen=True)
class WallSegment:
    """Recognized wall fragment from a PDF drawing."""

    identifier: str
    wall_type: str
    length_m: float
    page: int = 1
    is_external: bool = False
    confidence: float = 1.0
    openings: tuple[Opening, ...] = field(default_factory=tuple)

    @property
    def gross_length_m(self) -> float:
        """Length counted for takeoff; openings are already part of the wall."""

        return self.length_m

    @property
    def openings_width_m(self) -> float:
        return sum(opening.width_m for opening in self.openings)

    @property
    def optional_net_length_m(self) -> float:
        return max(self.length_m - self.openings_width_m, 0.0)


@dataclass(frozen=True)
class AnalysisResult:
    """Calculated wall takeoff ready for export and visual review."""

    scale: str
    source_pdf: str
    analyzed_scope: str
    rules: tuple[WallTypeRule, ...]
    walls: tuple[WallSegment, ...]

    def rule_for(self, wall_type: str) -> WallTypeRule | None:
        return next((rule for rule in self.rules if rule.code == wall_type), None)

    def walls_for_totals(self) -> Iterable[WallSegment]:
        for wall in self.walls:
            rule = self.rule_for(wall.wall_type)
            if rule is None or rule.count_in_totals:
                yield wall
