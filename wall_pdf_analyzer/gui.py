from __future__ import annotations

import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from wall_pdf_analyzer.analyzer import analyze_project
from wall_pdf_analyzer.editing import change_segment_type, delete_segments, merge_segments
from wall_pdf_analyzer.exporters import export_control_pdf, export_control_svg, export_result
from wall_pdf_analyzer.io import load_project
from wall_pdf_analyzer.models import AnalysisInput, AnalysisResult
from wall_pdf_analyzer.pdf_importer import (
    DEFAULT_RASTER_DPI,
    PdfScaleMissingError,
    import_pdf_project,
)

APP_TITLE = "Wall PDF Analyzer"
PROJECT_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[1]
)
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
SAMPLE_PROJECT = RESOURCE_ROOT / "examples" / "sample_project.json"


class WallAnalyzerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.project: AnalysisInput | None = None
        self.result: AnalysisResult | None = None
        self.project_path: Path | None = None
        self.last_output_dir = Path.home() / "Documents" / "Wall PDF Analyzer"

        self._configure_style()
        self._build_layout()
        if SAMPLE_PROJECT.exists():
            self.load_project(SAMPLE_PROJECT)

    def _configure_style(self) -> None:
        self.configure(bg="#F4F6F8")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#F4F6F8")
        style.configure("Panel.TFrame", background="#FFFFFF", relief="solid", borderwidth=1)
        style.configure("TLabel", background="#F4F6F8", foreground="#17202A")
        style.configure("Panel.TLabel", background="#FFFFFF", foreground="#17202A")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Metric.TLabel", background="#FFFFFF", font=("Segoe UI", 16, "bold"))
        style.configure("Muted.TLabel", background="#FFFFFF", foreground="#5D6D7E")
        style.configure("TButton", padding=(10, 6))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Analiza dlugosci scian z JSON lub PDF wektorowego",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        toolbar = ttk.Frame(self, padding=(16, 0, 16, 10))
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(6, weight=1)

        buttons = [
            ("Wczytaj JSON", self.choose_project),
            ("Analizuj PDF", self.choose_pdf),
            ("Przyklad", lambda: self.load_project(SAMPLE_PROJECT)),
            ("Zmien typ", self.change_selected_type),
            ("Scal", self.merge_selected),
            ("Usun", self.delete_selected),
            ("Eksportuj wszystko", self.export_all),
            ("Excel", lambda: self.export_one(".xlsx")),
            ("CSV", lambda: self.export_one(".csv")),
            ("JSON", lambda: self.export_one(".json")),
            ("Overlay SVG", self.export_overlay),
            ("Overlay PDF", self.export_overlay_pdf),
            ("Folder wynikow", self.open_output_folder),
        ]
        for column, (label, command) in enumerate(buttons):
            row = column // 7
            grid_column = column % 7
            ttk.Button(toolbar, text=label, command=command).grid(
                row=row, column=grid_column, padx=(0, 8), pady=(0, 6)
            )

        self.status = tk.StringVar(value="Wczytaj JSON albo analizuj PDF.")
        ttk.Label(toolbar, textvariable=self.status).grid(
            row=2, column=0, columnspan=7, sticky="ew"
        )

        metrics = ttk.Frame(self, padding=(16, 0, 16, 12))
        metrics.grid(row=2, column=0, sticky="ew")
        for column in range(4):
            metrics.columnconfigure(column, weight=1)
        self.metric_labels: dict[str, ttk.Label] = {}
        self._metric(metrics, 0, "Projekt", "Brak")
        self._metric(metrics, 1, "Odcinki", "0")
        self._metric(metrics, 2, "Suma brutto", "0.00 m")
        self._metric(metrics, 3, "Zewnetrzne", "0.00 m")

        notebook = ttk.Notebook(self)
        notebook.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 16))

        preview = ttk.Frame(notebook, style="Panel.TFrame", padding=8)
        preview.rowconfigure(0, weight=1)
        preview.columnconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(preview, bg="#FFFFFF", highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        notebook.add(preview, text="Podglad")

        self.summary_table = self._make_table(
            notebook,
            ("type", "name", "color", "count", "gross", "openings", "net", "exterior"),
            ("Typ", "Nazwa", "Kolor", "Odcinki", "Brutto [m]", "Otwory [m]", "Netto [m]", "Zew."),
        )
        notebook.add(self.summary_table.master, text="Podsumowanie")

        self.detail_table = self._make_table(
            notebook,
            (
                "id",
                "type",
                "page",
                "gross",
                "openings",
                "opening_count",
                "opening_kinds",
                "net",
                "confidence",
                "basis",
                "edge",
                "comment",
            ),
            (
                "ID",
                "Typ",
                "Strona",
                "Brutto [m]",
                "Otwory [m]",
                "Liczba otw.",
                "Typy otw.",
                "Netto [m]",
                "Pewnosc",
                "Podstawa",
                "Os/krawedz",
                "Komentarz",
            ),
        )
        self.detail_table.configure(selectmode="extended")
        notebook.add(self.detail_table.master, text="Odcinki")

        warning_frame = ttk.Frame(notebook, style="Panel.TFrame", padding=8)
        warning_frame.rowconfigure(0, weight=1)
        warning_frame.columnconfigure(0, weight=1)
        self.warning_text = tk.Text(
            warning_frame,
            wrap="word",
            height=8,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        self.warning_text.grid(row=0, column=0, sticky="nsew")
        notebook.add(warning_frame, text="Kontrola")

        self.preview_canvas.bind("<Configure>", lambda _event: self._draw_preview())

    def _metric(self, parent: ttk.Frame, column: int, label: str, value: str) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(frame, text=label, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        value_label = ttk.Label(frame, text=value, style="Metric.TLabel")
        value_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.metric_labels[label] = value_label

    def _make_table(
        self,
        parent: ttk.Notebook,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=8)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=columns, show="headings")
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        for column, heading in zip(columns, headings):
            table.heading(column, text=heading)
            table.column(column, width=120, minwidth=80, stretch=True)
        return table

    def choose_project(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz projekt JSON",
            initialdir=str(PROJECT_ROOT),
            filetypes=(("JSON", "*.json"), ("Wszystkie pliki", "*.*")),
        )
        if path:
            self.load_project(Path(path))

    def choose_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz PDF do analizy",
            initialdir=str(PROJECT_ROOT),
            filetypes=(("PDF", "*.pdf"), ("Wszystkie pliki", "*.*")),
        )
        if path:
            self.load_pdf(Path(path))

    def load_project(self, path: Path) -> None:
        try:
            self.project = load_project(path)
            self.result = analyze_project(self.project)
            self.project_path = path
        except Exception as exc:
            messagebox.showerror("Nie mozna wczytac projektu", str(exc))
            return
        self._refresh()
        self.status.set(f"Wczytano: {path.name}")

    def load_pdf(self, path: Path) -> None:
        try:
            self.project = import_pdf_project(path)
        except PdfScaleMissingError as exc:
            calibration = CalibrationDialog(self, path, str(exc)).show()
            if calibration is not None:
                pixels, meters = calibration
                try:
                    self.project = import_pdf_project(
                        path,
                        calibration_pixels=pixels,
                        calibration_meters=meters,
                    )
                except Exception as retry_exc:
                    messagebox.showerror("Analiza PDF nieudana", str(retry_exc))
                    return
            else:
                denominator = simpledialog.askfloat(
                    "Skala PDF",
                    f"{exc}\n\nPodaj mianownik skali, np. 100 dla 1:100.",
                    minvalue=1.0,
                )
                if denominator is None:
                    return
                try:
                    self.project = import_pdf_project(path, scale_denominator=denominator)
                except Exception as retry_exc:
                    messagebox.showerror("Analiza PDF nieudana", str(retry_exc))
                    return
        except Exception as exc:
            messagebox.showerror("Analiza PDF nieudana", str(exc))
            return
        self.result = analyze_project(self.project)
        self.project_path = path
        self._refresh()
        self.status.set(f"Przeanalizowano PDF: {path.name}")

    def change_selected_type(self) -> None:
        if self.project is None:
            self._show_no_data()
            return
        segment_ids = self._selected_segment_ids()
        if not segment_ids:
            messagebox.showinfo("Brak wyboru", "Zaznacz jeden lub wiecej odcinkow.")
            return
        codes = ", ".join(sorted(self.project.wall_types))
        type_code = simpledialog.askstring(
            "Zmien typ sciany",
            f"Dostepne typy: {codes}\nWpisz kod typu:",
        )
        if not type_code:
            return
        try:
            self.project = change_segment_type(self.project, segment_ids, type_code.strip())
        except Exception as exc:
            messagebox.showerror("Korekta nieudana", str(exc))
            return
        self._reanalyze_after_edit("Zmieniono typ zaznaczonych odcinkow.")

    def delete_selected(self) -> None:
        if self.project is None:
            self._show_no_data()
            return
        segment_ids = self._selected_segment_ids()
        if not segment_ids:
            messagebox.showinfo("Brak wyboru", "Zaznacz jeden lub wiecej odcinkow.")
            return
        if not messagebox.askyesno("Usun odcinki", f"Usunac odcinki: {', '.join(segment_ids)}?"):
            return
        try:
            self.project = delete_segments(self.project, segment_ids)
        except Exception as exc:
            messagebox.showerror("Korekta nieudana", str(exc))
            return
        self._reanalyze_after_edit("Usunieto zaznaczone odcinki.")

    def merge_selected(self) -> None:
        if self.project is None:
            self._show_no_data()
            return
        segment_ids = self._selected_segment_ids()
        if len(segment_ids) < 2:
            messagebox.showinfo("Za malo odcinkow", "Zaznacz co najmniej dwa odcinki do scalenia.")
            return
        try:
            self.project = merge_segments(self.project, segment_ids)
        except Exception as exc:
            messagebox.showerror("Scalenie nieudane", str(exc))
            return
        self._reanalyze_after_edit("Scalono zaznaczone odcinki.")

    def _reanalyze_after_edit(self, status: str) -> None:
        assert self.project is not None
        self.result = analyze_project(self.project)
        self._refresh()
        self.status.set(status)

    def _selected_segment_ids(self) -> list[str]:
        ids: list[str] = []
        for item_id in self.detail_table.selection():
            values = self.detail_table.item(item_id, "values")
            if values:
                ids.append(str(values[0]))
        return ids

    def export_one(self, suffix: str) -> None:
        if self.result is None:
            self._show_no_data()
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz raport",
            initialdir=str(self.last_output_dir),
            initialfile=f"{self._base_filename()}{suffix}",
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
        self.last_output_dir = Path(path).parent
        self.status.set(f"Zapisano: {Path(path).name}")
        messagebox.showinfo("Gotowe", f"Zapisano raport:\n{path}")

    def export_overlay(self) -> None:
        if self.project is None or self.result is None:
            self._show_no_data()
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz overlay SVG",
            initialdir=str(self.last_output_dir),
            initialfile=f"{self._base_filename()}-kontrola.svg",
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
        self.last_output_dir = Path(path).parent
        self.status.set(f"Zapisano: {Path(path).name}")
        messagebox.showinfo("Gotowe", f"Zapisano overlay:\n{path}")

    def export_overlay_pdf(self) -> None:
        if self.project is None or self.result is None:
            self._show_no_data()
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz kontrolny PDF",
            initialdir=str(self.last_output_dir),
            initialfile=f"{self._base_filename()}-kontrola.pdf",
            defaultextension=".pdf",
            filetypes=(("PDF", "*.pdf"),),
        )
        if not path:
            return
        try:
            export_control_pdf(self.project, self.result, path)
        except Exception as exc:
            messagebox.showerror("Eksport PDF nieudany", str(exc))
            return
        self.last_output_dir = Path(path).parent
        self.status.set(f"Zapisano: {Path(path).name}")
        messagebox.showinfo("Gotowe", f"Zapisano kontrolny PDF:\n{path}")

    def export_all(self) -> None:
        if self.project is None or self.result is None:
            self._show_no_data()
            return
        directory = filedialog.askdirectory(
            title="Wybierz folder wynikow",
            initialdir=str(self.last_output_dir),
        )
        if not directory:
            return
        output_dir = Path(directory)
        base_name = self._base_filename()
        try:
            export_result(self.result, output_dir / f"{base_name}.xlsx")
            export_result(self.result, output_dir / f"{base_name}.csv")
            export_result(self.result, output_dir / f"{base_name}.json")
            export_control_svg(self.project, self.result, output_dir / f"{base_name}-kontrola.svg")
            export_control_pdf(self.project, self.result, output_dir / f"{base_name}-kontrola.pdf")
        except Exception as exc:
            messagebox.showerror("Eksport nieudany", str(exc))
            return
        self.last_output_dir = output_dir
        self.status.set(f"Zapisano komplet wynikow w: {output_dir}")
        messagebox.showinfo("Gotowe", f"Zapisano komplet wynikow:\n{output_dir}")

    def open_output_folder(self) -> None:
        self.last_output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.last_output_dir)

    def _refresh(self) -> None:
        assert self.result is not None
        self._refresh_metrics()
        self._refresh_tables()
        self._refresh_warnings()
        self._draw_preview()

    def _refresh_metrics(self) -> None:
        assert self.result is not None
        total_gross = sum(row.gross_length_m for row in self.result.rows)
        warning_count = len(self.result.warnings)
        project_name = self.result.project_name
        if len(project_name) > 22:
            project_name = f"{project_name[:21]}..."
        self.metric_labels["Projekt"].configure(text=project_name)
        self.metric_labels["Odcinki"].configure(
            text=f"{len(self.result.rows)} / ostrz. {warning_count}"
        )
        self.metric_labels["Suma brutto"].configure(text=f"{total_gross:.2f} m")
        self.metric_labels["Zewnetrzne"].configure(
            text=f"{self.result.exterior_total_m:.2f} m"
        )

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
                    row.opening_count,
                    row.opening_kinds,
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
                    row.measurement_basis,
                    row.centerline_or_face,
                    row.comment,
                ),
            )

    def _refresh_warnings(self) -> None:
        assert self.result is not None
        metadata = self.result.source_metadata
        self.warning_text.configure(state="normal")
        self.warning_text.delete("1.0", "end")
        lines: list[str] = []
        if metadata:
            lines.extend(
                [
                    f"Typ PDF: {metadata.get('pdf_kind', 'brak danych')}",
                    f"Metoda: {metadata.get('method', 'brak danych')}",
                    f"Zrodlo skali: {metadata.get('scale_source', 'brak danych')}",
                    "",
                ]
            )
        if self.result.warnings:
            lines.append("Ostrzezenia:")
            lines.extend(f"- {item}" for item in self.result.warnings)
        else:
            lines.append("Brak ostrzezen.")
        assumptions = metadata.get("assumptions", []) if metadata else []
        if assumptions:
            lines.extend(["", "Zalozenia:"])
            lines.extend(f"- {item}" for item in assumptions)
        self.warning_text.insert("end", "\n".join(lines))
        self.warning_text.configure(state="disabled")

    def _draw_preview(self) -> None:
        canvas = self.preview_canvas
        canvas.delete("all")
        if self.project is None or self.result is None:
            canvas.create_text(
                20,
                20,
                anchor="nw",
                fill="#5D6D7E",
                text="Brak danych do podgladu.",
                font=("Segoe UI", 12),
            )
            return

        rows_by_id = {row.segment_id: row for row in self.result.rows}
        segments = [item for item in self.project.wall_segments if item.id in rows_by_id]
        if not segments:
            return

        width = max(canvas.winfo_width(), 200)
        height = max(canvas.winfo_height(), 200)
        min_x = min(min(segment.start.x, segment.end.x) for segment in segments)
        min_y = min(min(segment.start.y, segment.end.y) for segment in segments)
        max_x = max(max(segment.start.x, segment.end.x) for segment in segments)
        max_y = max(max(segment.start.y, segment.end.y) for segment in segments)
        drawing_width = max(max_x - min_x, 1)
        drawing_height = max(max_y - min_y, 1)
        padding = 48
        scale = min(
            (width - padding * 2) / drawing_width,
            (height - padding * 2) / drawing_height,
        )

        def px(value: float) -> float:
            return padding + (value - min_x) * scale

        def py(value: float) -> float:
            return padding + (value - min_y) * scale

        canvas.create_rectangle(14, 14, width - 14, height - 14, outline="#E5E7EB")
        for segment in segments:
            row = rows_by_id[segment.id]
            x1, y1 = px(segment.start.x), py(segment.start.y)
            x2, y2 = px(segment.end.x), py(segment.end.y)
            canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill=row.color,
                width=8 if row.exterior else 6,
                capstyle=tk.ROUND,
            )
            label_x = (x1 + x2) / 2
            label_y = (y1 + y2) / 2 - 14
            canvas.create_text(
                label_x,
                label_y,
                text=f"{row.wall_type} {row.gross_length_m:.2f} m",
                fill="#111827",
                font=("Segoe UI", 9, "bold"),
            )
            for opening in segment.openings:
                ratio = 0.5 if opening.offset is None else max(
                    0.0,
                    min(opening.offset / max(segment.drawing_length, 1), 1.0),
                )
                ox = x1 + (x2 - x1) * ratio
                oy = y1 + (y2 - y1) * ratio
                canvas.create_oval(
                    ox - 6,
                    oy - 6,
                    ox + 6,
                    oy + 6,
                    fill="#FFFFFF",
                    outline="#111827",
                    width=2,
                )

    def _base_filename(self) -> str:
        if self.result is None:
            return "raport"
        name = self.result.project_name.lower()
        name = re.sub(r"[^a-z0-9]+", "-", name, flags=re.IGNORECASE)
        return name.strip("-") or "raport"

    def _show_no_data(self) -> None:
        messagebox.showinfo("Brak danych", "Najpierw wczytaj JSON albo analizuj PDF.")


