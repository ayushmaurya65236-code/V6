# AURA LINK V6

**Gesture-controlled computer vision with an optional ESP32 hardware link.**

AURA LINK V6 is a Python project combining webcam hand tracking, a visual HUD, configurable gesture actions, and optional ESP32 communication. Start with the software/simulator path before connecting hardware.

<p align="center">
  <a href="https://github.com/ayushmaurya65236-code/V6/archive/refs/heads/main.zip"><strong>⬇ Download ZIP</strong></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/ayushmaurya65236-code/V6/blob/main/docs/index.html"><strong>Interactive Setup Guide</strong></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/ayushmaurya65236-code/V6/issues"><strong>Report a Problem</strong></a>
</p>

## What it does

- Webcam-based hand tracking using MediaPipe Tasks and OpenCV.
- Animated visual HUD for gesture feedback.
- Optional ESP32 discovery and HTTP communication.
- Configurable demo mode, camera index, web dashboard, and extended gestures.
- Separate ESP32 Arduino firmware example in `hardware/esp32/`.

> **Compatibility note:** Hardware commands depend on compatible firmware and matching settings. The included ESP32 sketch is a documented hardware starting point; do not assume every software feature automatically maps to hardware.

## Quick start (Windows)

### 1. Install prerequisites

Install **Python** and **Git**. Use a Python version supported by the MediaPipe package for your operating system. If package installation fails, check MediaPipe's current compatibility before changing versions.

### 2. Download the project

**Simplest option:** [Download the latest ZIP](https://github.com/ayushmaurya65236-code/V6/archive/refs/heads/main.zip), extract it, and open the extracted `V6-main` folder in Terminal or VS Code.

Or use Git:

```powershell
git clone https://github.com/ayushmaurya65236-code/V6.git
cd V6
```

### 3. Create an environment and install dependencies

Run these commands from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks environment activation, use Command Prompt and run `.venv\Scripts\activate.bat`, or follow your system's Python environment guidance.

### 4. Configure and run

```powershell
Copy-Item .env.example .env
python main.py
```

Allow camera access if requested. Review `.env.example` for configuration options; edit your local `.env` only when needed. Keep secrets and Wi-Fi credentials out of Git.

### 5. Try simulator mode first

If you want to test without an ESP32, set `AURA_DEMO_MODE=true` in your local `.env` file if supported by your current build, then launch again. Confirm the behavior in the HUD before moving on to hardware.

## Interactive setup guide

Open the [step-by-step setup guide](docs/index.html) for a checklist, copyable commands, setup progress, troubleshooting, and ESP32 guidance.

## ESP32 hardware (optional)

Firmware example: [`hardware/esp32/aura_link_esp32_core.ino`](hardware/esp32/aura_link_esp32_core.ino)

1. Install Arduino IDE and ESP32 board support.
2. Open the sketch and replace the Wi-Fi placeholders **on your local copy only**.
3. Select the correct board and port, then upload.
4. Open Serial Monitor at **115200 baud** and note the device IP.
5. Confirm the laptop and ESP32 are on the same trusted local network.
6. Check the sketch's endpoints and settings against the Python communication code.

The example uses local HTTP without authentication. Do not expose it directly to the public internet. Hardware pin mappings vary by board.

## Troubleshooting

| Problem | First checks |
| --- | --- |
| Package installation fails | Python/MediaPipe compatibility; active virtual environment |
| Camera unavailable | Camera permission; close other apps using the webcam; check `AURA_CAMERA_INDEX` |
| Model error | Confirm the expected model asset and path from the source code |
| ESP32 not discovered | Power, Wi-Fi, same-network requirement, firewall, firmware compatibility |
| Web port already in use | Change `AURA_WEB_PORT` in your local `.env` |

When asking for help, include your operating system, Python version, the command you ran, and the full error message. Do not post passwords, tokens, or private footage.

## Project layout

- `core/`, `services/` — application logic and services
- `vision/` — computer vision and gesture tracking
- `communication/` — device communication
- `hardware/` — ESP32 firmware examples
- `ui/`, `web/` — user interface and web components
- `models/` — local model assets (some are intentionally excluded from Git)
- `tests/` — tests and checks

## Privacy and safety

- Review the code and configuration before using camera-based features in sensitive environments.
- Never commit `.env`, Wi-Fi credentials, API tokens, or other private data.
- Test in demo mode before connecting hardware.
- Verify electrical requirements and use suitable motor drivers; never power motors directly from ESP32 GPIO pins.

## License

**No license file is currently included.** Public visibility does not automatically grant permission to reuse, modify, or redistribute this project. Add a license before inviting external redistribution.
