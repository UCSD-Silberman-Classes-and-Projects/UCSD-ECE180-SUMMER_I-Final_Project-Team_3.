# SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
#
# SPDX-License-Identifier: MPL-2.0
from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
import base64
import os
import subprocess
import tempfile
import time
import requests
import logging
import io
import numpy as np
import soundfile as sf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER = "http://172.19.0.1:5000"

STEM_NAMES = ["vocal", "drums", "bass", "other"]
STEM_ABBR = {"vocal": "V", "drums": "D", "bass": "B", "other": "O"}

SERVER_STEMS = {
    "vocal": "vocals",
    "drums": "drums",
    "bass": "bass",
    "other": "other",
}


def get_usb_stems() -> dict:

    # Wait until Demucs has finished
    while True:
        status = requests.get(SERVER + "/status").json()

        if status["status"] == "complete":
            break

        if status["status"] == "failed":
            raise Exception("Demucs failed")

        time.sleep(1)

    stems = {}

    for ui_name, server_name in SERVER_STEMS.items():

        download = requests.get(
            SERVER + "/download/" + server_name
        )

        if download.status_code != 200:
            raise Exception(f"Failed downloading {server_name}")

        stems[ui_name] = download.content

    return stems


def build_final_mix(stems: dict, muted: dict) -> bytes:
    kept = [name for name in STEM_NAMES if not muted.get(name, False)]
    if not kept:
        return b""

    mix = None
    samplerate = None
    for name in kept:
        data, sr = sf.read(io.BytesIO(stems[name]))
        data = data.astype(np.float32)
        if mix is None:
            mix = data
            samplerate = sr
        else:
            min_len = min(len(mix), len(data))
            mix = mix[:min_len] + data[:min_len]

    peak = np.max(np.abs(mix)) if mix.size else 0
    if peak > 1.0:
        mix = mix / peak

    buf = io.BytesIO()
    sf.write(buf, mix, samplerate, format='WAV')
    return buf.getvalue()

# ---------------------------------------------------------------------------
# Display: 5 independent lines. IMPORTANT: nothing pushes to the display
# except poll_buttons() at the bottom of this file. Functions that are
# invoked BY the MCU (play_audio, set_volume) must never call the display
# themselves -- that creates a nested Bridge call that deadlocks the
# connection. They only update these state variables; poll_buttons()
# notices the change and pushes it.
# ---------------------------------------------------------------------------

upload_status = "WAITING"
finalized_status = "NO"
playing_status = "NO"

spinner_frames = ["|", "/", "-", "\\"]
spinner_index = 0
last_spinner_update = 0

_last_pushed_state = None  # change-detection so we don't spam the SPI bus


def stem_letters(names: list) -> str:
    if not names:
        return "-"
    return ",".join(STEM_ABBR[n] for n in names)


def maybe_push_display():
    """Called only from poll_buttons(). Pushes to the display only if
    something actually changed since the last push."""
    global _last_pushed_state

    kept = [name for name in STEM_NAMES if not mute_state[name]]
    muted = [name for name in STEM_NAMES if mute_state[name]]

    # Show a spinner while Demucs is processing
    if upload_status == "PROCESSING":
        upload_line = f"PROCESSING {spinner_frames[spinner_index]}"
    else:
        upload_line = f"UPLOAD: {upload_status}"

    # Include spinner_index so the display refreshes every spinner frame
    state = (
        upload_status,
        spinner_index if upload_status == "PROCESSING" else -1,
        tuple(kept),
        tuple(muted),
        finalized_status,
        playing_status,
    )

    if state == _last_pushed_state:
        return

    try:
        Bridge.call(
            "set_display",
            upload_line,
            f"KEPT: {stem_letters(kept)}",
            f"MUTED: {stem_letters(muted)}",
            f"FINAL: {finalized_status}",
            f"PLAY: {playing_status}",
        )
        _last_pushed_state = state
    except Exception:
        pass
# ---------------------------------------------------------------------------
# Physical audio playback (speaker/AUX out, volume knob, play/pause button)
# ---------------------------------------------------------------------------

audio_process = None
paused = False
current_volume = 50
current_mix_path = None


