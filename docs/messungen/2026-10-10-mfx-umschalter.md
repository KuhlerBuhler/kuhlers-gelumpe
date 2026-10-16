# MFX 2 auf TOUCH SCALE (Idee 44): gebaut und im Emulator geprüft

Stand 2026-10-14. Alles im Emulator (`tools/emu/machine.py`, Unicorn 2.1.4) und offline mit Capstone.
Firmware: `SYSTEM.VSB` und `SYSTEM-ringtest.VSB`, Flash: eigener Dump vom 9.10. Am Gerät erprobt ist ein
früherer Stand des Patches ohne Startmodus (`2026-10-13-mfx-umschalter-geraet.md`: TOUCH SCALE schaltet
auf MFX 2, MASTER FX gibt den eigenen Typ, EXIT beim Einschalten hält den Patch aus); **der Startmodus
MASTER FX ist nur im Emulator geprüft.** Der DSP ist im Emulator eine Attrappe: dass es richtig klingt,
ist im Emulator nicht gemessen, nur dass der DSP dieselben Nachrichten bekommt wie bei einer Änderung im
Menü.

**Am Gerät offen:** dass bei GATE ARP wirklich nur die GATE-ARP-LED leuchtet und das Touch-Pad sich wie
zuvor verhält (Gerätetest unten, Schritt 7), dass die LEDs am Gerät wie bisher aussehen (der Weg über den
Manager ist nur im Emulator gemessen) und dass die Seite im Gerätemodus sie jetzt richtig zeigt.

Markierungen: **gemessen** (im Emulator ausgeführt), **offline** (Code gelesen),
**hergeleitet**, **offen**.

## Was gebaut ist

Ein Patch (`data/patches/mfx-switch.json`, erzeugt von `tools/patch/mfx_switch.py`).
TOUCH SCALE ist eine zweite MASTER-FX-Taste: ein Touch-Pad-Modus wie MASTER FX,
mit einem zweiten Effekttyp (MFX 2) für das aktuelle Pattern. Intern bleibt es ein
Effekt, MFX 2 ist ein schneller Typwechsel pro Pattern.

| Taste | Touch-Pad-Modus | Typ | LEDs |
|---|---|---|---|
| MASTER FX | Master FX (Firmware, unverändert) | der eigene Typ des Patterns (MFX 1) | MASTER FX an, TOUCH SCALE aus |
| TOUCH SCALE | Master FX | MFX 2 dieses Patterns | TOUCH SCALE an, MASTER FX aus |
| TOUCH SCALE noch einmal | nichts ändert sich | | |
| GATE ARP (aus jedem Modus) | Gate Arp + Touch Scale (Modus 3 der Firmware) | wieder der eigene Typ | nur GATE ARP an, TOUCH SCALE aus (die Firmware zündet beide) |
| GATE ARP noch einmal | nichts ändert sich | | |
| SHIFT + TOUCH SCALE | die alte Funktion von TOUCH SCALE: Touch Scale allein | wieder der eigene Typ | wie die Firmware |

- **Startmodus:** nach dem Einschalten steht das Touch-Pad im Modus Master FX (MASTER FX-LED
  an, TOUCH SCALE-LED aus), mit dem eigenen Typ des Patterns (MFX 1), wie nach einem Druck auf
  MASTER FX. Mit EXIT beim Einschalten ist der Start der der Firmware: Touch Scale, TOUCH SCALE-LED
  an. Woher der Startmodus kommt und wie er gesetzt wird: Abschnitt „Startmodus“.
- **Gate Arp:** GATE ARP führt aus jedem Modus (Touch Scale allein, Master FX, MFX 2) in den
  Modus Gate Arp + Touch Scale der Firmware: nur die GATE-ARP-LED an (die Firmware zündet auch TOUCH SCALE, der
  Patch löscht sie wieder, Abschnitt „GATE ARP: nur die GATE-ARP-LED“), das Touch-Pad löst das gehaltene Pad
  je Schritt aus (Gate-Arpeggiator) und spielt je Schritt einen Skalenton. In diesem Modus tut ein weiterer Druck nichts, wie MASTER FX
  und TOUCH SCALE (MFX 2). Der Patch ruft dafür die Tasten der Firmware: aus 1 GATE ARP, aus 0
  TOUCH SCALE, aus 2 erst GATE ARP, dann TOUCH SCALE. **Gate Arp allein (Modus 0) ist nicht mehr
  erreichbar** (die Firmware erreicht ihn nur mit GATE ARP aus 2 oder 3). Was dieser Modus
  tut, steht im Abschnitt „Reihenfolge der Modi“; die Taste dafür, SHIFT + GATE ARP, ist der
  Sprung auf die Seite GATE ARP des Pattern-Menüs und bleibt.
- **MFX HOLD:** unverändert. Ein gehaltener Effekt bei MFX 2 ist einfach MFX 2.
- **SHIFT + MASTER FX** (Firmware: Sprung auf die Seite MFX TYPE) bleibt, auch bei
  MFX 2. Die Seite zeigt dann MFX 2.
- **WRITE speichert immer den eigenen Typ (MFX 1)**, nie MFX 2.
- **MFX 2 wählen:** auf dem Gerät, mit der vorhandenen Seite MFX TYPE (Pattern-Menü,
  Anzeige „6/29“). Ist MFX 2 an, ändert VALUE dort MFX 2 dieses Patterns. Gespeichert wird die
  Tabelle (250 Einträge) beim nächsten WRITE. Leerer oder ungültiger Datensatz:
  jedes Pattern hat 07 Looper (wie das Display zählt).
