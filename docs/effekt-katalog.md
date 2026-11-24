# Effekt-Katalog

Der Katalog im Baukasten (`BLECHTRIBE -> Baukasten -> Katalog`, Daten in `data/fx/catalog.mjs`) hat 49 Insert- und Master-Effekte und 6 Modulationen: Delays, Effekte für Bässe, Kicks, Verzerrung und Mix. Die Insert- und Master-Effekte stehen nach dem Patchen fest in den Menüs (hinter den Presets der Firmware, Patch `fx-catalog`, siehe [Patcher](patcher.md#der-patch-satz)),
die Modulationen gehen über den Export auf die Karte. Alle Werte sind die Parameter der 66 [DSP](glossary.md#dsp)-Bausteine, die schon in der
Firmware stecken: es gibt keine neuen Bausteine, ein Effekt ist eine Einstellung davon.

**Am Gerät ist keiner dieser Effekte gehört.** Der Emulator rechnet kein Audio, er zeigt nur, dass die Presets sauber in die
Menüs kommen und dem DSP ihre Werte schicken ([Messung](messungen/2026-11-11-neue-effekte.md)). Die Werte sind aus den
Werkspresets derselben Bausteine hergeleitet. Wenn dir einer zu laut, zu leise oder anders vorkommt, ist das der Hörtest, der noch fehlt.

## Gleiche Plätze auf Korgs 2.02 und Hacktribe

Beide roten Firmwares haben dieselben Insert-Plätze: 1 bis 38 Korgs Werkspresets, 39 bis 49 Hacktribes eigene
Inserts (Lag, KP2 Comp, LP Drive, LP Drive Res, HP Drive, HP Res Drive, BP Drive, BP Drive Res, 9/32 Delay, 3/32 Delay,
1/12 Delay), ab 50 der Katalog. Hacktribe behält auf 39 bis 49 seine eigenen Presets. Korgs 2.02 bekommt dort Nachbauten
aus dem Katalog: dieselben Bausteine, dieselben Notenwerte, die übrigen Werte bewusst leicht anders gesetzt (Hacktribes
Bytes kommen nicht ins Projekt), im Klang nah dran. Master-Effekte: Hacktribe hat keine über Korgs 32 hinaus, es tauscht nur
vier Werksplätze (10 Big Hall, 11 Plate Reverb, 21 Tap Delay Sync, 32 Tube Drive). Korgs 2.02 bekommt diese vier als
Nachbauten auf 33 bis 36, angehängt, kein Werkspreset wird ersetzt; der Katalog beginnt dort bei 37. Hacktribe behält seine
vier auf den Werksplätzen, sein Katalog beginnt weiter bei 33. Das gilt für die Hacktribe-Datei mit 49 Inserts und 32
Master-Effekten. Es gibt auch Hacktribe-Dateien mit mehr eigenen Plätzen, Inserts bis 64 und Master-Effekte bis 50; dort
beginnt der Katalog bei 65 und 51.

Ein Patch-Update einer schon gepatchten Datei gibt dieselben Plätze wie ein Patch der Originaldatei, egal von welcher
Version (siehe [Patcher](patcher.md#eine-datei-auf-der-schon-blechtribe-ist)): die App nimmt die Katalog-Plätze der älteren Version zuerst heraus und legt den Katalog neu an. Sie erkennt
sie am Inhalt. Steht hinter dem Katalog ein eigenes Preset, bleibt es stehen, und mit ihm alles davor. Patterns, die einen
Katalog-Effekt nutzen, zeigen nach einem Update, das die Plätze verschiebt, auf einen anderen Effekt; sie werden nicht
umgeschrieben.

| Name | Baustein | Woher die Werte kommen |
|---|---|---|
| Big Hall | `M_hall_reverb` | Korgs Wet Reverb als Ausgang, länger und dunkler gesetzt, in Richtung Hacktribes Big Hall. Den Baustein nutzt kein Werkspreset. |
| Plate Reverb | `M_wet_plate_reverb` | Korgs Hall Reverb, leicht verschoben. Den Baustein nutzt kein Werkspreset. |
| Tap Delay Sync | `M_tape_echo` | Korgs Tape Delay mit Hacktribes Notenwerten (6 und 8), Ausgangspegel 44 statt 53, leichtes Leiern. |
| Tube Drive | `M_tubepre` | Korgs Tube EQ ohne Tiefen- und Höhenschnitt, Y fährt Sättigung und Gain. |

Im Emulator schicken die vier dem DSP dieselben Bausteine wie Hacktribes eigene, mit den eigenen Werten
([Messung](messungen/2026-11-17-hacktribe-master-rot.md)). Gehört ist keiner.

## Laut

| Name | Art | Was er tut |
|---|---|---|
| Loud Distortion | Insert | Gain 64, Ausgangspegel 15 (Werkspreset 11; höhere Pegel waren am Gerät deutlich lauter als die übrigen Presets, [Pegel](messungen/2026-10-29-fx-katalog-pegel.md)). Regler: Verzerrung. |
| ULTRA LOUD | Insert, zwei Stufen | Acid Drive mit Drive 127 und Ausgangspegel 30, dahinter ein Limiter: Röhrensättigung 127, Ausgangspegel 90 (Lautstärke sperrt der Linter nie, er warnt nur: über 90 `output-too-loud`, von 61 bis 90 `output-above-usable`, "nicht gehört"; 90 ist also die Grenze der Regeln). Regler: Drive 96 bis 127. Distortion vor Limiter stürzt ab, darum Acid Drive ([Messung](messungen/2026-11-11-neue-effekte.md)). |

## Bässe, die springen

Das Problem: die Hüllkurve des Verstärkers klingt zu lang aus und setzt zu langsam ein, die Bassline schiebt statt zu springen. Die
Firmware hat dafür keinen Regler im Effekt, aber zwei Wege:

| Name | Art | Was er tut |
|---|---|---|
| Bounce Gate 16 | Insert | Eine Hüllkurve auf jeder Sechzehntel: schneller Anschlag, kurzes Abklingen. Regler von sanft bis hart, Play setzt den Takt neu an. |
| Bounce Gate 8 | Insert | Dasselbe auf Achtel. |
| Bounce Pluck | Modulation | Jede Note öffnet den Filter kurz und gibt einen kleinen Lautstärke-Schub. Aus einem langen Bass wird ein Pluck. |
| Bounce Pitch | Modulation | Jede Note springt kurz etwa einen Halbton hoch und fällt zurück. Federt. |

Das Gate hängt am Takt der Maschine, nicht an der Note: Noten, die neben dem Raster liegen, werden angeschnitten. Die
Modulationen hängen an der Note und gehen mit jedem Rhythmus. Die Modulationen legst du auf einen Platz der EG+-Arten (1 bis 6):
die Zeit der Hüllkurve (MOD. SPEED) kommt vom Platz, den du überschreibst.

## Bass sauber lauter

| Name | Art | Was er tut |
|---|---|---|
| Bass Enhancer | Insert, zwei Stufen | EQ (2 Bänder) mit Tiefen-Regal und etwas weniger Tiefmitten, dahinter ein Limiter. Regler: mehr Bass, weniger Eingangspegel. |
| Glue Comp | Insert | Sanfter Kompressor auf Korgs Kompressor-Baustein, Werte wie das Werkspreset Sustainer. Regler: Hüllkurve wie dort. |

## Kicks

| Name | Art | Was er tut |
|---|---|---|
| Hardtekk Kick | Insert, eine Stufe | Hart verzerrt: Bass vor der Verzerrung hoch, danach wieder aufgefüllt. Ohne Limiter: Distortion vor Limiter stürzt ab. |
| Tekk Kick Soft | Insert, zwei Stufen | Acid Drive mit EQ dahinter (Bass hoch, Klick oben). Weicher. |
| Kick Drop | Modulation | Die Tonhöhe startet hoch und fällt in Millisekunden ab, dazu ein Lautstärke-Schub. |
| Kick Click | Modulation | Ein sehr kurzer, hoher Pitch-Sprung vorn: der Klick. |

## Verzerrer

| Name | Art | Was er tut |
|---|---|---|
| Warm Drive | Insert, zwei Stufen | Wenig Drive, EQ dahinter: wärmer und dichter. |
| Bass Drive | Insert | Verzerrung, die den Tiefbass stehen lässt. |
| Scream Drive | Insert | Mitten kräftig angehoben, für Leads und Acid. |
| Tight Fuzz | Insert | Fuzz ohne Bass, eng und bissig. |
| Bit Grinder | Insert | Bittiefe zerhackt. |
| Alias Crush | Insert | Abtastrate runter, Aliasing. |

## Mix und Master

| Name | Art | Was er tut |
|---|---|---|
| Tilt EQ | Insert | Kippt den Klang: links heller, rechts dunkler, Mitte unverändert. |
| Mix Clean Up | Insert | Rumpeln unten und Dröhnen in den Tiefmitten raus, oben etwas Luft. |
| Master Glue | Master | Kompressor auf der Summe. X dreht die Schwelle runter. |

## Delays, Hall und weitere Effekte

| Name | Art | Was er tut |
|---|---|---|
| Lag, KP2 Comp, LP Drive, LP Drive Res, HP Drive, HP Res Drive, BP Drive, BP Drive Res, 9/32 Delay, 3/32 Delay, 1/12 Delay | Insert | Nachbauten von Hacktribes Inserts auf den Plätzen 39 bis 49 (siehe oben): Echo ohne trockenes Signal, Kompressor aus dem Kaoss Pad 2, Filter mit Acid-Verzerrer dahinter, Echos auf Notenwerten |
| 1/6 Delay, 1/24 Delay, 5/32 Delay, 3/64 Delay, Slap Delay, Long Delay | Insert | weitere Echos auf Vierteltriolen, Sechzehnteltriolen, 5/4 Achtel, sehr kurz (metallisch), Slapback und punktierter Viertel |
| Fuzz, Crunch, Hot Overdrive | Insert | Verzerrer: voll mit vorgeschobenen Mitten, leicht angezerrt mit mehr Bass, weiter aufgedrehter Overdrive |
| Short Delay, Tri Ping Pong, Dub Echo | Master | kurzes Stereo-Echo, Ping-Pong auf Triolen, Bandecho mit dunkler werdenden Wiederholungen |
| Master Pumper, Tremolo 1/8, Wah 1/8, Small Plate, Master Limiter | Master | Pumpen auf der Summe, Tremolo und Wah im Achteltakt, kurzer Plattenhall, Limiter auf der Summe |
| Filter Wobble, Soft Vibrato | Modulation | Sinuswelle auf dem Filter (Wobble-Bass), leichtes Vibrato der Tonhöhe |

Die Delays rechnen mit Notenwert mal Faktor (hergeleitet aus der DSP-Tabelle ab DSP `0x9470`, Records zu 6 Byte): Notenwert 0 bis 13 ist 1/64, 1/32, 1/24, 1/16, 1/12, 1/8, 1/6, 3/16, 1/4, 1/3, 3/8, 1/2, 3/4, 1; der Zeitfaktor 0 bis 13 ist 1/8, 1/6, 1/4, 1/3, 1/2, 2/3, 3/4, 1, 5/4, 4/3, 3/2, 2, 5/2, 3. Alle Delay-Presets beider Firmwares passen auf diese Tabellen. Offen: ob "1" ein Takt oder eine Viertel ist. Am Gerät gemessen (21.09.): Der Insert-Distortion-Baustein ist mit `output_level` 124 unspielbar laut, spielbar waren 38 bis 60, darum stehen die Verzerrer hier auf Ausgangspegel 30 bis 40.

## Wie der Katalog gebaut wird

Die rohen Messnotizen stehen in der Git-Historie (`git show 03c7827adc7b:docs/messungen/<Datei>`).

### Anhängen (`fx-catalog`, `src/fx-append.mjs`)

- Jeder neue Platz ist eine Kopie von Preset 1 derselben Firmware, darin der Effekt (`fxToRecord`, wie bei der Sammeldatei). Sie hängen
  hinter dem letzten Preset jedes Menüs, die Menülängen gehen um die Zahl der Einträge hoch.
- Ein Effekt, dessen Name im Menü schon steht, wird ausgelassen. Zweimal angewendet kommt nichts dazu.
- Die Plätze hängen davon ab, wie viele Presets die Firmware schon hat. Was der Katalog schreibt, bleibt deshalb Nutzerdaten der
  Patch-Datei (`src/patchfile.mjs`), ihre Fingerabdrücke hängen nicht davon ab.
- Nur rot (Hacktribe und Korgs Original). Die blaue hat dieselben Bausteine und Records, der Karte fehlen nur ihre Orte
  ([eigene Effekte auf der blauen](messungen/2026-11-08-blau-eigene-effekte.md)). Short Delay sitzt auf demselben Basis-Record wie der
  ESX-Aufbau, der am Gerät gehört wurde.

Quelle: Messung 2026-10-23/fx-katalog-fest

### Stufenblock und unbenutzte Bausteine

Sieben Master-Bausteine stehen in Hacktribe in keinem Preset: mKP2 Comp, Limiter, 4 Band EQ, Wah, Tremolo, Level Mod, Dry Plate Reverb.
Wah und Level Mod hat Korgs Original in Presets, die übrigen fünf stehen in keiner der beiden Firmwares in einem Preset.

- **Gemessen (offline):** der Stufenblock (74 Byte ab dem Baustein-Byte) ist in allen Werkspresets beider Firmwares an jeder Stelle gleich, bis
  auf das Baustein-Byte, das Byte danach (meist `0x40`) und die Parameterwerte. Die ungeraden Bytes zwischen den Parametern und die 15 Bytes
  dahinter sind überall null. Geprüft mit `factory-check:stage-block-shared` (Hacktribe: Master 32, Insert Stufe 1 49, Stufe 2 8 Presets;
  Korg rot: 32, 38, 2).
- Darum nimmt `fxToRecord` für einen Baustein, den kein Preset trägt, den Stufenblock, den die meisten Presets an dieser Stelle teilen, und
  ändert nur das Baustein-Byte.
- **Offen:** ob die sieben Bausteine am Gerät so klingen wie gedacht.

Quelle: Messung 2026-10-22/fx-katalog-neu

### Notenwerttabellen der Delays

Im DSP-Strom liegt ab DSP `0x9470` eine Folge von Records zu 6 Byte (Zähler und Nenner als 16-Bit-Zahlen und eine Null, hergeleitet):

- Records 8 bis 71: **Notenwert** (`on_syncnote` im Short Delay, `on_l_syncnote` und `on_r_syncnote` im Mod Delay, Spanne 0 bis 63).
- Records 72 bis 135: **Zeitfaktor** (`on_time_ratio`, Spanne 0 bis 63). Die Verzögerung ist Notenwert mal Faktor.
- Die LFO-Tabelle (Records 136 bis 177) folgt bei `0x97A0` (`0x9470 + 136 * 6`).
- Ab Wert 14 wiederholen sich die Notenwerte in kürzeren Gruppen (14 bis 23: 1/64, 1/32, 1/16, 1/8, 1/6, 3/16, 1/4, 3/8, 1/2, 1; 24 bis 31:
  1/64, 1/32, 1/16, 1/8, 1/6, 3/16, 1/4, 1/2; und so weiter), die Faktoren ebenso (35 ist 1, 62 ist 3/2).
- Alle Delay-Presets beider Firmwares passen: Korg Delay 1/4, 3/16, 1/8, 1/16 und Roller 1/32 (Notenwert 20, 19, 17, 16, 15, Faktor 35);
  Hacktribe 1/12 Delay (4, 35), 9/32 Delay (7, 62), 3/32 Delay (60, 62); Korg High Pass Delay (Mod Delay, 17 und 19, Faktor 35).
- **Offen:** wie lang ein Delay höchstens sein darf, bevor der Puffer endet (die Insert-Presets reichen bis 9/32). Tape Echo (`s_note1`,
  `time_ratio`) passt mit seinem Werkspreset nicht auf diese Tabellen, der Katalog ändert dort keinen Notenwert.

Quelle: Messung 2026-10-22/fx-katalog-neu

### Slap Delay und Long Delay (Insert, `I_short_delay`, `0x18`)

Hergeleitet (Spannen in `data/map/fx-params.mjs`, Beleg `derived:vsb-table/0xC00FED74`):

| Parameter | Spanne | Bedeutung |
|---|---|---|
| `tempo_sync` | 0 bis 1 | 1: Zeit aus Notenwert mal Faktor, 0: `off_delay_time` mal `off_time_ratio` |
| `on_syncnote` | 0 bis 63 | Notenwert, 1 ist 1/32, 3 ist 1/16, 10 ist 3/8, 11 ist 1/2 |
| `on_time_ratio` | 0 bis 63 | Faktor, 35 ist 1 |
| `off_delay_time` | 0 bis 74 | Zeit ohne Sync, Einheit offen |
| `fb_depth`, `high_damp`, `low_damp` | 0 bis 127 | Wiederholungen und Filter in der Rückkopplung |

Eine eigene Typkennung für "Long" gibt es im Insert nicht, beide sind Presets des einen Bausteins.

| Name | Sync | Zeit | Feedback | Dämpfung hoch, tief | Wet |
|---|---|---|---|---|---|
| Slap Delay | an | 1/32 mal 1 | 35 | 60, 15 | 100 |
| Long Delay | an | 3/8 mal 1 | 70 | 50, 25 | 90 |

Regler 1 mischt das Echo dazu, beide Regler stellen das Feedback, das Feedback bleibt unter 90. **Offen:** Klang am Gerät, besonders ob 3/8 beim
Long Delay in den Puffer passt (die Insert-Werkspresets gehen nur bis 9/32 = 0,28, 3/8 ist 0,375, Obergrenze nicht gemessen; reicht der Puffer
nicht, ist Notenwert 9 = 1/3 der Ausweg). Die Einheit von `off_delay_time` und ob "1" ein Takt oder eine Viertel ist.

Quelle: Messung 2026-10-25/ifx-delays

### Pseudo-Reverb (Vorschlag im Presets-Bereich)

Ein Vorschlag, keine Preset-Datei (`data/suggestions.mjs`, Linter: [Linter](linter.md)). Werte auf `I_short_delay`: `tempo_sync` 0,
`off_delay_time` 19, `fb_depth` 64, `high_damp` 72, `low_damp` 8, `wet_level` 56. Sie liegen innerhalb dessen, was die Werkspresets des
Bausteins nutzen, das Feedback unter 90. **Nicht gehört.** Es gibt keinen Insert-Hall, nur Master-FX. Ein eigener Name ist nicht gesetzt.

Quelle: Idee 28

## Was nicht geht

- **Kein Falten, keine neue Verzerrer-Art.** Die Firmware hat im Insert zwei Verzerrer (Distortion, Acid Drive) und den Decimator, im
  Master Distortion, Decimator und die Röhrenvorstufe. Die Effekte oben sind verschiedene Einstellungen davon.
- **Keine Hüllkurve des Verstärkers im Effekt.** Attack und Decay des Verstärkers sind Werte des Parts, ein Effekt kommt nicht an sie
  heran. Ein Effekt kann nur im Takt formen (Bounce Gate), eine Modulation nur an der Note (Bounce Pluck).
- **Kein Kompressor als Modulation.** Eine Modulation bewegt Tonhöhe, Oszillator, Filter, Lautstärke, Pan und den Insert-Effekt,
  sie misst keinen Pegel.
- **Zwei Stufen nur mit gemessenen Bausteinen.** In Stufe 2 stehen hier nur EQ, Limiter, Acid Drive und Filter, die in der
  [Messreihe](messungen/2026-09-21-stage2-sweep.md) ohne Absturz liefen. Der Decimator läuft nur allein, der Kompressor SR1 nur in Stufe 1.

Die Namen sind höchstens 15 Zeichen lang, so viele zeigt die Firmware.
