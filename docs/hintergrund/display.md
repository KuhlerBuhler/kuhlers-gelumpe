# Display, LEDs und Gerätename

Was der Patch am Display und an den LEDs macht und was dazu gemessen ist: die Seite CALIBRATE DISPLAY, die Trägheit des
LCD im Emulator, die Farben der Pegelanzeige, das Dimmen der LEDs im Energiesparmodus und der Name, unter dem sich das Gerät
am Rechner zeigt. Die Rohnotizen stehen in der
Git-Historie, zum Beispiel `git show 03c7827adc7b:docs/messungen/2026-10-21-display-kalibrierung.md`.

## CALIBRATE DISPLAY auf der Seite LCD CONTRAST

Die vorhandene Seite **Global, LCD CONTRAST** (Seite 13, Index 12) zeigt mit dem Patch **CALIBRATE DISPLAY**, den
Kontrastwert und drei Bälle, die sich auf getrennten Zeilen im Geschwindigkeitsverhältnis 1:2:4 bewegen. Die Position
kommt aus dem vorhandenen Rahmenzähler. Die Seite ist eine Einstellhilfe, sie misst nichts am LCD.

- Das VALUE-Rad stellt weiter den Kontrast der Firmware ein. VALUE, WRITE und EXIT bleiben im Originalcode, es gibt keinen
  neuen Eingabe-, Speicher- oder Kontrastschreiber. Der Kontrast wird aus dem Global-Block gelesen: Byte 18 bis 42, auf dem
  Display 1 bis 25 (wie `korg.global.lcdContrast` in der [Plugin-Referenz](../plugins.md)).
