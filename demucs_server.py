from flask import Flask, request, send_file, jsonify, render_template
import subprocess
import os
import shutil
import threading
import time
import torch

torch.set_num_threads(8)
torch.set_num_interop_threads(8)


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024

UPLOAD_FOLDER = "/home/arduino/uploads"
USB_FOLDER = "/mnt/usb"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


LATEST_OUTPUT = None

PROCESS_STATUS = "idle"

CURRENT_SONG_FILE = "/home/arduino/current_song.txt"
LAST_PROCESSED_SONG = None

DEMUC_RUNNING = False

def cleanup_files():

    if os.path.isdir(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)

    if os.path.isdir("/home/arduino/separated"):
        shutil.rmtree("/home/arduino/separated")

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)



def run_demucs(input_path, filename):

    global LATEST_OUTPUT
    global PROCESS_STATUS
    global DEMUC_RUNNING
    DEMUC_RUNNING = True

    try:
        PROCESS_STATUS = "processing"

        print("Starting Demucs...")

        result = subprocess.run(
            [
                "/home/arduino/demucs-env/bin/demucs",
                input_path
            ],
            capture_output=True,
            text=True
        )

        print(result.stdout)
        print(result.stderr)

        if result.returncode != 0:
            raise Exception("Demucs failed")

        name = os.path.splitext(filename)[0]

        LATEST_OUTPUT = (
            f"/home/arduino/separated/htdemucs/{name}"
        )


        PROCESS_STATUS = "complete"

        print("Finished!")
        print("Output:", LATEST_OUTPUT)


    except Exception as e:

        print("Demucs failed:", e)

        PROCESS_STATUS = "failed"

    DEMUC_RUNNING = False

def find_usb_audio():

    extensions = (".wav", ".mp3", ".flac")

    for root, dirs, files in os.walk(USB_FOLDER):

        for file in files:

            if not file.startswith("._") and file.lower().endswith(extensions):
                return os.path.join(root, file)

    return None

def usb_watcher():

    global LAST_PROCESSED_SONG

    while True:
        try:

            if os.path.exists(CURRENT_SONG_FILE):

                with open(CURRENT_SONG_FILE) as f:
                    song_path = f.read().strip()


                if (
                    song_path
                    and song_path != LAST_PROCESSED_SONG
                    and os.path.exists(song_path)
                    and not DEMUC_RUNNING
                ):

                    print("New USB song detected:")
                    print(song_path)


                    cleanup_files()


                    filename = os.path.basename(song_path)

                    input_path = os.path.join(
                        UPLOAD_FOLDER,
                        filename
                    )


                    shutil.copy2(
                        song_path,
                        input_path
                    )


                    thread = threading.Thread(
                        target=run_demucs,
                        args=(input_path, filename)
                    )

                    thread.start()


                    LAST_PROCESSED_SONG = song_path


        except Exception as e:
            print("USB watcher error:", e)


        time.sleep(5)

@app.route("/")
def home():
    return render_template("index.html")



@app.route("/separate", methods=["POST"])
def separate():

    global PROCESS_STATUS


    cleanup_files()


    audio = request.files["file"]

    input_path = os.path.join(
        UPLOAD_FOLDER,
        audio.filename
    )

    audio.save(input_path)


    print("Received:", input_path)


    thread = threading.Thread(
        target=run_demucs,
        args=(input_path, audio.filename)
    )

    thread.start()


    return jsonify({
        "status": "processing"
    })

@app.route("/separate_usb", methods=["POST"])
def separate_usb():

    global PROCESS_STATUS

    cleanup_files()

    usb_file = find_usb_audio()

    if usb_file is None:
        return jsonify({
            "error": "No audio file found on USB"
        }), 400


    filename = os.path.basename(usb_file)

    # Copy from USB into uploads folder
    input_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    shutil.copy2(
        usb_file,
        input_path
    )


    print("Using USB file:", input_path)


    thread = threading.Thread(
        target=run_demucs,
        args=(input_path, filename)
    )

    thread.start()


    return jsonify({
        "status": "processing",
        "file": filename
    })

@app.route("/status")
def status():

    return jsonify({
    "status": PROCESS_STATUS,
    "ready": LATEST_OUTPUT is not None,
    "output": LATEST_OUTPUT
    })



@app.route("/download/vocals")
def download_vocals():

    return send_file(
        os.path.join(LATEST_OUTPUT, "vocals.wav"),
        mimetype="audio/wav",
        as_attachment=True,
        download_name="vocals.wav"
    )



@app.route("/download/drums")
def download_drums():

    return send_file(
        os.path.join(LATEST_OUTPUT, "drums.wav"),
        mimetype="audio/wav",
        as_attachment=True,
        download_name="drums.wav"
    )



@app.route("/download/bass")
def download_bass():

    return send_file(
        os.path.join(LATEST_OUTPUT, "bass.wav"),
        mimetype="audio/wav",
        as_attachment=True,
        download_name="bass.wav"
    )



@app.route("/download/other")
def download_other():

    return send_file(
        os.path.join(LATEST_OUTPUT, "other.wav"),
        mimetype="audio/wav",
        as_attachment=True,
        download_name="other.wav"
    )



if __name__ == "__main__":

    watcher = threading.Thread(
        target=usb_watcher,
        daemon=True
    )

    watcher.start()


    app.run(
        host="0.0.0.0",
        port=5000
    )