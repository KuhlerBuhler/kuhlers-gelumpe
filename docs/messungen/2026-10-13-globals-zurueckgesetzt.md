# Globals auf Werkseinstellung zurückgefallen: Ursache gesucht

Stand 2026-10-13. Emulator (`tools/emu/machine.py` mit dem Flash-Dump vom 9.10., virtuelle SD-Karte
für SOFTWARE UPDATE) und Firmware offline gelesen. Am Gerät nichts getan, außer den Messungen, die
unten als "am Gerät" markiert sind. Markierungen: **gemessen** (Emulator oder
Gerät), **offline** (Code gelesen), **hergeleitet**, **offen**.

## Befund am Gerät

- **Gemessen:** Der Globals-Block im Flash bei `0x230000` ist heute Byte für Byte gleich der
  Vorgabetabelle der Firmware bei `0xC00CFE58` (VSB-Offset `0xCFF58`, in allen vier geprüften VSB
  gleich: eigene Testfirmware, MFX-2-Variante, Startbild-Variante und `SYSTEM.VSB`; SHA-256 beginnt `dddd58cb`).
- **Gemessen:** Im Dump vom 9.10. wich der Block in fünf Bytes ab: `0x14` Audio In Thru (1),
  `0x1f` (1), `0x20` Batterietyp (1), `0x25` Stromsparen (1), `0x29` globaler MIDI-Kanal (9 = Kanal 10).
  Heute alle 0. Der Rest des Sektors (`0x230100` bis `0x230FFF`) ist weiter `FF`.

## Was Offset 0x1f ist

- **Gemessen im Emulator:** `0x1f` ist **CHAIN MODE**, Global-Menü Seite **19/20** (Seitenindex 18),
  Werte Off = 0, On = 1. Messung: Global öffnen, auf jeder Seite VALUE drehen, das lebende
  Globals-Objekt (`*0xC033E6A0 + 4`) vor und nach vergleichen.
- **Gemessen am Gerät (13.10.):** Chain Mode wurde am Gerät im Global-Menü eingeschaltet,
  ohne WRITE. Die Anfrage `0x0E` lieferte den RAM-Block, der sich vom Flash nur in `0x1f` unterschied
  (0 zu 1). Das stimmt mit der Zuordnung überein.

Alle Seiten, gemessen im Emulator (Seitenindex ab 0, Anzeige "n/20" ist Index + 1):

| Seite | Offset | Seite | Offset | Seite | Offset |
|---:|---|---:|---|---:|---|
| 0 | `0x1d` | 7 | `0x12` | 14 | `0x20` Battery Type |
| 1 | `0x1b` | 8 | `0x10` | 15 | `0x21` |
| 2 | `0x28` | 9 | `0x24` | 16 | `0x25` Power Save Mode |
| 3 | `0x29` Global MIDI Ch. | 10 | `0x1c` | 17 | `0x13` |
| 4 | `0x2b` | 11 | `0x26` | 18 | `0x1f` **Chain Mode** |
| 5 | `0x2a` | 12 | `0x1e` | 19 | keine Änderung am Block |
| 6 | `0x11` | 13 | `0x14` Audio In Thru | | |

`data/map/global.mjs` kennt `0x1f` noch nicht (und `0x21` steht als Auto Power Off drin, passt).
Eintrag dafür ist ein Vorschlag, nicht gemacht: Evidenz `measure:2026-10-13/globals-zurueckgesetzt`
wäre diese Datei.

## Wie die Firmware lädt und speichert

- **Offline:** Laden beim Start in `0xC004BE8C` (aufgerufen aus `0xC002ADD8`, und nach einem
  USER.VSB-Update aus `0xC003B484`): `0x100` Byte aus Flash-Block `0x23` (`0x230000`) in den Puffer
  `0xC08A2940`, Prüfung `0xC004718C`. Die Prüfung ist **nur**: Wort bei `+0xFC` gleich `GLED`
  (`0x44454C47`). Keine Version, keine Prüfsumme, kein Firmware-Stand. Schlägt Lesen oder Prüfung
  fehl, kopiert `0xC004BEE0` die Vorgabe von `0xC00CFE58` in den Puffer. Die Vorgabetabelle wird
  nur dort gelesen (einziges Literal darauf, `0xC004BF18`).
- **Offline:** Speichern `0xC004C1B4(obj, quelle)`: Quelle in den Puffer, dann Flash `0x230000`.
  Aufrufer: Ausschalten (`0xC0038B4C`, schreibt das lebende Objekt), WRITE auf Global (`0xC00317C4`,
  `0xC003182C`), SysEx `0x51` (`0xC0031204`) und Import einer Datei (`0xC002E5F8`, Import All Pattern:
  der Block hinter den ersten `0x100` Byte der `.e2sallpat`, jede Prüfung `GLED` vorher).
  Der Speicher schreibt also immer, was gerade im RAM steht: fällt das Laden auf die Vorgabe zurück,
  macht das nächste Ausschalten oder WRITE die Vorgabe dauerhaft.
