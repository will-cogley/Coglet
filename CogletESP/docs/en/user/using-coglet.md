# Using Coglet

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/user/using-coglet.md) · [Español](../../es/user/using-coglet.md) · [日本語](../../ja/user/using-coglet.md)

## Talking

Say **"Hello Coglet"** (or press the ESP BOOT button) and talk. The red LED is
on while Coglet listens. Coglet moves its head, ears, eyes and mouth to match
what it says and how it feels, and closes its eyes and relaxes when it goes
back to standby.

A few seconds after it starts up, Coglet starts listening by itself once, so
you can talk to it straight away.

By default Coglet stops listening while it speaks. To interrupt it in the
middle of a sentence, turn on **Talk over Coglet** in the
[settings](settings-and-songs.md).

## Moves on request

Ask in your own words, for example:

| Say | Coglet |
|---|---|
| "Shake your head" | shakes its head three times |
| "Blink" | blinks three times |
| "Move your left ear" / "your right ear" | moves that ear |
| "Wiggle your ears" | moves both ears |
| "Take a photo" / "What do you see?" | looks through its camera |

## Dancing

Say **"Dance for me"**. Coglet answers with one short line, ends the
conversation, plays a song of about 30 seconds and dances to it, then asks how
you liked it.

Each edition has three built-in dances; ask for one by name or let Coglet
choose:

| Edition | Dances |
|---|---|
| Standard | **mecha** (heavy electro), **evil** (gloomy gothic), **cat** (gentle cat pop) |
| Christmas | **lyrical** (Silent Night), **classic** (Jingle Bells), **grand** (Joy to the World) |
| Elf | **workshop** (Deck the Halls), **mischief** (God Rest Ye Merry Gentlemen), **party** (We Wish You a Merry Christmas) |
| Snowman | **lullaby** (Brahms' Lullaby), **stomp** (Good King Wenceslas), **blizzard** (Carol of the Bells) |

You can also add your own songs and say "dance to one of my songs" or
"dance to *song name*": see [Settings and songs](settings-and-songs.md).

Saying "Hello Coglet" or pressing the button during a dance stops it.

## Reminders

Ask, for example, "Remind me in 20 minutes to take the bread out" or
"Remind me tomorrow at 8 to call Anna". When it's time, Coglet plays a chime
and says the reminder, even if no conversation is open. You can also ask
"Which reminders do I have?" or "Cancel the reminder about the bread".

- Up to 12 reminders, each one-off (no repeats).
- Reminders are stored on Coglet and survive restarts and updates.
- Times follow the time zone that xiaozhi.me reports for your Coglet.

## Switches and buttons

| Control | What it does |
|---|---|
| **Mode switch** ESP / RP2040 (small, white, next to the programming USB-C port) | Which chip the USB port talks to. Leave it on **ESP** (right). |
| **Calibration** switch | Puts every servo in its calibration position, for assembly. |
| **Servo test** button | In Calibration Mode only: hold it to wiggle every servo ±10° around its calibration position. |
| **Face-track** switch | Turns face tracking (Grove Vision AI camera in the eye) on or off. Off does not stop the other moves. |
| **ESP BOOT** button | Start or stop a conversation. |
| **RST** buttons | Restart the ESP32-S3 or the RP2040. |

## Power and standby

In standby Coglet closes its eyes and switches its servos off, so they stay
quiet and cool. On waking, the servos switch on one after another to avoid a
current spike.

Use a **5 V / 3 A** supply. If Coglet restarts when it starts moving, the
supply or cable is too weak.
