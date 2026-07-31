import subprocess
import os

song = "/mnt/usb/sound.wav"

if not os.path.exists(song):
    print("Song not found")
    exit()

print("Starting Demucs on:")
print(song)

subprocess.run([
    "demucs",
    song,
    "-o",
    "/home/arduino/separated"
])

print("Done")
