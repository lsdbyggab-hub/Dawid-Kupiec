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
