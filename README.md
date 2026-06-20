# Wall PDF Analyzer

Aplikacja desktopowa do zestawiania dlugosci scian z JSON albo prostego PDF wektorowego. Program liczy dlugosci brutto, otwory, dlugosci netto, podsumowania po typach, sciany zewnetrzne oraz eksportuje Excel, CSV, JSON i kontrolny overlay SVG.

## Najprostsze uruchomienie

Kliknij dwukrotnie:

```text
Uruchom Wall PDF Analyzer.bat
```

Po starcie aplikacja wczytuje przyklad, pokazuje podglad i pozwala eksportowac komplet wynikow przyciskiem `Eksportuj wszystko`.

## Co dziala

- Wczytywanie gotowego projektu JSON.
- Przycisk `Analizuj PDF` dla PDF wektorowych.
- Rozpoznanie, czy PDF jest wektorowy, rastrowy/skanowany czy mieszany.
- Brak zgadywania skali: skala jest czytana z tekstu `Skala 1:100` albo podawana przez uzytkownika.
- Rozpoznawanie skanow i PDF rastrowych po kalibracji znanym odcinkiem.
- Kalibracja w GUI: kliknij dwa punkty znanego odcinka na podgladzie i wpisz jego dlugosc w metrach.
- Odmowa pomiaru rzeczywistych dlugosci, gdy PDF nie ma skali, kalibracji albo zawiera ostrzezenie typu `not to scale` bez podstawy pomiaru.
- Lepsze wykrywanie drzwi i okien w PDF: program laczy sciane przez typowa przerwe, wykrywa kreski rownolegle jako okna i linie skrzydla jako drzwi.
- Raport pokazuje `opening_count`, `opening_kinds`, szerokosc otworow oraz dlugosc netto.
- Rozpoznawanie oznaczen scian `IV20`, `IV31`, `IV30`, `IV02`, `YV...`, `BV...` z pozycji tekstu w PDF.
- Gdy takie oznaczenia sa widoczne na rzucie, importer przypisuje typ do najblizszej sciany i jej polaczonych odcinkow, a pomija kreski bez zwiazku z tagami, np. schody, meble i armature.
- Edytor korekt w GUI: zmiana typu sciany, scalanie odcinkow i usuwanie blednych rozpoznan.
- Eksport metody pomiaru, zrodla skali, zalozen, ostrzezen i podstawy pomiaru kazdego odcinka.
- Podstawowy kontekst szwedzkich planow: oznaczenia `IV`, `YV`, `BV`, `EI`, `REI`, legenda i ostrzezenie o niejednoznacznym `IV`.
- Otwory nie koncza sciany: dlugosc brutto pozostaje pelna dlugoscia odcinka, a szerokosci drzwi i okien sa raportowane osobno dla danych JSON.
- Sciany zewnetrzne sa sumowane osobno i oznaczane kolorem kontrolnym `#FF00FF`.
- Raport Excel zawiera arkusze `Podsumowanie`, `Odcinki` i `Kontrola`.
- Eksport do `.xlsx`, `.csv`, `.json`.
- Eksport overlay `.svg` z kolorowym oznaczeniem odcinkow.
- Eksport kontrolnego PDF z cienka kolorowa nakladka na oryginalny PDF albo na pusty arkusz dla danych JSON.
- Kontrolny PDF automatycznie dzieli duze lub geste plany na powiekszone fragmenty po stronie z pelnym rzutem, zeby dalo sie sprawdzac i poprawiac odcinki.
- Testy jednostkowe oparte na standardowym `unittest`.

## Uruchomienie z terminala

```powershell
python run_app.py
python -m wall_pdf_analyzer.cli examples\sample_project.json out\raport.xlsx --overlay out\kontrola.svg
python -m wall_pdf_analyzer.cli rzut.pdf out\raport.xlsx --overlay out\kontrola.svg --overlay-pdf out\kontrola.pdf --pdf-scale 100
python -m wall_pdf_analyzer.cli skan.pdf out\raport.xlsx --overlay-pdf out\kontrola.pdf --raster --calibration-pixels 420 --calibration-meters 3.0
python -m wall_pdf_analyzer.gui
```

