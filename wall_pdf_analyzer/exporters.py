from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from wall_pdf_analyzer.models import AnalysisInput, AnalysisResult


def export_result(result: AnalysisResult, path: str | Path) -> None:
    destination = Path(path)
    suffix = destination.suffix.lower()
    if suffix == ".xlsx":
        export_xlsx(result, destination)
    elif suffix == ".csv":
        export_csv(result, destination)
    elif suffix == ".json":
        export_json(result, destination)
    else:
        raise ValueError("Supported export formats: .xlsx, .csv, .json")


def export_json(result: AnalysisResult, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_name": result.project_name,
        "scale": result.scale_label,
        "scope": result.scope,
        "exterior_total_m": result.exterior_total_m,
        "summary": [asdict(row) for row in result.summary],
        "rows": [asdict(row) for row in result.rows],
        "warnings": list(result.warnings),
    }
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_csv(result: AnalysisResult, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "segment_id",
        "wall_type",
        "wall_name",
        "color",
        "page",
        "gross_length_m",
        "openings_m",
        "net_length_m",
        "confidence",
        "exterior",
        "scope",
        "comment",
    ]
    with destination.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in result.rows:
            writer.writerow(asdict(row))


def export_xlsx(result: AnalysisResult, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()

    summary_sheet = workbook.active
    summary_sheet.title = "Podsumowanie"
    summary_sheet.append(["Projekt", result.project_name])
    summary_sheet.append(["Skala", result.scale_label])
    summary_sheet.append(["Zakres", result.scope])
    summary_sheet.append(["Sciany zewnetrzne brutto [m]", result.exterior_total_m])
    summary_sheet.append([])
    summary_sheet.append(
        [
            "Typ",
            "Nazwa",
            "Kolor",
            "Liczba odcinkow",
            "Brutto [m]",
            "Otwory [m]",
            "Netto [m]",
            "Zewnetrzna",
        ]
    )
    _style_header(summary_sheet, 6)
    for row in result.summary:
        summary_sheet.append(
            [
                row.wall_type,
                row.wall_name,
                row.color,
                row.segment_count,
                row.gross_length_m,
                row.openings_m,
                row.net_length_m,
                "tak" if row.exterior else "nie",
            ]
        )
        _paint_color_cell(summary_sheet.cell(summary_sheet.max_row, 3), row.color)

    detail_sheet = workbook.create_sheet("Odcinki")
    detail_sheet.append(
        [
            "ID",
            "Typ",
            "Nazwa",
            "Kolor",
            "Strona",
            "Brutto [m]",
            "Otwory [m]",
            "Netto [m]",
            "Pewnosc",
            "Zewnetrzna",
            "Zakres",
            "Komentarz",
        ]
    )
    _style_header(detail_sheet, 1)
    for row in result.rows:
        detail_sheet.append(
            [
                row.segment_id,
                row.wall_type,
                row.wall_name,
                row.color,
                row.page,
                row.gross_length_m,
                row.openings_m,
                row.net_length_m,
                row.confidence,
                "tak" if row.exterior else "nie",
                row.scope,
                row.comment,
            ]
        )
        _paint_color_cell(detail_sheet.cell(detail_sheet.max_row, 4), row.color)

    audit_sheet = workbook.create_sheet("Kontrola")
    audit_sheet.append(["Ostrzezenia"])
    _style_header(audit_sheet, 1)
    if result.warnings:
        for warning in result.warnings:
            audit_sheet.append([warning])
    else:
        audit_sheet.append(["Brak ostrzezen"])

    for sheet in workbook.worksheets:
        _autosize(sheet)

    workbook.save(destination)


def export_control_svg(
    project: AnalysisInput,
    result: AnalysisResult,
    path: str | Path,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows_by_id = {row.segment_id: row for row in result.rows}
    segments = [
        segment for segment in project.wall_segments if segment.id in rows_by_id
    ]
    min_x = min(min(segment.start.x, segment.end.x) for segment in segments)
    min_y = min(min(segment.start.y, segment.end.y) for segment in segments)
    max_x = max(max(segment.start.x, segment.end.x) for segment in segments)
    max_y = max(max(segment.start.y, segment.end.y) for segment in segments)
    padding = 30
    width = max(max_x - min_x + padding * 2, 120)
    height = max(max_y - min_y + padding * 2, 120)

    def tx(value: float) -> float:
        return value - min_x + padding

    def ty(value: float) -> float:
        return value - min_y + padding

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
            f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">'
        ),
        '<rect width="100%" height="100%" fill="#F8FAFC"/>',
        (
            f'<text x="16" y="24" font-family="Arial" font-size="14" '
            f'fill="#111827">{escape(result.project_name)}</text>'
        ),
    ]
    for segment in segments:
        row = rows_by_id[segment.id]
        x1, y1 = tx(segment.start.x), ty(segment.start.y)
        x2, y2 = tx(segment.end.x), ty(segment.end.y)
        stroke_width = 7 if row.exterior else 5
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{escape(row.color)}" stroke-width="{stroke_width}" '
            'stroke-linecap="round"/>'
        )
        label_x = (x1 + x2) / 2
        label_y = (y1 + y2) / 2 - 8
        lines.append(
            f'<text x="{label_x:.2f}" y="{label_y:.2f}" font-family="Arial" '
            f'font-size="12" fill="#111827">{escape(row.wall_type)} '
            f'{row.gross_length_m:.2f} m</text>'
        )
        for opening in segment.openings:
            ratio = 0.5 if opening.offset is None else max(
                0.0, min(opening.offset / max(segment.drawing_length, 1), 1.0)
            )
            ox = x1 + (x2 - x1) * ratio
            oy = y1 + (y2 - y1) * ratio
            lines.append(
                f'<circle cx="{ox:.2f}" cy="{oy:.2f}" r="5" fill="#FFFFFF" '
                f'stroke="#111827" stroke-width="1.5"/>'
            )
    lines.append("</svg>")
    destination.write_text("\n".join(lines), encoding="utf-8")


def _style_header(sheet, row_number: int) -> None:
    for cell in sheet[row_number]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E5E7EB")


def _paint_color_cell(cell, color: str) -> None:
    cell.value = color
    if color.startswith("#") and len(color) == 7:
        cell.fill = PatternFill("solid", fgColor=color[1:].upper())


def _autosize(sheet) -> None:
    for column_cells in sheet.columns:
        max_length = 0
        column_letter = get_column_letter(column_cells[0].column)
        for cell in column_cells:
            if cell.value is not None:
                max_length = max(max_length, len(str(cell.value)))
        sheet.column_dimensions[column_letter].width = min(max_length + 2, 60)