class CalibrationDialog:
    def __init__(self, parent: tk.Tk, pdf_path: Path, message: str) -> None:
        self.parent = parent
        self.pdf_path = pdf_path
        self.message = message
        self.value: tuple[float, float] | None = None
        self.points: list[tuple[float, float]] = []
        self.display_scale = 1.0
        self.photo = None
        self.canvas: tk.Canvas | None = None
        self.length_var = tk.StringVar()
        self.ok_button: ttk.Button | None = None

    def show(self) -> tuple[float, float] | None:
        try:
            image, self.display_scale = self._render_preview()
        except Exception as exc:
            messagebox.showwarning(
                "Kalibracja niedostepna",
                f"Nie mozna pokazac podgladu kalibracji:\n{exc}",
            )
            return None

        window = tk.Toplevel(self.parent)
        window.title("Kalibracja znanym odcinkiem")
        window.transient(self.parent)
        window.grab_set()

        ttk.Label(
            window,
            text=(
                f"{self.message}\n"
                "Kliknij dwa punkty znanego odcinka na pierwszej stronie PDF i wpisz jego dlugosc w metrach."
            ),
            padding=10,
        ).grid(row=0, column=0, columnspan=3, sticky="ew")

        self.canvas = tk.Canvas(window, width=image.width, height=image.height, bg="#FFFFFF")
        self.canvas.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 8))
        self.photo = self._photo_image(image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.bind("<Button-1>", self._on_click)

        ttk.Label(window, text="Dlugosc [m]:").grid(row=2, column=0, padx=10, pady=8, sticky="e")
        ttk.Entry(window, textvariable=self.length_var, width=12).grid(
            row=2, column=1, pady=8, sticky="w"
        )
        self.ok_button = ttk.Button(window, text="OK", command=lambda: self._accept(window))
        self.ok_button.grid(row=2, column=2, padx=10, pady=8, sticky="e")
        ttk.Button(window, text="Pomin", command=window.destroy).grid(
            row=3, column=2, padx=10, pady=(0, 10), sticky="e"
        )
        self._update_ok_state()
        self.parent.wait_window(window)
        return self.value

    def _render_preview(self):
        import fitz  # type: ignore
        from PIL import Image

        with fitz.open(str(self.pdf_path)) as document:
            if len(document) == 0:
                raise ValueError("PDF nie ma stron.")
            page = document[0]
            scale = DEFAULT_RASTER_DPI / 72.0
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        max_width, max_height = 920, 620
        ratio = min(max_width / image.width, max_height / image.height, 1.0)
        if ratio < 1.0:
            image = image.resize((int(image.width * ratio), int(image.height * ratio)))
        return image, ratio

    def _photo_image(self, image):
        from PIL import ImageTk

        return ImageTk.PhotoImage(image)

    def _on_click(self, event) -> None:
        if self.canvas is None:
            return
        if len(self.points) >= 2:
            self.points.clear()
            self.canvas.delete("calibration")
        point = (float(event.x), float(event.y))
        self.points.append(point)
        x, y = point
        self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#DC2626", outline="", tags="calibration")
        if len(self.points) == 2:
            (x1, y1), (x2, y2) = self.points
            self.canvas.create_line(x1, y1, x2, y2, fill="#DC2626", width=2, tags="calibration")
        self._update_ok_state()

    def _accept(self, window: tk.Toplevel) -> None:
        if len(self.points) != 2:
            return
        try:
            meters = float(self.length_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Bledna dlugosc", "Wpisz dlugosc odcinka w metrach.")
            return
        if meters <= 0:
            messagebox.showerror("Bledna dlugosc", "Dlugosc musi byc wieksza od zera.")
            return
        (x1, y1), (x2, y2) = self.points
        display_pixels = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        original_pixels = display_pixels / max(self.display_scale, 0.0001)
        self.value = (original_pixels, meters)
        window.destroy()

    def _update_ok_state(self) -> None:
        if self.ok_button is not None:
            state = "normal" if len(self.points) == 2 else "disabled"
            self.ok_button.configure(state=state)


def main() -> None:
    app = WallAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
