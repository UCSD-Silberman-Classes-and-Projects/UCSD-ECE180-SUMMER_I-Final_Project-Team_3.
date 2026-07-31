import os

SONG_FILE = "/home/arduino/current_song.txt"

if os.path.exists(SONG_FILE):
    with open(SONG_FILE, "r") as f:
        song = f.read().strip()

    print("Detected song:")
    print(song)

    if os.path.exists(song):
        print("File exists!")
    else:
        print("File missing!")

else:
    print("No USB song detected")
