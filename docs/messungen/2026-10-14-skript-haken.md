# Plugin-Haken: Eingangsfilter und Rahmenhaken

Stand 2026-10-14. Kein Gerätezugriff.
Geprüft sind native Haken ohne Firmware und in der gebooteten Firmware.
Plugins wurden ausschließlich ins Emulator-RAM geladen, niemals in die VSB.
`korg.led`, produktiver Start und Kartenlader folgen danach
(`2026-10-14-skript-led.md`, `2026-10-14-skript-karte.md`).

## Ergebnis

Eingangsfilter `0xC002837C`: nur normalisierte Ereignisse in einen Ring mit
64 Plätzen, keine VM-Ausführung. Aufeinanderfolgende Werte desselben Reglers
werden zusammengefasst; volle Ringe verwerfen neue Ereignisse und zählen sie.
Vorabflags, unbekannte Paneltypen sowie Ausschalt- und Netzteilmeldungen gehen
unverändert weiter. Die Capturemaske wird vorher gesetzt; EXIT wird niemals
verschluckt. Eine spätere Capture-API ist hier noch nicht gebaut.

Rahmenhaken `0xC00836FC`: nur UiTask, READY je Plugin nach Hauptbildschirm,
danach eine Momentaufnahme der Warteschlange und FRAME. Alle Handler teilen
denselben Timer3-Start und die 5-ms-Grenze. Eintritt, Ende und lange Läufe
alle 256 Operationen prüfen die Zeit. Exakt 5 ms sind erlaubt. Bei TIME
wird nur der Verursacher abgeschaltet; der Cursor setzt die restliche Folge
im nächsten Rahmen fort. Ein laufender Hostaufruf ist nicht unterbrechbar.

Beide Haken erhalten Register, Flags und Stack. EXIT beim Start, fehlender
Panelzeiger oder ein globaler Schalter ungleich exakt 1 führen zum Original.
Der globale Schalter ist getrennt von `SCRIPT_STATE.ARMED == 2` je Plugin.
Der Rahmen lädt den Original-Literalplatz dynamisch, statt einen früher
beobachteten Zeigerwert fest einzusetzen. Veränderte Literale sind nativ
mit gleichen Registern und Flags geprüft.

## Speicher, offline gemessen

Die gelesenen eigenen Abbilder enthalten von `0xC01A6000` bis `0xC01FFFF0`
368624 Byte FF. Kein Bereich von MFX 2 oder Startbild wird belegt.
Dies beweist eine freie Abbildfläche, noch keine dauerhafte Nichtnutzung am Gerät.

| Bereich | Lage | Größe |
|---|---|---:|
| VM und Haken | `0xC01A6000` bis `0xC01A85C4` | 9668 Byte |
| Runtime, Prüfpuffer, Ring | `0xC01AE000` bis `0xC01D65A0` | 165280 Byte |
| gemeinsamer Plugin-Pool | `0xC01D7000` bis `0xC01F7000` | 131072 Byte |
| Summe genutzter Bereiche | hergeleitet aus Buildgrößen | 306020 Byte |

Der Eintrag je Plugin hat jetzt 200 Byte, einschließlich `readySent`.
Kontrollkopf, Ereignisrecord und Phasen werden aus dem öffentlichen Vertrag
erzeugt. Initialisierung bleibt aufrufbar; der produktive Bootlader folgt später.

## Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `tools/emu/.venv/bin/python -m unittest tools/patch/test_script_hooks.py tools/patch/test_script_vm.py` | 29 bestanden |
| native VM gegen JS-Referenz | 506 Vergleiche bestanden |
| `E2_EMU_REQUIRED=1 E2_VSB=<eigene SYSTEM.VSB> E2_FLASH=<eigener Flash-Dump> node --test test/script-runtime.test.mjs` | 3 bestanden, nichts übersprungen |
| `E2_ARM_REQUIRED=1 npm test` | 363 bestanden, 59 ohne Firmware übersprungen, null Fehler |
| `check.py` mit Runtime, MFX 2, Startbild und dokumentierten Startspans | 37 Prüfungen bestanden |
| vollständiger bestehender MFX-Ablauf mit Pflichtdump | bestanden |
| vollständiger bestehender Startbildablauf mit Pflichtdump | 36 Schritte bestanden |

Der Firmwarefall prüft Panelargumente, 25 Hz, unscharfen Start, EXIT,
Division durch null, Zeitfehler mit fortgesetztem Folge-Plugin und weitere
Originalbedienung. Status wird über echte DIN-SysEx-Suche und RAM-Lesen
der Firmware abgerufen; Overflow, armed und Fehlercode werden im JS-Client
mit dem vorhandenen Protokollparser geprüft.

Die temporäre Emulator-VSB für diese Läufe hat SHA256
`22496ec358318ae7b0db79ded89a714b4f30646e905d5b5efba94566b561a4a1`.
Sie liegt außerhalb des Repos und ist keine freigegebene Gerätedatei.
Der öffentliche Builder liefert Patch-Version 1 mit eigenen Bytes,
Erwartungsprüfsummen und den tatsächlich beanspruchten Haken.

## Gefundene Ursachen und Korrekturen

Der erste Firmwarelauf stoppte beim zweiten kurzen Plugin-Rumpf. Beleg:
`poll_stop == true`, Zeit 2003500200 ns bei Grenze 2003500000 ns.
`Dev.call` hatte ein reguläres Timerpoll-Scheibenende als fehlende Rückkehr
behandelt. Der gemeinsame Testhelfer führt Aufrufe jetzt mit dem normalen
Emulatorlauf einschließlich IRQ bis zur Rückkehr aus. Kein VM-Ersatz und
kein Rückfall auf den alten Helfer; derselbe Firmwarefall ist danach grün.

Breite MFX- und Startbildtests waren zunächst ohne Flashdump rot. Isolierte
Vergleiche alter und neuer Helfer auf identischer Firmware ergaben dieselben
Fehler. Leerer Flash löst schon beim Originalboot zusätzliche Schreibvorgänge
aus und verwendet MIDI-Kanal 1; der MFX-Ablauf erwartet die Dumpkonfiguration
mit Kanal 10. Mit Pflichtdump bestehen die unveränderten Prüfungen.
Keine zusätzliche Sektorfreigabe und keine geänderten MFX-Assertions.

Die erste Exportprüfung lehnte ausschließlich neue Startzugriffe ab.
Aus dem Trace wurden acht begrenzte Spans von zusammen 188 Byte abgeleitet:
Hookwörter, Schalterprüfungen, Registerrückwege und zugehörige Literale.
Die eigentliche VM bleibt außerhalb dieser Ausnahmen. Mit diesen Spans
ist `check.py` vollständig grün.

MRS/MSR-Encodings wurden unabhängig mit vorhandenem
`clang -target armv5-none-eabi` geprüft sowie mit
nativen CPSR- und IRQ-Tests. Der gemeinsame Assembler blieb unverändert.
Die Statusregisteroperationen folgen dem
[Arm Assembler Guide](https://documentation-service.arm.com/static/5e9831ef9931941038dd07ba).

Basis aller Abschlussläufe: eigene `SYSTEM.VSB`, SHA256
`b0890899cbe5951d0709724c46d38350a35a6134a4a01d3a5bad63e51ac22ae7`.
Die Testfirmware ist eine andere Datei (SHA256 beginnt `163d1d8d`);
sie wurde nicht als Ersatz für einen fehlgeschlagenen Abschlusslauf verwendet.