def set_volume(vol):
    """Called BY the MCU via Bridge -- must not touch the display."""
    global current_volume
    try:
        current_volume = max(0, min(100, int(vol)))
        result = subprocess.run(
            ["amixer", "set", "Headset", f"{current_volume}%"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info(f"Volume set to {current_volume}%")
        else:
            logger.error(result.stderr)
    except Exception as e:
        logger.error(f"Volume error: {e}")


def play_audio():
    """Called BY the MCU via Bridge (play/pause button) -- must not touch
    the display directly. Only updates state; poll_buttons() picks it up."""
    global audio_process, paused, playing_status

    if not current_mix_path or not os.path.exists(current_mix_path):
        logger.info("No finalized mix to play yet -- press Finalize first.")
        playing_status = "NO"
        return

    if audio_process is None or audio_process.poll() is not None:
        logger.info(f"Playing {current_mix_path}")
        audio_process = subprocess.Popen(["aplay", "-D", "hw:0,0", current_mix_path])
        paused = False
        playing_status = "PLAYING"
        return

    if paused:
        os.kill(audio_process.pid, 18)  # SIGCONT
        paused = False
        logger.info("Resumed")
        playing_status = "PLAYING"
    else:
        os.kill(audio_process.pid, 19)  # SIGSTOP
        paused = True
        logger.info("Paused")
        playing_status = "PAUSED"


Bridge.provide("play_audio", play_audio)
Bridge.provide("set_volume", set_volume)

# ---------------------------------------------------------------------------

OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "stem_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

mute_state = {name: False for name in STEM_NAMES}
last_stems = None

usb_song_loaded = False
last_status_check = 0



ui = WebUI()

prev_pressed = {name: False for name in STEM_NAMES}
prev_finalize_pressed = False


def handle_finalize_press():
    """Triggered from poll_buttons(), which is Python-initiated -- safe
    to update state here."""
    global current_mix_path, audio_process, finalized_status, playing_status

    if last_stems is None:
        ui.send_message('final_mix_error', {
            'error': 'No song has been separated yet. Upload and separate a song first.'
        })
        finalized_status = "ERR:NOSONG"
        return

    removed = [name for name in STEM_NAMES if mute_state[name]]
    kept = [name for name in STEM_NAMES if not mute_state[name]]

    try:
        final_audio = build_final_mix(last_stems, mute_state)
    except Exception as e:
        ui.send_message('final_mix_error', {'error': f'Failed to build mix: {e}'})
        finalized_status = "ERR:FAILED"
        return

    if not final_audio:
        ui.send_message('final_mix_error', {'error': 'All stems are muted -- nothing to play.'})
        finalized_status = "ERR:MUTED"
        return

    if audio_process is not None and audio_process.poll() is None:
        audio_process.terminate()
    playing_status = "NO"

    mix_path = os.path.join(tempfile.gettempdir(), "current_mix.wav")
    with open(mix_path, "wb") as f:
        f.write(final_audio)

    current_mix_path = mix_path
    finalized_status = f"READY ({stem_letters(kept)})"

    ui.send_message('final_mix_result', {
        'success': True,
        'audio_base64': base64.b64encode(final_audio).decode('utf-8'),
        'removed_stems': removed,
        'kept_stems': kept,
        'is_mock_audio': False,
    })


def poll_buttons():
    """The ONLY place that talks to the display. Reads button states,
    updates state, then pushes to the display if anything changed."""
    global prev_finalize_pressed
    global playing_status
    global last_stems
    global upload_status
    global finalized_status
    global usb_song_loaded
    global last_status_check
    global spinner_index
    global last_spinner_update

    if upload_status == "PROCESSING":
        if time.time() - last_spinner_update > 0.2:
            spinner_index = (spinner_index + 1) % len(spinner_frames)
            last_spinner_update = time.time()

    # Check every second whether Demucs has finished
    if time.time() - last_status_check > 1:

        last_status_check = time.time()

        if not usb_song_loaded:

            try:

                status = requests.get(
                    SERVER + "/status",
                    timeout=1
                ).json()

                upload_status = status["status"].upper()
                if upload_status != "PROCESSING":
                    spinner_index = 0

                if status["status"] == "processing":

                    usb_song_loaded = False
                    last_stems = None
                    finalized_status = "NO"

                if status["status"] == "complete":

                    logger.info("Downloading stems...")

                    last_stems = get_usb_stems()

                    usb_song_loaded = True

                    finalized_status = "READY"

                    logger.info("Stems loaded.")

            except Exception:
                pass

    if playing_status == "PLAYING" and audio_process is not None and audio_process.poll() is not None:
        playing_status = "NO"

    locked = (playing_status == "PLAYING")

    for name in STEM_NAMES:
        pressed = bool(Bridge.call(f"{name}_state"))
        if pressed and not prev_pressed[name] and not locked:
            mute_state[name] = not mute_state[name]
            ui.send_message('stem_mute_update', {'stem': name, 'muted': mute_state[name]})
        prev_pressed[name] = pressed

    finalize_pressed = bool(Bridge.call("finalize_state"))
    if finalize_pressed and not prev_finalize_pressed and not locked:
        handle_finalize_press()
    prev_finalize_pressed = finalize_pressed

    maybe_push_display()

    time.sleep(0.01)


App.run(user_loop=poll_buttons)
