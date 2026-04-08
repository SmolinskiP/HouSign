# HA Gestures - zalozenia prototypu

## Cel

Prototyp ma umozliwic sterowanie Home Assistantem za pomoca gestow rozpoznawanych poza HA przez zewnetrzna aplikacje.

Na tym etapie celem nie jest pelna integracja HA, tylko szybkie sprawdzenie:

- czy detekcja gestow jest wystarczajaco stabilna,
- czy opoznienie jest akceptowalne,
- czy model sterowania gestami jest naturalny w codziennym uzyciu,
- czy da sie wygodnie mapowac gesty na akcje w Home Assistant.

## Architektura prototypu

Na etapie eksperymentu przyjmujemy prosty model:

- zewnetrzna aplikacja wykrywa gesty,
- aplikacja laczy sie z Home Assistantem po WebSocket API,
- po rozpoznaniu gestu aplikacja wysyla komende lub odpala akcje w HA,
- logika mapowania gestow na akcje moze byc poczatkowo trzymana po stronie aplikacji.

Docelowo czesc tej logiki moze zostac przeniesiona do integracji HA, ale nie jest to wymagane dla prototypu.

## Wybor bazy modelowej

Wybrana baza modelowa dla pierwszego dzialajacego prototypu:

- `MediaPipe Hand Landmarker` jako glowny silnik percepcji dloni,
- opcjonalnie `MediaPipe Gesture Recognizer` tylko jako zrodlo dodatkowych hintow dla prostych gestow statycznych.

Powod wyboru:

- Hand Landmarker zwraca `handedness`,
- zwraca `21` landmarkow dloni,
- zwraca `world landmarks`,
- dobrze nadaje sie do strumienia wideo,
- pozwala budowac modulowy silnik oparty na prymitywach zamiast zamknietego klasyfikatora gestow.

Nie wybieramy Gesture Recognizer jako glownej podstawy systemu, bo jego gotowe klasy sa zbyt waskie dla naszego scenariusza i nie rozwiazuja problemu gestow ruchowych oraz dwurecznych.

## Kierunek rozpoznawania

Projekt przyjmuje podejscie `video-first`.

To znaczy:

- kamera dostarcza ciagly strumien obrazu,
- z kazdej klatki lub okna czasowego wyciagamy stan obu dloni,
- gest nie jest pojedyncza etykieta z modelu, tylko wynikiem analizy cech przestrzennych i ruchowych,
- system ma byc przygotowany na gesty jedno- i dwureczne.

Na poziomie architektury rozpoznawanie dzielimy na 3 warstwy:

1. `Perception`
   detekcja dloni, landmarki, orientacja, kierunek ruchu, stan palcow
2. `Interpretation`
   zamiana surowych cech na pose, ruch i kandydatow gestow
3. `Action`
   mapowanie gestu na akcje Home Assistant

## Zasada architektoniczna

Silnik ma byc modulowy.

Kluczowe zalozenie:

- model percepcyjny nie zwraca gotowej finalnej decyzji "to jest gest X",
- model zwraca prymitywy opisujace stan dloni,
- osobna warstwa interpretuje te prymitywy i ocenia, jaki gest zaszedl.

Minimalny zestaw prymitywow zwracanych przez warstwe percepcji:

- lewa / prawa dlon,
- rotacja dloni,
- przod / tyl dloni,
- stan kazdego palca: wyprostowany / schowany,
- polozenie dloni,
- kierunek ruchu,
- predkosc ruchu,
- relacja miedzy dwiema dlonmi.

Na tej podstawie warstwa interpretacji sklada finalny gest.

Przyklady:

- `thumb_up` = kciuk wyprostowany + pozostale palce schowane + odpowiednia orientacja dloni,
- `ok_sign` = zlaczenie kciuka i wskazujacego + pozostale palce wyprostowane,
- `swipe_left` = otwarta dlon + ruch w lewo przekraczajacy prog,
- `dim_hold` = odpowiedni uklad palcow + orientacja + utrzymany ruch / pozycja w czasie,
- `two_hand_expand` = dwie dlonie + wzrost odleglosci miedzy nimi.

To podejscie daje kilka korzysci:

- nowe gesty mozna dodawac bez retrenowania calego systemu,
- latwiej debugowac bledy rozpoznawania,
- latwiej stroic progi i histereze,
- mozna osobno rozwijac percepcje i logike gestow,
- system lepiej nadaje sie do gestow niestandardowych dla smart home.

## Docelowe cechy, ktore system ma rozpoznawac

Scenariusz docelowy dla silnika rozpoznawania:

