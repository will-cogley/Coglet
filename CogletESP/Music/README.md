# Music

Drop your own songs here and Coglet can dance to them.

1. Copy audio files into this folder: mp3, wav, flac, m4a, aac, ogg, opus,
   wma, aiff, or a video file (mp4, mov, m4v, webm, mkv; its audio is used).
2. Run `idf.py build`. Each song is converted for Coglet's speaker, its beats
   are detected, and it is compiled into the firmware. The build log lists
   every song with its tempo and dance preset.
3. Flash, then say "dance to <song name>" or "dance to one of my songs".

Requirements: ffmpeg (with libopus) on the build computer.
Windows 11: `winget install Gyan.FFmpeg`, then open a new ESP-IDF terminal.
Without ffmpeg the songs are skipped with a warning and the build still works.

## Presets

* **energetic**: the whole robot dances: head bobs, ears, sway, base turns,
  eyes and blinks.
* **calm**: only the ears, head and base move, gently, on the felt pulse.
  The eyelid and eye servos are relaxed (no torque) during the song.

The preset is picked automatically. Force it, and the tempo if the detection
is off, with tags in the file name:

```
Night Rain.calm.mp3
Drop It.energetic.wav
Free Fall.calm.68bpm.m4a
```

## Limits (menuconfig → NMRobotics Coglet Dance)

* 60 s per song by default (longer songs are cut with a fade-out);
* 1500 KB for all songs together (~6 minutes at 32 kbps).

## Copyright

Only use music you have the rights to. Songs in this folder end up inside
the firmware image: do not publish or sell images that contain music you are
not allowed to distribute. Everything in this folder except this README is
ignored by git, so your songs never land in the public repository.

Full details: `docs/coglet-dance.md`.
