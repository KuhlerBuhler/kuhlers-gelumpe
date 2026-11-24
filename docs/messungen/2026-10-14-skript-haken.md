# Plugin-Haken: Eingangsfilter und Rahmenhaken

Kein Gerätezugriff. Geprüft sind native Haken ohne Firmware und in der gebooteten Firmware ([Emulator](../glossary.md#emulator)).
[Plugins](../glossary.md#plugin) wurden dabei ausschließlich ins Emulator-RAM geladen, nie in die VSB. `korg.led` und der Kartenlader:
[`2026-10-14-skript-led.md`](2026-10-14-skript-led.md), [`2026-10-14-skript-karte.md`](2026-10-14-skript-karte.md).

## Ergebnis

Eingangsfilter `0xC002837C` (Kette `input-filter`, `data/hooks.mjs`): nur normalisierte Ereignisse in einen Ring mit
64 Plätzen, keine VM-Ausführung. Aufeinanderfolgende Werte desselben Reglers
werden zusammengefasst; volle Ringe verwerfen neue Ereignisse und zählen sie.
Vorabflags, unbekannte Paneltypen sowie Ausschalt- und Netzteilmeldungen gehen
unverändert weiter. Die Capturemaske wird vorher gesetzt; EXIT wird niemals
verschluckt.

Rahmenhaken `0xC00836FC` (Kette `frame-hook`): nur UiTask, READY je Plugin nach Hauptbildschirm,
danach eine Momentaufnahme der Warteschlange und FRAME. Alle Handler teilen
denselben Timer-3-Start und die 5-ms-Grenze. Eintritt, Ende und lange Läufe
alle 256 Operationen prüfen die Zeit. Exakt 5 ms sind erlaubt. Bei TIME
wird nur der Verursacher abgeschaltet; der Cursor setzt die restliche Folge
im nächsten Rahmen fort. Ein laufender Hostaufruf ist nicht unterbrechbar.

Beide Haken erhalten Register, Flags und Stack. EXIT beim Start, fehlender
Panelzeiger oder ein globaler Schalter ungleich exakt 1 führen zum Original
([Notschalter](../glossary.md#notschalter)). Der globale Schalter ist getrennt von `SCRIPT_STATE.ARMED == 2` je Plugin.
Der Rahmen lädt den Original-Literalplatz dynamisch, statt einen früher
beobachteten Zeigerwert fest einzusetzen. Veränderte Literale sind nativ
mit gleichen Registern und Flags geprüft.

## Speicher

Der gemeinsame Plugin-Pool ist 131072 Byte groß und liegt ab `0xC01D7000` (`test/patch-ram.test.mjs`). Alle Bereiche
der Laufzeit (Code, Zustand, Ring, Menü, Kartenlader und weitere) deklariert `tools/patch/script_hooks.py` als RAM-Bereiche des
Patches `script-runtime`; sie liegen in einem im Abbild freien Block (`FF`), den kein anderer Patch belegt. Das beweist eine
freie Abbildfläche, noch keine dauerhafte Nichtnutzung am Gerät. Die Belegung insgesamt:
[Speicherbereiche](../speicherbereiche.md).

## Prüfungen

- `tools/patch/test_script_hooks.py` und `tools/patch/test_script_vm.py` (native Haken und VM) und
  `test/script-runtime.test.mjs` (mit `E2_EMU_REQUIRED=1`, `E2_VSB` und `E2_FLASH`) prüfen Panelargumente, 25 Hz, unscharfen
  Start, EXIT, Division durch null, Zeitfehler mit fortgesetztem Folge-Plugin und weitere Originalbedienung. Der Status wird über
  echte DIN-SysEx-Suche und RAM-Lesen der Firmware abgerufen; Overflow, armed und Fehlercode werden im JS-Client mit dem
  vorhandenen Protokollparser geprüft.
- `check.py` mit Laufzeit, MFX 2, Startbild und den dokumentierten Startspans, dazu die bestehenden MFX- und Startbildabläufe,
  jeweils mit Pflichtdump.

## Gefundene Ursachen

- **Testhelfer:** Der erste Firmwarelauf stoppte beim zweiten kurzen Plugin-Rumpf, weil `Dev.call` ein reguläres
  Timerpoll-Scheibenende als fehlende Rückkehr behandelte. Der gemeinsame Testhelfer führt Aufrufe jetzt mit dem normalen
  Emulatorlauf einschließlich IRQ bis zur Rückkehr aus.
- **Flash-Dump Pflicht:** Mit leerem Flash lösen schon der Originalboot zusätzliche Schreibvorgänge aus und der MIDI-Kanal ist 1;
  der MFX-Ablauf erwartet die Dumpkonfiguration mit Kanal 10. Mit Pflichtdump bestehen die Prüfungen unverändert.
- **Startspans:** Die Exportprüfung lehnt neue Startzugriffe ab. Aus dem Trace wurden begrenzte Spans abgeleitet (Hookwörter,
  Schalterprüfungen, Registerrückwege und zugehörige Literale); die eigentliche VM bleibt außerhalb dieser Ausnahmen.
- **MRS und MSR:** die Encodings wurden unabhängig mit `clang -target armv5-none-eabi` und mit nativen CPSR- und IRQ-Tests geprüft.
