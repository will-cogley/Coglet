# Releases veröffentlichen

[Dokumentation](../README.md) · [English](../../en/developer/releasing.md) · **Deutsch** · [Español](../../es/developer/releasing.md) · [日本語](../../ja/developer/releasing.md)

Releases werden von GitHub Actions gebaut (`.github/workflows/firmware.yml`) und
auf der Seite Coglet Updater sowie als GitHub-Releases veröffentlicht.

## Einmalige Einrichtung des Repositorys

Administratorrechte nötig:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. **Settings → Environments → github-pages → Deployment branches and tags →
   Add rule → Ref type: Tag, Muster `v*`**. Ohne diese Regel wird ein Tag
   gebaut, aber sein Deploy abgelehnt („not allowed to deploy to github-pages
   due to environment protection rules“).

## Ein Release veröffentlichen

1. Erhöhen Sie `PROJECT_VER` in `CogletESP/CMakeLists.txt` (für lokale Builds
   und Builds ohne Tag).
2. Pushen Sie ein Tag:

```bash
git tag v2.4.0
git push origin v2.4.0
```

Tags haben die Form `v2.4.0` oder `v2.4.0-beta1`; alles andere wird abgelehnt.
Das Tag ohne `v` wird zur Firmware-Version (`-D PROJECT_VER=2.4.0`), die
**Meinen Coglet prüfen** zurückliest. Verwenden Sie nur Zahlen: Die OTA-Prüfung
vergleicht sie einzeln. Ein erneuter Lauf eines Tags baut den Commit, auf den es
zeigt; für neuen Code legen Sie ein neues Tag an.

## Was der Workflow macht

1. Baut viermal im Container `espressif/idf:v5.5.3`: Standard mit der
   `sdkconfig` des Repositorys, dann Weihnachten, Elfen und Schneemann in
   `build-<edition>/` mit `sdkconfig.<edition>` darüber. Jeder Build enthält das
   RP2040-Programm und speichert den kurzen Commit
   (`-D COGLET_BUILD_COMMIT=…`; lokale Builds speichern `local`).
2. Kopiert die Flash-Teile aus `build/flasher_args.json` und schreibt mit
   `tools/web_flasher/make_manifest.py` `firmware/manifest.json` (Offsets,
   Größen, MD5, Edition, Lage von Einstellungen und Songbibliothek, Link zu den
   Release-Notes), ebenso `firmware-christmas/`, `firmware-elf/` und
   `firmware-snowman/`.
3. Stellt die Seite, die Firmware und die RP2040-Dateien auf GitHub Pages bereit.
4. Hängt `coglet-firmware-<version>.zip` und je ein Zip pro Feiertags-Edition an
   das Release an, jeweils mit den Teilen und einer esptool-Befehlszeile.

Von Hand im Tab **Actions** gestartet, baut und veröffentlicht er eine Version
`dev-<commit>` ohne Release.

## Checkliste

- Baut lokal mit ESP-IDF **v5.5.3**, alle vier Editionen.
- An einem Coglet getestet: Update vom vorherigen Release mit dem Coglet
  Updater, Update der Servoplatine, Aktivierungswort, ein Tanz, eine Erinnerung.
- RP2040-Dateien geändert? Jeder Coglet überträgt sie nach dem Update erneut.
- Release-Notes geschrieben (die Seite verlinkt sie).