- **Notschalter:** EXIT beim Einschalten gehalten: alle Haken springen sofort ins
  Original, TOUCH SCALE ist die Firmware-Taste.
- **Start:** kein Haken läuft vor den Rettungswegen (gemessen im Emulator: Panel-Austausch
  69 ms, Startmodus-Weiche und Update-Abfrage 72 ms, Setter-Haken ab 95 ms beim Laden des
  ersten Patterns, Hauptbildschirm bei 260 ms; Tick-Haken ab 341 ms mit dem alten Takt, neu nicht
  gemessen, siehe `2026-10-12-emulator-takt.md`). Dort prüfen sie nur den
  Notschalter, den Bildschirm (der Startmodus kommt erst im Hauptbildschirm) und dass MFX 2 aus
  ist. Der Patch nennt diese Stellen unter `startPhase`
  (Ausnahme zu Regel 1 in `docs/patcher.md`, wie beim Startbild-Editor), `check.py` lässt sie
  mit `--allow-code` zu: zwei Wörter, 44 + 480 + 68 Byte. Die Tabelle wird erst beim ersten
  Druck auf TOUCH SCALE aus dem Flash gelesen.
- **Parameter beim Bauen:** `--b-type N` (Vorgabe für Patterns ohne Eintrag, 1 bis 100,
  wie das Display zählt).

### Keine eigene Menüseite

Geplant war eine Seite „MFX 2“ im Pattern-Menü nach MFX TYPE, ersatzweise
Global Seite 21. Beides ist nicht gebaut:

- **Pattern-Menü (offline):** Seiten sind fest im Code: Schalter über 0 bis 14
  (`0xC00672C4`, `cmp r3, #0xe`), eigene Widget-Aufbauten pro Seite, die Seitenzahl
  „/29“ im Kopf zählt Pattern- und Part-Menü zusammen, und Edit rechts auf der
  letzten Seite führt ins nächste Menü. Eine Seite nach MFX TYPE verschöbe alle
  folgenden; eine am Ende bräuchte Eingriffe in die Übergänge. Zu riskant.
- **Global Seite 21 (hergeleitet):** der Startbild-Editor ersetzt die vtable von
  Bildschirm 9 über ein einziges Literal (`0xC0064D3C`); ein zweiter Patch kann es nicht
  ebenfalls ersetzen, die Seite müsste in den Startbild-Editor gebaut werden (neue
  Fassung von dessen Code und Prüfung).
- **Stattdessen** wählt man MFX 2 auf der vorhandenen Seite MFX TYPE, solange MFX 2 an
  ist. Das braucht keine neuen Bildschirmklassen und zeigt den Namen des Effekts wie
  für MFX 1. Eine eigene Seite bleibt möglich (siehe „Offen“).

```bash
python3 tools/patch/mfx_switch.py --vsb SYSTEM-ringtest.VSB --out data/patches/mfx-switch.json [--b-type 7]
node tools/patch/apply.mjs --vsb SYSTEM-ringtest.VSB --patch data/patches/mfx-switch.json --out NEU.VSB
# zusammen mit dem Startbild-Editor:
node tools/patch/apply.mjs --vsb SYSTEM-ringtest.VSB --patch data/patches/splash-editor.json --patch data/patches/mfx-switch.json --out NEU.VSB
tools/emu/.venv/bin/python tools/emu/check.py --base SYSTEM-ringtest.VSB --patched NEU.VSB [--allow-code ...] --flash dump.bin
tools/emu/.venv/bin/python tools/emu/mfx_cases.py run --base SYSTEM-ringtest.VSB --patched NEU.VSB --flash dump.bin
```

## Wie es funktioniert

Vier Haken, alle mit dem Notschalter am Eingang, keiner vor den Rettungswegen. Code 1872 Byte
bei `0xC01A5000` (frei, hinter dem Startbild-Editor), Zustand bei `0xC01A5C00`, der
Datensatz-Puffer bei `0xC01A5D00`.

| Haken | Stelle | Zweck |
|---|---|---|
| Tasten | erster Befehl von `0xC00700D8` | TOUCH SCALE, MASTER FX, GATE ARP, SHIFT + TOUCH SCALE |
| Tick | der Aufruf von `0xC006F178` bei `0xC00836F8` (Bildtick, 22 Mal pro Sekunde) | setzt den Startmodus (einmal), folgt Patternwechseln, hält die LEDs |
| Typ-Setter | erster Befehl von `0xC0048A64` | sieht Laden (`melden = 0`) und Änderungen (`melden = 1`) |
| Pattern speichern | der Kopieraufruf `0xC004C2BC` | schreibt den eigenen Typ, speichert die Tabelle |

- **Typwechsel (offline + gemessen):** `0xC0048A64(Zugriff, Typ, melden)`, Zugriff
  `*0xC0691334 + 0x4004`, schreibt Byte `0x41` des Pattern-Objekts (Pattern-Block + 61)
  und meldet. Die Seite MFX TYPE ruft genau das. Der Patch ruft ihn am Haken vorbei
  (`0xC0048A68`).
- **Alle Typänderungen laufen hier durch (offline):** Aufrufer sind die Seite MFX TYPE
  (`0xC007D07C`), `0xC007D018`, `0xC007F2FC`, `0xC008FBA0`, `0xC0048694` und das Anwenden
  eines geladenen Patterns (`0xC004A9CC`, `melden = 0`).