- **Gemessen im Emulator:** Ausschalten schreibt den Globals-Sektor neu (1 Löschen, 16 Seiten);
  stand im RAM der Block vom 9.10., ist der Flash danach gleich.

## Frage 1: Update oder erster Start einer neu geflashten VSB

- **Gemessen im Emulator:** SOFTWARE UPDATE mit virtueller Karte (`KORG/hacktribe/System/SYSTEM.VSB`,
  Netzteil eingesteckt, DATA UTILITY 14/14, Anzeige "Now 2.02, Next 2.02", dreimal MENU): schreibt
  genau `0x020000` bis `0x220000` (2 MiB, Block 2). `0x230000` wird nicht gelöscht und nicht programmiert.
  Drei Strecken, jede mit anschließendem Start der neuen VSB und Ausschalten:
  Testfirmware nach Startbild-Variante, Startbild-Variante nach Testfirmware, Testfirmware nach
  MFX-2-Variante.
  Jedes Mal: Globals im Flash unverändert, RAM beim ersten Start der neuen VSB gleich dem Block vom
  9.10., nach dem Ausschalten Flash weiter gleich, keine Assertion.
- **Gemessen im Emulator:** Auf dem Bildschirm "OK. Please Reboot." (Bildschirm 30) reagiert die
  Ein/Aus-Taste im Emulator nicht (12 s gehalten). Es gibt dort also keinen Speichervorgang beim
  Ausschalten. **Offen:** ob das am Gerät auch so ist.
- **Offline:** Die Update-Wege schreiben Block 0 und 2 (Firmware), `0x22` (USER.VSB, danach lädt
  `0xC003B484` die Globals neu aus dem Flash), `0x75` (SLICE), `0x80`. Keiner davon liegt auf `0x23`.
  Im Emulator nicht ausgeführt: USER.VSB, SLICE.
- **Ergebnis:** Weder die Prüfung noch das Update hängen an der Firmware-Version. Ein Update oder
  der erste Start einer anderen VSB lässt die Globals-Prüfung im Emulator **nicht** scheitern.

## Frage 2: MFX-2-Patch (WRITE-Pfad)

- **Gemessen im Emulator:** die MFX-2-Variante mit Blech-Startbild mit dem Flash vom 9.10.: TOUCH SCALE
  (MFX 2), Seite MFX TYPE, VALUE, WRITE, WRITE, Patternwechsel, MASTER FX, Ausschalten. Flash-Zugriffe
  (jede Löschung und jeder Seitenprogrammierbefehl mitgeschrieben):
  - WRITE: Löschen und Schreiben von `0x7E8000` (unsere Tabelle) und `0x240000` bis `0x243000`
    (das Pattern). Sonst nichts. Der Eintrag bei `0x7E8000` ist danach gültig.
  - Patternwechsel, Moduswechsel: keine Flash-Zugriffe.
  - Ausschalten: nur `0x230000`, mit dem RAM-Inhalt; Globals danach gleich dem Block vom 9.10.
- **Offline:** Der Patch hält `STATE` und `RECBUF` bei `0xC01A5C00` und `0xC01A5D00` (freier Bereich
  im Abbild), der Globals-Puffer liegt bei `0xC08A2940`: keine Überlappung. Er ruft `0xC0029AB8` nur
  mit `0x7E8000`.
- **Ergebnis:** Der Patch berührt den Globals-Sektor nicht und speichert keine Globals. Nichts an
  `tools/patch/mfx_switch.py` oder `tools/emu/mfx_cases.py` zu ändern, kein Regressionsfall nötig.

## Frage 3: Was sonst die Vorgabe schreibt

- **Gemessen im Emulator, der Mechanismus:** Flash mit dem Dump vom 9.10., dann nur der Globals-Sektor
  verändert, Start, Ausschalten:

  | Zustand von `0x230000` | RAM nach Start | Flash nach Ausschalten |
  |---|---|---|
  | unverändert | Block vom 9.10. | gleich |
  | Sektor gelöscht (`FF`) | Vorgabe | Vorgabe |
  | nur `GLED` bei `+0xFC` zerstört | Vorgabe | Vorgabe |
  | `0x100` Byte genullt | Vorgabe | Vorgabe |

  Genau der heutige Befund entsteht also, wenn beim Start der Block nicht gelesen oder nicht als
  gültig erkannt wird und danach einmal ausgeschaltet oder WRITE gedrückt wird.
- **Gemessen im Emulator, FACTORY RESET** (DATA UTILITY 13/14, zweimal MENU): schreibt `0x230000`,
  `0x240000` bis `0x628000` (alle Patterns) und `0x6B0000` bis `0x750000`. Die Globals danach sind
  **nicht** die Vorgabetabelle (z. B. `0x20` Batterietyp 1, `0x1b` 1, `0x1e` `0x20`, `0x26` 2), und
  alle Patterns sind weg. Heutiger Befund (Vorgabetabelle, Patterns vermutlich da) ist also kein
  FACTORY RESET. **Gemessen:** FACTORY RESET steht in der Liste direkt vor SOFTWARE UPDATE.
