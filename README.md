# Wall PDF Analyzer

Aplikacja desktopowa do zestawiania długości ścian z danych rozpoznanych z rysunku PDF.

Program przyjmuje plik JSON z geometrią ścian, typami ścian, skalą, otworami i zakresem analizy. Następnie liczy długości brutto, szerokości otworów, długości netto, sumuje ściany po typach, osobno raportuje ściany zewnętrzne i generuje raporty do Excela, CSV, JSON oraz kontrolny overlay SVG.

## Najprostsze uruchomienie

Kliknij dwukrotnie:

```text
Uruchom Wall PDF Analyzer.bat
```

Po starcie aplikacja automatycznie wczytuje przykładowy projekt. Możesz od razu sprawdzić podgląd, tabele i wyeksportować komplet wyników przyciskiem `Eksportuj wszystko`.

## Co działa

- Model danych dla skali, zakresu analizy, typów ścian, odcinków i otworów.
- Liczenie długości ścian w metrach na podstawie skali.
- Otwory nie kończą ściany: długość brutto pozostaje pełną długością odcinka, a szerokości drzwi i okien są raportowane osobno.
- Ściany zewnętrzne są sumowane osobno i oznaczane kolorem kontrolnym `#FF00FF`.
- Raport Excel zawiera arkusze `Podsumowanie`, `Odcinki` i `Kontrola`.
- Eksport do `.xlsx`, `.csv`, `.json`.
- Eksport overlay `.svg` z kolorowym oznaczeniem odcinków.
- Ostrzeżenia dla odcinków o niskiej pewności rozpoznania.
- Okno aplikacji z podglądem kolorowych ścian, tabelą podsumowania, tabelą odcinków i panelem kontroli.
- Jeden przycisk do eksportu kompletu wyników: Excel, CSV, JSON i SVG.
- Testy jednostkowe oparte na standardowym `unittest`.

## Uruchomienie z terminala

Z katalogu repozytorium:

```powershell
python run_app.py
python -m wall_pdf_analyzer.cli examples\sample_project.json out\raport.xlsx --overlay out\kontrola.svg
python -m wall_pdf_analyzer.cli examples\sample_project.json out\raport.json
```

Jeżeli używasz Pythona z pakietu Codex na tej maszynie:

```powershell
& 'C:\Users\dawid\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wall_pdf_analyzer.cli examples\sample_project.json out\raport.xlsx --overlay out\kontrola.svg
```

## Budowanie pliku EXE

Opcjonalnie można zbudować wersję `.exe` dla Windows:

```powershell
python -m pip install pyinstaller
python build_windows_app.py
```

Gotowy plik pojawi się w:

```text
dist\Wall PDF Analyzer\Wall PDF Analyzer.exe
```

## Testy

```powershell
python -m unittest discover -s tests
python -m compileall wall_pdf_analyzer
```

## Format wejściowy

Przykład znajduje się w [examples/sample_project.json](examples/sample_project.json).

Najważniejsze pola:

- `scale.drawing_units_per_meter` określa, ile jednostek rysunku odpowiada jednemu metrowi.
- `wall_types` definiuje kody, nazwy, kolory i reguły typów ścian.
- `wall_segments` zawiera odcinki z punktami `start` i `end`, typem ściany, stroną PDF, pewnością rozpoznania i opcjonalnymi otworami.
- `openings[].width` jest szerokością otworu w jednostkach rysunku.
- `exterior: true` na typie lub odcinku oznacza ścianę zewnętrzną.

## Zakres aplikacji

Ta wersja nie rozpoznaje jeszcze automatycznie geometrii z surowego PDF. Jest przygotowana jako drugi etap procesu: przyjmuje dane, które mogą pochodzić z ekstraktora PDF, ręcznego oznaczenia albo przyszłego modelu rozpoznawania.

Najbliższe kroki rozwoju:

1. Dodać importer PDF, który rozróżnia PDF wektorowy i skan.
2. Dodać ręczną kalibrację skali przez wskazanie znanego odcinka.
3. Dodać edytor korekt: zmiana typu ściany, łączenie odcinków, usuwanie błędnych rozpoznań.
4. Generować kontrolny PDF z nakładką zamiast samego SVG.
5. Dodać historię zmian i wersjonowanie raportów.
6. Dodać eksport reguł specjalnych dla typów takich jak `NNLK`.
