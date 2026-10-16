# TAP und Reglerbewegungen: Recherche im Emulator

Stand 2026-10-15. Kein Gerätezugriff. Alles ist im Emulator gemessen (Firmware 2.02 mit Hacktribe, eigene
`SYSTEM.VSB`, eigener Flash-Dump), nichts am Gerät. `tools/emu/tap_motion_probe.py` wiederholt jede Messung
(`E2_VSB=... E2_FLASH=... tools/emu/.venv/bin/python tools/emu/tap_motion_probe.py`, rund 20 Minuten), die Namen der
Prüfungen stehen in Klammern. Die Skizze der Funktion, die daraus folgt, steht in [Idee 39](../ideen/39-automationen-tap.md).

Offsets im Pattern sind in dieser Datei RAM-Offsets im Pattern-Objekt (Zeiger in `0xC033E6A4`, hier `0xC06B2798`). Die
[Gerätekarte](../geraetekarte.md) zählt vom Dateianfang und damit 4 weniger: `motion.part` bei 256 ist hier `0x104`, `part.motionMode` bei
`0x803` ist hier `0x807`.

Die Prüfungen laufen auf der Firmware allein, ohne die Plugin-Laufzeit: zwei kleine ARM-Stümpfe liegen nur im RAM des
Emulators (im freien FF-Bereich des Abbilds, nie in einer Datei) und hängen an denselben Stellen wie die Laufzeit, am
Rahmenhaken `0xC00836FC` (UiTask) und am Eingangsfilter `0xC002837C` (CsTask). Nur der Abschnitt "Laufzeit" lädt die echte
Laufzeit (`tools/patch/script_hooks.s`, unverändert) mit einem kleinen Plugin. Marker: **gemessen**, **offline** (Code
gelesen, nicht ausgeführt), **hergeleitet**, **offen**.

## Ergebnis in einem Satz je Frage

| Frage | Antwort | Marker |
|---|---|---|
| Wirkt ein Regler, den die Firmware selbst auslöst, wie ein echter? | ja: `0xC0040A50(index, wert)` aus dem Rahmenhaken gleicht der Panel-Nachricht in Parameter, Anzeige, Aufnahme | gemessen |
| Touchpad-Gesten genauso? | ja: Taste `0x22` (Berühren), `0xC004596C(x, y)`, Taste `0x22` (Loslassen) | gemessen |
| Motion Sequence je Part lesbar und schaltbar? | ja: ein Byte je Part im Pattern, per RAM-Schreiben schaltet es die Wiedergabe der Spuren ab dem nächsten Schritt | gemessen |
| Gilt das auch für die Touchpad-Spuren? | nein: die Master-FX-Spuren spielt die Firmware immer, das Part-Byte ändert daran nichts | gemessen |
| Beginn zum nächsten Takt? | ja, über den Schrittzähler, mit Verzug unter einem Rahmen (10 bis 30 ms) | gemessen |
| Lässt sich TAP einzeln verschlucken? | nicht mit der Laufzeit von heute (die Sperre gilt für alle Tasten); mit einer Maske je Taste ja | gemessen und hergeleitet |
| Tap-Tempo auf SHIFT+TAP? | SHIFT+TAP ist in der Firmware schon belegt (Seite BPM des Pattern-Menüs); Tap-Tempo kann das Plugin selbst rechnen | gemessen |

## 1. Regler

**Weg der Nachricht (offline, gelesen).** Das Panel schickt `02 nn hi lo` über UART0, die CsTask holt die Nachricht und ruft die
Verteilerfunktion `0xC002837C` (Typ in `msg+0xC`, Daten `msg+0xD` bis `+0x10`). Für den Typ 2 (Regler) ruft sie
`0xC0040A50(index, wert)`. Diese Funktion fragt zuerst `0xC002D634` (liefert sie nicht 0, kehrt sie zurück), geht bei Bildschirmmodus 2
(Byte `0xC03404C4`) in `0xC0083A40` und sonst, für Index 0 bis 10, über das Reglerobjekt `[0xC03487EC]` in `0xC00423A0(objekt, index,
wert, 1, 0)`. Das setzt den Parameter und meldet danach mit `0xC0083B2C` (Typ 12) an die UiTask. Die Wege für Tasten (`0xC0042BB8`),
Drehgeber (`0xC00419B4`), Pads (`0xC0044874`) und Touchpad (`0xC004596C`) stehen im Hintergrund zur [Plugin-Laufzeit](../hintergrund/skript-laufzeit.md).

