# Tastenkombinationen: SHIFT, Halten, Einschalten

Zweck: welche Tastenkombinationen der electribe sampler (Firmware 2.02 mit Hacktribe) kennt,
was sie bewirken und woher die Angabe stammt. Stand 2026-10-10.

So wurden die Angaben gewonnen: Alles, was mit "gemessen" markiert ist, lief im Emulator
(`tools/emu/machine.py`, Unicorn 2.1.4) mit einer unveränderten eigenen `SYSTEM.VSB` und
dem eigenen Flash-Dump vom 9.10. Die geprüfte VSB wird am Anfang ihres SHA-256 erkannt
(`b0890899cbe5951d`). **Am Gerät wurde nur die Ein/Aus-Taste geprüft** (Abschnitt 4), sonst
nichts.

Markierungen:

- **gemessen**: im Emulator ausgeführt und beobachtet (Display, LEDs, RAM, MIDI-Ausgang).
- **Handbuch**: Hinweis auf eine Fundstelle bei Korg (Owner's Manual EFGSCJ3 = OM, Parameter
  Guide E3, Anhang "Shortcut list", Seite 11 = PG, Korg FAQ 367, Hacktribe-Wiki "Test-Mode").
  Die Seitenzahl zeigt nur, wo es steht, der Text ist nicht übernommen.
- **offline**: im Firmware-Code gelesen (Adressen im Abbild, `0xC0...`).
- **Hacktribe**: Das Hacktribe-Wiki dokumentiert keine eigenen Kürzel, und im Tasten-Code
  ist nichts Hacktribe-Typisches aufgefallen. Ein Vergleich mit der unveränderten
  Korg-Firmware war nicht möglich (liegt hier nicht vor), die Aussage "alles Stock" ist
  also **hergeleitet**, nicht gemessen. Die Startmodi gelten laut Wiki für jede
  electribe 2, mit oder ohne Hacktribe.

Tastenbezeichnungen wie auf dem Gerät: Taste "1" bis "4" sind die vier Schritt-Tasten
(Panel-Nummern `0x1c` bis `0x1f`), "Pad 1" bis "Pad 16" die Trigger-Pads, "Touchpad"
das X/Y-Feld. Nummern siehe `data/panel.mjs`.

## Die zehn nützlichsten

1. **SHIFT + Pad 1 bis 16** springt direkt auf die Einstellseite (SWING, LENGTH, KEY, SCALE,
   GATE ARP, GROOVE, MOTION SEQ, STEP EDIT, COPY PART, CLEAR ..., METRONOME). Kein Menü-Blättern.
2. **SHIFT + EDIT<** nimmt die letzte Einzelaktion zurück (Reglerwert, Schritt-Eingabe).
3. **SHIFT + VALUE** wählt Patterns in 10er-Schritten.
4. **SHIFT + TAP** öffnet BPM; mit SHIFT gehalten VALUE drehen gibt 0,1-BPM-Schritte.
5. **SHIFT + PLAY** startet das Pattern von vorn (auch während es läuft).
6. **SHIFT + PART MUTE** hebt alle Stummschaltungen auf einmal auf.
7. **SHIFT + WRITE** öffnet die Namenseingabe (Pattern als Kopie speichern).
8. **TRIGGER / SEQUENCER / KEYBOARD / CHORD halten + Pad** wählt den Part, ohne dass es klingt
   oder ein Schritt gesetzt wird (MIDI-Ausgang bleibt stumm).
9. **PATTERN SET halten + Pad** legt das aktuelle Pattern auf das Pad; danach ruft PATTERN SET + Pad es ab.
10. **SHIFT + SAMPLE/OSC** springt kategorieweise, **SHIFT + IFX TYPE** in 10er-Schritten durch die Effekte.

## 1. SHIFT + Taste

Alle 34 anderen Tasten wurden einzeln mit SHIFT gedrückt, im Stand, beim Abspielen, in den
Modi SEQUENCER, KEYBOARD, TRIGGER, PART MUTE, CHORD, STEP JUMP, PATTERN SET, im Menü,
im WRITE-Fenster, bei GATE ARP und in mehreren Einstellseiten. Wenn nichts anderes
steht, gilt die Zeile in allen diesen Zuständen.

