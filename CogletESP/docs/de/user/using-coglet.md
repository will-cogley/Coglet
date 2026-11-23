# Coglet benutzen

[Dokumentation](../README.md) · [English](../../en/user/using-coglet.md) · **Deutsch** · [Español](../../es/user/using-coglet.md) · [日本語](../../ja/user/using-coglet.md)

## Sprechen

Sagen Sie **„Hello Coglet“** (oder drücken Sie die Taste ESP BOOT) und
sprechen Sie. Die rote LED leuchtet, solange Coglet zuhört. Coglet bewegt Kopf,
Ohren, Augen und Mund passend zu dem, was er sagt und wie er sich fühlt, und
schließt die Augen und entspannt sich, wenn er wieder in Bereitschaft geht.

Einige Sekunden nach dem Start beginnt Coglet einmal von selbst zuzuhören,
sodass Sie gleich mit ihm sprechen können.

Standardmäßig hört Coglet nicht zu, während er spricht. Um ihn mitten im Satz
zu unterbrechen, schalten Sie **Coglet ins Wort fallen** in den
[Einstellungen](settings-and-songs.md) ein.

## Bewegungen auf Wunsch

Fragen Sie mit eigenen Worten, zum Beispiel:

| Sagen Sie | Coglet |
|---|---|
| „Schüttel den Kopf“ | schüttelt dreimal den Kopf |
| „Blinzle“ | blinzelt dreimal |
| „Beweg dein linkes Ohr“ / „dein rechtes Ohr“ | bewegt dieses Ohr |
| „Wackel mit den Ohren“ | bewegt beide Ohren |
| „Mach ein Foto“ / „Was siehst du?“ | schaut durch seine Kamera |

## Tanzen

Sagen Sie **„Tanz für mich“**. Coglet antwortet mit einer kurzen Zeile, beendet
das Gespräch, spielt einen etwa 30 Sekunden langen Song, tanzt dazu und fragt
dann, wie es Ihnen gefallen hat.

Jede Edition hat drei eingebaute Tänze; fragen Sie nach einem bestimmten oder
lassen Sie Coglet wählen:

| Edition | Tänze |
|---|---|
| Standard | **mecha** (wuchtiger Elektro), **evil** (düsterer Gothic), **cat** (sanfter Katzen-Pop) |
| Weihnachten | **lyrical** (Stille Nacht), **classic** (Jingle Bells), **grand** (Freue dich, Welt) |
| Elfen | **workshop** (Deck the Halls), **mischief** (God Rest Ye Merry Gentlemen), **party** (We Wish You a Merry Christmas) |
| Schneemann | **lullaby** (Guten Abend, gut’ Nacht von Brahms), **stomp** (Good King Wenceslas), **blizzard** (Carol of the Bells) |

Sie können auch eigene Songs hinzufügen und sagen „tanz zu einem meiner Songs“
oder „tanz zu *Songname*“: siehe [Einstellungen und Songs](settings-and-songs.md).

„Hello Coglet“ oder ein Druck auf die Taste beendet einen Tanz.

## Erinnerungen

Sagen Sie zum Beispiel „Erinnere mich in 20 Minuten daran, das Brot
herauszunehmen“ oder „Erinnere mich morgen um 8, Anna anzurufen“. Zur
richtigen Zeit spielt Coglet einen Ton und sagt die Erinnerung, auch wenn
gerade kein Gespräch läuft. Sie können auch fragen „Welche Erinnerungen habe
ich?“ oder „Lösch die Erinnerung mit dem Brot“.

- Bis zu 12 Erinnerungen, jeweils einmalig (keine Wiederholungen).
- Erinnerungen sind auf Coglet gespeichert und überstehen Neustarts und Updates.
- Die Zeiten folgen der Zeitzone, die xiaozhi.me für Ihren Coglet meldet.

## Schalter und Tasten

| Bedienelement | Funktion |
|---|---|
| **Modusschalter** ESP / RP2040 (klein, weiß, neben dem USB-C-Programmieranschluss) | Mit welchem Chip der USB-Anschluss spricht. Lassen Sie ihn auf **ESP** (rechts). |
| Schalter **Kalibrierung** | Bringt jeden Servo in seine Kalibrierposition, für den Zusammenbau. |
| Taste **Servotest** | Nur im Kalibriermodus: gedrückt halten, um jeden Servo um ±10° um seine Kalibrierposition zu bewegen. |
| Schalter **Gesichtsverfolgung** (FACE-TRACK) | Schaltet die Gesichtsverfolgung (Grove-Vision-AI-Kamera im Auge) ein oder aus. Aus stoppt die übrigen Bewegungen nicht. |
| Taste **ESP BOOT** | Gespräch beginnen oder beenden. |
| Tasten **RST** | Startet den ESP32-S3 oder den RP2040 neu. |

## Strom und Bereitschaft

In Bereitschaft schließt Coglet die Augen und schaltet seine Servos ab, damit
sie leise und kühl bleiben. Beim Aufwachen schalten sich die Servos
nacheinander ein, um eine Stromspitze zu vermeiden.

Verwenden Sie ein **5-V/3-A-Netzteil**. Startet Coglet neu, sobald er sich zu
bewegen beginnt, sind Netzteil oder Kabel zu schwach.
