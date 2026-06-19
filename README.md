# Dawid-Kupiec

## Koncepcja aplikacji do analizy ścian z PDF

Aplikacja ma odczytywać rysunki techniczne z plików PDF, rozpoznawać skalę, identyfikować typy ścian oraz przygotowywać zestawienie długości do pobrania w formacie Excel. Okna i inne otwory nie powinny kończyć odcinka ściany, dlatego ich szerokość należy doliczać do całkowitej długości ściany. Ściana zewnętrzna budynku powinna być obliczana osobno i oznaczana innym kolorem, a każdy typ ściany powinien mieć własne oznaczenie kolorystyczne na pliku kontrolnym.

## Propozycje udoskonaleń modelu i aplikacji

### 1. Precyzyjny odczyt skali i kalibracja

- Automatyczne wykrywanie skali z opisu rysunku, tabelki projektowej albo wymiarów referencyjnych.
- Tryb ręcznej kalibracji, w którym użytkownik wskazuje znany odcinek na PDF, jeśli skala nie zostanie rozpoznana automatycznie.
- Walidacja skali przez porównanie kilku wymiarów z rysunku, aby wykryć błędnie zeskanowane lub przeskalowane PDF-y.
- Osobna obsługa PDF-ów wektorowych i skanów rastrowych, ponieważ wymagają innych metod odczytu geometrii.

### 2. Rozpoznawanie typów ścian

- Biblioteka typów ścian, np. zdefiniowane oznaczenia, grubości, kreskowania, warstwy CAD i kolory.
- Możliwość uczenia modelu na przykładach użytkownika: użytkownik oznacza kilka ścian danego typu, a system proponuje resztę.
- Reguły priorytetu dla niejednoznacznych przypadków, np. gdy kolor, grubość i opis tekstowy wskazują różne typy.
- Osobne wykrywanie ścian zewnętrznych na podstawie obrysu budynku, ciągłości konturu, grubości i relacji do pomieszczeń.

### 3. Liczenie długości ścian z uwzględnieniem otworów

- Traktowanie okien i drzwi jako elementów leżących w ścianie, a nie jako końców ściany.
- Łączenie współliniowych fragmentów ścian rozdzielonych otworami w jeden odcinek obliczeniowy.
- Raportowanie długości brutto ściany, długości otworów oraz opcjonalnie długości netto, jeżeli użytkownik będzie tego potrzebował.
- Oznaczanie miejsc, w których algorytm połączył odcinki przez okno lub drzwi, aby użytkownik mógł łatwo sprawdzić decyzję modelu.

### 4. Kontrola jakości i tryb weryfikacji

- Generowanie podglądu PDF z kolorową nakładką: każdy typ ściany w innym kolorze, ściana zewnętrzna osobno, a elementy nierozpoznane wyróżnione kolorem ostrzegawczym.
- Wyświetlanie zakresu, który został przeliczony, np. przez obramowanie analizowanego obszaru albo listę stron i fragmentów PDF.
- Dodanie poziomu pewności dla każdego odcinka ściany, np. wysoka, średnia lub niska pewność rozpoznania.
- Panel korekty ręcznej, w którym użytkownik może zmienić typ ściany, połączyć odcinki, usunąć błędne rozpoznanie albo dodać brakujący fragment.

### 5. Eksport do Excela

- Arkusz zbiorczy z sumami długości według typu ściany.
- Osobny arkusz dla ścian zewnętrznych budynku.
- Kolumny: typ ściany, kolor oznaczenia, długość, jednostka, strona PDF, zakres analizy, poziom pewności i komentarz.
- Linki albo identyfikatory pozycji prowadzące do oznaczeń na podglądzie PDF.
- Możliwość eksportu także do CSV, PDF z adnotacjami oraz pliku JSON dla integracji z innymi systemami.

### 6. Obsługa wyjątków projektowych

- Lista reguł specjalnych dla typów takich jak NNLK, aby aplikacja wiedziała, czy mają być kolorowane, pomijane, liczone osobno lub raportowane bez oznaczania.
- Wykrywanie ścian łukowych, ukośnych, warstwowych i przerywanych.
- Obsługa wielu kondygnacji, wielu stron PDF i różnych skal w jednym dokumencie.
- Wykrywanie legendy rysunku i automatyczne mapowanie oznaczeń z legendy na typy ścian.

### 7. Bezpieczeństwo i audyt obliczeń

- Historia zmian po korektach użytkownika.
- Wersjonowanie wyników, aby można było porównać kolejne przeliczenia.
- Raport audytowy pokazujący, jakie reguły zastosowano do każdego typu ściany.
- Oznaczanie elementów wymagających ręcznego potwierdzenia przed finalnym eksportem.

## Proponowany przepływ pracy użytkownika

1. Użytkownik przesyła PDF.
2. Aplikacja wykrywa skalę, strony i zakres analizy.
3. Model rozpoznaje ściany, typy ścian, ściany zewnętrzne i otwory.
4. System łączy odcinki ścian przerwane przez okna lub drzwi.
5. Użytkownik otrzymuje podgląd z kolorową nakładką i listą pozycji do sprawdzenia.
6. Użytkownik zatwierdza lub poprawia wyniki.
7. Aplikacja generuje Excel oraz oznaczony plik kontrolny do pobrania.
