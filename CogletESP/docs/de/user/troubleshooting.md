# Fehlerbehebung

[Dokumentation](../README.md) · [English](../../en/user/troubleshooting.md) · **Deutsch** · [Español](../../es/user/troubleshooting.md) · [日本語](../../ja/user/troubleshooting.md)

## Hilfe bekommen

Klicken Sie auf der Seite [Coglet Updater](https://will-cogley.github.io/Coglet/)
auf **Geräteprotokoll anzeigen**, lassen Sie das Problem auftreten, klicken Sie
auf **Protokoll kopieren** und posten Sie es in der Community. Das Protokoll ist
absichtlich auf Englisch, damit alle es lesen können.

## Update

**Coglet steht nicht in der Liste der Ports.**
Versuchen Sie ein anderes USB-Kabel (viele laden nur) und einen anderen
USB-Anschluss ohne Hub. Verwenden Sie den oberen USB-C-Anschluss von Coglet mit
dem Modusschalter auf **ESP**. Unter Windows installiert sich der Treiber beim
ersten Mal selbst; warten Sie eine Minute. Erscheint Coglet immer noch nicht,
aktivieren Sie **Erweiterte Optionen → Alle Ports anzeigen**.

**In der Liste stehen mehrere Ports. Welcher ist Coglet?**
Trennen Sie Coglet und verbinden Sie erneut: Der Eintrag, der verschwunden ist,
ist Coglet. Er heißt meist „USB Serial“, „CH340/CH343“, „CP210x“ oder
„USB JTAG/serial“.

**„Failed to connect“ (Verbindung fehlgeschlagen).**
Schließen Sie alles andere, das den Port verwendet (Thonny, die Arduino IDE,
einen weiteren Tab mit der Seite). Klappt es immer noch nicht: Halten Sie
**BOOT**, drücken und lösen Sie **RESET**, lösen Sie **BOOT** und klicken Sie
auf **Verbinden & Aktualisieren**. Eine niedrigere Geschwindigkeit unter
**Erweiterte Optionen** kann ebenfalls helfen.

**Das Update brach mittendrin ab, oder ich habe Coglet getrennt.**
Nichts geht dauerhaft kaputt: Schließen Sie ihn wieder an und aktualisieren Sie
erneut. Wurde gerade die Servoplatine aktualisiert, beendet oder wiederholt
Coglet das beim nächsten Start selbst.

**Die Seite zeigt „Noch ein Schritt“.**
Ihre Servoplatine braucht die einmalige Einrichtung: siehe
[Erste Schritte](getting-started.md#ein-zusätzlicher-schritt-bei-älteren-coglets).

**Die Einrichtung der Servoplatine kann keine Verbindung herstellen.**
Prüfen Sie, dass der Modusschalter auf **RP2040** steht und kein anderes
Programm den Port geöffnet hat. Wurde auf der Platine nie MicroPython
installiert, fragen Sie in der Community nach der Starter-Firmware.

**Muss ich Coglet öffnen, um an den Modusschalter zu kommen?**
Nur für die einmalige Einrichtung der Servoplatine, und nur bei Coglets, die vor
November 2026 hergestellt wurden. Wenn Sie ihn lieber nicht öffnen möchten,
können Sie trotzdem aktualisieren: Alles funktioniert außer neuen
Servobewegungen.

**Ich baue meine eigene Firmware. Überschreibt die Seite sie?**
Ja, **Verbinden & Aktualisieren** installiert die offizielle Firmware. Songs,
die Sie auf der Seite hinzugefügt haben, bleiben erhalten; Songs, die in Ihren
eigenen Build kompiliert sind, nicht.

## Sprechen

**Coglet wacht nicht auf oder wacht von selbst auf.**
Senken Sie in den Einstellungen die Aufweckschwelle (zum Beispiel auf 3), wenn
er Sie überhört, oder erhöhen Sie sie (zum Beispiel auf 10), wenn er von selbst
aufwacht. Sprechen Sie aus normaler Entfernung und Coglet zugewandt. Sie können
auch ein anderes Aktivierungswort wählen.

**Coglet sagt einen 6-stelligen Code.**
Er muss erneut mit xiaozhi.me gekoppelt werden (das passiert nach einer
Neuinstallation): siehe
[Erste Schritte](getting-started.md#3-coglet-mit-xiaozhime-koppeln).

**Coglet verbindet sich nicht mit meinem WLAN.**
Nur 2,4-GHz-Netze funktionieren. Bei einem iPhone-Hotspot schalten Sie
**Maximale Kompatibilität** ein. Um das Netz neu einzugeben, drücken Sie
**ESP BOOT**, während Coglet startet.

## Bewegung

**Coglet startet neu oder die LEDs werden dunkler, sobald er sich bewegt.**
Netzteil oder Kabel sind zu schwach. Verwenden Sie ein einfaches
**5-V/3-A-Ladegerät** und ein kurzes, dickes Kabel. Mehrport-Schnellladegeräte
scheitern hier oft.

**Ein Servo bewegt sich nicht.**
Prüfen Sie, in welchem Steckplatz er steckt: Die Nummern sind auf die Platine
gedruckt (siehe [Hardware](../developer/hardware.md#servo-steckplätze)). Prüfen
Sie jeden Servo mit dem Kalibrierschalter und der Servotest-Taste.

**Die Augen folgen mir nicht.**
Prüfen Sie, dass der Schalter **Gesichtsverfolgung** eingeschaltet ist. Die
Gesichtsverfolgung läuft nur, wenn Coglet wach ist; in Bereitschaft ist das
Augenlid geschlossen.