**Aufruf aus dem Rahmenhaken (gemessen, `knob-call-equals-uart`).** Von 11 Reglern mit je 5 Werten (0, 64, 128, 200, 255)
wurde jeder Fall zweimal auf einer frischen Kopie desselben gebooteten Geräts gespielt: einmal als Panel-Nachricht, einmal als Aufruf
von `0xC0040A50` aus dem Rahmenhaken (`Dev.call` am Haken `0xC00836FC`, dieselbe UiTask-Stelle, an der die Laufzeit ihre
Glue-Funktionen ruft). In 55 von 55 Fällen sind die geänderten Bytes des Pattern-Blocks, das Display und die Assertions gleich.

| Regler | Parameter, Pattern-Byte von Part 1 | Kopie |
|---|---|---|
| 0 LEVEL | `0x81C` | `0x404A` |
| 1 PAN | `0x81D` | `0x404B` |
| 2 OSC PITCH | `0x828` | `0x4052` |
| 3 RESONANCE | `0x812` | `0x4040` |
| 4 EG INT. | `0x813` | `0x4041` |
| 5 MOD. DEPTH | `0x816` | `0x4044` |
| 6 ATTACK | `0x818` | `0x4046` |
| 7 IFX EDIT | `0x826` | `0x4050` |
| 8 DECAY / RELEASE | `0x819` | `0x4047` |
| 9 SAMPLE/OSC EDIT | `0x80F` | `0x403D` |
| 10 MOD. SPEED | `0x815` | `0x4043` |

Bei Part 1 liegt die Kopie 0x382E hinter dem Byte. Das Byte eines Parts weiter liegt 0x330 weiter, die Kopie 0x24 weiter
(Part 2, Regler 0: `0xB4C` und `0x406E`, `knob-second-part-offset`).

- **Wertebereich (gemessen, `knob-value-to-byte`).** Bei Regler 0 (Pegel, Vorgabe 52) steht im Byte `wert >> 1` und nichts begrenzt es:
  255 ergibt 127, 256 ergibt 128, 511 ergibt 255, 1023 ergibt 255. Ein Wert, der `wert >> 1` nicht ändert (0 und 1 bei Vorgabe 52,
  gleicher Wert noch einmal), wird übergangen (187 statt 2100 bis 4000 Befehle). Die Spanne 0 bis 255 deckt den ganzen
  Parameterbereich (PAN: 0 gibt -63, 255 gibt +63). **Offen:** der [Plugin-Vertrag](../plugins.md) und der Hintergrund nennen
  für das `knob`-Ereignis 0 bis 1023. Was das Panel am Gerät schickt (8 oder 10 Bit), ist nicht gelesen. Eine Funktion, die Reglerwerte
  einspielt, sollte auf 0 bis 255 klemmen, solange das nicht geklärt ist.
- **Anderer Bildschirm (gemessen, `knob-on-other-screens-like-uart`).** Aufruf und Nachricht verhalten sich im Hauptbildschirm, im
  Pattern-Menü und im WRITE-Fenster gleich (der Parameter ändert sich, die Firmware leitet nach Bildschirmmodus). Wer nur auf dem
  Hauptbildschirm einspielen will, prüft die Bildschirmnummer selbst (Wort `[0xC03404C0]`, Feld `+0x2C`, 1 ist der Hauptbildschirm).
