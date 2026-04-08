# HA Gestures Prototype

Runtime rozpoznawania gestow dalej siedzi po stronie Pythona (`MediaPipe Hand Landmarker + nasze prymitywy + engine gestow`).
Konfigurator GUI tez wraca do Pythona i jest teraz budowany na `flet`.
Ustawienia aplikacji sa trzymane w `settings.json`.

## Python runtime

Python odpowiada za:

- odczyt kamerki,
- landmarki dloni,
- prymitywy (`hand`, `palm_side`, `rotation`, `fingers`, `motion`),
- skladanie `compound_id`,
- dopasowanie nazwanych gestow z `gestures.yaml`.

Uruchomienie debug runtime:

```powershell
python -m ha_gestures.cli --camera 0 --show --print-every 10
```

Nowy wspolny entrypoint aplikacji:

```powershell
python -m ha_gestures.app settings
python -m ha_gestures.app preview
python -m ha_gestures.app run
python -m ha_gestures.app runtime
```

Na Windows `run` uruchamia tray aplikacji.
`runtime` zostaje technicznym trybem bez traya.

Domyslnie CLI i GUI czytaja:

- `settings.json`
- `gestures.yaml`
- `gesture_bindings.json`

## Studio GUI (Flet)

Nowy edytor jest uruchamiany jako czysta aplikacja Pythonowa:

```powershell
python -m ha_gestures.gui
```

Na ten moment GUI ma:

- zakladki `Editor`, `Bindings`, `About`,
- zakladki `Home Assistant` i `Runtime` do edycji `settings.json`,
- osobny edytor lewej i prawej dloni,
- klikalny szkielet dloni rysowany bezposrednio w `flet.canvas`,
- sterowanie `front/back` i `0/90/180/270`,
- przelaczanie stanu kazdego palca,
- tryb `one hand` lub `two hands`,
- preview `compound_id`,
- placeholderowa akcja przypisywana do gestu,
- liste zapisanych mapowan gest -> akcja,
- osobna strone `About` z logo i informacjami o projekcie.

## Gesture bindings JSON

Bindingi sa zapisywane jako JSON i maja juz osobne sekcje `action` oraz `execution`.

Przyklad:

```json
{
  "mode": "one_hand",
  "trigger_id": "right_back_0_00100",
  "gesture_name": "FUCK",
  "action": {
    "type": "placeholder",
    "label": "dimm light"
  },
  "execution": {
    "mode": "instant",
    "cooldown_ms": 800,
    "repeat_every_ms": 150
  }
}
```

Aktualnie wspierane tryby `execution.mode`:

- `instant`
- `hold_start`
- `hold_repeat`
- `hold_end`

## Python dependencies

```powershell
python -m pip install -r requirements.txt
```
