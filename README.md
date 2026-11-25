# AIRSTRINGS 🎵

**Draw musical strings in front of your webcam and play them with hand gestures.**

AIRSTRINGS is an experimental computer-vision instrument written in Python. Instead of using a fixed harp layout, you **pinch and drag to create your own strings**, choose their on-screen lengths and angles, then **pluck** them by swiping a fingertip across them. Plucked strings respond with sound, a brief vibration, a light pulse and sparks.

> **Demo:** Add a link to your own demonstration video here after publishing it. This repository does not contain a recording.

## Features

- **Gesture-created strings:** pinch thumb and index finger, drag, release to save (up to 12).
- **Play notes or chords:** swipe your index or middle finger across the lines you created.
- **Responsive visuals:** string vibration, pulses and sparks when played.
- **Length-based pitch:** shorter strings map to higher notes; alternatively, tune by creation order.
- **Live two-hand string:** stretch a temporary string between both index fingertips and play it.
- **Camera selection:** press `V` to cycle through detected cameras; the selected index is remembered locally.
- **Natural webcam feed:** no artificial dimming or brightness controls in V2.3.

**Important:** the strings are defined in **2D camera-image coordinates**. They look like they float in the air on screen, but this is not a calibrated 3D spatial tracking system or a physical string simulation.

## Built with

- Python 3.11
- [MediaPipe Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python) — hand landmarks
- OpenCV — camera input and visual rendering
- NumPy — sound generation and calculations
- Pygame — audio playback

The audio notes are synthesised in code; no prerecorded commercial music or copyrighted samples are included.

## Quick start — macOS (Apple Silicon)

1. Install **Python 3.11**. The Python executable must be available as `python3.11` (check with `python3.11 --version`). Python 3.15 on your Mac can coexist with it; the setup script explicitly uses 3.11.
2. Download/clone this repository and open Terminal inside the project folder.
3. Run:

   ```bash
   sh setup_mac.sh
   ```

4. Download the MediaPipe model (see the **Required hand-tracking model** section below), or allow the first run to try downloading it automatically.
5. Start the app:

   ```bash
   sh run_mac.sh
   ```

6. Grant your terminal program permission to use the camera if macOS asks. Select the AIRSTRINGS window and press `V` to switch cameras if your iPhone/Continuity Camera appears instead of the built-in webcam.

### Manual setup alternative (macOS)

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python laser_harp.py
```

## Required hand-tracking model — read this if you get a download error

**AIRSTRINGS needs a separate file named `hand_landmarker.task`.** It is a Google MediaPipe model and is deliberately **not included in this GitHub repository**. The script attempts to download it automatically on first run, but that step may fail due to network restrictions.

**Manual download (the workaround used during the original Mac setup):**

1. Open this **official Google-hosted model URL** in a browser:

   **[Download hand_landmarker.task](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)**

2. Save the downloaded file using the **exact filename** `hand_landmarker.task`.
3. Move it into the **same folder as `laser_harp.py`** (the root folder of this repository).
4. Start the application again with `sh run_mac.sh`.

Expected layout after setup:

```text
AIRSTRINGS/
├── laser_harp.py
├── hand_landmarker.task    # downloaded separately; do not commit
├── requirements.txt
├── setup_mac.sh
├── run_mac.sh
├── setup_windows.bat
├── run_windows.bat
└── README.md
```

> On macOS, verify the file was not accidentally renamed to `hand_landmarker.task.txt`. Avoid committing the model binary: the README links to its source, and the model remains subject to its provider's terms.

## Controls

| Gesture or key | Action |
| --- | --- |
| Pinch thumb + index, drag, release | Draw and save a string |
| Swipe index or middle finger across a saved string | Play a note or chord |
| `T` | Toggle the live string between two index fingertips |
| `C` | Switch between notes and chords |
| `L` | Switch tuning: string length / creation order |
| `V` | Switch camera and remember the selection |
| `U` | Undo the last string |
| `X` | Clear saved strings |
| `Q` or `Esc` | Quit |

**Tip:** keep your hands well lit and inside the webcam image. A line must be at least 65 pixels long before it can be saved.

## Windows (experimental)

Python 3.11 is required by the included setup script. From the project folder, run `setup_windows.bat` and then `run_windows.bat`. The Mac build was used for the initial demonstration; Windows camera/audio behavior has not been validated in the same way.

## Recording a demonstration

Use [OBS Studio](https://obsproject.com/) and capture the **AIRSTRINGS/Python application window**, not a second webcam source. Include desktop/application audio in the recording so the music is audible. Review camera and microphone permissions on your operating system. Your recording is yours to publish; the project does not automatically upload video or camera data.

## Troubleshooting

| Issue | Fix |
| --- | --- |
| `python3.11: command not found` | Install Python 3.11 and restart Terminal. Check `python3.11 --version`, not just `python3 --version`. |
| Model download fails | Download `hand_landmarker.task` manually from the Google link above and place it next to `laser_harp.py`. |
| `Could not open camera 0` | Quit webcam-consuming applications, check macOS **Privacy & Security → Camera**, and use `V` to switch camera. The macOS implementation first tries OpenCV's AVFoundation backend. |
| Phone camera appears instead of Mac webcam | Press `V` until the built-in camera is selected. The choice is saved locally in `camera_index.txt`. |
| No sound | Check system audio output and make sure a finger **crosses** a saved string, rather than resting on it. |
| Camera appears too dark or too bright | Version 2.3 leaves camera exposure unchanged; adjust room lighting or your camera's own settings. |

## Project status

**Version:** 2.3 (prototype). Tested as a personal macOS Apple Silicon webcam project. More extensive testing across camera devices, operating systems and lighting conditions is still needed.

Possible next steps: smoother gesture recognition, richer physical string synthesis, MIDI export, a browser demo and more visual styles.

## Acknowledgements

Inspired by a public demonstration of gesture-created musical strings [shared on X](https://x.com/danielmiessler/status/2124651010677440895/video/1?a=Fv91SnMgplHAieyftpQ&s=46). This is an independent Python prototype, not the original creator's code.

Hand tracking uses Google's MediaPipe technology. Model downloads and usage are governed by the applicable provider terms.

## Licensing

No open-source license has been selected for this repository yet. Add a `LICENSE` file if you decide to grant reuse rights. Third-party dependencies and model assets retain their own licenses/terms.