- **Parameterfenster (gemessen, `knob-popup-like-a-real-turn`).** Ein eingespielter Regler öffnet das Fenster mit dem Parameternamen
  wie ein echter, es schließt 2,0 s (Nachricht) oder 2,1 s (Aufruf) nach dem letzten Wert, und solange alle 0,5 s ein neuer Wert
  kommt, bleibt es offen. Der erste Druck auf MENU schließt nur das Fenster. Ein Weg ohne Fenster ist nicht gefunden: `0xC0041E64` allein
  ändert das Pattern-Byte nicht, und `0xC00423A0` meldet den Wert immer an die UiTask (die letzten beiden Argumente ändern daran nichts, vier Varianten gleich gemessen,
  `knob-inner-handler-arguments-do-not-hide-the-window`). **Offen:** ein Aufruf des Parametersetzers `0xC0059720` ohne die Meldung.
- **Kosten (gemessen, `cost-knob-instructions`, `cost-other-calls-instructions`).** Befehle der Funktion allein, ohne Unterbrechung und
  ohne Taskwechsel: Regler 2140 bis 4039 (je nach Regler), gleicher Wert 187; Touchpad-Punkt 8013 bis 10543; Taste
  `0x22` gedrückt 160, losgelassen 2500, Taste `0x0D` 109; Tempo setzen (`0xC004A80C`) 7116. Elf Regler je Schritt sind rund 35 000
  Befehle. Im Rahmenhaken-Stumpf mit Timer3 gemessen: der langsamste Einzelaufruf bei elf Spuren über einen Takt dauert 0,103 ms,
  mit allen Unterbrechungen, die ihn trafen (hergeleitet: die Wanduhr am Gerät ist nicht gemessen, der Emulator zählt 5 ns je Befehl).
- **Sturm (gemessen, `knob-storm-11-per-frame-5s`).** Elf Regler in jedem Rahmen (25 Hz) fünf Sekunden lang: keine Assertion, die
  Firmware antwortet danach auf MENU.
- **Aufnahme und Transport (gemessen, `motion-transport-3-4-5-0`).** Nach REC steht das Transportwort auf 3, nach PLAY auf 4,
  sobald die Firmware den ersten Wert aufnimmt auf 5, nach STOP auf 0; Nachricht und Aufruf geben dieselbe Folge. Der Vertrag
  kennt 3 und 4, die 5 ist neu (hergeleitet für das Ereignis `rec`: es kommt beim Eintritt in 3 oder 4, die 5 meldet nichts).
- **Task (hergeleitet).** Ein echter Regler läuft in der CsTask (Priorität 3), der Aufruf aus dem Rahmenhaken in der UiTask. Dreht
  die Hand zugleich, überholt die CsTask den Aufruf. Beide schreiben dasselbe Byte, eine Wertzeile geht verloren, kaputtgehen
  kann nichts, was ein Byte schreibt. Ob die Meldung an die UiTask bei vielen Aufrufen die Warteschlange füllt, zeigt der Sturm nicht.

## 2. Touchpad

**Aufruf (gemessen, `touch-mfx-call-equals-uart`, `touch-scale-call-equals-uart`).** Eine Geste ist: Taste `0x22` gedrückt
(`0xC0042BB8(0x22, 1)`), beliebig oft `0xC004596C(x, y)` mit x und y als Rohwerte 0 bis 1023, Taste `0x22` losgelassen. Gespielt
wurden acht Punkte (100 bis 900) im Master-FX-Modus und im Touch-Scale-Modus, je als Nachricht und als Aufruf. Pattern-Block, Display und
Assertions sind in beiden Wegen gleich.

- **Master FX (gemessen, `touch-mfx-xy-bytes`).** Das Pattern hält die Lage bei `+0x40` (Flag, 1 solange berührt, 0 nach dem Loslassen),
  `+0x42` (x) und `+0x43` (y), 7 Bit: x roh 200, 300, 400, 500, 600, 700, 100, 900 ergibt 24, 36, 50, 62, 74, 86, 12, 112; y roh 300, 350, 400, 500,
  650, 800, 100, 900 ergibt 36, 42, 50, 62, 80, 100, 12, 112.
