# Dawid-Kupiec

## Prototyp aplikacji do analizy ścian z PDF

Repozytorium zawiera działający model aplikacji, który przyjmuje dane rozpoznane z rysunku PDF, liczy długości ścian i przygotowuje raport do pobrania. Prototyp zakłada, że moduł OCR/CAD/PDF dostarcza listę ścian, otworów, typów ścian, skali i zakresu analizy, a warstwa obliczeniowa odpowiada za spójne reguły zliczania oraz eksport.

Najważniejsza reguła: okna, drzwi i inne otwory nie kończą ściany. Długość brutto ściany pozostaje pełną długością odcinka, a szerokość otworów jest raportowana osobno tylko jako informacja kontrolna.

## Funkcje modelu

- Definicje typów ścian z etykietą, kolorem, regułą zliczania i regułą podświetlania.
- Osobne oznaczanie ścian zewnętrznych budynku kolorem kontrolnym `#FF00FF` i sumowanie ich w oddzielnej pozycji.
- Obsługa typów specjalnych, np. `NNLK`, które mogą być raportowane bez kolorowania na podglądzie.
- Raportowanie długości brutto, łącznej szerokości otworów i opcjonalnej długości netto.
- Eksport do `XLSX`, `CSV` albo `JSON` bez zewnętrznych zależności.
- Przykładowy plik wejściowy w `examples/sample_project.json`.

## Struktura

- `wall_pdf_analyzer/model.py` — dataclassy opisujące ściany, otwory, reguły typów i wynik analizy.
- `wall_pdf_analyzer/processor.py` — logika zliczania długości i przygotowania wierszy raportu.
- `wall_pdf_analyzer/export.py` — eksport raportu do plików `XLSX`, `CSV` i `JSON`.
- `wall_pdf_analyzer/cli.py` — interfejs CLI do wygenerowania pliku wynikowego.
- `tests/test_processor.py` — testy reguł zliczania otworów i ścian zewnętrznych.

## Użycie

Wygenerowanie Excela:

```bash
python -m wall_pdf_analyzer.cli examples/sample_project.json out/raport.xlsx
```

Wygenerowanie JSON z wynikiem obliczeń:

```bash
python -m wall_pdf_analyzer.cli examples/sample_project.json out/raport.json
```

Uruchomienie testów:

```bash
python -m pytest
```

## Kolejne kroki rozwoju

1. Dodać adapter odczytu PDF wektorowego, który pobierze linie, warstwy, kolory i teksty bezpośrednio z pliku.
2. Dodać adapter OCR dla skanów rastrowych oraz ręczną kalibrację skali na wskazanym wymiarze referencyjnym.
3. Zbudować widok kontrolny PDF z kolorową nakładką dla każdego typu ściany i osobnym kolorem dla ścian zewnętrznych.
4. Dodać panel korekt, w którym użytkownik zatwierdza, łączy albo poprawia rozpoznane odcinki.
5. Rozszerzyć plik XLSX o style komórek zgodne z kolorami ścian oraz linki do oznaczeń na podglądzie PDF.
