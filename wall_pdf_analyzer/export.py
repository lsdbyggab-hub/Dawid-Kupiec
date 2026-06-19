from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from .processor import analyze_project


def export_csv(payload: dict, path: str | Path) -> Path:
    report = analyze_project(payload)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report["rows"][0].keys()))
        writer.writeheader()
        writer.writerows(report["rows"])
    return output


def export_xlsx(payload: dict, path: str | Path) -> Path:
    """Create a dependency-free XLSX workbook with summary and wall rows."""

    report = analyze_project(payload)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_rows = [["Typ ściany", "Długość brutto [m]"]] + [
        [key, value] for key, value in report["totals_by_type"].items()
    ] + [["Ściana zewnętrzna", report["external_total_m"]]]
    detail_rows = [list(report["rows"][0].keys())] + [list(row.values()) for row in report["rows"]]

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", _content_types())
        xlsx.writestr("_rels/.rels", _root_rels())
        xlsx.writestr("xl/workbook.xml", _workbook())
        xlsx.writestr("xl/_rels/workbook.xml.rels", _workbook_rels())
        xlsx.writestr("xl/worksheets/sheet1.xml", _sheet(summary_rows))
        xlsx.writestr("xl/worksheets/sheet2.xml", _sheet(detail_rows))
    return output


def export_json(payload: dict, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(analyze_project(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def _sheet(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{chr(64 + column_index)}{row_index}"
            cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'


def _content_types() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'


def _root_rels() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'


def _workbook() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Podsumowanie" sheetId="1" r:id="rId1"/><sheet name="Ściany" sheetId="2" r:id="rId2"/></sheets></workbook>'


def _workbook_rels() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>'