- **Scale (gemessen).** Die Berührung spielt eine Note; die Lage steht im Wort `0xC06B20F0`. Das Pattern ändert sich nicht.
- **Die Master-FX-Taste ist ein Schalter (gemessen, `touch-master-fx-latches`):** einmal gedrückt und losgelassen bleibt der
  Pad-Modus Master FX (LED `0x1C` an, `0x1B` aus). Man muss sie nicht halten.
- **Aufnahme (gemessen, `touch-rec-mfx-lanes-same-for-both-paths`, `touch-rec-scale-notes-same-for-both-paths`).** Mit REC und PLAY schreibt
  die Firmware eine Master-FX-Geste in drei Bewegungsspuren (Ziele 15, 16 und 19, Eintrag bei `0x11C` bis `0x11E`, siehe
  Abschnitt 3: Master FX X, Master FX Y und MFX Pad An/Aus) und eine Scale-Geste als Noten in die Sequenz des Parts. Aufruf und Nachricht ergeben dasselbe.

## 3. Motion Sequence

**Der Schalter (gemessen, `motion-mode-byte`, `motion-mode-byte-part2`).** Menü Part, Seite 21 von 29 "MOTION SEQ" mit den Werten
Smooth, Trigger Hold, Off. Das Byte liegt bei `Pattern + 0x807` (Part 1) und `+ 0x330` je Part, dazu eine Kopie im Abstand `0x382E` (Part 1
`0x4035`, Part n `0x4035 + 0x24 * (n - 1)`); das Menü ändert beide (`motion-mode-byte-per-part-and-copy`, gemessen für die Parts 1, 2, 3 und
6). Werte: 0 Off, 1 Smooth (Vorgabe), 2 Trigger Hold, wie `part.motionMode` der Gerätekarte (Korg-Spezifikation). Die Meldung "Motion Seq
Full" (String `0xC00A5D33`) und die Seite CLEAR MFX MOTION im Pattern-Menü zeigen, dass die Spuren ein Vorrat sind (hergeleitet).

**Die Spuren (gemessen, `motion-rec-same-lane-for-both-paths`, `motion-rec-byte-is-half-plus-one`, `gate-part-two-has-its-own-switch`).**
Die Firmware nimmt Reglerbewegungen mit REC und PLAY in Spuren auf, die jeweils das nächste freie Fach im Pattern belegen:

| Was | Wo (Pattern-Offset) |
|---|---|
| Part je Spur (0 Aus, 1 bis 16 der Part, 17 Master FX): `motion.part` der Gerätekarte | `0x104 + Spur` |
| Ziel je Spur (nach der Zielliste der Korg-Spezifikation: 10 Amp Level, also Regler 0, und 15, 16, 19 Master FX X, Master FX Y, MFX Pad An/Aus): `motion.destination` | `0x11C + Spur` |
| Daten, 64 Bytes je Spur, ein Byte je Schritt, `(wert >> 1) + 1`, 0 heißt kein Eintrag: `motion.value` | `0x134 + 0x40 * Spur + Schritt` |

Das sind die Felder, die die Gerätekarte schon aus der Korg-Spezifikation kennt, "am Gerät nicht geprüft". Gemessen ist jetzt: die Firmware legt
sie so an (Part 1 gleich 1, Part 2 gleich 2, eine Master-FX-Geste ergibt drei Spuren mit den Zielen 15, 16 und 19, ein Regler eine mit 10), und
24 Spuren je Pattern (die Tabellen haben 24 Plätze). Die Spuren gehören zum Pattern-Format und gehen darum mit WRITE auf den Speicher des
Geräts (hergeleitet, am Gerät nicht geprüft), anders als alles, was ein Plugin hält. Ein eingespielter Regler schreibt in dieselbe Spur wie eine
Nachricht: gleicher Eintrag, gleiche Bytes (`09 0D 11 15 ...` für `16, 24, 32, 40 ...`), gleiche Halte-Bytes hinter dem letzten Wert. Die Aufnahme
läuft auch bei Modus Off (`gate-rec-with-mode-0`).

