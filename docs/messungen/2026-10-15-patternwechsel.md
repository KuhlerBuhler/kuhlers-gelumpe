# Patternwechsel erst nach Bestätigung (Idee 46): gebaut und im Emulator geprüft

Stand 2026-10-15. Alles im Emulator (`tools/emu`, Unicorn 2.1.4) mit der eigenen `SYSTEM.VSB`
(Hacktribe 2.02) und dem eigenen Flash-Dump vom 9.10., Code offline mit Capstone gelesen.
**Am Gerät nichts geprüft.** Recherche und Entwurf: [Patternwechsel](../hintergrund/patternwechsel.md),
Idee: [Idee 46](../ideen/46-patternwechsel-bestaetigung.md). Markierungen: **gemessen**,
**hergeleitet**, **offen**.

## Was gebaut ist

Der Patch `data/patches/pattern-switch.json`, erzeugt von `tools/patch/pattern_switch.py`
(968 Byte Code ab `0xC0180000`, Zustand ab `0xC0180F00`, nur RAM). Er liegt im Patch-Satz BLECH.

| Haken | Stelle | Wirkung |
|---|---|---|
| Rad | Aufruf von `0xC008206C` in `0xC006513C` | beim Spielen `set_number(psel, n, 0)` ohne MIDI, Merker "blättert" |
| Pad | erster Befehl von `0xC006EDE4` | löscht Blättern und Bestätigung |
| MIDI Program Change | erster Befehl von `0xC006EE00` | ebenso |
| MENU | Platz `+0x18` der Klasse des Hauptbildschirms, `0xC00E34B0` | bestätigt: Nummer merken, `set_number(psel, n, 1)` (Bank Select und Program Change gehen jetzt raus) |
| EXIT | Platz `+0x08`, `0xC00E34A0` | nimmt Blättern oder Bestätigung zurück |
| Sequenzende | Aufruf von `0xC00818D8` in `0xC005F1C4` | liefert die bestätigte Nummer, beim Blättern die laufende, sonst wie bisher; liest nur (Engine-Task) |
| STOP | erster Befehl von `0xC0081B5C` | verwirft ein Blättern, wendet eine Bestätigung an wie die Firmware |
| Zeile unten | Laden von `NEXT:` in `0xC0086DC4` | beim Blättern `VIEW:`, nach der Bestätigung `NEXT:` |

Keiner der Haken liegt vor dem Hauptbildschirm. Alle geben die Firmware zurück, wenn EXIT beim
Einschalten gehalten wurde, keine Karte gemountet ist (`FatFs[0]->fs_type` ist 0, `0xC06A010C`) oder
das Einstellungswort `PS_SETTING` (`0xC0180F10`) 0 ist. Nie geschrieben (`0xFFFFFFFF`) oder 1 heißt an,
das ist die Voreinstellung. Das Wort schreibt das BLECH-Menü (siehe unten, "Was das Menü ergänzen muss").

Die Kette `pattern-set` in `data/hooks.mjs` hat jetzt eine Stufe für `set_number` hinter den drei
Einstiegen. Der Haken am Rad ersetzt den Sprung in die Auswahl und ruft `set_number` selbst, die Plugin-
Laufzeit hängt an `set_number` (`patternChange`) und sieht die Nummer also weiter. Der alte Test, der
beide als unverträglich abgelehnt hat, ist ein Test auf "angenommen" geworden.

## Gemessen (Prüfungen `pswitch:*` in `check.py`, `tools/emu/pswitch_cases.py`)

| Fall | Ergebnis |
|---|---|
| Referenz: dieselbe Kopie mit EXIT beim Einschalten | jeder Klick sendet Program Change, die gewählte Nummer startet am Sequenzende (nach 5,99 s) |
| blättern, nicht bestätigen | laufende Nummer bleibt, gewählte Nummer vorgemerkt, **kein** MIDI, Zeile unten nur in den Seiten 6 und 7 anders (`VIEW:`), nach 7 s läuft das alte Pattern weiter |
| blättern, MENU | Program Change einmal beim MENU, Wechsel **zur selben Zeit** wie bei der Firmware (Unterschied höchstens 30 ms Abtastung), danach sauber (Merker 0), das neue Pattern läuft weiter |
| nach der Bestätigung weiter blättern | die bestätigte Nummer startet, nicht die weiter geblätterte |
| zurück auf die laufende Nummer blättern | nichts vorgemerkt, nichts bestätigt |
| EXIT beim Blättern | gewählte Nummer zurück auf die laufende, kein MIDI, nie ein Wechsel |
| EXIT nach der Bestätigung | Program Change für die laufende Nummer geht raus, nie ein Wechsel |
| weiter geblättert, EXIT | erst zurück auf die bestätigte Nummer, ein zweiter EXIT nimmt die Bestätigung |
| Stillstand, SHIFT + Rad | Nummer, MIDI (9 Nachrichten) und Display gleich denen der Firmware |
| MENU, EXIT ohne Vorgemerktes | Bildschirm und Display gleich denen der Firmware |
| STOP beim Blättern | das spielende Pattern bleibt, nichts vorgemerkt (die Firmware wendet das Vorgemerkte an) |
| STOP nach der Bestätigung | das bestätigte Pattern wird angewendet, wie bei der Firmware |
| Kette Pattern 5 zu 10 | ohne Blättern, mit Blättern: die Kette läuft zur selben Zeit; bestätigt gewinnt die bestätigte Nummer (wie bei einer vorgemerkten) |
| Pad, MIDI Program Change nach dem Blättern | die bewusste Wahl gewinnt, startet am Sequenzende wie bei der Firmware, Merker gelöscht |
| Rad Umlauf und SHIFT | `-1` von 0 gibt 249, SHIFT + 1 sind 10 und laufen um (9), gleich der Firmware |
| EXIT beim Einschalten, keine Karte, Einstellung 0 | jeder Klick sendet Program Change, die Nummer ist vorgemerkt, MENU und EXIT ändern nichts, der Zustand des Patches bleibt unberührt |
| mit MFX 2 im Satz | Blättern ändert den Effekttyp nicht, nach dem Wechsel ist MFX 2 für das neue Pattern an wie ohne den Patch |
| `check.py` auf der Kopie | alle Prüfungen der Startwege bestehen (Boot mit und ohne Flash, Update-Abfrage, Panel-Update, alle Startmodi, EXIT), **keine** `startPhase`-Ausnahme nötig |

