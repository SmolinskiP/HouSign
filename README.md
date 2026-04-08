# HouSign — Gesture Control for Home Assistant

Control your smart home with hand gestures. No buttons, no voice, no phone — just a wave.

HouSign watches your camera in the background, detects hand gestures using MediaPipe, and fires actions in Home Assistant the moment it recognizes what you're doing.

---

## 📺 See it in action

<!-- YouTube showcase video -->
> 🎬 [Watch the demo](https://youtu.be/3JQjFe2N2d4)
> 
<img width="1907" height="981" alt="image" src="https://github.com/user-attachments/assets/d74510da-50e6-4439-b522-8ee54a7bba31" />

---

## What it does

- Runs quietly in the **system tray** — starts with Windows, stays out of your way
- Uses your **webcam** to track hand gestures in real time
- Sends commands to **Home Assistant** via WebSocket (lights, media players, scenes, scripts — anything)
- Supports an **activation gesture** (like a wake word, but for your hands) so it only listens when you want it to
- Plays **sound feedback** so you know when it picked up your gesture
- Comes with a clean **settings UI** to configure everything without touching JSON

---

## Getting started

### Option 1 — Windows installer (recommended)

Download `HouSign-Setup.exe` from [Releases](https://github.com/SmolinskiP/HouSign/releases). Direct link - [HouSign-Setup.exe](https://github.com/SmolinskiP/HouSign/releases/latest/download/HouSign-Setup.exe), run it, enter your Home Assistant URL and token, done.

The installer handles everything — shortcuts, autostart option, default config.

<img width="1196" height="867" alt="image" src="https://github.com/user-attachments/assets/372b499b-57fa-446c-8a68-5616761df33c" />

### Option 2 — Run from source

```bash
git clone https://github.com/SmolinskiP/HouSign
cd HouSign
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
python ha_gestures/app.py
```

Requires **Python 3.11**.

---

## Configuration

On first run, open **Settings** from the tray menu and fill in:

- **Home Assistant URL** — e.g. `http://homeassistant.local:8123/`
- **Long-Lived Access Token** — create one in HA under Profile → Security → Long-Lived Access Tokens

<img width="1875" height="409" alt="image" src="https://github.com/user-attachments/assets/048c6277-af07-48a4-b64f-0ae56a00cf55" />

### Activation gesture

By default, HouSign uses an activation mode — it won't fire commands until you make a specific pose (like an open palm held for ~600ms). This prevents accidental triggers while you're just moving around. You can disable it and go always-listening if you prefer.

<img width="840" height="935" alt="image" src="https://github.com/user-attachments/assets/d51c2a13-ed25-445e-8bbb-b0ab69bcdba7" />

---

## How gesture bindings work

<img width="1723" height="514" alt="image" src="https://github.com/user-attachments/assets/74063caf-30a8-4928-b1b9-f0f81253cca0" />

Each binding connects a gesture to a Home Assistant action:

| Field | Example |
|-------|---------|
| Gesture | `open_palm` |
| Mode | `one_hand` |
| Action type | `service` |
| Domain | `light` |
| Service | `turn_off` |
| Entity | `light.living_room` |

<img width="1856" height="532" alt="image" src="https://github.com/user-attachments/assets/377d0fa9-9956-4006-ad09-969c93d7976f" />

Execution modes:
- **instant** — fires once, immediately ends the session
- **hold & repeat** — keeps firing while you hold the gesture (great for dimming)

---

## System tray

The tray icon shows the current runtime state and lets you open settings, start a preview, reload config, or quit.

<img width="233" height="196" alt="image" src="https://github.com/user-attachments/assets/c3da1005-8176-472d-bd1c-c187edd6ef0c" />

---

## Requirements

- Windows 10/11 (64-bit)
- Webcam
- Home Assistant instance reachable on your local network

---

## Built with

- [MediaPipe](https://developers.google.com/mediapipe) — hand tracking
- [Flet](https://flet.dev) — settings UI
- [pystray](https://github.com/moses-palmer/pystray) — system tray
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) — sound feedback
- [PyInstaller](https://pyinstaller.org) — Windows packaging

---

## Support the project

If HouSign saves you a few trips to the light switch, consider buying me a coffee ☕

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-☕-yellow?style=flat-square)](https://buymeacoffee.com/smolinskip)

---

## License

MIT — do whatever you want with it.