**Wiedergabe (gemessen, `motion-engine-follows-the-recorded-lane`).** Sie ändert das Parameter-Byte nicht. Ihr Ausgang für Spur 0 ist das
Wort `0xC068DB1C` (die Spuren 1 und 2 bei `+4` und `+8`): `0xFFFFFFFF` heißt still, sonst steht dort der Wert des Spurbytes
ohne die Verschiebung, einmal je Schritt neu. Für die Spur des Tests (16, 24 ... 136) steht dort 8, 12 ... 68, Schritt für Schritt. Ob die Stimme dem Ausgang der
Spur oder dem Parameter-Byte folgt, sieht der Emulator nicht (das DSP ist nicht nachgebildet): **offen**, am Gerät zu hören.

**Schalten per RAM-Schreiben (gemessen, `motion-ram-mode-byte-off-silences-playback`, `motion-ram-mode-byte-is-0x807-not-the-copy`,
`motion-ram-mode-byte-live`, `gate-switch-on-at-the-bar-and-off-again`).**

| Schreiben | Wirkung auf die Wiedergabe von Spur 0 |
|---|---|
| `+0x807` und Kopie auf 0 | still in allen 16 Schritten |
| nur `+0x807` auf 0 | still |
| nur die Kopie auf 0 | spielt weiter (16 verschiedene Werte) |
| `+0x807 + 0x330` (Part 2) auf 0, Spur gehört Part 1 | spielt weiter |
| beide auf 2 (Trigger Hold) | spielt (16 Werte; ob Hold einen hörbaren Unterschied macht: offen) |
| während des Spielens bei Schritt 24 auf 0 | Ausgang bis Schritt 24 wie aufgenommen, ab Schritt 25 still |
| von 0 auf 1 bei Schritt 16, zurück auf 0 bei Schritt 24 | die Spur spielt in den Schritten 17 bis 24 (12, 16 ... 40), sonst still |

Maßgebend ist also `Pattern + 0x807 + 0x330 * Part`; die Kopie schaltet nichts. Zwei Parts haben ihre eigene Spur und ihren eigenen
Schalter (Part 2: Eintrag 2, Ziel 10; Schalter von Part 1 auf 0 lässt Part 2 spielen und umgekehrt).

**Master-FX-Spuren (gemessen, `gate-mfx-lanes-ignore-the-part-byte`).** Die drei Spuren einer Geste spielen mit Part-Byte 1 und 0 gleich
(16 verschiedene Wertepaare in beiden Läufen). Ebenso wirkungslos: den Part-Eintrag bei `0x104` auf 0, 1 oder 0x10 setzen oder das Ziel bei `0x11C` auf
`0xFF` (`gate-mfx-registry-writes-do-not-switch-them`, in allen vier Läufen spielen alle Spuren). Ein Schalter für diese Spuren ist nicht
gefunden: **offen**.

**Regler gegen Spur (gemessen, `motion-moving-injection-silences-the-lane-then-it-resumes`, `motion-constant-injection-is-ignored-after-the-first-call`).**
Gibt man Reglerwerte ein, während die Spur spielt, verhält sich die Firmware wie bei der Hand am Regler: der Ausgang der Spur wird still
(`0xFFFFFFFF`), solange sich der Wert ändert, und die Spur spielt wieder, 5 bis 6 Schritte (rund 0,55 s bei 160 BPM) nach dem letzten
geänderten Wert (Eingriff Schritte 16 bis 25, still ab 18 bis 30, wieder da bei 31). Ein zweimal gleicher Wert zählt nicht als
Eingriff: ein konstanter Wert hält die Spur nur für diese 5 bis 6 Schritte an. Das Parameter-Byte nimmt den eingespielten Wert an, und die Spur läuft
daneben weiter. Ohne Schalter (Part-Byte 0) bleibt der eingespielte Wert allein (`motion-off-then-injection-alone`).