## Wie das Gerät den Wechsel entscheidet (gemessen, bestätigt den Entwurf)

Die Firmware merkt sich nur die Nummer `psel+0x318` und das Flag `psel+0x341`; am Sequenzende holt die
Engine die Nummer über `0xC00818D8`. Der Patch ersetzt genau diese eine Abfrage. Wird die laufende Nummer
zurückgegeben, wiederholt oder verkettet das Pattern wie ohne Vormerkung (`player_change` mit der
laufenden Nummer). Die Zustandswörter gelten nur, solange das Flag gesetzt ist; was die Firmware selbst
löscht (Kette, Rückkehr auf die laufende Nummer), wird beim nächsten Rad-Klick bereinigt.

## Was das Menü ergänzt (gebaut, 15.10.)

Die Seite PATTERN CONFIRM (ON, OFF) steht als neunte Seite in der Gruppe CUSTOMIZATION ("Custom 9/9", Art 18 in `menu_kind`).

1. Ein Bit in den **Flags der Einstellungsdatei** (`settings.a/b.bin`, das Wort bei `+12`): Bit 2,
   gesetzt heißt **aus**. Die Bedeutung ist so umgekehrt, damit eine bestehende Datei, in der Bit 2 immer 0 ist,
   weiter "an" heißt. Die Datei bleibt Version 2, die älteren Leser ignorieren das Bit, die Prüfsumme gilt wie bisher.
   Es stößt weder an die Bits 0 und 1 der Flags (Laufzeit, MFX 2) noch an das Look-Wort bei `+16` (Bit 28 DISPLAY INVERT).
2. Beim Laden der Datei (`menu_settings_load`, nach dem Lesen der Flags) und bei jedem Umschalten wird das Wort
   `0xC0180F10` geschrieben: `1` für an, `0` für aus. Fehlt die Datei oder ist sie ungültig, wird nichts geschrieben
   (bleibt `0xFFFFFFFF`, an). EXIT beim Einschalten lässt das Menü ungerüstet, das Wort bleibt `0xFFFFFFFF`.
3. Die Seite gilt sofort beim Drehen, gespeichert wird mit WRITE wie die anderen Einstellungen.

**Gemessen** (Emulator, `menu:confirm_*` in `tools/emu/menu_cases.py`, Satz BLECH auf Hacktribe 2.02): Vorgabe ON mit Karte ohne Datei und
ohne Karte, das Wort bleibt `0xFFFFFFFF`, eine Datei ohne das Bit schreibt 1; die Seite zeigt "PATTERN CONFIRM" und ON, Zähler 9 von 9;
das Rad stellt das Wort sofort auf 0 und 1; WRITE legt Bit 2 in die Flags (Flags 7 statt 3), das Look-Wort bleibt; der nächste Start liest es
(Zustand 0, Wort 0, die Seite zeigt OFF); ON und WRITE löscht das Bit; eine beschädigte Datei wird ignoriert, eine Version-1-Datei mit dem Bit
gilt; EXIT beim Einschalten: Wort `0xFFFFFFFF`. Wie das Wort auf den Patch wirkt, zeigen die Fälle in
`tools/emu/pswitch_cases.py` (die Vergleichsläufe mit dem Wort 0).

## Grenzen und offen

- **Am Gerät nichts geprüft**, auch nicht das Timing von MENU im letzten Takt: wer MENU im letzten Tick
  drückt, kann den Wechsel um ein Pattern verpassen (die Entscheidung fällt 22 ms vor dem ersten Takt des neuen,
  Entwurf 1.5).
- Das Wartend-Flag `0xC068FC64` bleibt beim Blättern gesetzt (Firmware-Verhalten, gemessen: die Notenfolge
  bleibt gleich); was die Firmware damit in `0xC005CDE4` macht, ist offen.
- Nicht geprüft: WRITE und Bearbeiten (Fenster 0x1B) während des Blätterns, Song-Modi, Blättern über Minuten
  am Stück (Entwurf: 40 s).
- Ohne gemountete Karte (`FatFs[0]->fs_type == 0`) bleibt alles wie im Original, auch bei Voreinstellung "an":
  das Einstellungswort kommt von der Karte, ohne Karte gibt es keinen Nutzerwunsch.
- Ob die Lücke beim Wechsel (Effekt-Neuinitialisierung, siehe Hintergrund) durch den Patch verschwindet:
  nein, der Patch ändert nur, wann gewechselt wird.
