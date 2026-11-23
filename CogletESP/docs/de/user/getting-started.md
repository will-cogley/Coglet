# Erste Schritte

[Dokumentation](../README.md) · [English](../../en/user/getting-started.md) · **Deutsch** · [Español](../../es/user/getting-started.md) · [日本語](../../ja/user/getting-started.md)

Diese Seite führt einen fertig gebauten Coglet aus dem Karton bis zum ersten
Gespräch. Für den Zusammenbau siehe das [Aufbauvideo](https://youtu.be/EdgYNhH70Qo)
und die [NMRobots-Wissensdatenbank](https://nmrobots.com/pages/coglet).

## Was Sie brauchen

- Einen Computer mit **Chrome oder Edge** (Windows, macOS oder Linux). Andere
  Browser können nicht mit USB-Geräten kommunizieren.
- Ein **USB-C-Datenkabel** (manche Kabel laden nur).
- Ein **5-V/3-A-Netzteil** für die Servos. Mehrport-Schnellladegeräte liefern
  oft keine 3 A bei 5 V; ein einfaches 5-V/3-A-Ladegerät funktioniert am besten.
- Ein **2,4-GHz**-WLAN (5-GHz-Netze werden nicht unterstützt).

## 1. Coglet mit dem Coglet Updater aktualisieren

1. Öffnen Sie <https://will-cogley.github.io/Coglet/>.
2. Schließen Sie Coglet über den **oberen USB-C-Anschluss (Programmieranschluss)**
   an. Lassen Sie den kleinen weißen **Modusschalter** auf **ESP** (nach rechts
   geschoben), so wie ab Werk.
3. Wählen Sie eine Edition (Standard, Weihnachten, Elfen oder Schneemann; sie
   unterscheiden sich nur in den eingebauten Tänzen und Tönen) und klicken Sie
   auf **Verbinden & Aktualisieren**.
4. Wählen Sie Coglet in der Portliste und warten Sie, bis **Fertig** erscheint.

WLAN, Kopplung, Erinnerungen, Einstellungen und Songs bleiben erhalten. Nur
**Erweiterte Optionen → Neuinstallation** löscht alles.

**Meinen Coglet prüfen** zeigt Ihnen, ob sich ein Update lohnt, ohne etwas zu
verändern.

### Ein zusätzlicher Schritt bei älteren Coglets

Wenn die Seite **„Noch ein Schritt“** anzeigt, braucht Ihre Servoplatine
(RP2040) eine einmalige Einrichtung. Das betrifft nur Coglets, die vor
November 2026 hergestellt wurden:

1. Trennen Sie Coglet, schieben Sie den Modusschalter nach links (**RP2040**)
   und schließen Sie ihn wieder an.
2. Klicken Sie auf **Servoplatine einrichten** und wählen Sie den RP2040 in der
   Liste (oft „Board CDC“ oder „USB Serial Device“).
3. Wenn **Fertig** erscheint, trennen Sie Coglet, schieben Sie den Schalter
   zurück nach rechts (**ESP**), schließen Sie ihn an und klicken Sie auf
   **Coglet prüfen**.

Ab dann hält Coglet seine Servoplatine nach jedem Update selbst aktuell.

## 2. Coglet mit dem WLAN verbinden

Beim ersten Start (oder wenn er sein Netz nicht findet) öffnet Coglet einen
eigenen WLAN-Hotspot:

1. Verbinden Sie Ihr Handy oder Ihren Computer mit dem Netz **Xiaozhi-XXXX**.
2. Eine Einrichtungsseite öffnet sich. Falls nicht, rufen Sie
   <http://192.168.4.1> auf.
3. Wählen Sie Ihr 2,4-GHz-Netz, geben Sie das Passwort ein und tippen Sie auf
   **Connect**. Bei einem iPhone-Hotspot schalten Sie **Maximale
   Kompatibilität** ein.
4. Coglet startet neu und verbindet sich mit Ihrem Netz.

Um Coglet in ein anderes Netz zu bringen: Drücken Sie die Taste **ESP BOOT**,
während Coglet startet und noch nicht verbunden ist. Er vergisst das alte Netz
und öffnet den Hotspot erneut.

## 3. Coglet mit xiaozhi.me koppeln

Coglet spricht über den Dienst xiaozhi.me. Beim ersten Verbinden sagt er einen
**6-stelligen Code**:

1. Melden Sie sich bei <https://xiaozhi.me> an und öffnen Sie die Konsole.
2. Fügen Sie ein Gerät hinzu und geben Sie den Code ein.
3. Coglet ist bereit. Sagen Sie **„Hello Coglet“**.

Dort können Sie auch Stimme, Sprache und Persönlichkeit wählen.

Die Kopplung bleibt bei normalen Updates erhalten. Nach einer
**Neuinstallation** sagt Coglet einen neuen Code und muss erneut gekoppelt
werden.

> Ein Offline-Backend, das auf Ihrem eigenen Computer läuft, ist in früher
> Entwicklung: [NMWorkbench](https://github.com/will-cogley/NMWorkbench).

## Weiter

- [Coglet benutzen](using-coglet.md)
- [Einstellungen und Songs](settings-and-songs.md)
- [Fehlerbehebung](troubleshooting.md)