- ktora to dlon: lewa / prawa,
- orientacja dloni co `90` stopni,
- przod czy tyl dloni,
- stan kazdego palca: wyprostowany / zlozony,
- polozenie dloni w kadrze,
- kierunek i charakter ruchu dloni,
- relacja pomiedzy dwiema dlonmi,
- klasyczne gesty statyczne typu `OK`, `Thumbs Up`, `Victory`, `Open Palm`.

To oznacza, ze silnik powinien umiec opisywac reke nie tylko jedna etykieta, ale zestawem cech.

## Reprezentacja stanu dloni

Wewnetrznie pojedyncza dlon powinna byc opisana jako obiekt stanu:

```json
{
  "hand_id": "left",
  "palm_side": "front",
  "rotation_quadrant": 90,
  "fingers": {
    "thumb": "extended",
    "index": "extended",
    "middle": "folded",
    "ring": "folded",
    "pinky": "folded"
  },
  "position": {
    "x": 0.42,
    "y": 0.31,
    "z": -0.12
  },
  "motion": {
    "direction": "up",
    "speed": 0.37
  },
  "confidence": 0.93
}
```

Taki model jest lepszy niz sama etykieta gestu, bo pozwala skladac wiele gestow z tych samych klockow.

Przyklady:

- `right hand + open palm + move left`
- `left hand + index extended + hold steady`
- `two hands + palms facing each other + moving apart`

## Gest jako kombinacja cech

Docelowo gest powinien byc definiowany jako kombinacja:

- ukladu palcow,
- orientacji dloni,
- strony dloni,
- liczby widocznych dloni,
- ruchu w czasie,
- relacji miedzy dlonmi.

Przyklady definicji:

- `OK sign` = kciuk i wskazujacy zlaczone + pozostale palce wyprostowane,
- `swipe_right` = otwarta dlon + dominujacy ruch w prawo przez okreslony czas,
- `volume_up_hold` = otwarta dlon + ruch / utrzymanie ku gorze,
- `two_hand_expand` = dwie dlonie skierowane do siebie + rosnaca odleglosc miedzy srodkami dloni,
- `two_hand_join` = dwie dlonie + malejaca odleglosc miedzy nimi.

W praktyce oznacza to, ze definicja gestu powinna byc mozliwa do zapisania jako zestaw warunkow logicznych i czasowych, a nie tylko jako nazwa klasy z modelu.

## Gesty jedno- i dwureczne

Silnik musi wspierac dwa poziomy gestow:

### 1. Gesty jednoreczne

Budowane z cech jednej dloni:

- `open_palm`,
- `closed_fist`,
- `ok_sign`,
- `victory`,
- `swipe_left`,
- `swipe_right`,
- `hand_up_hold`,
- `hand_down_hold`.

### 2. Gesty dwureczne

Budowane z relacji dwoch dloni:

- odleglosc miedzy dlonmi,
- czy dlonie sa do siebie rownolegle,
- czy patrza w tym samym kierunku,
- ruch zblizania / oddalania,
- symetria ukladu palcow.

Przyklady:

- `two_hand_expand` -> rozjasnij lub zwieksz glosnosc,
- `two_hand_contract` -> sciemnij lub scisz,
- `two_hand_hold_open` -> aktywuj scene,
- `two_hand_push_forward` -> akcja specjalna lub tryb "confirm".

## Pipeline rozpoznawania wideo

Rekomendowany pipeline:

1. detekcja obu dloni w kazdej klatce,
2. estymacja landmarkow dla kazdej dloni,
3. stabilizacja i tracking tej samej dloni miedzy klatkami,
4. wyliczenie cech:
   - lewa / prawa dlon,
   - orientacja,
   - strona dloni,
   - stan palcow,
   - pozycja i predkosc,
   - relacje miedzy dlonmi,
5. zlozenie cech w `hand state`,
6. analiza okna czasowego `N` klatek,
7. klasyfikacja gestu:
   - regula,
   - state machine,
   - model sekwencyjny.

Na pierwszy etap nadal najbardziej sensowna jest hybryda:

- gotowy model do landmarkow i bazowych gestow statycznych,
- logika regułowa dla ruchu i gestow przedluzonych,
- pozniejsze douczenie modelu sekwencyjnego na zebranych danych.

## Co realnie powinno byc inferowane przez model

Nie wszystko trzeba wrzucac do jednego modelu.

Sensowny podzial odpowiedzialnosci:

- model 1: detekcja dloni i landmarki,
- model 2 lub warstwa geometryczna: stan palcow, rotacja, front / back,
- warstwa czasowa: kierunek ruchu, hold, swipe, circle,
- warstwa kompozycji: gesty dwureczne i niestandardowe definicje.

