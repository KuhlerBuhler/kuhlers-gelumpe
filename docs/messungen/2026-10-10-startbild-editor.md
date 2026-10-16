# Startbild-Editor im Menü Global (Idee 35): gebaut und im Emulator geprüft

Stand 2026-10-10. **Seit dem 15.10. speichert der Editor auf die Karte statt in den Flash:** [Startbild auf der Karte](2026-10-15-startbild-karte.md); wo unten Flash `0x7F0000` steht, ist das der erste Stand. Alles im Emulator (`tools/emu/machine.py`, Unicorn 2.1.4)
und offline mit Capstone. Firmware: `SYSTEM.VSB` (Basis des Emulators) und
`SYSTEM-ringtest.VSB` (die Datei auf dem Gerät, Grundlage für die fertige
Kopie), Flash: eigener Dump vom 9.10. **Am Gerät nichts geprüft, kein
Gerätezugriff.** Entwurf und Adressen: [Startbild-Editor, Hintergrund](../hintergrund/startbild-editor.md).

Markierungen: **gemessen** (im Emulator ausgeführt und beobachtet),
**offline** (Code gelesen), **hergeleitet**, **offen**.

## Was gebaut ist

Ein Patch (`data/patches/splash-editor.json`, Format `gelumpe-patch` Version 1),
erzeugt von `tools/patch/splash_editor.py` mit dem kleinen ARM-Assembler
`tools/patch/arm.py`. Er trägt nur eigenen Code und fünf Wörter, nie
Firmware-Bytes: die vtable des Global-Bildschirms wird beim Anwenden aus der
eigenen VSB kopiert (Änderungsart `copy`, `src/patch.mjs`).

```bash
python3 tools/patch/splash_editor.py --vsb SYSTEM.VSB --out data/patches/splash-editor.json
node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch data/patches/splash-editor.json --out NEU.VSB
tools/emu/.venv/bin/python tools/emu/check.py --base SYSTEM.VSB --patched NEU.VSB \
  --allow-code 0x2aeac:4 --allow-code 0x2ad38:4 --allow-code 0x1a2200:496 [--flash dump.bin]
tools/emu/.venv/bin/python tools/emu/splash_cases.py run --base SYSTEM.VSB --patched NEU.VSB [--flash dump.bin]
```

Bedienung (Seiten ab 0 gezählt):

- Global, Seite 20 **SPLASH SCREEN** nach XY CALIBRATION. Die Seitenanzeige
  zeigt „/21“ (zwei Literale der Firmware).
- **MENU** (am Gerät als ENTER beschriftet) öffnet den Editor: das aktuelle
  Startbild, Pixel (0, 0) blinkt.
- **VALUE** bewegt den Cursor, Index `y * 128 + x` modulo 8192, also mit
  Zeilenumbruch und Umlauf. **MENU** kehrt den Pixel unter dem Cursor um.
  **WRITE** speichert. **EXIT** verlässt den Editor. Edit links und rechts
  werden im Editor ignoriert.
- **Start:** der Aufruf `0xC002AC38` (Startbild vor den Rettungswegen) ist ein
  `nop`; an `0xC002ADAC` (nach den Rettungswegen) läuft unser Code und
  zeichnet einmal das gespeicherte Bild, sonst das der VSB. Zur Anzeige ruft er
  nur `0xC0015DD0(DISPLAY_OUT, 2, 0)` und `(…, 3, 0)` (Merker setzen, senden).
  `0xC0015C78` ist der DSP-Boot (Reset und Upload von 271 008 Byte) und kommt
  im Startcode nicht vor: das DSP-Programm wird einmal geladen, vom frühen Pfad
  der Firmware (Reset bei 52,95 ms, Upload bei 56,1 ms), mit und ohne EXIT.
- **Notschalter:** EXIT beim Einschalten (Maske `0x2000` an
  `*(*0xC033E6F8 + 0x18)`) überspringt alles: der Startcode liest nichts und
  richtet nichts ein, und jeder ersetzte vtable-Slot springt zuerst ins
  Original.

Speicher (Abbild, `FF`-Bereich ab `0xC01A2100`): Startcode 496 Byte, Editor
1680 Byte, vtable-Kopie 72 Byte, Laufzeitzustand `0xC01A4000`, Puffer
`0xC01A4100` (Datensatz) und `0xC01A4600` (Bild in Bearbeitung). Flash: ein
Datensatz von 1036 Byte bei `0x7F0000` (Kennung `GLSP`, Version 1, Länge 1024,
Bild im Format von Bild 13, CRC-32 über alles davor).

