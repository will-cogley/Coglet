# Getting started

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/user/getting-started.md) · [Español](../../es/user/getting-started.md) · [日本語](../../ja/user/getting-started.md)

This page takes a built Coglet from the box to its first conversation. For
assembly, see the [build video](https://youtu.be/EdgYNhH70Qo) and the
[NMRobots knowledge base](https://nmrobots.com/pages/coglet).

## What you need

- A computer with **Chrome or Edge** (Windows, macOS or Linux). Other browsers
  can't talk to USB devices.
- A **USB-C data cable** (many cables only charge).
- A **5 V / 3 A** power supply for the servos. Multi-port fast chargers often
  can't deliver 3 A at 5 V; a plain 5 V / 3 A charger works best.
- A **2.4 GHz** Wi-Fi network (5 GHz networks are not supported).

## 1. Update Coglet with the Coglet Updater

1. Open <https://will-cogley.github.io/Coglet/>.
2. Plug Coglet in through the **top (programming) USB-C port**. Leave the small
   white **mode switch** on **ESP** (slid to the right), as it comes.
3. Choose an edition (Standard, Christmas, Elf or Snowman; they only differ in
   the built-in dances and sounds) and click **Connect & Update**.
4. Pick Coglet in the port list and wait for **Done**.

Your Wi-Fi, pairing, reminders, settings and songs are kept. Only
**Advanced options → Fresh install** erases everything.

**Check my Coglet** tells you whether an update is worth it, without changing
anything.

### One extra step on older Coglets

If the page says **"One more step"**, your servo board (RP2040) needs a
one-time setup. This only applies to Coglets made before November 2026:

1. Unplug Coglet, slide the mode switch to the left (**RP2040**), plug it back in.
2. Click **Set up servo board** and choose the RP2040 in the list (often
   "Board CDC" or "USB Serial Device").
3. When it says **Done**, unplug, slide the switch back to the right (**ESP**),
   plug in, and click **Check Coglet**.

From then on, Coglet keeps its servo board up to date by itself after every
update.

## 2. Connect Coglet to Wi-Fi

On first start (or when it can't find its network), Coglet opens its own
Wi-Fi hotspot:

1. On your phone or computer, join the network **Xiaozhi-XXXX**.
2. A setup page opens. If it doesn't, browse to <http://192.168.4.1>.
3. Pick your 2.4 GHz network, enter the password and press **Connect**.
   On an iPhone hotspot, turn on **Maximize Compatibility**.
4. Coglet restarts and joins your network.

To move Coglet to another network: press the **ESP BOOT** button while Coglet
is starting up and not yet connected; it forgets the old network and opens
the hotspot again.

## 3. Pair Coglet with xiaozhi.me

Coglet talks through the xiaozhi.me service. The first time it connects, it
says a **6-digit code**:

1. Sign in at <https://xiaozhi.me> and open the console.
2. Add a device and enter the code.
3. Coglet is ready. Say **"Hello Coglet"**.

There you can also choose the voice, language and personality.

Pairing is kept through normal updates. After a **Fresh install** Coglet
says a new code and needs to be paired again.

> An offline backend that runs on your own computer is in early development:
> [NMWorkbench](https://github.com/will-cogley/NMWorkbench).

## Next

- [Using Coglet](using-coglet.md)
- [Settings and songs](settings-and-songs.md)
- [Troubleshooting](troubleshooting.md)
