# Patternwechsel: Bestätigung vor dem Wechsel und die Lücke beim Wechsel

Hintergrund zu zwei Fragen: Lässt sich der Patternwechsel beim Spielen erst nach einer Bestätigung ausführen (gebaut als Patch
`data/patches/pattern-switch.json`, Menü BLECH > FEATURES > PATTERN CONFIRM), und woher kommt die hörbare Lücke von etwa 100 ms
beim Wechsel? Alle Adressen gelten für Korg electribe sampler, Firmware 2.02 mit [Hacktribe](../glossary.md#hacktribe). Die
Prüfungen und Zahlen des Patches stehen in [Patternwechsel gebaut](../messungen/2026-10-15-patternwechsel.md).

Grundlage: der Emulator (`tools/emu`) und offline gelesener Code, mit einer eigenen [`SYSTEM.VSB`](../glossary.md#vsb) und dem
eigenen Flash-Dump. **Am Gerät nichts geprüft.** Der DSP ist im Emulator eine Attrappe: was hörbar passiert, ist Hypothese.
Alle Zeiten sind mit dem korrigierten Emulator-Takt gemessen (Timer-Zeiten genau, befehlsgebundene Zeiten wie Kopieren und
Frames beruhen auf 5 ns je Befehl und sind auf etwa Faktor 2 genau).

Markierungen: **gemessen** (im Emulator ausgeführt und beobachtet), **offline** (Code gelesen), **hergeleitet** (aus beidem
geschlossen), **geschätzt**, **offen** (nicht geklärt, braucht das Gerät).

Verwandt: [dsp-erster-blick.md](dsp-erster-blick.md) (DSP-Seite des Effektwechsels), [sequencer-timing.md](sequencer-timing.md),
[patcher.md](../patcher.md), [MFX-2-Umschalter](../messungen/2026-10-10-mfx-umschalter.md).

**Kurz:** Die Firmware merkt sich beim Drehen am Rad während des Spielens nur eine Nummer und ein Flag, lädt nichts vor dem
Sequenzende und zeigt das gewählte Pattern schon als "NEXT:nnn Name". Der Patch macht nur das Anwenden am Sequenzende von einer
Bestätigung abhängig. Die Lücke beim Wechsel kommt auf der ARM-Seite nicht vor (Takt stetig, Pattern im RAM, kein Flash-Zugriff);
wahrscheinlichste Ursache ist die Effekt-Neuinitialisierung im DSP (**hergeleitet**).

---

## Frage 1: Patternwechsel erst nach Bestätigung

### 1.1 Was die Firmware heute macht

Ablauf, wenn beim Spielen am Rad gedreht wird (**gemessen**, Stellen **offline**):

1. Der VALUE-Handler des Hauptbildschirms `0xC006508C` (Slot `+0x28` der Bildschirmklasse bei `0xC00E3498`)
   fragt: Sperrflag `this+0x38`, Transportzustand 11 und eine Abfrage `0xC00475B4` (vermutlich "Pattern
   bearbeitet": dann Fenster 0x1B statt Wechsel; nicht getestet). Danach springt er an seinem Ende
   (`0xC006513C`, ein Sprung nach `0xC008206C`) in die Auswahl. Mit SHIFT ist das Delta mal 10
   (`0xC0065124`).
2. `0xC008206C(psel, delta)` rechnet `n = wrap(psel+0x318 + delta, 0, 249)` und ruft `set_number` =
   `0xC0081F50(psel, n, senden)`.
3. `psel` ist die Auswahl-Instanz (Singleton, Zeiger `0xC03487E8`, Getter `0xC00431F0`). Im Zustand "spielt"
   (nicht 0, nicht 3 bis 5) macht `set_number`: Wechsel-Anforderung `0xC0057840` (setzt das Wartend-Flag
   `0xC068FC64` auf 1), `psel+0x318 = n`, `psel+0x341 = 1`, schickt die Nachricht Typ 1 an die Zuhörer von
   `psel` (Anzeige) und, wenn `senden` gesetzt ist, MIDI Bank-Select und Program Change (`0xC0045320` und
   `0xC00406A0`, DIN und USB).
4. **Es wird nichts geladen und nichts in eine Liste gelegt.** Jeder weitere Klick überschreibt `psel+0x318`.
   Die Namen für die Anzeige liest die Firmware aus der Pattern-Bank im RAM (`0xC004A350`), ohne ein Pattern
   zu laden.
5. Am Sequenzende entscheidet die Engine-Task bei `0xC005F1B8`: sie holt `psel+0x318` (Aufruf von
   `0xC00818D8` bei `0xC005F1C4`) und ruft `player_change(player, n, 0)` = `0xC0079AA8`. Bei einer anderen
   Nummer als der laufenden stößt das über `0xC002D5D8` das Laden an (siehe 2.3), bei derselben Nummer
   wiederholt oder verkettet es (Chain, in `0xC00799A4`).

Zahlen (Pattern mit Anzeige 1, 64 Schritte; Nummern 0-basiert wie in der Firmware): Klicks bei
6051, 6551 und 7051 ms setzen `psel+0x318` auf 1, 2, 3 und das Flag auf 1; `player_change` kommt einmal bei
11 978 ms mit Nummer 3, kurz vor dem Ende der 64 Schritte.

**Was "Ende der Sequenz" ist (gemessen):** der letzte Takt-Tick der Patternlänge, nicht der Taktstrich und
nicht ein Schritt. Pattern 7 (Länge 0, 16 Schritte, 96 Clocks): Entscheidung nach Clock 95. Pattern 8 (Länge
3, 64 Schritte, 384 Clocks): nach Clock 383. Die Entscheidung fällt nach dem vorletzten Clock, bei 160 BPM
22 ms (1,4 Clocks) bevor der erste Clock des neuen Patterns kommt; der nächste Clock gehört noch zum alten
Pattern. Ob ein "Last Step" pro Part (Feld `part.lastStep`, in allen Werks-Parts 0) das Ende verschiebt, ist
**offen**; die Engine rechnet in `0xC005EB44` ff. mit Part-Längen.

**MIDI:** jeder Klick schickt sofort Bank-Select (CC 0 und 32) und Program Change auf Kanal 10 (drei
Klicks, drei Dreiergruppen). Das passiert beim Vormerken, nicht beim Wechsel. Ein extern synchronisiertes
Gerät springt also schon beim Durchblättern mit.

### 1.2 Verhalten der Nachbarn

| Bedienung beim Spielen mit vorgemerktem Pattern | Firmware heute |
|---|---|
| MENU | ignoriert (`0xC0065144` kehrt zurück, wenn `psel+0x341` gesetzt ist) |
| EXIT | tut auf dem Hauptbildschirm nichts (ruft den leeren Basis-Stub `0xC0060F04`, Slot `+0x08`) |
| STOP | wendet das Vorgemerkte sofort an (`0xC0081B5C`, Aufrufe aus der Transport-Behandlung), Zustand 0 |
| PATTERN SET + Pad | `0xC006EDE4` -> `set_number(psel, n, senden=1)`, wirkt wie das Rad: vorgemerkt bis Sequenzende |
| MIDI Program Change (Kanal 10) | `0xC006EE00` -> Kopie `0xC0081E60(psel, n, senden=0)`, vorgemerkt bis Sequenzende |
| Chain (`pattern.chainTo`) | wird in `player_change` bei gleicher Nummer ausgeführt, setzt `player+0x318`, danach gleicht ein Zuhörer `psel` an (`0xC0081888`); kein `set_number`-Aufruf |
| SHIFT + VALUE | Delta mal 10 im selben Handler; gleiche Kette |
| Pause (PLAY noch einmal, Zustand 2) | wie Spielen: Rad merkt vor |
| REC bereit oder REC (Zustände 3, 4) | `set_number` kehrt sofort zurück (Code `sub 3; cmp 2`); gemessen im Zustand 4: Rad ändert nichts, Zustand 3 nicht gedreht |
| Stillstand (Zustand 0) | jeder Klick lädt sofort (Nachricht an den Zuhörer `0xC0081E18`, `player_change` etwa 75 ms später) |

### 1.3 Wie der Patch eingreift

Das Anzeigen ohne Laden ist schon in der Firmware. Der Patch ergänzt:

1. **Zustand:** drei Wörter im freien RAM-Bereich des Abbilds (FF heißt aus): `browse` (Rad hat geändert, nicht bestätigt),
   `armed` und `armnum` (bestätigte Nummer).
2. **Rad beim Spielen** (`0xC006513C`): statt des Sprungs nach `0xC008206C` rechnet der Haken `n` wie die Firmware, ruft
   `set_number(psel, n, 0)` **ohne** MIDI und setzt `browse = 1`. Die Anzeige zeigt `VIEW:` statt `NEXT:`.
3. **MENU** (Slot `+0x18` der Hauptbildschirm-Klasse, `0xC00E34B0`): bei `browse` wird bestätigt: `armnum = psel+0x318`,
   `armed = 1`, `browse = 0`, `set_number(psel, n, 1)` noch einmal (löst die Anzeige neu aus und schickt jetzt den MIDI-Program-Change).
4. **EXIT** (Slot `+0x08`, `0xC00E34A0`): bei `browse` zurück zur bestätigten Nummer oder zur laufenden; sonst bei `armed` die
   Bestätigung zurücknehmen (MIDI zurück auf die laufende).
5. **Sequenzende** (Aufruf von `0xC00818D8` bei `0xC005F1C4`): der Ersatz liefert `armnum`, wenn `armed`, sonst die laufende Nummer,
   wenn `browse`, sonst `psel+0x318` wie bisher. Läuft in der Engine-Task, liest deshalb nur.
6. **STOP** (erster Befehl von `0xC0081B5C`): bei `browse` vorher `psel+0x318` auf die bestätigte oder laufende Nummer zurücksetzen
   und das Flag `+0x341` löschen (direkt schreiben, nicht über `set_number`: im Stillstand lässt `set_number` bei Nummer gleich
   Player `psel+0x318` unberührt, gemessen).
7. **Fremde Quellen** (erste Befehle von `0xC006EDE4` und `0xC006EE00`: Pad und MIDI-PC): löschen `browse` und `armed`, denn eine
   bewusste Wahl gilt wie bisher.
8. **Anzeige:** Beschriftung der Zeile unten (Builder `0xC0086DC0`, Text `NEXT:` bei `0xC00A72E0`): ein Aufruf statt des
   Ladebefehls bei `0xC0086DC4` liefert bei `browse` den Text `VIEW:`, sonst `NEXT:`.

Alle Stellen liegen **hinter** den Rettungswegen, es braucht keine `startPhase`-Ausnahme. Mit dem
[Notschalter](../glossary.md#notschalter) (EXIT beim Einschalten) verhält sich alles wie die Firmware. Das Zeigerwort im
Haupttastenverteiler `0xC00700D8` wird nicht gebraucht: MENU und EXIT kommen über Slots der Bildschirmklasse an, der MFX-2-Patch
hat den Verteiler schon (zwei Patches an derselben Stelle gibt es nicht, Regel in [patcher.md](../patcher.md), "Einhaken").

### 1.5 Grenzen und Risiken

- **Nicht getestet (offen):** WRITE und Bearbeiten (Fenster 0x1B, "Pattern bearbeitet") während des
  Blätterns; die Wirkung auf Song- oder PATTERN-SET-Modi mit gehaltenen Pads; Blättern über Minuten (getestet:
  40 s); das Verhalten am Gerät. Part-spezifisches Last Step.
- **Wartend-Flag:** `set_number` setzt `0xC068FC64 = 1` beim Blättern. Es bleibt gesetzt, solange geblättert
  wird. Gemessen: die Notenfolge ist unverändert, die Firmware wertet es in `0xC005CDE4` aus,
  wozu genau, ist **offen**. Falls das Gerät sich anders verhält, löscht ein Aufruf von `0xC0057844` im
  Sequenzende-Haken das Flag (billige Rückfallstufe).
- **Nach dem Wechsel:** wurde nach dem Bestätigen weiter geblättert, springt die Anzeige auf die neue laufende
  Nummer, das weitere Blättern geht verloren (hinnehmbar, `T4`).
- **Zeitnah zum Ende:** wer MENU im letzten Tick drückt, kann den Wechsel verpassen; die Entscheidung fällt
  22 ms (1,4 Clocks bei 160 BPM) vor dem Beginn des neuen Patterns.
- **Der Sequenzende-Haken läuft in der Engine-Task** (nicht in der Bedienoberfläche): er darf nur lesen, nie
  Sperren oder `set_number` aufrufen. Der Patch tut das nicht.
- **Anzeige:** das große Feld blinkt, wenn etwas vorgemerkt ist (Firmware-Verhalten, gemessen). Es blinkt beim
  Blättern ebenso; das Blinken ließe sich über `psel+0x341` trennen.
- **Mehrere Patches:** die Stellen kollidieren nicht mit MFX 2 und dem
  [Startbild-Editor](startbild-editor.md), aber jede Einhängestelle von zwei Patches an derselben Adresse
  bleibt ein ungelöstes Patcher-Thema ([../patcher.md](../patcher.md), "Später: Code als Quelltext").

Wer live weit springen will (zum Beispiel von 68 auf 211), hat SHIFT + VALUE (10er-Schritte) und PATTERN SET + Pad (Schnellwahl,
gilt wie bisher sofort als bestätigt).

---

## Frage 2: Lücke beim Patternwechsel

### 2.1 Zeitleiste des Wechsels (gemessen, 160 BPM)

Pattern 7 (1 Takt) nach Pattern 8, Zeit relativ zur Entscheidung T0 der Engine. Ein Clock ist 15,6 ms.

| Zeit | Ereignis |
|---|---|
| -40,0 / -24,0 / -9,0 | MIDI-Clocks, Abstand 16, 15 ms |
| 0,00 | Entscheidung `0xC005F1B8`, `player_change(Nummer 7)` (0-basiert, Anzeige 8) |
| +0,26 | Kopie 16 KiB aus der RAM-Bank (`0xC08CE940`) ins Live-Pattern (`0xC06B279C`) |
| +0,32 | zweite Kopie 16 KiB (Live -> `0xC06B7AA4`, Vergleichs- oder Rückgängig-Puffer, **hergeleitet**) |
| +0,81 | MIDI Note-Off für die noch klingende Note des alten Patterns (`84 45 40`) |
| +4,56 bis +5 | 17 Mailbox-Frames mit den Part-Parametern zum DSP |
| +6,99 | MIDI-Clock (letzter Tick des alten Patterns), Abstand 16,0 ms |
| +22,00 | MIDI-Clock = erster Tick des neuen Patterns, Abstand 15,0 ms |
| +22,96 | erste Note des neuen Patterns (`94 3c 60`), 0,96 ms nach dem Clock |
| ab +4,5 bis etwa +30 | Effekt-Neuinitialisierung, wenn Effekttypen abweichen (2.4) |

- **Der Takt hat keinen Sprung.** Die Abstände vor und nach dem Wechsel sind 15 bis 16 ms; der Wechsel kostet
  die Engine weniger als 1 ms (gemessen).
- Am MIDI-Ausgang endet eine über das Patternende gehaltene Note **etwa 1,4 Clocks vor dem Patternende**: das
  Note-Off kommt bei T0 + 0,8 ms statt am eigenen Gate-Ende. Bei sehr langen Gates ist das ein hörbar
  vorzeitiges Ende, aber 20 ms, keine 100.
- Die neuen Part-Parameter kommen 4,5 ms nach T0 am DSP an, also 17 ms vor dem ersten Ton des neuen Patterns.

### 2.2 Schrittzähler und Variablen

Die Schrittzählung (`0xC031668C`) zeigt beim Wechsel kurz einen Zeiger (`0xC0...`) statt 0 bis 63: die Stelle
ist dann kein Zähler, sondern wird anders benutzt. Sie ist als Messpunkt für den Wechsel unbrauchbar; der
MIDI-Takt (Clock-Zählung ab dem Start) und der Engine-Haken `0xC005F1B8` sind die verlässlichen Anker.
(**gemessen**.)

### 2.3 Flash: es gibt keinen Lesezugriff beim Wechsel

- **gemessen:** beim Start liest die Firmware **einmal** 4 096 000 Byte (250 Patterns zu je `0x4000`) ab Flash
  `0x240000` nach RAM `0xC08B2940`. Danach nie wieder: im Fenster des Wechsels 0 Aufrufe der
  Flash-Lesefunktion `0xC001E4AC` und unveränderte SPI-Befehlszähler. WRITE schreibt die Bank und
  den Flash-Slot ([../messungen/2026-10-10-mfx-umschalter.md](../messungen/2026-10-10-mfx-umschalter.md)).
- **gemessen:** der Wechsel kopiert den Slot im RAM (`0xC08B2940 + n * 0x4000`) ins Live-Pattern. Das
  Überschreiben eines Bank-Slots im Emulator reicht, um das Pattern zu ändern, das wechselt.
- **geschätzt:** wäre es ein Flash-Lesen, kostet es bei SPI1 mit den Formaten der Firmware (SPIFMT0 `0x10308`,
  Teiler 4; SPIFMT1 `0x11808`, Teiler 25, gemessen in den Registern) und einem Modultakt von 150 MHz
  (angenommen) 16 KiB in etwa 3,5 ms (37,5 MHz) oder 22 ms (6 MHz). Beides ist weit unter 100 ms und wird nie
  ausgeführt.

### 2.4 DSP-Mailbox-Verkehr

Format (**offline**, `0xC003DD28`, `0xC003DBC4`, **gemessen** an den Frames): der ARM schickt Befehlswörter in
Frames zu 64 16-Bit-Wörtern (32 Befehle) abwechselnd an die Mailboxen `0xFF900018` und `0xFF900098`. Ein
Befehl ist `Folge (Bit 31 bis 28) | Feld (27 bis 22) | Befehl (21 bis 16) | Wert (15 bis 0)`. Die Felder 0x02
bis 0x21 tragen Part-Werte, Feld `2k` mit den Befehlen 0x30 und 0x31 gehört zu Effektplatz k, Feld 0x28 ist
ein Effekt-Parameterblock, Feld 0x3E ein Frame-Ende (die Zuordnung der Felder ist **hergeleitet**, die
Bitaufteilung **gemessen**). Vor jedem nächsten Frame **wartet der ARM, bis der DSP Bit 31 im ersten Wort des
anderen Puffers gelöscht hat** (Schleife in `0xC003DD28`/`0xC003DBC4`). Die DSP-Attrappe liest immer 0 und
gibt sofort frei: **der Emulator kann dieses Warten nicht zeigen.**

Jeder Wechsel (**gemessen**):

| Unterschied zwischen altem und neuem Pattern | Frames | letzter Frame |
|---|---|---|
| keiner (Kopie, `identical`) | 17 | +4,7 ms |
| nur Steps, Name, Tempo | 17 | +4,7 ms |
| Cutoff, Level, Sample, MFX-Send (einzelner Part oder alle 16) | 17 | +4,7 ms |
| ein Insert-Effekttyp (Part 1) | 21 | +17,5 ms |
| der Master-Effekttyp | 21 | +17,5 ms |
| alle 16 Insert-Effekttypen | 66 | +53,5 ms |

Die Effekt-Folge je Effektplatz (Platz 0 bis 15 Insert, 16 Master; Tabelle `0xC00F934C`, 18 Einträge,
Handler `0xC003E018`, ein Zustandsautomat in `0xC003E65C`) ist **gemessen** dieselbe:

1. **+4,5 ms:** Befehl `0x30` für den Platz (Wert 0), mit Beginn der Part-Frames.
2. **genau 10 Kernel-Ticks = 10,0 ms Pause** (Zähler +10, Befehl `0x30` bei +4,5 ms und `0x31` bei +14,5 ms; der Wert 10
   steht als Konstante bei `0xC003E244`, **offline**).
3. **+14,5 ms:** Befehl `0x31`.
4. **+16 bis +18 ms:** zwei Parameterblöcke zu je 30 Wörtern (Feld 0x28, Befehle 0 bis 29), je mit einem
   Abschluss `0x3F`.

Mehrere Plätze laufen nebeneinander durch denselben Automaten; sie teilen sich die Mailbox, daher die 66
Frames und etwa 1 Frame je 0,75 ms bei 16 Wechseln. Befehl `0x30` und `0x31` sind als "Platz abschalten" und
"Platz wieder zulassen" gedeutet (**hergeleitet**, die Namen sind nicht belegt; die DSP-Seite steht in
[dsp-erster-blick.md](dsp-erster-blick.md), Abschnitt 2.2).

**Echte Paare aus der eigenen Pattern-Bank** (das alte Pattern ist für die
Messung auf einen Takt gekürzt, sonst gleich):

| Wechsel (Anzeigenummer) | Insert-Plätze anders | Master anders | Frames | letzter Effekt-Frame |
|---|---|---|---|---|
| 68 -> 211 (Sprung beim Live-Spielen) | 6 | nein | 39 | +34,5 ms |
| 67 -> 68 | 1 | nein | 36 | +20,0 ms |
| 68 -> 69 | 1 | nein | 40 | +20,5 ms |
| 7 -> 8 | 11 | nein | 57 | +45,5 ms |
| 1 -> 2 | 7 | ja | 42 | +35,5 ms |
| 32 -> 34 | 1 | ja | 27 | +22,5 ms |
| 38 -> 40 | 13 | nein | 57 | +46,1 ms |
| 9 -> 10 | 11 | nein | 62 | +48,0 ms |

Später im Fenster folgen weitere Frames (198 ms und 116 ms bei zwei Paaren): das sind die laufenden Motion-
und LFO-Werte des Patterns, nicht der Wechsel.

**Wie oft trifft das die eigene Bank?** (**hergeleitet** aus den Patterndaten, Vergleich je Part von
Insert-an-Flag, Byte 32, und Effekttyp, Byte 33, sowie Master-Typ, Byte 61): von 249 aufeinanderfolgenden
Paaren haben 141 (57 Prozent) mindestens einen Effektwechsel, 138 davon bei Inserts, 73 beim Master. Von 43
Ketten (`chainTo`) haben 37. Von 2000 zufälligen Paaren 78 Prozent. Alle 14 in den Emulator gesteckten Paare
mit vorhergesagtem Unterschied zeigten die Effekt-Folge; Paare ohne Unterschied sind nur über die
künstlichen Varianten oben gemessen.

### 2.5 Stimmen

Eine Stimme wird am Wechsel am MIDI-Ausgang mit Note-Off beendet, wenn ihr Gate über das Patternende reichte
(+0,8 ms nach T0). Ob der DSP dabei Stimmen abschneidet oder ausklingen lässt, ist **offen**; unter den 17
Part-Frames wurde kein eigener "alle Stimmen aus"-Befehl gefunden (**offline**, nur die Frames gedeutet, nicht
jeden Befehl).

### 2.6 Wahrscheinliche Ursache und warum Vorladen nicht hilft

**Hypothese (hergeleitet):** die Lücke hängt an der Effekt-Neuinitialisierung im DSP. Gründe:

1. Auf der ARM-Seite gibt es keine Lücke: Takt stetig, Pattern im RAM, Kopie unter 1 ms, kein Flash.
2. Das Einzige, was beim Wechsel ungewöhnlich lang dauert, ist die Effektfolge: Abschalten, 10 ms warten,
   Wieder-Zulassen, 60 Parameterwörter je Platz, und alles nur dann, wenn sich ein Effekttyp ändert. Das trifft
   in der eigenen Bank mehr als die Hälfte der Wechsel.
3. Die Folge läuft Platz für Platz durch eine Mailbox mit Quittierung: die Dauer ist
   `10 ms + Frames * Zeit des DSP je Frame`. Die Zeit des DSP je Frame ist **offen**. Ein Frame je Audioblock
   (zum Beispiel 64 oder 128 Samples bei 48 kHz = 1,3 oder 2,7 ms) ergäbe für 49 Frames (etwa zehn geänderte
   Plätze) 65 bis 130 ms plus die 10 ms: das wäre die gehörte Lücke. Das ist eine Rechnung mit einer
   geschätzten Zahl, **kein Beleg**.
4. Ist ein Insert-Platz abgeschaltet, während er im Weg des Parts liegt, schweigt der Part, ein Master-Wechsel
   schneidet Hallfahnen ab (**hergeleitet**, nicht gehört).

Was dagegen spricht oder offen lässt: die Lücke ist laut Beobachtung **bei jedem** Wechsel zu hören, bei 43
Prozent der Nachbarpaare gibt es aber laut Daten keinen Effektwechsel (dort blieben es die 17 Part-Frames und
das frühere Note-Off). Die Lücke bei Wechseln ohne Effektwechsel könnte aus einer anderen Ursache stammen
(Stimmen, Part-Parameter, Sample-Wechsel am DSP).

**Vorladen beim Vormerken** (das Pattern vor dem Sequenzende in den RAM holen) schließt die Lücke **nicht**:
die Patterns sind schon im RAM. Was man vorziehen könnte, sind die DSP-Frames des neuen Patterns, aber der DSP
hat vermutlich einen Satz Parameter und Effektplätze für die laufende Musik; sie vor dem Ende des alten
Patterns zu setzen, ändert den Klang früher. Ein Zwischenweg (Effektplätze, die im neuen Pattern genauso
sind, nicht anfassen) ist schon Firmware-Verhalten: gleiche Typen lösen die Folge nicht aus (gemessen).

### 2.7 Gegenprobe am Gerät (ohne Code)

Zwei Patterns anlegen, die in allen 16 Insert-Typen und im Master-Typ **gleich** sind und sich nur in den
Steps unterscheiden (am schnellsten: Pattern kopieren, Steps ändern), und die zwei im Wechsel laufen lassen,
mit Aufnahme. **Verschwindet die Lücke, ist die Effekt-Neuinitialisierung bewiesen.** Dann zwei weitere
Patterns mit genau einem geänderten Insert-Typ, dann mit 8. Wächst die Lücke mit der Zahl der geänderten
Plätze, passt das Modell `10 ms + n * Frame`. Bleibt sie bei gleichen Effekten, liegt die Ursache woanders
(Stimmen oder DSP-Parameter) und die Auswertung ist zu ergänzen.


---

## Offen

Im Ladepfad sind zwei globale Abschaltungen der Stimmenverwaltung
nachgewiesen, eine vor der Patternkopie und eine nach der Aufbereitung der neuen Part-Sounds.
Hinzu kommen Freigaben gehaltener Noten und die erneute Einrichtung ihrer Notenplätze.
Diese Aufrufe laufen auch innerhalb derselben Sync-Gruppe. Der Patch und die
Gegenproben stehen unter [Stimmen beim Gruppenwechsel](../messungen/2026-10-25-sync-group-stimmen.md).
Das ist ein eigener Befund neben der Effekt-Neuinitialisierung. 

- Der Ton am Gerät: ob und wie lang die Effekt-Neuinitialisierung hörbar schweigt (2.7).
- Die Zeit, die der DSP je Mailbox-Frame braucht (der Emulator quittiert sofort).
- Part-spezifisches Last Step: ob es das Sequenzende verschiebt.
- Was `0xC005CDE4` mit dem Wartend-Flag macht (nicht gebraucht, nur wegen langem Blättern).
- Wechsel ohne Effektunterschied: gibt es dort trotzdem eine Lücke (Stimmen, DSP-Parameter)?
- Verhalten des Wechsels nach Bestätigung beim Bearbeiten (Fenster 0x1B) und in Song-Modi.
