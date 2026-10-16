# Linter und simuliertes Gerät

Bevor Daten ans Gerät gehen, prüfen der Linter und das simulierte Gerät, ob das
Gerät sie voraussichtlich annimmt. Wie beide im Ablauf sitzen, steht in
[architektur.md](architektur.md).

## Die Befehlszeile

```bash
node bin/e2.mjs ls      /pfad/SYSTEM.VSB
node bin/e2.mjs show    /pfad/SYSTEM.VSB mfx 12
node bin/e2.mjs profile /pfad/SYSTEM.VSB     # Wertebereiche der Werksdaten ermitteln
node bin/e2.mjs lint    /pfad/SYSTEM.VSB
node bin/e2.mjs selftest /pfad/SYSTEM.VSB    # das simulierte Gerät ansteuern, Ablehnungen zeigen
```

`profile` liest die von Korg mitgelieferten Presets und schreibt die daraus
ermittelten Wertebereiche nach `.e2/factory-profile.json`. Die Datei wird von Git
ignoriert, weil sie aus der eigenen Firmware abgeleitet ist. Der Linter verwendet sie,
wenn sie vorhanden ist, und weist andernfalls darauf hin. Die Firmware-Datei bleibt, wo
sie ist, nichts schreibt hinein.

## Schweregrade

| Stufe | Bedeutung |
|-------|-----------|
| `fatal` | Das Gerät gibt keinen Ton mehr aus oder hängt, ein Neustart ist nötig. |
| `silent` | Das Preset wird geladen, bleibt aber stumm. |
| `error` | Eine Steuerung verhält sich nicht wie vorgesehen. |
| `warn` | Technisch zulässig, liegt aber außerhalb der Werte aller bekannten Werks-Presets. |
| `note` | Kosmetischer Hinweis. |

## Was der Linter weiß

Die Regeln stehen in `src/rules.mjs`, das Wissen dahinter in `data/findings.mjs`, mit
Beleg. Alles ist am Gerät abgeglichen:

- Welche Einheiten in der zweiten Insert-Stufe laufen und **wie die anderen
  scheitern**. Neun Einheiten wurden in einem automatisierten Durchlauf zweimal
  gemessen: `0x03`, `0x04`, `0x05`, `0x06` und `0x07` funktionieren, `0x01` und `0x08`
  laden, geben aber kein Audio aus, `0x02` und `0x09` verursachen Abstürze. Manuelle
  Tests ergänzen `0x0a`, `0x10` und `0x16` sowie `0x18`, das die gesamte Audioausgabe bis
  zu einem Neustart abschaltet. Alle anderen Werte gelten als **ungetestet**, nicht
  automatisch als verboten.
- Der Decimator `0x09` funktioniert allein, stürzt aber mit einer nachgeschalteten
  zweiten Stufe ab.
- Ein Master-Preset braucht eine Einstellung, durch die der Effekt im ausgeschalteten
  Zustand umgangen wird. Sonst bleibt er stumm, solange das Touchpad nicht gedrückt wird.
- Ein Datensatz aus der falschen Tabelle sieht gültig aus, bleibt aber stumm. Beide
  Tabellen enthalten jeweils 524 Bytes.
- Ausgangspegel nahe der Obergrenze und Delay-Feedback über 90 sind durch Hörtests
  auffällig, obwohl die Bytewerte formal zulässig sind. Bei den Ausgangspegeln
  (`output_level`, `output_gain`) gibt es drei Stufen, alle als Warnung, weil das Gerät die
  Werte annimmt und der Türsteher sie nach Bestätigung durchlässt: Werte ab dem gehörten
  Fehlerfall (124 beim Verzerrer, 95 beim Pegelmodulator) und alles über 90 melden
  `output-too-loud`, die gehörten Fälle mit dem Hinweis darauf; zwischen 60, der Obergrenze
  der brauchbaren Pegel, und 90 meldet `output-above-usable`, dass dort nichts gehört wurde.
  Erreichen die Werks-Presets desselben Bausteins den Wert selbst (der Decimator steht ab
  Werk auf 127), schweigt der Linter, sobald ein Werksprofil da ist. Die Pegel eines
  Patterns zeigt und skaliert die Pegel-Ansicht im Bereich Presets ([Idee 31](ideen/31-gain-staging.md)).
- Manche Felder wählen Einträge aus einer Liste statt Werte aus einem Bereich. Erlaubte
  Werte werden aus Werks-Presets abgeleitet und nicht fest einprogrammiert.