- **Touch-Pad-Modus:** Wort an `*0xC06912E0 + 0x334`: 0 Gate Arp allein, 1 Touch Scale
  allein, 2 Master FX, 3 beide (gemessen an den LEDs `0x1a`/`0x1b`/`0x1c`). TOUCH SCALE
  ohne SHIFT ruft die MASTER-FX-Taste der Firmware (Taste 6) und schaltet MFX 2 an,
  wenn der Modus danach 2 ist. Lehnt die Firmware die Taste ab (zum Beispiel bei einem
  offenen Fenster), geschieht nichts.
- **SHIFT:** Merker der Firmware (`0xC0040F04()`, Wort `+0x358`). Für SHIFT + TOUCH
  SCALE wird er für den Aufruf des Originals gelöscht und danach zurückgesetzt.
- **Patternwechsel:** das Rad lädt (gemessen) über `0xC004A8E4`, das den eigenen Typ des
  Patterns mit `melden = 0` setzt; Pad und MIDI-Programmwechsel verhielten sich im Lauf
  gleich (hergeleitet: dieselbe Funktion), Ketten (Chain) sind nicht gemessen. Der Haken
  am Setter merkt sich diesen Typ als „eigener Typ“ und markiert „Pattern geladen“.
  Die Nummer des Patterns (`*0xC034029C + 0x318`) steht bei Rad und Pad erst kurz
  danach, darum wertet der Tick beides aus: bei Markierung oder neuer Nummer wird MFX 2
  des (neuen) Patterns angewendet. Eine alte Nummer wird dabei von selbst korrigiert,
  sobald die neue steht.
- **Verhalten beim Patternwechsel (gemessen, Firmware):** der Touch-Pad-Modus bleibt
  bei einem Patternwechsel stehen (Rad und Pad: LEDs unverändert). MFX 2 bleibt darum auch
  an und gilt für das neue Pattern; die LEDs stimmen spätestens einen Tick (45 ms) später.
- **Speichern (gemessen):** `0xC004C28C(…, Nummer, Quelle, kopieren)` kopiert das Pattern
  (`0xC06B279C`, Block) in den Puffer `0xC08B2940` und schreibt ihn nach
  `0x240000 + Nummer * 0x4000`. Der Haken ersetzt den Kopieraufruf: nach dem Kopieren
  steht der eigene Typ im Puffer (Byte 61), das Live-Pattern bleibt MFX 2. Ist die Tabelle
  geändert, geht sie vor der Firmware-Schreibung in den Flash.
- **Datensatz:** Flash `0x7E8000` (ein 4-KiB-Sektor, im Dump `FF`, kein bekannter
  Schreiber, wie beim Startbild-Editor hergeleitet, `docs/hintergrund/startbild-editor.md`): Kennung `MFX2`,
  Version 1, Länge 256, 256 Byte Tabelle (Eintrag n = Anzeigenummer 1 bis 100 für
  Pattern n, 0 = Vorgabe), CRC-32 über alles davor. 268 Byte.
- **Seite MFX TYPE:** der Patch baut die Seite neu auf (`0xC0067270`), wenn er den Typ
  ändert und die Seite offen ist. Der Name stimmt sofort.
- **LEDs:** über den Weg der Firmware: der Patch schreibt den gewollten
  Wert in den Sollwert des LED-Managers (`*0xC0345A1C + 8 * LED + 0x4e`) und ruft
  `0xC00875F4(Manager, LED, 0)`, das die Kopie des Gesendeten nachführt und die Nachricht
  einreiht. Nach MASTER FX, GATE ARP und beim Verlassen von MFX 2 setzt die Firmwarefunktion
  `0xC0088118(Manager, Modus)` die drei Modus-LEDs; im Modus 3 löscht der Patch TOUCH SCALE danach.
  Direkt über `0xC0028600` am Manager vorbei zu schreiben (so tat es ein früherer Stand), ließ die
  Kopie, die der Gerätemodus der Seite liest, TOUCH SCALE und MASTER FX vertauscht zeigen
  (`2026-10-14-led-zustand-ram.md`).
- **Zustand:** `FF` im Abbild heißt „aus“, ein Start-Code ist nicht nötig.

## Reihenfolge der Modi

Der Touch-Pad-Modus (0 Gate Arp allein, 1 Touch Scale allein, 2 Master FX, 3 Gate Arp + Touch
Scale) wird nur von GATE ARP, TOUCH SCALE und MASTER FX geändert. Die Firmware
(`SYSTEM-ringtest.VSB`, gemessen, alle zwölf Übergänge) macht:

| von \ Taste | GATE ARP | TOUCH SCALE | MASTER FX |
|---|---|---|---|
| 0 Gate Arp | 0 | 3 | 2 |
| 1 Touch Scale | 3 | 1 | 2 |
| 2 Master FX | 0 | 1 | 2 |
| 3 Gate Arp + Touch Scale | 0 | 1 | 2 |

**Was Gate Arp allein tut (gemessen, Firmware):** Sequenzer läuft, Trigger-Pad 3 gehalten, Touch-Pad
berührt, Noten am MIDI-Ausgang in 2 s:

| Modus | X = 100 | X = 500 | X = 900 | ohne gehaltenes Pad (X = 500) |
|---|---|---|---|---|
| 0 Gate Arp allein | 9 Noten, davon 7 das Pad (60) | 11, davon 9 das Pad | 25, davon 23 das Pad | keine |
| 3 Gate Arp + Touch Scale | 46: Pad (60) 22 mal, Skalenton (48) 22 mal | 46: Pad 22, Skalenton (53) 22 | 25: Pad 23, kein Skalenton | 22: Skalenton (53) |
| 1 Touch Scale allein | 4: ein Skalenton (48) | 4: ein Skalenton (53) | 4: keiner | 1: Skalenton (53) |

