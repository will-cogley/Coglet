# Echounterdrückung im Gerät (AEC)

[Dokumentation](../README.md) · [English](../../en/developer/audio-aec.md) · **Deutsch** · [Español](../../es/developer/audio-aec.md) · [日本語](../../ja/developer/audio-aec.md)

Mit AEC kann der Nutzer Coglet ins Wort fallen: Coglet hört weiter zu, während
er spricht, und lässt sich ohne Aktivierungswort unterbrechen. Nutzer schalten
das mit **Coglet ins Wort fallen** im Coglet Updater um.

## Funktionsweise

Mikrofon und MAX98357A-Verstärker hängen an zwei getrennten I2S-Ports, und es
gibt keine Hardware-Rückführung des Lautsprechersignals, daher kann die
serienmäßige AEC im Gerät nicht laufen. Coglet erzeugt die Referenz in Software
auf dem ESP32-S3, ohne serverseitige AEC:

1. Jedes Mal, wenn der I2S-TX-DMA des Lautsprechers einen 10-ms-Block gesendet
   hat, sieht sein Callback `on_sent` das PCM, das tatsächlich zum Verstärker
   ging.
2. Jedes Mal, wenn der I2S-RX-DMA des Mikrofons einen 15-ms-Block empfangen
   hat, sieht `on_recv` ihn ebenfalls.
3. Beide Callbacks erhalten Zeitstempel mit `esp_timer`. `SoftwareAecReference`
   glättet die Zeitstempel mit einem Taktverfolger, ordnet jedem
   Mikrofon-Sample das im selben Moment gespielte Lautsprecher-Sample zu und
   tastet 24 kHz mit Anti-Aliasing auf 16 kHz um.
4. `Read()` liefert verschachtelt `[mic, ref]`, das `MR`-Format der esp-sr-AFE-AEC.
5. Mit AEC verwenden alle Aufweckwege den Zuhörmodus **realtime**, auch das
   Boot-Auto-Awake.

Ist AEC aus, läuft nichts davon: Der Audiopfad ist derselbe wie in einem Build
ohne AEC.

## Konfiguration

| Option | Veröffentlichte Firmware | |
|---|---|---|
| `CONFIG_USE_DEVICE_AEC` | an | AEC einkompiliert |
| `CONFIG_COGLET_AEC_DEFAULT_OFF` | an | aus, bis der Nutzer es einschaltet (Einstellung `aec=on`) |
| `CONFIG_COGLET_AEC_REF_DELAY_MS` | 0 | Referenzversatz, −10…20 ms |

Die Einstellung wird einmal beim Start gelesen (`CogletSettings::DeviceAec()`),
daher startet Coglet beim Umschalten neu. Lässt sich die Referenz nicht
anlegen, protokolliert Coglet `Device AEC unavailable on this boot` und hört
zu wie ohne AEC.

## Prüfen am Gerät

Startprotokoll:

```
NoAudioCodec: [AEC-REF] software loopback ENABLED: mic 16000 Hz (slot 0/2), speaker 24000 Hz ...
CogletAutoAwake: BOOT_LISTENING: mode=realtime
CogletSettings: Device AEC: on (from settings)
```

`AfeAudioProcessor` darf nicht `no reference channel` melden.

Mit *Coglet: log microphone levels every second* (`CONFIG_COGLET_MIC_DIAG_LOG`)
erscheint jede Sekunde eine Zeile:

```
[MIC] mode=aec-ref ... | [AEC-REF] refPeak=... offset=..us missing=.. late=.. micOvr=.. refOvr=.. resync=a/b torn=..
```

| Feld | In Ordnung |
|---|---|
| `refPeak` | deutlich über 0, während Coglet spricht, 0 in Stille |
| `offset` | stabil innerhalb weniger Millisekunden (Stabilität zählt mehr als der Wert) |
| `missing` / `late` | wachsen kaum |
| `micOvr` | wächst beim Wechsel zwischen Aktivierungswort und Gespräch: normal |
| `resync` | je 1 beim Start, dann stabil |
| `torn` | immer 0 |

Hörtest: Lassen Sie Coglet eine lange Antwort geben und unterbrechen Sie ihn;
er sollte aufhören und Sie verstehen. Solange Sie schweigen, darf er sich nicht
selbst unterbrechen.

## Die Referenz ausrichten

1. Aktivieren Sie in menuconfig *Enable Audio Debugger* und tragen Sie
   `IP:8000` Ihres Computers ein.
2. Starten Sie auf dem Computer `python scripts/audio_debug_server.py`
   (standardmäßig 16 kHz, 2 Kanäle).
3. Lassen Sie Coglet sprechen und öffnen Sie das WAV in Audacity: links ist das
   Mikrofon, rechts die Referenz.
4. Das Echo im Mikrofon sollte etwas **nach** der Referenz kommen (0–3 ms).
   - Echo **vor** der Referenz: Referenzversatz negativ stellen (−1, −2, …).
   - Echo mehr als 10 ms zu spät: Die Zeitstempel stimmen nicht; melden Sie es
     bitte mit der Aufnahme.

## Bekannte Grenzen

- **Servogeräusche** sind kein Echo: Getriebegeräusche, während Mund, Ohren und
  Nacken sich bewegen, lassen sich nicht unterdrücken und können Coglet
  unterbrechen.
- **Hohe Lautstärke**: Verzerrungen durch den kleinen Lautsprecher und das
  Gehäuse werden nicht vollständig unterdrückt. AEC funktioniert am besten bei
  höchstens 50 % Lautstärke.
- Mit AEC ist die lokale VAD der AFE aus (wie bei den Upstream-Platinen
  ESP-Box); der Server entscheidet, wo Sprache beginnt und endet.

## Dateien

- `main/audio/codecs/software_aec_reference.{h,cc}`: Zeitausrichtung, ohne IDF
- `main/audio/codecs/no_audio_codec.{h,cc}`: DMA-Callbacks, `EnableSoftwareAecReference()`, `MR`-Ausgabe
- `main/boards/cognog-v3/cognog_v3_board.cc`: startet die Referenz, wenn AEC an ist
- `main/audio/processors/afe_audio_processor.cc`: Rückfall ohne Referenzkanal
- `main/application.cc`: realtime-Modus für Auto-Awake mit AEC
