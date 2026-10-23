# BLECH: gemeinsame automatische Leistungsprüfung

Stand 22.10.2026. Im Emulator gemessen, am Gerät nicht geprüft.
Die gemeinsame Prüfung besteht für Hacktribe, Korg rot und Synth.

Die [registrierte Basis](2026-10-22-gesamtpruefung-basis.json) bindet die
früheren Abnahmen für Pad-Geometrie, Plugin-Prüfung und MUL an die genaue
Vergleichsbasis und die Hashes der Messdateien. Diese Gewinne werden nicht
nochmals gegen einen Stand verlangt, der sie schon enthält. Die bestätigte
MUL-Grenze bleibt 19,83 Prozent. Der zusätzliche Code der Füllroutine darf
höchstens 112 Byte je Build belegen. Der alte Einzelphasenvergleich bleibt streng.

| Build | Mehr Code und Daten | Weniger reserviertes RAM | Größte freie Lücke | Native SysEx-Fälle je Wiederholung |
|---|---:|---:|---:|---:|
| Hacktribe | 44 Byte | 19 KiB | 19 KiB | 490 |
| Korg rot | 44 Byte | 19 KiB | 19 KiB | 490 |
| Synth | 60 Byte | 19 KiB | 322,26 KiB | 452 |

Die größte Mehrarbeit eines Szenenfensters beträgt rund 0,21 Prozent und
bleibt unter einem Prozent. Die Decoderarbeit sinkt bei Life und Mandelbrot
um mehr als die verlangten drei Prozent. Bilder und Zustände der Apps stimmen
überein. Die langen Pad-Bindungen bleiben innerhalb der Grenze von fünf Prozent
über dem Original. Die Plugin-Prüfung ist gegenüber der integrierten Basis
nochmals rund 39,59 Prozent günstiger; das ist keine neue Abnahme des früheren
70-Prozent-Ziels. Die [Messdatei](2026-10-22-patch-effizienz-gesamt-zahlen.json)
enthält die genauen Werte.

Der native SysEx-Test wurde zusätzlich dreimal je Build gegen die exakte
Basis-VSB ausgeführt. Der ursprüngliche Generator erzeugt genau die in dieser
Datei enthaltenen Bytes. Firmwarehash, Befehlsvektoren, Ergebnisse und Datei-I/O
werden mitgeprüft. Der maximale Block bleibt 32 KiB. Der Emulator bildet den
USB-Controller und dessen echte Wartezeiten weiterhin nicht ab.

Die vollständigen Firmwareprüfungen 459/459, 484/484 und 363/363 sowie die
Profilmatrix stammen aus dem unveränderten geprüften Produktstand. Für diese
Anpassung wurde nur das Messwerkzeug geändert, keine Firmwarefunktion. Die
privaten Eingangsdateien und erzeugten VSBs bleiben außerhalb dieses Repos.

```sh
python3 tools/emu/patch_performance.py \
  --baseline "$baseline" --candidate "$candidate" --phase combined \
  --integrated-baseline --baseline-transfers "$baseline_transfers" \
  --out "$report"
```

Die gesonderte Transferdatei wird mit `sysex_bench.py --generator` gegen die
Basis erzeugt. Ein anderer Firmwarehash, geänderte historische Nachweise,
fehlende Transferdaten, zusätzliche RAM-Belegung, mehr als 112 Byte neuer Code,
verkleinerte Lücken oder abweichende App-Bilder lassen die Prüfung scheitern.
Dies ersetzt keine Geräteabnahme und belegt keinen schnelleren Sample-Import.

14 Werkzeugtests, 963 Unit-Tests, 164 Browserprüfungen und neun Dokuprüfungen
bestehen. Die 143 vorgesehenen Unit-Auslassungen und eine Browser-Auslassung
bleiben ausgewiesen. Alle 273 Produktquellen und sechs Firmwarehashes wurden
erneut geprüft. Der erneute Aufbau der drei Sätze ist bytegleich.
