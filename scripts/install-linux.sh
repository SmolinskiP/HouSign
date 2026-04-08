#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"

print_step() {
  printf '\n[%s] %s\n' "$1" "$2"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

install_system_packages() {
  if command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip portaudio19-dev libasound2-dev
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip python3-virtualenv portaudio-devel alsa-lib-devel
    return
  fi

  if command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python python-pip portaudio
    return
  fi

  if command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y python3 python3-pip python3-virtualenv portaudio-devel alsa-devel
    return
  fi

  echo "Unsupported package manager. Install Python 3, pip, venv and PortAudio manually."
  exit 1
}

configure_home_assistant() {
  local ha_url=""
  local ha_token=""

  printf '\nHome Assistant configuration\n'
  printf 'Leave fields blank to keep current values.\n'
  printf 'Example URL: http://homeassistant.local:8123/\n'
  read -r -p "Home Assistant URL: " ha_url
  read -r -p "Long-Lived Access Token: " ha_token

  if [[ -z "${ha_url}" && -z "${ha_token}" ]]; then
    echo "Keeping existing Home Assistant settings."
    return
  fi

  "${VENV_DIR}/bin/python" - <<'PY' "${PROJECT_DIR}/settings.json" "${ha_url}" "${ha_token}"
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
ha_url = sys.argv[2]
ha_token = sys.argv[3]
payload = json.loads(settings_path.read_text(encoding="utf-8"))
payload.setdefault("ha", {})
if ha_url:
    payload["ha"]["url"] = ha_url
if ha_token:
    payload["ha"]["token"] = ha_token
settings_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

  echo "Updated ${PROJECT_DIR}/settings.json"
  echo "Token instructions:"
  echo "  1. Open Home Assistant."
  echo "  2. Go to your profile page."
  echo "  3. Create a Long-Lived Access Token for HouSign."
}

print_step "1/5" "Installing system packages"
install_system_packages

print_step "2/5" "Checking required tools"
require_command python3

print_step "3/5" "Creating virtual environment"
if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

print_step "4/5" "Installing Python dependencies"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"

print_step "5/5" "Optional Home Assistant setup"
configure_home_assistant

printf '\nDone.\n'
printf 'Useful commands:\n'
printf '  Settings UI: %s\n' "${VENV_DIR}/bin/python -m ha_gestures.app settings"
printf '  Runtime:     %s\n' "${VENV_DIR}/bin/python -m ha_gestures.app runtime"
printf '  Preview:     %s\n' "${VENV_DIR}/bin/python -m ha_gestures.app preview"