## Belege

| Behauptung | Status | Befehl |
|---|---|---|
| Patch gleicht dem, was der Builder erzeugt | gemessen | `npm test` mit `E2_VSB` (Test „the assembler and the patch builder agree with the committed patch“) |
| Assembler erzeugt dieselben Wörter wie Capstone und wie die Firmware (jede zweite Anweisung im Code-Bereich, über 20000 Treffer, weniger als 1 % Abweichung) | gemessen | `python -m unittest discover -s tools/patch -p 'test_*.py'` mit `E2_VSB` |
| Patch ändert nur genannte Bytes, Kopie ist die echte Tabelle | gemessen | `test/splash-editor.test.mjs` |
| Alle Startwege bestehen mit dem Patch | gemessen | `check.py`, unten |
| Speicherfälle und Notschalter | gemessen | `check.py` / `splash_cases.py cases`, unten |
| Editor-Ablauf mit Neustart | gemessen | `splash_cases.py run`, unten |
| Notschalter-Bit 13 ist EXIT am Gerät | gemessen am Gerät | `docs/messungen/2026-10-10-rueckweg-geuebt.md`, Punkt 6 (`screen_check.py --held`) |
| Das DSP-Programm wird in jedem der 16 Läufe von `check.py` (alle Startwege) genau einmal geladen (Upload bei 68,7 ms im Original, bei 56,1 ms mit dem Patch), mit und ohne EXIT | gemessen | `check.py` Prüfung `dsp_boot_once`, `splash_cases.py cases` (Detail „DSP booted 1 time(s)“) |
| Der Startcode ruft `0xC0015C78`, `0xC0011A04`, `0xC0011A5C`, `0xC0011AB8` nicht | gemessen | `test/splash-editor.test.mjs` „the start code never calls the DSP boot“; ein Startcode mit zweitem DSP-Boot fällt im selben Test durch |
| Flash-Sektor `0x7F0000` hat keinen anderen Schreiber | hergeleitet | direkte Aufrufe in der Firmware, siehe Abschnitt 4 in `docs/hintergrund/startbild-editor.md` |

## Prüfung vor dem Export (`check.py`)

Gemessen, einmal gegen `SYSTEM.VSB` (29 von 29) und einmal gegen
`SYSTEM-ringtest.VSB` (29 von 29), jeweils mit dem Flash-Dump; zusammen mit dem
MFX-2-Umschalter und dem Blech-Startbild (`assets/blechy/splash.json`) auf
`SYSTEM-ringtest.VSB` 33 von 33:

- `dsp_boot_once`: das DSP-Programm wird in allen 16 Läufen genau einmal
  geladen.
- Kopf unverändert; Booten bis Bildschirm 1 mit Flash-Dump und mit leerem
  Flash; Update-Abfrage ohne Kennung `0x220000`; Panel-Update bei falscher
  Panel-Version; alle elf Startmodi; Notschalter.
- `start_phase` besteht nur mit den drei Ausnahmen des Patches (`startPhase` im
  Patch, jeweils mit Begründung): der Aufruf nach den Rettungswegen
  (`0x2aeac`), der gestrichene Aufruf davor (`0x2ad38`) und der Startcode
  selbst (`0x1a2200`, 496 Byte). Ohne `--allow-code` lehnt `check.py` den Patch
  ab (Test im Repo). Die Ausnahmen stehen im Ergebnis als
  `start_phase_exceptions`.
- Der Editorcode (`0x1a2600`) steht **nicht** auf der Liste: er läuft vor
  Bildschirm 1 nie.

### Speicherfälle beim Start (Pflicht)

Wird eines der Bilder gezeigt: 0,12 / 0,16 / 0,2 s Emulator-Zeit nach dem
Einschalten, danach muss Bildschirm 1 erreicht sein, ohne Assertion und ohne
dass der Patch den Flash verändert, und das DSP-Programm muss genau einmal
geladen worden sein.