- Short Delay (`0x18`) in Stufe 2 schaltet den Ton geräteweit ab (`stage2-fatal`, Befund
  `stage2.18`). Der Vorschlag "Pseudo Reverb" ([Idee 28](ideen/28-pseudo-reverb.md)) setzt
  nur Parameter eines Short-Delay-Datensatzes in Stufe 1 und lehnt Stufe 2 ab; die Regel
  war schon da und ein Test hält sie fest.
- Eine Master-Einheit innerhalb einer Insert-Kette lässt das Gerät hängen.
- Ein Master-Slot verwendet genau eine Einheit.
- Insert-Presets haben keine Y-Achse. Das Touchpad steuert den Master-Effekt, ein
  Insert-Preset wird mit dem einzelnen Regler gesteuert, dessen beide Hälften separat
  zugeordnet werden können.
- Eine Controller-Zuordnung speichert die Position eines Parameters in der Parameterliste
  seiner Einheit, nicht dessen Adresse. Ein Index hinter dem Listenende greift auf
  nachfolgende Daten zu.
- In der Ruhestellung muss der Effekt unhörbar sein. Ein Preset, das nur einen
  Klangparameter verändert, ist dauerhaft aktiv, die Steuerung verändert dann lediglich den
  Klang. Bei einem bipolaren Parameter wie `level_mod_int` liegt der neutrale Wert in der
  Mitte bei 63, nicht bei 0.
- Ein Pegelmodulator benötigt `lfo_reset` auf der Play-Taste. Sonst läuft er frei weiter
  und setzt nach Stop und Play an wechselnden Stellen ein.
- Werte außerhalb des von Korg für dieselbe Einheit verwendeten Bereichs sollten
  überprüft werden. Ein Ausgangspegel von 95, während Werks-Presets nur 32 bis 36
  verwenden, übersteuert bei jeder Einstellung.

Für Patterns gibt es bisher eine Regel (`src/pattern-rules.mjs`): ein Step mit "An" und
ohne "Trigger" klingt nicht, das ist eine Warnung.

Für Samples gibt es vier Regeln (`src/sample-rules.mjs`), alle Warnungen, weil Name und Tune je
einmal am Gerät geschrieben wurden und alles darüber hinaus ungetestet ist: ein leerer Name, ein
Name, der alle 16 Byte füllt (gemessen ist ein kürzerer, mit NUL aufgefüllt), ein Tune außerhalb von
-16 bis 0 (die Werte, die am Gerät gesehen wurden; die Skala ist nicht gemessen) und ein Platz, der
unbenutzt aussieht (PCM-Länge 0; ein leerer Name oder eine fehlende Samplerate ist dafür kein Zeichen, im
Emulator tragen unbenutzte Plätze `SampleNNN` und 48000 Hz). Ein Name mit Zeichen, die das Display nicht zeigt, und
ein Name über 16 Zeichen kommen gar nicht bis zum Linter: die Typen der Karte lehnen sie ab,
bevor der Plan entsteht.

Für Modulationsarten gibt es sechs Regeln (`src/modtable-rules.mjs`), alle Warnungen, weil alles im
Emulator gemessen ist, an Engine-Werten und Wörtern zum DSP, und nichts gehört wurde. Sie sprechen nur über
das, was sich gegenüber der Datei geändert hat: eine Kurve außerhalb der sieben gemessenen (7 lief wie 4, ab 8 liest
die Firmware hinter eine Tabelle), ein Ziel-Code 4 bis 7 (wirkt, am Klang offen), ein Slot mit Ziel ohne Wirkung
(Quelle aus oder Stärke 0), eine Stärke mit "von" unter 0 und "bis" über 0 (läuft immer von 0 bis 63), zwei Slots auf
demselben Ziel (sie addieren sich) und eine geänderte Kurve ohne Slot mit der Quelle LFO (sie wirkt nur dort).

## Eine Regel hinzufügen

Eine Regel kommt in `src/rules.mjs` mit einem Schweregrad und einer Meldung, die sagt, was
beobachtet wurde, nicht was verboten ist. Eine Regel verdient ihren Platz, indem sie etwas
gekostet hat: wurde sie noch nicht am Gerät gesehen, ist sie eine `warn`, die sagt, dass
sie ungetestet ist, kein `error`. Die Beobachtung gehört mit ihrem Beleg nach
`data/findings.mjs`, damit Wissen und Prüfung zusammenbleiben.

## Das simulierte Gerät