(Die Zählung enthält die Noten des Patterns selbst, 62 und 67, und die Note beim Drücken des Pads;
die Zahlen sind aus einem Lauf des Emulators, die Aussage steht in `mfx_cases.py run`.) Gate Arp allein wiederholt also
nur die Note des gehaltenen Pads, je nach X schneller oder langsamer (bei X = 900 so schnell wie Gate Arp + Touch Scale), und spielt keinen Skalenton.
Gate Arp + Touch Scale wiederholt das Pad (bei X = 500 doppelt so oft wie Gate Arp allein) und
spielt zusätzlich je Schritt einen Skalenton. Gate Arp allein ist damit **eigenständig**, nicht
dasselbe wie Gate Arp + Touch Scale. Es war nur über GATE ARP aus 2 oder 3 zu erreichen; die
Taste, die sonst dafür frei wäre, SHIFT + GATE ARP, ist der Sprung auf die Seite GATE ARP im
Pattern-Menü (`docs/tastenkombinationen.md`) und bleibt. Gate Arp allein ist darum im Patch nicht
erreichbar; mit EXIT beim Einschalten (Notschalter) ist es wie in der Firmware da.

**Festgelegt (13.10.):** Gate Arp allein ist nicht nützlich; GATE ARP soll aus jedem Modus direkt Gate Arp
+ Touch Scale geben (siehe oben), ein weiterer Druck bleibt ohne Wirkung. SHIFT + TOUCH SCALE ist die
Firmware-Taste (aus 3, 2 und 1 nach Touch Scale allein).

Geprüft in `mfx_cases.py run`: alle 64 Folgen aus drei Tasten (GATE ARP, TOUCH SCALE, SHIFT +
TOUCH SCALE, MASTER FX) mit Modus, LEDs, Effekttyp und MFX-2-Flag nach jeder Taste gegen die in der
Datei gemessene Tabelle der Firmware; mit EXIT beim Einschalten alle 9 Folgen aus GATE ARP, TOUCH SCALE
und MASTER FX, zwei tief, gleich der Firmware. Dazu die Noten am MIDI-Ausgang (Abspielen, Pad gehalten,
Touch-Pad berührt): nach GATE ARP, GATE ARP zweimal, TOUCH SCALE und dann GATE ARP, GATE ARP und dann
SHIFT + TOUCH SCALE sind sie gleich denen der Firmware im selben Modus.

## GATE ARP: nur die GATE-ARP-LED

**Festgelegt (14.10.):** die Firmware lässt bei GATE ARP die LEDs GATE ARP und TOUCH SCALE leuchten. Im Patch leuchtet nur die
GATE-ARP-LED, das Verhalten ist genau das von Gate Arp + Touch Scale (Pad je Schritt neu ausgelöst, dazu
ein Skalenton). Sonst gilt das oben Beschriebene: Start in MASTER FX, TOUCH SCALE ist MFX 2, SHIFT + TOUCH SCALE ist die
Firmware-Taste, EXIT beim Einschalten ist die Firmware.

**Wie die Firmware die LEDs für den Modus setzt (gemessen im Emulator, offline gelesen, `SYSTEM-ringtest.VSB`):**

- Die drei LEDs GATE ARP (`0x1a`), TOUCH SCALE (`0x1b`) und MASTER FX (`0x1c`) setzt `0xC0088118(LED-Verwaltung,
  Modus)`: je LED ein Byte aus der Tabelle `0xC00E5030` (drei Bytes je Modus, Modus 0 `01 00 00`, 1 `00 01 00`,
  2 `00 00 01`, 3 `01 01 00`; die LED-Nummern stehen in `0xC00E50FF`), schreibt es nach `LED-Verwaltung + 8 * LED
  + 0x4e` und ruft `0xC00875F4(…, LED, 0)`. Der Modus 3 ist also in den Daten der Firmware „GATE ARP an, TOUCH
  SCALE an“.
- Ausgelöst wird das einmal je Moduswechsel: die Taste ruft `0xC00819D8(Touch-Pad, Modus)`, das den Modus
  speichert und über die Signalliste `0xC0070688` die Meldung 5 an den Empfänger `0xC008963C` schickt; dessen
  Sprungtabelle hat für Meldung 5 den Eintrag `0xC00896E4`, der nach `0xC0088118` springt. Die Empfänger werden
  durch Funktionszeiger aufgerufen (hergeleitet: ohne Warteschlange; im Emulator stehen die LED-Nachrichten des
  Modus schon da, wenn die Taste zurückkehrt). Der zweite Aufrufer, `0xC0089A3C`, liegt im Startcode der LED-Task (Funktion `0xC0089730`,
  ein Eintrag in der Tabelle bei `0xC00E5118`) und setzt den Modus beim Start.
- **Gemessen:** solange der Modus 3 bleibt, schreibt die Firmware GATE ARP, TOUCH SCALE und MASTER FX nicht
  wieder (alle Panel-Nachrichten an `0x1a` bis `0x1c`, aufgezeichnet nach dem Wechsel: 3 s Leerlauf,
  Patternwechsel mit Rad, Pad und MIDI-Programmwechsel, Abspielen und Stopp, Menü und EXIT, Touch-Pad, WRITE, MFX
  HOLD, 19 weitere Tasten allein und mit SHIFT, 10 s Leerlauf: keine einzige).