To jest lepsze od jednej "czarnej skrzynki", bo:

- latwiej debugowac bledy,
- latwiej zbierac dane,
- mozna szybko dodawac nowe gesty bez retrenowania wszystkiego,
- system jest bardziej przewidywalny.

## Notatka o ambicji zakresu

Scenariusz docelowy jest sensowny, ale to nie powinno oznaczac, ze pierwszy build ma umiec wszystko naraz.

Najbardziej krytyczne jest, aby juz pierwsza wersja silnika potrafila zwracac stabilnie:

- lewa / prawa dlon,
- landmarki,
- stan palcow,
- przyblizony kierunek ruchu,
- prosty opis relacji dla dwoch dloni.

Jesli te prymitywy beda stabilne, liczba mozliwych gestow faktycznie zrobi sie bardzo duza bez przebudowy calej architektury.

## Typy obslugiwanych gestow

W prototypie rozrozniamy dwa typy gestow:

### 1. Gesty pojedyncze

Gest jednorazowy, ktory po wykryciu wywoluje jedna konkretna akcje.

Przyklady:

- machniecie w lewo: wylacz swiatlo,
- machniecie w prawo: wlacz swiatlo,
- pokazanie otwartej dloni: stop / anuluj,
- gest "OK": uruchom skrypt lub scene,
- dwa szybkie tapniecia w powietrzu: play / pause.

Charakterystyka:

- wywolanie typu `fire-and-forget`,
- brak stanu ciaglego po stronie gestu,
- najlepiej nadaja sie do wlacz / wylacz / uruchom / toggle.

### 2. Gesty przedluzone

Gest utrzymywany w czasie, ktory podczas trwania steruje wartoscia ciagla lub krokowa.

Przyklady:

- dlon przesuwana do gory i utrzymywana: zwiekszanie glosnosci,
- dlon przesuwana w dol i utrzymywana: zmniejszanie glosnosci,
- przytrzymany ruch w prawo: rozjasnianie swiatla,
- przytrzymany ruch w lewo: sciemnianie swiatla,
- utrzymanie reki w pozycji "mute" przez 2 sekundy: wycisz.

Charakterystyka:

- gest ma poczatek, trwanie i koniec,
- podczas trwania moze generowac serie aktualizacji,
- nadaje sie do sterowania wartoscia: jasnosc, glosnosc, pozycja rolety, temperatura.

## Model zdarzen

Warto od poczatku przyjac prosty, czytelny model zdarzen wysylanych przez aplikacje.

### Gest pojedynczy

Minimalny payload:

```json
{
  "type": "single",
  "gesture": "swipe_right",
  "confidence": 0.94,
  "timestamp": "2026-04-03T12:00:00Z"
}
```

### Gest przedluzony

Minimalny payload:

```json
{
  "type": "continuous",
  "gesture": "raise_hand",
  "phase": "start",
  "confidence": 0.91,
  "timestamp": "2026-04-03T12:00:01Z"
}
```

W czasie trwania:

```json
{
  "type": "continuous",
  "gesture": "raise_hand",
  "phase": "update",
  "value": 0.62,
  "delta": 0.08,
  "confidence": 0.89,
  "timestamp": "2026-04-03T12:00:01.200Z"
}
```

Przy zakonczeniu:

```json
{
  "type": "continuous",
  "gesture": "raise_hand",
  "phase": "end",
  "timestamp": "2026-04-03T12:00:02.100Z"
}
```

### Znaczenie pol

- `type`: `single` albo `continuous`,
- `gesture`: nazwa gestu rozpoznanego przez silnik,
- `phase`: `start`, `update`, `end` dla gestow przedluzonych,
- `value`: znormalizowana wartosc z zakresu `0.0-1.0`,
- `delta`: zmiana od poprzedniej probki,
- `confidence`: pewnosc klasyfikacji,
- `timestamp`: czas zdarzenia.

## Mapowanie gestow na akcje HA

Na etapie prototypu mapowanie powinno byc jawne i proste do edycji.

Przyklad:

```yaml
single:
  swipe_right:
    action: light.turn_on
    target:
      entity_id: light.salon

  swipe_left:
    action: light.turn_off
    target:
      entity_id: light.salon

  ok_sign:
    action: script.turn_on
    target:
      entity_id: script.movie_mode

continuous:
  hand_up:
    mode: media_volume
    target:
      entity_id: media_player.salon

  hand_left:
    mode: brightness_down
    target:
      entity_id: light.salon
```

## Zasady obslugi gestow pojedynczych