**REC (gemessen, `motion-rec-without-record-flag-injects-nothing`).** Spielt man während der Aufnahme der Firmware ein, nimmt sie es
auf (Abschnitt 1). Eine Funktion, die einspielt, darf es nur außerhalb von REC tun oder muss es wollen.

## 4. Takt

**Schrittzähler (gemessen, `bar-counter-16-slot-groups`, `bar-beat-32-has-32-slots-per-bar`).** Das Wort `0xC06904B0 + 0x48 * Part` zählt
`Gruppe * 16 + Schritt in der Gruppe`. Eine Gruppe ist bei BEAT 16 und 8 Tri ein Takt, bei BEAT 32 und 16 Tri ein halber. Bei 160 BPM:

| BEAT (Pattern-Byte `+0x2A`) | Schritt | Zähler | Takt (4 Viertel) |
|---|---|---|---|
| 16 (0) | 93,75 ms | 0 bis 63, ein Zähler je Schritt | 16 Plätze, bis 4 Takte |
| 32 (1) | 46,9 ms | 0 bis 63 | 32 Plätze, bis 2 Takte |
| 8 Tri (2) | 125 ms | 0 bis 11, dann 16 bis 27 usw. (Sprung 5) | 16 Plätze, 12 gespielt |
| 16 Tri (3) | 62,5 ms | wie 8 Tri, 12 je 16er Gruppe | 32 Plätze, zwei Gruppen je Takt |

Mit der Vorgabe Länge 4 (Byte `+0x29`, 3 gleich 4 Takte) laufen BEAT 32 und 16 Tri über 2 Takte. Eine Taktgrenze ist damit
`zähler >> 4` (BEAT 16 und 8 Tri) oder `zähler >> 5` (BEAT 32 und 16 Tri) ändert sich, nicht `zähler % 16 == 0`: bei Tri und kurzen
Schritten kann der Zähler die 0 überspringen.

**Je Part ein Zähler (gemessen, `bar-counter-is-per-part-and-last-step-shortens-it`).** LAST STEP je Part (Byte `+0x804 + 0x330 * Part`, 0 heißt
16, sonst die Zahl; das ist `part.lastStep` der Gerätekarte, dort noch "Bedeutung offen") kürzt den Takt dieses Parts: bei 8 zählt Part 1 `0 bis 7, 16 bis 23, 32 bis 39`, seine Takte sind 8 Schritte lang,
Part 2 zählt `0 bis 15, 16 ...` weiter. Das `step`-Ereignis der Laufzeit liest Part 1 (`0xC06904B0`). Mit verkürztem LAST STEP an Part 1
stimmen seine Taktgrenzen nicht mit denen des Patterns überein: für einen Takt braucht es den Zähler eines Parts mit LAST STEP 16.

**Rahmenraster (gemessen, `bar-frame-misses-steps-only-when-steps-are-shorter-than-a-frame`).** In 8 s beim Raster von 40 ms verlorene
Schritte: BEAT 16 mit 160 und 300 BPM: 0; BEAT 32 mit 160 BPM: 0; BEAT 32 mit 300 BPM (Schritt 25 ms): 120. Der Takt selbst geht nicht verloren, wenn der
Vergleich auf die Gruppe zielt (`>>` statt `== 0`), hergeleitet: der Stumpf vergleicht so und hat im Lauf mit 40-ms-Raster nie einen Takt verpasst, geprüft ist es nur bei BEAT 16 und 160 BPM.

**Start zum nächsten Takt (gemessen, `bar-start-is-the-next-bar`, `bar-start-late-by-at-most-a-frame`).** Der Stumpf im Rahmenhaken fängt
bei der nächsten Gruppe an: TAP bei Schritt 2, 5, 10 und 14 beginnt bei Schritt 16, TAP bei Schritt 17 bei Schritt 32. Vom Schrittwechsel
bis zum ersten eingespielten Wert vergehen 10 bis 30 ms (ein Rahmen, 40 ms, ist die Grenze).