**Was der Patch ändert:** nichts am Modus und nichts an den Tasten. `led_restore` (läuft am Ende jedes Tastenereignisses,
das der Patch behandelt, nach dem Aufruf der Firmware-Taste) schreibt für TOUCH SCALE `0` statt des Tabellenwerts,
wenn der Modus 3 ist. Die Tabelle und das Byte in der LED-Verwaltung bleiben, wie die Firmware sie hat (TOUCH
SCALE „an“); der Patch schickt nur die Panel-Nachricht für die LED. Weil die Firmware die LEDs nach dem Wechsel
nicht neu setzt, reicht dieser eine Aufruf, ein Nachhalten im Tick ist nicht nötig. Code: 1872 Byte, kein eigener Haken
für die LED, keine eigene Startphasen-Stelle.

**Verworfen:** das Byte für Modus 3 in der Tabelle `0xC00E5030` auf `01 00 00` ändern. Das wäre ein Datenbyte
statt Code, aber es gälte auch mit EXIT beim Einschalten (Modus 3 aus den Tasten der Firmware), der Notschalter
verspricht „nichts vom Patch wirkt“.

**Gemessen im Emulator (`mfx_cases.py run`, `cases`):**

- GATE ARP aus Master FX, aus MFX 2, aus Touch Scale und ein zweites Mal: Modus 3, LEDs GATE ARP an, TOUCH SCALE und
  MASTER FX aus. Mit EXIT beim Einschalten bleibt es die Firmware: beide LEDs.
- Gegen die unveränderte Firmware im selben Modus 3 (GATE ARP aus ihrem Startmodus): gleicher Bildschirm, Effekttyp,
  Modus und gleiches Display; der **einzige** Unterschied aller LEDs ist `0x1b` (Firmware 255, Patch 0).
- Danach SHIFT + TOUCH SCALE: Modus 1, GATE ARP aus, TOUCH SCALE an, gleich der Firmware (alle LEDs und das Display).
  Die 64 Tastenfolgen aus drei Tasten prüfen Modus, LEDs und Effekttyp nach jeder Taste, auch alle Wege aus und
  nach Modus 3.
- **MIDI-Ausgabe beim Spielen gleich wie vorher:** Sequenz läuft, Trigger-Pad gehalten, Touch-Pad berührt,
  2 s, nach GATE ARP, GATE ARP zweimal, TOUCH SCALE dann GATE ARP und GATE ARP dann SHIFT + TOUCH SCALE.
  (a) Alle Kanalnachrichten (Note an, Note aus, Controller; im Lauf 91 in Modus 3, davon 46 Note-ons, und 7 in
  Modus 1) sind gleich denen der Firmware im selben Modus; geprüft in `mfx_cases.py run` (Note-ons, Note-offs und der
  Rest). (b) Gegen den Patch ohne die LED-Änderung (aus dem Patch vom 13.10. auf
  `SYSTEM-ringtest.VSB` gebaut) sind die **rohen MIDI-Bytes** des ganzen Laufs in allen fünf Folgen gleich (342, 342, 342, 162 und 168 Byte,
  gemessen mit einem einmaligen Vergleichslauf, nicht als Dauerprüfung, weil der alte Patch nicht mehr im Repository liegt).
  Die einzige Differenz zwischen alt und neu in diesen Läufen sind die LEDs.
- **Offen am Gerät:** ob die TOUCH-SCALE-LED im Moment des Drucks sichtbar aufblitzt. Die Firmware schickt ihre
  Nachricht für den Modus 3 vor der des Patches (im Emulator `0x1b` 255, zwei Nachrichten später 0); wie weit das
  am Gerät auseinanderliegt, ist nicht gemessen. Dass der Ton und das Touch-Pad gleich bleiben, ist aus dem
  Vergleich der MIDI-Bytes hergeleitet; der Gerätetest (Schritt 7) prüft es.

## Startmodus

Der Touch-Pad-Modus nach dem Einschalten ist in der Firmware eine Konstante, kein Datenfeld
(gemessen im Emulator, Schreibzugriffe auf `*0xC06912E0 + 0x334` ab dem Einschalten, dazu
offline gelesen):

- Der Konstruktor des Touch-Pad-Objekts (`0xC0081838`, `mov r2, #1` bei `0xC0081810`) schreibt
  beim Start (52 ms) den Modus 1, Touch Scale. Vorher (30 ms) hat die Allokation das Objekt
  mit 0 gefüllt. Der Wert ist ein Befehlsoperand, er stammt nicht aus den Globals, dem Pattern
  oder dem Flash.
- Die LEDs folgen später (99,7 ms): ein Aufruf von `0xC0088118(LED-Verwaltung, Modus)` setzt
  GATE ARP, TOUCH SCALE und MASTER FX aus einer Tabelle (`0xC00E5030`, drei Bytes je Modus).
- Eine Taste setzt den Modus über `0xC00819D8(Objekt, Modus)` (speichert und stellt eine
  Meldung in die Warteschlange des Objekts; die LED-Funktion läuft dabei sofort, gemessen). Der
  Taste-Handler dafür ist `0xC006FF94` (r1 = Taste, gemessen beim Druck auf MASTER FX): nach
  mehreren Sperren (unter anderem Modus 4) ruft er für MASTER FX (Taste 6) ohne SHIFT
  `0xC00819D8(*0xC06912E0, 2)`. Der Patch erreicht ihn schon über den Tastendispatcher
  (TOUCH SCALE reicht Taste 6 weiter).

Zwei Wege, MASTER FX als Startmodus zu bekommen:

| Weg | Urteil |
|---|---|
| die Konstante im Konstruktor ändern (`mov r2, #2`) | verworfen: ein Wort in der Startphase, vor Panel-Austausch (69 ms) und Rettungswegen; der Notschalter ist dort noch nicht lesbar, EXIT beim Einschalten würde ebenfalls Master FX liefern |
| beim ersten Tick im Hauptbildschirm den Taste-Handler für MASTER FX aufrufen | gebaut |