- **Offline:** Import einer `.e2sallpat` setzt die Globals aus deren Block (offline gelesen, nicht
  im Emulator ausgeführt). Die eigenen Pattern-Sicherungen: die Werks-Sicherung
  (`electribe_sampler_factory_allpattern`) trägt `0x14/0x1f/0x20/0x25/0x29 = 0` aber sonst abweichende
  Werte (nicht die Vorgabetabelle, nicht der heutige Block), die übrigen Sicherungen tragen
  `0x1f=1, 0x20=1, 0x25=1, 0x29=9`.
  Keine der Dateien gleicht dem heutigen Block, ein Import ist als Ursache damit unwahrscheinlich.
- **Gemessen am Gerät (13.10.):** Das Format des Global-Dumps (`0x51`, Anfrage `0x0E`)
  ist derselbe 256-Byte-Block wie Flash `0x230000`. Den Block vom 9.10. als `0x51` gesendet:
  quittiert mit `0x23`, Flash `0x230000` sofort geschrieben, Rücklesen gleich dem Block vom 9.10.
  **außer** `0x29` (globaler MIDI-Kanal), der 0 bleibt: der Dump setzt den Kanal nicht, er wird von Hand
  eingestellt. `0x51` speichert also sofort, ohne WRITE.
- **Offline:** Die Editor-Seite und `tools/device/*` senden nie einen Global-Dump an ein Gerät
  (`globalDump` in `src/protocol.mjs` nur als Baustein und in Tests); `vm_bench.py` schreibt nur auf
  `0xC1000000`.

## Ursache

**Offen.** Im Emulator löst weder Korgs Update noch der erste Start einer anderen VSB noch unser
MFX-2-Patch den Rückfall aus. Der einzige Weg zur Vorgabetabelle, der zum heutigen Befund passt,
ist: Beim Start ist der Globals-Block nicht lesbar oder ohne `GLED`. Was das am Gerät auslöst, ist
nicht gemessen. Hergeleitet, nicht gemessen:

1. Strom- oder Absturz während des Speicherns der Globals (Ausschalten oder WRITE auf Global):
   der Sektor wird erst gelöscht und dann neu programmiert, dazwischen ist er leer. Wäre die Stromzufuhr
   oder die Software in dieser Lücke abgebrochen, fällt der nächste Start auf die Vorgabe zurück, und
   das nächste Ausschalten macht sie dauerhaft. Das passt auch dazu, dass nach einem Update
   "OK. Please Reboot." im Emulator kein Ausschalten annimmt: dort wird nur hart abgeschaltet, das
   schreibt im Emulator nichts. Ob das Gerät das auch so macht, ist offen.
2. Ein hängendes Gerät durch ein Skript mit `execute` und anschließendes hartes Abschalten
   (Kabel, Batterie): wäre nur dann ursächlich, wenn es in der Lücke aus Punkt 1 passiert.

Nicht verifizierbar offline. Ein Hinweis am Gerät: den Flash ab `0x230000` lesen (nur lesen) und
prüfen, ob `0x230100` bis `0x230FFF` noch `FF` sind und `0x7E8000` (MFX 2) und `0x7F0000` einen
gültigen Datensatz tragen. Dann ist nur der Globals-Sektor betroffen gewesen.

## Vermeiden

- Vor jedem Update oder Test mit Skripten die Globals sichern: `0x0E` anfragen und den Block in eine
  Datei legen (gleiches Format wie Flash `0x230000`), nach dem Update mit einer neuen Anfrage vergleichen.
- Nach einer Abweichung zuerst im Global-Menü nachsehen und **nicht** ausschalten oder WRITE drücken,
  solange das RAM nicht stimmt: Ausschalten und WRITE speichern, was im RAM steht.
- Wiederherstellen: den gesicherten Block als `0x51` senden (speichert sofort). Den globalen MIDI-Kanal
  danach von Hand setzen.
- Vor dem Menüpunkt SOFTWARE UPDATE kommt FACTORY RESET (13/14): nach dem Bestätigen sind Patterns
  und Globals weg. Nicht mit EDIT links/rechts über zwei Seiten scrollen, ohne auf das Display zu sehen.

## Belege (Befehle, im Repo-Ordner)

| Aussage | Prüfung |
|---|---|
| Vorgabetabelle gleich heutigem Block | `dd if=SYSTEM*.VSB bs=1 skip=$((0xCFF58)) count=256 \| cmp - globals-now.bin` |
| Prüfung nur `GLED` | `0xC004718C` disassembliert (`ldr r0,[r1,#0xfc]; cmp 0x44454C47`) |
| Update schreibt nur `0x020000` bis `0x220000` | Emulator, Flash-Befehle `0x20` und `0x02` mit Adresse mitgeschrieben |
| MFX-2-WRITE berührt `0x230000` nicht | wie oben, Lauf `mfxwrite` mit `Box` aus `tools/emu/mfx_cases.py` |
| Rückfall bei zerstörtem Sektor | Emulator, vier Varianten der Tabelle in "Frage 3" |
| Seite 19/20 ist `0x1f` | Emulator, VALUE je Seite, lebendes Objekt verglichen |
