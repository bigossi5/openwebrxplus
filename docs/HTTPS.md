# HTTPS w OpenWebRX+ (Settings → General Settings → HTTPS)

Ten fork pozwala włączyć HTTPS bez ręcznego babrania się w certyfikatach: z poziomu
przeglądarki, z certyfikatem samopodpisanym albo zaufanym certyfikatem
Let's Encrypt (certbot).

## Po co HTTPS

Przeglądarki udostępniają część funkcji **tylko na stronach HTTPS** (albo `localhost`):

- powiadomienia przeglądarki (przycisk *Enable* w wtyczce **Alerts**),
- blokada wygaszania ekranu (wake lock),
- bezpieczniejsze logowanie do panelu administratora (hasło nie leci otwartym tekstem po sieci).

Na zwykłym `http://10.10.10.123:8073` te funkcje są blokowane przez samą przeglądarkę.

## Wymagania

Pakiet `openwebrx` z tego forka (wersja z sekcją **HTTPS** w General Settings) zawiera:

| Element | Gdzie | Po co |
| --- | --- | --- |
| `/usr/lib/openwebrx/ssl-helper` | instalowany z paczki | skrypt roota, który zapisuje certyfikaty |
| `/etc/sudoers.d/openwebrx-ssl` | tworzony w `postinst` | wąska reguła sudo dla użytkownika `openwebrx` |
| `openssl` | zależność paczki | generowanie certyfikatu samopodpisanego |
| `certbot` | zalecany pakiet | tylko dla Let's Encrypt: `sudo apt install certbot` |

Aktualizacja do tej wersji (na serwerze):

```bash
cd openwebrxplus && git pull
rm -f ../openwebrx_*.deb
dpkg-buildpackage -us -uc -b
sudo apt install -y ../openwebrx_*.deb
sudo systemctl restart openwebrx
```

## Opcja 1: certyfikat samopodpisany (najprościej, działa w LAN)

1. Zaloguj się do panelu i wejdź w **Settings → General Settings**, sekcja **HTTPS**.
2. Zaznacz **Enable HTTPS (a self-signed certificate is generated and installed automatically)**.
3. Pole **Domain name (FQDN)** zostaje wypełnione wykrytą nazwą hosta. Możesz ją zmienić;
   do certyfikatu trafiają też automatycznie adresy IP serwera, więc działa także wejście
   przez `https://10.10.10.123:8073`.
4. Kliknij **Apply and save** na dole strony.
5. Po kilku sekundach usługa sama się restartuje. **Zwykły `http://` na tym porcie przestaje
   działać.** Otwórz `https://ADRES:8073` (np. `https://10.10.10.123:8073`).
6. Przeglądarka pokaże ostrzeżenie o niezaufanym certyfikacie (to normalne dla certyfikatu
   samopodpisanego). Wybierz *Zaawansowane → Przejdź do strony*.

Certyfikat jest ważny 10 lat.

> **Uwaga o powiadomieniach.** Chrome/Edge potrafią odmówić powiadomień na stronie otwartej
> mimo ostrzeżenia o certyfikacie. Strona jest już „bezpiecznym kontekstem”, więc wake lock
> zadziała, ale jeśli powiadomienia mają działać na pewno, użyj opcji 2 (certyfikat zaufany).

## Opcja 2: zaufany certyfikat Let's Encrypt (certbot)

### Warunki wstępne (sprawdź PRZED włączeniem)

1. **Publiczna nazwa domeny** (np. `sdr.twojadomena.pl`) z rekordem **A** wskazującym na Twój
   publiczny adres IP. (Dla serwera wyłącznie w LAN bez domeny użyj opcji 1.)
2. **Przekierowanie portu 80** w routerze: `TCP 80 → 10.10.10.123:80`. Let's Encrypt łączy się
   z internetu na port 80, żeby potwierdzić, że domena jest Twoja.
3. **Port 80 na serwerze musi być wolny** na czas wystawiania certyfikatu (nic na nim nie może
   nasłuchiwać, np. nginx/apache). Sam OpenWebRX+ słucha na 8073, więc nie przeszkadza.
4. Zainstalowany `certbot`: `sudo apt install certbot`.

### Kroki

1. **Settings → General Settings → HTTPS**.
2. Zaznacz **Enable HTTPS**.
3. Zaznacz **Use a trusted Let's Encrypt certificate (certbot)**.
4. W polu **Domain name (FQDN)** wpisz swoją publiczną domenę (wykryta nazwa hosta jest tylko
   podpowiedzią i zwykle nie jest publiczna).
5. Opcjonalnie podaj **E-mail for Let's Encrypt** (powiadomienia o wygasaniu certyfikatu).
6. **Apply and save**. Wystawianie może potrwać do kilkudziesięciu sekund; strona czeka na wynik.
   Błąd (np. zajęty port 80, domena nie wskazuje na serwer) pojawi się w czerwonej ramce
   „Your settings could not be saved”, a nic się nie zmieni.
7. Po sukcesie usługa restartuje się i działa pod `https://TWOJA.DOMENA:8073` z zielonym
   kłódką, bez ostrzeżenia.

### Odnowienia

Certyfikat Let's Encrypt ważny jest 90 dni. Odnawia go systemowy timer certbota (zwykle
dwa razy dziennie sprawdza, czy to już czas). Po każdym odnowieniu certbot uruchamia nasz hook,
który kopiuje nowy certyfikat na miejsce i **restartuje OpenWebRX+** (krótkie rozłączenie
słuchaczy raz na ok. 2 miesiące). Nie musisz robić nic ręcznie.