Gebaut ist der zweite Weg im vorhandenen Tick-Haken (`boot_mode` in `mfx_switch.py`), hinter dem
Notschalter. Beim Tick prüft er: Zustandswort `S_BOOT` noch nicht gesetzt, Bildschirm des
Screen-Managers ist 1 (Hauptbildschirm). Dann setzt er `S_BOOT`, überspringt den Start, wenn beim
Einschalten irgendeine Taste gehalten war (die Startmodi der Firmware bleiben, wie sie sind) oder SHIFT
jetzt gehalten wird, prüft, dass der Modus Touch Scale (1) ist, und ruft `0xC006FF94` mit Taste 6. Einmal pro Einschalten; danach bedient die Firmware den Modus allein.
Kein neuer Haken, keine neue Einhängestelle im Register (die Beschreibung des Tick-Haken sagt,
dass er den Startmodus setzt). Im Emulator erscheint der erste Tick bei 179 ms im Bildschirm 0,
der erste im Hauptbildschirm bei 340 ms: die TOUCH-SCALE-LED leuchtet vom LED-Abgleich (99,7 ms)
bis dahin, dann wechselt sie auf MASTER FX. Wie lange das am Gerät sichtbar ist, ist nicht
gemessen.

## Belege

| Behauptung | Status | Befehl |
|---|---|---|
| Patch gleicht dem, was der Builder erzeugt; beide VSB ergeben denselben Patch | gemessen | `npm test` mit `E2_VSB` |
| Patch ändert nur genannte Bytes (Code und vier Wörter); die Start-Spans sind genannt | gemessen | `test/mfx-switch.test.mjs`, `check.py` (`start_phase`, ohne die Spans schlägt es fehl) |
| 56 Schritte des Laufs gegen die unveränderte Firmware, auf `SYSTEM-ringtest.VSB` und `SYSTEM.VSB`, alle bestanden | gemessen | `mfx_cases.py run` |
| GATE ARP: nur `0x1b` unterscheidet sich von der Firmware im Modus 3 (255 gegen 0); MIDI-Nachrichten gleich der Firmware; rohe MIDI-Bytes gleich dem Patch ohne LED-Änderung | gemessen | `mfx_cases.py run` (zwei Schritte); Vergleich mit dem Patch ohne LED-Änderung einmalig |
| Die Firmware setzt die drei Modus-LEDs nur im Moduswechsel, danach nicht mehr (Modus 3: keine Nachricht an `0x1a` bis `0x1c` in 10 s Leerlauf, Patternwechseln, Spielen, Menüs, WRITE, 19 Tasten) | gemessen | Panel-Nachrichten im Emulator, Disassembly `0xC0088118`, `0xC00819D8` |
| Alle Startwege bestehen: allein 28 von 28 (`SYSTEM-ringtest.VSB`) und 28 von 28 (`SYSTEM.VSB`) mit den Start-Spans des Patches | gemessen | `check.py --flash` |
| Nach jeder Taste einer Folge (MFX 2, MASTER FX, GATE ARP, SHIFT + TOUCH SCALE, Patternwechsel) ist die Kopie des LED-Managers (`+ 0x88c + 8 * LED`, Byte 2) für `0x1a` bis `0x1d` gleich dem, was zuletzt an die Panel-UART ging; im Modus 3 nur GATE ARP an. Dieselbe Prüfung schlägt gegen den Patch mit dem direkten LED-Weg fehl (Kopie vertauscht) | gemessen | `mfx_cases.py cases` (`mfx:led_copy`), `mfx_cases.py run` (alle 64 Dreierfolgen und neun Zweierfolgen mit EXIT) |
| Gerätedatei `SYSTEM-blech-v6.VSB` (sha256 `ec4a54e17036e3d18cdc38ed4028402326aee9962a7feffa186fca738fb652fe`, `SYSTEM.VSB` (`b0890899…`) + Startbild-Editor + MFX 2 + Blech-Startbild): `mfx_cases.py run` 56 von 56 und `check.py` 38 von 38 (Startbild-Editor-Fälle eingeschlossen), `splash_cases.py run` 36 von 36, alle mit dem Flash-Dump vom 9.10. Ohne `--flash` schlagen zwei Schritte von `run` (MIDI-Programmwechsel, Flash-Sektoren) und je ein Schritt von `check.py` und `splash_cases.py` fehl (für `run` und `splash_cases.py` an einem früheren Stand gemessen, dort fehlt der Flash-Sektor ebenso) | gemessen | `check.py --flash`, `mfx_cases.py run --flash`, `splash_cases.py run --flash` |
| Startmodus: nach dem Einschalten Modus 2, MASTER FX-LED an, eigener Typ, gleiches Display und LEDs wie die Firmware nach einem Druck auf MASTER FX; mit EXIT gehalten Modus 1, TOUCH SCALE-LED an, `S_BOOT` nie gesetzt, gleich der Firmware; mit SHIFT, REC oder dem Startmodus XY-Pad-Check gehalten wie die Firmware | gemessen | `mfx_cases.py run` (Schritte „start“), `cases` (`mfx:boot_mode`, `mfx:exit_held_boot_mode`) |
| Die Firmware setzt den Startmodus als Konstante im Konstruktor, nicht aus Globals, Pattern oder Flash | gemessen + offline | Schreibzugriffe auf `*0xC06912E0 + 0x334` im Emulator (2 Schreibungen: Allokation 0, Konstruktor 1), Disassembly `0xC0081810` |
| EXIT ist am Gerät Bit 13 | gemessen am Gerät (10.10.) | `docs/messungen/2026-10-10-rueckweg-geuebt.md` |
| Der Ton ändert sich am Gerät wie bei einer Menü-Änderung | hergeleitet (gleiche Funktion, gleiche DSP-Nachrichten), am Gerät offen | |

