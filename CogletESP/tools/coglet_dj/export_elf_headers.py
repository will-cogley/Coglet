"""Write the Elf sounds (out/approved/elf_*.ogg) as firmware headers.

python3 export_elf_headers.py <path/to/CogletESP/main/coglet_sounds>
"""
import sys

import export_xmas_headers

SOUNDS = [
    ("elf_workshop.ogg", "coglet_dance_workshop.h", "CogletDanceWorkshop",
     "Coglet Elf dance (workshop) - Deck the Halls (Welsh traditional, public domain),\n"
     "// our own arrangement: xylophone, pizzicato, woodblock, toy hammers. 132 BPM, ~32 s."),
    ("elf_mischief.ogg", "coglet_dance_mischief.h", "CogletDanceMischief",
     "Coglet Elf dance (mischief) - God Rest Ye Merry Gentlemen (English traditional, public domain),\n"
     "// our own arrangement: tiptoe pizzicato, bassoon, clarinet, accordion. 156 BPM, ~32 s."),
    ("elf_party.ogg", "coglet_dance_party.h", "CogletDanceParty",
     "Coglet Elf dance (party) - We Wish You a Merry Christmas (English traditional, public domain),\n"
     "// our own arrangement: fiddle, accordion, tuba, tambourine. 160 BPM 3/4, ~31 s."),
    ("elf_startup.ogg", "coglet_elf_boot_chime.h", "CogletElfBootChime",
     "Coglet Elf startup sound - a wind-up key, a spring and a xylophone run, ~3.2 s."),
    ("elf_reminder.ogg", "coglet_elf_reminder_chime.h", "CogletElfReminderChime",
     "Coglet Elf reminder sound - a toy clock ticking, then two xylophone 'ta-da!' calls, ~2.7 s."),
]

if __name__ == "__main__":
    export_xmas_headers.main(sys.argv[1], SOUNDS, prefix="elf")
