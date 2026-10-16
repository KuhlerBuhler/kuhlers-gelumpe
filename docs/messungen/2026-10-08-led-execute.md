# LEDs selbst setzen: Execute, Caches, RGB

Stand 2026-10-08. Eigenes Gerät, nur RAM, mit Rücksicherung. Gemessen im
Emulator (`tools/emu/machine.py`) und am Gerät über die emulierte DIN-MIDI
(SysEx-Weg der Firmware). Skript: `tools/device/led_show.py`. Keine
Firmware-Bytes im Repo, nur Adressen und Prüfsummen.

## Warum Execute nötig ist

- **Gemessen:** Die Firmware hält je LED einen Sollwert in einer Tabelle
  (8 Byte pro LED ab Panel-Objekt + `0x4c`). Nur diese Tabelle im RAM zu
  beschreiben leuchtet nichts: die Firmware schickt eine LED erst, wenn ihr
  eigener Code die Setz-Funktion aufruft, und überschreibt fremde Werte beim
  nächsten Moduswechsel.
- **Gemessen:** Deshalb ruft man die Setz-Funktion der Firmware selbst auf.
  Von außen geht das nur über Hacktribes Execute-Befehl (`0x57`,
  `docs/messungen/2026-10-08-dsp-audiopfade.md`), der an eine übermittelte
  Adresse springt.

## Weg

- **Gemessen:** Panel-Objekt-Zeiger bei `0xC033E6FC`. Die LED-Funktion
  `0xC0028600(objekt, index, helligkeit)` baut die Panel-Nachricht
  `00 index helligkeit` und reiht sie über `0xC00285C0` in die Sendequeue
  `0xC0024BF4` ein.
- **Gemessen:** Ein kleiner Stub (60 Byte) geht nach `0xC1000000`, dem
  Arbeitsbereich, den Hacktribe selbst für hochgeladenen Code nutzt
  (`docs/speicherbereiche.md`). Er liest `*0xC033E6FC` und ruft die
  LED-Funktion für jedes Paar (index, helligkeit) aus einer angehängten
  Liste auf, bis `0xFF` sie beendet.
- **Gemessen:** Ablauf im Skript: RAM-Lesen prüft per SHA-256, dass
  `0xC0028600`, `0xC00285C0`, `0xC00016A4`, `0xC0170624` und `0xC0024BF4`
  dem vermessenen Build entsprechen, und dass das Panel-Objekt bereit ist
  (Busy-Byte + `4` = 0). Weicht etwas ab, bricht es vor jedem Schreiben ab.
  Dann Stub-Adresse sichern, I-Cache leeren, Stub schreiben und zurücklesen,
  per Execute starten, zum Schluss die Originalbytes zurückschreiben.
- **Gemessen am Gerät (2026-10-08):** Prüfungen bestanden, Panel-Objekt bei
  derselben Adresse wie im Emulator, Muster leuchtet (Pads abwechselnd rot
  und blau, PLAY/REC/STOP), keine Assertion, Gerät antwortet danach weiter
  auf Kanal 9. Erster Beleg, dass Execute am echten Gerät läuft.

## Caches

- **Gemessen offline (Flash-Dump 2026-10-09):** Der Bootloader schaltet MMU,
  Daten-Cache, Write-Buffer und I-Cache ein (Steuerregister `0x107D` bei Flash
  `0x54F0`); `0xC0000000` bis `0xC3FFFFFF` sind cachebar und
  zurückschreibend, `0xC4000000` bis `0xC7FFFFFF` der nicht gecachte Alias.
  Einzelheiten in [vm-tempo](2026-10-12-vm-tempo.md#gerätelauf-2026-10-13-execute-ohne-antwort).
- **Gemessen am Gerät:** Die kleinen LED-Stubs laufen trotzdem, obwohl die
  Skripte die Bytes vorher lesen. Warum, ist nicht geklärt.
- Vor dem Start leert das Skript den Befehls-Cache über die firmware-eigene
  Routine `0xC00016A4` (per Execute, ohne eigenen Code); sie leert den
  Daten-Cache nicht.

## Farben

- **Gemessen:** Die 16 Pads haben je zwei LEDs, rot (`0x2c + 2n`) und blau
  (`0x2d + 2n`). Ein Pad kann rot, blau oder beides (wirkt violett) zeigen,
  kein Grün. Namen aus dem Werkstatt-Test der Firmware (`Pad_N_RED`,
  `Pad_N_BLUE`).
- **Gemessen:** Echtes RGB haben nur vier LEDs, `LED_RGB_0` bis `3`, mit je
  einem roten, grünen und blauen Element: `0x52`/`0x53`/`0x54`,
  `0x55`/`0x56`/`0x57`, `0x4c`/`0x4d`/`0x4e`, `0x4f`/`0x50`/`0x51`. Das sind
  die unteren Lichter, die zwischen Rot, Grün, Blau und Weiß wechseln.
- **Gemessen:** Diese vier setzt die Firmware 25-mal pro Sekunde neu
  (`0xC0088380`, der Pegel/Velocity-Meter). Ein per Execute gesetzter Wert
  wird darum binnen rund 50 ms überschrieben; er bleibt nicht stehen wie bei
  Pads und Tasten-LEDs. Um eine Farbe zu halten, müsste man die Quelle des
  Meters anfassen; das ist offen.