Test na sucho:

```bash
sudo certbot certificates          # lista certyfikatów i terminy ważności
sudo certbot renew --dry-run       # symulacja odnowienia (uruchamia też hook)
systemctl list-timers | grep certbot
```

> Port 80 musi być osiągalny z internetu także w momencie odnowienia (nie tylko przy
> pierwszym wystawieniu).

## Wyłączanie HTTPS (powrót do http)

Odznacz **Enable HTTPS** i zapisz. Certyfikaty z `/etc/openwebrx` są usuwane, a usługa
wraca po kilku sekundach na zwykły `http://ADRES:8073`.

Certyfikat Let's Encrypt zostaje w `/etc/letsencrypt` (certbot nadal może go odnawiać).
Jeśli go nie potrzebujesz: `sudo certbot delete --cert-name TWOJA.DOMENA`.

## Jak to działa pod spodem

- OpenWebRX+ szuka certyfikatu **tylko przy starcie** w stałych ścieżkach
  `/etc/openwebrx/cert.pem` i `/etc/openwebrx/key.pem`. Jeśli oba pliki istnieją, startuje
  jako HTTPS, inaczej jako HTTP. Zmiana certyfikatu wymaga restartu usługi.
- HTTP i HTTPS **nie działają jednocześnie** na tym samym porcie (domyślnie 8073).
- Usługa działa jako użytkownik `openwebrx` i nie może pisać do `/etc/openwebrx` ani
  uruchamiać certbota, dlatego panel woła przez `sudo` skrypt `/usr/lib/openwebrx/ssl-helper`
  (reguła w `/etc/sudoers.d/openwebrx-ssl` dopuszcza tylko jego cztery polecenia).
- Skrypt waliduje wszystkie argumenty (nazwa domeny, e-mail, adresy IP) zanim zrobi cokolwiek
  z uprawnieniami roota i nigdy nie wykonuje ich jako polecenia powłoki.
- Restart jest zaplanowany z 3-sekundowym opóźnieniem (`systemd-run`), żeby nie zabić procesu,
  który jeszcze czeka na wynik skryptu.
- Klucz prywatny trafia do `key.pem` jako `root:openwebrx`, tryb `0640`; certyfikat `0644`.

## Ręczna obsługa z terminala

To samo co robi panel, np. gdy nie możesz wejść na stronę:

```bash
# certyfikat samopodpisany (nazwa hosta + opcjonalnie adresy IP)
sudo /usr/lib/openwebrx/ssl-helper selfsigned moj-serwer 10.10.10.123

# Let's Encrypt (domena + opcjonalnie e-mail)
sudo /usr/lib/openwebrx/ssl-helper letsencrypt sdr.twojadomena.pl ty@twojadomena.pl

# wyłączenie HTTPS
sudo /usr/lib/openwebrx/ssl-helper disable
```

Każde z poleceń planuje też restart usługi. Wszystko, co robi skrypt, widać w `Settings →
Server Logs` (po włączeniu „Debug” w General Settings) oraz w `sudo journalctl -u openwebrx -f`.

## Rozwiązywanie problemów

**Po włączeniu HTTPS strona się nie otwiera.** Wejdź przez `https://` (nie `http://`) i na
tym samym porcie. Jeśli coś poszło nie tak i chcesz awaryjnie wrócić do http:

```bash
sudo rm -f /etc/openwebrx/cert.pem /etc/openwebrx/key.pem
sudo systemctl restart openwebrx
```

**Błąd „sudo: a password is required” / „HTTPS setup failed”.** Brakuje reguły sudo
(np. po instalacji starszej paczki). Sprawdź plik i zainstaluj paczkę ponownie:

```bash
sudo ls -l /etc/sudoers.d/openwebrx-ssl /usr/lib/openwebrx/ssl-helper
sudo apt install --reinstall ../openwebrx_*.deb
```

**„certbot is not installed”.** `sudo apt install certbot`.

**„certbot failed (is port 80 free and reachable from the internet?)”.** Sprawdź po kolei:
rekord A domeny (`dig +short sdr.twojadomena.pl` zwraca Twój publiczny IP), przekierowanie
portu 80 w routerze, brak innej usługi na porcie 80 (`sudo ss -ltnp | grep ':80 '`). Przy
wielu nieudanych próbach Let's Encrypt chwilowo blokuje domenę, więc poczekaj godzinę.

**Przeglądarka nadal nie daje włączyć powiadomień.** Przy certyfikacie samopodpisanym patrz
uwaga w opcji 1. Alternatywa tylko dla Twojej przeglądarki, bez HTTPS: w Chrome/Edge wpisz
`chrome://flags/#unsafely-treat-insecure-origin-as-secure`, dodaj `http://10.10.10.123:8073`,
ustaw *Enabled* i zrestartuj przeglądarkę.

## Znane ograniczenia

- Obsługiwana jest tylko weryfikacja **HTTP-01 na porcie 80**. Weryfikacja DNS-01 (bez otwierania
  portów, np. dla serwera tylko w LAN z domeną w Cloudflare) nie jest zaimplementowana.
- Ciasteczka sesji nie mają flagi `Secure` (to kod z upstreamu, świadomie nie ruszany w forku).
- Nie ma przekierowania z `http` na `https`, bo oba protokoły nie mogą współdzielić portu.
