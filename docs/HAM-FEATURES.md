# Funkcje krótkofalarskie tego forka

Siedem dodatków zbudowanych na istniejącym potoku raportowania (Discord, `ReportingEngine`).
Wszystkie są **domyślnie wyłączone**, poza dziennikiem aktywności (punkt 6). Alerty trafiają
na Discorda, więc wymagają skonfigurowanego **Settings → Spotting and reporting → Discord alert
settings** (włączony Discord + adres webhooka).

| # | Funkcja | Gdzie w GUI |
| --- | --- | --- |
| 1 | Harmonogram przelotów satelitów | Settings → **Satellite passes** |
| 2 | Obrazy SSTV/FAX na Discorda | Spotting and reporting → Discord |
| 3 | Alerty o radiosondach | Spotting and reporting → **Radiosonde alerts** |
| 4 | Lista obserwowanych znaków | Spotting and reporting → **Callsign alerts** |
| 5 | Alert „nowy kraj” | Spotting and reporting → **Callsign alerts** |
| 6 | Dziennik aktywności, heatmapa, eksport ADIF | Settings → **Activity statistics** |
| 7 | Monitor beaconów NCDXF | Settings → **Plugins** (plugin `ncdxf`) |

Po aktualizacji paczki: `sudo apt install python3-sgp4` (tylko dla przelotów satelitów, patrz niżej).

---

## 1. Harmonogram przelotów satelitów

**Settings → Satellite passes.** Odbiornik sam przełącza profil SDR na czas przelotu
(od AOS do LOS) i wraca do poprzedniego profilu po zakończeniu.

1. Zainstaluj bibliotekę orbit: `sudo apt install python3-sgp4` i zrestartuj usługę.
   Bez niej strona pokazuje komunikat „orbit library not installed”, a reszta aplikacji działa normalnie.
2. Zaznacz **Enable**, dodaj satelity do listy: nazwa (z listy podpowiedzi albo wpisana ręcznie),
   **profil SDR**, który ma zostać włączony na przelot, i minimalna elewacja (0–90°).
3. Tabela **Upcoming passes** pokazuje nadchodzące przeloty na najbliższe 48 godzin.

Jak to działa:
- Dane orbitalne (TLE) są pobierane z celestraka co ok. 12 godzin i trzymane w pamięci podręcznej
  (`tle.json` w katalogu danych), a przy błędzie pobierania używana jest ostatnia kopia.
- Pozycja odbiornika pochodzi z `receiver_gps` (General Settings).
- **Przelot, w którym ktoś słucha odbiornika, jest pomijany** (ta sama zasada co przy zwykłym
  harmonogramie profili). Jeśli słuchacz zmieni profil w trakcie przelotu, po LOS profil nie jest
  wymuszany z powrotem.
- Dekodery działają w tle tylko, jeśli plan pasm ma częstotliwość danego trybu w zakresie profilu.
  Dodałem wpis `sstv` na 145,800 MHz (ISS) do `bands*.json` obok istniejącego `packet` 145,825 MHz.
  Pamiętaj, że w **Background decoding** musi być włączony **SSTV** i usługi tła.

Uwagi:
- Nazwy muszą pasować do danych celestraka. Na przykład AO-91 występuje tam jako `RADFXSAT (FOX-1B)`,
  a `SO-50` i `AO-95` rozpoznawane są po fragmencie nazwy. NOAA 15/18/19 są pobierane osobno po numerze katalogowym.
- Odbiornik **nie koryguje Dopplera** w czasie przelotu (dryf ok. ±3,4 kHz na 145,8 MHz). Do tego służy
  plugin `doppler` z katalogu pluginów.
- **Obrazy Meteor-M2 LRPT nie są wysyłane**: dekoder upstreama zostawia same surowe ramki `.cadu`
  (`--finish_processing` jest tam wyłączone), więc nie powstaje plik obrazu.

## 2. Obrazy SSTV i FAX na Discorda

**Spotting and reporting → Discord alert settings → „Send received SSTV/FAX images to Discord”.**
Gotowy obraz (po konwersji do PNG) leci na webhook jako załącznik z opisem: tryb, częstotliwość, pasmo i czas UTC.
Dotyczy tylko dekodowania w tle (usługa SSTV/FAX), a nie sesji słuchaczy w przeglądarce, więc nie ma duplikatów.

## 3. Alerty o radiosondach

**Spotting and reporting → Radiosonde alerts.**
- **Alert when a radiosonde is near the receiver** (włącznik), promień w km (domyślnie 50, zakres 5–500) i
  cooldown (domyślnie 30 min, osobno dla każdej sondy).
