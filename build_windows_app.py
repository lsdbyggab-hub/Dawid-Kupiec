from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    try:
        import PyInstaller.__main__  # type: ignore
    except ModuleNotFoundError:
        print("PyInstaller is not installed.")
        print("Install it with: python -m pip install pyinstaller")
        return 1

    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--windowed",
            "--name",
            "Wall PDF Analyzer",
            "--add-data",
            f"{ROOT / 'examples'};examples",
            "--hidden-import",
            "pypdf",
            "--hidden-import",
            "pypdf.generic",
            "--hidden-import",
            "fitz",
            "--hidden-import",
            "PIL.Image",
            "--hidden-import",
            "PIL.ImageTk",
            str(ROOT / "run_app.py"),
        ]
    )
    exe = ROOT / "dist" / "Wall PDF Analyzer" / "Wall PDF Analyzer.exe"
    print(f"Created: {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
