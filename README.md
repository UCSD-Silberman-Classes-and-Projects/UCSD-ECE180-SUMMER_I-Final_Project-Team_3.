# <div align="center">AI Music Instrument & Vocal Removal Device</div>
### <div align="center">ECE 180 Final Project</div>
#### <div align="center">Team #3 — Summer Session I 2026</div>

**Photos:** [Front View](https://drive.google.com/file/d/1DdtovpZk14N7O1HgtoTwd-P9sjlYPKgB/view?usp=sharing) | [Side View](https://drive.google.com/file/d/1why-yrY0hsEtVmtkVGPhBQCBYVUqeQCW/view?usp=sharing) | [Back View](https://drive.google.com/file/d/10IjpwqsGlS_dRstfoKWQImvOjWGpgrZu/view?usp=sharing)
<!-- TODO: for photos to display inline instead of as links, upload them directly into the repo (e.g. docs/media/) and swap these links for ![Front View](docs/media/front.jpg) etc. -->

## Table of Contents
1. [Team Members](#team-members)
2. [Abstract](#abstract)
3. [What We Promised](#what-we-promised)
4. [Accomplishments](#accomplishments)
5. [Challenges](#challenges)
6. [Final Project Video](#final-project-video)
7. [How It Works](#how-it-works)
8. [Hardware](#hardware)
9. [Repo Contents](#repo-contents)
10. [Setup / Usage](#setup--usage)
11. [Troubleshooting](#troubleshooting)
12. [Restoring the Project on a New Board](#restoring-the-project-on-a-new-board)
13. [If We Had Another Week](#if-we-had-another-week)
14. [Acknowledgements](#acknowledgements)
15. [Contacts](#contacts)

<hr>

## Team Members

Eli Carsenti - Electrical & Computer Engineering

Jason Salazar Rios - Electrical & Computer Engineering

Vadim Keenan - Electrical & Computer Engineering

<hr>

## Abstract

A karaoke-style audio stem separation system that runs entirely on the Arduino Uno Q. Load a song from a USB flash drive, and the board automatically detects it and uses a Demucs-based ML model to split it into vocal, drums, bass, and other stems. Physical buttons let you mute/unmute individual stems on the fly — sing along without the vocals, drop the drums, isolate the bass — then finalize a real mixed-down track and play it back over AUX with adjustable volume and a live status display.

<hr>

## What We Promised

### Must Have
- [x] Upload song
- [x] Play back song w/ vocals removed
- [x] Physical controls (switches/buttons)
- [x] Display showing progress and status
- [x] Aux output for headphones and speakers
- [x] Adjustable volume
- [x] Pause and play
- [ ] Rewind and fast forward

### Nice to Have
- [x] Remove acoustic/electric guitar, bass, piano, drums
- [ ] Play parts in lower volume instead of only muting
- [ ] Advanced display (load time, song timer, progress bar)
- [x] Labeled controls
- [x] Soldered build in a nice 3D-printed case

<hr>

## Accomplishments

**Design Evolution**
- Initial version: fully webpage-based — upload, stem separation, playback, mute feedback
- Final version: moved entirely to hardware — no webpage upload flow; USB ingestion, physical buttons, potentiometer, TFT display, AUX output

**Core Pipeline (Final Version)**
- Song dropped on a USB flash drive is auto-detected by `demucs_server.py`'s USB watcher thread and separated with Demucs 4.1.0
- `main.py` polls the server's `/status` endpoint and downloads all four stems (vocal, drums, bass, other) once separation completes
- Buttons mute/unmute individual stems; pressing **Finalize** builds a real mixed-down track by summing the non-muted stems' waveforms and normalizing if needed
- Play/pause plays the finalized mix via `aplay`; the potentiometer sets system volume via `amixer`
- A 5-line ST7735 TFT display (driven directly over SPI with a hand-rolled font) shows upload status, which stems are kept/muted, finalize status, and play status — each line owned independently so different events never overwrite each other

**Hardware & Controls**
- Physical buttons for stem muting, finalize, and pause/play
- Potentiometer for adjustable volume
- SPI TFT display working, showing live status
- Flash drive file reading integrated with playback
- Soldered build housed in a 3D-printed case

**AI Model**
- Iterated past an early overtrained model (dataset too large → too small dataset) by switching to a bigger Demucs model, landing on an "optimal" result
- New trained model successfully combined with the Arduino circuit

<hr>

## Challenges

| Issue | Why | Fix |
|---|---|---|
| Rewind / fast-forward on device | Implementing it in App Lab would've required overhauling how audio is handled there; the needed library was too large and wouldn't install properly | Kept this feature in the Web UI version instead — drag the bar/point to jump to any timestamp in the song |
| Web UI file size limit | The way App Lab ingests files has this limit built in; it could not be fixed or worked around | Switched to USB flash drive upload (the original design) to remove the file size limit entirely |
| AUX port power | Direct connection wasn't getting sufficient power to play audio | Ran the AUX cord through a USB hub (via a USB-C converter) instead — also freed up room on the Arduino for the flash drive and power |
| Model training | An early fine-tuning attempt overtrained on a too-small dataset | Switched to a bigger Demucs model and retrained, landing on an "optimal" result |

<hr>

## Final Project Video

- [Demo Video 1 — before stem separation](https://drive.google.com/file/d/1QZgK7SNFArip6ig8x3jpaVQxmAbc0eBg/view?usp=sharing)
- [Demo Video 2 — after stem separation](https://drive.google.com/file/d/1xyiZW-JPjazSeEFnDOGOuh60KiNtbXhP/view?usp=sharing)

<hr>

## How It Works

The system splits work across the Uno Q's two processors:

- **MCU side (STM32):** Reads button and potentiometer input, drives the ST7735 TFT display directly over SPI, and communicates with the Linux side over Bridge RPC.
- **MPU side (Debian Linux):** Runs a Python backend (`main.py`) plus a separate Demucs server (`demucs_server.py`) for stem separation and playback via `aplay`/`amixer`.

### Workflow

1. Load a song onto a USB flash drive and plug it into the board. A background thread in `demucs_server.py` polls for a new song every 5 seconds and starts separation automatically — no manual upload step.
2. The server runs Demucs 4.1.0 as a subprocess, splitting the song into **vocals**, **drums**, **bass**, and **other**, and exposes progress via `/status`.
3. `main.py` polls `/status`; once complete, it downloads each stem from `/download/<stem>`.
4. Physical buttons mute/unmute each stem individually:
   - `VOCAL` → pin 2
   - `BASS` → pin 3
   - `DRUMS` → pin 4
   - `OTHER` → pin 5
   - `FINALIZE` → pin 6
   - `PLAY/PAUSE` → pin 7
5. Pressing **Finalize** builds a real mix from the kept stems (sums the waveforms, normalizes on clipping) and saves it to a temp WAV.
6. **Play/Pause** plays that finalized mix via `aplay -D hw:0,0`; the potentiometer (analog pin A0) sets system volume via `amixer`.
7. The ST7735 TFT display shows five independent status lines: upload/processing status (with a spinner), which stems are kept, which are muted, finalize status, and play status.
8. Audio plays out over AUX, routed through a USB hub via a USB-C converter.

<hr>

## Hardware

- Arduino Uno Q
- USB DAC for AUX audio output
- ST7735 SPI TFT display (128×160)
- Potentiometer (volume control, analog pin A0)
- USB flash drive (song input)
- 3D-printed enclosure

See [Side View](https://drive.google.com/file/d/1why-yrY0hsEtVmtkVGPhBQCBYVUqeQCW/view?usp=sharing) and [Back View](https://drive.google.com/file/d/10IjpwqsGlS_dRstfoKWQImvOjWGpgrZu/view?usp=sharing) above for the internal wiring layout.
<!-- TODO: add a dedicated circuit/wiring diagram if you have one, separate from the enclosure photos -->

<hr>

## Repo Contents

| File | Description |
|---|---|
| `app.yaml` | App Lab project metadata (Bricks used, etc.) |
| `python/main.py` | Core application logic: polls the Demucs server, downloads stems, handles button-driven mute/finalize/play state, builds the final mixed-down track, and pushes status to the display. |
| `python/requirements.txt` | Python dependencies (`numpy`, `soundfile`). |
| `sketch/sketch.ino` | STM32 firmware — reads all six buttons and the volume pot, drives the ST7735 TFT display over SPI, and exposes button states to Python via `Bridge.provide_safe`. |
| `sketch/sketch.yaml` | Sketch configuration. |
| `assets/index.html`, `assets/app.js`, `assets/style.css` | Browser-side status mirror (not an upload UI) — reflects stem mute state and finalized-mix playback. |
| `demucs_server.py` *(Linux-side, separate from this App Lab project)* | Flask server that watches the USB drive for a new song, runs Demucs 4.1.0, and exposes `/status` and `/download/<stem>` endpoints. |
| `usb_song_test.py` *(Linux-side)* | Small test/debug script — reads `/home/arduino/current_song.txt` and confirms whether the referenced song file actually exists on the USB drive. |
| `usb_demucs_test.py` *(Linux-side)* | Small test/debug script — runs Demucs directly on a hardcoded USB song path (`/mnt/usb/sound.wav`) to verify Demucs works standalone, outside the full server pipeline. |
| `local_demucs_test.py` *(Linux-side)* | Test/debug script for running Demucs on a local (non-USB) file. |
<!-- TODO: add local_demucs_test.py to the repo — referenced in the setup guide but not yet uploaded -->

<hr>

## Setup / Usage

### 1. Set up the Python virtual environment (Linux side of the Uno Q)

```bash
python3 -m venv ~/demucs-env
source ~/demucs-env/bin/activate
pip install --upgrade pip
pip install demucs
pip install torch torchaudio
pip install soundfile numpy scipy pygame requests
```

### 2. Create the required directories

```bash
mkdir ~/uploads
mkdir ~/separated
mkdir ~/usb_import
```

### 3. Copy the Linux-side scripts

Copy `demucs_server.py`, `usb_song_test.py`, `usb_demucs_test.py`, and `local_demucs_test.py` into the Arduino user's home directory (`/home/arduino/`).

### 4. Prepare the USB flash drive

Format it as **FAT32** and place one supported audio file on it (`.wav`, `.mp3`, or `.flac`).

### 5. Flash the sketch and deploy the App Lab project

Flash `sketch/sketch.ino` to the STM32 side via App Lab, then import/deploy the App Lab project (`app.yaml`, `python/`, `assets/`) to the Uno Q.

### 6. Run it

Start the Demucs server (`python demucs_server.py`) and launch the App Lab app. Insert the USB drive — separation starts automatically. Use the buttons to mute/unmute stems, press Finalize to build the mix, and Play/Pause to listen.

<hr>

## Troubleshooting

**USB not detected**
- Run `lsblk` to confirm the drive shows up.
- Reinsert the drive or try another one.
- Confirm it's formatted as FAT32.
- If it still doesn't auto-mount: `sudo mkdir -p /mnt/usb && sudo mount /dev/sda1 /mnt/usb` (replace `sda1` with the correct device from `lsblk`).

**No stems created**
- Check `find ~/separated` for output.
- Confirm the audio file is readable and Demucs is installed inside `demucs-env`.
- Check the terminal for Python errors.

**Display frozen**
- Restart the App Lab application.
- Verify the display's ribbon/SPI connection is firmly seated.
- Confirm `set_display()` is still being called from `poll_buttons()`.

<hr>

## Restoring the Project on a New Board

If you need to set up the project on a fresh Uno Q from `unoq_project_backup.tar.gz` (containing `ArduinoApps/`, `demucs-env/`, `demucs_server.py`, `requirements.txt`, `uploads/`, and `separated/`):

1. Connect the Uno Q and get it on the same network as your computer.
2. Find the board's IP with `hostname -I`.
3. Copy the backup over: `scp unoq_project_backup.tar.gz arduino@<ARDUINO_IP>:/home/arduino/`
4. SSH in, extract it (`tar -xzvf unoq_project_backup.tar.gz`), and restore the files (`cp -r ~/backup_files/* ~/`).
5. Activate the venv and confirm Demucs is installed: `source ~/demucs-env/bin/activate && demucs --version`
6. Start the server: `python demucs_server.py`
7. Reopen this App Lab project and upload it to the board.

<hr>

## If We Had Another Week

**Trained Demucs Model**
- Implement our own trained version of the Demucs model instead of the preexisting version
- Allows for guitar and piano separation as well
- Make sure it works without internet or computer connection

**Per-Stem Volume Control**
- Tackle this Nice to Have: adjustable volume for each individual stem, not just an all-out mute
- Lets users blend stems in rather than only choosing to include or remove them entirely

<hr>

## Acknowledgements

Thank you to our Professor, TAs, and classmates!

<hr>

## Contacts

- Vadim Keenan - vkeenan@ucsd.edu
- Eli Carsenti - ecarsenti@ucsd.edu
- Jason Salazar Rios - jasalazarrios@ucsd.edu