- Dwa rodzaje alertów: *near* (sonda w promieniu) i *landing* (sonda opada szybciej niż 5 m/s, a przewidywane
  miejsce lądowania mieści się w promieniu). Wiadomość zawiera linki do SondeHub i mapy.
- **Miejsce lądowania jest przybliżone**: prosta ekstrapolacja z aktualnej prędkości opadania i kursu,
  **bez korekty na wiatr**. Traktuj je jako orientację, a nie dokładną predykcję.
- Wysokość terenu przyjmowana jest z `receiver_asl` (General Settings).

## 4. Lista obserwowanych znaków

**Spotting and reporting → Callsign alerts → „Enable the callsign watchlist”.**
Pole **Watched callsigns**: jeden znak lub wzorzec w linii, `*` jako dzika karta (np. `SP3*`, `*/P`),
`#` zaczyna komentarz. Dopasowanie ignoruje wielkość liter, sufiks `-SSID` i oznaczenia `/P`, `/M`, `/QRP`,
`/MM`, `/AM`. Obejmuje FT8, FT4, WSPR i inne tryby WSJT-X, JS8Call oraz APRS (statki AIS są pomijane).
Powtórne alerty dla tego samego znaku blokuje **cooldown** (domyślnie 30 min).

Wykrywa też wiadomości bez lokatora (np. „CQ DX W1AW”), które zwykłe raporty (PSKReporter itp.) pomijają,
a przy tym nie zmienia niczego z tego, co te raporty dostają.

## 5. Alert „nowy kraj”

**Callsign alerts → „Alert on new countries”.** Gdy usłyszysz stację z kraju, którego jeszcze nie było
(FT8/FT4/WSPR/JS8 i pokrewne), dostajesz alert. Zbiór usłyszanych krajów jest trwały
(`seen_countries.json` w katalogu danych).

- To alert **na nazwę kraju z prefiksu**, a nie ścisły DXCC: w danych nie ma identyfikatorów DXCC ani stref CQ.
- Przez **pierwsze 24 godziny** (konfigurowalne: *New country learning period*) funkcja tylko się uczy
  i nie wysyła alertów, żeby na starcie nie zalać Discorda każdym już słyszalnym krajem.

## 6. Dziennik aktywności, heatmapa i ADIF

Domyślnie **włączony** (`activity_enabled`), baza SQLite `activity.db` w katalogu danych, retencja 90 dni.
Zapisuje zdarzenia Signal Alert oraz usłyszane stacje (te z lokatorem) z FT8, FT4, WSPR, JS8 i pokrewnych trybów.

**Settings → Activity statistics**:
- heatmapa pasmo × godzina (okres 1/7/30/90 dni, czas UTC albo lokalny serwera), liczniki alertów i stacji,
- **eksport ADIF** (`owrx-heard.adi`): usłyszane stacje z pasmem, częstotliwością, trybem, lokatorem i SNR;
  `MY_GRIDSQUARE` liczony z pozycji odbiornika. To logi nasłuchu, a nie łączności.
  Zakres: `?days=30` albo `?from=2026-11-01&to=2026-11-30`.

Wyłączenie: klucz `activity_enabled` (np. w JSON File Editor lub `settings.json`); nie ma jeszcze przełącznika w GUI.

## 7. Monitor beaconów NCDXF/IARU

Plugin po stronie przeglądarki. **Settings → Plugins**, włącz `ncdxf` (nie jest włączony domyślnie), potem na stronie
odbiornika pojawi się przycisk **Beacons**. Okno pokazuje zegar UTC, bieżący slot 10 s w 3-minutowym cyklu i dla
pięciu częstotliwości (14,100, 18,110, 21,150, 24,930 i 28,200 MHz), który beacon nadaje teraz i który będzie następny.
Gdy waterfall obejmuje daną częstotliwość, oznacza „heard” (słychać) albo „quiet”; w przeciwnym razie „not covered”.

> **Wykrywanie nie było testowane na żywo**: wymaga dongla HF, który w chwili pisania był odłączony.
> Tabela harmonogramu i logika slotów były sprawdzone osobno.

---

## Rozwiązywanie problemów

- **Nic nie przychodzi na Discorda:** sprawdź, czy włączony jest *Discord* i podany webhook, a dana funkcja ma
  własny włącznik. Szczegóły błędów: Settings → Server Logs (po włączeniu „Debug”).
- **Brak przelotów:** strona Satellite passes pokaże powód (brak `python3-sgp4`, brak danych TLE, brak wpisów).
- **Zbyt dużo alertów:** zwiększ cooldown albo (przy sondach) zmniejsz promień.
