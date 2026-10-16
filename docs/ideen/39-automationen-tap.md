# Idee 39: Automationen auf TAP

Stand: **als Firmware-Patch gebaut und im Emulator geprüft** (`data/patches/tap-motion.json`, [Messung](../messungen/2026-10-15-tap-motion-patch.md)), am Gerät nichts bestätigt. Der Entwurf als Plugin weiter unten ist damit nicht mehr der Weg; er bleibt als Hintergrund stehen. Recherche im Emulator: [Messung](../messungen/2026-10-15-tap-motion.md). Zurück zu den [Ideen](../ideen.md).

Reglerbewegungen aufnehmen (wie Motion Sequence) und per TAP für den gewählten Part abspielen. Ist Pad 1 gewählt, spielt TAP die Aufnahme dieses Parts, im Takt, ab dem nächsten Takt. Für Touchpad-Gesten hält man den jeweiligen Master-FX-Knopf und drückt TAP. Dazu ein eigenes Menü zum Aufnehmen und Verwalten.

Vorrang haben diese Automationen vor Code-Plugins auf TAP; Code ist Teil 2.

## Gebaut: TAP Motion als Firmware-Patch

Entschieden (2026-10-15): ein Patch im BLECH-Satz, kein Plugin (die Plugin-Laufzeit ist voll, der Patch hat einen eigenen Codebereich).

1. Bewegungen werden wie immer mit REC aufgenommen und liegen im Pattern, eine Aufnahme je Part.
2. TAP schaltet die Motion Sequence des gewählten Parts sofort, wie Gross Beat in FL Studio, ohne auf den Takt zu warten: aus ist das Byte 0, an gibt den Modus zurück, den der Part hatte (Smooth, wenn er nie einen hatte; Smooth ist die Vorgabe der Firmware, auch nach einer Aufnahme).
3. Das Tap-Tempo der TAP-Taste ist weg, SHIFT + TAP bleibt die Seite BPM der Firmware.
4. Die TAP-Lampe zeigt den Zustand des gewählten Parts und folgt dem Part-Wechsel.
5. Menü BLECH, Seite TAP MOTION in der Liste (ON ist die Vorgabe): OFF ist die Firmware ohne den Patch; ohne Karte oder mit EXIT beim Einschalten ebenso.
6. **Master FX:** ein Schalter ist gefunden, das Byte `+0x44` im Pattern-Objekt; MASTER FX gehalten und TAP schaltet die Geste (und lässt den Effekt los, wenn die Geste gerade lief). Das Einspielen von Touchpad-Werten (Weg B) ist dafür nicht nötig. Gehalten statt "als Pad-Modus gewählt", weil das Pad nach dem Start auf Master FX steht und der Part sonst in der Grundstellung nicht zu schalten wäre.