## Gemessen im Emulator (`mfx_cases.py run`)

- **Andere Tasten:** 14 Tasten allein (darunter MASTER FX, ohne GATE ARP und TOUCH SCALE) und 9 mit SHIFT
  gleichen der unveränderten Firmware: Bildschirm, MFX-Typ, LEDs, Touch-Pad-Modus,
  Display. Das Blinken der TAP-LED (`0x14`, folgt dem Tempo) ist ausgenommen.
- **SHIFT + TOUCH SCALE = die alte Taste:** GATE ARP, dann zweimal SHIFT + TOUCH
  SCALE ergibt dieselben LEDs und denselben Modus (Touch Scale allein) wie GATE ARP, dann zweimal die Firmware-Taste.
  Von MFX 2 aus: eigener Typ, dann das, was die Firmware-Taste aus dem Master-FX-Modus macht.
- **Notschalter:** mit EXIT beim Einschalten verhalten sich TOUCH SCALE, SHIFT + TOUCH
  SCALE und GATE ARP wie in der Firmware, kein Zustand des Patches.
- **TOUCH SCALE:** Typ 1 → 6 (Display „07 Looper“, auf beiden VSB), Modus 2, LEDs
  TOUCH SCALE an, MASTER FX und GATE ARP aus. DSP-Übertragungen gleich dem direkten Aufruf
  der Firmware-Funktion. Noch einmal: nichts ändert sich. MASTER FX: eigener Typ, MASTER FX
  an, TOUCH SCALE aus, DSP gleich dem Wechsel zurück. GATE ARP von MFX 2 aus: eigener Typ,
  Modus 3, nur GATE ARP an (nur die GATE-ARP-LED, die Firmware lässt beide leuchten).
- **Patternwechsel bei MFX 2:** Rad (+1, +1, −2, +5), Pad (nach PATTERN SET) und MIDI-
  Programmwechsel (Kanal 10, Programm 12): jeweils MFX 2 des neuen Patterns, Modus 2, LEDs
  stimmen 0,5 s danach, der eigene Typ jedes Patterns stimmt mit dem der Firmware überein,
  MASTER FX danach gibt den eigenen Typ des neuen Patterns (nichts leckt). Beim Abspielen
  (PLAY): das Rad löst den Wechsel verzögert aus wie in der Firmware (nach 3 s Abspielen gleiche Pattern-Nummer), MFX 2 bleibt an.
- **WRITE:** bei MFX 2 ist das gespeicherte Pattern Byte für Byte das der unveränderten
  Firmware (eigener Typ, nicht MFX 2); MFX 2 bleibt danach an; ohne geänderte Tabelle bleibt
  der Tabellen-Sektor `FF`.
- **MFX 2 wählen und speichern:** bei MFX 2 wählt VALUE auf der Seite MFX TYPE MFX 2 dieses
  Patterns; MASTER FX, dann TOUCH SCALE bringt den gewählten Typ zurück; WRITE speichert
  Datensatz (gültig: Kennung, Version, Länge, CRC-32; nur der Eintrag dieses Patterns gesetzt)
  und den eigenen Typ; nach einem Neustart mit diesem Flash gilt der gewählte Typ für dieses
  Pattern und der Vorgabewert für ein anderes. Ein Datensatz mit gekipptem Bit, falscher
  Kennung, halb geschrieben, oder ein Eintrag außerhalb von 1 bis 100: Vorgabe. Geändert sind
  nur der Slot des Patterns und der Tabellen-Sektor. Ohne MFX 2 ändert die Seite MFX TYPE
  den Typ wie in der Firmware und berührt die Tabelle nicht.
- **MFX HOLD:** der gehaltene Zustand (Pattern-Byte 65) bleibt beim Wechsel unverändert.
- **Seite MFX TYPE:** nach dem Druck steht der neue Name sofort da (gleiches Bild wie nach
  erneutem Aufbau); zehn schnelle Paare auf der Seite ohne Assertion.
- **Der Typ des Patterns ist schon MFX 2:** TOUCH SCALE schaltet den Modus ein, ohne Effektwechsel.
- **Zwölf schnelle Drücke** (sechs Paare) wechseln sauber.
- **`check.py`:** allein 28 von 28 (die fünf Start-Spans des Patches, ohne sie schlägt
  `start_phase` fehl), auf `SYSTEM.VSB` und `SYSTEM-ringtest.VSB`; zusammen mit dem
  Startbild-Editor und dem Blech-Startbild 37 von 37 auf `SYSTEM-ringtest.VSB`.

## Gefunden, nicht Teil dieser Änderung

- **Startbild-Editor, Zeitabhängigkeit (gemessen):** nach WRITE zeichnet der Editor das
  Bild neu, sobald das Fenster „Working...“ weg ist. In `splash_cases.py run` scheitert
  dieser Schritt (das Display zeigt die Seite SPLASH SCREEN statt des Bildes), wenn der
  WRITE-Druck um 10 ms verschoben wird, auch ohne den MFX-Patch (gemessen mit dem
  Startbild-Editor allein). Gespeichert wird richtig; betroffen ist nur die Anzeige nach WRITE,
  EXIT bleibt möglich. Nicht angefasst. Im Lauf mit beiden Patches besteht dieser Schritt
  (36 von 36), die Verschiebung hängt an der Zeit.

## Risiken beim Einsatz am Gerät