- pojedynczy gest powinien odpalac akcje dopiero po przekroczeniu progu `confidence`,
- po rozpoznaniu trzeba wprowadzic krotki `cooldown`, zeby uniknac wielokrotnego odpalenia tej samej akcji,
- ten sam gest nie powinien byc interpretowany dwa razy z jednego ruchu,
- akcje powinny byc idempotentne tam, gdzie to mozliwe, np. `light.turn_on` zamiast niestabilnego `toggle`.

Sugestia startowa:

- `confidence_threshold`: `0.85`
- `cooldown_ms`: `700-1200`

## Zasady obslugi gestow przedluzonych

- gest przedluzony powinien miec wyrazny warunek wejscia, np. wykrycie przez minimum `300 ms`,
- po wejsciu w tryb `continuous` aplikacja powinna wysylac aktualizacje cyklicznie albo przy istotnej zmianie,
- po utracie gestu albo powrocie do neutralnej pozycji nalezy wyslac `end`,
- zmiany powinny byc ograniczone filtrowaniem i hysteresis, zeby uniknac skakania wartosci.

Sugestia startowa:

- `hold_threshold_ms`: `300-500`
- `update_interval_ms`: `100-200`
- `min_delta`: `0.03-0.08`
- `end_timeout_ms`: `250-400`

## Tryby sterowania dla gestow przedluzonych

Na start warto wspierac dwa tryby:

### 1. Sterowanie krokowe

Kazdy `update` powoduje krok w gore albo w dol.

Przyklady:

- glosnosc +/- 2%,
- jasnosc +/- 5%,
- roleta +/- jeden krok.

Zalety:

- prostsze do wdrozenia,
- latwiejsze do stabilizacji,
- lepsze na pierwszy prototyp.

### 2. Sterowanie proporcjonalne

Pozycja reki lub intensywnosc ruchu mapowana jest bezposrednio na wartosc.

Przyklady:

- wysokosc dloni = poziom glosnosci,
- odleglosc od punktu bazowego = poziom jasnosci.

Zalety:

- bardziej naturalne sterowanie,
- szybsza zmiana wartosci.

Wady:

- trudniejsze strojenie,
- wieksza wrazliwosc na szum i przypadkowe ruchy.

Dla pierwszej wersji prototypu rekomendowany jest tryb krokowy.

## Przykladowe scenariusze

### Sterowanie swiatlem

- `swipe_right` -> `light.turn_on`
- `swipe_left` -> `light.turn_off`
- `hand_right_hold` -> rozjasnianie
- `hand_left_hold` -> sciemnianie

### Sterowanie audio

- `open_palm` -> play / pause
- `hand_up_hold` -> glosniej
- `hand_down_hold` -> ciszej
- `mute_hold_2s` -> `media_player.volume_mute`

### Skrypty i sceny

- `ok_sign` -> uruchom scene wieczorna
- `double_wave` -> uruchom skrypt "good night"

## Wymagania niefunkcjonalne dla prototypu

- opoznienie od gestu do reakcji HA powinno byc subiektywnie "natychmiastowe",
- aplikacja musi logowac rozpoznane gesty i wykonane akcje,
- aplikacja musi pozwalac wlaczyc tryb debug z podgladem surowych zdarzen,
- utrata polaczenia z HA nie moze zawiesic aplikacji,
- brak rozpoznania gestu nie moze uruchamiac zadnej akcji domyslnej.

## Ryzyka

- falszywe trafienia przy gestach podobnych do siebie,
- zbyt duza liczba powtorzen jednego gestu,
- slaba ergonomia gestow przedluzonych przy dluzszym uzyciu,
- opoznienia i nierowny sampling przy sterowaniu ciaglym,
- trudnosc rozroznienia intencji: pojedynczy ruch vs poczatek gestu przedluzonego.

## Rekomendacje na pierwszy sprint

- zrobic 3 gesty pojedyncze,
- zrobic 2 gesty przedluzone,
- wdrozyc prosty plik konfiguracyjny mapujacy gesty na akcje,
- dodac logowanie zdarzen i wynikow wywolan HA,
- zaczac od sterowania krokowego dla glosnosci i jasnosci.

## Proponowany pierwszy zakres

- `swipe_right` -> wlacz swiatlo,
- `swipe_left` -> wylacz swiatlo,
- `ok_sign` -> odpal skrypt,
- `hand_up_hold` -> glosniej,
- `hand_left_hold` -> sciemniaj swiatlo.

To wystarczy, zeby sprawdzic:

- gesty binarne,
- gesty ciagle,
- wywolania serwisow HA,
- stabilnosc klasyfikacji,
- sensownosc UX.