| Kombination | Wirkung | Beleg |
|---|---|---|
| SHIFT + REC | Fenster "Sampling Mode" (Quelle wählen), die REC-LED **blinkt** (Sampling-Bereitschaft) statt wie bei REC dauernd zu leuchten; die Pattern-Aufnahme startet nicht. Nur im Stand: beim Abspielen passiert nichts. | gemessen (Fenster Art 42, im Lauf aus), Handbuch PG S.11, offline `0xC006F6B4` |
| SHIFT + STOP | nichts | gemessen, offline: der STOP-Zweig liest SHIFT nicht |
| SHIFT + PLAY | Pattern von vorn: beim Abspielen springt die Schrittzahl von 12 auf 1 und läuft weiter, im Stand startet es ab Anfang. Ohne SHIFT pausiert PLAY beim Abspielen. | gemessen (Schrittzähler `0xC031668C`), Handbuch PG S.11, offline `0xC008308C` |
| SHIFT + TAP | Pattern-Seite 0 BPM. Zählt nicht als Tap-Tempo (der Tap-Zweig wird übersprungen). | gemessen, Handbuch PG S.11, offline `0xC006F7B4` und `0xC0042CA4` |
| SHIFT + GATE ARP | Pattern-Seite 10 GATE ARP. Der Touchpad-Modus bleibt, wie er war. | gemessen, Handbuch PG S.11, offline `0xC006FFFC` |
| SHIFT + TOUCH SCALE | Pattern-Seite 8 SCALE. Touchpad-Modus bleibt. | gemessen, Handbuch PG S.11, offline `0xC007003C` |
| SHIFT + MASTER FX | Pattern-Seite 5 MFX TYPE. Touchpad-Modus bleibt. | gemessen, Handbuch PG S.11, offline `0xC0070094` |
| SHIFT + MFX HOLD | nichts | gemessen |
| SHIFT + EDIT< | Rückgängig. Fenster "Undo!"; gibt es nichts zurückzunehmen, folgt "Error / Cannot Undo". Zurückgenommen wurden Reglerwert und Schritt-Eingabe, ein Patternwechsel nicht. | gemessen, Handbuch PG S.11 (ab System 2.00) und OM S.5, offline `0xC0070164` |
| SHIFT + EDIT> | Auf dem Hauptbildschirm nichts. **Im Menü** springt es auf die erste Seite der nächsten Menügruppe: Pattern, Part, Step, Part Util, Sample, Global, Data Util, Event, dann wieder Pattern. SHIFT + EDIT< macht dort dagegen Undo, einen Weg zurück gibt es nicht. | gemessen (alle 29 Menüeinträge), **nicht im Handbuch**, offline `0xC00676DC` (Menü-Klasse Pattern: SHIFT und Cursor nach rechts) |
| SHIFT + MENU | wie MENU (Menü öffnen, im Menü eine Ebene tiefer) | gemessen |
| SHIFT + EXIT | wie EXIT | gemessen |
| SHIFT + WRITE | Namenseingabe "enter NAME" (Pattern unter neuem Namen speichern). Im Zielwahl-Fenster "select DESTINATION" springt es ebenfalls auf die Namenseingabe. | gemessen, Handbuch OM S.5 und S.12, PG S.11, offline `0xC006F15C` |
| SHIFT + Part< / Part> | nichts Besonderes, der Part wechselt wie ohne SHIFT | gemessen |
| SHIFT + PART MUTE | Hebt die Stummschaltung **aller 16 Parts** auf (im Pattern-Puffer gehen die 16 Stumm-Bytes auf 0, alle Pad-LEDs rot). Der Modus selbst schaltet nicht um. Mit BLECH in der Vorschau (`VIEW:`, `NEXT:`) schaltet es stattdessen die Pads zwischen angesehenem und laufendem Pattern um ([Messung](messungen/2026-10-30-vorschau-part-reinholen.md)) | gemessen, Handbuch PG S.11, offline `0xC007042C` (Schleife über 16 Parts) |
| SHIFT + PART ERASE | wie PART ERASE allein: der Modus PART ERASE geht an (LED `0x21` auf 255), Display und Pattern bleiben, wie sie sind. Mit dem Patch Würfeln würfelt die Kombination eine Melodie und der Modus bleibt aus | gemessen, 2026-10-16 ([Messung](messungen/2026-10-16-wuerfeln.md)) |
| SHIFT + TRIGGER, SEQUENCER, KEYBOARD, STEP JUMP, PATTERN SET, MFX SEND | wie ohne SHIFT | gemessen, offline: die Modus-Tasten lesen SHIFT (`0xC006FF60`), reagieren aber nur bei CHORD |
| SHIFT + CHORD | Pattern-Seite 9 CHORD SET. Der Chord-Modus schaltet trotzdem um. | gemessen, Handbuch PG S.11, offline `0xC006FF60` (SHIFT und Taste 0x18) |
| SHIFT + LPF, HPF, BPF | wie ohne SHIFT (Filtertyp wechseln) | gemessen |
| SHIFT + 1, 2, 3, 4 | nichts | gemessen |
| SHIFT + AMP EG, IFX ON | wie ohne SHIFT | gemessen |
| SHIFT + Touchpad berühren | nichts | gemessen |