`--pdf-scale 100` oznacza skale `1:100`.

## Budowanie pliku EXE

```powershell
python -m pip install pyinstaller
python -m PyInstaller "Wall PDF Analyzer.spec" --noconfirm
```

Gotowy plik pojawi sie w:

```text
dist\Wall PDF Analyzer\Wall PDF Analyzer.exe
```

## Testy

```powershell
python -m unittest discover -s tests
python -m compileall wall_pdf_analyzer run_app.py
```

## Format wejsciowy

Program przyjmuje:

- JSON z gotowa geometria scian.
- PDF wektorowy, w ktorym sciany sa narysowane jako odcinki/linie.

Przyklad JSON znajduje sie w [examples/sample_project.json](examples/sample_project.json).

Najwazniejsze pola JSON:

- `scale.drawing_units_per_meter` okresla, ile jednostek rysunku odpowiada jednemu metrowi.
- `wall_types` definiuje kody, nazwy, kolory i reguly typow scian.
- `wall_segments` zawiera odcinki z punktami `start` i `end`, typem sciany, strona PDF, pewnoscia rozpoznania i opcjonalnymi otworami.
- `measurement_basis` opisuje, skad pochodzi pomiar.
- `centerline_or_face` okresla, czy pomiar jest po osi, krawedzi, czy jest niejasny.
- `openings[].width` jest szerokoscia otworu w jednostkach rysunku.
- `exterior: true` na typie lub odcinku oznacza sciane zewnetrzna.

## Zakres PDF

Importer PDF wyciaga proste odcinki z geometrii wektorowej PDF. W raporcie oznacza metode jako `vector_geometry_pdf_points_scaled`, zapisuje typ PDF, zrodlo skali, zalozenia oraz ostrzezenia.

Skan lub raster bez linii wektorowych moze byc analizowany po kalibracji znanym odcinkiem. W GUI program pokazuje pierwsza strone, pozwala kliknac dwa punkty i wpisac dlugosc. W CLI trzeba podac `--raster --calibration-pixels ... --calibration-meters ...`.

Wyniki ze skanow sa oznaczane jako `raster_image_calibrated` i maja nizsza pewnosc, bo sa wnioskowane z obrazu.

Drzwi i okna sa wykrywane heurystycznie. Program szuka przerw w jednej linii sciany, dodatkowych kresek rownoleglych dla okien i linii skrzydla dla drzwi. Takie otwory sa oznaczane w overlay i wymagaja kontroli przed uzyciem wartosci netto.

Gdy PDF zawiera widoczne oznaczenia typow scian, np. `IV20`, `IV31`, `IV30`, `IV02`, `YV...` lub `BV...`, program uzywa ich jako wskazowek. Najpierw znajduje najblizszy odcinek sciany przy etykiecie, potem dolacza tylko odcinki polaczone z ta sciana. Odcinki niezalezne od tagow sa odrzucane, zeby nie liczyc schodow, mebli, sanitariatow i innych symboli technicznych jako scian.

Kontrolny PDF ma cienkie linie nakladki. Dla duzych lub gestych planow po stronie z pelnym rzutem dodawane sa kolejne strony z powiekszonymi fragmentami, zeby nie trzeba bylo poprawiac odcinkow na nieczytelnym przyblizeniu calego arkusza.

## Zastrzezenie

Pomiary z rysunkow moga wplywac na koszty, zamowienia i decyzje budowlane. Wyniki nalezy zweryfikowac z oryginalnymi plikami CAD/BIM, oficjalnymi wymiarami albo pomiarem na miejscu przed zamawianiem materialow, wycena lub wykonaniem prac.

## Najblizsze kroki rozwoju

1. Dodac reczna edycje otworow drzwiowych i okiennych w GUI.
2. Dodac zapisywanie recznie poprawionego projektu do JSON.
3. Dodac kontrolny PDF z rasteryzowanym tlem dla podgladu JSON bez oryginalnego PDF.
4. Dodac historie zmian i wersjonowanie raportow.
5. Dodac eksport regul specjalnych dla typow takich jak `NNLK`.