- Gezeichnet wird im vorhandenen [Rahmenhaken](../glossary.md#rahmenhaken) der Laufzeit (`tools/patch/script_calibrate.s`),
  nur auf dem Global-Bildschirm 9 mit Seitenindex 12 und ohne offenes Fenster, und nur in die mittleren sechs Seiten des
  Displaypuffers. Kopfzeile und unterste Zeile bleiben bei der Firmware, andere Bildschirme und Dialoge werden nicht
  überzeichnet. Der [Notschalter](../glossary.md#notschalter) umgeht die Laufzeit und damit auch diese Darstellung.
- Kosten: kein neuer dauerhafter RAM-Bereich, die eigene Schrift der Laufzeit wird wiederverwendet, 516 Byte Code und Daten
  einschließlich des Aufrufs, 2247 ARM-Befehle je Aufruf (die Prüfung verlangt unter 4000). Gemessen im Emulator.
- Adressen (offline gelesen, mit `tools/patch/fwmap.py` zugeordnet): der Global-Objektzeiger liegt bei `0xC033E6A0`, gleich
  auf Sampler und Synth. Der Ladebefehl `0xC0064728` des Samplers entspricht `0xC005ABC4` im Synth, gleicher Code. Die
  Literale `0xC0064834` (Sampler) und `0xC005ACD0` (Synth) enthalten beide diesen Zeiger. Die Zuordnung steht in
  `data/synth-map/display-calibrate.json`.
- **Offen, am Gerät:** bei welchem Kontrast die drei Bewegungen am besten zu sehen sind. Das Nachleuchten des LCD kann der
  Emulator nicht bestätigen.

Quelle: Messung 2026-10-21/display-kalibrierung

## Trägheit des LCD aus einem Video bestimmen

Der Emulator bildet die Trägheit der LCD-Bildpunkte als Verzögerungsglied erster Ordnung nach (`tools/emu/lcd.py`,
`TAU_ON` fürs Dunkelwerden, `TAU_OFF` fürs Hellwerden). `TAU_OFF` ist eine Schätzung. So wird es gemessen (Anleitung,
hergeleitet; die Formel ist im Test `test_the_constants_follow_from_the_extremes_of_the_280_ms_blink` geprüft):

Dunkelheit eines Bildpunkts: `d(t) = Ziel + (Start - Ziel) * exp(-t / tau)`. Die Zeitbasis ist das Blinken des wartenden
Patternnamens: die Firmware wechselt genau alle 280 ms (7 Bildschirm-Takte zu 40 ms).

**Filmen**

1. Gerät am Netzteil, nicht am Akku: auf Batterie dimmt die Firmware das Licht durch schnelles Ein und Aus, das gibt in
   Zeitlupe Streifen. Licht auf Weiß.
2. Telefon auf Stativ, Zeitlupe mit 240 Bildern/s (120 geht auch, 60 ist zu grob). Belichtung, Fokus und Weißabgleich
   sperren, Blitz und Bildstabilisierung aus. Das Display füllt das Bild, von vorn, kein Spiegeln, so nah, dass ein
   Display-Bildpunkt mindestens 4 Kamera-Bildpunkte breit ist.
3. 2 s Standbild des Displays vor dem Drehen (Bezug für dunkel).
4. PLAY, mit VALUE das nächste Pattern wählen, bis zum Ende des Takts filmen und den Wechsel mit aufnehmen. Mindestens
   8 Blinkzyklen (nach drei ist der Hub eingeschwungen). Zwei bis drei Aufnahmen am selben Platz.

**Wo messen** (Display von links oben, Bildpunkt 0 bis 127 und 0 bis 63, gemessen im Emulator):

- Strich: der Schaft des großen "I" von "Init", Spalten 5 und 6, Zeilen 33 bis 43. Mittelwert über die Zeilen 36 bis 40.
- Dunkel-Bezug: ein Punkt der Leiste ohne Text, zum Beispiel Spalten 5 und 6, Zeile 25.
- Hell-Bezug: derselbe Strich, wenn der Name nach dem Wechsel ruhig steht. Er nimmt die Unschärfe der Kamera mit.

**Ablesen**

1. Bilder ziehen, zum Beispiel `ffmpeg -i clip.mov -vf "crop=W:H:X:Y,format=gray" frame_%05d.png`, je Bild die mittlere
   Helligkeit `b(n)` des Strichs, `t = n / Bildrate`. Nichts darf übersteuern.
2. `d(t) = (b_hell - b(t)) / (b_hell - b_dunkel)`, 0 sichtbar, 1 dunkel.
3. Im eingeschwungenen Blinken `H` (Ende der Dunkelphase) und `L` (Ende der Hellphase), gemittelt über die letzten 4 Zyklen.
4. Mit `T = 0,28 s`: `a = (1 - H) / (1 - L)`, `b = L / H`, `TAU_ON = -T / ln(a)`, `TAU_OFF = -T / ln(b)`. Beispiel:
   `H = 0,95`, `L = 0,24` ergibt `a = 0,066`, `b = 0,25`, `TAU_ON = 0,10 s`, `TAU_OFF = 0,20 s`.
5. Gegenprobe an den Flanken: `ln(1 - d(t))` in der Dunkelphase und `ln(d(t))` in der Hellphase gegen `t` sind Geraden mit
   der Steigung `-1 / TAU_ON` und `-1 / TAU_OFF` (Bilder mit `d` zwischen 0,05 und 0,95). Beide Wege sollen innerhalb von
   20 % übereinstimmen, sonst passt das Modell nicht oder die Aufnahme zählt neu.
6. Grenzen: bei `H` über 0,97 ist `TAU_ON` im Blinken kaum zu sehen, dann nur die Flanke nehmen oder "kleiner als 0,12 s"
   angeben. Dasselbe für `TAU_OFF` bei `L` unter 0,03. Kälte macht das LCD langsamer, die Raumtemperatur dazuschreiben.

**Anwenden:** Probelauf mit `E2_LCD_TAU_ON=... E2_LCD_TAU_OFF=... npm start` (oder `--lcd-tau-on`/`--lcd-tau-off` am
Dienst), dauerhaft in `tools/emu/lcd.py` und `tools/emu/README.md`. Danach dieselbe Aufnahme gegen den Emulator ansehen:
`H` und `L` aus dem Emulator müssen zu den gemessenen passen (mit den Vorgaben Stufe 14 und 4 von 15).

Quelle: Messung 2026-10-12/lcd-helligkeit

## Pegelanzeige: Farben und die hängende 1

- **Vier Farben mit LED-Farbe** (Code gelesen, im Emulator geprüft): ist auf einer der Seiten METER STILL bis METER LOUD eine
  Farbe gesetzt, auch RAINBOW, setzt `menu_look_apply` die Anzeige auf vier Farben (`M_LED_EFF` 3). Eine Zone auf STOCK
  nimmt dann die Farbe der LED-Seiten (LED RED, GREEN, BLUE), wenn dort eine gesetzt ist, so hell wie der Pegel
  (`64 + Pegel² * 191`). Mit RAINBOW bei STILL läuft im Stillen der Regenbogen, beim Spielen leuchtet die LED-Farbe. Ohne
  LED-Farbe bleiben die Farben der Firmware.
- **Nie eine 1 senden** (gemessen im Emulator, disassembliert): die Sendefunktion `0xC00875F4` (LED-Manager, LED, force)
  vergleicht erst das Halbwort LED/Modus (`+4`) der Kopie des Gesendeten (`Manager + 0x888 + 8 * LED`) mit dem Eintrag
  (`Manager + 0x48 + 8 * LED`), dann aber die Helligkeit der Kopie (`+6`) mit dem Modusbyte des Eintrags (`+5`, bei den
  Pegel-LEDs immer 1):

  ```
  c008763c  ldrb r0, [r5, #2]     ; Kopie +6: Helligkeit
  c0087640  ldrb r2, [ip, #1]     ; Eintrag +5: Modus
  c0087644  cmp r0, r2
  c0087648  popeq {r3, r4, r5, pc}
  ```

  Ist einmal die Helligkeit 1 hinausgegangen, schickt die Funktion für diese LED nichts mehr, bis jemand mit `force`
  sendet. Die Firmware selbst schreibt nur 0, 192, 255 und 2 × Velocity und trifft das nie. Ein Regenbogen läuft durch alle
  Werte und blieb im Emulator nach der ersten 1 auf einem Kanal stehen (rot und grün auf 1, blau lief weiter). Darum
  schreibt die Pegelanzeige nie 1, sondern 2, in beiden Wegen (eigene Farbe und vier Farben). Diese Regel gilt für jeden
  Code, der LEDs ohne `force` über `0xC00875F4` schickt.
- Der Regenbogen geht drei Schritte je 40-ms-Takt, einmal rundum in rund 3,4 s.
- Geprüft im Emulator (`menu_cases.py`, Fall `led_meter_rainbow_keeps_the_led_colour`), am Gerät nicht.

Quelle: Messung 2026-10-22/meter-led-farbe

## Energiesparen: LEDs dimmen

Der Patch `pad_colors.py` dimmt im Power Save der Firmware auch die LEDs (Seite LED DIMMING). Was er tut und wie es
gemessen ist, steht in der [Messung Energiesparen](../messungen/2026-10-18-energiesparen-leds.md). Dazu:

- Die Aufrufer des Power-Save-Schalters `0xC0028AB4` sind Funktionen der Oberfläche (`0xC00511A4`, `0xC00740B0`,
  `0xC007410C`, `0xC0075B3C`, `0xC007611C`, `0xC0076184`), kein Interrupt. Hergeleitet aus dem Code.
- **Offen:** am Gerät zeigen die LEDs im Power Save nur aus, ganz hell oder sehr dunkel. Der nächste Schritt am Gerät, nur
  mit Zustimmung, weil er LEDs am Gerät setzt:
  1. Eine Pad-LED nacheinander auf 255, 192, 128, 64, 32, 16, 8 setzen und jeweils ansehen.
  2. Dasselbe mit einer Tasten-LED.
  3. Beides einmal mit und einmal ohne Power Save.

  Damit ist zu entscheiden, warum das Bedienfeld keine Zwischenstufen zeigt.

Quelle: Messung 2026-10-18/energiesparen-leds

## USB-Gerätename "Electribe 3"

Der Datenpatch `usb-name` (Häkchen im [Patcher](../patcher.md), aus per Voreinstellung) ersetzt den Gerätenamen und die
Namen der beiden MIDI-Ports: "Electribe 3", "Electribe 3 SOUND" und "Electribe 3 PAD/KNOB", rot und blau gleich.

**Wo die Namen liegen** (gemessen an den Dateien, rot, Hacktribe, blau 2.02):

- Herstellername ist String 1, Gerätename String 2, die beiden MIDI-Ports nehmen String 3 und 4. Jeder String hat genau
  einen Verweis, aus einer Tabelle mit 5 Einträgen.
- Rot (Korg und Hacktribe gleich): Tabelle `0xC00A40A0`, Gerätename `0xC00A4120`, Ports `0xC00A4148` und `0xC00A4180`.
- Blau: Tabelle `0xC008EB00`, Gerätename `0xC008EB80`, Ports `0xC008EB98` und `0xC008EBC0`.
- Platz (2 Byte Kopf plus UTF-16): rot Gerätename 40 Byte, Ports 56 und 60; blau 24, 40 und 44. "Electribe 3" braucht
  24 Byte und füllt den Platz auf der blauen genau, "Electribe 3 _ SOUND" (40) passt auf beiden, "Electribe 3 _ PAD/KNOB"
  (46) nur auf der roten, auf der blauen fehlen 2 Byte. Nach dem letzten Port folgt direkt die nächste Beschreibung.
- "KORG INC." als Hersteller und die USB-Kennungen bleiben: VID 0944, PID 012E rot, 012D blau (hergeleitet).
- Die Firmware liest die Strings beim Start nicht, der Emulator kennt kein USB. Geprüft werden nur die Bytes
  (`test/usb-name.test.mjs`).

**Was daraus folgt:**

- Die App findet die Ports mit `/electribe/i` (`src/session.mjs`). Jeder Portname muss "Electribe" behalten.
- Der Rechner liest die Namen nur beim Einstecken, darum ist es eine Wahl beim Patchen, kein Menüpunkt am Gerät.
- DAW-Zuordnungen und Controller-Skripte, die am alten Portnamen hängen, müssen neu verknüpft werden (ungeprüft).
- Windows kann den alten Namen behalten, bis das Gerät einmal im Geräte-Manager entfernt wird (ungeprüft). macOS und Linux
  zeigen Gerätename und Portnamen, Windows je nach Treiber.

**Gerätetest, offen (rot und blau):**

1. Name ansehen: Linux mit `amidi -l` und `aconnect -l`, macOS im Audio-MIDI-Setup, Windows mit Klassentreiber und mit
   Korgs Treiber.
2. Die App verbindet, SysEx geht in beide Richtungen.
3. Korgs Editoren finden das Gerät noch.
4. Windows: zeigt es nach dem Umstecken den neuen Namen, oder erst nach Entfernen im Geräte-Manager?

Quelle: Idee 69

## Werte-Fenster nach einem Regler

Ein Dreh an einem Regler oder Drehgeber zeigt den neuen Wert in einem Fenster über dem Hauptbild (Fenster `0x17`, beim
Sample-Drehgeber `0x18`). Es bleibt im Emulator etwa 1,7 s, am Gerät etwa 5 s stehen; das passt zum gemessenen Faktor 3,45
zwischen Gerät und Emulator (hergeleitet).

**Korgs Firmware** (rot, Hacktribe und blau 2.02 gleich): die Tasten-Funktion des Fensters (rot `0xC006543C` für `0x17`,
`0xC0065498` für `0x18`; blau nur eine, `0xC005B8B4`) ignoriert jeden Druck. Erst beim Loslassen schließt sie das Fenster
(`0xC0083E30`, setzt das Merkmal "kein Fenster" sofort) und schickt das Loslassen erneut ab (`0xC00839F0`). LPF, HPF und
BPF gehen beim Loslassen an den Filter und lassen das Fenster stehen. Folge: der Druck ist verloren. Im Emulator verlieren
so MENU und WRITE ihren ersten Druck, und SHIFT + Taste (etwa SHIFT + LEFT, SHIFT + PART ERASE) wirkt nur wie die Taste
allein, weil das Hauptbild das SHIFT nie sieht (gemessen: jede Taste `0x00` bis `0x23`, SHIFT + Taste, Pads, Hauptrad,
gestoppt und laufend, mit und ohne Fenster verglichen). Die Part-Tasten, TRIGGER, SEQUENCER, KEYBOARD, CHORD, PATTERN SET,
die Pads nimmt die Firmware schon vor dem Fenster: sie wirken, das Fenster bleibt bis zu seinem Ende stehen.

**Hauptrad**: es geht nicht an die Tasten-Funktion des Fensters, sondern an die Drehgeber-Funktion des Bildschirm-Verwalters
(rot `0xC006EB90`, blau `0xC0062030`; `r1` = 0 das Hauptrad). Bei offenem Fenster gibt Korgs Funktion das Hauptrad nur dem
Hauptbild (das Fenster bleibt stehen) oder dem Fenster `0x2a`; auf jedem anderen Bild, also in jedem Menü, geht der Dreh
verloren (gemessen: MENU, RIGHT, Regler, dann Hauptrad hoch und runter, mit und ohne Fenster verglichen; rot, Hacktribe mit
BLECHTRIBE 1.4.9 und blau gleich). Am Gerät: im Menü musste man warten, bis das Fenster weg war. Ohne Fenster ruft Korgs
Funktion bei jedem Dreh das Schließen auf und gibt den Dreh dann dem Bild.

**Patch `value-popup`** schreibt die Tasten-Funktion an derselben Stelle um, gleiche Länge, gleiche Aufrufe: ein Druck
schließt das Fenster und schickt denselben Druck erneut ab, der dann den Weg des Hauptbilds nimmt. Das gilt auch für SHIFT,
so geht SHIFT + Taste; ein Regler mit SHIFT öffnet sein Fenster neu. Die Filtertasten bleiben wie bei Korg. Dazu schreibt
er die Drehgeber-Funktion an derselben Stelle um: das Hauptrad schließt ein Werte-Fenster (`0x17`, rot auch `0x18`) und
geht an das Bild wie ohne Fenster. Das Fenster `0x2a` behält das Hauptrad, andere Fenster bleiben bei Korgs Weg, die
anderen Drehgeber gehen weiter an das Fenster.

Geprüft im Emulator (`tools/emu/value_popup_cases.py`, rot, Hacktribe, blau): jede Taste, SHIFT + Taste, Pads und Hauptrad
enden mit Fenster im selben Zustand wie ohne, auch Hauptrad, LEFT und RIGHT in einer Menü-Seite (ohne Patch fällt dort
das Hauptrad durch). Offen: EXIT schließt im Menü bei offenem Fenster nur das Fenster und verlässt das Menü nicht (Korgs
Tasten-Verteiler ruft das Schließen des Fensters selbst, `0xC0070348`). Offen auch, dass die Tasten, die die Firmware vor dem Fenster nimmt, und
die Pads das Fenster schließen (dafür müsste der Patch an den Verteiler der Panel-Nachrichten). Das Hauptrad im Menü ist am Gerät noch ungetestet.

Quelle: Messung 2026-11-27/werte-fenster-tasten
