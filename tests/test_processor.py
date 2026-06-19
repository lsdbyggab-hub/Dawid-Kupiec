from wall_pdf_analyzer.export import export_csv, export_xlsx
from wall_pdf_analyzer.processor import analyze_project


def test_openings_are_counted_inside_gross_wall_length():
    payload = {
        "rules": [{"code": "S1", "label": "Ściana S1", "color_hex": "#111111"}],
        "walls": [
            {
                "identifier": "W1",
                "wall_type": "S1",
                "length_m": 4.0,
                "openings": [{"identifier": "O1", "width_m": 1.0}],
            }
        ],
    }

    report = analyze_project(payload)

    assert report["totals_by_type"] == {"S1": 4.0}
    assert report["rows"][0]["openings_width_m"] == 1.0
    assert report["rows"][0]["optional_net_length_m"] == 3.0


def test_external_walls_are_summarized_separately():
    payload = {
        "rules": [{"code": "S2", "label": "Ściana S2", "color_hex": "#222222"}],
        "walls": [{"identifier": "W2", "wall_type": "S2", "length_m": 6.5, "is_external": True}],
    }

    report = analyze_project(payload)

    assert report["external_total_m"] == 6.5
    assert report["rows"][0]["label"] == "Ściana zewnętrzna"
    assert report["rows"][0]["color"] == "#FF00FF"
    assert report["rows"][0]["highlight"] is True


def test_non_highlighted_wall_type_is_reported_without_overlay_color():
    payload = {
        "rules": [{"code": "NNLK", "label": "NNLK", "color_hex": "#CCCCCC", "highlight": False}],
        "walls": [{"identifier": "W3", "wall_type": "NNLK", "length_m": 2.1}],
    }

    report = analyze_project(payload)

    assert report["totals_by_type"] == {"NNLK": 2.1}
    assert report["rows"][0]["highlight"] is False
    assert report["rows"][0]["color"] == ""


def test_exporters_handle_empty_wall_list(tmp_path):
    payload = {"rules": [], "walls": []}

    csv_path = export_csv(payload, tmp_path / "empty.csv")
    xlsx_path = export_xlsx(payload, tmp_path / "empty.xlsx")

    assert csv_path.read_text(encoding="utf-8").startswith("id,type,label,color,highlight")
    assert xlsx_path.exists()