Zusammenspiel: WRITE sichert den Zustand, den das Byte beim WRITE hat; ein Patternwechsel lädt, was geschrieben ist, und vergisst den gemerkten Modus; REC nimmt bei ausgeschalteter Bewegung auf; bei offener App gehört TAP der App und schaltet nichts. Alles in der [Messung](../messungen/2026-10-15-tap-motion-patch.md), Gerätetest in [live.md](../geraetetests/live.md#4-tap-motion). Offen am Gerät bleibt, was man hört (Punkte 1 und 2 der Liste ganz unten).

## Was die Recherche ergeben hat

Alles im Emulator gemessen, die Zahlen und Namen der Prüfungen stehen in der [Messung](../messungen/2026-10-15-tap-motion.md).

- **Die Firmware hat die Aufnahme schon.** REC plus Regler schreibt die Bewegung in Spuren im Pattern (64 Schritte je Spur, ein Byte je Schritt), WRITE sichert sie mit dem Pattern (hergeleitet: die Spuren gehören zum Pattern-Format der Korg-Spezifikation). Das Menü Part, Seite 21 "MOTION SEQ" (Smooth, Trigger Hold, Off) liegt als ein Byte je Part im Pattern (`+0x807 + 0x330 * Part`). Schreibt man dieses Byte im RAM, schaltet die Wiedergabe der Spuren des Parts ab dem nächsten Schritt ein oder aus. Die Aufnahme läuft auch bei Off.
- **Eine Regler-Bewegung lässt sich auch einspielen.** `0xC0040A50(index, wert)` aus dem Rahmenhaken wirkt wie ein echter Regler (55 von 55 Fällen gleich), auch in der Aufnahme der Firmware. Es öffnet das Parameterfenster wie ein echter. Das gilt ebenso für Touchpad-Gesten (Taste `0x22`, `0xC004596C(x, y)`).
- **Master-FX-Gesten spielt die Firmware ohne das Part-Byte,** ihre drei Spuren lassen sich damit nicht abschalten. Gefunden ist später ein eigenes Byte bei `+0x44` im Pattern-Objekt ([Messung](../messungen/2026-10-15-tap-motion-patch.md#master-fx-ein-schalter-ist-gefunden)); der Satz "nur das Einspielen bleibt" gilt nicht mehr.
- **Ein Takt** ist `zähler >> 4` (BEAT 16 und 8 Tri) oder `>> 5` (BEAT 32 und 16 Tri) des Schrittzählers; der Zähler läuft je Part, ein Part mit verkürztem LAST STEP hat kürzere Takte. Der Start im Takt ist auf einen 40-ms-Rahmen genau.
- **TAP einzeln fangen** kann die Laufzeit heute nicht (die Fangmaske gilt für alle Tasten). SHIFT+TAP ist in der Firmware belegt (Seite BPM des Pattern-Menüs), stellt aber kein Tempo; das Tap-Tempo kann ein Plugin selbst rechnen.

## Entwurf

Zwei Wege, ein Plugin "Automation" (eine App unter TOOLS).

**Weg A: Spur schalten (für Regler).** Aufgenommen wird mit der Firmware, mit REC und den Reglern, wie bei jeder Motion Sequence. Wer eine Aufnahme nur auf Abruf will, stellt den Part danach im Menü der Firmware auf MOTION SEQ Off. Das Plugin schaltet ihn bei TAP zum nächsten Takt ein (Byte 1) und nach einer wählbaren Zahl Takte wieder aus. Die Aufnahme liegt im Pattern und überlebt Ausschalten und Patternwechsel wie alles im Pattern, sobald es mit WRITE gesichert ist. Das Plugin braucht dafür keinen eigenen Speicher und keine Einspielfunktion, und es ändert keinen Schalter, den man nicht per TAP anfasst.

**Weg B: Einspielen (für Gesten, später auch für Regler).** Das Plugin nimmt selbst auf (die Ereignisse `knob`, `touch` und `step` sind schon da) und spielt mit `korg.knob.set` und `korg.touch.set` ab. Nötig für Gesten, weil sich ihre Spuren nicht schalten lassen, und für alles, was nicht an ein Pattern gebunden sein soll.

Empfehlung: **A zuerst, B danach.** A ist klein, nutzt die Firmware, wie sie ist, und läuft ohne Speicherfrage. B ist größer, kostet Speicher und bringt die Nebenwirkungen des Einspielens mit (Parameterfenster, Aufnahme der Firmware, zwei Tasks).

### Die kleinste Schnittstelle

Namen als Vorschlag; Bereiche, Version und Beschreibungstexte setzt der Vertrag (`data/script/contract.mjs`).

| Aufruf | Wirkung | Weg | Erlaubt in |
|---|---|---|---|
| `korg.read.motion(part)` | 0 Off, 1 Smooth, 2 Trigger Hold, gelesen bei `Pattern + 0x807 + 0x330 * part` | A | überall |
| `korg.motion(part, modus)` | schreibt Byte und Kopie (siehe unten) | A | wie `korg.mute` |
| `korg.read.beat()` | BEAT des Patterns: 0 für 16, 1 für 32, 2 für 8 Tri, 3 für 16 Tri (Byte `Pattern + 0x2A`), für die Taktgrenze | A | überall |
| `korg.capture(taste, an)` | die Taste geht nicht mehr an die Firmware, das Plugin sieht sie weiter; EXIT, die Ausschalt-Taste und PLAY, STOP, REC lassen sich nicht fangen | A, B | wie `korg.led` |
| `korg.knob.set(index, wert)` | wie ein Regler, `index` 0 bis 10, `wert` 0 bis 255 | B | wie `korg.play` |
| `korg.touch.set(x, y)` | Finger bei (x, y): drückt beim ersten Aufruf Taste `0x22` und ruft dann `0xC004596C` | B | wie `korg.play` |
| `korg.touch.release()` | Taste `0x22` loslassen | B | wie `korg.play` |

- **Weg A braucht drei kleine Funktionen und die Fangfunktion.** Die Schrittzähler liefert `korg.read.step(part)` schon (alle 16 Parts), nur der BEAT fehlt, damit das Plugin weiß, wie lang ein Takt ist. Lesen und Schreiben eines Bytes im Pattern sind je ein paar Befehle, wie bei `korg.read.mute`.
- **Die Kopie des Schalters:** das Menü ändert zwei Bytes, `+0x807 + 0x330 * part` (maßgebend, gemessen) und die Kopie bei `+0x4035 + 0x24 * part`. Die Funktion schreibt beide, damit das Pattern aussieht, als wäre es im Menü geändert worden.
- **`korg.capture`** braucht in `input_mask` (`tools/patch/script_hooks.s`) eine zweite Maske für Tasten (35 Bits, zwei Wörter, `RT_KEY_CAPTURE`) vor der Klassenmaske; das Plugin gibt die Sperre mit seinem Ende (Fehler, Pause, Ausschalten) wieder zurück, wie die Laufzeit es bei `korg.ledHold` tut. Eine Prüfung gegen EXIT und PLAY, STOP, REC steht im Vertrag.
- **Optional, nicht nötig für den Anfang:** `korg.read.lanes(part)` (wie viele Spuren dem Part gehören, aus den Part-Einträgen bei `0x104`) für die Anzeige, ein Ereignis `bar` statt der 16 Lesezugriffe auf die Zähler.
- **Reglerwerte klemmt die Funktion auf 0 bis 255,** solange offen ist, was das Panel am Gerät schickt (Messung, Abschnitt 1). Die Firmware übergeht einen Wert, der `wert >> 1` nicht ändert (187 statt 2100 bis 4000 Befehle), ein Aufruf mit dem alten Wert kostet also fast nichts.

### Ablauf Weg A

1. Menü `AUTOMATION` AN: das Plugin fängt TAP (`korg.capture(korg.key.TAP, 1)`). Sonst ändert es nichts, auch keinen Schalter.
2. TAP: der gewählte Part (`korg.read.part()`, 16 heißt alle) wird zum nächsten Takt umgeschaltet. Steht er auf Off, wird er Smooth; steht er auf Smooth oder Hold, wird er Off. Der alte Wert wird gemerkt. Läuft der Transport nicht (`korg.read.transport()` ist nicht 1), passiert nichts, die TAP-LED blinkt kurz.
3. Im letzten Schritt des Takts schaltet das Plugin um (im `step`-Ereignis): die Wiedergabe wirkt ab dem Schritt danach (gemessen: Schalten bei Schritt 16 ergibt Wiedergabe ab 17), so beginnt die Spur auf der Eins. Der Takt ist `zähler >> 4` (BEAT 0 und 2) oder `>> 5` (BEAT 1 und 3), gelesen vom kleinsten Zähler aller Parts, weil ein Part mit verkürztem LAST STEP seine Takte früher beginnt.
4. Nach der gewählten Zahl Takte (Menü `BARS`, 0 heißt bis zum nächsten TAP) schaltet es auf den alten Wert zurück.
5. `patternChange`, `stop` und das Ende des Plugins geben die Schalter zurück, die das Plugin umgelegt hat. Wechselt das Pattern, gelten die Schalter des neuen.

### Ablauf Weg B

1. Aufnehmen (Menü `GESTURE REC`): bei jedem `step` merkt das Plugin Lage des Fingers (aus `touch` und `buttonPress`/`buttonRelease` der Taste `TOUCHPAD`) in einem Feld je Part, ein Wort je Schritt (`x << 10 | y`, 0 heißt nichts). Reglerbewegungen genauso mit Regler und Wert.
2. Abspielen (Master FX gewählt, TAP): ab dem nächsten Takt je Schritt `korg.touch.set(x, y)`, am Ende `korg.touch.release()`.
3. Während die Firmware selbst aufnimmt (Transport 3, 4 oder 5), spielt das Plugin nichts ein, sonst landet es in der Aufnahme der Firmware.

### Speicher

| Was | Wo | Wieviel | Wann weg |
|---|---|---|---|
| Regler-Aufnahme (Weg A) | Spuren im Pattern | 64 Byte je Spur, bis 24 Spuren je Pattern | mit dem Pattern (WRITE sichert sie) |
| Schalter je Part | im Pattern, Byte und Kopie | 2 Bytes je Part | mit dem Pattern |
| Gesten (Weg B) | Feld im Plugin, 1 Wort je Schritt | 4 KiB für 16 Parts mit 64 Schritten | beim Ausschalten, bis es eine Karten-Funktion gibt |
| Gesten auf der Karte (später) | `KORG/blechtribe/Plugin/<name>.<platz>.bin`, zwei Dateien im Wechsel wie `store.a.bin` | je Platz bis 4 KiB | nie von selbst; geschrieben wird nur auf Anforderung, frühestens 2 s nach dem letzten Schreiben |

**Nie in den Flash.** Die 16 Plätze von `korg.store` reichen für keine Aufnahme (64 Byte), darum eine Funktion `korg.blob` (Platz, Feld, Länge) als eigener Schritt, wenn Gesten bleiben sollen; bis dahin gelten sie nur bis zum Ausschalten. Der Pool für Plugins (128 KiB) trägt vier KiB.

### Menü

Je eine Seite in der Gruppe PLUGINS über `korg.menu.add` (höchstens zwölf Seiten für alle Plugins zusammen):

| Seite | Werte | Wirkung |
|---|---|---|
| `AUTOMATION` | OFF, ON | AN fängt TAP; AUS gibt TAP an die Firmware zurück, alles andere wie am Anfang |
| `BARS` | 0 bis 4 | Wie viele Takte ein TAP spielt, 0 bis zum nächsten TAP |
| `TAP TEMPO` | OFF, ON | SHIFT+TAP rechnet das Tap-Tempo (Mittel der letzten drei Abstände, `korg.tempo`); die Firmware öffnet dabei die Seite BPM, die das Tempo zeigt |
| `GESTURE REC` (B) | OFF, ARM | schaltet die Geste auf Aufnahme |

Dazu die App "Automation" unter TOOLS: die 16 Parts als Pads mit Zustand (Spur ja oder nein, an, wartet auf den Takt), Aufnahme von Gesten, Löschen einer Geste. Spuren löscht die Firmware selbst (Part-Werkzeuge, CLEAR MOTION).

### Aufwand und Risiko

Schätzung aus der Größe der bisherigen Schritte (`korg.mute` mit Tests und Beschreibung war etwa ein halber Tag), nicht gemessen:

| Schritt | Aufwand | Risiko |
|---|---|---|
| `korg.read.motion`, `korg.motion`, `korg.read.beat` (ARM-Glue, Vertrag, Beschreibung, Tests im Emulator) | 0,75 Tage | klein: ein Byte je Funktion |
| `korg.capture` (zweite Maske im Eingangsfilter, Freigabe bei Fehler und Pause, Tests) | 1 Tag | mittel: eine tote TAP-Taste, wenn die Freigabe fehlt; Ausweg: EXIT beim Einschalten, Seite RUNTIME |
| Plugin "Automation", Weg A, mit Menü, Probe im Editor, Emulatorlauf | 1,5 Tage | klein |
| Weg B: `korg.knob.set`, `korg.touch.set`, `korg.touch.release`, Aufnahme und Abspielen im Plugin | 3 Tage | mittel: Parameterfenster, zwei Tasks, Aufnahme der Firmware |
| Karte: `korg.blob` mit Datei, Prüfsumme, zwei Dateien im Wechsel | 2 Tage | mittel: Schreiben auf eine echte Karte, wie bei `korg.store` ungeprüft |
| Gerätetest der Schritte (Liste unten) | 1 Tag | die Unbekannten stehen alle am Gerät |

Weg A allein mit Gerätetest: rund 4 Tage. Mit Weg B und Karte: rund 9 Tage.

Als fest eingebaute Firmware-Funktion (ohne Plugin) wäre es ein eigener Patch mit denselben Haken (Eingangsfilter, Rahmenhaken) und eigenem Menü, rund 4 bis 5 Tage für A, also nicht billiger, aber ohne die Plugin-Sprache, ohne Menüseiten und ohne Speicher für B. Dagegen spricht, dass `korg.capture` und `korg.motion` auch Idee 34 und andere Plugins brauchen.

### Offen und am Gerät zu prüfen

1. Klingt es richtig, wenn das Part-Byte mitten im Spiel umspringt: Sprung des Parameters beim Ein- und Ausschalten, Rückkehr auf den Reglerwert nach dem Abschalten (im Emulator ohne DSP nicht zu sehen).
2. Unterschied zwischen Smooth und Trigger Hold.
3. Wertebereich der Regler (255 oder 1023) und ob eingespielte Werte am Gerät das Parameterfenster zu oft öffnen.
4. ~~Ein Schalter für die Master-FX-Spuren~~: gefunden, das Byte `+0x44` (siehe oben). Am Gerät offen, ob 2 anders klingt als 1.
5. Der Vertrag ändert sich gerade; die Namen oben sind Vorschläge.

Plugins bekommen Regler-, Touchpad-, Sequencer- und Tastenereignisse ([Plugins](../plugins.md)); die Messung zeigt, was darüber hinaus fehlt (nur die Funktionen der Tabelle).
