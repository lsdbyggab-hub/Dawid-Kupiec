from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from wall_pdf_analyzer.analyzer import analyze_project
from wall_pdf_analyzer.exporters import export_control_svg, export_result
from wall_pdf_analyzer.io import load_project
from wall_pdf_analyzer.models import AnalysisInput, AnalysisResult


class WallAnalyzerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Wall PDF Analyzer")
        self.geometry("980x640")
        self.minsize(860, 560)

        self.project: AnalysisInput | None = None
        self.result: AnalysisResult | None = None

        self._build_layout()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(self, padding=12)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(2, weight=1)

        ttk.Button(toolbar, text="Otworz JSON", command=self.open_project).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Excel", command=lambda: self.export(".xlsx")).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(toolbar, text="CSV", command=lambda: self.export(".csv")).grid(
            row=0, column=2, sticky="w", padx=(0, 8)
        )
        ttk.Button(toolbar, text="JSON", command=lambda: self.export(".json")).grid(
            row=0, column=3, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Overlay SVG", command=self.export_overlay).grid(
            row=0, column=4
        )

        self.status = tk.StringVar(value="Wczytaj plik JSON z rozpoznanymi scianami.")
        ttk.Label(self, textvariable=self.status, padding=(12, 0, 12, 8)).grid(
            row=1, column=0, sticky="ew"
        )

        notebook = ttk.Notebook(self)
        notebook.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.summary_table = self._make_table(
            notebook,
            (
                "typ",
                "nazwa",
                "kolor",
                "odcinki",
                "brutto",
                "otwory",
                "netto",
                "zewnetrzna",
            ),
            ("Typ", "Nazwa", "Kolor", "Odcinki", "Brutto", "Otwory", "Netto", "Zew."),
        )
        notebook.add(self.summary_table.master, text="Podsumowanie")

        self.detail_table = self._make_table(
            notebook,
            (
                "id",
                "typ",
                "strona",
                "brutto",
                "otwory",
                "netto",
                "pewnosc",
                "komentarz",
            ),
            ("ID", "Typ", "Strona", "Brutto", "Otwory", "Netto", "Pewnosc", "Komentarz"),
        )
        notebook.add(self.detail_table.master, text="Odcinki")

        warning_frame = ttk.Frame(notebook)
        warning_frame.rowconfigure(0, weight=1)
        warning_frame.columnconfigure(0, weight=1)
        self.warning_text = tk.Text(warning_frame, wrap="word", height=8)
        self.warning_text.grid(row=0, column=0, sticky="nsew")
        notebook.add(warning_frame, text="Kontrola")

    def _make_table(
        self,
        parent: ttk.Notebook,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=columns, show="headings")
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=yscroll.set)
        table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        for column, heading in zip(columns, headings):
            table.heading(column, text=heading)
            table.column(column, width=110, minwidth=70, stretch=True)
        return table

    def open_project(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz projekt JSON",
            filetypes=(("JSON", "*.json"), ("Wszystkie pliki", "*.*")),
        )
        if not path:
            return
        try:
            self.project = load_project(path)
            self.result = analyze_project(self.project)
        except Exception as exc:
            messagebox.showerror("Nie mozna wczytac projektu", str(exc))
            return
        self._refresh_tables()
        self.status.set(
            f"{self.result.project_name}: {len(self.result.rows)} odcinkow, "
            f"sciany zewnetrzne {self.result.exterior_total_m:.2f} m."
        )

    def export(self, suffix: str) -> None:
        if self.result is None:
            messagebox.showinfo("Brak danych", "Najpierw wczytaj projekt JSON.")
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz raport",
            defaultextension=suffix,
            filetypes=((suffix.upper().replace(".", ""), f"*{suffix}"),),
        )
        if not path:
            return
        try:
            export_result(self.result, path)
        except Exception as exc:
            messagebox.showerror("Eksport nieudany", str(exc))
            return
        messagebox.showinfo("Gotowe", f"Zapisano raport:\n{path}")

    def export_overlay(self) -> None:
        if self.project is None or self.result is None:
            messagebox.showinfo("Brak danych", "Najpierw wczytaj projekt JSON.")
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz overlay SVG",
            defaultextension=".svg",
            filetypes=(("SVG", "*.svg"),),
        )
        if not path:
            return
        try:
            export_control_svg(self.project, self.result, path)
        except Exception as exc:
            messagebox.showerror("Eksport nieudany", str(exc))
            return
        messagebox.showinfo("Gotowe", f"Zapisano overlay:\n{path}")

    def _refresh_tables(self) -> None:
        assert self.result is not None
        for table in (self.summary_table, self.detail_table):
            table.delete(*table.get_children())
        for row in self.result.summary:
            self.summary_table.insert(
                "",
                "end",
                values=(
                    row.wall_type,
                    row.wall_name,
                    row.color,
                    row.segment_count,
                    f"{row.gross_length_m:.2f}",
                    f"{row.openings_m:.2f}",
                    f"{row.net_length_m:.2f}",
                    "tak" if row.exterior else "nie",
                ),
            )
        for row in self.result.rows:
            self.detail_table.insert(
                "",
                "end",
                values=(
                    row.segment_id,
                    row.wall_type,
                    row.page,
                    f"{row.gross_length_m:.2f}",
                    f"{row.openings_m:.2f}",
                    f"{row.net_length_m:.2f}",
                    f"{row.confidence:.0%}",
                    row.comment,
                ),
            )
        self.warning_text.delete("1.0", "end")
        if self.result.warnings:
            self.warning_text.insert("end", "\n".join(self.result.warnings))
        else:
            self.warning_text.insert("end", "Brak ostrzezen.")


def main() -> None:
    app = WallAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
