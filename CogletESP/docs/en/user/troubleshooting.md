# Troubleshooting

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/user/troubleshooting.md) · [Español](../../es/user/troubleshooting.md) · [日本語](../../ja/user/troubleshooting.md)

## Asking for help

On the [Coglet Updater](https://will-cogley.github.io/Coglet/) page, click
**Show device log**, make the problem happen, then click **Copy log** and post
it in the community. The log is in English on purpose, so everyone can read it.

## Updating

**Coglet isn't in the list of ports.**
Try another USB cable (many only charge) and another USB port without a hub.
Use Coglet's top USB-C port with the mode switch on **ESP**. On Windows the driver
installs itself the first time; give it a minute. If it still doesn't appear,
tick **Advanced options → Show all ports**.

**There are several ports. Which one is Coglet?**
Unplug Coglet and connect again: the entry that disappeared is Coglet. It is
usually called "USB Serial", "CH340/CH343", "CP210x" or "USB JTAG/serial".

**"Failed to connect".**
Close anything else that uses the port (Thonny, the Arduino IDE, another tab
with the page). If it still fails: hold **BOOT**, press and release **RESET**,
release **BOOT**, then click **Connect & Update**. A lower speed under
**Advanced options** can help as well.

**The update stopped halfway, or I unplugged Coglet.**
Nothing breaks for good: plug it back in and update again. If the servo board
was being updated, Coglet finishes or repeats that by itself at the next start.

**The page says "One more step".**
Your servo board needs the one-time setup: see
[Getting started](getting-started.md#one-extra-step-on-older-coglets).

**The servo board setup can't connect.**
Check that the mode switch is on **RP2040** and that nothing else has the port
open.
If the board never had MicroPython installed, ask the community for the
starter firmware.

**Do I have to open Coglet to reach the mode switch?**
Only for the one-time servo board setup, and only on Coglets made before
November 2026. If you'd rather not, you can still update: everything works
except new servo moves.

**I build my own firmware. Will the page overwrite it?**
Yes, **Connect & Update** installs the official firmware. Songs added on the
page are kept; songs compiled into your own build are not.

## Talking

**Coglet doesn't wake up, or wakes up by itself.**
In the settings, lower the wake-up sensitivity (for example 2) if it misses
you, or raise it (for example 10) if it wakes up by itself. Speak at a normal
distance, facing Coglet. You can also choose another wake word.

**Coglet says a 6-digit code.**
It needs to be paired with xiaozhi.me again (this happens after a Fresh
install): see [Getting started](getting-started.md#3-pair-coglet-with-xiaozhime).

**Coglet can't join my Wi-Fi.**
Only 2.4 GHz networks work. On an iPhone hotspot, turn on **Maximize
Compatibility**. To enter the network again, press **ESP BOOT** while Coglet
starts up.

## Moving

**Coglet restarts or the LEDs dim when it starts moving.**
The power supply or cable is too weak. Use a plain **5 V / 3 A** charger and a
short, thick cable. Multi-port fast chargers often fail here.

**A servo doesn't move.**
Check which socket it is plugged into: the socket numbers are printed on the
board (see [Hardware](../developer/hardware.md#servo-sockets)). Use the
Calibration switch and the Servo test button to check every servo.

**The eyes don't follow me.**
Check that the **Face-track** switch is on. Face tracking only runs while
Coglet is awake; in standby the eyelid is closed.