Zur Orientierung: ohne SHIFT öffnen GATE ARP, TOUCH SCALE und MASTER FX keine Seiten, sie
schalten die drei Touchpad-Modi um (Touch Scale allein, Gate Arp + Touch Scale, Gate Arp allein,
Master FX; Näheres in `docs/messungen/2026-10-10-mfx-umschalter.md`).

## 2. SHIFT + Regler und Drehgeber

Die Drehgeber (VALUE, SAMPLE/OSC, CUTOFF, MOD. TYPE, IFX TYPE) wurden mit +1 und -1 je zweimal
gedreht, die elf Regler mit zwei Sprüngen.

| Kombination | Wirkung | Beleg |
|---|---|---|
| SHIFT + VALUE, Hauptbildschirm | Pattern in **10er-Schritten**: 1 geht auf 21, rückwärts von 1 auf 231 (250 Patterns). | gemessen, Handbuch PG S.11, offline `0xC0065110` |
| SHIFT + VALUE, Seite BPM | 0,1 BPM pro Klick statt 1,0 BPM | gemessen, Handbuch PG S.3 und OM S.5, offline `0xC00675E0` |
| SHIFT + VALUE, Seite CHAIN TO | 10 Patterns pro Klick | gemessen, offline `0xC0066314` (Schrittweite 10 statt 1) |
| SHIFT + VALUE, übrige 27 Menüeinträge | kein Unterschied bei einem Klick (je Gruppe die erste Seite geprüft) | gemessen |
| SHIFT + VALUE, Zielwahl nach WRITE | kein Unterschied, auch hier 1 Pattern pro Klick | gemessen |
| SHIFT + VALUE, Step Edit, STEP NUMBER | ein **ganzer Takt** statt eines Schritts (1:01 geht auf 2:01 statt 1:02) | gemessen, Handbuch PG S.5, offline `0xC008DB80` |
| SHIFT + VALUE, Step Edit, NOTE | **Oktave** statt Halbton (C 04 geht auf C 05 statt C#04) | gemessen, Handbuch PG S.5, offline `0xC008E7BC` |
| SHIFT + VALUE, Step Edit, GATE TIME | **1** statt 10 pro Klick (72 geht auf 73 statt 82), also feiner, nicht gröber | gemessen, nicht im Handbuch |
| SHIFT + VALUE, Step Edit, VELOCITY und OSC EDIT MOTION | **10** statt 1 pro Klick (96 geht auf 106) | gemessen, nicht im Handbuch |
| SHIFT + SAMPLE/OSC | springt zur nächsten Kategorie (002 PULSE [Analog] geht auf 017 Audio In Mn [Audio In]) | gemessen, Handbuch PG S.11, offline `0xC0041878` |
| SHIFT + MOD. TYPE | **6** Einträge pro Klick (04 geht bei zwei Klicks auf 16 statt 06). Das Handbuch deutet es als "Wellenform wechseln, Ziel behalten". | gemessen, Handbuch PG S.11, offline `0xC0040F88` |
| SHIFT + IFX TYPE | **10** Effekte pro Klick (17 geht bei zwei Klicks auf 37 statt 19) | gemessen, **nicht im Handbuch**, offline `0xC0041310` |
| SHIFT + CUTOFF | kein Unterschied | gemessen, offline: liest SHIFT nicht |
| SHIFT + PITCH/GLIDE | stellt **OSC GLIDE** statt OSC PITCH ein (Fenster "OSC GLIDE") | gemessen, Handbuch PG S.11 und OM S.5, offline `0xC004242C` |
| SHIFT + LEVEL, PAN, RESONANCE, EG INT., MOD. DEPTH, ATTACK, IFX EDIT, DECAY/RELEASE, OSC EDIT, MOD. SPEED | kein Unterschied | gemessen |

Nicht gemessen: Time Slice (braucht ein Sample). Dort belegt das Handbuch SHIFT + VALUE und
SHIFT + Trigger-Pad (PG S.6), die Wirkung ist hier nicht geprüft.

## 3. SHIFT + Pad

Alle 16 Pads gemessen. Seiten wie im Handbuch (PG S.11), die Seitenzahlen (z.B. "Pattern 2/29")
stehen in der Kopfzeile des Geräts. SHIFT + Pad wählt dabei **keinen Part** und spielt **keinen
Ton**, und im SEQUENCER-Modus setzt es keinen Schritt (gemessen: Part-LED, Pattern-Bytes).

| Pad | Seite | Pad | Seite |
|---|---|---|---|
| 1 | SWING (Pattern 2/29) | 9 | GROOVE DEPTH (Part 18/29) |
| 2 | LENGTH (Pattern 4/29) | 10 | MOTION SEQ (Part 21/29) |
| 3 | CLEAR MFX MOTION (Pattern 7/29) | 11 | TRG. PAD VELOCITY (Part 22/29) |
| 4 | KEY (Pattern 8/29) | 12 | STEP EDIT (Step 24/29) |
| 5 | SCALE (Pattern 9/29) | 13 | COPY PART (Part Util 1/4) |
| 6 | GATE ARP (Pattern 11/29) | 14 | CLEAR SEQUENCE (Part Util 3/4) |
| 7 | LAST STEP (Part 16/29) | 15 | CLEAR MOTION (Part Util 4/4) |
| 8 | GROOVE TYPE (Part 17/29) | 16 | METRONOME (Global 9/20) |

Beleg: gemessen und Handbuch, offline `0xC0043FC8` (der Pad-Verteiler liest SHIFT). Die
Seiten 13 bis 15 zeigen "press [Enter]", MENU führt aus. Pad 12 öffnet STEP EDIT; MENU
öffnet dort die eigentliche Schritt-Eingabe (STEP NUMBER, NOTE, GATE TIME, VELOCITY, OSC EDIT MOTION).

## 4. Halten + Taste, Modus + Pad

Gemessen wurde jede der 34 Tasten (ohne SHIFT) **gehalten**, während 72 zweite Bedienelemente
(34 Tasten, 10 Drehgeber-Richtungen, 11 Regler, 16 Pads, Touchpad) benutzt wurden, jeweils im
Stand und beim Abspielen. Verglichen wurde mit "Taste kurz antippen, loslassen, dann das zweite
Element". Als Halte-Effekt, also als Unterschied zwischen Halten und Antippen, fand dieser Vergleich nur
die ersten zwei Zeilen. Alle anderen Paare verhalten sich gehalten wie angetippt, soweit Display, LEDs,
Pattern-Daten und (bei Pad und Touchpad als zweitem Element) der MIDI-Ausgang es zeigen. Die Zeilen
3 und 4 (PART ERASE, GATE ARP) sind Einzelversuche, weil die Matrix nur kurze Pad-Drücke macht.

| Kombination | Wirkung | Beleg |
|---|---|---|
| TRIGGER, SEQUENCER, KEYBOARD oder CHORD **halten** + Pad | wählt den Part des Pads **still**: keine Note an MIDI-Out (die angetippten Modi senden Note bzw. Akkord, hier nichts), kein Schritt im SEQUENCER-Modus, nur die blaue Part-LED wandert | gemessen (MIDI-Ausgang, LEDs), Handbuch (Korg FAQ 367, schnelles Part-Wählen), offline `0xC0043F10` (liest die Zustände der Tasten 19, 21, 23, 24 = TRIGGER, SEQUENCER, KEYBOARD, CHORD) |
| PATTERN SET **halten** + Pad | legt das gerade gewählte Pattern auf das Pad. Danach ruft PATTERN SET (angetippt, Modus an) + dasselbe Pad es ab (Pattern-Hash wie zuvor, MIDI Bank/Programm-Wechsel). Gruppe 1 bis 4 über die Tasten 1 bis 4. | gemessen, Handbuch OM S.6 und S.11 |
| PART ERASE (Modus an) + Pad **halten**, nur beim Abspielen | löscht die Noten des Parts, solange das Pad gehalten wird (Pattern-Bytes: 1 Note nach 0,1 s, 26 Bytes nach 1 s, 75 Bytes nach 3 s). Im Stand passiert nichts. | gemessen, Handbuch OM S.6, S.12, S.13 |
| GATE ARP an + Trigger-Pad **halten** + Touchpad | Gate-Arpeggiator: Ohne gehaltenes Pad keine Noten. X ändert die Rate (x=100: 5 Noten in 1,5 s, x=900: 15 Noten), Y die Länge. | gemessen (MIDI-Ausgang, X-Achse), Handbuch OM S.10 bis 11 (Y-Achse nur Handbuch) |
| PART MUTE (Modus an) + Pad | schaltet den Part stumm oder wieder an (Taste antippen, nicht halten) | gemessen, Handbuch OM S.6 und S.13 |
| STEP JUMP (Modus an) + Pad, beim Abspielen | springt auf den Schritt des Pads (Pad 3: Schritt 3, Pad 9: Schritt 9); mehrere Pads laufen als Schleife | gemessen (Schrittzähler; Schleife nur Handbuch OM S.6) |
| KEYBOARD (Modus an) + Taste 1 oder 4 | Oktave tiefer oder höher (Pad 1: Note 60, nach Taste 1: 48, nach Taste 4: 72) | gemessen (MIDI-Ausgang), Handbuch OM S.10 |
| SEQUENCER (Modus an) + Taste 1 bis 4 | wählt den Taktabschnitt, rote LED 1 bis 4 folgt | gemessen, Handbuch OM S.12 |
| REC (armiert) + PLAY, dann Regler drehen | Motion Sequence wird aufgezeichnet (Pattern-Bytes: 44 geändert, ohne REC 2) | gemessen, Handbuch OM S.12 |
| WRITE, dann WRITE oder MENU | der zweite Druck speichert (Fenster "Working..."), EXIT bricht ab. SHIFT + MENU im Zielwahl-Fenster speichert ebenso. | gemessen (im Emulator nur in den Flash-Speicher der Kopie), Handbuch OM S.12 und S.13 |
| EXIT mehrmals | zurück zum Pattern-Bildschirm | Handbuch OM S.5 |
| Ein/Aus-Taste 2 s halten | ausschalten | gemessen am Gerät am 8.10. (`docs/messungen/2026-10-08-panel-bedienung.md`) |
| Pad **halten** + Regler, Taste oder Drehgeber | nur der übliche Part-Wechsel durch das Pad, sonst nichts | gemessen (985 Läufe je Zustand) |

**Mit BLECH** (nicht mit EXIT beim Einschalten, nicht auf der blauen):

| Kombination | Wirkung | Beleg |
|---|---|---|
| EXIT **halten** + WRITE | speichert das Pattern sofort an seinen eigenen Platz (ohne das Zielwahl-Fenster zu bestätigen) | gemessen, `docs/messungen/2026-10-19-exit-shortcuts.md` |
| EXIT **halten** + Pad | setzt den Klang eines Parts auf die gespeicherten Werte zurück, die Steps bleiben; SEQUENCER und STEP JUMP: der gewählte Part, sonst der Part des Pads | gemessen, ebenda |

Die Modus-Tasten (TRIGGER, SEQUENCER, KEYBOARD, CHORD, PART MUTE, PART ERASE, STEP JUMP,
PATTERN SET) bleiben nach dem Loslassen an. Sie müssen nicht gehalten werden, nur die ersten
vier Zeilen oben verlangen das Halten.

## 5. Beim Einschalten

Die Firmware fragt die gehaltenen Tasten einmal ab (Panel-Nachricht `0x91`/`0x92`) und vergleicht
mit einer Tabelle bei `0xC002882C`. Es zählt **nur die genaue Maske**: eine zusätzliche gehaltene
Taste (auch AMP EG, IFX ON oder das Touchpad) macht daraus einen normalen Start. Alle Masken
nochmals im Emulator gebootet (6 s Gerätezeit), keine Assertion. Die Zuordnung "Bit n ist Taste n"
(`data/panel.mjs`) ist hergeleitet; dass das Hacktribe-Wiki dieselben Tastenpaare für diese Modi nennt,
stützt sie. Quelle der Tabelle: `docs/messungen/2026-10-10-startphase.md`.

| Gehalten beim Einschalten | Maske | Ergebnis im Emulator | Beleg |
|---|---|---|---|
| PATTERN SET + Taste 1 | `0x18000000` | Versionsseite `[ALL]` | gemessen, offline, Hacktribe-Wiki (Test-Mode ALL) |
| PATTERN SET + Taste 2 | `0x28000000` | Versionsseite `[SHIP]` | gemessen, offline, Wiki (SHIP) |
| PATTERN SET + Taste 3 | `0x48000000` | Versionsseite `[MAIN]` | gemessen, offline, Wiki (MAIN) |
| PATTERN SET + Taste 4 | `0x88000000` | Versionsseite `[PNL]` | gemessen, offline, Wiki (PNL) |
| MFX SEND + Taste 1 | `0x14000000` | Versionsseite `[EXT]` | gemessen, offline, Wiki (EXT) |
| MFX SEND + Taste 2 | `0x24000000` | Versionsseite `[SERV]` | gemessen, offline, Wiki (SERV) |
| PATTERN SET + MFX SEND | `0x0C000000` | Tabelle `00: ---` bis `15: ---` (Pad-Messung) | gemessen, offline, Wiki (Pad-Druckmessung) |
| MFX HOLD | `0x00000080` | Versionsseite `[XY]`, "XYPad Check" | gemessen, offline, Wiki (XY) |
| PATTERN SET + STEP JUMP | `0x0A000000` | "XY TEST, Step 1" | gemessen, offline, Wiki (XY-Test) |
| LPF + HPF | `0x00140000` | Data Util 1/3, IMPORT PATTERN (Karten-Import) | gemessen, offline, **nicht im Wiki** |
| SHIFT | `0x00000400` | normaler Start, die Firmware merkt sich SHIFT. Im Emulator kein sichtbarer Unterschied; im Code wählt ein Ereignis (Bildschirm 0x1d, Wert 0x1c) dann Fenster-Ereignis `0x1c` statt `4`, und `4` ist das Fenster "Working...". Wirkung am Gerät offen. | gemessen (Start), offline (`0xC006B9F4`), Deutung hergeleitet |
| EXIT | `0x00002000` | normaler Start, kein Modus. Der MFX-Patch nutzt es als Notschalter. | gemessen, `docs/messungen/2026-10-10-mfx-umschalter.md` |
| eine zusätzliche Taste zu einer der Masken | | normaler Start, kein Testmodus | gemessen (PATTERN SET + 1 plus AMP EG, EXIT oder Part<), offline |
| beliebige andere Taste oder Kombination | | normaler Start | offline (Tabelle kennt nur die genannten Masken) |

Das Handbuch kennt **keine** Einschalt-Tastenkombinationen. Factory Reset, Software-Update und
Versionsprüfung laufen über DATA UTILITY (PG S.10, OM S.15). Die Test-Modi (ALL bis XY) führen
auf Seiten, die für die Fertigung gedacht sind; was hinter SHIP und SERV passiert, wurde nicht untersucht,
am Gerät also nicht ausprobieren, ohne nachzulesen.

## 6. Was überraschend ist

- **SHIFT + EDIT> im Menü springt die Menügruppe weiter** (Pattern, Part, Step, ...). Steht in keinem
  Handbuch, spart viel Blättern (29 Einträge).
- **SHIFT + IFX TYPE** springt in 10er-Schritten, ebenfalls nicht dokumentiert.
- **SHIFT + VALUE im Step Edit ist nicht überall gröber**: bei GATE TIME ist es feiner (1 statt 10).
- **SHIFT + REC öffnet nur im Stand das Sampling-Fenster**, beim Abspielen passiert nichts.
- **SHIFT + TAP** zählt nicht als Tap-Tempo, es springt nur auf die Seite.
- **SHIFT + GATE ARP, TOUCH SCALE, MASTER FX** lassen den Touchpad-Modus unangetastet, ohne SHIFT
  schalten dieselben Tasten ihn um.
- **Halten + Pad** wählt den Part still. Wer in SEQUENCER oder KEYBOARD den Part wechseln will,
  ohne einen Schritt zu setzen oder eine Note zu spielen, hält die Modus-Taste.
- **Die gehaltene Tastenmaske beim Einschalten** muss exakt sein. Ein versehentlich mitgehaltener
  Finger auf einer dritten Taste verhindert jeden Testmodus.
- **LPF + HPF beim Einschalten** führt in IMPORT PATTERN, im Wiki steht es nicht.
- Hacktribe-spezifisches Tastenverhalten wurde nicht gefunden.

## 7. Offline: wo die Firmware SHIFT liest

- **Tasten-Verteiler** `0xC00700D8(Objekt, Taste, gedrückt)` (jede Taste kommt dort vorbei, gemessen in
  `docs/messungen/2026-10-10-mfx-umschalter.md`; Taste 0x23 wird verworfen). Aus dem Code gelesen: Tasten 0 bis 3
  gehen an die Transport-Funktion `0xC006F638`, 4 bis 6 (GATE ARP, TOUCH SCALE, MASTER FX) an `0xC006FF94`,
  0x0e (WRITE) an `0xC006F094`, 0x10 (PART MUTE) in einen eigenen SHIFT-Zweig ab `0xC0070428`, die Modus-Tasten
  im Bereich 0x11 bis 0x1b an `0xC006FEDC`, 0x1c bis 0x1f (Schritt-Tasten) an `0xC006F968`.
- **Das SHIFT-Wort** liegt im Tasten-Zustandsobjekt, das `0xC0040F04()` liefert, bei `+0x358`
  (Zustand der Taste 10: `0x308 + 8 * 10`), im laufenden Gerät bei `0xC06BCAC0`. Es steht auf 0 (los),
  geht beim Drücken auf 1 und bei gehaltener Taste über einen Takt-Zähler (`0xC00825E8`) weiter auf 2 und 3.
  Es wird nur auf Nicht-Null geprüft. Geschrieben wird es von `0xC00824AC`.
- Das gilt für alle Tasten: Zustand der Taste k bei `+0x308 + 8 * k`. Code, der den Zustand einer anderen
  Taste als SHIFT liest, ließ sich über den Zugriff auf dieses Objekt finden: die Pad-Funktion `0xC0043F10`
  fragt TRIGGER (19), SEQUENCER (21), KEYBOARD (23) und CHORD (24) ab. Das ist die Stelle hinter
  "Halten + Pad wählt still". Weitere Stellen, die einen Tastenzustand außer SHIFT lesen, wurden so nicht
  gefunden (nur Aufrufe, die das Objekt über `0xC0040F04` holen, sind erfasst).
- **Zur Laufzeit** (Hook auf die Speicherstelle, in allen rund 17 000 Läufen und den Step-Edit-Versuchen) lasen
  34 verschiedene Befehle das SHIFT-Wort. Je Bedienelement die lesende Stelle: Spalte "Beleg" in den
  Tabellen oben. Die Lesestelle `0xC008258C` ist nur der Takt-Zähler, kein Tasten-Code.
- **Aus dem Code gelesen, aber im Emulator nicht ausgelöst** (Aufrufe über `0xC0040F04`): `0xC0043604` (Nebenzweig
  der Pad-Funktion `0xC0043580`), `0xC0065CEC` (Tastenfunktion `0xC0065CD8`, Sprungtabelle für die Tasten 6 bis 10
  nur mit SHIFT), `0xC0067604` (Seiten-Funktion der Menü-Klasse Pattern, mit SHIFT Schrittweite mal 10),
  `0xC00686EC` (kleine Funktion neben `0xC006865C` und `0xC006869C`, die bei SHIFT + WRITE im WRITE-Fenster
  getroffen wurden), `0xC006FC20` (Zuordnung der Modus-Tasten, Zweig von PART MUTE, über den Tasten-Verteiler
  nicht erreichbar). `0xC0066314` (CHAIN TO) ist der Code hinter einem gemessenen Fall, die Stelle selbst wurde dort
  nicht aufgezeichnet. Ob diese Reste weitere SHIFT-Kürzel tragen, ist offen. Die rund 50 weiteren
  Befehle mit `ldr rX, [rY, #0x358]` im Abbild sind in der Regel andere Felder oder Literal-Pool-Zugriffe,
  kein SHIFT.

## 8. Grenzen und Offenes

- **Am Gerät nur die Ein/Aus-Taste geprüft.** Der DSP ist im Emulator eine Attrappe: ob etwas klingt, ist nicht
  gemessen, nur MIDI-Ausgang, Display, LEDs und RAM.
- Zustände, die der Emulator nicht erreicht: Time Slice (braucht ein Sample), die Untermenüs von Global und
  Data Util, Sample-Bearbeitung. Dort gelten nur die Handbuch-Angaben.
- **Nur auf der Hauptebene des Menüs** je Gruppe wurde SHIFT + VALUE getestet (erste Seite). Innerhalb der
  Untermenüs von Global und Data Util kann es weitere Unterschiede geben.
- Das Handbuch dokumentiert keine SHIFT-Kombination für STOP, MENU, EXIT, Part </>, PART ERASE, STEP JUMP, MFX HOLD,
  die Tasten 1 bis 4, Filtertasten, MFX SEND, AMP EG, IFX ON und die meisten Regler. Der Emulator bestätigt
  für alle: kein Unterschied (außer den in Abschnitt 1 und 2 genannten, nicht dokumentierten Fällen).
- Die Zuordnung der gehaltenen Tasten beim Einschalten zu Panel-Nummern ist hergeleitet, nicht am Gerät geprüft;
  siehe `docs/messungen/2026-10-10-startphase.md`.

## 9. Messaufbau

Aufbau und Zahlen, damit es nachvollziehbar bleibt:

- Eine Firmware-Instanz wird 5 s gebootet (Hauptbildschirm, Pattern 1 aus dem Flash-Dump), dann je Lauf
  per `fork` kopiert. Ein Lauf drückt Tasten, dreht Drehgeber, stellt Regler, drückt Pads und das Touchpad
  mit Panel-Nachrichten (`00 Taste 1|0`, `01 Nr 00 Delta`, `02 Nr hi lo`, `04 Nr 00 Velocity an`,
  `05 xh xl yh yl`) und liest danach Bildschirm-Nummer (`*0xC03404C0`), Display, LED-Befehle, das
  Pattern (16 KiB ab `*0xC033E6A4`), 38 MiB Heap-Unterschiede und den MIDI-Ausgang.
- Zustände: Stand, Abspielen, SEQUENCER, KEYBOARD, TRIGGER, PART MUTE, CHORD, STEP JUMP, PATTERN SET,
  SEQUENCER und Abspielen, GATE ARP, Menü (Seite 0, 1, 2), WRITE-Fenster, SHIFT + WRITE, SHIFT + REC,
  SHIFT + Pad 12 bis 16.
- Rund 17 000 Läufe: 2 595 "Taste gehalten + zweites Element" je für Stand und Abspielen, 2 487 "angetippt + zweites Element"
  je für Stand und Abspielen, 985 "Pad gehalten + zweites Element" für drei Zustände, 181 "SHIFT +
  alles" je weiterem Zustand. Dazu rund 20 Einzelversuche (SHIFT + PLAY, Undo, PART ERASE, STEP JUMP,
  Gate Arp, MIDI-Ausgang, Einschalt-Masken).
- Ohne Unterschiede im Anzeige-Pfad bleiben Audio-Wirkungen unsichtbar, außer sie erscheinen im
  MIDI-Ausgang. Deshalb wurden alle Halten-Paare mit Pad und Touchpad zusätzlich auf den MIDI-Ausgang
  verglichen.
- Die Messskripte liegen nicht im Repo (Wegwerf-Werkzeuge). Ein Kürzel ist mit dem vorhandenen
  Werkzeug einzeln nachstellbar, zum Beispiel SHIFT + TAP:

```sh
tools/emu/.venv/bin/python tools/emu/machine.py --vsb SYSTEM.VSB --flash flash_full.bin --seconds 7 \
  --send 000a010000@5.0 --send 0003010000@5.3 --send 0003000000@5.4 --send 000a000000@6.0 --png out.png
```

Das Bild zeigt "Pattern 1/29, BPM 160.0". Einschalt-Masken: `--held 0x18000000` und die übrigen aus Abschnitt 5.
