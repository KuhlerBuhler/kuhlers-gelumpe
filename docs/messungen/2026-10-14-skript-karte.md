# Plugin-Datei von der Karte: Lader und Dateiformat

Stand 2026-10-14. Kein Gerätezugriff. Plugins
liegen nur auf der virtuellen Karte im Emulator und im RAM, nie in der VSB.
Alles hier ist im Emulator gemessen oder aus dem Code hergeleitet (markiert).

## Umsetzung

- **Format** (`data/script/contract.mjs`: `ARCHIVE`, `SOURCE_TRAILER`,
  `CARD_STATUS`): `e2sPlugin.all` mit 16 Byte Kopf (`GSAL`, Version 1, Anzahl,
  Gesamtgröße, CRC-32 ab Byte 16), danach die Format-2-Blöcke hintereinander.
  `.blech` ist ein Block mit Quelltext-Anhang (`GSRC`, Länge, UTF-8).
  Öffentlich und im Browser lauffähig: `src/script/archive.mjs`
  (`packAll`, `parseAll`, `packBlech`, `parseBlech`), 7 Tests in
  `test/script-archive.test.mjs`.
- **Lader** (`tools/patch/script_card.s`, eingebunden von `script_hooks.py`):
  Haken `0xC0038D68` (der Befehl `add r0, sp, #4` direkt nach dem Laden der
  `e2sSample.all`, Rücksprung `0xC0038D6C`). Reihenfolge: Panel und EXIT
  prüfen, `f_open` auf `SD:KORG/blechtribe/Plugin/e2sPlugin.all`, Kopf lesen
  und prüfen, Laufzeit initialisieren, je Block den Kopf (52 Byte) und den Rest
  in den Puffer `0xC01F8000` lesen, CRC mitrechnen, `script_load_block`
  aufrufen; am Ende Größe und CRC der Datei gegen den Kopf prüfen, die Datei
  schließen, den `start`-Rumpf jedes geladenen Blocks ausführen, erst dann
  `ARMED = 1`. Jeder Fehler vorher setzt die Laufzeit zurück und lässt sie
  unscharf. Ergebnis im Kontrollblock: `cardStatus`, `cardLoaded`,
  `cardRejected`, `cardFirstError`.
- **Speicher:** Arbeitsbereich des Laders (FIL-Objekt mit 640 Byte, 64 Byte
  Zustand) bei `0xC01F7000`, direkt hinter dem Plugin-Pool, vor dem
  Blockpuffer bei `0xC01F8000` (32752 Byte, ein Block darf nicht größer sein).
  `BuiltHooks.apply` verlangt für `0xC01F7000` bis `0xC01FFFF0` den FF-Zustand
  der Basis. Der Bereich ist in den gelesenen eigenen Abbildern FF (siehe
  `2026-10-14-skript-haken.md`).
- **Haken-Register:** Kette `start` hat die neue Stufe `after-sample-load`
  (`data/hooks.mjs`); der Haken wird als `before`, nicht verschluckend,
  gemeldet. Startspannen für `check.py`: Haken, Rückweg und Lader, zusammen
  11 Spannen.

## Prüfungen

| Prüfung | Ergebnis (gemessen) |
|---|---|
| `node --test test/script-archive.test.mjs test/script-contract.test.mjs` | 22 bestanden |
| `python -m unittest tools.patch.test_script_card` (Lader über ein vorgetäuschtes FatFs, ohne Firmware) | 12 bestanden |
| Firmware im Emulator, echtes FatFs und virtuelle Karte (`script_cases.py`, 16 neue Prüfungen `karte-*`) | alle bestanden |
| `check.py` auf Startbild + MFX 2 + Laufzeit mit Lader | 37 von 37 |
| `E2_ARM_REQUIRED=1 npm test` | 448 Tests, 407 bestanden, 41 ohne Firmware übersprungen, 0 Fehler |
| `tools/device/fatfs_probe.py --emu` | alle Prüfungen bestanden, siehe `docs/geraetetests/karte.md` |

Gesamtlauf der Firmwaretests (`E2_EMU_REQUIRED=1`, neun Dateien): 66 von 67
bestanden. Der eine Fehler war `emulator-flash` mit Timeout nach 161 s, während
auf dem Rechner eine Last von 36 bis 66 lag (andere Läufe liefen parallel,
hergeleitet); allein läuft derselbe Test in 32 s und besteht.

Die Firmware-Prüfungen im Einzelnen: leere Karte setzt Status 2, lässt
`ARMED` auf `0xFFFFFFFF` und der Bildschirm, die Pattern, das Display und die
LEDs gleichen einem Start der Originalfirmware mit derselben Karte. Eine vom
JS-Packer erzeugte Datei mit zwei Blöcken lädt (Status 1, 2 geladen, 0
abgelehnt), die Laufzeit ist scharf, beide `start`-Rümpfe sind gelaufen, der
`ready`-Handler setzt die LED 0 auf 0, TAP schaltet die LED 0 auf 255 und
zurück auf 0, jeweils ein Paket, die Firmware bleibt bedienbar (MENU öffnet
ein Menü). Ein Block mit falscher Prüfsumme in einer sonst gültigen Datei
wird allein abgelehnt (Status 1, 1 geladen, 1 abgelehnt). Falsche
Dateiprüfsumme (Status 4), falsche Kennung (Status 3) und halbierte Datei
(Status 5) lassen die Laufzeit unscharf und das Gerät wie das Original. EXIT
beim Einschalten ergibt Status 7, `ARMED` bleibt `0xFFFFFFFF`, und die Karte
wird weniger gelesen (7 gegen 12 Sektoren).

Dauer des Laders im Emulator für eine Datei mit zwei Blöcken: 16,8 ms
Emulatorzeit vom Haken bis zum Rücksprung (gemessen, DSP-Attrappe, keine
Gerätezeit; der Emulator ist 1,3 bis 1,6 mal schneller als das Gerät, siehe
`2026-10-12-vm-tempo.md`, also geschätzt 25 ms am Gerät für diese Datei).

## Grenzen und Offenes

- Am Gerät ist der Lader nicht geprüft, auch das Lesen und Schreiben über die
  FatFs-Funktionen nicht. Die Schrittliste dafür steht in
  `docs/geraetetests/karte.md`.
- Der Stack des Laders (rund 150 Byte eigener Bedarf plus FatFs) ist am Gerät
  nicht gemessen; die Firmware nutzt an derselben Stelle `0x844` Byte
  (hergeleitet aus der Recherche zur virtuellen SD).
- Die Prüfung mit einer echten `e2sSample.all` auf der Karte läuft nicht im
  Test, weil deren Format nicht bekannt ist und keine Korg-Daten im Repository
  liegen dürfen. Der Haken liegt an derselben Stelle, die der frühere
  Importprototyp mit einer echten Datei gemessen hat
  ([`../hintergrund/virtuelle-sd.md`](../hintergrund/virtuelle-sd.md)).
- Schreiben der `e2sPlugin.all` am Gerät ("EXPORT ALL") und die
  dauerhaften Werte (`korg.store`) brauchen den Schreibdienst. Er wird erst gebaut,
  wenn ein Verbraucher ihn braucht (`2026-10-14-skript-speicher.md`, `2026-10-14-blech-menue.md`).
- Die Bestätigung eines fremden Plugins beim ersten Laden kommt mit
  dem Bildschirm `0x2D` (`2026-10-14-blech-menue.md`). Bis dahin lädt der Lader jede Datei ohne
  Rückfrage; die Laufzeit ist aber nur im BLECH-Patch, der noch in keiner
  Gerätedatei ist.
