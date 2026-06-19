from __future__ import annotations

import argparse
import json
from pathlib import Path

from .export import export_csv, export_json, export_xlsx


def main() -> None:
    parser = argparse.ArgumentParser(description="Eksport modelu analizy ścian z PDF.")
    parser.add_argument("input", help="Plik JSON z rozpoznanymi ścianami")
    parser.add_argument("output", help="Docelowy plik .xlsx, .csv albo .json")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    suffix = Path(args.output).suffix.lower()
    if suffix == ".xlsx":
        export_xlsx(payload, args.output)
    elif suffix == ".csv":
        export_csv(payload, args.output)
    elif suffix == ".json":
        export_json(payload, args.output)
    else:
        raise SystemExit("Obsługiwane formaty: .xlsx, .csv, .json")


if __name__ == "__main__":
    main()
