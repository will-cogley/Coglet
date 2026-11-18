"""Write the Snowman sounds (out/approved/snow_*.ogg) as firmware headers.

python3 export_snow_headers.py <path/to/CogletESP/main/coglet_sounds>
"""
import sys

import export_xmas_headers

SOUNDS = [
    ("snow_lullaby.ogg", "coglet_dance_lullaby.h", "CogletDanceLullaby",
     "Coglet Snowman dance (lullaby) - Brahms, Wiegenlied Op. 49 No. 4 (1868, public domain),\n"
     "// our own arrangement: music box, celesta, soft strings, wind chimes. 104 BPM 3/4, ~32 s."),
    ("snow_stomp.ogg", "coglet_dance_stomp.h", "CogletDanceStomp",
     "Coglet Snowman dance (stomp) - Good King Wenceslas (tune from Piae Cantiones, 1582, public domain),\n"
     "// our own arrangement: tuba, bassoon, pizzicato, snow crunch, snowballs. 108 BPM, ~32 s."),
    ("snow_blizzard.ogg", "coglet_dance_blizzard.h", "CogletDanceBlizzard",
     "Coglet Snowman dance (blizzard) - Leontovych, Shchedryk (1914, public domain; only its own\n"
     "// bell ostinato and sequence), our own arrangement: glass bells, strings, wind. 150 BPM 3/4, ~32 s."),
    ("snow_startup.ogg", "coglet_snowman_boot_chime.h", "CogletSnowmanBootChime",
     "Coglet Snowman startup sound - a gust of wind, rising ice chimes and a soft 'poof' of snow, ~3.2 s."),
    ("snow_reminder.ogg", "coglet_snowman_reminder_chime.h", "CogletSnowmanReminderChime",
     "Coglet Snowman reminder sound - falling icicle bells, then two clear calls, ~2.7 s."),
]

if __name__ == "__main__":
    export_xmas_headers.main(sys.argv[1], SOUNDS, prefix="snow")