- **Haken in jedem Tastenereignis und jedem Tick:** der Code läuft bei jedem Tastendruck
  (nicht bei Pads, Reglern, Touch-Pad) und 22 Mal pro Sekunde im Tick. Im Tick tut er im
  Normalfall (MFX 2 aus) nur den Notschalter-Test und eine Abfrage. Ein Fehler, der nur am
  Gerät auftritt, könnte die Bedienung stören. Rettung: EXIT beim Einschalten halten, dann
  ist der Patch aus (EXIT ist am Gerät Bit 13, gemessen 10.10.).
- **Flash beim WRITE:** hat man MFX 2 verändert, schreibt WRITE zusätzlich einen 4-KiB-
  Sektor (`0x7E8000`) vor dem Pattern. Das dauert länger, die Firmware macht es für das
  Pattern ohnehin. Bricht der Strom dabei ab, ist der Datensatz ungültig (Vorgabe) oder
  noch der alte, das Pattern ist davon unabhängig. Der Sektor liegt hinter dem Bereich,
  den Korgs Update schreibt (bis `0x7E0000`); ob ein Update ihn trotzdem löscht, ist nicht
  gemessen.
- **Ton ungeprüft:** der DSP-Verkehr gleicht dem Menü-Wechsel; ob Looper am Gerät sofort
  sauber startet und ob der Wechsel knackt (die Firmware tauscht die Master-Stufe), ist nur
  am Gerät zu hören.
- **Patternwechsel:** zwischen Laden und nächstem Tick (bis 45 ms) läuft das neue Pattern kurz mit
  seinem eigenen Effekt, dann schaltet MFX 2 um, hörbar möglich.
- **RAM-Lesen durch den Editor:** liest der Editor das Pattern aus dem Gerät, während MFX 2
  an ist, sieht er MFX 2 als Typ. Der Patch schreibt nichts davon in den Flash.
- **Verlorene Funktion:** SHIFT + TOUCH SCALE springt nicht mehr auf die Menüseite SCALE
  (der Weg über MENU bleibt).
- **MFX 2 gehört zum Pattern-Platz, nicht zum Inhalt:** kopiert man ein Pattern in einen
  anderen Platz, gilt dort dessen Eintrag.

## Schritte für den Gerätetest

1. `SYSTEM-blech-v6.VSB` (Startbild-Editor, MFX 2, Blech-Startbild)
   wie beim Rückweg-Versuch (`2026-10-10-rueckweg-geuebt.md`) über die SD-Karte und DATA UTILITY einspielen, am Netzteil; die Originaldatei
   (`163d1d8d…`) bleibt als Rückweg bereit.
2. Beim Einschalten **EXIT halten**: Gerät startet, TOUCH SCALE verhält sich wie vorher.
   Ausschalten.
3. Normal einschalten: MASTER FX-LED an, TOUCH SCALE-LED aus (Startmodus). Pattern mit Delay als Master-Effekt. TOUCH SCALE: Touch-Pad im
   Master-FX-Modus, TOUCH SCALE-LED an, MASTER FX-LED aus, Effekt ist 07 Looper (MENU, MFX
   TYPE, zeigt „07 Looper“). MASTER FX: Delay zurück, MASTER FX-LED an, TOUCH SCALE-LED aus.
   TOUCH SCALE noch einmal drücken: nichts passiert.
4. MFX 2 wählen: TOUCH SCALE, MENU, Seite MFX TYPE, VALUE auf den Wunschtyp, EXIT. MASTER FX,
   dann TOUCH SCALE: der gewählte Typ kommt. WRITE zweimal (wie immer), Gerät aus und an,
   dasselbe Pattern: TOUCH SCALE gibt den gewählten Typ; ein anderes Pattern gibt 07 Looper.
5. Mit MFX 2 an das Pattern wechseln (Rad, Pad): Modus und LEDs bleiben, der neue Effekt ist
   MFX 2 des neuen Patterns. MASTER FX: sein eigener Effekt.
6. Mit MFX 2 an WRITE: gespeichertes Pattern öffnen, sein Effekt ist der eigene (nicht MFX 2).
7. GATE ARP (aus Master FX, aus MFX 2, aus Touch Scale): **nur die GATE-ARP-LED leuchtet**, TOUCH SCALE
   und MASTER FX sind dunkel (kurzes Aufblitzen der TOUCH-SCALE-LED beim
   Druck wäre ein Befund, der Patch löscht sie im selben Tastenereignis). Bei laufender Sequenz
   ein Trigger-Pad halten und das Touch-Pad berühren: das Pad wird je Schritt ausgelöst, dazu
   ein Skalenton, wie bei Gate Arp + Touch Scale der Firmware. Noch einmal GATE ARP: nichts ändert sich. MFX 2 geht mit GATE ARP aus (eigener
   Effekt kommt zurück). SHIFT + TOUCH SCALE: Touch Scale allein (TOUCH SCALE-LED an), MFX 2 geht dabei aus.
8. Das Ganze bei laufender Sequenz, Ton auf Knackser achten. MFX HOLD bei MFX 2 ausprobieren.
9. Wenn etwas hängt: ausschalten, EXIT halten beim Einschalten, Original zurück.

## Offen

- Der Ton am Gerät, das Knacken beim Wechsel.
- Eine eigene Menüseite „MFX 2“ (Global Seite 21 im Startbild-Editor, oder Pattern-Menü
  nach MFX TYPE): nicht gebaut, siehe oben. Die Tabelle und die Haken bleiben dieselben.
- Zeigt das Gerät beim Laden eines Patterns kurz den eigenen Effekt (bis zu 45 ms)?