| Fall | Datensatz in `0x7F0000` | Bild | Hauptbildschirm | Patch scharf |
|---|---|---|---|---|
| `empty` | alles `FF` | VSB | ja | ja |
| `valid` | gültig, anderes Bild | gespeichert | ja | ja |
| `bit_flipped` | ein Bit im Bild gekippt | VSB | ja | ja |
| `half_written` | `FF`, nur die ersten 512 Byte geschrieben | VSB | ja | ja |
| `exit_held` | gültig, EXIT gehalten | VSB | ja | nein |
| `wrong_id` | CRC passt, Kennung falsch | VSB | ja | ja |
| `wrong_version` | CRC passt, Version 2 | VSB | ja | ja |
| `wrong_length` | CRC passt, Länge 512 | VSB | ja | ja |
| `exit_held_menu` | gültig, EXIT gehalten | Global hat seine 20 Seiten, keine Seite 20, kein Editor | | nein |

**Gemessen:** Das Startbild kommt mit dem Patch bei 75 Emulator-ms statt bei
66 ms (Original). Dazwischen ist das Display leer, aber hell, weil das Licht
die Firmware schon bei 52,5 ms einschaltet (so gewollt, siehe
`docs/hintergrund/startbild-editor.md`, Abschnitt „Entwurf und Umsetzung“).

## Der Editor im Emulator (`splash_cases.py run`)

Gemessen, 36 von 36 Schritten, gegen `SYSTEM.VSB` und gegen
`SYSTEM-ringtest.VSB`; die Seiten 0 bis 19 werden Schritt für Schritt gegen die
unveränderte Firmware verglichen.

- Global öffnet auf Seite 0. Die Seiten 0 bis 19 gleichen unterhalb der
  Kopfzeile (Anzeige „n/20“ gegen „n/21“) Pixel für Pixel der unveränderten
  Firmware, und VALUE ändert dort dieselben Pixel wie dort, vor und zurück.
- MENU auf XY CALIBRATION öffnet weiter Bildschirm `0x20`; EXIT von dort geht
  wie im Original auf den Kopfbildschirm 8, MENU öffnet wieder Seite 19.
- Edit rechts auf Seite 19 öffnet Seite 20: Titel „SPLASH SCREEN“ und
  „press  [ Enter ]“ stehen im Titel-Widget, das Seitenbyte der Firmware
  (`0xC0691328`) bleibt 19 und wird nie 20 (die drei Tabellen zu je 20
  Einträgen würden sonst mit Index 20 gelesen). VALUE tut dort nichts; Edit
  links geht auf 19, Edit rechts auf Seite 0, Edit links auf Seite 0 auf
  Seite 20.
- MENU öffnet den Editor; das Display zeigt das Startbild der VSB Byte für
  Byte; Pixel (0, 0) blinkt (beide Werte gesehen). VALUE +5 setzt den Cursor
  auf 5, -6 von 0 aus auf 8191, `+1` und `+127` zusammen auf 128 (nächste Zeile).
- MENU kehrt genau ein Pixel um (Byte 3, Bit `0x80`), noch einmal MENU
  kehrt es zurück. Edit links und rechts, und andere Tasten (SEQUENCER) tun im
  Editor nichts.
- WRITE: Fenster „Working...“, danach der Datensatz bei `0x7F0000` mit
  gültiger CRC und dem bearbeiteten Bild. Geändert sind genau zwei Sektoren:
  `0x7F0000` und `0x230000` (die Globals, die die Firmware bei jedem WRITE in
  diesem Menü sowieso speichert; sie sind danach nur dann anders, wenn der Lauf
  zuvor einen Global-Wert verändert hat). Das bearbeitete Bild ist nach dem
  Fenster wieder auf dem Display.
- EXIT verlässt den Editor auf Seite 20, die Seite ist wieder wie vorher; EXIT
  noch einmal verlässt Global auf Bildschirm 8, MENU öffnet Global wieder auf
  Seite 19.
- Ein Bildschirmwechsel mitten im Editor (Aufruf von `0xC0083D28(1, 0)`) setzt
  den Editor zurück und stürzt nicht ab (keine Assertion); danach öffnet der
  Editor wieder mit dem Cursor auf 0.
- **Neustart** mit dem gespeicherten Datensatz: das Display zeigt bei allen drei
  Proben das bearbeitete Bild, Bildschirm 1 wird erreicht.

## Wie es funktioniert (hergeleitet aus dem Code und durch die Läufe bestätigt)

- Der Konstruktor von Bildschirm 9 lädt seine vtable aus dem Literal
  `0xC0064D3C`; das Wort zeigt auf unsere Kopie (18 Wörter aus der eigenen VSB,
  Slots 0, 1, 2, 3, 4, 5, 6, 10 ersetzt). Jeder ersetzte Slot prüft zuerst
  Magic und Notschalter und springt sonst mit unveränderten Argumenten ins
  Original (`ldr pc, [ORIG_VT + 4 n]`).
