# Doom auf der Electribe

Was über Doom auf dem roten Gerät bekannt ist: Start, Anzeigen und Fehlercodes, Bild, Bedienung, Speicher, Ton und der
Gerätetest. Der [Doom-Lader](../glossary.md#doom-lader) selbst steht in [Nativer Doom-SD-Lader](../messungen/2026-10-15-doom-sd-lader.md), die Prüfläufe im
Emulator in [Doom im Firmwareemulator](../messungen/2026-10-15-doom-v21.md), die Einbindung in den Patch-Satz in
[Doom als Patch](../messungen/2026-10-15-doom-im-patcher.md), Lizenzen in [doom-lizenz.md](../doom-lizenz.md), der Rückweg
in [Rettung](../rettung.md#doom). Die Quellen liegen in `tools/doom/` ([Buildanleitung](../../tools/doom/README.md)).

Die genannten Rohmessungen sind gelöscht und in der Git-Geschichte lesbar:
`git show origin/develop:docs/messungen/<datei>.md`.

Markierungen: **gemessen am Gerät**, **gemessen im Emulator**, **offline gelesen** (Code gelesen), **hergeleitet**, **offen**.

## Stand am Gerät

- Doom startet am Gerät und das Spielbild ist erkennbar. Es ist zu dunkel, bei Bewegung erschwert das Nachziehen des LCD
  das Erkennen, die Steuerung ist schwer zu bedienen. Das ist eine Rückmeldung vom Gerät (23.10.), keine instrumentierte
  Messung von Helligkeit, Bildrate oder LCD-Reaktionszeit. Mit dem Bildadapter davor zeigte das Gerät hauptsächlich ein
  regelmäßiges Punktraster (der Hash der installierten Dateien war nicht bestätigt).
  Quelle: Messung 2026-10-23/doom-bild
- Die feste Kennlinie und die beleuchteten Pads (siehe unten) sind am Gerät nicht geprüft.
  Quelle: Messung 2026-10-23/doom-pads
- Ein/Aus in Doom: siehe [Rettung](../rettung.md#doom).
- **offen:** Bildrate, echte Ladezeit bis zum ersten Bild, Lesbarkeit auf dem LCD, Ton.

## Start

**Einsprung nach dem Einhängen der Karte.** Der Lader sitzt bei `0xC002AE64`, direkt hinter der Frage der Firmware nach
der Sample-Datei (`0xC002AE60`). Er hängt die Karte nicht selbst ein, sondern prüft den Volume-Eintrag der Firmware
(`0xC06A010C`) und öffnet `doom.bin` dort. Ein Lader, der die Karte bei `0xC002ADB0` selbst einhängt, bevor die Firmware
es tut, lief im Emulator, am Gerät endete er in `DOOM ERROR 00000101` (`0x100` plus `FR_DISK_ERR` von `f_mount`).
Gemessen am Gerät (17.10.) und im Emulator. Quelle: Messung 2026-10-17/doom-nach-dem-einhaengen

**Die Frage nach der Sample-Datei hängt die Karte nicht sicher ein.** FatFs registriert das Volume und hängt es erst beim
ersten Dateizugriff ein. Der Lader versucht `doom.bin` darum bis zu sechsmal mit 500 ms Abstand zu öffnen
(Schlaf `0xC0000B78`). Offline gelesen (`tools/doom/bootstrap.c`). Quelle: Messung 2026-10-19/doom-start-stack

**Startaufrufe vor dem Öffnen.** Der Doom-Zweig ruft `0xC0025754(1)` (Systemtakt ohne die Sampler-Rückrufe), aktiviert
Task 8 (SD-Karte) und ruft `0xC003FD20` (SD-Diskdienst). Ohne diese Aufrufe hängt `f_open` (Stufe 2, nichts gelesen).
Ein früher direkter Dateiaufruf ohne diese Initialisierung lieferte `FR_NOT_ENABLED`, das Aktivieren der SD-Task allein
reichte nicht. Gemessen im Emulator.
Quelle: Messung 2026-10-17/doom-nach-dem-einhaengen, Messung 2026-10-15/doom-machbarkeit

**Nur Tasks 1 und 8.** Im Doom-Zweig laufen nur StartupTask 1 und SDCardDriverTask 8, keine USB-, Command-, UI-, Voice-
oder SeqTask. Vor dem Lader hat die Firmware ihre Globals und Patterns aus dem Flash gelesen und den Bildschirm-Manager
angelegt, Samples lädt sie nicht. Gemessen im Emulator. Folge: Während Doom läuft oder hängt, meldet sich die Electribe
nicht am USB, es gibt keinen MIDI-Port (gemessen am Linux-Rechner, 19.10.). `doom_probe.py` kann diesen Zustand darum nicht
über BLECH READ untersuchen, und ein Hintergrundtask nur für Diagnose wird nicht gestartet.
Quelle: Messung 2026-10-17/doom-nach-dem-einhaengen, Messung 2026-10-19/doom-start-stack

**Stack am Einstieg.** Der Einstieg sichert Statusflags und ein weiteres Register zusammen, 32 Byte, damit SP beim Sprung in
den C-Lader auf acht Byte ausgerichtet bleibt (Arm AAPCS32, öffentliche Schnittstelle). Ein Einstieg mit sechs Registern
plus Flags-Register (28 Byte) lässt SP mit Rest vier bei Division durch acht in den C-Lader: im vollständigen Firmwarestart
gemessen SP `0xC0202364` statt `0xC0202360`. `tools/doom/bootstrap_tests.py` prüft die Ausrichtung (der alte Einstieg
scheitert mit `4 != 0`). Ob dieser Fehler den Hänger am BLECH-Startbild am Gerät (19.10.) erklärte, ist **offen**.
Gemessen im Emulator. Quelle: Messung 2026-10-19/doom-start-stack

**Cache vor dem Sprung.** Der Prefetch-Befehl `c7, c5, 4` hängt am Gerät, er steht im
[Lader](../messungen/2026-10-15-doom-sd-lader.md) nicht. `c7, c10, 1` und `c7, c10, 4` kommen am Gerät zurück. Unicorn
führt `c7, c5, 4` aus, als wäre nichts, darum zeigte der Emulator den Hänger nicht. Gemessen am Gerät (22.10., nur im RAM über
Hacktribes Execute). Quelle: Messung 2026-10-22/doom-am-geraet

## Anzeigen und Fehlercodes

Bis zum ersten Spielbild zeigt das Display, wie weit der Start ist. Offline gelesen (`tools/doom/bootstrap.c`,
`tools/doom/runtime.c`). Quelle: Messung 2026-10-19/doom-start-stack, Messung 2026-10-22/doom-am-geraet

| Anzeige | Wann |
|---|---|
| `DOOM` `BOOT` | Lader gewählt, vor den Startaufrufen |
| `DOOM` `READ` mit Bytezähler (hex) | beim Lesen von `doom.bin`, alle 32 KiB und am Ende |
| `DOOM` `START` | Länge und SHA-256 stimmen, Sprung in die Engine |
| `DOOM` `ENGINE` | erste Anweisung der Engine |
| `DOOM` `ENGINE INIT` mit Zahl | Tickzähler der Firmware beim Start der Engine (hex) |
| `DOOM` und die letzten zwei Zeilen der Engine | bei jeder Ausgabe der Engine, zum Beispiel `M_INIT: ...` |
| `DOOM` `OPEN WAD` | vor dem Öffnen der WAD |
| `DOOM` `LADE WAD` mit MB und Balken | alle 200 ms, solange die Engine vor ihrem ersten Bild liest |
| `DOOM ERROR` `POWER OFF` mit Code | Fehler, siehe unten |
| `DOOM STOP` `POWER OFF` | nach QUIT DOOM |
| `POWER KEY` `HOLD 5 S`, dann `POWER OFF` | Ein/Aus gedrückt, siehe Ausschalten |

Der Balken von `LADE WAD` ist gelesene Bytes durch WAD-Größe. Die Engine liest nicht die ganze WAD, beim ersten Bild steht
er also nicht am Ende. Die Schrift kann A bis Z, 0 bis 9 und `: . - /`.

| Code | Bedeutung |
|---|---|
| `0x100` + FatFs-Fehler | Öffnen von `doom.bin` scheitert sechsmal, das Volume ist nicht eingehängt. `00000100`: Karte beim Start des Laders nicht eingehängt (am Gerät gesehen, 18.10.) |
| `0x200` + FatFs-Fehler | Öffnen scheitert sechsmal bei eingehängtem Volume |
| `0x300` | `doom.bin` hat die falsche Länge |
| `0x400` + FatFs-Fehler | Lesefehler in `doom.bin` |
| `0x500` | SHA-256 von `doom.bin` falsch |
| `0x600` + FatFs-Fehler | Schließen von `doom.bin` scheitert |
| `0x700` | Lader und Engine passen nicht zusammen (Anzeige `DOOM ERROR ABI`) |
| `0x800` + FatFs-Fehler | WAD lässt sich nicht öffnen (Anzeige `DOOM WAD FEHLT`) |

Fehlen `doom.bin` oder `doom.wad` ganz, oder gibt es keine Karte, kehrt der Lader zurück und der Sampler startet
(FatFs-Antworten 4, 5, 11, 13).

Quelle: Messung 2026-10-19/kartenfehler-beim-start (Code `00000100` am Gerät), Messung 2026-10-22/doom-am-geraet

## Laden der WAD

- Im Emulator spielt Doom nach 55,6 s Gerätezeit auf einer 512-MiB-Karte. Bis dahin liest die Engine die WAD. Auf einer
  64-MiB-Karte mit 512-Byte-Clustern liest sie etwa neunmal langsamer (nach 110 s 6 MB). Der Ladebalken-Patch ändert daran
  nichts (mit und ohne Seitenhaken nach 30 s je 7,8 MB). Die Anzeige `LADE WAD` kostet keine messbare Zeit. Gemessen im
  Emulator.
- Am Gerät blieb mit diesem Stand nach SHIFT + TAP nur das Startbild stehen, gewartet wurde weniger als 56 s
  (Rückmeldung 20.10.). Die echte Ladezeit am Gerät ist **offen**.

Quelle: Messung 2026-10-17/doom-nach-dem-einhaengen

## Bild

Die Engine zeichnet intern 320 mal 200 Pixel in Farbe. `DOOMGENERIC_RESX=128` allein geht nicht, die vorhandene
Bildausgabe vergrößert nur ganzzahlig. Alle sechs `DG_*`-Plattformfunktionen sind eigene Adapter. `DG_DrawFrame` rechnet
auf 128 mal 64 Pixel mit einem Bit je Pixel um, 1024 Byte im Seitenformat des Displays. Offline gelesen.
Quelle: Messung 2026-10-15/doom-engine-build

So rechnet der Adapter um (offline gelesen, `tools/doom/runtime.c`, im Emulator geprüft):

1. **Flächenmittelung:** gewichtete Pixelflächen auf 128 mal 64. Ein Ring aus vier Zeilen vermeidet doppelte
   Farbumrechnung, alle 64.000 Quellpixel werden genau einmal gelesen.
2. **Feste Kennlinie:** Exponent 0,4, die 256 Werte stehen im Code. Gleiche Eingangshelligkeit gibt damit immer dieselbe
   Ausgabe, unabhängig vom übrigen Bild. Den globalen LCD-Kontrast schreibt der Adapter nicht.
3. **Atkinson-Fehlerverteilung** auf ein Bit je Pixel.
4. **Distanzlicht:** Vor dem Renderaufruf begrenzt der Adapter die Entfernungstabellen `scalelight` und `zlight` auf
   Farbtabelle 16 statt höchstens 31 (Linker-Wrap von `R_RenderPlayerView`, die gepinnte Enginequelle bleibt unverändert).
   Hellere Tabellen, Texturen und besondere Spielbeleuchtung bleiben.

Warum: Die mittlere Helligkeit im untersuchten E1M1-Bild ist nur 37,38 von 255. Einzelne herausgegriffene Pixel mit
einem festen 4-mal-4-Raster lassen dunkle Konturen weitgehend verschwinden, das gab am Gerät das Punktraster. Mit der
festen Kennlinie hat dieselbe RGB-Szene 3528 statt 2208 helle Pixel von 8192 (etwa 43 statt 27 Prozent). Das ist kein
Maß für die Helligkeit am Display. Die Kennlinie braucht für dieselbe Szene 1.682.668 statt 1.756.606 native ARM-Befehle
(rund 4,2 Prozent weniger), der temporäre Stackbedarf sinkt von 11.900 auf 2.932 Byte. Das ist keine Bildrate am Gerät.
Gemessen im Emulator. Quelle: Messung 2026-10-23/doom-bild, Messung 2026-10-23/doom-pads

## Bedienung

| Electribe | Doom |
|---|---|
| PART ab / auf | vorwärts / rückwärts |
| EDIT links / rechts | links / rechts drehen |
| PLAY | schießen |
| TAP | benutzen |
| REC | bestätigen, auch Ja in Ja/Nein-Fragen |
| MENU oder EXIT | Menü öffnen oder schließen, EXIT ist auch Nein |

| Pad | Doom | Licht |
|---|---|---|
| 2 / 10 | vorwärts / rückwärts | blau |
| 9 / 11 | links / rechts drehen | blau |
| 1 / 3 | seitwärts links / rechts | blau |
| 16 | schießen | rot |
| 8 | benutzen | violett |
| 15 halten | rennen | violett |
| 7 | nächste verfügbare Waffe | violett |

- Die Tasten nutzen die Konstanten der gepinnten `doomkeys.h`. Nach der Initialisierung der Engine setzt der Adapter
  `key_menu_confirm` auf `KEY_ENTER` und `key_menu_abort` auf `KEY_ESCAPE`. Er liest höchstens 32 Panel-Nachrichten je
  Abfrage. Offline gelesen. Quelle: Messung 2026-10-15/doom-native-runtime
- Belegte Pads leuchten gedämpft und werden beim Drücken heller, unbelegte bleiben aus. Die Pads haben rote und blaue
  Ausgänge, Violett nutzt beide, ein grünes Padlicht wird nicht vorausgesetzt. Mehrere Quellen derselben Aktion bleiben
  gehalten, bis die letzte losgelassen ist. Die Drehschritte sind 320/480/240 statt 640/1280/320, die Laufgeschwindigkeit
  bleibt. Gemessen im Emulator, am Gerät **offen**. Quelle: Messung 2026-10-23/doom-pads

## Uhr und Ausschalten

- **Uhr:** Millisekunden kommen aus dem Kernelwort `0xC06A2930` (Disassembly `0xC0000454` bis `0xC000059C`). Der Adapter
  zählt nicht selbst, `DG_SleepMs` wartet auf einen echten Tickabstand, Interrupts bleiben im Zustand des Aufrufers. Im
  Doom-Zweig liefert die Uhr über 0,9999894 Emulatorsekunden genau 1000 Ticks. Gemessen im Emulator.
  Quelle: Messung 2026-10-15/doom-native-runtime
- **Ausschalten:** Das Panel meldet Ein/Aus nach 2 s Halten (Typ 6, Wert 1). Bleibt die Taste (GPIO 7.15, low = gedrückt)
  danach weitere 5 s unten, lässt der Adapter die Stromhaltung los (GPIO 7.11 über `0xC0016BB4`) und ruft den letzten
  nativen Haltaufruf `0xC001734C(0x01E26000, 1)`, nicht die volle Ausschaltroutine des Samplers. Vorher losgelassen, läuft
  das Spiel weiter. Fehler und QUIT warten ebenso auf die Taste. Offline gelesen (`tools/doom/native_power.h`).
  Quelle: Messung 2026-10-15/doom-native-runtime

## Speicher

- Die Engine wird nach `0xC1000000` geladen, der Stack endet bei `0xC1800000`
  ([Lader](../messungen/2026-10-15-doom-sd-lader.md)).
- Stack-Hochwasser der Engine: 1256 Byte, gemessen in der Engineprobe für Initialisierung und die getestete Kartenfolge,
  keine Obergrenze aller Pfade. Daraus der eigene Engine-Stack von 64 KiB (mehr als Faktor 50).
- Heap: mit 16-MiB-Zone fordert die Engine 17.132.064 Byte an, mit 6-MiB-Zone 6.646.304 Byte. Doom läuft mit `-mb 6`.
- Code, Daten und BSS der Probe: 689.620 Byte. Mit Heap 7.335.924 Byte (rund 7,0 MiB), mit 64 KiB Stack 7.401.460 Byte.
  In einer Reserve von 8 MiB bleiben 987.140 Byte. Treiber und Firmwaretasks gehören nicht in diese Rechnung.

Gemessen im Emulator (Unicorn, Engineprobe). Quelle: Messung 2026-10-15/doom-engine-build

## Ton

Doom läuft ohne Ton. **Offline gelesen:** Der Port startet mit `-nosound`. `build_runtime.py` definiert kein
`FEATURE_SOUND` und baut weder `i_sdlsound.c` noch `i_sdlmusic.c`, `-nosound` wegzulassen ergibt also noch keinen Tonpfad.
Der DSP-Boot `0xC0011AB8` ist im Emulator ein Platzhalter (Steuerport immer `0x81`, PCM-Wörter werden nicht ausgegeben),
der Emulator belegt darum keinen Ton. **Gemessen im Emulator:** Der originale DSP-Boot läuft schon vor der Wahl zwischen
Sampler und Doom (56,18 ms, in beiden Zweigen). **Hergeleitet:** Ein fertiger PCM-Ausgabepfad ohne Samplerstart ist nicht
bekannt. Die bekannten Audiopfade zeigen weder einen fortlaufenden PCM-Ring noch einen direkten DAC-Aufruf, der
Exportpuffer `0xC0D3A940` ist ein Arbeitsbereich für Dateien.

**Offen, in dieser Reihenfolge:** Audioanschluss, Wiedergabetakt, PCM-Format, Eigentümer des Puffers, Nachfüllen des Rings
und Verhalten bei Unterlauf; dann ein nativer Mixer für Soundeffekte mit gemessener CPU-Last (Musik getrennt), dann ein
Gerätetest mit bekanntem Signal. Quelle: Messung 2026-10-15/doom-native-runtime

## Doom über USB auf die Karte

Die App schreibt `doom.bin` und `doom.wad` über die FILE-Befehle von BLECH nach `KORG/blechtribe/Doom/`, ohne Kartenleser.
Welche Offset-Bits welche Datei wählen, steht in [Sample-Datei](sample-datei.md).

- **offen:** Zeit für die 28 MB `doom.wad` am Gerät. Geschätzt mit den gemessenen 150 bis 200 KiB/s beim Lesen: 2,5 bis
  3 Minuten, Schreiben ist nicht gemessen. Danach SHIFT + TAP und Doom von den so geschriebenen Dateien.
- **offen:** Die blaue Electribe 2 hat keinen Doom-Lader. Sie nimmt das Doom-Bit an, obwohl sie es nicht meldet, das ist
  nicht geprüft, die App nutzt es dort nicht.

Quelle: Messung 2026-11-11/doom-usb

## Gerätetest

Die Schritte stehen in [Gerätetest BLECH v21 mit Doom](../geraetetests/doom-v21.md). Dazu kommen aus dem älteren
Testablauf:

1. **EXIT prüfen,** nach dem Normalstart: mit EXIT einschalten. Erwartet: normaler Sampler, kein Doom. Ausschalten.
2. **Testlimit beim Doom-Start:** fünf Minuten. Das ist das gewählte Limit, keine geschätzte Ladezeit. Die letzte Anzeige
   (siehe Anzeigen oben) mit notieren, sie trennt Initialisierung, Programmlesen und Engine-Start.
3. **Ohne Karte, erst nach bestandenem Rückweg:** Gerät aus, Karte heraus, SHIFT + TAP. Erwartet: normaler Sampler (der
   Lader kehrt ohne Karte zurück). Die Karte nie während eines Zugriffs ziehen.

Quelle: Messung 2026-10-15/doom-geraetetest, Messung 2026-10-19/doom-start-stack