`SimDevice` beantwortet erweiterte SysEx-Befehle anhand eines echten Firmwareabbilds. Es
verwendet dieselben Adressen wie die Hardware.

```js
import { VsbImage, SimDevice } from "kuhlers-gelumpe";

const device = new SimDevice({ image: new VsbImage(bytes), channel: 9 });
device.handle(sysexMessage);   // Antwort oder null bei Ablehnung
device.faults;                 // Gründe für Ablehnungen
```

Der voreingestellte Kanal ist absichtlich nicht 0. Hacktribes eigene Skripte gehen von
Kanal 0 aus. Ist am Gerät ein anderer Kanal eingestellt, erscheint jeder Befehl fälschlich
als nicht unterstützt, weil die Antwort nicht zugeordnet wird.

Im Browser kann die Simulation MIDI-Ports bereitstellen. So lässt sich der Editor ohne
angeschlossene Hardware vollständig testen:

```js
import { installWebMidiStub } from "kuhlers-gelumpe/webmidi";
const sim = installWebMidiStub({ image, channel: 9 });
// die Seite ruft navigator.requestMIDIAccess auf und findet eine Electribe
sim.faults;   // alle abgelehnten Befehle und ihre Gründe
```

## Grenzen der Prüfung

Der Schutzmechanismus prüft bekannte Speicherbereiche, das Nachrichtenformat und
dokumentierte Fehlerfälle. `SimDevice` führt keine ARM- oder DSP-Instruktionen aus und
kann daher nicht garantieren, dass beliebige Speicherschreibzugriffe oder hochgeladene
Programme sicher sind. Die Simulation erzeugt kein Audio. Ob ein Preset auf echter
Hardware klingt oder überhaupt einen Ton erzeugt, lässt sich nur durch Hören feststellen.
Die Firmware selbst läuft im [Emulator](emulator.md), der ebenfalls keinen Ton erzeugt.

## Offene Punkte

Stand der Liste: September 2026, nicht erneut geprüft.

- Drei Werks-Presets von Korg werden vom Linter beanstandet. Das deutet eher auf Lücken
  im Verständnis als auf Fehler von Korg hin: **IFX 7 Sustainer** weist Parameter 5 einer
  Einheit zu, für die die Tabelle nur vier Parameter kennt. **IFX 15 High Pass Filter**
  verwendet die bisher nicht beobachtete Kette `0x05`. **MFX 12 Grain Shifter** enthält
  eine Zuordnung zu einer Insert-Stufe.
- Die Stufe-2-Liste ist nicht vollständig durchprobiert, und Stufe 1 mit einem Filter in
  Stufe 2 ebenfalls nicht. Beim Decimator wären als Nächstes `0x09 -> 0x10` und
  `0x09 -> 0x06` zu testen. Ungeklärt ist, warum drei Kompressoren drei verschiedene
  Ergebnisse liefern.
- `mfx_device 0x30` sowie `ifx_device 0x0B` bis `0x0E` und `0x17` fehlen in der Aufzählung.
  Eine Lücke kann heißen "da ist nichts" oder "da ist etwas, das niemand identifiziert hat,
  weil kein Preset es benutzt". Über RAM ist das gefahrlos testbar.
- Sieben MFX-Bausteine haben kein Werks-Preset (`mkp2_comp`, `limiter`, `eq_4_band`,
  `tremolo`, `dry_plate_reverb`, dazu `wah` und `level_mod`, die Hacktribe freigeräumt hat).
  Dafür gibt es keinen Spender, die Parameter müssen von Hand gesetzt werden.
- Slicer und Repeater laufen nach einer Parameteränderung aus dem Takt und fangen sich erst
  bei Stop und Play. Ungetestet sind die unbelegten `lfo_reset`-Werte 2 und 3.
- Die Skala der Sync-Notenwerte ist je Baustein unterschiedlich und undokumentiert. Eine
  Tabelle "Wert zu Notenwert" pro Baustein fehlt.
- Die Felder der Modulationstabelle ab `+0x29` sind nicht zugeordnet.
- Ob das SQEZ-Format auch beim Schreiben verwendet wird, ob sich also eine eigene Werksbank
  zurückschreiben ließe, ist offen.

Das Muster hinter fast allen Fehlern in diesem Projekt war dasselbe: eine plausible Annahme,
die niemand nachgemessen hat. Wer etwas herausfindet, baut sich vorher eine Kontrolle ein,
deren Ausgang er kennt. Bestätigte Funde ergänzen die [Gerätekarte](geraetekarte.md).