- Seite 20 wird nur von uns gezeichnet (Text-Widgets der Firmware, Titel aus
  eigenem String). Der Cursor ist ein eigenes Widget im Vektor des
  Bildschirms, dessen Zeichen-Slot alle sechs Takte den Pixel umschaltet; die
  Slots „Löschen“ sind leer, damit der Basis-Destruktor es unbeschadet abbauen
  kann. Die Destruktor-Slots setzen den Editor zurück.
- Das Bild des Editors wird an Bild 13 vorbei gezeichnet: Deskriptor-Zeiger
  `0xC00C5A54` kurz auf den Arbeitspuffer, `0xC003F650`, zurück. Der Zeiger
  zeigt nach dem Start oder nach WRITE dauerhaft auf den gespeicherten Datensatz
  (Puffer `0xC01A4100 + 8`), sonst auf das Bild der VSB.
- Nach WRITE legt die Firmware das Fenster „Working...“ über das Bild. Der
  Editor wartet, bis das Fenster erschienen und wieder weg ist, und zeichnet
  dann das Bild neu (`S_REDRAW` 1 wartet auf das Fenster, 2 es steht). Das
  Fenster erscheint je nach Phase gegenüber dem Takt des Bildschirm-Verwalters
  erst einen oder mehrere Takte nach dem Tastendruck (gemessen); zeichnete der
  Editor vorher, stünde nach dem Fenster die Seite 20 statt des Bildes. Kommt
  das Fenster nicht, zeichnet der Editor nach 40 Takten.

## Grenzen und Risiken vor einem Gerätetest

- **Startcode (hergeleitet):** läuft bei jedem normalen Start nach den
  Rettungswegen. Ein Fehler darin, der nur am Gerät vorkommt, würde den
  Hauptbildschirm verhindern. Rettung: EXIT beim Einschalten, aber dass EXIT am
  Gerät Bit 13 ist, ist am Gerät gemessen (`2026-10-10-rueckweg-geuebt.md`).
  Das ist die gewollte Ausnahme zu Regel 1 in `docs/patcher.md`.
- **Kein Startbild vor den Rettungswegen:** das Display ist bis rund 75 ms
  leer; am Gerät nicht gemessen. Ein Gerät, das vor dem Hook hängt, zeigt nie
  ein Bild.
- **Flash-Lesen im Emulator:** der Emulator ersetzt den Treiber-Lesezugriff
  `0xC001E4AC` durch eine Kopie; ob der SPI-Treiber am Gerät an `0xC002ADAC`
  schon bereit ist, ist nicht gemessen (die Firmware liest dort selbst
  bereits die Kennung und die Globals über denselben Weg, hergeleitet).
- **Flash-Ort `0x7F0000`:** kein bekannter Schreiber, hergeleitet aus direkten
  Aufrufen. Ein Löschen ganzer Blöcke durch Bootloader oder Korgs Update ist
  nicht ausgeschlossen; dann greift der Rückfall auf das VSB-Bild.
- **Löschdauer:** 4-KiB-Löschen und 16 Seiten halten die Sperre
  `0xC0000D80(2)`; Audio- und MIDI-Aussetzer beim WRITE sind möglich (macht
  die Firmware beim Speichern der Globals auch). Dauer am Gerät nicht
  gemessen.
- **Globals beim WRITE:** die Firmware speichert bei WRITE im Menü die
  Globals mit; wer vorher Werte auf Seiten 0 bis 19 geändert hat, speichert sie
  damit wie im Original.
- **Batterie-Symbol:** die Hintergrund-Recherche maß auf Bildschirm 9 ein Symbol der
  Statusleiste, das 14 Byte oben im Bild regelmäßig neu malt. Im Editorlauf
  zeigte das Display nach MENU das Startbild Byte für Byte (keine Abweichung);
  ob das Symbol am Gerät im Editor das Bild oben stört, ist offen. Das Bild im
  Arbeitspuffer und der gespeicherte Datensatz sind davon nicht betroffen.
- **Offen:** Speicherort am Gerät, Flash-Typ, Verhalten bei Korgs Update
  (ob `0x7F` berührt wird), andere Leser von Bild 13 nach dem Start, ob die
  zweite Zeichenebene im Editor angehalten werden darf.
- **Hacktribe-Stand:** alle Adressen gelten für diese VSB (2.02 mit Hacktribe);
  der Patch verweigert jede andere Basis über die Hashes der ersetzten Bytes.
