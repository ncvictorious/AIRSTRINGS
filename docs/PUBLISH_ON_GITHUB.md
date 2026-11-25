# AIRSTRINGS: development, release and recording guide

This repository contains AIRSTRINGS v2.3, a webcam-based gesture-controlled musical instrument. This guide is for collaborators who want to reproduce the original macOS setup, record a demonstration, or contribute a change.

## Clone and install

Use GitHub's **Code → Download ZIP**, or clone with Git:

```bash
git clone https://github.com/ncvictorious/AIRSTRINGS.git
cd AIRSTRINGS
python3.11 --version
sh setup_mac.sh
```

On an Apple Silicon Mac, `python3.11` must be installed. A different default `python3` version can coexist with it. The setup script creates `.venv` and installs the dependencies. For experimental Windows support, run `setup_windows.bat` and then `run_windows.bat`.

## Mandatory MediaPipe model

The program needs Google's **hand_landmarker.task** model, which is not stored in this repository. The application first tries to download it itself. If that fails:

1. Open https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task in a browser.
2. Save the file exactly as `hand_landmarker.task`; do not append `.txt`.
3. Move it into the repository root next to `laser_harp.py`.
4. Launch the app with `sh run_mac.sh`.

The `.gitignore` excludes the model, local virtual environment, camera preferences and recordings. Do not commit them.

## Use the built-in Mac camera

Camera 0 may be an iPhone Continuity Camera on some Macs. Launch the program and press `V` to cycle between camera indices 0–2, until the correct built-in webcam appears. The selection is saved in `camera_index.txt` (ignored by Git). If you get a camera error, check **System Settings → Privacy & Security → Camera** and close other camera apps. On macOS the Python code uses the **AVFoundation** backend when opening a camera.

## Draw and play

- **Pinch** thumb + index, move to draw a line, then **release** to save a musical string.
- **Swipe** an index or middle fingertip through the saved string to sound it.
- **T** toggles a live string between index fingers of both hands.
- **C** toggles chord mode; **L** toggles the note-tuning strategy.
- **U** undoes the last string; **X** clears strings; **Q/Esc** quits.

String geometry operates in two-dimensional image coordinates. It is a visual prototype, not a calibrated 3D instrument.

## Record a demo with OBS Studio

1. Install OBS Studio from https://obsproject.com/.
2. Start AIRSTRINGS before opening OBS.
3. In OBS, add a **macOS Screen Capture** source using the **Window Capture** method and select the AIRSTRINGS/Python app. Do *not* add a separate camera source; your camera is already visible inside AIRSTRINGS.
4. Under **System Settings → Privacy & Security → Screen & System Audio Recording**, give OBS the permissions it needs.
5. Capture system/application audio and confirm an OBS audio meter moves while a string plays. Avoid adding the same audio source twice.
6. Choose 1080p/30fps if performance allows, start recording, demonstrate drawing and plucking, then stop.
7. Review the video and audio; if recorded as MKV, use **File → Remux Recordings** to make an MP4.

Neither AIRSTRINGS nor this repository automatically publishes webcam content.

## Publish a code change

1. Clone the repository and work on a separate branch.
2. Edit the code, run it with your actual camera, and test drawing, plucking, sound and camera switching.
3. Check Python syntax with `python3.11 -m py_compile laser_harp.py`.
4. Review `git status` to confirm no downloaded models, recordings or private data have been staged.
5. Commit, push your branch and create a pull request explaining the change and how it was tested.
6. Update the README when you change gesture controls, the required model or installation steps.

## Current limitations

The demonstration was developed on an Apple Silicon Mac. Windows behavior, other webcam drivers, complex lighting conditions and end-to-end latency have not been comprehensively tested. The repository doesn't include the demo video or a third-party model binary. No open-source license has yet been granted.

## Credit

The project was inspired by the musical gesture demonstration shared at https://x.com/danielmiessler/status/2124651010677440895/video/1?a=Fv91SnMgplHAieyftpQ&s=46 . This is independent original Python code, not a copy of the demonstrated author's source code.
