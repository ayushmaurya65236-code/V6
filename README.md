# AURA LINK V6

AURA LINK V6 is a Python-based gesture-control and robotics interface with a visual HUD, webcam hand tracking, an optional local web dashboard, and an ESP32 connection or virtual ESP32 simulator.

> **Project status:** This guide describes the current project structure. Hardware features require compatible ESP32 firmware; simulator mode can be used without connecting a physical ESP32.

## Features

- Webcam-based hand tracking for up to two hands using MediaPipe Tasks.
- Gesture mapping: **Open Palm → LED ON**, **Fist → LED OFF**, and **Peace → LED BLINK** when extended gestures are enabled.
- Animated HUD with status information and keyboard controls.
- Optional eye-openness estimation (not identity recognition or a medical tool).
- ESP32 discovery/HTTP communication and a virtual ESP32 simulator.
- Local web dashboard, configured by default for `http://127.0.0.1:8080` when the dashboard server is running.

## Requirements

- Windows 10/11 is the primary documented setup; other operating systems may work but are not yet verified.
- Use a Python version supported by the current MediaPipe wheel for your operating system. Python 3.11 or 3.12 is a sensible starting point if you encounter install errors; confirm support before choosing a version.
- A webcam for live hand tracking.
- Internet access on first run if the required MediaPipe task model files need to be downloaded.
- Optional: compatible ESP32 hardware and matching firmware.
- Optional: audio output and a working audio device for sound effects.

## Install

Open a terminal in the project folder. If you are using Windows, install Git and Python first, then clone the repository and enter its folder:

```powershell
git clone https://github.com/ayushmaurya65236-code/V6.git
cd V6
```

If the full V6 files are still on the `aura-link-v6-upload` branch rather than `main`, use the branch-specific clone command until the pull request is merged:

```powershell
git clone --branch aura-link-v6-upload https://github.com/ayushmaurya65236-code/V6.git
cd V6
```

1. Create and activate a virtual environment:

   **Windows PowerShell**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install the core Python packages from the dependency file:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

   Optional audio effects use `sounddevice`:
   ```bash
   python -m pip install sounddevice
   ```

   If installation fails, check that your Python version and operating system are supported by MediaPipe. The dependency file lists the core packages but does not pin exact versions, so installs may change over time.

3. Create your local configuration file from the example:

   **Windows PowerShell**
   ```powershell
   Copy-Item .env.example .env
   ```

   **macOS/Linux**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` only if you need to change settings. Keep real tokens and private information out of GitHub. Do not put Wi-Fi passwords in this file; use the ESP32 setup form provided by the project.

## Run

From the project root, with your virtual environment activated:

```bash
python main.py
```

Allow camera access when prompted by your operating system. The application may download its required model files on first run. Those model files are intentionally excluded from the repository and are stored locally.


## ESP32 hardware firmware (Arduino)

A standalone ESP32 firmware example is included at [`hardware/esp32/aura_link_esp32_core.ino`](hardware/esp32/aura_link_esp32_core.ino). It provides a local web dashboard, LED control routes, a status endpoint, and UDP discovery on port **4210**. This is the AURA LINK v4-style hardware core; it is a starting point and is **not guaranteed to integrate automatically with every V6 software feature**.

### Upload it to an ESP32

1. Install the Arduino IDE and the ESP32 board support package for your board.
2. Open `hardware/esp32/aura_link_esp32_core.ino` in the Arduino IDE.
3. In the sketch, replace `YOUR_WIFI_NAME` and `YOUR_WIFI_PASSWORD` with your Wi-Fi credentials **on your own local copy only**. Never commit real credentials to GitHub.
4. Select the correct ESP32 board and USB/serial port, then upload the sketch.
5. Open Serial Monitor at **115200 baud**. After it connects to Wi-Fi, note the IP address printed in the output.
6. Connect your laptop to the same trusted local network and open `http://<ESP32-IP>/` in a browser, replacing `<ESP32-IP>` with the address shown in Serial Monitor.

### Available endpoints

| Endpoint | Purpose |
| --- | --- |
| `/` | Open the LED dashboard |
| `/status` | Read plain-text device status |
| `/led/on` | Turn the built-in LED on |
| `/led/off` | Turn the built-in LED off |
| UDP port `4210` | Respond to `AURA_DISCOVER_V1` discovery messages |

**Network safety:** this example uses plain HTTP and does not implement authentication. Use it only on a trusted local network; do not expose it directly to the public internet. The built-in LED pin can vary by ESP32 board.

## Gesture and keyboard controls

| Gesture / key | Action |
| --- | --- |
| Open Palm | LED ON |
| Fist | LED OFF |
| Peace | LED BLINK when extended gestures are enabled |
| `h` | Show or hide help |
| `d` | Toggle demo mode / virtual ESP32 |
| `e` | Enable or disable extended gestures |
| `s` | Save a screenshot |
| `f` | Toggle fullscreen |
| `m` | Mute or unmute sound |
| `+` / `-` | Adjust volume |
| `r` | Reset the system |
| `q` | Quit |

Some gestures display information on the HUD rather than issuing a hardware command. Actual hardware control requires compatible firmware and a reachable ESP32.

## Configuration

The example `.env.example` documents supported settings, including:

- `AURA_CAMERA_INDEX` — camera index (default `0`).
- `AURA_DEMO_MODE` — start with demo/simulator mode enabled.
- `AURA_EYE_TRACKING` — enable optional eye tracking.
- `AURA_EXTENDED_GESTURES` — enable extended gestures.
- `AURA_WEB_HOST` and `AURA_WEB_PORT` — dashboard bind address and port.
- `AURA_ESP32_IP` — optional fixed ESP32 address.

The dashboard binds to localhost by default. Do not expose it to a network unless you understand the security implications and have configured authentication appropriately.

## Troubleshooting

- **Camera not found:** close other apps using the webcam and check `AURA_CAMERA_INDEX`.
- **MediaPipe/model error:** verify Python compatibility, install the packages above, and ensure the first-run model download can access the internet.
- **ESP32 offline:** try demo mode first; then check that the ESP32 is on the same network and running firmware compatible with this project.
- **No sound:** install `sounddevice` and check your operating system's audio device. Audio is optional.
- **Port already in use:** change `AURA_WEB_PORT` in your local `.env` file.

## Safety and privacy

- Camera frames are used for local vision processing by this application; review the code and configuration before using it in sensitive environments.
- Use the virtual simulator to test before connecting hardware.
- This version's allowed hardware commands are limited to LED/display-related actions and emergency stop; do not assume it supports motor or servo control.
- Never commit `.env`, API tokens, Wi-Fi credentials, or other secrets.

## Contributing

Bug reports and improvements are welcome. Describe your operating system, Python version, steps to reproduce, and relevant error messages. Do not include passwords, API keys, or private camera footage in an issue.

## License

No open-source license has been added yet. Until a license is chosen, public visibility on GitHub does not automatically grant permission to redistribute or publish modified copies of this code.