## 5. TAP und SHIFT+TAP

**Was die Firmware tut (gemessen, `tap-stock-plain-sets-tempo`, `tap-stock-shift-tap-opens-the-bpm-page`).** TAP allein ist Tap-Tempo: vier
Tastenschläge im Abstand 0,65 s ergeben 92,3 BPM (Tempo-Wort `0xC0691518` gleich 923). SHIFT+TAP stellt kein Tempo, sondern
öffnet das Pattern-Menü auf der Seite BPM (Bildschirm 3, Seite 1 von 29 "BPM").

**Was die Laufzeit kann (gemessen, `runtime-mask-0-plugin-sees-tap-and-firmware-takes-it`, `runtime-mask-1-drops-every-key-not-only-tap`,
`runtime-plugin-sees-shift-and-tap-in-order`).** Mit der echten Laufzeit und einem Plugin, das Tasten zählt (`tools/emu/tap_motion_request.mjs`):

| Fangmaske | TAP (4 Schläge) | Part-Taste |
|---|---|---|
| 0 (nichts gefangen) | Plugin sieht 4 TAP, Firmware stellt 92,3 BPM | Plugin sieht sie, Part wechselt |
| 1 (Klasse Tasten) | Plugin sieht 4 TAP, Tempo bleibt 160,0 | Plugin sieht sie, Part wechselt nicht |

Die Maske gilt für eine Klasse (Bit n gleich Nachrichtentyp n, `input_mask` in `script_hooks.s`, offline gelesen): Bit 0 sperrt alle Tasten. Eine
Einzeltaste lässt sich damit nicht fangen. Das Plugin sieht SHIFT und TAP in dieser Reihenfolge.

**Prototyp einer Maske je Taste (gemessen, `tap-stub-drops-plain-tap`, `tap-stub-sees-shift-tap`, `tap-stub-other-keys-pass`,
`tap-stub-without-drop-flag-is-the-stock-behaviour`).** Ein Stumpf am Eingangsfilter, der nur Taste 3 ohne SHIFT verschluckt: vier TAP gehen
nicht an die Firmware (Tempo bleibt 160,0, die vier Schläge sind gezählt), SHIFT+TAP wird getrennt gezählt (drei Schläge), die
Part-Taste kommt durch, ohne gesetzten Schalter ist es das Verhalten der Firmware (923).

**Tap-Tempo im Plugin (gemessen, `tap-plugin-side-tap-tempo-matches-the-firmware`).** Setzt man das Tempo mit dem Mittel der drei
Abstände (0,65 s) über die Funktion, die `korg.tempo` ruft (`0xC004A80C`), ergibt das 923, wie die Firmware. Das Tap-Tempo kann also ein
Plugin auf SHIFT+TAP rechnen, ohne dass der Tastendruck verschluckt werden muss: die Firmware öffnet dabei die Seite BPM, die das neue
Tempo zeigt.

## Was offen bleibt

- **Alles am Gerät.** Hörbarer Unterschied zwischen Spur und Parameter-Byte, was die Stimme beim Abschalten tut (springt der Parameter
  auf den Reglerwert zurück?), ob Trigger Hold einen anderen Klang als Smooth gibt, Zeit eines Aufrufs mit echter Last.
- **Wertebereich der Regler am Gerät** (255 oder 1023, Abschnitt 1) und damit der Bereich einer Einspielfunktion.
- **Parameterfenster ohne Meldung** und ob es bei viel Einspielen stört (Abschnitt 1).
- **Ein Schalter für die Master-FX-Spuren** (Abschnitt 3); bis dahin braucht ein Abspielen von Gesten das Einspielen von Touchpad-Werten.
- **Spurzahl.** 24 Spuren je Pattern sind hergeleitet, bis zur Meldung "Motion Seq Full" nicht gefüllt.
- **Karten- und Menüarbeit** für ein Plugin, das Aufnahmen selbst hält (Abschnitt Entwurf in Idee 39).
