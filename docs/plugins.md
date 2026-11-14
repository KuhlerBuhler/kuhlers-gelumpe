# Plugins für die Electribe

Deutsche Version | [English version](plugins.en.md) | [Français](plugins.fr.md)

Stand 2026-11-09.

Ein Plugin gibt der Electribe eine neue Funktion, etwa ein Lauflicht, ein Spiel auf
dem Display oder eine eigene Menüseite. Man lädt es über die SD-Karte aufs Gerät,
wie ein Plugin in einem Musikprogramm. Wer will, schreibt eigene Plugins: der
Plugin-Code ist eine Teilmenge von JavaScript.

Der Editor übersetzt ein Plugin in einen Block aus Bytecode, den eine kleine VM in
der Firmware ausführt. Ein Fehler schaltet das Plugin ab und zeigt eine Meldung im
Menü BLECH, die Electribe läuft weiter.

Alle Plugins werden beim Start geladen und laufen sofort: ein Plugin, das nur LEDs
setzt oder Tasten umbelegt, braucht keinen Menüschritt. Das **Display** gehört dem
Gerät. Ein Plugin mit eigenem Bildschirm ist eine **App**: sie steht im Menü BLECH
unter GAMES oder TOOLS, erst ENTER öffnet sie, und EXIT schließt sie immer. Wer
unbedingt direkt aufs Display will, nimmt es mit `korg.display.take()` und gibt es
mit EXIT zurück. Das Laden eines Plugins zeichnet nie etwas (Abschnitt "Apps und das
Display").

Die Seite hat fünf Teile: die Sprachreferenz (Aufbau, Apps und Display, Sprache,
Ereignisse, Funktionen, Grenzen), die Karte mit dem Dateiformat, das Menü BLECH am Gerät, die
Seite Plugins im Editor und den Abschnitt Stand. Was in der Sprachreferenz steht,
gilt für die Sprache und ihre Prüfung im Browser und im Emulator. Am Gerät laufen das Menü BLECH
und die Plugins der Karte; was dort im Einzelnen geprüft ist, steht unter Stand.

## Sprachreferenz

### Aufbau

Die Anweisungen ganz oben sind der Rumpf des Plugins. Er läuft einmal beim
Start: Variablen anlegen, Werte setzen, Handler anmelden. Danach laufen nur
noch die Handler, jeweils wenn ihr Ereignis eintritt.

```js
korg.app("Zaehler", "TOOLS");
let count = 0;

function show() {
  korg.display.clear();
  korg.display.number(count, 0, 16);
}

korg.onEvent("open", () => show());
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) { count += 1; show(); }
});
```

`korg.onEvent("Ereignis", Handler)` steht nur ganz oben, ein Handler je
Ereignis und Plugin. Der Handler ist eine Pfeilfunktion oder der Name einer
Funktion. Er darf weniger Werte nehmen, als das Ereignis liefert. Die Handler
werden aktiv, wenn der Rumpf ohne Fehler zu Ende gelaufen ist.

### Apps und das Display

Das Display der Electribe gehört der Firmware. Ein Plugin zeichnet nur dann hinein,
wenn es das Display besitzt, und das kann auf zwei Wegen passieren. Beide enden mit
EXIT: die Firmware wertet EXIT im Eingangsfilter aus, bevor ein Plugin die Taste
sieht, ein Plugin kann EXIT nicht abfangen und nicht verschlucken. Ein Plugin, das
kein Display besitzt und trotzdem zeichnet, wird übergangen: die Aufrufe tun nichts
und melden nichts. Das Laden und Importieren eines Plugins besetzt das Display nie.

**Weg 1, die App im Menü (der Normalfall).** Das Plugin meldet sich ganz oben im Code
mit `korg.app("Name", "Gruppe")` an. Der Name hat 1 bis 15 Zeichen (ASCII), die Gruppe
ist `"GAMES"` oder `"TOOLS"`, die Anmeldung steht einmal und nicht in einer Funktion.
Das Plugin läuft vom Start an, auch die App: ihre Handler für Tasten, Pads, Takt und
alles andere laufen immer, nur `frame` kommt erst, wenn sie offen ist. Im Menü BLECH
steht die App unter GAMES oder TOOLS. ENTER (die Taste MENU) öffnet sie: das Display
wird gelöscht, die Firmware zeigt ihren Hauptbildschirm, die App bekommt `open` und
von da an `frame` und das Display. Solange sie offen ist, gehören ihr die Tasten:
die Firmware sieht sie nicht (Encoder, Regler, Pads und Touchpad bleiben bei der
Firmware, das Spielen geht weiter). Eine Ausnahme bilden **PLAY, STOP und REC**: sie
erreichen die Firmware auch bei offener App (der Sequencer startet und hält an), und
die App bekommt `buttonPress` und `buttonRelease` für sie ebenfalls. Alle anderen
Tasten, auch die Part Tasten, ändern an der Firmware nichts. EXIT schließt sie, sie bekommt `close`, das
Display ist wieder das der Firmware. Verlässt die Firmware den Hauptbildschirm aus
anderem Grund, schließt die App ebenso.

```js
// Snake als App: öffnet im Menü unter GAMES, fängt bei jedem Öffnen neu an.
korg.app("Snake", "GAMES");
// ... Spielzustand und Funktionen wie im Beispiel-Plugin Snake ...
korg.onEvent("open", () => { reset(); frames = 0; draw(); });
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PART_LEFT) dir = (dir + 3) % 4;
  if (key == korg.key.PART_RIGHT) dir = (dir + 1) % 4;
});
korg.onEvent("frame", () => { frames += 1; if (frames >= 3) { frames = 0; step(); } draw(); });
```

**Weg 2, das Display nehmen (sparsam benutzen).** Ein Plugin, das keine App ist, kann in
einem Ereignis `korg.display.take()` rufen, solange die Firmware ihren Hauptbildschirm
zeigt und das Display niemand besitzt. Die Funktion gibt 1 zurück, wenn es klappt,
sonst 0. Danach zeichnet das Plugin, bis es `korg.display.release()` ruft oder der
Nutzer EXIT drückt (das Plugin bekommt dann `close`). Eine App nimmt das Display nicht,
sie wird im Menü geöffnet. Nicht im Rumpf: dort gibt es kein Display.
Eine Taste, die beim `korg.display.take()` gehalten ist, bleibt bei der Firmware: ihr
Loslassen kommt dort an, während das Plugin das Display besitzt, SHIFT oder PART MUTE
bleiben also nicht hängen (gemessen im Emulator auf Hacktribe, rot und blau,
`take_lets_key_releases_reach_the_firmware`). Anders als EXIT setzt
`korg.display.release()` `korg.passKeys` und `korg.padHold` nicht auf die Vorgaben zurück.

```js
// Ein Hinweis auf dem Display, solange PLAY gehalten wird.
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PLAY && korg.display.take()) korg.display.text("PLAY aktiv", 0, 0);
});
korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.PLAY) korg.display.release();
});
```

**Rand.** Text und Bedienhinweise halten Abstand zum Displayrand, wie die Menüs der Firmware: links und rechts 4 Pixel,
oben und unten 2 Pixel (eine Zeile Text oben bei `y = 2`, unten bei `y = 55`, rechtsbündig endet sie bei `x = 123`).
Ein Spielfeld oder Bild darf bis an den Rand gehen. Die Plugins im Katalog halten sich daran.

Nimm Weg 2 nur, wenn ein Menüeintrag nicht passt: das Display ist dann belegt, bis
jemand EXIT drückt, und die Tasten gehören dem Plugin, solange es das Display hat.
Ein Plugin, das nur LEDs oder Tasten braucht, nimmt das Display nie.

### Sprache

- **Werte:** ganze 32-Bit-Zahlen (`-2147483648` bis `2147483647`, Hex bis
  `0xFFFFFFFF`) und kurzer Text. `true` ist 1, `false` ist 0.
- **Text:** nur ein Literal in Anführungszeichen (ASCII und ä, ö, ü, höchstens 31 Zeichen)
  oder eine Variable, die einen hält. Vergleichen mit `==` und `!=`, an
  `korg.*` übergeben, mehr nicht: kein Verbinden, kein Zerlegen. Zahlen zeigt
  `korg.display.number`.
- **Variablen:** `let` und `const`. Eine `const` mit festem Wert ist eine
  Konstante und braucht keinen Platz. Jede Variable hat einen festen Platz
  (4 Byte) im Variablenbereich des Plugins. Der Bereich ist so groß, wie das
  Plugin Variablen und Felder anlegt, ein Plugin ohne Felder braucht kaum
  Platz. Das Blockformat erlaubt bis zu 65536 Plätze pro Plugin. Auf dem
  Gerät teilen sich Blöcke, Variablen und Plugin-Einträge 128 KiB, siehe „Grenzen“.
- **Felder:** `const a = new Array(16);` oder `const a = [1, 2, 3];`, nur ganz
  oben, fest 1 bis 65535 Plätze, Zahlen. `a[i]`, `a[i] = x`, `a[i] += x`,
  `a.length`. Ein Index außerhalb des Felds beendet das Plugin mit einem Fehler.
  Hat ein Feld-Literal nur Werte von 0 bis 255 (etwa ein Bild für
  `korg.display.bitmap`), stehen sie als Bytes im Block und kosten keinen Code,
  sonst schreibt der Code jeden Wert außer 0 einzeln ins Feld.
- **Rechnen:** `+ - * / %`, `& | ^ << >> ~`, Vergleiche `== != === !== < <= > >=`,
  `&& || !`, `? :`. Alles rechnet mit 32 Bit und läuft über. `/` teilt ganzzahlig
  und schneidet gegen null ab (anders als in JavaScript), `%` hat das Vorzeichen
  des Dividenden, die Schiebezahl zählt mit ihren unteren 5 Bit, `>>` erhält
  das Vorzeichen. `&&` und `||` liefern wie in JavaScript einen der beiden Werte.
- **Anweisungen:** Zuweisung (`= += -= *= /= %= &= |= ^= <<= >>=`), `++` und
  `--` als eigene Anweisung, `if` / `else`, `while`, `for`, `break`,
  `continue`, `return`, Blöcke. Jede Anweisung endet mit `;`.
- **Funktionen:** `function name(a, b) { … }` ganz oben, mit Zahlen als
  Argumenten und Ergebnis (`return;` oder das Ende gibt 0). Eine Funktion sieht
  die Variablen ganz oben und ihre eigenen, sonst nichts: es gibt keine
  Closures. Eine Funktion darf sich nicht selbst aufrufen, auch nicht über
  andere (Rekursion), weil alle Variablen feste Plätze haben.
- **Nicht dabei:** Kommazahlen, eigene Objekte (die Electribe selbst gibt es als
  Objekte, siehe „Die Electribe als Objekte“), `var`, `switch`, `do`, Ausnahmen,
  Vorlagentexte, `null`, Zuweisung innerhalb eines Ausdrucks.

Ein Fehler beim Übersetzen nennt Zeile und Spalte und sagt auf Deutsch, was
zu tun ist.

### Ereignisse

| Ereignis | Werte | Wann |
|---|---|---|
| `ready` | | einmal, im ersten Rahmen nach dem Start |
| `frame` | | 25 Mal je Sekunde; eine App bekommt es nur, solange sie offen ist |
| `buttonPress`, `buttonRelease` | `key` | Taste gedrückt, losgelassen; `key` vergleicht man mit einem Namen wie `korg.key.TAP`, siehe „Namen für Tasten und LEDs“ |
| `knob` | `index`, `value` | Regler bewegt (Rohwert 0 bis 255) |
| `encoder` | `index`, `delta` | Drehgeber gedreht |
| `pad` | `index`, `down`, `velocity` | Pad gedrückt oder losgelassen |
| `touch` | `x`, `y`, `first` | Touchpad berührt oder der Finger darauf bewegt. `x` und `y` sind die Werte der Panel-Nachricht (0 bis 1023, `y` nach oben, am Gerät nicht geprüft). `first` ist 1 bei der ersten Stelle einer Berührung, also dort, wo der Finger aufsetzt, sonst 0. `buttonPress` mit `korg.key.TOUCHPAD` hat keine Lage; sie kommt mit dem `touch` danach, und der trägt `first`. Ein Handler, der nur `x` und `y` nimmt, bleibt Version 1; wer `first` nimmt, braucht API Version 6 |
| `step` | `step` | Sequencer-Schritt (16tel) |
| `beat` | | Viertel |
| `play`, `stop`, `rec` | | Transport |
| `patternChange` | `index` | Pattern gewechselt |
| `partChange` | `part` | Part gewechselt |
| `mute` | `part`, `muted` | Part stumm oder nicht |
| `tempo` | `tenthsBpm` | Tempo geändert |
| `touchpadMode` | `mode` | Touchpad-Modus geändert, der neue Wert von `korg.touchpad.mode` (0 bis 4), ob eine Taste oder `korg.touchpad.mode` ihn geändert hat; ab API Version 27 |
| `padMode` | `mode` | Pad-Modus geändert, der neue Wert von `korg.pads.mode`; ab API Version 29 |
| `screen` | `number` | ein anderer Bildschirm der Firmware ist offen, der neue Wert von `korg.screen`; ab API Version 29 |
| `write` | `pattern` | ein Pattern wird in die Bank geschrieben (WRITE, auch der Shortcut EXIT + WRITE), `pattern` sein Platz 0 bis 249, bevor die Firmware schreibt; ab API Version 29 |
| `midiIn` | `status`, `data1`, `data2` | die Firmware hat über MIDI (DIN oder USB) eine Kanalnachricht empfangen, Status 128 bis 239 (Typ und Kanal), die Datenbytes 0 bis 127; auf jedem Kanal und vor dem MIDI RECEIVE FILTER, die Firmware bekommt sie danach, außer ein Plugin hält ihren Typ mit `korg.midi.hold`. Clock, SysEx und Echtzeitnachrichten kommen nicht; ab API Version 30 |
| `save` | | WRITE in Global, Ausschalten |
| `menu` | `id`, `value` | am Hauptrad wurde eine Seite gedreht, die das Plugin mit `korg.menu.add` angelegt hat |
| `open`, `close` | | nur für Apps und für ein Plugin, das das Display nahm: `open`, wenn der Nutzer die App im Menü öffnet; `close`, wenn EXIT sie schließt (oder die Firmware den Hauptbildschirm verlässt). Sie gehen nur an dieses Plugin und kommen nie von außen |

Die Sequencer-Ereignisse (`step`, `beat`, `play`, `stop`, `rec`, `patternChange`,
`partChange`, `mute`, `tempo`) entstehen auf dem Gerät nicht in der SeqTask: der
Rahmenhaken vergleicht einmal je Rahmen die Zustandswörter der Firmware (Transport,
Tempo, Pattern, Part, Schritt von Part 0, Mutes) mit denen des vorigen Rahmens und
legt für jede Änderung ein Ereignis in den Ring. Das Raster ist damit 40 ms: bei
höchstem Tempo (300 BPM, 20 Schritte je Sekunde) kommt noch jeder Schritt, was
zwischen zwei Rahmen mehrfach wechselt, sieht ein Plugin als eine Änderung. Das
erste Lesen nach dem Scharfschalten gilt als Ausgangszustand und löst nichts aus.
`step` trägt den Schrittzähler von Part 0 (0 bis 63), `beat` kommt bei jedem vierten
Schritt (mit BEAT 8 also jede halbe Note des echten Tempos), `play` bei Transport 1, `stop` bei 0 oder 2, `rec` beim Übergang in 3 oder 4,
`mute` je geänderten Part mit dem neuen Zustand. Ein Plugin sieht auch, was es
selbst ausgelöst hat (`korg.tempo` löst `tempo` aus). Ein Patternwechsel setzt das
Tempo des neuen Patterns, `tempo` folgt ihm dann. `save` kommt aus einem Haken am
Eingang der Einstellungs-Schreibfunktion `0xC004C1B4` (CommandTask), die nur den
Ring beschreibt. Beim Ausschalten läuft die Laufzeit noch rund eine Sekunde, doch
`korg.store` schreibt dann nicht mehr, weil das Fenster "Power Off" offen ist.

Die Ereignisse außer `ready` und `frame` kommen über einen Ring mit 64
Plätzen. Ist er voll, geht das neue Ereignis verloren und wird gezählt. Ein
Regler, der sofort wieder gedreht wird, behält nur seinen letzten Wert.
Die Handler eines Rahmens laufen zusammen höchstens 5 ms; wer darüber
kommt, wird abgeschaltet. Ein einzelner Handler über 0,5 ms ist eine Warnung.
Der Status hält die höchsten Kosten und den höchsten Zeitverbrauch getrennt
für jeden Handler. In der JS Referenzlaufzeit nennt `maxMs` diese Zeiten in
Millisekunden; der ARM Eintrag hält Timer3 Ticks je Ereignis.

Die Laufzeit verwendet einen gemeinsamen Rahmenanfang für alle Handler.
Die VM prüft die Zeit vor dem ersten Befehl, bei erfolgreichem Ende und alle
256 Operationen. Damit fallen auch viele kurze Handler unter das gemeinsame
Budget. Genau 5 ms sind erlaubt; erst darüber entsteht `TIME`. Ein solcher
Fehler schaltet nur das gerade laufende Plugin ab. Die übrigen Plugins des
aktuellen Ereignisses, danach die weiteren Eingaben und der Rahmenhandler
laufen im nächsten Rahmen weiter, ohne bereits gelieferte Ereignisse zu
wiederholen. Noch nicht begonnene Handler werden bei abgelaufener Zeit
verschoben und bleiben eingeschaltet.

Ein Zyklus liefert zunächst einmal `ready` je Plugin, erfasst danach die
wartenden Eingaben und liefert zuletzt `frame`. Später eintreffende Eingaben
bleiben bis zum nächsten Zyklus im Ring. Neue Plugins erhalten `ready`, wenn
die verbliebene Folge des vorherigen Zyklus abgeschlossen ist. Die JS
Referenzlaufzeit kann vor dem ersten Hauptbildschirm mit
`frame({ ready: false })` warten. Nach dem ersten freigegebenen Rahmen bleibt
diese Freigabe bestehen; `frame()` gibt sie standardmäßig frei. Das ist die
Abbildung des Hauptbildschirmmerkers der ARM Laufzeit.

Solange das Menü BLECH offen ist, gehen Pads, Tasten und Encoder direkt an die
Firmware, und kein Plugin bekommt ein Ereignis (nur die Seite von Blechy bekommt
das Touchpad und ihre Taste). In allen Menüs der Firmware (Pattern, Global, Part
Edit, Step Edit und die übrigen) bekommen Plugins die Eingaben wie auf dem
Hauptbildschirm.

### Was ein Plugin erreicht (API 35)

Die Tabelle zeigt für jedes Bedienelement und jeden Zustand der Electribe, womit ein Plugin ihn liest, setzt und von ihm
erfährt. „nein“ heißt: das geht heute nicht; Tasten, die ein Plugin nicht als Wert setzen kann, drückt es mit
`korg.keyDown` wie ein Finger (API 25). Die Tabelle wird aus `data/script/coverage.mjs` erzeugt
(`node tools/plugin-coverage.mjs`), ein Test schlägt fehl, wenn ein Aufruf, ein Ereignis oder ein Blatt des Objektbaums fehlt.

<!-- coverage -->
| Bereich | Lesen | Setzen | Event |
|---|---|---|---|
| **Bedienfeld** | | | |
| Tasten (REC bis IFX ON) | nein | `korg.pressKey`, `korg.keyDown`, `korg.keyUp`, `korg.remapKey`, `korg.keyHold`, `korg.keyMask`, `korg.passKeys` | `buttonPress`, `buttonRelease` |
| Regler | `korg.read.knob` | `korg.knob`, `korg.knobHold` | `knob` |
| Encoder | nein | `korg.encoder` | `encoder` |
| Pads | nein | `korg.padDown`, `korg.padUp`, `korg.padHold` | `pad` |
| Touchpad | nein | `korg.touch`, `korg.touchLockX`, `korg.touchLockY` | `touch` |
| Touchpad-Modus (Gate Arp, Touch Scale, Master FX, MFX 2) | `korg.touchpad.mode` | `korg.touchpad.mode` | `touchpadMode` |
| Pad-Modus (TRIGGER, SEQUENCER, KEYBOARD und die anderen) | `korg.pads.mode` | nein | `padMode` |
| Takt auf den Pads (1 bis 4) | `korg.pads.bar` | nein | nein |
| LEDs | `korg.read.led` | `korg.led`, `korg.ledHold` | nein |
| Display (eigenes Bild, Fenster der Firmware) | `korg.read.popups` | `korg.display.*`, `korg.file.frame` | `open`, `close` |
| Displaylicht | nein | `korg.backlight` | nein |
| Welcher Bildschirm oder welches Menü offen ist | `korg.screen` | nein | `screen` |
| **Sequencer, Pattern, Part, Step** | | | |
| Transport (PLAY, STOP, REC) | `korg.read.transport` | `korg.play`, `korg.stop` | `play`, `stop`, `rec` |
| Tempo | `korg.read.tempo` | `korg.tempo` | `tempo` |
| Gewähltes, angezeigtes und nächstes Pattern | `korg.read.pattern`, `korg.read.viewedPattern`, `korg.read.nextPattern` | `korg.pattern` | `patternChange` |
| Gewählter Part, Mute | `korg.read.part`, `korg.read.mute` | `korg.part`, `korg.mute` | `partChange`, `mute` |
| Step-Zähler | `korg.read.step` | nein | `step`, `beat` |
| Werte des Patterns (Tempo bis MFX-Pad, Chain, Sync Group) | `korg.read.patternValue`, `korg.read.chainMode` | `korg.seq.setPatternValue` | nein |
| Werte eines Parts (Sample bis Groove, mit Motion Seq an oder aus) | `korg.read.patternValue` | `korg.seq.setPartValue`, `korg.part.copy` | nein |
| Steps (an, Gate, Velocity, Noten) | `korg.seq.getOn`, `korg.seq.getGate`, `korg.seq.getNote`, `korg.seq.getVelocity`, `korg.read.patternBytes` | `korg.seq.setStep`, `korg.seq.setGate`, `korg.seq.clearPart`, `korg.seq.writeSteps` | nein |
| Pattern speichern (WRITE) | nein | `korg.pattern.write` | `write` |
| Name des Patterns | `korg.read.patternName` | nein | nein |
| Motion-Spuren und ihre Wiedergabe | `korg.motion.lane`, `korg.motion.destination`, `korg.motion.value`, `korg.motion.output` | `korg.motion.setValue`, `korg.motion.clearLane`, `korg.motion.clearPart`, `korg.motion.clearMfx` | nein |
| Motion des gewählten Parts an oder aus (TAP mit dem Patch tap-motion) | `korg.motion.enabled` | `korg.motion.enabled` | nein |
| **Effekte** | | | |
| MFX: Typ, Pad, HOLD, MFX SEND | `korg.read.patternValue` | `korg.seq.setPatternValue`, `korg.seq.setPartValue` | nein |
| MFX-2-Typ des Patterns | `korg.read.patternValue` | `korg.seq.setPatternValue` | nein |
| IFX: an, Typ, Edit | `korg.read.patternValue` | `korg.seq.setPartValue` | nein |
| **Klang, MIDI, Samples** | | | |
| Ausgangspegel wie die Pegelanzeige | `korg.audio.level` | nein | nein |
| Spektrum, Wellenform | `korg.audio.capture`, `korg.audio.spectrum`, `korg.audio.wave` | nein | nein |
| Eigene MIDI-Nachrichten senden, MIDI empfangen | nein | `korg.midi.cc`, `korg.midi.noteOn`, `korg.midi.noteOff`, `korg.midi.program`, `korg.midi.hold` | `midiIn` |
| Name und Daten eines Samples | `korg.read.sampleName`, `korg.read.sampleInfo` | nein | nein |
| **System und Einstellungen** | | | |
| Gerät, Version, Anzahl Effekte und Sample-Slots | `korg.system.device`, `korg.system.version`, `korg.system.limits.*` | nein | nein |
| Reparaturen, Test-Modus, Auto Power Off | `korg.system.repairs`, `korg.system.testMode` | `korg.system.keepAwake` | nein |
| GLOBAL PARAMETERS | `korg.global.*` | `korg.global.*` | nein |
| Menü BLECH (CUSTOMIZATION, FEATURES) | `korg.menu.blech.*` | `korg.menu.blech.*` | nein |
| Netzteil oder Batterie, Ladestand | `korg.system.power`, `korg.system.battery` | nein | nein |
| **Dienste für Plugins** | | | |
| Eigene Einträge im Menü BLECH | nein | `korg.menu.add` | `menu` |
| Apps | nein | `korg.app` | `open`, `close` |
| Gespeicherte Werte | `korg.store.get` | `korg.store.set`, `korg.store.save` | `save` |
| Eigene Datei auf der Karte | `korg.file.read` | `korg.file.write` | nein |
| Zeit und Timer | `korg.millis` | `korg.after`, `korg.every`, `korg.afterSteps`, `korg.cancel` | `ready`, `frame` |
<!-- /coverage -->

### Die Electribe als Objekte

Was die Electribe gerade tut, liest und setzt ein Plugin wie eine Variable: `korg.tempo` ist das Tempo,
`korg.tempo = 1280;` stellt es um, `korg.parts[3].muted = 1;` schaltet Part 4 stumm. Das sind keine
Objekte der Sprache, die man in einer Variablen halten könnte. Der Übersetzer macht aus jedem Lesen und
Setzen den Aufruf, der in der Tabelle unten daneben steht, und der Block ist derselbe. Darum läuft ein
so geschriebenes Plugin auf jedem Gerät, auf dem diese Aufrufe laufen, auch mit BLECHTRIBE 1.2. Es gelten
dieselben Grenzen und Ereignisse wie für den Aufruf: `korg.tempo = …` geht wie `korg.tempo(…)` nicht im
Rumpf.

| Eigenschaft | Lesen | Setzen | entspricht |
|---|---|---|---|
| `korg.tempo` | Tempo in Zehntel BPM, 1280 ist 128,0 | 100 bis 3000 | `korg.read.tempo()`, `korg.tempo(x)` |
| `korg.transport` | 0 Stop, 1 Play, 2 Pause, 3 REC bereit, 4 Aufnahme | nein, dafür `korg.play()` und `korg.stop()` | `korg.read.transport()` |
| `korg.selectedPattern` | gewähltes Pattern, 0 bis 249 | wählt ein anderes | `korg.read.pattern()`, `korg.pattern(x)` |
| `korg.viewedPattern` | Pattern, das das Display zeigt, 0 bis 249 (ab API Version 18). Das Rad durchblättert beim Spielen ein anderes, das Display zeigt dann dieses, das spielende läuft weiter | nein | `korg.read.viewedPattern()` |
| `korg.nextPattern` | nächstes Pattern, das der Patternwechsel bestätigt hat und das am Ende der Sequenz startet, 0 bis 249; -1, wenn keins wartet (ab API Version 18) | nein | `korg.read.nextPattern()` |
| `korg.selectedPart` | gewählter Part, 0 bis 15, 16 für alle | 0 bis 15 | `korg.read.part()`, `korg.part(x)` |
| `korg.parts[i].step` | Schrittzähler des Parts, 0 bis 63 | nein | `korg.read.step(i)` |
| `korg.parts[i].muted` | 1, wenn der Part stumm ist | 1 stumm, 0 an | `korg.read.mute(i)`, `korg.mute(i, x)` |
| `korg.knobs.LEVEL`, `korg.knobs[i]` | letzter Wert des Reglers, bis er bewegt wurde 0 | nein | `korg.read.knob(i)` |
| `korg.store[i]` | gespeicherter Wert von Platz 0 bis 15, sonst 0 | ja, auf die Karte mit `korg.store.save()` | `korg.store.get(i, 0)`, `korg.store.set(i, x)` |
| `korg.led.TAP`, `korg.leds[i]` | nein | Helligkeit 0 bis 255 | `korg.led(i, x)` |
| `korg.chainMode` | 1, wenn CHAIN MODE im Global-Menü an ist (nur dann kettet die Firmware). **Veraltet seit API 35**, nimm `korg.global.chainMode` | nein | `korg.read.chainMode()` |
| `korg.pattern.current.tempo` (auch `korg.current.tempo`, **veraltet seit API 35**) und die anderen Werte unten | das Pattern, das gerade läuft, mit ungespeicherten Änderungen | ja, über die Funktion der Firmware aus dem Pattern-Menü (`korg.pattern.current` ab API Version 21, `korg.current` ab 15) | `korg.read.patternValue(-1, -1, wert)`, `korg.seq.setPatternValue(wert, x)` |
| `korg.patterns[i].tempo` und die anderen Werte unten | Pattern `i` (0 bis 249), so wie es gespeichert ist | nein | `korg.read.patternValue(i, -1, wert)` |
| `korg.parts[i].cutoff` und die anderen Part-Werte unten | Part `i` (0 bis 15) im Pattern, das gerade läuft | ja (ab API Version 14; `voiceAssign` und `mfxSend` ab 21; `sample`, `ifxOn`, `ifxType` und `ampEg` ab 23; `lastStep` bis `grooveDepth` ab 24) | `korg.read.patternValue(-1, i, wert)`, `korg.seq.setPartValue(i, wert, x)` |

**Werte eines Patterns** (`korg.pattern.current.…`, `korg.current.…`, `korg.patterns[i].…`): `tempo` (Zehntel BPM), `swing` (-48 bis 48), `length`
(Takte, 1 bis 4), `beat` (0 16tel, 1 32tel, 2 8tel-Triolen, 3 16tel-Triolen, 4 8tel mit BLECHTRIBE), `key` (0 C bis 11 H), `scale`, `chordSet`,
`level`, `mfxType`, `chainTo` (das nächste Pattern, 0 bis 249, -1 ohne Kette), `chainRepeat` (mindestens 1), `gateArp` (die Seite GATE ARP, 0 aus), `syncGroup` (0 aus, 1 bis 999; ab API Version 21), ab API Version 24
`alternate1314` und `alternate1516` (1 an), `mfxHold` (1 an), `mfxPadX` und `mfxPadY` (das Touchpad im MFX-Modus, 0 bis 127), ab API Version 27 `mfx2Type` (der MFX-2-Typ des Patterns aus dem Patch
mfx-switch, 0 bis 99 wie die Anzeige minus 1, 6, wenn das Pattern keinen eigenen hat, -1 ohne den Patch). Setzen geht nur, wenn MFX 2 im
BLECH-Menü an ist, sonst bleibt alles, wie es war; ist MFX 2 gerade aktiv, geht der Wert über dieselbe Funktion wie die Seite MFX TYPE,
sonst in die Tabelle des Patches. Gespeichert wird er mit WRITE.
**Werte eines Parts** (`korg.parts[i].…`): `sample` (Slot), `filterType`, `cutoff`, `resonance`, `egInt` (-63 bis 63),
`modType`, `modSpeed`, `modDepth`, `attack`, `decay`, `level`, `pan` (-63 links bis 63 rechts), `ifxOn`, `ifxType`,
`ifxEdit`, `pitch` (-63 bis 63), `glide`, `voiceAssign`, `oscEdit`, `mfxSend`, `ampEg` (1 an; ab API Version 23), ab API Version 24 `lastStep` (1 bis 15, 0 heißt 16), `motionMode` (0 aus,
1 smooth, 2 trigger hold), `padVelocity` (1 an), `scaleMode` (1 an), `priority` (1 hoch), `grooveType`, `grooveDepth`. Die Werte sind in den Einheiten des Geräts
(meist 0 bis 127). Die Werte des laufenden Patterns und seiner Parts lassen sich auch setzen, siehe
`korg.seq.setPatternValue` und `korg.seq.setPartValue` unten; die eines gespeicherten Patterns (`korg.patterns[i]`) nur lesen.
`sample`, `ifxOn`, `ifxType` und `ampEg` lassen sich ab API Version 23 setzen, die neuen Werte von API Version 24 gleich mit,
die Einzelheiten stehen bei `korg.seq.setPartValue` und `korg.seq.setPatternValue`. Die Liste und woher jeder Wert kommt, steht in `data/script/contract.mjs`
(`PATTERN_FIELDS`, `PART_FIELDS`), gemessen sind die Stellen in der Gerätekarte `data/map/pattern.mjs`. Ab API Version 8.

**Motion Sequence an und aus**: `korg.parts[i].motionMode` ist die Seite MOTION SEQ des Part-Menüs, 0 aus, 1 smooth,
2 trigger hold (ab API Version 24). Ein Plugin schaltet damit die Motion Sequence eines Parts aus, ohne die aufgenommene
Bewegung zu löschen; mit dem alten Wert spielt sie wieder.

```js
// TAP schaltet die Motion Sequence aller Parts aus und wieder so ein, wie sie war.
const saved = new Array(16);
let off = 0;
korg.onEvent("buttonPress", (key) => {
  if (key != korg.key.TAP) return;
  for (let i = 0; i < 16; i++) {
    if (off == 0) {
      saved[i] = korg.parts[i].motionMode;
      korg.parts[i].motionMode = 0;
    } else {
      korg.parts[i].motionMode = saved[i];
    }
  }
  off = 1 - off;
});
```

`+=`, `-=` und die anderen zusammengesetzten Zuweisungen gehen bei allem, was sich lesen und setzen lässt,
dazu `++` und `--`: `korg.tempo += 10;` liest das Tempo und setzt es um 1,0 BPM höher. Der Index in den
Klammern darf dabei keinen Funktionsaufruf enthalten. `korg.led.TAP` allein ist weiter die Nummer der
LED, so wie in `korg.led(korg.led.TAP, 255)`; erst als linke Seite einer Zuweisung setzt es die LED.

Die Regler haben die Namen aus der Tabelle des Panels: `LEVEL`, `PAN`, `PITCH`, `RESONANCE`, `EG_INT`,
`MOD_DEPTH`, `ATTACK`, `IFX_EDIT`, `DECAY`, `OSC_EDIT` und `MOD_SPEED`, in dieser Reihenfolge die Nummern
0 bis 10.

```js
// Ab dem 16. Schritt von Part 1 wird Part 4 stumm, bei jedem Takt neu.
korg.onEvent("step", (step) => {
  korg.parts[3].muted = korg.parts[0].step >= 15 ? 1 : 0;
});
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) korg.tempo += 10;
  korg.led.TAP = korg.transport == 1 ? 255 : 0;
});
```

Die Aufrufe in der Tabelle unten bleiben gültig, ältere Plugins laufen unverändert weiter. Was eine
Handlung ist, bleibt ein Aufruf: zeichnen, PLAY drücken, eine App anmelden, speichern.

### Die Electribe als Objektbaum (API 10, BLECHTRIBE 1.3.8)

Ab API 10 hängen die Einstellungen der Electribe und des Menüs BLECH an langen Pfaden. Ein Pfad liest und
setzt sich wie eine Eigenschaft oben, der Übersetzer macht daraus `korg.get` oder `korg.set` mit der Nummer
des Blatts, lange Namen kosten am Gerät also nichts. Ein Plugin, das einen Pfad nutzt, braucht API 10 und
läuft auf älterer Firmware nicht (sie lehnt den Block ab).

Ein Wert außerhalb des Bereichs wird auf die nächste Grenze geklemmt und gezählt (`korg.system.repairs`),
das Plugin läuft weiter. Steht der Wert schon beim Übersetzen fest, meldet der Übersetzer ihn als Fehler.
Ein falsch geschriebener Pfad ist ein Fehler beim Übersetzen, die Meldung nennt, was es an der Stelle gibt.
Gespeicherte Werte prüft die Laufzeit beim Start, egal woher ein ungültiger Wert kommt, und klemmt oder
setzt ihn auf den Werkswert zurück; auch das zählt `korg.system.repairs`.

| Pfad | Lesen | Setzen | Bereich |
|---|---|---|---|
| `korg.menu.blech.customizations.display.intensity` | Helligkeit des Display-Lichts wie die Seite INTENSITY | ja, wirkt sofort; WRITE im Menü behält sie | 0 (aus) bis 15 (voll) |
| `korg.system.repairs` | wie viele Werte seit dem Start geklemmt oder zurückgesetzt wurden | nein | 0 bis 2147483647 |
| `korg.system.testMode` | ob der Test-Modus an ist: Display, Licht und alle LEDs dunkel, Auto Power Off angehalten | nein, nur über USB; nur im RAM, nach einem Neustart aus | 0 (aus) bis 1 (an) |
| `korg.system.keepAwake()` | (ein Aufruf, kein Wert) | startet die 4 Stunden von Auto Power Off neu, wie eine Taste am Gerät | |
| `korg.system.device` | auf welchem Gerät das Plugin läuft: 0 Hacktribe, 1 roter Sampler (Korg), 2 blauer Synth (Korg) (ab API Version 26) | nein | 0 bis 2 |
| `korg.system.version` | Version des BLECHTRIBE-Sets als Zahl, x * 10000 + y * 100 + z, 1.5.0 ist 10500; 0, wenn das Set keine Versionsangabe hat (im Simulator des Editors 0) | nein | 0 bis 999999 |
| `korg.system.limits.ifxTypes` | wie viele Insert-Effekte die Firmware hat, `ifxType` geht von 0 bis zu diesem Wert minus 1; die Firmware zählt sie beim Lesen, ein Effekt-Katalog erhöht sie | nein | 0 bis 255 |
| `korg.system.limits.mfxTypes` | wie viele Master-Effekte die Firmware hat, `mfxType` geht von 0 bis zu diesem Wert minus 1; wie oben | nein | 0 bis 255 |
| `korg.system.limits.samples` | wie viele Sample-Slots `sample` wählen kann: 1000 auf dem roten Sampler, 0 auf dem blauen Synth | nein | 0 bis 1000 |
| `korg.touchpad.mode` | Touchpad-Modus: 0 Gate Arp, 1 Touch Scale, 2 Master FX, 3 Gate Arp + Touch Scale, 4 MFX 2 (Master FX mit dem MFX-2-Typ des Patches mfx-switch) (ab API Version 27) | ja: drückt die eine Taste, die vom jetzigen Modus dorthin führt, LEDs und Effekt stehen danach wie nach der Taste. Mit MFX 2 an: GATE ARP gibt 3, TOUCH SCALE 4, MASTER FX 2, SHIFT + TOUCH SCALE 1; 0 ist dann nicht erreichbar. Ohne MFX 2 die Tasten der Firmware; ein Modus, den kein Druck erreicht, bleibt, wie er ist | 0 bis 4 |
| `korg.motion.enabled` | 1, wenn der gewählte Part seine Motion Sequence spielt (Modus Smooth oder Trigger Hold), 0, wenn sie aus ist (ab API Version 28) | ja: drückt einmal TAP, wenn der Patch tap-motion an ist und der Wert sich ändert, wie die Hand; der Patch merkt sich den Modus. Ohne den Patch ändert sich nichts | 0 bis 1 |
| `korg.pads.mode` | Pad-Modus der Firmware: 0 PART MUTE, 2 PART ERASE, 3 TRIGGER, 4 SEQUENCER, 5 KEYBOARD, 6 CHORD, 7 STEP JUMP, 9 PATTERN SET (ab API Version 29) | nein | 0 bis 9 |
| `korg.pads.bar` | welchen Takt eines Patterns über 16 Steps die Pads zeigen, 0 bis 3 für Takt 1 bis 4 (ab API Version 29) | nein | 0 bis 3 |
| `korg.screen` | Nummer des offenen Bildschirms der Firmware: 1 Hauptbildschirm, 3 Pattern-Menü, 7 Part Edit, 8 Global, 19 Step Edit, 21 Part Util, 37 Sample; die übrigen Nummern stehen in der [Messung](messungen/2026-11-11-plugin-api29-state-events.md) (ab API Version 29) | nein | 0 bis 255 |
| `korg.system.power` | Stromquelle, wie die Firmware sie oben rechts zeigt: 1 Netzteil, 0 Batterie (Panel-Nachricht 7; ab API Version 34, [Messung](messungen/2026-11-11-plugin-api34-system.md)) | nein | 0 bis 1 |
| `korg.system.battery` | Ladestand der Batterie wie das Symbol oben rechts: 4 voll, 3, 2, 1 schwach (die Firmware meldet dann die Batterie), 0 leer; am Netzteil ohne Bedeutung (ab API Version 34) | nein | 0 bis 4 |
| `korg.menu.blech.customizations.display.red` | Rotanteil des Display-Lichts (die Seiten BACKLIGHT HUE, SAT und BRIGHT zeigen ihn als Farbton, Sättigung, Helligkeit); alle drei auf 0 ist das Weiß der Firmware | ja, wirkt sofort wie die Seite | 0 bis 15 |
| `korg.menu.blech.customizations.display.green` | Grünanteil des Display-Lichts | ja, wirkt sofort wie die Seite | 0 bis 15 |
| `korg.menu.blech.customizations.display.blue` | Blauanteil des Display-Lichts | ja, wirkt sofort wie die Seite | 0 bis 15 |
| `korg.menu.blech.customizations.display.invert` | Display invertiert (1), wie die Seite DISPLAY INVERT | ja, wirkt sofort wie die Seite | 0 bis 1 |
| `korg.menu.blech.customizations.led.mode` | untere LEDs: 0 Meter, 1 Farbe, 2 aus (Seite BOTTOM LEDS) | ja, wirkt sofort wie die Seite | 0 bis 2 |
| `korg.menu.blech.customizations.led.red` | Rotanteil der unteren LEDs (Seiten LED HUE, SAT, BRIGHT); alle drei auf 0 sind die Farben der Firmware | ja, wirkt sofort wie die Seite | 0 bis 15 |
| `korg.menu.blech.customizations.led.green` | Grünanteil der unteren LEDs | ja, wirkt sofort wie die Seite | 0 bis 15 |
| `korg.menu.blech.customizations.led.blue` | Blauanteil der unteren LEDs | ja, wirkt sofort wie die Seite | 0 bis 15 |
| `korg.menu.blech.customizations.led.meter.still` | Farbe von METER STILL: 0 Firmware, 1 bis 7 weiß, rot, grün, blau, gelb, cyan, rosa, 8 Regenbogen, 9 aus | ja, wirkt sofort wie die Seite | 0 bis 9 |
| `korg.menu.blech.customizations.led.meter.low` | Farbe von METER LOW: 0 Firmware, 1 bis 7 wie oben | ja, wirkt sofort wie die Seite | 0 bis 7 |
| `korg.menu.blech.customizations.led.meter.mid` | Farbe von METER MID: 0 Firmware, 1 bis 7 wie oben | ja, wirkt sofort wie die Seite | 0 bis 7 |
| `korg.menu.blech.customizations.led.meter.loud` | Farbe von METER LOUD: 0 Firmware, 1 bis 7 wie oben, 8 Regenbogen | ja, wirkt sofort wie die Seite | 0 bis 8 |
| `korg.menu.blech.customizations.padColor.part` | PAD COLOR: 0 rot, 1 blau, 2 rosa; nie gleich SELECT COLOR, ein Schreiben, das beide gleich machen würde, vertauscht sie | ja, wirkt sofort wie die Seite | 0 bis 2 |
| `korg.menu.blech.customizations.padColor.select` | SELECT COLOR: 0 rot, 1 blau, 2 rosa; Regel wie bei PAD COLOR | ja, wirkt sofort wie die Seite | 0 bis 2 |
| `korg.menu.blech.customizations.padColor.overlap` | OVERLAP, Farbe eines Pads, das leuchtet und gewählt ist: 0 die Farbe, die bleibt, 1 rot, 2 blau, 3 rosa | ja, wirkt sofort wie die Seite | 0 bis 3 |
| `korg.menu.blech.customizations.powerSave.displayLight` | DISPLAY LIGHT im Power Save: 0 das Dimmen der Firmware, 1 bis 15 Stärke des Lichts | ja, wirkt sofort wie die Seite | 0 bis 15 |
| `korg.menu.blech.customizations.powerSave.ledDimming` | LED DIMMING im Power Save als Schritt des Rads: 0, 10, 20, 30, 40, 50, 60, 70, 75, 80, 90, 100 Prozent gedimmt | ja, wirkt sofort wie die Seite | 0 bis 11 |
| `korg.menu.blech.features.mfx2` | MFX 2 an (1); gilt ab dem nächsten Start, die Seite sagt das | ja | 0 bis 1 |
| `korg.menu.blech.features.patternConfirm` | PATTERN CONFIRM: der Patternwechsel wartet auf einen zweiten Druck (1) | ja, wirkt sofort wie die Seite | 0 bis 1 |
| `korg.menu.blech.features.tapMotion` | TAP MOTION: 0 aus, 1 an, 2 einmal | ja, wirkt sofort wie die Seite | 0 bis 2 |
| `korg.menu.blech.features.noteAssist` | NOTE ASSIST: die Pads zeigen die Noten, die passen (1) | ja, wirkt sofort wie die Seite | 0 bis 1 |
| `korg.menu.blech.features.lastPattern` | LAST PATTERN: beim Einschalten das zuletzt gewählte Pattern öffnen (1) | ja, wirkt sofort wie die Seite | 0 bis 1 |
| `korg.menu.blech.features.stereo1Pad` | STEREO 1 PAD: ein Stereo-Sample belegt nur seinen eigenen Pad (1) | ja, wirkt sofort wie die Seite | 0 bis 1 |
| `korg.menu.blech.features.initPattern` | SET INIT PATTERN: das Pattern, das INITIALIZE PATTERN kopiert; 0 die Vorlage der Firmware | ja, wirkt sofort wie die Seite | 0 bis 250 |
| `korg.menu.blech.write()` | (ein Aufruf, kein Wert) | schreibt die Einstellungen des Menüs BLECH auf die Karte wie WRITE auf einer Seite, siehe unten | |
| `korg.global.triggerMode` | Seite TRIGGER MODE von GLOBAL PARAMETERS: 0 Normal, 1 Seq 1st, 2 Seq Play | ja, wie das Menü, über die Funktion der Firmware | 0 bis 2 |
| `korg.global.velocityCurve` | Seite VELOCITY CURVE von GLOBAL PARAMETERS: 0 Heavy, 1 Normal, 2 Light, 3 Const96 | ja, wie das Menü, über die Funktion der Firmware | 0 bis 3 |
| `korg.global.clockMode` | Seite CLOCK MODE von GLOBAL PARAMETERS: 0 Internal, 1 Auto, 2 External USB, 3 External MIDI, 4 External Sync | ja, wie das Menü, über die Funktion der Firmware | 0 bis 4 |
| `korg.global.midiChannel` | Seite GLOBAL MIDI CH. von GLOBAL PARAMETERS: 0 bis 15 für Kanal 1 bis 16 | ja, wie das Menü, über die Funktion der Firmware | 0 bis 15 |
| `korg.global.receiveFilter` | Seite MIDI RECEIVE FILTER von GLOBAL PARAMETERS: 0 Off, 1 Short, 2 Short + Program | ja, wie das Menü, über die Funktion der Firmware | 0 bis 2 |
| `korg.global.sendFilter` | Seite MIDI SEND FILTER von GLOBAL PARAMETERS: 0 Off, 1 Short, 2 Short + Program | ja, wie das Menü, über die Funktion der Firmware | 0 bis 2 |
| `korg.global.syncPolarity` | Seite SYNC POLARITY von GLOBAL PARAMETERS: 0 Hi, 1 Lo | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |
| `korg.global.syncResolution` | Seite SYNC UNIT von GLOBAL PARAMETERS: 0 1 Step, 1 2 Steps | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |
| `korg.global.metronome` | Seite METRONOME von GLOBAL PARAMETERS: 0 Off, 1 Rec 0, 2 Rec 1, 3 Rec 2, 4 On | ja, wie das Menü, über die Funktion der Firmware | 0 bis 4 |
| `korg.global.tempoLock` | Seite TEMPO LOCK von GLOBAL PARAMETERS: 0 Off, 1 On | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |
| `korg.global.knobMode` | Seite KNOB MODE von GLOBAL PARAMETERS: 0 Jump, 1 Catch, 2 Value Scale | ja, wie das Menü, über die Funktion der Firmware | 0 bis 2 |
| `korg.global.touchScaleRange` | Seite TOUCH SCALE RANGE von GLOBAL PARAMETERS: Oktaven, 0 spielt nur den Grundton | ja, wie das Menü, über die Funktion der Firmware | 0 bis 4 |
| `korg.global.lcdContrast` | Seite LCD CONTRAST von GLOBAL PARAMETERS: 18 bis 42, das Display zeigt 1 bis 25 | ja, wie das Menü, über die Funktion der Firmware | 18 bis 42 |
| `korg.global.audioInThru` | Seite AUDIO IN THRU von GLOBAL PARAMETERS: 0 Off, 1 On | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |
| `korg.global.batteryType` | Seite BATTERY TYPE von GLOBAL PARAMETERS: 0 Ni-MH, 1 Alkali | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |
| `korg.global.autoPowerOff` | Seite AUTO POWER OFF von GLOBAL PARAMETERS: 0 Disable, 1 4 hours | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |
| `korg.global.powerSave` | Seite POWER SAVE MODE von GLOBAL PARAMETERS: 0 Disable, 1 Auto, 2 Enable | ja, wie das Menü, über die Funktion der Firmware | 0 bis 2 |
| `korg.global.patternChangeLock` | Seite PTN. CHANGE LOCK von GLOBAL PARAMETERS: 0 Off, 1 On | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |
| `korg.global.chainMode` | Seite CHAIN MODE von GLOBAL PARAMETERS: 0 Off, 1 On | ja, wie das Menü, über die Funktion der Firmware | 0 bis 1 |

```js
// Licht aus, solange die App offen ist, danach wieder wie vorher.
let light = 15;
korg.app("Dunkel", "TOOLS");
korg.onEvent("open", () => {
  light = korg.menu.blech.customizations.display.intensity;
  korg.menu.blech.customizations.display.intensity = 0;
});
korg.onEvent("close", () => {
  korg.menu.blech.customizations.display.intensity = light;
});
```

**Die Seiten von BLECHTRIBE (API 17).** Alle Seiten von CUSTOMIZATION und FEATURES haben ein Blatt, dazu das
Blatt SET INIT PATTERN aus DATA UTILITY. Ein Blatt dieser Gruppe braucht API 17. Jede Schreibung ruft die Anwendefunktion, die
auch die Seite nimmt: die Look-Seiten setzen Licht, LEDs und Display neu, PAD COLOR, SELECT COLOR, OVERLAP und LED DIMMING gehen
durch den Patch der Pad-Farben, PATTERN CONFIRM, TAP MOTION und NOTE ASSIST setzen zusätzlich das Wort, das ihr Patch liest.
Danach zeigt die Seite den neuen Wert. Die Farben zeigen die Seiten als Farbton, Sättigung und Helligkeit, gespeichert und
darum als Blatt sichtbar sind Rot, Grün und Blau mit je 0 bis 15. Ein Wert, den ein Patch nie geschrieben hat (LAST PATTERN,
STEREO 1 PAD), liest sich als Werkswert, wie der Patch ihn behandelt. Nicht als Blatt stehen die Aktionen der Seiten
(SPLASH IMPORT, DRAW und RESET, die Exporte), PLUGIN RUNTIME (ein Plugin, das seine eigene Laufzeit ausschaltet, ließe das
Gerät beim nächsten Start ohne Plugins) und SYNC GROUP (eine Einstellung des Patterns).

**Nur im RAM, bis WRITE.** Die Werte gelten sofort, liegen aber nur im RAM. Auf die Karte kommen sie mit WRITE auf einer Seite
des Menüs BLECH (die Datei `settings.a.bin` oder `settings.b.bin`), vorher nicht; nach einem Neustart gilt, was zuletzt
geschrieben wurde. Mit AUTO SAVE schreibt auch das Verlassen des Menüs BLECH die Datei, wenn sich die Einstellungen geändert haben,
seit es geöffnet wurde. Ausnahme ist SET INIT PATTERN: es liegt in den Global-Einstellungen der Firmware, die das Gerät beim
Ausschalten speichert. Wie die Seiten von GLOBAL PARAMETERS zeigen die Seiten von BLECH das Schildchen ORIG, solange der Wert der
gespeicherte ist (der in der Einstellungsdatei, ohne Datei der Standard): es verschwindet, wenn du den Wert änderst, kommt beim
Zurückdrehen wieder und gilt nach WRITE für den neuen Wert. Aktionen und Listen (EXPORT, SPLASH, PLUGINS) haben keins.
`korg.menu.blech.write()` schreibt die Einstellungsdatei aus dem Plugin, wie WRITE es tut. Es fragt nur
an: geschrieben wird einen Moment später, nur solange der Hauptbildschirm oder BLECH offen ist, und frühestens 2 Sekunden nach
dem letzten Schreiben, weitere Aufrufe davor bleiben eine Anfrage. Ohne Karte oder bei einem Fehler passiert nichts weiter, wie
bei WRITE im Menü. Ein Plugin sollte es sparsam rufen, etwa wenn es einen Wert gesetzt hat, den der Anwender behalten soll.

```js
// Beim Öffnen der App das Display umkehren und die Einstellung behalten.
korg.app("Invert", "TOOLS");
korg.onEvent("open", () => {
  korg.menu.blech.customizations.display.invert = 1 - korg.menu.blech.customizations.display.invert;
  korg.menu.blech.write();
});
```

Der Test-Modus lässt das Gerät aussehen wie ausgeschaltet, während es läuft: Display aus, Display-Licht aus,
jede LED auf 0, auch wenn die Firmware, Blechy oder ein anderes Plugin sie setzt, und Auto Power Off schaltet
nicht ab. Das Gerät nimmt weiter Tasten, Regler und Pads an, und sein Bild lässt sich über USB lesen. Nur der
Rechner schaltet ihn, über USB ([Test-Modus](test-modus.md)); ein Plugin liest `korg.system.testMode` nur, damit
keines das Gerät bei jedem Start dunkel lassen kann. Beim Ausschalten kommen Licht und LEDs zurück, wie sie ohne
Test-Modus wären; eine LED, die ein Plugin inzwischen gesetzt hat, zeigt dessen Wert.

**Die Globals (`korg.global`, API 20).** Zu jeder bekannten Seite von GLOBAL PARAMETERS gibt es ein Blatt, mit dem
Namen der Seite in camelCase und den Werten, die das Gerät speichert (`korg.global.midiChannel` 0 bis 15 ist Kanal 1 bis 16).
Die Bereiche sind die Grenzen des Menüs. Nicht im Baum sind die Kennungen am Anfang und Ende des Blocks, die Bytes, die
kein Menü ändert, und die Plätze 247 bis 249, die Patches von BLECHTRIBE belegen. Ein Plugin, das ein Blatt nennt, braucht API 20.

Setzen ruft dieselbe Funktion der Firmware, die auch die Seite im Menü beim Drehen ruft: sie schreibt das Byte und meldet
es an Klangerzeugung, Display und MIDI-Seite (bei `tempoLock` stellt sie danach das Tempo neu). Der Wert wirkt sofort, ohne
Neustart; die Seite im Menü zeigt ihn, sobald sie neu gezeichnet wird, also wenn man sie öffnet. Bei `clockMode` lehnt die
Firmware das Setzen ab, solange der Transport in ihrem Zustand 6 bis 9 ist, genau wie im Menü. Ein Wert außerhalb der Grenzen
wird auf die nächste Grenze geklemmt und gezählt, ein gespeicherter Wert außerhalb wird beim Start repariert: auf die nächste
Grenze, ohne die Funktion der Firmware zu rufen. Im Emulator gemessen auf Hacktribe, Korg rot und Korg blau
([Messung](messungen/2026-11-05-plugin-api20-globals.md)); am Gerät nicht.

**Speichern.** Dafür gibt es keinen Aufruf. Die Firmware speichert die Globals beim Ausschalten und bei WRITE auf der Seite
GLOBAL PARAMETERS, wie sie auch das letzte Pattern behält. Mit BLECH > FEATURES > AUTO SAVE speichert sie sie außerdem, wenn
jemand GLOBAL PARAMETERS verlässt und die Werte vom gespeicherten Stand abweichen ([Messung](messungen/2026-11-09-auto-save.md)). Ein Wert, den ein Plugin gesetzt hat, bleibt deshalb über den
nächsten Neustart, auch wenn das Plugin dann nicht mehr läuft. Ein Plugin, das die Einstellung des Nutzers nur vorübergehend
ändern will, setzt sie zurück, wie das Beispiel oben mit der Helligkeit.

**Zustimmung.** Ein Plugin, das Globals setzt, braucht keine eigene Zustimmung. Ein fremdes Plugin (ein Block ohne das Bit
"geprobt") läuft ohnehin erst nach WRITE=ALLOW; mit dieser Zustimmung darf es auch die Globals dauerhaft ändern. Wer WRITE=ALLOW gibt,
erlaubt das also mit.

```js
// Metronom an und Kontrast eine Stufe höher, solange die App offen ist, danach wie vorher.
let metro = 0;
let contrast = 0;
korg.app("Metronom", "TOOLS");
korg.onEvent("open", () => {
  metro = korg.global.metronome;
  contrast = korg.global.lcdContrast;
  korg.global.metronome = 4;
  korg.global.lcdContrast = contrast + 1;
});
korg.onEvent("close", () => {
  korg.global.metronome = metro;
  korg.global.lcdContrast = contrast;
});
```

`korg.pattern.current` ist der Name des laufenden Patterns im Objektbaum; `korg.current` meint dieselben
Werte, ist aber seit API 35 veraltet (siehe [Veraltete Aufrufe](#veraltete-aufrufe-api-35)).

### Timer (API 11, BLECHTRIBE 1.3.8)

Ein Plugin kann nicht warten: alle Handler eines Rahmens haben zusammen 5 ms, ein `wait(ms)` würde das Gerät
anhalten. Stattdessen gibt es Timer. Man übergibt eine Funktion, die Laufzeit ruft sie später auf:

| Aufruf | Wirkung |
|---|---|
| `korg.after(ms, fn)` | ruft `fn` einmal auf, sobald `ms` Millisekunden vergangen sind (0 bis 86400000) |
| `korg.every(ms, fn)` | ruft `fn` alle `ms` Millisekunden auf (1 bis 86400000), bis `korg.cancel` den Timer stoppt |
| `korg.afterSteps(n, fn)` | ruft `fn` einmal auf, wenn der Sequencer `n` Schritte (16tel, 1 bis 65535) weiter ist |
| `korg.cancel(nummer)` | stoppt den Timer mit dieser Nummer |

`fn` ist der Name einer Funktion ohne Parameter oder ein Pfeil ohne Werte, `() => { ... }`. Wie jede Funktion
sieht sie nur die globalen Variablen, keine lokalen der Stelle, an der der Timer gesetzt wurde. Die drei Aufrufe
geben die Nummer des Timers zurück, die `korg.cancel` nimmt. Jedes Plugin hat 8 Plätze; sind alle belegt, kommt
-1 zurück und nichts passiert. Ein einmaliger Timer gibt seinen Platz frei, sobald er gelaufen ist. Eine alte
Nummer, deren Timer schon gelaufen ist, stoppt nicht den Timer, der den Platz inzwischen hat, und `korg.cancel(-1)`
tut nichts, man kann also das -1 eines vollen `korg.after` gefahrlos weitergeben.

Die Laufzeit prüft die Timer am Anfang jedes Rahmens, also alle 40 ms. Ein Timer läuft frühestens nach `ms`, höchstens
einen Rahmen später: `korg.after(1000, fn)` kommt nach 1000 bis 1040 ms. `korg.every` hält sein Raster, ein Rahmen
später verschiebt den nächsten Termin nicht. Wer in `fn` mit `korg.after` neu setzt, zählt dagegen vom Rahmen aus, in
dem `fn` lief, und wandert pro Runde um bis zu 40 ms. Timer laufen auch für eine geschlossene App, und sie gehen nur an
das Plugin, das sie gesetzt hat. Erlaubt sind sie überall außer in `save`, auch im Rumpf.

`korg.afterSteps` zählt die Ereignisse `step`, solange der Sequencer läuft: bei STOP steht der Zähler, bei PLAY zählt
er weiter, und er folgt dem Tempo. Der Timer läuft im selben Rahmen wie das Ereignis `step`, das ihn auslöst, direkt
danach. Kommen bei sehr hohem Tempo zwei Schritte in einem Rahmen, sieht die Laufzeit nur einen (bei 300 BPM liegt ein
Schritt 50 ms auseinander, der Rahmen 40 ms).

```js
// Die TAP-LED blinkt alle 500 ms, nach 2 Sekunden zeigt das Display eine Nachricht.
let on = 0;
function blink() {
  on = 1 - on;
  korg.led(korg.led.TAP, on * 255);
}
korg.onEvent("ready", () => {
  korg.every(500, blink);
  korg.after(2000, () => { korg.display.take(); korg.display.text("HALLO", 0, 0); });
});
```

```js
// Ein Takt (16 Schritte) nach PLAY wird Part 1 stumm, mit STOP vor Ablauf passiert nichts mehr.
let timer = -1;
korg.onEvent("play", () => { timer = korg.afterSteps(16, () => { korg.mute(0, 1); }); });
korg.onEvent("stop", () => { korg.cancel(timer); });
```

Die Uhr hinter den Timern und `korg.millis()` ist Timer3 (150 MHz), den die Firmware jede Sekunde überlaufen lässt.
Die Laufzeit führt sie in jedem Rahmen nach; ganze Sekunden, die zwischen zwei Aufrufen verloren gingen (vor dem
ersten Rahmen nach dem Start), holt sie aus dem Tick-Zähler des Betriebssystems, eins je Millisekunde. Gemessen im
Emulator ([Messung](messungen/2026-10-29-plugin-timer.md)): nach dem Start kommt der Rahmen alle 40 ms, höchstens 46 ms,
auch bei einem Pattern-Wechsel; Samples lädt die Firmware vor dem ersten Rahmen, und ein Plugin auf der Karte
startet erst danach, ein Timer aus dem Rumpf kommt daher rechtzeitig. Am Gerät ist das noch nicht geprüft.

### Funktionen der Electribe

Alle Namen beginnen mit `korg.`. Zahlen außerhalb des Bereichs beenden das
Plugin mit einem Fehler.

| Aufruf | Wirkung | Erlaubt in |
|---|---|---|
| `korg.led(index, level)` | LED Auftrag vormerken, `index` 0 bis 87 (am besten ein Name wie `korg.led.TAP`), `level` 0 bis 255 | allen Ereignissen außer dem Rumpf und `save` |
| `korg.millis()` | Millisekunden seit dem ersten Aufruf, aus Timer3 (150 MHz), das alle 150 Millionen Ticks überläuft; ganze Sekunden zwischen zwei Aufrufen aus dem Tick-Zähler des Betriebssystems | überall |
| `korg.after(ms, fn)`, `korg.every(ms, fn)`, `korg.afterSteps(n, fn)`, `korg.cancel(nummer)` | Timer, siehe oben. Ab API Version 11 | überall außer `save` |
| `korg.app(name, gruppe)` | meldet das Plugin als App an: `name` 1 bis 15 Zeichen, `gruppe` `"GAMES"` oder `"TOOLS"`. Gibt die Nummer der App zurück, -1 wenn alle 16 Plätze belegt sind (das Gerät meldet dann beim Import "max 16 apps", das Plugin steht trotzdem in der Plugin-Liste und läuft). Als eigene Anweisung ganz oben, einmal je Plugin (der Übersetzer prüft das) | nur im Rumpf |
| `korg.file.frame(feld, datei, bild)` | liest Bild `bild` (0 bis 65535) der Datei `GIFnn.E2G` (`datei` 0 bis 99 ist nn) aus `KORG/blechtribe/Gif/` ins Feld, ein Byte je Platz, also genau, was `korg.display.bitmap(feld, 0, 0, 128)` zeichnet. Das Feld braucht mindestens 1024 Plätze. Gibt die Dauer des Bildes in ms zurück (mindestens 1), 0 hinter dem letzten Bild, -1 ohne Datei, bei falscher oder abgeschnittener Datei und außerhalb des Hauptbildschirms; nach -1 kann am Gerät das letzte Viertel des Felds verändert sein. Ab API Version 7 | wie `korg.led` |
| `korg.display.take()` | das Display nehmen (Weg 2, siehe oben); 1 wenn es klappt, 0 wenn nicht (eine App, ein anderer Besitzer, nicht der Hauptbildschirm) | wie `korg.led` |
| `korg.display.release()` | das Display zurückgeben | wie `korg.led` |
| `korg.display.popups = 0` | hält das Parameterfenster zu, das `korg.seq.setPartValue` sonst wie der Regler öffnet; nur für die Aufrufe dieses Plugins, 1 schaltet es wieder ein. Beim Laden steht es auf 1. `korg.knob` öffnet das Fenster der Firmware weiter, weil es den Regler selbst spielt. Lesen mit `korg.display.popups` oder `korg.read.popups()`. Ab API Version 24 | wie `korg.led` |
| `korg.display.clear()` | Display löschen; die Zeichenaufrufe wirken nur für den Besitzer des Displays (die offene App, oder wer es nahm) | wie `korg.led` |
| `korg.display.text(text, x, y)` | Text mit der linken oberen Ecke bei `x`, `y` (0 bis 127, 0 bis 63) | wie `korg.led` |
| `korg.display.number(wert, x, y)` | Zahl | wie `korg.led` |
| `korg.display.pixel(x, y, an)` | ein Pixel, `an` 0 oder 1 | wie `korg.led` |
| `korg.display.textNumber(text, wert, x, y)` | Text und gleich dahinter die Zahl, ohne dass das Plugin Ziffern zählt; wie `text` und danach `number`, die Zahl beginnt beim Zeichen hinter dem Text (6 Pixel je Zeichen). Ab API Version 6 | wie `korg.led` |
| `korg.display.chars(feld, x, y, anzahl)` | zeichnet das untere Byte jedes Platzes als Zeichen, wie `text` einen Text zeichnet: höchstens `anzahl` Zeichen (bis 31), bis zum Ende des Felds oder einem Platz, dessen unteres Byte 0 ist. Für Texte, die ein Plugin liest, etwa `korg.read.patternName`. Ab API Version 29 | wie `korg.led` |
| `korg.display.bitmap(feld, x, y, breite)` | zeichnet ein Bild aus einem globalen Feld, links oben bei `x` (-128 bis 127), `y` (-64 bis 63); was über den Rand reicht, wird abgeschnitten. Aufbau und Kosten siehe unten. Ab API Version 6 | wie `korg.led` |
| `korg.display.rect(x, y, breite, hoehe)` | gefülltes Rechteck | wie `korg.led` |
| `korg.display.clearRect(x, y, breite, hoehe)` | Rechteck löschen | wie `korg.led` |
| `korg.store.get(slot, vorgabe)` | gespeicherten Wert des Platzes `slot` (0 bis 15) dieses Plugins, oder `vorgabe`, wenn dort nie einer gespeichert wurde | überall, auch im Rumpf |
| `korg.store.set(slot, wert)` | Wert im RAM setzen, noch nicht auf der Karte | überall |
| `korg.store.save()` | Speichern vormerken | wie `korg.led` |
| `korg.read.transport()` | Zustand des Transports: 0 Stop, 1 Play, 2 Pause, 3 REC bereit, 4 Aufnahme | überall |
| `korg.read.tempo()` | Tempo in Zehntel BPM (1600 gleich 160,0) | überall |
| `korg.read.pattern()` | gewähltes Pattern, 0 bis 249 | überall |
| `korg.read.viewedPattern()` | Pattern, das das Display zeigt, 0 bis 249: beim Blättern und nach MENU das angesehene (aus der Bank), sonst das spielende. Es folgt dem Pattern, das die Pads und die Info-Texte der Edit-Zeile zeigen. Ab API Version 18 | überall |
| `korg.read.nextPattern()` | das bestätigte nächste Pattern, 0 bis 249, solange die Firmware es für das Sequenzende hält, sonst -1. Blättern allein (`VIEW:`) zählt nicht, erst MENU (`NEXT:`), und mit ausgeschaltetem PATTERN CONFIRM oder EXIT beim Einschalten bleibt es -1. Ab API Version 18 | überall |
| `korg.read.part()` | gewählter Part 0 bis 15, 16 für alle | überall |
| `korg.read.step(part)` | Schrittzähler des Parts, 0 bis 63 | überall |
| `korg.read.mute(part)` | 1, wenn der Part gemutet ist | überall |
| `korg.read.knob(index)` | letzter Rohwert des Reglers `index` (0 bis 19), den die Laufzeit gesehen hat, bis dahin 0 | überall |
| `korg.read.chainMode()` | 1, wenn CHAIN MODE im Global-Menü an ist. Ab API Version 8. **Veraltet seit API 35**, nimm `korg.global.chainMode` | überall |
| `korg.read.patternValue(pattern, part, wert)` | ein Wert eines Patterns: `pattern` -1 das laufende, 0 bis 249 ein gespeichertes; `part` -1 ein Wert des Patterns, 0 bis 15 einer des Parts; `wert` die Nummer in `PATTERN_FIELDS` oder `PART_FIELDS`. Lesbarer mit den Namen oben (`korg.current.tempo`). Ab API Version 8 | überall |
| `korg.play()` | PLAY drücken und loslassen, über den Tastenweg der Firmware | wie `korg.led` |
| `korg.stop()` | STOP drücken und loslassen | wie `korg.led` |
| `korg.pattern(index)` | Pattern wählen, 0 bis 249 | wie `korg.led` |
| `korg.tempo(zehntelBpm)` | Tempo setzen, 100 bis 3000 | wie `korg.led` |
| `korg.part(part)` | Part wählen, 0 bis 15 | wie `korg.led` |
| `korg.mute(part, stumm)` | Part stumm schalten (1) oder spielen lassen (0); die Firmware kennt nur Umschalten, die Laufzeit drückt das Pad nur, wenn der Zustand nicht schon stimmt | wie `korg.led` |
| `korg.backlight(rot, gruen, blau)` | die drei Farben des Display Lichts ein (1) oder aus (0), über die GPIO Funktion der Firmware; auf Batterie mit Power Save "Auto" überschreibt die Dimm Routine der Firmware die Farbe laufend; hat der Nutzer im Menü eine Mischfarbe mit Pegeln zwischen 1 und 14 gewählt, überschreibt auch deren PWM die Farbe | wie `korg.led` |
| `korg.menu.add(name, min, max, wert)` | legt eine Seite im Menü BLECH am Gerät an und gibt ihre Nummer zurück (-1, wenn alle 12 Plätze belegt sind). `name` höchstens 15 Zeichen, die Seite zeigt `wert` (in `min` bis `max` geklemmt, Betrag unter 100 Millionen) und den Plugin-Namen. Wird am Hauptrad gedreht, bekommt das Plugin `menu`(nummer, wert). Derselbe Name vom selben Plugin ist dieselbe Seite. `min` über `max` ist ein Argumentfehler | nur im Rumpf und in `ready` |
| `korg.ledHold(an)` | 1 hält die Firmware davon ab, die Panel LEDs neu zu schreiben (Pads, Tasten, untere RGB LEDs zeigen dann, was das Plugin gesetzt hat), 0 gibt sie zurück und lässt die Firmware alle LEDs neu senden; fällt das letzte laufende Plugin aus, gibt die Laufzeit sie selbst zurück | wie `korg.led` |
| `korg.padHold(an)` | 1 hält Pad-Anschläge von der Firmware fern: kein Klang, keine Änderung am Step, das Plugin bekommt `pad` aber weiter. Die Laufzeit setzt dafür das Pad-Bit der Maske, die der Eingangsfilter vor der Firmware liest. 0 nimmt den Halt dieses Plugins zurück; die Pads gehen erst an die Firmware zurück, wenn kein laufendes Plugin sie mehr hält (Abschnitt Eingaben fernhalten). Die Laufzeit gibt sie auch selbst zurück, wenn eine App schließt, und ein Plugin, das nicht mehr läuft, hält nichts mehr. Das Loslassen folgt immer seinem Anschlag: wurde der Anschlag zurückgehalten, bleibt auch das Loslassen bei den Plugins, sonst geht es an die Firmware. Ab API Version 12 | wie `korg.led` |
| `korg.knobHold(index, an)` | 1 hält die Bewegungen des Reglers `index` (0 bis 10, die Indizes stehen unter Regler, OSC EDIT ist 9) von der Firmware fern: der Parameter bleibt stehen, das Plugin bekommt `knob` aber weiter, mit dem Rohwert. 0 nimmt den Halt dieses Plugins zurück; ein Regler bleibt der Firmware verborgen, solange irgendein laufendes Plugin ihn hält. Ein Plugin, das nicht mehr läuft, hält nichts mehr; eine App, die schließt, gibt die Regler nicht zurück, ein Filter läuft auch ohne App. Gilt außerhalb des Menüs BLECH. Ab API Version 13 | wie `korg.led` |
| `korg.passKeys(taste, an)` | solange eine App offen ist, hält der Eingangsfilter die Tasten von der Firmware fern, außer REC, STOP, PLAY und EXIT. 1 lässt die Taste `taste` (0 bis 33, am besten ein Name wie `korg.key.PART_MUTE`) trotzdem zur Firmware, 0 hält sie fern, auch REC, STOP und PLAY. Das Plugin bekommt `buttonPress` und `buttonRelease` in beiden Fällen. Das Loslassen folgt seinem Anschlag wie bei `korg.padHold`. EXIT schließt die App immer. Schließt die App, gilt wieder die Vorgabe. Ab API Version 14 | wie `korg.led` |
| `korg.touchLockX(x)` | hält das X des Touchpads, das die Firmware sieht, auf `x` (0 bis 127), Y bleibt das des Fingers; -1 lässt los. Im Modus Master FX und Touch Scale rechnet die Firmware in Schritten von 2, `x` wird auf gerade abgerundet (127 ist 126); im Modus Gate Arp sieht sie `x` genau. Ein Finger am rohen X `r` ist `x = r >> 3`. Das Plugin bekommt `touch` weiter mit dem echten X. Gilt ab der nächsten Touch-Nachricht und außerhalb des Menüs BLECH. Die Laufzeit lässt auch selbst los, sobald das Plugin nicht mehr läuft. Im Emulator gemessen auf Hacktribe, rot und blau, im Modus Master FX, Touch Scale und Gate Arp; am Gerät nicht. Ab API Version 15 | wie `korg.led` |
| `korg.touchLockY(y)` | hält das Y des Touchpads, das die Firmware sieht, auf `y` (0 bis 127), X bleibt das des Fingers; -1 lässt los. Im Modus Master FX rechnet die Firmware in Schritten von 2, `y` wird auf gerade abgerundet (127 ist 126); im Modus Touch Scale und Gate Arp sieht sie `y` genau. Ein Finger am rohen Y `r` ist `y = r >> 3`. Mit `korg.touchLockX` zusammen sind beide fest. Das Plugin bekommt `touch` weiter mit dem echten Y. Gilt ab der nächsten Touch-Nachricht und außerhalb des Menüs BLECH. Die Laufzeit lässt auch selbst los, sobald das Plugin nicht mehr läuft. Im Emulator gemessen auf Hacktribe, rot und blau, im Modus Master FX, Touch Scale und Gate Arp; am Gerät nicht. Ab API Version 35 | wie `korg.led` |
| `korg.keyHold(taste, an)` | 1 hält die Taste `taste` (0 bis 33) von der Firmware fern, auch ohne offene App; das Plugin bekommt `buttonPress` und `buttonRelease` weiter. 0 nimmt den Halt dieses Plugins zurück, ein anderes Plugin kann die Taste weiter halten. Das Loslassen folgt seinem Anschlag wie bei `korg.passKeys`. EXIT beendet das Plugin mit einem Fehler, Apps bleiben schließbar. Ein Plugin, das nicht mehr läuft, hält keine Taste mehr. Seit API Version 19 hat jedes Plugin seine eigene Maske (`korg.keyMask`), `korg.keyHold` ändert nur ein Bit darin. Gilt außerhalb des Menüs BLECH. Im Emulator gemessen auf Hacktribe, rot und blau; am Gerät nicht. Ab API Version 15 | wie `korg.led` |
| `korg.pressKey(taste)` | gibt der Firmware einen kurzen Druck der Taste `taste` (0 bis 33): der Anschlag geht sofort in die Warteschlange des Panels, das Loslassen im nächsten Frame, beides über denselben Weg wie die Tasten des Panels. Eine Markierung lässt beide an Umbelegung, `korg.keyHold`, App und Plugins vorbei, kein Plugin bekommt sie als `buttonPress`. Ein zweiter Druck, bevor das Loslassen raus ist, entfällt, eine volle Warteschlange verwirft den Druck. EXIT schließt erst eine offene App und geht dann an die Firmware. Im Emulator gemessen auf Hacktribe, rot und blau (PLAY startet, STOP hält an); am Gerät nicht. Ab API Version 15 | wie `korg.led` |
| `korg.keyMask(low, high)` | setzt die ganze Tastenmaske dieses Plugins: Bit n von `low` ist die Taste n (0 bis 31, `1 << korg.key.PLAY`), Bit n von `high` die Taste 32 + n (`high` 0 bis 3). Jede Taste in der Maske hält das Plugin von der Firmware fern wie `korg.keyHold(taste, 1)`, jede andere gibt es zurück, andere Plugins bleiben unberührt. Das Plugin bekommt `buttonPress` und `buttonRelease` weiter. EXIT in der Maske beendet das Plugin mit einem Fehler. Was bei zwei Plugins mit derselben Taste gilt, steht im Abschnitt Eingaben fernhalten. Im Emulator gemessen auf Hacktribe, rot und blau; am Gerät nicht. Ab API Version 19 | wie `korg.led` |
| `korg.keyDown(taste)` | drückt die Taste `taste` (0 bis 33) für die Firmware und hält sie, bis `korg.keyUp` sie loslässt, wie ein Finger: lange Drücke und SHIFT-Kombinationen gehen so. Die Nachricht ist die des Panels und geht in seine Warteschlange; eine Markierung lässt sie an Umbelegung, `korg.keyHold`, `korg.passKeys`, App, Tastenkürzeln von BLECHTRIBE und Plugins vorbei, kein Plugin bekommt sie als `buttonPress`. Ein zweites `korg.keyDown` derselben Taste sendet nichts. EXIT schließt erst eine offene App, dann bekommt die Firmware EXIT. Abschnitt Bedienen wie ein Finger. Im Emulator gemessen auf Hacktribe, rot und blau; am Gerät nicht. Ab API Version 25 | wie `korg.led` |
| `korg.keyUp(taste)` | lässt die Taste `taste` los, die `korg.keyDown` gedrückt hat; für eine Taste, die das Plugin nicht drückt, sendet es nichts. Ab API Version 25 | wie `korg.led` |
| `korg.padDown(pad, velocity)` | schlägt das Pad `pad` (0 bis 15) mit `velocity` (1 bis 127) für die Firmware an und hält es, bis `korg.padUp` es loslässt, in jedem Pad-Modus wie ein Finger: TRIGGER spielt und wählt den Part, SEQUENCER schaltet den Step, KEYBOARD und CHORD spielen Noten, bei gehaltenem PART MUTE schaltet es die Stummschaltung. `korg.padHold` hält es nicht fest, das Plugin bekommt sein eigenes Pad nicht als `pad`. Im Emulator gemessen auf Hacktribe, rot und blau; am Gerät nicht. Ab API Version 25 | wie `korg.led` |
| `korg.padUp(pad)` | lässt das Pad `pad` los, das `korg.padDown` angeschlagen hat. Ab API Version 25 | wie `korg.led` |
| `korg.encoder(index, delta)` | dreht den Encoder `index` (0 VALUE, 1 SAMPLE/OSC, 2 CUTOFF, 3 MOD TYPE, 4 IFX TYPE) um `delta` Rasten (-127 bis 127, negativ nach links) für die Firmware, mit der Nachricht des Panels. 0 sendet nichts. Mit gedrücktem SHIFT (`korg.keyDown(korg.key.SHIFT)`) wirkt er wie SHIFT und Drehen. Im Emulator gemessen auf Hacktribe, rot und blau; am Gerät nicht. Ab API Version 25 | wie `korg.led` |
| `korg.touch(x, y)` | legt einen Finger auf das Touchpad bei `x` und `y` (Rohwerte 0 bis 1023 wie die des Panels): der erste Aufruf drückt die Taste TOUCHPAD und sendet die Stelle, jeder weitere bewegt den Finger, `x` = -1 hebt ihn ab. Das Plugin bekommt keinen `touch`, `korg.touchLockX` und `korg.touchLockY` gelten nicht für diesen Finger. Im Emulator gemessen auf Hacktribe, rot und blau, in Master FX und Touch Scale; am Gerät nicht. Ab API Version 25 | wie `korg.led` |
| `korg.motion.lane(lane)` | liest, wem Motion-Spur `lane` (0 bis 23) des bearbeiteten Patterns gehört: 0 niemandem, 1 bis 16 Part 1 bis 16, 17 dem Master-Effekt. Die Firmware belegt bei REC die nächste freie Spur. Im Emulator gemessen auf Hacktribe, rot und blau ([Messung](messungen/2026-11-11-plugin-api28-motion.md)). Ab API Version 28 | überall |
| `korg.motion.destination(lane)` | liest das Ziel der Spur, wie die Firmware es aufnahm, nach der Korg-Liste (10 Amp Level, also Regler 0; 15 und 16 Master FX X und Y; 19 MFX-Pad an/aus). Ab API Version 28 | überall |
| `korg.motion.value(lane, step)` | liest den Wert der Spur bei Step `step` (0 bis 63), 0 bis 127, -1 ohne Eintrag. Die Firmware hält einen Regler halbiert, ein Regler auf 200 liest also 100. Ab API Version 28 | überall |
| `korg.motion.setValue(lane, step, value)` | schreibt `value` (0 bis 127) in Step `step` der Spur, -1 leert den Step. Nur auf einer Spur, die jemandem gehört; auf einer freien bleibt alles, wie es ist. Ab API Version 28 | wie `korg.led` |
| `korg.motion.clearLane(lane)` | löscht die Spur über dieselbe Funktion der Firmware, die CLEAR MOTION benutzt: die Spur ist frei, die Wiedergabe für sie still. Die anderen Spuren rücken nicht nach. Ab API Version 28 | wie `korg.led` |
| `korg.motion.clearPart(part)` | löscht alle Spuren von Part `part` (0 bis 15), wie Part Util CLEAR MOTION. Ab API Version 28 | wie `korg.led` |
| `korg.motion.clearMfx()` | löscht alle Spuren des Master-Effekts, wie CLEAR MFX MOTION im Pattern-Menü. Ab API Version 28 | wie `korg.led` |
| `korg.motion.output(lane)` | liest, was die Motion-Wiedergabe gerade für die Spur sendet, 0 bis 127, -1 wenn still (gestoppt, Motion aus oder kein Eintrag). Ab API Version 28 | überall |
| `korg.knob(index, wert)` | gibt der Firmware den Wert `wert` (0 bis 255) für den Regler `index` (0 bis 10), über ihre eigene Reglerfunktion, als hätte der Regler ihn gesendet. Zusammen mit `korg.knobHold` filtert ein Plugin einen Regler, der springt. `korg.read.knob` zeigt weiter den Wert des Panels. Im Emulator gemessen auf Hacktribe, rot und blau: gleicht der Nachricht des Reglers in Pattern, Anzeige, LEDs und MIDI ([Messung](messungen/2026-11-08-plugin-api25-panel-calls.md)); am Gerät nicht. Ab API Version 13 | wie `korg.led` |
| `korg.remapKey(von, nach)` | die Taste `von` kommt bei der Firmware und bei den Plugins als Taste `nach` an (beide 0 bis 33, am besten Namen wie `korg.key.PART_ERASE`), solange das Plugin läuft: der Eingangsfilter schreibt den Code in der Panel-Nachricht um, bevor die Firmware sie liest, die Firmware tut also genau, was sie mit `nach` tut. Es gilt eine Umlegung für alle Plugins, die letzte zählt; dieselbe Taste zweimal hebt sie auf. EXIT lässt sich nicht umlegen. Ab API Version 8 | nur im Rumpf und in `ready` |
| `korg.seq.setStep(part, step, note, velocity)` | schreibt Step `step` (0 bis 63) von Part `part` (0 bis 15) im Pattern, das läuft: `note` 0 bis 127 mit `velocity` 1 bis 127 schaltet ihn an, mit dieser Note auf dem ersten Notenplatz (die anderen drei leer); `note` -1 oder `velocity` 0 schaltet ihn aus. Das Gate bleibt, wie es ist. Der Trigger ist an, ab API Version 22 aus, wenn der Step davor an ist und ein TIE hat (Gate über 96), so wie die Firmware ihn beim Setzen eines TIE schreibt: dann klingt eine gebundene Kette derselben Note wie eine Note, statt bei jedem Step neu anzuschlagen ([Messung](messungen/2026-11-06-step-trigger.md)). Das Gate des Steps davor also zuerst setzen. Ab API Version 9 | wie `korg.led` |
| `korg.seq.setGate(part, step, gate)` | setzt das Gate des Steps, 0 bis 127; 96 ist ein ganzer Schritt, über 96 bindet an die nächste Note (Tie; die Firmware wertet jedes Gate über 96 als TIE, 127 und die 255, die in einem Pattern stehen kann, verhalten sich gleich). Ab API Version 9 | wie `korg.led` |
| `korg.seq.clearPart(part)` | schaltet alle 64 Steps des Parts aus, Noten, Gates und Velocity bleiben stehen. Ab API Version 9 | wie `korg.led` |
| `korg.seq.getOn(part, step)` | liest das An-Byte von Step `step` (0 bis 63) von Part `part` (0 bis 15) im Pattern, das läuft: 1 an, 0 aus. Liest nur, die Pads zeichnen sich dafür nicht neu. Im Emulator geprüft auf Hacktribe, rot und blau ([Messung](messungen/2026-11-06-plugin-api22-step-getters.md)). Ab API Version 22 | überall |
| `korg.seq.getGate(part, step)` | liest das Gate-Byte des Steps so, wie es im Pattern steht, ohne Umrechnung: 0 bis 96 ist die Länge, die Step-Eingabe der Firmware schreibt 127 für TIE (das Display zeigt TIE für jeden Wert über 96). In Patterns steht auch 255, `getGate` gibt es unverändert zurück; der Sequencer spielt jedes Gate über 96 als TIE, 127 und 255 gleich (im Emulator auf Hacktribe gemessen). Ab API Version 22 | überall |
| `korg.seq.getNote(part, step, platz)` | die MIDI-Note auf Notenplatz `platz` (0 bis 3) des Steps, -1 für einen leeren Platz (im Pattern steht Note + 1, 0 heißt leer). Ab API Version 22 | überall |
| `korg.seq.getVelocity(part, step)` | liest das Velocity-Byte des Steps so, wie es im Pattern steht. Ab API Version 22 | überall |
| `korg.seq.setPartValue(part, wert, x)` | setzt den Wert `wert` (Nummer in `PART_FIELDS`, wie bei `korg.read.patternValue`) von Part `part` auf `x`, in seinen Bereich geklemmt, über die Funktion der Firmware, die auch die Regler nehmen: Pattern im RAM und Klang ändern sich wie beim Drehen. Für den gewählten Part öffnet sich das Parameterfenster wie beim Regler. `voiceAssign` und `mfxSend` (ab API Version 21) gehen über die Funktion der Firmware, die auch die Seite VOICE ASSIGN im Part-Menü und die Taste MFX SEND rufen; sie schreiben Pattern und die Kopie der Klangerzeugung auf allen drei Firmwares, ohne Parameterfenster. Ab API Version 23 (im Emulator geprüft auf Hacktribe, rot und blau, [Messung](messungen/2026-11-07-plugin-api23-part-writes.md)): `ifxOn` und `ampEg` gehen den Weg der Tasten IFX ON und AMP EG, Pattern, Kopie der Klangerzeugung und die LED der Taste stehen danach wie nach der Taste; `mfxSend` schaltet jetzt auch seine LED. Die LED leuchtet nur für den gewählten Part, wie an der Taste. Ab API Version 24 schickt der Aufruf denselben MIDI-CC wie der Regler, der Drehgeber CUTOFF oder die Taste (IFX ON, MFX SEND), auf dem Kanal des Parts. `ifxType` geht wie der Drehgeber IFX über den Part-Edit und zeigt dasselbe Fenster; er hält bei der letzten Nummer der Firmware an (mit dem BLECHTRIBE-Satz 58 auf Hacktribe, 47 auf rot, 37 auf blau; die Grenze liest der Aufruf zur Laufzeit aus der Firmware, ein fx-Katalog mit mehr Typen hebt sie mit), statt umzuspringen. `sample` nimmt die ganze Slotnummer (0 bis 999) über den Part-Edit wie der Regler SAMPLE, aber nur einen Slot, bei dem der Regler stehen bleibt; einen leeren Slot schreibt der Aufruf nicht. Auf blau gibt es keine Samples, dort schreibt `sample` nichts. Jeder Wert geht außerdem so an die Klangerzeugung wie vom Bedienelement (im Emulator auf allen drei Firmwares geprüft, Befunde aus PR #401, [Messung](messungen/2026-11-09-plugin-part-dsp.md)): die Werte der Regler und CUTOFF danach an den Parametersetzer der Firmware wie der Regler, `sample`, `modType`, `ifxType` und `filterType` mit dem Auffrischen wie die Drehgeber und Filtertasten, `mfxSend` mit 127 statt 1 wie die Taste. `filterType` schaltet für den gewählten Part die LEDs LPF, HPF und BPF wie die Taste, `modType` zeigt das Fenster des Drehgebers MOD. Ab API Version 24 setzt `sample` auf einem Sample mit Slices auch den Slice wie der Regler SAMPLE, wenn er auf das Sample hochgedreht wird (im Emulator mit einem gestellten Slice-Sample geprüft, die Karte im Emulator hat keins). Lesbarer als `korg.parts[i].cutoff = x`. Ab API Version 24 geht der Aufruf auch auf der blauen Electribe über den Part-Edit der Regler, mit Fenster. Die Werte der Seiten LAST STEP bis SCALE MODE und GROOVE im Part-Menü (ab API Version 24) gehen über die Funktion dieser Seiten und landen wie nach dem Drehen im Menü. Im Emulator geprüft ([Messung](messungen/2026-11-06-plugin-api21-pattern-parts.md), [API 24](messungen/2026-11-08-plugin-api24-part-cc.md)), am Gerät nicht. Ab API Version 14 | wie `korg.led` |
| `korg.seq.setPatternValue(wert, x)` | setzt den Wert `wert` (Nummer in `PATTERN_FIELDS`, wie bei `korg.read.patternValue` mit `part` -1) des Patterns, das läuft, auf `x`, in seinen Bereich geklemmt, über die Funktion der Firmware, die auch das Pattern-Menü nimmt: im Block steht danach dasselbe Byte wie nach dem Drehen im Menü. MFX TYPE geht auf blau nur bis 31. `syncGroup` (Wert 12, ab API Version 21) hat keine Funktion der Firmware, die Firmware kennt es nicht; der Aufruf schreibt es in den Block wie die Seite SYNC GROUP. Ab API Version 24: `alternate1314` und `alternate1516` gehen über die Funktion der Seiten ALTERNATE; `mfxHold` drückt die Taste MFX HOLD, wenn der Wert sich ändert, LED, Effekt und Touchpad stehen danach wie nach der Taste (der Wert steht erst nach dem nächsten Bild im Block); `mfxPadX` und `mfxPadY` setzen den Wert des Touchpads und schicken den MIDI-CC wie das Touchpad auf dem globalen Kanal. Der Name des Patterns lässt sich nicht setzen. Im Emulator geprüft auf Hacktribe, rot und blau ([Messung](messungen/2026-11-03-plugin-api15.md)), am Gerät noch nicht. Die Tabelle je Firmware steht in `tools/patch/script_hooks.py` (`PATTERN_SETTERS`). Ab API Version 15 | wie `korg.led` |
| `korg.read.patternBytes(feld, pattern, offset)` | kopiert Bytes eines Patterns ins Feld, ein Byte je Platz: `pattern` -1 das im RAM, 0 bis 249 ein gespeichertes, ab `offset` (0 bis 16383) im Block von 16384 Byte, so viele wie das Feld Plätze hat und der Block reicht. Gibt die Zahl der Bytes zurück. Die Stellen stehen in `data/map/pattern.mjs`: Part `p` beginnt bei 2048 + 816 × `p`, sein Step `s` bei 48 + 12 × `s` darin. Ab API Version 14 | überall |
| `korg.read.patternName(feld, pattern)` | kopiert die 16 Bytes des Pattern-Namens (Offset 16 im Block) ins Feld, ein Byte je Platz, wie `korg.read.patternBytes(feld, pattern, 16)` mit höchstens 16 Plätzen; `pattern` -1 das im RAM, 0 bis 249 ein gespeichertes. Gibt die Zahl der Bytes zurück. Anzeigen mit `korg.display.chars`. Ab API Version 29 | überall |
| `korg.midi.cc(kanal, cc, wert)` | schickt einen Control Change über DIN und USB, über die Sendefunktion, die auch die Pads und Regler der Firmware nehmen: `kanal` 0 bis 15 für Kanal 1 bis 16, -1 der globale MIDI-Kanal (`korg.global.midiChannel`), `cc` und `wert` 0 bis 127. Der MIDI SEND FILTER gilt wie für die Nachrichten der Firmware: mit Short oder Short + Program geht nichts hinaus. Gibt 1 zurück, wenn gesendet, 0, wenn der Filter sie zurückhielt. Ab API Version 30 ([Messung](messungen/2026-11-11-plugin-api30-midi.md)) | wie `korg.led` |
| `korg.midi.noteOn(kanal, note, velocity)` | schickt Note On, `velocity` 1 bis 127; Kanal und Filter wie `korg.midi.cc`. Ab API Version 30 | wie `korg.led` |
| `korg.midi.noteOff(kanal, note)` | schickt Note Off mit Velocity 64, wie die Pads der Firmware; Kanal und Filter wie `korg.midi.cc`. Ab API Version 30 | wie `korg.led` |
| `korg.midi.program(kanal, program)` | schickt einen Program Change, `program` 0 bis 127; nur der MIDI SEND FILTER Short + Program hält ihn zurück, wie den der Firmware. Gibt 1 oder 0 zurück wie `korg.midi.cc`. Ab API Version 30 | wie `korg.led` |
| `korg.midi.hold(typ, an)` | hält einen Typ empfangener Nachrichten von der Firmware fern, solange `an` 1 ist: 0 Note Off, 1 Note On, 2 Poly Pressure, 3 Control Change, 4 Program Change, 5 Channel Pressure, 6 Pitch Bend. Die Plugins bekommen `midiIn` trotzdem. Wie `korg.keyHold` gilt der Typ als gehalten, solange irgendein laufendes Plugin ihn hält; ein Plugin, das endet, gibt seine frei. Ab API Version 30 | wie `korg.led` |
| `korg.audio.level(kanal)` | der Ausgangspegel einer Seite der Pegelanzeige, `kanal` 0 oder 1, 0 bis 254: derselbe geglättete Wert, den die unteren LEDs zeigen (alle 40 ms neu), auch wenn die Anzeige aus ist oder ein Plugin die LEDs hält. Welche Seite links ist, ist am Gerät noch nicht geprüft. Ab API Version 31 ([Messung](messungen/2026-11-11-plugin-api31-audio-level.md)) | überall |
| `korg.audio.capture(quelle)` | fordert den Ton einer Quelle an: `quelle` 1 bis 16 Part 1 bis 16, 17 bis 24 die Part-Paare 1+2 bis 15+16 (beide Seiten), -1 oder 0 hört auf. Die Firmware nimmt den Ton der Quelle am DSP ab und rechnet alle 50 ms ein Spektrum (FFT über 4096 Frames, 48 kHz), in ihrer eigenen Task, nicht im Plugin. Gibt den Status zurück (`AUDIO_STATUS` im Vertrag): 0 ok, 1 aus, 2 belegt, 3 warten (die ersten Daten kommen), 4 Lücke, 5 kein Speicher, 6 nicht auf dieser Electribe. Wer nicht mindestens alle 2 s `capture`, `spectrum` oder `wave` ruft, verliert die Aufnahme. Capture, FFT und Ring kommen aus Spettro von Luigi (GitHub reflectiveboi, PR #429). Nur Sampler (Hacktribe und rot), auf dem blauen Synth 6. Ab API Version 31 ([Messung](messungen/2026-11-12-plugin-api31-spektrum.md)) | überall |
| `korg.audio.spectrum(feld, bins, bereich)` | füllt die ersten `bins` (1 bis 128) Plätze des Felds mit dem Spektrum der Quelle, dB 0 bis 96 je Band, 96 ist ein Sinus mit voller Aussteuerung; `bereich` 0 voll 20 Hz bis 20 kHz, 1 Bass 20 Hz bis 2 kHz, logarithmisch geteilt, je Platz das lauteste der 128 Bänder darin. Gibt den Status wie `korg.audio.capture` zurück; das Feld wird nur bei 0 beschrieben. Ab API Version 31 | überall |
| `korg.audio.wave(feld)` | füllt das Feld mit den neuesten Frames der Quelle, -128 bis 127 (die oberen 8 Bit), höchstens 256, der letzte Platz am neuesten; bei einem Part-Paar der Mittelwert beider Seiten. Gibt den Status wie `korg.audio.capture` zurück. Ab API Version 31 | überall |
| `korg.file.read(feld, offset)` | liest die Datendatei des Plugins (siehe [Datendatei](#datendatei)) ab Byte `offset` (0 bis 4095) ins Feld, ein Byte je Platz, so viele wie das Feld Plätze hat und die Datei reicht. Gibt die Zahl der Bytes zurück (0 ohne Datei), -1 außerhalb des Hauptbildschirms und des Menüs BLECH, ohne lesbare Karte oder solange ein anderes Plugin noch auf das Schreiben seiner Datei wartet. Ab API Version 32 ([Messung](messungen/2026-11-11-plugin-api32-data-file.md)) | wie `korg.led` |
| `korg.file.write(feld, offset)` | schreibt das untere Byte jedes Platzes ab Byte `offset` in die Datendatei des Plugins, bis zum Ende des Felds oder der Grenze von 4096 Byte; eine Lücke hinter dem alten Ende liest sich als 0. Auf die Karte kommt die Datei wie bei `korg.store.save` erst im Hauptbildschirm oder im Menü BLECH und frühestens 2 s nach dem letzten Schreiben. Gibt die Zahl der Bytes zurück, -1 wie `korg.file.read`. Ab API Version 32 | wie `korg.led` |
| `korg.read.sampleName(feld, slot)` | liest den Namen des Samples in Slot `slot` (0 bis 997, die Nummer am Display minus 1, wie der Part-Wert `sample`) ins Feld, ein Zeichen je Platz, bis zum ersten Nullbyte, 16 Zeichen oder dem Ende des Felds. Gibt die Zahl der Zeichen zurück (0 für einen leeren Slot), -1 auf dem blauen Synth. Ab API Version 33 ([Messung](messungen/2026-11-11-plugin-api33-samples.md)) | überall |
| `korg.read.sampleInfo(slot, wert)` | ein Wert des Samples in Slot `slot` aus den Tabellen des Samplers: `wert` 0 Start, 1 Ende, 2 Loop (Rohwerte wie in der Sample-Datei, die Einheit ist nicht gemessen), 3 Tune (-128 bis 127), 4 Stereo (0 oder 1), 5 Länge der PCM-Daten in Byte, 6 One-Shot (0 oder 1), 7 Samplerate in Hz (`SAMPLE_INFO.fields` im Vertrag). 0 für einen leeren Slot, -1 auf dem blauen Synth. Ab API Version 33 | überall |
| `korg.pattern.write()` | speichert das laufende Pattern an seinen Platz in der Bank, wie EXIT + WRITE: drückt WRITE, und das Fenster der Firmware bekommt im nächsten Rahmen sein zweites WRITE. Gibt 1 zurück, wenn das Speichern läuft, 0 außerhalb des Hauptbildschirms oder solange ein Speichern noch auf sein Fenster wartet. Das Ereignis `write` kommt wie bei der Taste. Ab API Version 33 | wie `korg.led` |
| `korg.part.copy(pattern, von, nach)` | kopiert Part `von` (0 bis 15) aus Pattern `pattern` (0 bis 249) auf Part `nach` des laufenden Patterns, wie Part Util COPY PART: Klang, Steps und Motion, mit der Funktion der Firmware. Ist `pattern` das gewählte Pattern, kommt der Part aus dem Pattern im RAM (mit ungespeicherten Änderungen), sonst aus der Bank. Ab API Version 33 ([Messung](messungen/2026-10-30-vorschau-part-reinholen.md)) | wie `korg.led` |
| `korg.read.led(index)` | die Helligkeit, die die Firmware zuletzt an die LED `index` (0 bis 87, Nummern wie bei `korg.led`) geschickt hat, 0 bis 255, aus der Kopie des LED-Managers. LEDs, die ein Plugin mit `korg.led` setzt, stehen nicht darin. Ab API Version 34 ([Messung](messungen/2026-10-14-led-zustand-ram.md)) | überall |
| `korg.seq.writeSteps(feld, part, erster)` | schreibt Steps aus dem Feld in Part `part` des Patterns, das läuft, ab Step `erster` (0 bis 63): je 12 Plätze ein Step wie im Pattern (an, Gate, Velocity, Trigger, vier Notenplätze, vier Plätze, die die Laufzeit stehen lässt), so viele ganze Steps wie das Feld hat und bis Step 63. Jeder Wert wird geklemmt (an und Trigger 0 bis 1, Gate 0 bis 127, Velocity 1 bis 127, Noten 0 bis 128), das An-Byte kommt zuletzt. Gibt die Zahl der Steps zurück. Ab API Version 14 | wie `korg.led` |

**Steps schreiben** (`tools/patch/script_seq.s`, ab API Version 9): `korg.seq.*` schreibt in das Pattern im RAM,
das gerade läuft oder bearbeitet wird, genau wie das Würfeln mit SHIFT + PART ERASE
([Würfeln](messungen/2026-10-16-wuerfeln.md)): dieselben Bytes im Step, kein Umweg über die Bedienung. Der Sequencer spielt
einen geschriebenen Step beim nächsten Durchlauf, auch während er läuft (gemessen im Emulator, siehe unten). Das Pattern im RAM
weicht danach von seinem gespeicherten Platz ab und zählt wie nach einer Eingabe von Hand als ungespeichert: erst WRITE legt es
ab, ohne WRITE ist die Änderung nach dem Laden eines anderen Patterns weg. Der Flash und die Karte bleiben unberührt, und
SHIFT + EDIT< nimmt nichts zurück. Die Pads zeigen die Steps des gewählten Taktabschnitts; hat ein Plugin in
einem Rahmen Steps geschrieben, sagt die Laufzeit der Firmware am Ende des Rahmens einmal Bescheid, und die Pads zeichnen sich
neu (nur auf dem Hauptbildschirm, sonst beim nächsten Rahmen dort). Ein Step, der hinter der Länge des Patterns oder hinter
LAST STEP des Parts liegt, wird geschrieben, aber nicht gespielt. Die Noten sind MIDI-Noten wie beim Würfeln: 48 ist der
Grundton C, auf dem die Tonart des Patterns aufsetzt (`korg.current.key`).

```js
// TAP schreibt ein Arpeggio in den gewählten Part: Grundton, Terz, Quinte und Oktave
// in der Tonart des Patterns, auf jedem zweiten 16tel, so lang wie das Pattern.
const chord = [0, 4, 7, 12];
korg.onEvent("buttonPress", (key) => {
  if (key != korg.key.TAP) return;
  let part = korg.selectedPart;
  if (part > 15) return;
  korg.seq.clearPart(part);
  for (let step = 0; step < korg.current.length * 16; step += 2) {
    let note = 48 + korg.current.key + chord[(step / 2) % 4];
    korg.seq.setStep(part, step, note, step % 8 == 0 ? 110 : 80);
    korg.seq.setGate(part, step, 40);
  }
});
```

Ein Arpeggiator, der mitläuft, schreibt im Ereignis `step` den Schritt, der als nächster kommt. Ein Aufruf kostet wenig
(`setStep` 6, `setGate` 4, `clearPart` 30 Einheiten), ein ganzes Pattern von 64 Steps passt bequem in einen Rahmen.

**Patterns kopieren** (ab API Version 14): `korg.read.patternBytes` liest die Steps eines gespeicherten Patterns so, wie
sie im Block liegen, `korg.seq.writeSteps` schreibt sie in das Pattern, das läuft, und `korg.seq.setPartValue` zieht die
Werte des Parts nach. Für das Speichern gilt dasselbe wie oben: erst WRITE legt das Pattern ab. Im Emulator kopiert so ein
Plugin einen Part mit allen 64 Steps und seinen Werten, WRITE legt das Pattern ab und nach dem Wechsel auf ein anderes
Pattern und zurück ist es Byte für Byte gleich (`tools/emu/plugin_edit_cases.py`). Die Notenplätze tragen die MIDI-Note
plus 1, 0 ist leer. `setPartValue` schickt ab API Version 24 denselben MIDI-CC wie der Regler (gemessen im Emulator,
[Messung](messungen/2026-11-08-plugin-api24-part-cc.md)); ob es in die Motion Sequence aufgenommen wird, ist nicht gemessen.

```js
// TAP kopiert Part 1 von Pattern 5 in den gewählten Part: Steps und Werte.
const steps = new Array(768);
const fields = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 18];
korg.onEvent("buttonPress", (key) => {
  if (key != korg.key.TAP) return;
  const part = korg.read.part();
  if (part > 15) return;
  korg.read.patternBytes(steps, 4, 2048 + 48);
  korg.seq.writeSteps(steps, part, 0);
  for (let i = 0; i < 15; i = i + 1) korg.seq.setPartValue(part, fields[i], korg.read.patternValue(4, 0, fields[i]));
});
```

**Display auf dem Gerät** (`tools/patch/script_display.s`): Die Laufzeit hält ein
eigenes Bild von 1024 Byte (8 Seiten zu 128 Spalten, Bit 0 die oberste Zeile) und
zeichnet nur dort hinein, Koordinaten über dem Rand werden abgeschnitten, nie
umgebrochen. Zeichnen darf nur der Besitzer des Displays (die offene App, oder ein
Plugin, das es nahm): die Aufrufe jedes anderen Plugins tun nichts. Solange es einen
Besitzer gibt, kopiert der Rahmenhaken das Bild in jedem Rahmen über das Display RAM
der Firmware (`0xC031B310`, nach dem Zeichnen ihrer Widgets), aber nur, solange der
Hauptbildschirm offen ist. Ohne Besitzer rührt die Laufzeit das Display nicht an.
Menüs und Fenster zeigt die Firmware wie gewohnt, ein Plugin sieht sie nicht. Die
Schrift ist eine eigene 5 mal 7 Schrift mit 6 Pixel Zeichenabstand
(`data/script/font.mjs`), dieselbe Tabelle in Browser und Laufzeit; die Ausgabe
ist Pixel für Pixel gleich dem Browsermodell (`src/script/display.mjs`, 70
Fälle in `tools/patch/test_script_display.py`). Texte sind höchstens 31 Zeichen
(ein Textplatz), Zahlen werden dezimal gezeichnet.

**Bilder aus Feldern** (`korg.display.bitmap`): ein Platz des Felds hält die 8 Pixel einer Spalte,
das niedrigste Bit ist das oberste Pixel (nur die unteren 8 Bit zählen); das ist der Aufbau des
Display RAMs und der gängigen Bitmaps für OLED-Anzeigen. Ein Streifen sind `breite` Plätze, von
links nach rechts, die Streifen folgen von oben nach unten. Die Höhe ist 8 mal die Zahl ganzer
Streifen (Länge des Felds geteilt durch `breite`, Rest ungelesen); die Breite geht bis 128. Es werden
nur gesetzte Pixel gezeichnet, nichts gelöscht, `clearRect` davor löscht. `y` muss kein Vielfaches
von 8 sein, dann teilt jeder Platz sich auf zwei Seiten des Display RAMs. Beispiel, ein Smiley von
8 mal 8 Pixeln:

    const gesicht = [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C];
    korg.display.bitmap(gesicht, 10, 5, 8);

Als Feld kommt nur der Name eines globalen Felds in Frage (`const bild = [...]` oder
`new Array(n)`). Der Übersetzer reicht es als ein Wert weiter (erster Platz in den unteren 16 Bit,
Länge in den oberen 16) und prüft, wenn `breite` eine feste Zahl ist, dass mindestens ein Streifen
im Feld liegt; die VM prüft bei jedem Aufruf, dass das Feld im Variablenbereich liegt (sonst
`BAD_VAR`). Nullen im Feldliteral kosten keinen Code, weil die Laufzeit jeden Variablenplatz beim
Laden löscht. Ein Aufruf kostet 14 Einheiten und 3 für jeden Platz des Felds (ein Bild von 41 mal
56 Pixeln mit 287 Plätzen also 875). Der Wert ist an den ARM Befehlszahlen gemessen: 63 Befehle für den
Aufruf, höchstens 28 für einen gesetzten Platz, bei Bildern von einem Platz Breite rund 20 mehr für
jeden Streifen, zu 10 Befehlen je Einheit (`tools/patch/test_script_display.py` prüft die Zahlen).
Leere Plätze und Plätze außerhalb des Displays kosten weniger, als berechnet wird.
`textNumber` kostet wie `text` die Obergrenze von 250: der echte Aufwand liegt darüber (rund 4900
Befehle für 5 Zeichen und 3 Ziffern), die 5 ms des Rahmens bleiben die Grenze.

**Berührung mit Lage:** Das Panel schickt `05 xh xl yh yl`; der Eingangsfilter macht daraus
`x = xh * 256 + xl` und `y = yh * 256 + yl`, ohne zu begrenzen (im Emulator mit der Firmware
gemessen: `01 23 03 FF` ergibt 291 und 1023, `FF FF FF FE` ergibt 65535 und 65534). Die Taste 34
(`0x22`) kommt für sich, ohne Lage, und löst kein `touch` aus. Der Filter merkt sich je Berührung, ob die
erste Lage schon da war: Aufsetzen (Taste 34 gedrückt) setzt es zurück, die erste Lage danach ist
`first` = 1, auch ohne vorherigen Tastendruck, Loslassen setzt es zurück. Läuft der Ring voll, geht
auch ein erstes `touch` verloren. Wie das Pad zum Display liegt, ist nicht gemessen: der Editor und
der Emulator senden 0 bis 1023 über das ganze Pad, `y` nach oben; Blechy rechnet angenommen
`x / 8` zur Display-Spalte. Am Gerät offen.

**Fehlermeldung am Display:** Schaltet ein Fehler das Plugin ab, das das Display
besitzt (die offene App), ersetzt die Laufzeit das Bild durch drei Zeilen: den
Plugin-Namen, `Line` mit der Quellzeile und den Namen des Fehlers (`DIV_ZERO`). Der
Fehler jedes anderen Plugins steht im Menü BLECH auf seiner Seite (`DIV_ZERO L3`),
das Display bleibt unberührt. Die Firmware bleibt bedienbar, andere Plugins laufen
weiter.

Im Rumpf darf noch nichts ausgegeben werden: LEDs überschreibt die Firmware beim
Start, und ein Display gibt es dort nicht. Ausgaben gehören in `ready`, `frame`, `open`
oder die Handler der Eingaben.

LED Aufträge werden im Hostmodell `src/script/led.mjs` gesammelt. Die letzte
Anforderung je LED zählt, auch der Wert null ist eine ausdrückliche
Anforderung. Gleiche Aufträge werden innerhalb desselben Rahmens
zusammengefasst. Je Rahmen werden höchstens 16 Pakete angenommen, auch bei
mehreren Aufrufen des Sendeschritts. Der Rahmenbesitzer prüft vor jedem
Paket sein verbleibendes Zeitbudget. Ohne Budget, bei voller Warteschlange
oder bei abgelehntem Transport bleibt der Auftrag ausstehend.

Ein Paket braucht fünf Byte. Nach seiner Annahme müssen noch mindestens
256 Byte in der Firmwarewarteschlange frei bleiben. Die Begrenzung ist eine
hergeleitete Vorgabe: 16 Pakete bei 25 Hz ergeben maximal 400 Plugin-Pakete
je Sekunde, kein am Gerät gemessener Durchsatz. Freier Platz allein beweist
keine Annahme; der Transport muss sie atomar bestätigen. Es gibt keine
Warteschleife auf freien Platz.

Die Firmware darf LEDs weiter ändern. Der Anfang eines neuen Rahmens
verwirft deshalb das Wissen über die zuletzt angenommene Ausgabe, ohne
automatisch alte Anforderungen erneut zu senden. Ein Plugin, das einen Wert
in jedem Rahmen haben möchte, fordert ihn in `frame` erneut an. Eine feste
Übernahme der RGB LEDs und das Sperren von Firmwarewegen sind damit nicht
vorausgesetzt. Das eigenständige Hostmodell wird ausdrücklich über
`ScriptRuntime` und dessen `api["korg.led"]` verbunden; es gibt keine
versteckte globale Warteschlange.

### Eingaben fernhalten (API 19)

Ein Plugin nimmt der Firmware Tasten, Pads und Regler weg, damit sie nur das Plugin bekommt: `korg.keyMask` und
`korg.keyHold` für Tasten, `korg.padHold` für die Pads, `korg.knobHold` für Regler. Jedes Plugin hat dafür seine eigene
Maske, die Aufrufe ändern nur die des aufrufenden Plugins. Der Eingangsfilter der Laufzeit gibt jede Eingabe an alle
laufenden Plugins, die einen Handler dafür haben, und entscheidet danach, ob sie die Firmware sieht.

- **Zwei Plugins, dieselbe Taste:** beide bekommen die Taste, die Firmware bekommt sie nicht, solange **irgendein**
  laufendes Plugin sie hält. Lässt eines los, hält das andere weiter. Für Pads und Regler gilt dasselbe.
- **Ein Plugin hört auf** (abgeschaltet, mit Fehler beendet, entfernt): seine Masken zählen ab dem Ende des nächsten Rahmens
  nicht mehr. Was nur dieses Plugin gehalten hat, geht an die Firmware zurück.
- **Eine App schließt:** sie gibt die Pads aller Plugins zurück (wie bisher); Tasten und Regler bleiben gehalten.
- **Das Loslassen folgt dem Anschlag:** ein Anschlag, der der Firmware vorenthalten wurde, hält auch sein Loslassen von ihr
  fern, auch wenn der Halt dazwischen endet; ein Anschlag, der durchging, lässt sein Loslassen durch.
- **EXIT** lässt sich nicht halten (`korg.keyHold` und `korg.keyMask` beenden das Plugin mit einem Fehler), Apps bleiben
  schließbar.
- **Gemessen:** im Emulator auf Hacktribe, rot und blau mit zwei Plugins (`tools/emu/plugin_api19_cases.py`); am Gerät nicht.
  Das Beispiel-Plugin Gate Hold läuft unverändert weiter.

### Bedienen wie ein Finger (API 25)

`korg.keyDown` und `korg.keyUp`, `korg.padDown` und `korg.padUp`, `korg.encoder` und `korg.touch` geben der Firmware die
Nachrichten, die das Panel selbst schickt, über seine Warteschlange. Was am Gerät mit Taste, Pad, Encoder oder Touchpad geht,
geht damit auch aus einem Plugin.

- **An allem vorbei:** eine Markierung lässt diese Nachrichten an Umbelegung, `korg.keyHold`, `korg.keyMask`,
  `korg.passKeys`, `korg.padHold`, `korg.touchLockX`, `korg.touchLockY`, der offenen App und den Tastenkürzeln von BLECHTRIBE vorbei. Kein Plugin
  bekommt sie als Ereignis, auch das aufrufende nicht. Ein Plugin, das die Pads mit `korg.padHold` hält und selbst
  `korg.padDown` ruft, spielt also seine eigenen Anschläge, die Anschläge des Panels bleiben bei ihm.
- **Drücken und Loslassen gehören zusammen:** ein zweites Drücken derselben Taste oder desselben Pads sendet nichts, ein
  Loslassen ohne Drücken auch nicht. Hört das Plugin auf (abgeschaltet, Fehler, entfernt), lässt die Laufzeit am Ende des
  Frames alles los, was es noch drückt, auch den Finger auf dem Touchpad. Es gilt das Plugin, das zuletzt etwas gedrückt hat.
- **Eine volle Warteschlange** verwirft die Nachricht; das Drücken zählt dann nicht.
- **Einen Frame später:** die Nachricht geht im Rahmen des Plugins raus und kommt einen Frame nach einer Nachricht des
  Panels zur selben Zeit an.
- **EXIT** geht seit API 25 mit `korg.keyDown` und `korg.pressKey`: eine offene App schließt erst, dann bekommt die
  Firmware EXIT. `korg.keyHold`, `korg.keyMask` und `korg.remapKey` lehnen EXIT weiter ab.
- **Gemessen:** im Emulator auf Hacktribe, rot und blau, jedes Mal gegen dieselbe Bedienung über das Panel
  ([Messung](messungen/2026-11-08-plugin-api25-panel-calls.md)); am Gerät nicht.

### Namen für Tasten und LEDs

Statt `key == 11` oder `korg.led(20, 255)` schreibt man, was gemeint ist:

```js
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) korg.led(korg.led.TAP, 255);
  if (key == korg.key.PART_LEFT) korg.led(korg.led.PAD_1_RED, 255);
});
```

`korg.key.NAME` ist der Tastencode, den `buttonPress` und `buttonRelease` als `key`
liefern. `korg.led.NAME` ist die LED Nummer für das erste Argument von `korg.led`.
Die Namen sind Konstanten der Sprache: der Compiler schreibt die Nummer hin, wo der
Name steht. Ein Block mit Namen ist deshalb Byte für Byte derselbe wie einer mit
Nummern (`test/script-names.test.mjs` prüft das an allen Beispiel-Plugins), am Gerät
und in der Blockgröße ändert sich nichts, und die Blockversion bleibt. Nummern bleiben
erlaubt. Ein Name lässt sich wie eine Zahl in `const` und in Ausdrücken benutzen
(`const BASE = korg.led.PAD_1_RED;`, `BASE + 2`). Ein Name, den es nicht gibt, ist ein
Fehler beim Übersetzen und nennt ähnliche Namen. Dass `korg.led` zugleich die Funktion
ist, stört nicht: mit Klammern ist es der Aufruf, mit `.NAME` die Konstante.

Der Name ist die Beschriftung am Gerät in GROSSBUCHSTABEN mit Unterstrich: `GATE ARP`
ist `GATE_ARP`, `◄ Part` und `Part ►` sind `PART_LEFT` und `PART_RIGHT`, `◄ Edit` und
`Edit ►` sind `EDIT_LEFT` und `EDIT_RIGHT`, die Tasten `1` bis `4` sind `BAR_1` bis
`BAR_4`. Eine zweite LED derselben Taste trägt ihre Farbe im Namen (`PLAY_BLUE`,
`BAR_1_BLUE`), ebenso die Pads: `PAD_1_RED`, `PAD_1_BLUE` bis `PAD_16_BLUE`. Die blaue Pad
LED zeigt den gewählten Part. Die roten Pad LEDs liegen 2 auseinander, `PAD_1_RED + 2`
ist `PAD_2_RED`. Die Tabellen entstehen aus `data/panel.mjs` (`data/script/names.mjs`);
ein neues Bedienelement dort bekommt seinen Namen von selbst, die LED Nummern prüft das
Laden des Moduls gegen den Bereich von `korg.led`. Woher die Nummern kommen
(gemessen, von Freetribe hergeleitet), steht in `data/panel.mjs`.

**Tasten** (`korg.key`):

| Name | Nummer | Taste |
|---|---|---|
| `korg.key.REC` | 0 | REC |
| `korg.key.STOP` | 1 | STOP |
| `korg.key.PLAY` | 2 | PLAY |
| `korg.key.TAP` | 3 | TAP |
| `korg.key.GATE_ARP` | 4 | GATE ARP |
| `korg.key.TOUCH_SCALE` | 5 | TOUCH SCALE |
| `korg.key.MASTER_FX` | 6 | MASTER FX |
| `korg.key.MFX_HOLD` | 7 | MFX HOLD |
| `korg.key.EDIT_LEFT` | 8 | ◄ Edit |
| `korg.key.MENU` | 9 | MENU |
| `korg.key.SHIFT` | 10 | SHIFT |
| `korg.key.PART_LEFT` | 11 | ◄ Part |
| `korg.key.EDIT_RIGHT` | 12 | Edit ► |
| `korg.key.EXIT` | 13 | EXIT |
| `korg.key.WRITE` | 14 | WRITE |
| `korg.key.PART_RIGHT` | 15 | Part ► |
| `korg.key.PART_MUTE` | 16 | PART MUTE |
| `korg.key.PART_ERASE` | 17 | PART ERASE |
| `korg.key.LPF` | 18 | LPF |
| `korg.key.TRIGGER` | 19 | TRIGGER |
| `korg.key.HPF` | 20 | HPF |
| `korg.key.SEQUENCER` | 21 | SEQUENCER |
| `korg.key.BPF` | 22 | BPF |
| `korg.key.KEYBOARD` | 23 | KEYBOARD |
| `korg.key.CHORD` | 24 | CHORD |
| `korg.key.STEP_JUMP` | 25 | STEP JUMP |
| `korg.key.MFX_SEND` | 26 | MFX SEND |
| `korg.key.PATTERN_SET` | 27 | PATTERN SET |
| `korg.key.BAR_1` | 28 | 1 (Takt-Taste) |
| `korg.key.BAR_2` | 29 | 2 (Takt-Taste) |
| `korg.key.BAR_3` | 30 | 3 (Takt-Taste) |
| `korg.key.BAR_4` | 31 | 4 (Takt-Taste) |
| `korg.key.AMP_EG` | 32 | AMP EG |
| `korg.key.IFX_ON` | 33 | IFX ON |
| `korg.key.TOUCHPAD` | 34 | Touchpad berührt |

Die Tasten `1` bis `4` und `TOUCHPAD` (das Berühren des Touchpads, mit `touch` für die
Lage) kommen wie jede Taste als `buttonPress`. Ein Drehgeber, ein Regler oder ein Pad
sendet kein `buttonPress`, sondern `encoder`, `knob` und `pad` mit ihrem `index`.

**Regler** (`index` bei `knob`, `korg.read.knob(index)`, `korg.knobs.NAME`):

| Index | Name | Regler |
|---|---|---|
| 0 | `korg.knobs.LEVEL` | LEVEL |
| 1 | `korg.knobs.PAN` | PAN |
| 2 | `korg.knobs.PITCH` | PITCH / GLIDE |
| 3 | `korg.knobs.RESONANCE` | RESONANCE |
| 4 | `korg.knobs.EG_INT` | EG INT. |
| 5 | `korg.knobs.MOD_DEPTH` | MOD. DEPTH |
| 6 | `korg.knobs.ATTACK` | ATTACK |
| 7 | `korg.knobs.IFX_EDIT` | IFX EDIT |
| 8 | `korg.knobs.DECAY` | DECAY / RELEASE |
| 9 | `korg.knobs.OSC_EDIT` | OSC EDIT |
| 10 | `korg.knobs.MOD_SPEED` | MOD. SPEED |

Die Indizes 11 bis 19 gehören zu keinem Regler, sie bleiben 0. CUTOFF ist kein Regler, sondern ein Drehgeber.

**Drehgeber** (`index` bei `encoder`):

| Index | Drehgeber |
|---|---|
| 0 | VALUE / PATTERN (das große Rad) |
| 1 | SAMPLE / OSC |
| 2 | CUTOFF |
| 3 | MOD. TYPE |
| 4 | IFX TYPE |

**Pads** (`index` bei `pad`): 0 bis 15 sind die Pads 1 bis 16.

Die Nummern kommen aus `data/panel.mjs` (dort gemessen am Panel).

**LEDs** (`korg.led`):

| Name | Nummer | LED |
|---|---|---|
| `korg.led.REC` | 18 | REC |
| `korg.led.STOP` | 19 | STOP |
| `korg.led.PLAY` | 9 | PLAY |
| `korg.led.PLAY_BLUE` | 21 | PLAY, blaue LED |
| `korg.led.TAP` | 20 | TAP |
| `korg.led.GATE_ARP` | 26 | GATE ARP |
| `korg.led.TOUCH_SCALE` | 27 | TOUCH SCALE |
| `korg.led.MASTER_FX` | 28 | MASTER FX |
| `korg.led.MFX_HOLD` | 29 | MFX HOLD |
| `korg.led.EDIT_LEFT` | 5 | ◄ Edit |
| `korg.led.MENU` | 7 | MENU |
| `korg.led.SHIFT` | 10 | SHIFT |
| `korg.led.PART_LEFT` | 30 | ◄ Part |
| `korg.led.EDIT_RIGHT` | 6 | Edit ► |
| `korg.led.EXIT` | 8 | EXIT |
| `korg.led.WRITE` | 11 | WRITE |
| `korg.led.PART_RIGHT` | 31 | Part ► |
| `korg.led.PART_MUTE` | 32 | PART MUTE |
| `korg.led.PART_ERASE` | 33 | PART ERASE |
| `korg.led.LPF` | 12 | LPF |
| `korg.led.TRIGGER` | 34 | TRIGGER |
| `korg.led.HPF` | 13 | HPF |
| `korg.led.SEQUENCER` | 35 | SEQUENCER |
| `korg.led.BPF` | 14 | BPF |
| `korg.led.KEYBOARD` | 36 | KEYBOARD |
| `korg.led.CHORD` | 37 | CHORD |
| `korg.led.STEP_JUMP` | 38 | STEP JUMP |
| `korg.led.MFX_SEND` | 15 | MFX SEND |
| `korg.led.PATTERN_SET` | 39 | PATTERN SET |
| `korg.led.BAR_1` | 40 | 1 (Takt-Taste) |
| `korg.led.BAR_1_BLUE` | 22 | Taste 1, blaue LED |
| `korg.led.BAR_2` | 41 | 2 (Takt-Taste) |
| `korg.led.BAR_2_BLUE` | 23 | Taste 2, blaue LED |
| `korg.led.BAR_3` | 42 | 3 (Takt-Taste) |
| `korg.led.BAR_3_BLUE` | 24 | Taste 3, blaue LED |
| `korg.led.BAR_4` | 43 | 4 (Takt-Taste) |
| `korg.led.BAR_4_BLUE` | 25 | Taste 4, blaue LED |
| `korg.led.AMP_EG` | 16 | AMP EG |
| `korg.led.IFX_ON` | 17 | IFX ON |
| `korg.led.VALUE_PATTERN` | 0 | VALUE / PATTERN |
| `korg.led.SAMPLE_OSC` | 1 | SAMPLE / OSC |
| `korg.led.CUTOFF` | 2 | CUTOFF |
| `korg.led.MOD_TYPE` | 3 | MOD. TYPE |
| `korg.led.IFX_TYPE` | 4 | IFX TYPE |
| `korg.led.PAD_n_RED` | 44 + 2 (n - 1) | Pad n, rote LED (n = 1 bis 16) |
| `korg.led.PAD_n_BLUE` | 45 + 2 (n - 1) | Pad n, blaue LED, zeigt den gewählten Part (n = 1 bis 16) |

Der Editor zeigt dieselbe Liste unter dem Code („Namen der Tasten und LEDs“, mit
Filter, ein Klick fügt den Namen am Cursor ein). Steht der Cursor in einer Nummer, die
nach Taste oder LED aussieht (`key == 11`, `korg.led(20, …)`), sagt eine Zeile unter
dem Code, welche Taste oder LED das ist, und nach `korg.key.` oder `korg.led.` bietet
die Vervollständigung des Editors alle Namen an (siehe „Die Seite Plugins im Editor“).

### Veraltete Aufrufe (API 35)

Diese Aufrufe und Eigenschaften ersetzt ein neuerer. Sie laufen weiter wie bisher, der Block bleibt derselbe. Der Editor
markiert sie als Warnung, nennt den Ersatz in der Fehlerliste und im Tooltip. Entfernt werden sie frühestens in einer späteren
Version, das steht dann in den Release Notes. Die Liste steht in `data/script/contract.mjs` (`DEPRECATED`).

| Veraltet | Ersatz | Ersatz ab API |
|---|---|---|
| `korg.read.chainMode()` | `korg.global.chainMode` | 20 |
| `korg.chainMode` | `korg.global.chainMode` | 20 |
| `korg.current.…` (alle Werte des Patterns) | `korg.pattern.current.…` | 21 |

Wer ein Plugin auch für eine Firmware vor API 21 schreibt, bleibt bei der alten Form; die Warnung hält es nicht auf.

### Grenzen

| | Grenze |
|---|---|
| Variablenbereich eines Plugins | bis 65536 Plätze (je 4 Byte), so groß wie angelegt |
| Blöcke, Variablen und Plugin-Einträge zusammen | 128 KiB |
| Plugin-Zahl | keine feste Grenze, solange der gemeinsame Speicher reicht |
| Ein Feld | 1 bis 65535 Plätze |
| Verschiedene Texte | 64, je 31 Zeichen |
| Verschiedene Zahlen über 255 oder negativ | 256 |
| Code | 16 KiB |
| Stapel (Ausdrücke) | 32 Werte |
| Aufrufe ineinander | 8 |
| Rechenbudget je Lauf | 20000 Kosteneinheiten |

Die Laufzeit rechnet je Plugin die auf 4 Byte ausgerichtete Blockgröße
`totalSize`, vier Byte je Variablenplatz und einen Plugin-Eintrag zusammen.
Der Eintrag braucht derzeit 292 Byte: 48 Byte feste Felder einschließlich
des `ready` Merkers, je vier Byte für die höchsten Kosten und Zeiten der
22 Ereignisse (der Rumpf `start` zählt mit) und 68 Byte für die dauerhaften
Werte (Maske und 16 Plätze). Sein Aufbau steht im gemeinsamen
Vertrag `SCRIPT_ENTRY`, aus dem auch die ARM Konstanten entstehen. Stapel,
Prüfpuffer, globaler Status und Ereignisring liegen außerhalb des Pools.
Abgeschaltete Plugins behalten ihren Speicher und Fehlerstatus.

Reicht der gemeinsame Speicher nicht, lehnt die Laufzeit den Block vor dem
Anlegen der Variablen und vor dem Rumpf ab („Plugin-Budget aller Plugins reicht
nicht“, Code `POOL_BUDGET`). Dabei bleiben der belegte Speicher und die
geladenen Plugins unverändert. `ScriptRuntime.status().memory` nennt die
belegten Bytes und das Budget. Der Quelltextanhang einer `.blech` liegt hinter
`totalSize`, wird auf dem Gerät nicht geladen und kostet keinen Poolplatz.

Der Compiler prüft mit `slotsAvailable` vorab nur die Variablenzahl an ihrer
Deklaration. Sein Standard von 32768 Plätzen ist aus 128 KiB geteilt durch
vier hergeleitet; Block und Eintrag brauchen zusätzlich Platz. Ein erfolgreich
übersetzter Block kann deshalb beim Laden noch `POOL_BUDGET` auslösen.
Ein ausdrücklich kleineres `varSlots` der Referenzlaufzeit bleibt eine
zusätzliche Grenze mit `VARS_BUDGET`, unabhängig vom gemeinsamen Pool.
Die 65536 Plätze und 65535 Feldplätze bleiben Formatgrenzen für Prüfer und VM,
kein Versprechen, dass so große Bereiche in den Gerätpool passen.

Der Pool liegt im freien FF-Bereich des Abbilds, von `0xC01D7000` bis
`0xC01F7000` (131072 Byte). Offline an den eigenen Abbildern gemessen: der
Bereich ist dort FF. Das belegt eine freie Abbildfläche, keine dauerhafte
Nichtnutzung am Gerät ([Messung](messungen/2026-10-14-skript-haken.md)). Die
Speicherbilanz des Bereichs steht in der
[Recherche zur Laufzeit](hintergrund/skript-laufzeit.md), Abschnitt 3. Das
gemeinsame 128 KiB Budget ersetzt ein älteres Modell mit 64 KiB nur für
Variablen.

### Format 2 und die Kosten

Blockformat 2 ist das einzige Format; ein Block aus Format 1 (nie
ausgeliefert) wird mit der Versionsmeldung abgelehnt. Gegenüber Format 1 sind
die Operanden von `LOAD`, `STORE`, `ALOAD` und `ASTORE` (Platz, Feldanfang,
Feldlänge) 16 Bit breit, der Kopf wächst von 48 auf 52 Byte und nennt die
Variablenzahl mit 32 Bit (ein voller Bereich von 65536 Plätzen passt nicht in
16 Bit). Die Länge eines Felds ist ein 16-Bit-Operand und kann daher höchstens
65535 sein; Feldanfang plus Länge muss in den Bereich des Plugins passen, und
jeder Zugriff wird wie vorher gegen die Länge geprüft (Prüfer und VM,
Fehlercodes unverändert `BAD_VAR` und `BOUNDS`).

Mehrkosten, hergeleitet und nicht gemessen:
ein 16-Bit-Operand liegt hinter dem Opcode auf einer ungeraden Adresse, ein
`ldrh` geht dort nicht; die VM liest zwei Bytes und fügt sie zusammen, das
sind 2 Befehle mehr je Operand. `LOAD` und `STORE` kosten damit 11 statt 9
Befehle (Dispatch inklusive, Messwert 9 aus der [Recherche](hintergrund/skript-laufzeit.md), Abschnitt 2.3),
`ALOAD` und `ASTORE` mit zwei Operanden 4 mehr. Die Kosteneinheiten im
Vertrag bleiben, sie sind ohnehin Schätzungen. Beim Lauf von Snake (300
Rahmen mit Tastendrücken in der JS-VM, Operationen nach Art gezählt, mit den
Messwerten der Recherche gewichtet) sind 30,4 % der Operationen `LOAD` oder
`STORE` und 6,2 % `ALOAD` oder `ASTORE`: von 9,25 auf 10,11 Befehle je
Operation, rund 9 %. Beim Klicker rund 6 %. Der Block wächst: Snake von 952 auf
1080 Byte (davon 4 im Kopf), Klicker von 220 auf 232. Wird der Aufschlag auf
dem Gerät zu teuer (die Zeit je Operation ist dort noch nicht gemessen), ist eine Kurzform mit
8-Bit-Platz für die ersten 256 Variablen ein Zusatz-Opcode und kein
Formatbruch.

### Wenn etwas schiefgeht

Der Block wird vor dem Laden geprüft: Sprungziele, Konstanten, Variablen,
Aufrufe, Stapelhöhe, Aufruftiefe und die erlaubten Funktionen je Ereignis.
Zur Laufzeit beendet die VM ein Plugin bei einer Endlosschleife
(Rechenbudget oder Zeit), einem Feldindex außerhalb, Division durch null und
einem Argument außerhalb des Bereichs. Das Plugin ist dann aus, die Meldung
nennt Plugin, Zeile und Art des Fehlers, andere Plugins laufen weiter.
Die Fehlercodes stehen in `data/script/contract.mjs`.

## Karte und Dateiformat

### Dateien für die Karte

Plugins kommen nur über die SD-Karte aufs Gerät, nie in die VSB. Der Ordner ist
`KORG/blechtribe/Plugin/` (Einzahl, nicht "Plugins"; bei der roten und der blauen Electribe derselbe), den die
Firmware nicht selbst anlegt. Mit verbundenem Gerät legt die Seite Plugins
sie auch über USB dorthin (Knopf "Aufs Gerät", BLECHTRIBE-SysEx-Befehl `0x67` PLUGIN BEGIN, Name aus Buchstaben,
Ziffern, `_` und `-`, höchstens 16 Zeichen); danach am Gerät BLECH, PLUGINS.

- `e2sPlugin.all` ist die Sammeldatei, die das Gerät beim Start liest. Kopf, 16
  Byte, little endian: Kennung `GSAL`, Dateiversion 1 (u16), Anzahl Blöcke
  (u16), Gesamtgröße (u32), CRC-32 über alles ab Byte 16 (u32). Danach die
  Blöcke im Format 2 unverändert hintereinander (jeder hat seine eigene Größe
  und CRC; eine Blockgröße ist durch 4 teilbar, es gibt kein Auffüllen).
  Ein Block darf höchstens 32752 Byte haben (Puffer des Laders).
- `<name>.blech` ist ein Block mit angehängter Beschreibung und angehängtem
  Quelltext: nach dem Block die Kennung `GDSC`, die Länge (u32) und die
  Beschreibung in ASCII, Zeilen von höchstens 20 Zeichen mit `\n` am Ende
  (höchstens 2047 Byte); dann die Kennung `GSRC`, die Länge (u32) und der Text
  in UTF-8. Die Beschreibung sind die `//`-Zeilen ganz oben im Plugin-Code
  (eine leere `//`-Zeile beginnt einen neuen Absatz, Umlaute werden zu ae, oe,
  ue, ss); ohne solche Zeilen fehlt der Anhang `GDSC`. Das Gerät lädt den
  Block und zeigt die Beschreibung auf der Seite DESCRIPTION des Plugins, der Editor liest den
  Quelltext, um das Plugin wieder zu öffnen.

Der Lader läuft einmal beim Start direkt nach dem Laden der `e2sSample.all`
(Einhängestelle `0xC0038D68`, Kette `start`). Mit EXIT beim Einschalten, ohne
Karte oder ohne Datei tut er nichts und die Electribe startet wie ohne ihn.
Eine Datei mit falschem Kopf, falscher Prüfsumme oder abgeschnittenem Inhalt
wird ganz abgelehnt. Ein einzelner Block, der nicht lädt (Prüfsumme, Budget,
ungültiger Code), wird übersprungen, die übrigen laufen. Danach läuft der Rumpf
(`start`) jedes geladenen Plugins, dann ist die Laufzeit scharf; `ready` kommt
mit dem ersten Rahmen nach dem Hauptbildschirm. Was der Lader gemacht hat, steht
im Kontrollblock der Laufzeit (`cardStatus`, `cardLoaded`, `cardRejected`,
`cardFirstError` bei 164 bis 176 Byte hinter dem Laufzeitanfang).

Dateien schreibt der Editor (`src/script/archive.mjs`: `packAll`, `parseAll`,
`packBlech`, `parseBlech`). Ein Plugin, das nur auf der Karte liegt, läuft erst
beim nächsten Start; in MANAGE PLUGINS am Gerät (siehe unten) steht es als OFF in der Liste und läuft, sobald man es dort einschaltet.

**Das Kennzeichen "geprobt".** Der Kopf eines Blocks hat ein Feld `flags` (Byte 34,
u16). Bit 0 heißt PROBED: der Editor setzt es beim Export, nachdem er den Text
geprobt hat (`markProbed` in `src/script/blob.mjs`, die Prüfsumme wird neu
gerechnet). Alle anderen Bits sind verboten, Browser und Gerät lehnen den Block
dann ab. Ein Block ohne das Bit ist fremd: das Gerät lädt ihn, startet ihn aber
erst, wenn am Gerät einmal zugestimmt wurde (siehe "Das Menü BLECH am Gerät"). Das Bit ist
ein Hinweis, kein Schutz, jeder kann es setzen.

**Bilddateien** (`korg.file.frame`): `KORG/blechtribe/Gif/GIF00.E2G` bis `GIF99.E2G`, little endian:
Kennung `GGIF`, Version 1 (u16), Zahl der Bilder (u16), dann je Bild die Dauer in ms (u16), zwei Nullbytes und 1024
Byte Displayspeicher (Byte `(y / 8) * 128 + x`, Bit `y % 8`). `tools/gif/gif2e2g.py` macht so eine Datei aus einem GIF
(Pillow), aus mehreren Bildern (etwa BMPs) eine Datei mit einem Bild je Eingabe in der genannten Reihenfolge, `src/script/gif.mjs` liest sie im Browser. Ein Aufruf öffnet die Datei, springt zum Bild, liest es und schließt
sie wieder, über die FatFs-Funktionen der Firmware (auch `f_lseek`, `0xC009E404`, in Blau `0xC008AF5C`) und mit dem
Dateiobjekt des Kartenladers. Er liest nur bei offenem Hauptbildschirm. Wie lange das
Lesen von 1 KiB am Gerät dauert, ist nicht gemessen; die 5 ms des Rahmens bleiben die Grenze.

### Dauerhafte Werte

Jedes Plugin hat 16 ganze Zahlen als dauerhafte Plätze, getrennt nach dem
Plugin-Namen. `korg.store.get` liest einen Platz (im Rumpf, vor allen
Handlern, sind die gespeicherten Werte schon da), `korg.store.set` ändert ihn im
RAM. Auf die Karte kommt nur, was `korg.store.save()` anfordert; die Laufzeit
schreibt nie von selbst, auch nicht beim Ausschalten. Ein Plugin, das die
Funktionen nutzt, trägt API Version 2 im Block; ein Plugin ohne sie bleibt bei
Version 1.

Die Werte liegen in `KORG/blechtribe/Plugin/store.a.bin` und `store.b.bin`. Sie
wechseln sich ab: jeder Schreibvorgang bringt die nächste Generation in die andere
Datei, beim Start gilt die neuere gültige, eine beschädigte oder fehlende Datei
fällt auf die andere zurück, ohne Datei gelten die Vorgaben von `get`. Aufbau (little
endian, `STORE` im Vertrag): 16 Byte Kopf (`GSST`, Version 1, Anzahl der Einträge,
Generation, CRC-32 ab Byte 16), je Plugin 84 Byte: Name (16 Byte), Maske der
belegten Plätze (u32), 16 Werte (i32). Einträge von Plugins, die gerade nicht auf
der Karte liegen, bleiben beim Schreiben erhalten (höchstens 194 Einträge).
`src/script/store.mjs` baut und liest die Datei im Browser.

Geschrieben wird frühestens 50 Rahmen (2 Sekunden) nach dem letzten Schreiben und
nur, solange der Hauptbildschirm oder das Menü BLECH offen ist (dort liegen die Seiten von
`korg.menu.add`); ein weiterer `save()` davor bleibt
vorgemerkt. Ein Fehlschlag (keine Karte, Karte voll) zählt im Kontrollblock
(`storeErrors`) und wiederholt sich nicht von selbst. Im Lauf im Browser halten die
Werte bis zum Neuladen der Seite.

### Datendatei

Jedes Plugin hat eine Datei für eigene Bytes, `KORG/blechtribe/Plugin/Data/<name>.bin`: der Plugin-Name, jedes Zeichen außer
A bis Z, a bis z, 0 bis 9 und `-` als `_` (`dataFileName` im Vertrag). Sie ist höchstens 4096 Byte groß (`SCRIPT_DATA_FILE.maxBytes`);
die Grenze kann in einer späteren API-Version wachsen. `korg.file.read` und `korg.file.write` arbeiten auf einer Kopie im
RAM: die Laufzeit hält die Datei eines Plugins zur Zeit in einem Block vom Heap der Firmware (4112 Byte, beim ersten Aufruf
genommen, bis zum Ausschalten behalten). Ein anderes Plugin bekommt den Block erst, wenn die Datei des vorigen auf der Karte
steht. Was ein Plugin schreibt, bevor die Datei auf der Karte steht, geht beim Ausschalten verloren.

## Das Menü BLECH am Gerät

Mit dem BLECHTRIBE Patch hat die Electribe einen eigenen Bildschirm "BLECH", am Ende des EDIT Rings
hinter Event (Bildschirm 0x2D). Er hat drei Ebenen und sieht aus wie
Data Util: gleiche Schrift, gleiche Plätze, dieselbe Zeile `press  [ Enter ]`.

- **Im Ring** ist BLECH eine einzige Seite ("BLECH 31/32") hinter Event, danach kommt als letzte Seite
  [Blechy](#blechy-die-letzte-seite-des-rings) (32/32), dann wieder das Pattern Menü. Eine dritte Seite des Patches steht
  mitten im Ring: SYNC GROUP (16/32, eine Einstellung des Patterns, siehe unten) gleich hinter CHAIN REPEAT, der letzten Seite
  des Pattern Menüs, und vor der ersten Seite des Part Menüs, das damit bei 17 beginnt. Deshalb zählt der Ring bis 32 statt
  bis 29; auf der blauen bis 31 statt bis 28 (SYNC GROUP 16/31, BLECH 30/31, Blechy 31/31, die blaue hat kein Sample Menü).
  EDIT links und rechts blättern durch den Ring. Mit EXIT beim Einschalten ist der Bildschirm nicht da und der Ring ist der
  der Firmware.
- **In GLOBAL PARAMETERS** steht hinter der letzten Seite der Firmware (XY CALIBRATION) die Seite PLUGIN RUNTIME
  ("Global 21/21"), **in DATA UTILITY** stehen hinter der letzten Funktion (SOFTWARE UPDATE) EXPORT ALL CUSTOMIZATIONS,
  EXPORT ALL PLUGINS, EXPORT ALL EFFECTS und SET INIT PATTERN ("Data Util 15/18" bis "18/18"; auf der blauen, die 11 Funktionen
  und keine Sammeldatei hat, ohne EXPORT ALL EFFECTS: 12/14 bis 14/14). Sie sehen aus wie
  die Seiten der Firmware und gehören zum Bildschirm BLECH: EDIT blättert zwischen ihnen und den Seiten der Firmware in
  beide Richtungen, EXIT geht dorthin, wohin es von den Seiten der Firmware geht (Global, Data Util), die Zähler der
  Firmware zählen sie mit. Seiten in den Menüs der Firmware selbst anzulegen, hieße deren Tabellen und Zustandsmaschinen
  zu ändern; so bleiben beide unberührt (Entscheidung vom 29.10., [Messung](messungen/2026-10-29-menue-anordnung.md)).
- **ENTER auf der Seite BLECH** öffnet die Liste auf der Gruppe, aus der man zuletzt herauskam, auch nach
  einem Umweg durch die anderen Menüs.
- **ENTER**, die Taste MENU, öffnet die Liste der Gruppen. Das Schild oben links nennt
  BLECH, der Zähler zählt nur die Gruppen ("BLECH 2/3", mit Apps bis 5), EDIT blättert darin im Kreis.
- **ENTER auf einer Gruppe** zeigt ihre Seiten. Das Schild nennt die Gruppe ("Plugins 3/5"),
  der Zähler zählt nur ihre Seiten, EDIT blättert darin im Kreis, das Hauptrad ändert den
  Wert, WRITE führt aus oder speichert.
- **EXIT** geht immer eine Ebene zurück (Seite einer Gruppe, Liste der Gruppen, Ring) und
  auf der Ringseite zum Hauptbildschirm. MENU auf dem Hauptbildschirm kehrt dorthin zurück,
  wo man das Menü verlassen hat, auch in eine Gruppe.
- Solange der Bildschirm offen ist, sehen die Plugins keine Eingaben, damit ein Plugin,
  das Tasten abfängt, das Menü nicht sperren kann.

Die Liste der ersten Ebene besteht aus Gruppen, in dieser Reihenfolge: erst die eingebauten Schalter, dann
die Plugins, dann die Anpassung, dann die Gruppen, die Plugins selbst anmelden (`korg.app`), und als letzte Seite
VERSION, die keine Gruppe ist:

| Eintrag | Was dahinter liegt |
|---|---|
| FEATURES | die Schalter der eingebauten Funktionen: MFX 2, PATTERN CONFIRM, TAP MOTION, NOTE ASSIST und, wo der Satz den Patch last-pattern hat, LAST PATTERN, und, wo er den Patch stereo-pad hat (rot), STEREO 1 PAD, dazu KEY PADS, FILTER TOGGLE und AUTO SAVE (Tabelle unten) |
| PLUGINS | ENTER öffnet direkt die Liste der Plugins (MANAGE PLUGINS); siehe unten |
| CUSTOMIZATION | DISPLAY, LED, dazu PAD COLOR, POWER SAVE und SPLASH, wo der Satz sie hat; siehe unten |
| GAMES | je App eine Seite; erscheint nur, wenn ein Plugin eine App der Gruppe angemeldet hat |
| TOOLS | wie GAMES |
| VERSION | keine Gruppe: oben die Version des Satzes, mit dem die Firmware gepatcht wurde (`BLECH 1.3.7`, aus dem Patch `blech-version`), darunter die Firmware, für die das Menü gebaut ist (HACKTRIBE, KORG RED, KORG BLUE). Hinter der Firmware, was der Start mit `KORG/blechtribe/Presets/e2sFx.all` gemacht hat: "FX" (geladen, IFX und MFX der Parts gleich neu an den DSP geschickt, also z. B. "HACKTRIBE FX"), "FX off" (beim Start übersprungen), "FX fw?" (Datei für eine andere Firmware) oder "FX bad" (Datei kaputt); nichts ohne Datei. ENTER, WRITE und das Rad ändern nichts |

Die Seiten von FEATURES (das Schild nennt die Gruppe "Feature"), jede mit dem Wert ON oder OFF, das Hauptrad ändert ihn:

| Seite | Wert |
|---|---|
| MFX 2 | ON, OFF: MFX 2 auf TOUCH SCALE, gilt ab dem nächsten Start (Wert zeigt dann "ON, RESTART") |
| PATTERN CONFIRM | ON, OFF (siehe unten) |
| TAP MOTION | OFF, ON, ONCE (siehe unten) |
| NOTE ASSIST | ON, OFF (siehe unten) |
| LAST PATTERN | ON, OFF (siehe unten) |
| STEREO 1 PAD | ON, OFF (siehe unten, nur rot) |
| KEY PADS | ON, OFF (siehe unten) |
| FILTER TOGGLE | ON, OFF (siehe unten) |

Eine Gruppe ABOUT gibt es nicht mehr: sie zeigte nur die Zahl der geladenen Plugins und verwirrte.

Die Seiten der Gruppen:

| Gruppe, Seite | Wert | Wirkung |
|---|---|---|
| GLOBAL PARAMETERS, PLUGIN RUNTIME | ON, OFF | die Plugins der Karte an oder aus, gilt ab dem nächsten Start ("OFF, RESTART" zeigt, dass es noch nicht gilt); Blechy ist kein Plugin der Karte und bleibt. Die Seite 21/21 von GLOBAL PARAMETERS, WRITE speichert die Einstellungen des Menüs BLECH |
| PLUGINS, MANAGE PLUGINS | ENTER auf PLUGINS führt ohne Zwischenseite hierher; die Seite MANAGE PLUGINS selbst (`press  [ Enter ]`) zeigt sich nur mit "No Plugin", wenn es nichts zu zeigen gibt, und nach REMOVE mit dessen Meldung, ENTER dort öffnet die Liste wieder | ENTER liest den Ordner `KORG/blechtribe/Plugin/` (bis 64 Plugin-Dateien; hat er mehr, steht hinter dem letzten Plugin die Seite LIST FULL mit "64 files shown", [Messung](messungen/2026-10-30-plugin-liste-64-entfernen.md)) und öffnet die Liste aller Plugins, eine Seite je Plugin (das Schild bleibt "Plugins", der Zähler zählt sie, EDIT blättert im Kreis wie in jedem anderen Menü). Seit 1.4.5 sieht die Liste aus wie der Dateibrowser von DATA UTILITY: drei Zeilen in großer Schrift mit Dateisymbol vor dem Namen, lange Namen mit "..", das Dreieck links am gezeigten Plugin, die Bildlaufleiste rechts ([Messung](messungen/2026-11-08-plugin-liste-browser.md)). Sie öffnet auf dem Plugin, das man zuletzt gesehen hat; EXIT führt zurück auf die Zeile PLUGINS (bis 1.4.5 gab es dazwischen die eine Seite MANAGE PLUGINS). In der Liste stehen zuerst die geladenen Plugins, dann die der `*.blech`-Dateien, die nicht geladen sind, jedes Plugin einmal (gleicher Name im Kopf der Datei und im geladenen Block heißt: dasselbe Plugin). Ein Plugin, das nur in `e2sPlugin.all` steht und zu dem es keine Datei gibt, steht als geladenes in der Liste und hat keine Beschreibung. Teile der Firmware (Blechy und was BLECHTRIBE selbst mitbringt) sind keine Plugins und stehen nie hier, ihre Schalter sind unter FEATURES |
| ein Plugin der Liste | seine Zeile: ein Blatt mit zwei Linien heißt ON, ein leeres Blatt OFF (auch nicht geladen oder mit Fehler); unter den Zeilen klein `DIV_ZERO L3`, WRITE=ALLOW oder was getan wurde | das Hauptrad blättert durch die Liste wie im Dateibrowser von IMPORT SAMPLE und bleibt am Anfang und am Ende stehen, EDIT auch, im Kreis ([Messung](messungen/2026-11-09-menue-liste-rad.md)). Geschaltet wird auf der Seite ACTIVE, der ersten Seite des Plugins: ENTER auf dem Plugin öffnet sie, das Hauptrad schaltet gleich, weder ENTER noch EDIT sind dafür nötig. Nach unten hält es das Plugin an und nimmt es aus `e2sPlugin.all` (die Datei wird ohne es neu geschrieben, auch leer, wenn es das letzte war), die `*.blech` im Ordner bleibt: die Seite bleibt offen und zeigt OFF, das Plugin steht als nicht geladenes in der Liste. Ein Plugin, zu dem es keine `*.blech` gibt (nur in `e2sPlugin.all`), hält nur an, sonst wäre es weg; WRITE behält diesen Stand über einen Neustart (es startet dann nicht, beim Einschalten läuft sein Start nach). Bei einem Fehler steht der Fehler mit der Zeile; ein fremdes Plugin wartet mit WRITE=ALLOW auf die Zustimmung (nur WRITE erlaubt es, das Rad nicht). Ein Plugin, das nicht geladen ist, zeigt OFF wie ein ausgeschaltetes: das Hauptrad nach oben auf ACTIVE lädt es aus der Datei, startet es und schreibt `e2sPlugin.all` mit ihm neu, so läuft es auch nach einem Neustart (ein fremdes wartet dann auf WRITE=ALLOW, ein kaputter Block meldet "rejected", ohne Plugins in der Laufzeit "runtime off"), nach unten tut das Rad nichts. ENTER öffnet die Seiten des Plugins: ACTIVE, DESCRIPTION, seine eigenen Seiten und REMOVE; EXIT führt zurück auf das Plugin in der Liste |
| Plugin, ACTIVE (die erste Seite) | ON, OFF, `DIV_ZERO L3`, WRITE=ALLOW oder was getan wurde | der Zustand des Plugins wie unter seiner Zeile in der Liste: das Hauptrad schaltet es, WRITE speichert den Stand oder erlaubt ein fremdes Plugin, wie oben beschrieben |
| Plugin, DESCRIPTION | der Zustand des Plugins unter der Beschreibung | die Beschreibung aus der `*.blech`-Datei des Plugins (die `//`-Zeilen ganz oben im Code), als Bild über den ganzen Bildschirm: oben der Name, darunter die Zeilen, unten der Stand. Das Hauptrad scrollt zeilenweise, `^` und `v` zeigen, dass es weitergeht; ENTER tut hier nichts. Ohne Datei oder ohne Beschreibung steht "no description" |
| Plugin, je `korg.menu.add` eine Seite | die Zahl | die Einstellungen dieses Plugins: das Hauptrad ändert sie, das Plugin bekommt `menu` |
| Plugin, REMOVE | `press  [ Enter ]` | ENTER fragt ("Enter = remove"), ein zweites ENTER nimmt es aus `e2sPlugin.all` wie ACTIVE OFF und löscht danach die `*.blech` des Plugins von der Karte (`f_unlink` der Firmware): es steht nicht mehr in der Liste, MANAGE PLUGINS meldet "removed". Bei einem Plugin, das nur eine Datei ist, wird nur die Datei gelöscht, bei einem nur in `e2sPlugin.all` nur diese neu geschrieben. Die blaue Electribe hat kein `f_unlink`: dort bleibt die Datei, MANAGE PLUGINS meldet "file stays on card". Hat sich der Ordner seit dem Öffnen der Liste geändert, wird nichts gelöscht ("folder changed") ([Messung](messungen/2026-10-30-plugin-liste-64-entfernen.md)) |
| DATA UTILITY, EXPORT ALL CUSTOMIZATIONS | (leer, `press  [ Enter ]`; der Titel heißt "EXPORT ALL CUSTOM", der ganze Name passt nicht in die Zeile) | ENTER oder WRITE schreibt die Anpassung als `KORG/blechtribe/e2sCustom.all`: derselbe Satz wie die Einstellungsdatei, ohne die Liste der Prüfsummen der Plugins, und meldet "exported". Beim Start liest noch nichts diese Datei; kopiert über `settings.a.bin` liest sie der Einstellungslader, und die Anpassung ist zurück |
| DATA UTILITY, EXPORT ALL EFFECTS | (leer, `press  [ Enter ]`) | ENTER oder WRITE schreibt die Presets und Modulationstypen, wie die Firmware sie gerade im RAM hält, zurück in die Sammeldatei `KORG/blechtribe/Presets/e2sFx.all` (IFX, MFX und Modulation aus dem Baukasten): jeder Eintrag bleibt an seinem Platz, mit seinem `.e2fx`-Text, den der Editor zurückliest; die Prüfsumme wird neu. Gibt es keine Sammeldatei, legt es eine an (Einträge ohne Text, die lässt der Baukasten beim Laden aus). Eine vorhandene Datei nur, wenn sie beim Einschalten geladen wurde: "bad e2sFx.all", wenn sie seitdem eine andere oder kaputt ist, dann wird nichts geschrieben. Rot und blau (Korgs 2.02 mit dem BLECH-Satz) |
| DATA UTILITY, EXPORT ALL PLUGINS | (leer, `press  [ Enter ]`) | ENTER oder WRITE schreibt alle geladenen Plugins als `e2sPlugin.all`, Byte für Byte so, wie der Browser sie packt, und speichert danach die Einstellungen mit (ausgeschaltete Plugins bleiben aus) |
| GAMES oder TOOLS, eine App je Seite | ENTER=OPEN | ENTER oder WRITE öffnet die App ("Apps und das Display"); steht das Plugin auf OFF oder ist es ausgefallen, zeigt der Wert OFF oder FAULT |
| CUSTOMIZATION, DISPLAY | ENTER | öffnet die Seiten des Display-Lichts; EXIT führt zurück auf DISPLAY |
| DISPLAY, BACKLIGHT HUE, SAT, BRIGHT | HUE 0 bis 95, SAT und BRIGHT 0 bis 15 | Farbe des Display-Lichts: HUE läuft einmal um den Farbkreis (16 Schritte je Rot, Gelb, Grün, Cyan, Blau, Magenta und der Weg dazwischen), SAT ist die Sättigung, BRIGHT die Helligkeit; gespeichert bleibt Rot, Grün, Blau zu je 0 bis 15, eine ältere Datei liest sich also wie vorher; ohne Einstellung steht STOCK da (das Weiß der Firmware), volle Helligkeit ohne Sättigung ist wieder STOCK; ein Schritt, der dieselbe Farbe ergäbe, springt zum nächsten, der sie ändert; gilt sofort; nach WRITE leuchtet das Display beim Einschalten in den Kanälen der Farbe (ein Kanal leuchtet dort, wenn er mindestens halb so stark ist wie der stärkste, Gelb statt Weiß bei HUE 15, SAT 13, BRIGHT 14), auf der roten schon vor dem Startbild, auf der blauen kurz nachdem es erscheint, Zwischenstufen erst, wenn das Menü geladen ist ([Messung](messungen/2026-10-29-hintergrundlicht-beim-start.md)) |
| DISPLAY, INTENSITY | 0 bis 15 | Helligkeit des Display-Lichts über alle drei Farben, die Mischung bleibt; 0 ist kein Licht, 15 die volle Farbe; gilt sofort |
| DISPLAY, DISPLAY INVERT | OFF, ON | kehrt das Display um: helle Punkte dunkel und dunkle hell (Befehl `0xA7` an den Display-Baustein, `0xA6` stellt zurück); gilt sofort; ON ist die Vorgabe (eine helle Spur auf dunklem Grund schmiert weniger als eine dunkle), eine Einstellungsdatei aus 1.2 ohne das Bit bleibt bei OFF |
| CUSTOMIZATION, POWER SAVE | ENTER | öffnet die Seiten für den Energiesparmodus (nur auf Batterie); EXIT führt zurück auf POWER SAVE |
| POWER SAVE, DISPLAY LIGHT | STOCK, 1 bis 15 | das Display-Licht im Energiesparmodus: STOCK ist das Dimmen der Firmware, 1 bis 15 die eigene Farbe, 1 leuchtet mit 3 von 15, 15 voll |
| POWER SAVE, LED DIMMING | 0 bis 100 % | wie stark der Energiesparmodus Pads, Tasten und Regler-LEDs dimmt: 0 % gar nicht, 100 % aus, 75 % (die Vorgabe) ein Viertel der Helligkeit; die Regler-LEDs gehen aus, außer bei 0 %; gilt sofort, WRITE behält es |
| CUSTOMIZATION, LED | ENTER | öffnet die Seiten der unteren LEDs; EXIT führt zurück auf LED |
| LED, BOTTOM LEDS | METER, COLOR, OFF | die vier unteren RGB-LEDs: METER ist die Pegelanzeige, COLOR eine feste Farbe, OFF dunkel; gilt sofort |
| LED, LED HUE, SAT, BRIGHT | HUE 0 bis 95, SAT und BRIGHT 0 bis 15 | Farbe der unteren LEDs für COLOR, eingestellt wie beim Display-Licht; bei METER bestimmt der Pegel die Helligkeit dieser Farbe, solange keine Meter-Farbe gesetzt ist; STOCK heißt die Farben der Firmware; gilt sofort |
| LED, METER STILL, LOW, MID, LOUD | STOCK, WHITE, RED, GREEN, BLUE, YELLOW, CYAN, PINK (STILL und LOUD: RAINBOW, STILL: zusätzlich OFF) | die Farbe der Pegelanzeige je Zone, aufgeteilt wie in der Firmware: STILL ohne Pegel, LOW, MID, LOUD; STOCK ist die Farbe der Firmware (weiß, blau, grün, rot); STILL und LOUD haben dahinter noch RAINBOW, die Farbe läuft flüssig durch Rot, Grün und Blau: bei STILL in rund 3,5 s einmal rundum, bei LOUD einmal je Takt im Tempo des Patterns (bei 128 BPM rund 1,9 s); STILL OFF lässt die Anzeige ohne Pegel dunkel |
| LED, KNOB LEDS | ON, OFF | die LEDs hinter den Reglern VALUE, SAMPLE/OSC, CUTOFF, MOD TYPE und IFX TYPE: ON wie in der Firmware, OFF hält sie dunkel, alles andere bleibt; gilt sofort, WRITE behält es (Bit 6 von Byte 5 der Einstellungsdatei heißt OFF); ohne Datei ON; EXIT beim Einschalten: wie in der Firmware; nur wo der Satz den Patch pad-colors hat; Hacktribe, rot und blau, im Emulator geprüft, am Gerät nicht ([Messung](messungen/2026-11-12-knopf-leds.md)) |
| CUSTOMIZATION, PAD COLOR | ENTER | öffnet die Seiten der Pad-Farben; nur wo der Satz den Patch pad-colors hat ([Messung](messungen/2026-10-17-pad-farben.md)) |
| PAD COLOR, PAD COLOR | RED, BLUE, PINK | die Farbe, in der die Pads zeigen, was die Firmware rot zeigt (Part spielt, Pad gedrückt, Schritt); gilt sofort, WRITE behält sie; RED ist die Vorgabe. Im SEQUENCER-Modus zeigt ein Step, der die Note des vorigen per TIE weiterspielt, einen Schweif in Pink, der über die Länge der Note ausläuft; überlappen sich gebundene Noten, addiert sich ihre Helligkeit ([Messung](messungen/2026-10-19-gate-schweif.md)). |
| PAD COLOR, SELECT COLOR | RED, BLUE, PINK | die Farbe des gewählten Parts, nie die von PAD COLOR; leuchten beide, zeigt das Pad die Farbe von OVERLAP; BLUE ist die Vorgabe |
| PAD COLOR, OVERLAP | AUTO, RED, BLUE, PINK | die Farbe eines Pads, das zugleich leuchtet und gewählt ist; AUTO ist die dritte Farbe, die weder PAD COLOR noch SELECT COLOR ist |
| CUSTOMIZATION, SPLASH | ENTER | öffnet die drei Seiten des Startbilds; EXIT führt zurück auf SPLASH. Nur wo der Satz den Startbild-Editor hat |
| SPLASH, SPLASH IMPORT | Rad, ENTER | zeigt die `.bmp`-Dateien direkt in `KORG/blechtribe/` wie der Dateibrowser von IMPORT SAMPLE (drei Zeilen, Name ohne `.bmp`, ein Name mit mehr als 11 Zeichen auf 11 gekürzt mit "..", der Zähler im Kopf zählt die Dateien, ohne Datei steht NO .BMP FILE; keine Unterordner, keine Namen mit Punkt vorn wie die `._` von macOS), das Rad blättert in der Reihenfolge des Ordners. ENTER liest die gezeigte Datei (128 x 64 Pixel, 1 Bit je Pixel, unkomprimiert; gezeichnet wird die dunklere Farbe) und speichert sie als Startbild wie WRITE im Startbild-Editor; ab dem nächsten Start zu sehen. Meldet "loaded", "no .bmp file" oder "not 128x64 1 bit" (dann bleibt alles, wie es war). Nur wo der Satz den Startbild-Editor hat, also nicht auf der blauen |
| SPLASH, SPLASH DRAW | ENTER | öffnet den Startbild-Editor (eine Seite des Global-Bildschirms, die nur von hier aus erreichbar ist): Rad bewegt den Cursor nach links und rechts, mit gehaltenem SHIFT hoch und runter, MENU kippt das Pixel, gehalten malt es dessen neue Farbe überall hin, wo der Cursor langläuft, WRITE speichert, EXIT verlässt den Editor. Nur wo der Satz den Startbild-Editor hat |
| SPLASH, SPLASH RESET | ENTER | verwirft das gespeicherte Startbild (Import oder Editor), ab sofort und bei jedem weiteren Start kommt wieder das Startbild der Firmware; die Seite sagt "original back". Nur wo der Satz den Startbild-Editor hat |
| FEATURES, PATTERN CONFIRM | ON, OFF | ON: ein anderes Pattern, das am Rad gewählt wird, wartet beim Spielen auf MENU (ENTER) und startet am Sequenzende; OFF: die Firmware wie ohne den Patch Patternwechsel; gilt sofort, ON ist die Vorgabe (auch ohne Datei); OFF steht als Bit 2 der Flags in der Einstellungsdatei Die Taste MENU zeigt, wo man drücken muss: sie blinkt, solange ein Pattern nur angesehen ist (VIEW:, auch gestoppt mit ungespeicherten Änderungen), und leuchtet, sobald es bestätigt ist (NEXT:), bis zum Wechsel; danach ist sie wieder so, wie die Firmware sie hatte. Dabei zeigen die Pads und, nach EDIT, die Info-Texte (OSC, Pitch und so weiter) das Pattern, das angesehen oder bestätigt ist ([Messung](messungen/2026-10-25-pattern-ansicht.md)). Die Pads gehören dann diesem Pattern und haben eine eigene Farbe: PART MUTE schaltet seine Mutes, die es beim Wechsel mitnimmt ([Messung](messungen/2026-10-29-vorschau-pads.md)). Der erste Druck auf ein Pad holt den Part mit Copy Part sofort ins laufende Pattern, nicht stumm, ohne Wechsel; danach schaltet sein Pad ihn dort ([Messung](messungen/2026-10-30-vorschau-part-reinholen.md)). |
| Ring, SYNC GROUP | OFF, 1 bis 999 | eine eigene Seite im Ring (16/32), gleich hinter CHAIN REPEAT, der letzten Seite des Pattern Menüs, und vor dem Part Menü (EDIT rechts von dort, EDIT links von der ersten Seite des Part Menüs; das Schild sagt "Pattern"), auf beiden Electribes (auf der blauen seit 24.10., [Messung](messungen/2026-10-24-blau-sync-group.md)): die Sync Group des Patterns im RAM; das Hauptrad ändert sie, WRITE öffnet das Speichern des Patterns wie auf den Seiten des Pattern Menüs, gespeichert wird sie mit dem Pattern. Läuft ein Pattern, startet ein anderes Pattern derselben Gruppe am Rad ohne MENU am Sequenzende (unten NEXT:), eines außerhalb der Gruppe wartet wie immer auf MENU; gestoppt lädt das Rad ein Pattern der Gruppe auch dann sofort, wenn das Pattern ungespeicherte Änderungen hat ([Messung](messungen/2026-10-25-sync-ungespeichert.md)); beim Wechsel zwischen zwei Patterns einer Gruppe geht der Stand des Patterns mit, das gespielt hat, verändert oder nicht: Part-Mutes und Klang der Parts (Sample, Filter, Modulation, Pitch, Amp, IFX und die übrigen Part-Werte), Tempo, Swing, Lautstärke, das MFX-Pad mit HOLD, auch zurück; die Effekttypen MFX 1 und MFX 2 bleiben die des neuen Patterns; die Patterns einer Gruppe spielen wie eines (nur im RAM). Steps, Motion, Länge, Beat, Tonart, Tonleiter und Chord Set bleiben die des neuen Patterns. OFF (0) heißt keine Gruppe, kein Abgleich ([Messung](messungen/2026-10-19-sync-groups.md), [Stand vom 22.10.](messungen/2026-10-22-sync-und-menues.md)) |
| Pattern Menü, BEAT | 16, 32, 8 Tri, 16 Tri, 8 | der fünfte Wert `8` macht jeden Step zur Achtel: das Pattern läuft doppelt so lang, bei 160 BPM wie BEAT 16 bei 80 BPM, MIDI Clock und TAP-LED bleiben beim echten Tempo, mit externer Clock 12 Pulse je Step; wird mit dem Pattern gespeichert; Gate Arp, Export und Slices folgen dem Step; auf Korgs Firmware ohne BLECHTRIBE läuft ein solches Pattern mit einem Step alle 2 ms; rot und blau ([Messung](messungen/2026-10-29-beat-achtel.md)) |
| FEATURES, TAP MOTION | OFF, ON, ONCE | ON: TAP schaltet die aufgenommene Motion Sequence des gewählten Parts an und aus (Idee 39), TAP länger als 0,3 s gehalten schaltet nur, solange es gehalten ist, beim Loslassen zurück; OFF: TAP ist wieder das Tap-Tempo der Firmware; ONCE (Wert 2 des Einstellungsworts): eine mit TAP eingeschaltete Bewegung spielt bis zum Ende des Patterns und geht dann aus; gilt sofort, ON ist die Vorgabe (auch ohne Datei); OFF steht als Bit 3, ONCE als Bit 5 der Flags in der Einstellungsdatei (Bit 3 gewinnt) |
| FEATURES, NOTE ASSIST | ON, OFF | ON: im KEYBOARD-Modus leuchten nach einer Note die Pads der passenden Noten rosa, je besser sie passen, desto heller (Prim und Quinte, dann Terzen, Quarte und ein Tonleiterschritt, dann Sexten); gestoppt oder pausiert bleiben sie stehen, beim Spielen blenden sie aus, die schwachen zuerst; im CHORD-Modus (Skalen mit sieben Tönen) zeigen die Pads ebenso, welche Akkorde gut folgen ([Messung](messungen/2026-10-15-note-assistant.md), [Helligkeit und Ausblenden](messungen/2026-10-19-notenassistent-helligkeit.md)); OFF: die Pads wie in der Firmware; gilt sofort, ON ist die Vorgabe (auch ohne Datei); OFF steht als Bit 4 der Flags in der Einstellungsdatei |
| FEATURES, LAST PATTERN | ON, OFF | ON: beim Einschalten öffnet die Electribe das Pattern, das vor dem Ausschalten gewählt war ([Idee 76](ideen/76-letztes-pattern.md)); OFF: sie startet wie in der Firmware mit 001, die gemerkte Nummer bleibt für einen Start mit ON; gilt ab dem nächsten Einschalten, WRITE behält es (Bit 3 von Byte 5 der Einstellungsdatei heißt OFF); ohne Datei ON; EXIT beim Einschalten: 001; rot und blau, wo der Satz den Patch last-pattern hat ([Messung](messungen/2026-10-29-letztes-pattern-schalter-doom-ohne-dateien.md)) |
| FEATURES, STEREO 1 PAD | ON, OFF | ON: ein Stereo-Sample belegt nur sein eigenes Pad und spielt dort auf einer Stimme, das Pad daneben spielt sein eigenes Sample; OFF: wie in der Firmware belegt ein Stereo-Sample auf Pad 1, 3, ... auch das nächste Pad; gilt sofort, WRITE behält es (Bit 2 von Byte 5 der Einstellungsdatei heißt OFF); ohne Datei ON; EXIT beim Einschalten: wie in der Firmware; nur wo der Satz den Patch stereo-pad hat (rot) ([Messung](messungen/2026-10-29-stereo-ein-pad.md)) |
| FEATURES, KEY PADS | ON, OFF | ON: KEYBOARD gehalten + Pad setzt den KEY (chromatisch in Pad-Reihenfolge: Pad 1 C bis Pad 12 B, Pads 13 bis 16 wählen die Oktave der Tastatur, Pad 14 ist die nach dem Start), das Wertefenster der Firmware zeigt ihn; OFF: die Pads wie in der Firmware (KEYBOARD + Pad 13 wählt still Part 13); gilt sofort, WRITE behält es (Bit 4 von Byte 5 der Einstellungsdatei heißt OFF); ohne Datei ON; Hacktribe, rot und blau, im Emulator geprüft, am Gerät nicht ([Messung](messungen/2026-11-07-key-pads-eingebaut.md), [Belegung](messungen/2026-11-08-key-pads-chromatisch.md)) |
| FEATURES, FILTER TOGGLE | ON, OFF | ON: SHIFT + LPF, HPF oder BPF schaltet das Filter des gewählten Parts aus und wieder an, mit dem Typ, den die Taste zuletzt hatte; OFF: SHIFT + Filtertaste wie in der Firmware; gilt sofort, WRITE behält es (Bit 5 von Byte 5 der Einstellungsdatei heißt OFF); ohne Datei ON; Hacktribe, rot und blau, im Emulator geprüft, am Gerät nicht ([Messung](messungen/2026-11-08-filter-toggle-eingebaut.md)) |
| FEATURES, AUTO SAVE | ON, OFF | ON: wer GLOBAL PARAMETERS (oder PLUGIN RUNTIME dahinter) verlässt und dort einen Wert geändert hat, dem speichert BLECHTRIBE die Global-Werte mit demselben Auftrag wie WRITE dort (die Firmware zeigt rund eine Sekunde ihr Fenster "Writing...", wie nach WRITE); wer das BLECH-Menü verlässt und eine Einstellung geändert hat, dem schreibt es die Einstellungsdatei wie WRITE; ohne Änderung wird nichts geschrieben, Patterns bleiben bei WRITE; OFF: nur WRITE speichert, wie in der Firmware; gilt sofort, ON ist die Vorgabe (auch ohne Datei); OFF steht als Bit 7 von Byte 5 der Einstellungsdatei, ein BLECHTRIBE vor 1.5 verwirft eine Datei mit diesem Bit; das Ausschalten von AUTO SAVE selbst behält erst WRITE ([Messung](messungen/2026-11-09-auto-save.md)) |
| DATA UTILITY, SET INIT PATTERN | FACTORY, 1 bis 250 | das Pattern, das DATA UTILITY > INITIALIZE PATTERN als Vorlage nimmt; FACTORY ist die Vorlage der Firmware; gilt sofort und bleibt über das Ausschalten (Global-Byte 247, kein WRITE nötig); nur wo der Satz den Patch init-pattern hat (rot) ([Messung](messungen/2026-10-28-init-pattern.md)) |

Rückmeldungen ("saved", "no card", "imported", "2 exported" und so weiter) ersetzen den
Wert der Seite, bis man das Hauptrad dreht oder die Seite wechselt. Die dritte Zeile der
Firmware (die Einheit hinter einem Wert) beginnt bei jedem Bildschirm in Spalte 28 der
Wertzeile: jeder Wert, der breiter ist als ein oder zwei Zeichen, läuft hinein. Das Menü
benutzt sie deshalb nie. Was eine Seite sagt, steht im Wert, der rund 14 Zeichen fasst, der
Titel rund 18.

Auf den Seiten PLUGIN RUNTIME, den Seiten von FEATURES, den Seiten von CUSTOMIZATION und bei der Zustimmung für fremde Plugins
speichert WRITE (mit AUTO SAVE auch das Verlassen des Menüs nach einer Änderung) die Einstellungen in `KORG/blechtribe/settings.a.bin` und `settings.b.bin`, die
sich mit einer Generationsnummer abwechseln (24 bis 280 Byte: Kennung `GSET`, Version 3, ein Byte mit METER LOUD RAINBOW in Bit 0 (ein BLECHTRIBE vor 1.3 verwirft eine Datei, in der es gesetzt ist), Anzahl
erlaubter Prüfsummen, Generation, Schalter, das Wort für die Anpassung, die Prüfsummen der
erlaubten fremden Blöcke, CRC-32; höchstens 64 Einträge (bis 1.3.7 Version 2 mit höchstens 16; ein BLECHTRIBE bis 1.3.7 liest Version 3 nicht, es nimmt dann eine ältere Datei der Version 2, die noch auf der Karte liegt, oder die Standardwerte);
in derselben Liste steht für jedes ausgeschaltete Plugin seine Prüfsumme invertiert, ein älteres BLECHTRIBE liest sie als
Prüfsumme, die nie passt, [Messung](messungen/2026-10-18-plugin-bleibt-aus.md); ist die Liste voll, fliegt zuerst der
älteste Eintrag raus, der zu keinem geladenen Plugin gehört (ein Plugin, das nicht mehr auf der Karte liegt, oder eine ältere
Fassung davon), sonst bei einer Zustimmung der älteste überhaupt; eine Markierung, für die dann kein Platz bleibt, fehlt, und das Plugin läuft nach dem Neustart wieder;
Dateien der Version 2 und der Version 1 ohne das Wort werden weiter gelesen und beim nächsten WRITE als Version 3 geschrieben). Ohne Datei, Karte oder bei
beschädigter Datei gelten die Voreinstellungen (alles an, die Anpassung auf den Werten der
Firmware). Die Seite meldet "saved", "no card", "card protected", "folder missing" oder "write error".
Es wird nichts in den Flash geschrieben.

**Anpassung (CUSTOMIZATION):** Was am Gerät sichtbar ist, gilt sofort beim Drehen, das Menü ist die
Vorschau; erst WRITE merkt es sich für den nächsten Start. Die Firmware behält ihre eigenen Schalter:
Power Save (die unteren LEDs aus, das Display-Licht gedimmt) bleibt, wie sie es macht, ein Plugin, das
die LEDs sperrt (`korg.ledHold`), behält sie, und mit EXIT beim Einschalten ist alles wie im
Original. Die Farben der Firmware sind der Vorgabewert. Gespeichert sind sie weiter als alle Pegel 0 (so lesen
auch alte Dateien wie bisher, die Datei bekommt kein neues Bit), die Seiten zeigen diesen Zustand aber als 15 mit dem
Zusatz "stock", denn das Gerät leuchtet dann voll: der Wert, der "nichts eingestellt" heißt, ist die hellste Stufe.
Das Hauptrad geht von dort nach unten (15 für alle drei, dann der gewählte Kanal tiefer), nach oben ändert es nichts; stellt
man den letzten Kanal auf 0 zurück, ist wieder der Zustand der Firmware da und die Seiten zeigen wieder 15 "stock". Eine Datei
mit eigenen Werten zeigt diese Werte, auch 0. Die Einstellungen gelten ab dem Befehl, der die `e2sSample.all` lädt, also schon
vor dem Laden der Samples und nicht erst danach ([Zeitlinie](messungen/2026-10-16-blech-look-frueh.md)). Messungen und Grenzen:
[Anpassung](messungen/2026-10-14-blech-anpassung.md).

Der Startbild Schalter fehlt mit Absicht: das Startbild wird rund 290 ms gezeichnet, bevor
die Karte lesbar ist, eine Einstellung von der Karte kann es nicht mehr ändern.

## Blechy, die letzte Seite des Rings

Blechy, das heruntergekommene Nasenwesen, ist kein Plugin. Er ist in BLECHTRIBE eingebaut und hat die
**letzte Seite im EDIT Ring** der Firmware: hinter Event und BLECH, vor dem Pattern Menü ("32/32"; auf der
blauen "31/31"). Vom Pattern Menü aus erreicht man ihn mit EDIT links auf dessen erster Seite. Auf der Seite steht er sofort da, live:
kein Untermenü, kein `press  [ Enter ]`, das ganze Display gehört ihm (die Seitenzahl ist dabei nicht zu sehen).

- **Wie jede Seite des Rings:** EDIT links geht zu BLECH, EDIT rechts zum Pattern Menü, EXIT zum
  Hauptbildschirm. Das Hauptrad, MENU und WRITE ändern auf seiner Seite nichts (das Hauptrad blättert auf den
  Ringseiten der Firmware auch nicht). Gemessen im Emulator ([Messung](messungen/2026-10-15-blechy.md)).
- **Er winkt.** Landet man auf der Seite, steht er da. Etwa eine Sekunde später winkt er einmal: die Hand schwingt
  alle 220 ms hin und her, 1,76 s lang (vier volle Schwünge), dann steht er wieder. Einmal je Landung: wer weg- und
  zurückblättert, wird wieder begrüßt. Die Sekunde ist eine Wahl, keine Messung am Gerät: kurz genug, dass es
  wie ein Gruß wirkt, lang genug, dass er nicht schon beim Bildschirmwechsel mitten in der Bewegung ist und man ihn
  erst als stehendes Bild sieht. Tippt man ihn in der Wartezeit an, kommt zuerst der Ärger und der Gruß danach.
  Die zwei Winkbilder (`blechy-wave-1.png`, `blechy-wave-2.png`) sind aus der ruhigen Pose abgeleitet, nur der rechte
  Arm und die Hand sind anders (`tools/art/make_blechy.py`).
- **Er geht.** Nach dem Winken läuft er langsam über das Display, ein Pixel alle 120 ms (rund 10 s von einem Rand zum
  anderen) und zurück, mit dem Gehbild (`blechy-walk.png`); an jedem Rand bleibt er eine Sekunde stehen und kehrt um.
  Beim Gehen senkt er sich alle zwei Pixel um eine Zeile, mehr Schritt gibt das eine Gehbild nicht her. Wo er gerade steht,
  gilt auch das Antippen (wütend) und das Streicheln (froh); danach geht er weiter.
- **Er redet.** Hin und wieder, wenn er einen Rand erreicht hat, bleibt er 3,5 s stehen und sagt etwas in einer Sprechblase,
  auf der Seite, auf der Platz ist: am linken Rand rechts von ihm, am rechten links. Die erste Blase kommt nach gut 12 s,
  danach alle 20 s oder 30 s (8 s plus 0 bis 8 s Zufall nach der letzten, dazu der Weg zum nächsten Rand). Die Zeilen kommen
  der Reihe nach: "yo, na du?", das Lieblingstempo (das am häufigsten gespielte, je Beat gezählt; solange noch nichts
  gespielt wurde, die feste Zeile "mein Tempo ist 150 bpm"), seit wann es läuft ("Spielt seit n min" seit dem ersten PLAY,
  sonst "Läuft seit" seit dem Einschalten, unter einer Minute in Sekunden), "Blech ist mein Ding",
  "bisschen mehr Bass?", "nicht so doll tippen", "Schranz ist Liebe". Alles in der eigenen Schrift (5 mal 7, ASCII und ä, ö,
  ü). Die Wartezeiten, das Tempo des Gehens und die Texte sind eine Wahl, am Gerät nicht erprobt.
- **PLAY.** Drückt man PLAY, geht er zügig (zwei Pixel alle 70 ms) in die Mitte, ein Stück links davon, damit neben ihm Platz
  für die Blase bleibt, sagt "ich hör mir das kurz an" (2,8 s), steht noch und tanzt dann, solange das Pattern spielt, ein Bild
  je Achtel. Die Wartezeit von 12 s bis zum Tanz gibt es nicht mehr. STOP beendet den Tanz, er geht wieder; die Frage "wat
  machst'n du da atze?" ist weg, sie passte nur auf den Hauptbildschirm.
- **Sonst wie vorher:** ein Tipp des Touchpads nahe an ihm macht ihn wütend, Streicheln froh. Die Zahlen (Tempo, Spielzeit)
  leben nur im RAM und beginnen mit jedem Start neu.
- **Kein Plugin der Karte:** er steht weder unter GAMES noch unter PLUGINS, wird nicht gezählt, nicht von EXPORT ALL PLUGINS
  geschrieben und lässt sich nicht ausschalten. Er braucht keine Karte und keine Datei `e2sPlugin.all` und läuft auch mit
  der Einstellung PLUGIN RUNTIME auf OFF. Mit EXIT beim Einschalten fehlt er (und mit ihm die Seite): der Ring ist der der Firmware.
- **Eingaben:** auf seiner Seite sehen die Plugins der Karte nur das Touchpad (die Taste und die Lage), alles andere geht
  allein an die Firmware, und ein Plugin kann dort keine Taste abfangen: EDIT und EXIT funktionieren immer.
- **Eingebaut heißt:** sein Block (15476 Byte, ein ganz normaler Plugin-Block der API 6, vom Editor übersetzt und im
  Browser geprüft, `tools/blechy-build.mjs`) steht im Abbild der Firmware bei `0xC0184000` und bleibt dort. Der Lader
  legt für ihn nur den Eintrag und seine Variablen in den Pool (15904 Byte von 128 KiB), den Block nicht. Beim Start
  lädt BLECHTRIBE ihn vor der Karte, meldet ihn als verborgene App an (Eintrag 0 der Tabelle, in einer Gruppe, die kein Menü
  zeigt) und lässt seinen Rumpf laufen. Öffnen und Schließen folgt der Seite: sobald die Firmware sie zeigt, bekommt er `open`
  und das Display, wenn sie etwas anderes zeigt, `close`. Die Quelle bleibt `data/script/blechy-source.mjs`, auch wenn er
  kein Beispiel-Plugin mehr ist. Der Start kostet rund 5,4 Millionen Befehle (gezählt im Emulator; am Gerät sind das geschätzt
  einige zehn Millisekunden), davon 70 % das byteweise Nullen der Laufzeit und der Prüftabellen (`mem_fill`), 8 % die
  Prüfsumme des Blocks.

## Die Beispiel-Plugins

Alle zehn Apps stehen im Katalog der Seite Plugins und in `data/script/presets.mjs`. Sie laufen im Emulator
der Plugin-Laufzeit (Browser-VM), am Gerät ist von ihnen nichts geprüft. `test/script-plugins.test.mjs` spielt jede
mit Eingaben durch. Die Kosten sind der teuerste Handler in Kosteneinheiten, gezählt in einem Lauf mit Eingaben
(Tetris 3000 Rahmen, Mandelbrot mit vollständigen Bildern und Randansichten, Set-Timer 90 Sekunden). Die Zeit daneben ist **hergeleitet**: der Snake-Rahmen
mit 542 Einheiten brauchte im Emulator 0,103 ms ([Messung](messungen/2026-10-14-skript-snake.md)), die Warnschwelle von
0,5 ms liegt also bei rund 2630 Einheiten. Jede App bleibt darunter, die Tests prüfen es. Am Gerät kann die Zeit je
Einheit anders sein.

| App | Gruppe | Bedienung | Block | Teuerster Handler |
|---|---|---|---|---|
| BLECH Clicker | GAMES | jeder Pad-Druck zählt eins hoch, der Kristall wackelt; der Stand bleibt über `korg.store` | 1720 Byte | 1041 Einheiten, 0,20 ms |
| Set-Timer | TOOLS | große Uhr mm:ss, ab einer Stunde h:mm:ss; Taste 1 startet, Taste 4 setzt zurück (zweimal drücken) | 1996 Byte | 2434 Einheiten, 0,46 ms (Bildaufbau); ohne Änderung 201, geschlossen nichts je Rahmen |
| Snake | GAMES | Part links und rechts drehen | 1180 Byte | 2215 Einheiten (das Öffnen), Rahmen 537 |
| Tetris | GAMES | Part links und rechts bewegen, Edit rechts dreht, Edit links gehalten lässt schneller fallen, jede Taste startet nach Game Over neu | 3772 Byte | 2305 Einheiten, 0,44 ms |
| Game of Life | GAMES | das Touchpad setzt Zellen, Taste 1 startet und pausiert (LED), Taste 2 ein Schritt, Taste 3 löscht, Taste 4 füllt zufällig | 2944 Byte | 2457 Einheiten, 0,47 ms |
| Pong | GAMES | Paddel mit dem Touchpad (Höhe des Fingers), Part links hoch, Part rechts runter, Encoder; wer zuerst 9 hat, gewinnt; Ball und Bot ziehen jeden zweiten Rahmen, ein kurzer Schweif hält die letzten zwei Ballpositionen sichtbar | 2304 Byte | 1224 Einheiten, 0,23 ms |
| Simon | GAMES | die 16 Pads leuchten eine Folge vor (ein Schritt 0,72 s, alle vier Runden etwas kürzer, nie unter 0,4 s), man spielt sie nach, jede Runde einen Schritt mehr; das Display zeigt Runde, Schritt und was zu tun ist; ein falsches Pad beendet das Spiel, TAP oder ein Pad startet neu | 2268 Byte | Rahmen höchstens 1673 Einheiten (Spielende), das Öffnen 1644 |
| Mandelbrot | GAMES | ein Finger auf dem Touchpad verschiebt, Part rechts und Encoder zoomen hinein, Part links hinaus, Taste 1 und 2 stellen die Iterationen (8 bis 64), TAP setzt zurück | 3452 Byte | 2441 Einheiten, 0,46 ms |
| GIF Player | TOOLS | spielt `GIF00.E2G` bis `GIF99.E2G` von der Karte ab: der Encoder wählt die Datei, Part links und rechts halbieren und verdoppeln das Tempo (25 bis 400 %), TAP hält an; fehlt die Datei, sagt er es. Zum Ausprobieren von Animationen am Display, ein Bild steht mindestens einen Rahmen (40 ms) | 972 Byte | Rahmen 3762 Einheiten, rund 0,72 ms (Bild allein 3086), über der Warnschwelle von 0,5 ms |
| Image Viewer | TOOLS | zeigt die Bilder einer Datei `GIF00.E2G` bis `GIF99.E2G` einzeln, etwa mehrere BMPs, die `tools/gif/gif2e2g.py` in eine Datei gelegt hat: Part rechts und links blättern vor und zurück, nach dem letzten Bild kommt wieder das erste, der Encoder wählt die Datei. Oben links steht nach jedem Wechsel zwei Sekunden lang die Nummer (`2/3`, die Gesamtzahl erst, wenn er einmal durch ist), TAP lässt sie stehen oder blendet sie aus. Rückwärts vom ersten Bild zum letzten geht erst, wenn er die Zahl kennt, denn die Laufzeit sagt sie nicht vorher | 1128 Byte | Tastendruck höchstens 4414 Einheiten (über das letzte Bild hinaus: zwei Lesevorgänge und das Bild), rund 0,84 ms hergeleitet, über der Warnschwelle von 0,5 ms |

**Set-Timer** ist für den Einsatz im Set gedacht. Die Uhr ist `korg.millis()`, die die Laufzeit in jedem Rahmen
nachführt, auch wenn die App geschlossen ist. Er abonniert nur `play`, die Tasten und `open` und `close`: geschlossen
kostet er je Taste ein paar Operationen und je Rahmen nichts (`frame` bekommt eine App nur, solange sie offen ist), offen
zeichnet er nur die Ziffern neu, die sich geändert haben. Das erste PLAY (der Übergang des Transports auf Play) startet
ihn, danach zählt er einfach weiter: PLAY und STOP ändern nichts, er ruft nie `korg.play`, `korg.stop` oder
`korg.led` und liest die Pads nicht. Die Tasten 1 und 4 gelten nur bei offener App. Nach dem Zurücksetzen wartet er
wieder auf ein PLAY, das ein STOP davor braucht (das Ereignis kommt beim Übergang). Er kennt keinen Speicher: nach dem
Ausschalten und im Menü auf OFF gestellt zählt er nicht, ein Neustart beginnt bei 0.

**Game of Life** rechnet eine Zeile des Felds (32 Zellen) als eine 32-Bit-Zahl und die nächste Generation für alle 32
Zellen einer Zeile gleichzeitig mit Bitoperationen. Wenige Änderungen werden als einzelne Zellen gezeichnet, dichte
Doppelzeilen als Bitmap. Berechnen und Zeichnen teilen sich das Rahmenbudget; die nächste Generation wird erst
nach dem vollständigen Bild übernommen ([Messung](messungen/2026-10-19-pong-life.md)). **Mandelbrot** rechnet mit 14 Nachkommabits (1,0 ist 16384). Eine Arbeitsliste enthält offene Rechtecke.
Nachweislich innenliegende Rechtecke werden einmal gefüllt; unklare Rechtecke werden geteilt, bis ihre Pixel
berechnet werden. Die Ausgabe hat von Anfang an die Zielauflösung 128 mal 64. Es gibt keine geschätzten
Großpixel und keine vier Verfeinerungsdurchgänge. Ein angefangener Pixel läuft im nächsten Rahmen weiter.
Die Liste wird bei jeder Ansichtsänderung neu aufgebaut; Ergebnisse anderer Ansichten werden nicht gespeichert.

In der gemessenen Gesamtansicht erscheint der weiße Mittelpunkt nach sieben statt 35 Rahmen. Das Fertigrechnen
braucht 2594 statt 3065 Rahmen. Eine vollständig innenliegende Zoomansicht wird in einem Rahmen gefüllt.
Das sind Messungen der JavaScript-Referenz, keine Gerätezeiten. Die Arbeitsreihenfolge kann einzelne Randdetails
später sichtbar machen ([Messung](messungen/2026-10-19-mandelbrot-arbeitsliste.md)). Die Zoomstufe geht bis 7,
tiefer reichen die 14 Bit nicht.

**BPM Glide** (Idee: [KrImZoR](https://www.instagram.com/krimzor_live)) ist keine App, sondern läuft im Hintergrund.
Kettet das laufende Pattern weiter (Chain To, CHAIN MODE an), gleitet das Tempo vom Tempo beim Start zum gespeicherten
Tempo des nächsten Patterns, verteilt über Länge mal Chain Repeat; der letzte Schritt erreicht das neue Tempo, der
Wechsel springt also nicht. Es liest die Kette beim ersten Schritt nach PLAY oder einem Patternwechsel, weil die Firmware
das neue Pattern erst dann im RAM hat. STOP setzt das Tempo zurück, mit dem das Pattern gestartet ist. Die Seite
BPM GLIDE im Menü BLECH schaltet es an (1) und aus (0), `korg.store` behält die Einstellung. Weil `korg.tempo` das
Tempo des Patterns im RAM setzt, gilt es bis STOP als ungespeicherte Änderung. Im Simulator geprüft
(`test/script-bpm-glide.test.mjs`), am Gerät nicht.

**Momentary Mute** (Wunsch aus der Community nach dem Vorbild des Korg ESX, [Idee 91](ideen/91-moment-mute.md)) braucht
API 15 und läuft im Hintergrund. Mutes ändern sich nur, solange PART MUTE gehalten wird: PART MUTE gehalten, schaltet ein
Pad seinen Part stumm oder wieder an, und die Pads zeigen die Mutes. PART MUTE losgelassen, spielen die Pads wie im Modus
TRIGGER und zeigen, was TRIGGER zeigt. Das macht alles die Firmware: PART MUTE schaltet ihren Pad-Modus schon beim Druck
um und hält ihn nach dem Loslassen (im Emulator gemessen). Das Plugin drückt beim Loslassen von PART MUTE mit
`korg.pressKey` TRIGGER für die Firmware, mehr nicht; es hält weder Tasten noch Pads. Die Taste TRIGGER leuchtet danach,
weil die Firmware im Modus TRIGGER ist. SHIFT + PART MUTE bleibt bei der Firmware, und wer bei gehaltenem PART MUTE eine
andere Modus-Taste drückt, bleibt in deren Modus. Die Seite MOMENT MUTE im Menü BLECH schaltet es an (1) und aus (0: PART
MUTE bleibt ein Modus wie ohne das Plugin), `korg.store` behält die Einstellung. Im Simulator
(`test/script-moment-mute.test.mjs`) und im Emulator (`tools/emu/plugin_catalog15_cases.py`, Hacktribe, rot, blau)
geprüft, am Gerät nicht.

**Filter Toggle** ([Idee 81](ideen/81-filter-schnellschalter.md)) war bis 2026-11-08 ein Plugin dieses Katalogs (API 14).
Seitdem ist es als FILTER TOGGLE fest in der Laufzeit des BLECH-Menüs eingebaut und braucht kein Plugin auf der Karte:
SHIFT + LPF, HPF oder BPF schaltet das Filter des gewählten Parts aus, dieselbe Kombination wieder an mit dem Typ, den die
Taste zuletzt hatte, SHIFT + eine andere Filtertaste gibt deren letzten Typ, je Part. Den Typ setzt die Firmware auf ihrem
eigenen Weg, mit ihrem Fenster "FILTER TYPE", auch auf der blauen. Der Schalter liegt unter BLECH > FEATURES > FILTER
TOGGLE ([Tastenkombinationen](tastenkombinationen.md), [Messung](messungen/2026-11-08-filter-toggle-eingebaut.md)). Im
Katalog steht es nicht mehr. Wer das alte Plugin noch auf der Karte hat: bei geschlossener App setzt es im nächsten Rahmen
denselben Typ, den FILTER TOGGLE schon gesetzt hat; bei offener App hält es SHIFT + Filtertaste von der Firmware fern, dann
schaltet nur das Plugin, ohne Fenster (**hergeleitet** aus dem Quelltext des Plugins, nicht gemessen). Am besten das
Plugin von der Karte nehmen oder FILTER TOGGLE ausschalten.

**Gate Hold** ([Idee 72](ideen/72-gate-arp-note-halten.md)) braucht API 15 und läuft im Hintergrund. Im Modus Gate Arp
bleibt die Note dort, wo der Finger das Touchpad zuerst berührt: `korg.touchLockX` hält das X fest, das die Firmware sieht,
Y bleibt das des Fingers. Bewegt sich der Finger danach, wählt X von links nach rechts den Gate-Arp-Rhythmus des Patterns
(die Seite GATE ARP im Pattern-Menü, 0 bis 49) mit `korg.seq.setPatternValue`. Finger weg setzt den Rhythmus zurück, den
das Pattern hatte, ein Patternwechsel mit Finger auf dem Pad merkt sich den des neuen Patterns. Den Touchpad-Modus führt
die Firmware, bis eine andere Modus-Taste kommt (im Emulator gemessen, [Messung](messungen/2026-11-03-plugin-api15.md)):
GATE ARP schaltet Gate Arp ein, MASTER FX und TOUCH SCALE beenden es, SHIFT + GATE ARP und SHIFT + MASTER FX öffnen nur
ihre Menüseite. Das Plugin folgt diesen Tasten; in Master FX und Touch Scale bleibt das Touchpad unberührt. Die Seite
GATE HOLD im Menü BLECH schaltet es an (1) und aus (0). Plugins laufen einmal je Bild (40 ms): bewegt sich der Finger
in den ersten 40 ms nach dem Aufsetzen, kann die Firmware diese Bewegung noch sehen (hergeleitet). Im Simulator
(`test/script-gate-hold.test.mjs`) und im Emulator (`tools/emu/plugin_catalog15_cases.py`, Hacktribe, rot, blau) geprüft,
am Gerät nicht.

**Key Pads** ([Idee 85](ideen/85-keyboard-tonart.md)) war bis 2026-11-07 ein Plugin dieses Katalogs (API 15). Seitdem ist
es als KEY PADS fest in der Laufzeit des BLECH-Menüs eingebaut und braucht kein Plugin auf der Karte: KEYBOARD gehalten +
Pad setzt den KEY (chromatisch in Pad-Reihenfolge: Pad 1 C, Pad 2 C# bis Pad 12 B, Pads 13 bis 16 wählen die Oktave der Tastatur, Pad 14 ist die nach dem Start), das
Wertefenster der Firmware zeigt ihn, der Schalter liegt unter BLECH > FEATURES > KEY PADS
([Tastenkombinationen](tastenkombinationen.md), [Messung](messungen/2026-11-07-key-pads-eingebaut.md),
[Belegung](messungen/2026-11-08-key-pads-chromatisch.md)). Im Katalog steht
es nicht mehr.

**Step Copy** braucht API 15 und läuft im Hintergrund. Es kopiert die Steps eines Takts (16 Steps) des Patterns, das läuft,
in einen anderen Takt, damit eine Figur nicht noch einmal eingespielt werden muss. Ein Pattern ist 1 bis 4 Takte lang. Drei
Seiten im Menü BLECH: STEP COPY FROM (Quelltakt, 1 bis 4), STEP COPY TO (Zieltakt 1 bis 4, 0 ist jeder Takt nach der Quelle
bis zur Länge des Patterns) und STEP COPY (1 kopiert den gewählten Part, 2 alle 16 Parts, 0 nichts). Kopiert wird, wenn das
Rad 0,6 s auf 1 oder 2 geruht hat, die Werte beim Drehen dazwischen kopieren nichts; zum erneuten Kopieren auf 0 und zurück
drehen. Kopiert wird je Step: an oder aus, die vier Notenplätze (also auch Akkorde), Velocity, Gate und Trigger, mit
`korg.read.patternBytes` und `korg.seq.writeSteps`. Ein Zieltakt hinter der Länge verlängert das Pattern bis dorthin
(`korg.seq.setPatternValue`, der Setter von LENGTH im Pattern-Menü), "jeder Takt danach" bleibt in der Länge. Ein Quelltakt
hinter der Länge oder derselbe Takt als Quelle und Ziel kopiert nichts. **Nicht kopiert:** die Motion Sequence (die API
liest Motion-Bytes, hat aber keinen Aufruf, der sie schreibt) und die Werte des Parts. Gespeichert wird nichts: WRITE
sichert das Pattern wie immer. Firmware: die hier gemessene Seitenliste ([Tastenkombinationen](tastenkombinationen.md))
kennt COPY PART (Part Util 1/4) und CLEAR SEQUENCE, aber kein Kopieren eines Takts innerhalb eines Patterns. Im Simulator
(`test/script-step-copy.test.mjs`) und im Emulator (`tools/emu/plugin_catalog15_cases.py`, Hacktribe, rot, blau) geprüft,
am Gerät nicht.

**303Pattern** (von Crank, aus dem BLECH-Discord) ist eine App unter TOOLS. Sie erzeugt aus einer von 14 Skalen ein zufälliges
16-Schritt-Pattern mit Accent-, Slide- und Tie-Steps (der Algorithmus des Pattern303 VST), leuchtet die Pads der Steps mit Note
und schreibt das Pattern in den Sequencer. Steps lassen sich sperren, ein neues Pattern lässt sie dann in Ruhe; der Regler setzt
die Gate-Länge, ein Menü in der App hält Skala, Grundton, Dichte, Slide, Tie und Accent. Im Simulator durch Kompilieren geprüft, nicht am Gerät.

**EUCLID FLOW** (von SLTK023, aus dem BLECH-Discord) ist eine App unter TOOLS, ein euklidischer Rhythmusgenerator: Er verteilt
eine Zahl von Schlägen so gleichmäßig wie möglich auf die Steps des Patterns (16 bis 64, nach seiner Länge), verschiebt sie um
die Rotation und schreibt sie mit TAP in den gewählten Part, auf dem Grundton des Patterns mit Velocity 100 und Gate 96. Vorher
schaltet er alle Steps des Parts aus. Im Katalog reagieren die Tasten nur bei offener App: die Handler einer App laufen vom Start
an, und TAP bei geschlossener App hätte sonst den Part überschrieben. Im Simulator geprüft (`test/script-community-catalog.test.mjs`), nicht am Gerät.

**LIVE RELOAD** (von handst0n3, aus dem BLECH-Discord) ist eine App unter TOOLS. SHIFT + 1 setzt die Klangwerte aller 16 Parts
auf den gespeicherten Stand des Patterns zurück, ohne die Wiedergabe anzuhalten, SHIFT + 2 blendet die Regler-Werte (Cutoff,
Resonance, EG Int, Attack, Decay, Level, Pan) in drei Stufen dorthin. Gelesen wird mit `korg.read.patternValue`, geschrieben mit
`korg.seq.setPartValue`. Sample, IFX an und Typ, Voice Assign und MFX Send bleiben, wie sie sind. Ein Patternwechsel bricht ab.
Im Simulator geprüft, laut Autor am Gerät.

**RANDOM SLOT** (von handst0n3, aus dem BLECH-Discord) ist eine App unter TOOLS: ein Zufallsgenerator mit Spielautomat für einen
Part. Die Pads wählen den Part (`korg.padHold`, solange die App offen ist), 1 würfelt Klangwerte, 2 eine Melodie über 64 Steps,
3 und 4 ändern Klang oder Steps ein wenig. PART MUTE schaltet den Part solo und stellt die Mutes danach wieder her. Gespeichert
wird nichts. Im Simulator geprüft, laut Autor am Gerät.

**Better Accent** (von alarykko, aus dem BLECH-Discord, nach dem TD-3-MO) läuft im Hintergrund unter TOOLS. Ein Step mit
Velocity über 96 ist ein Accent: beim `step` schreibt es für diesen Part die Accent-Werte von EG INT, DECAY und LEVEL, bei
einem Step darunter die normalen. SHIFT + EG INT, DECAY oder LEVEL setzt die Accent-Werte des gewählten Parts
(`korg.knobHold` hält die drei Regler dann von der Firmware fern), ohne SHIFT merkt es sich die normalen Werte. STOP stellt
die normalen Werte wieder her. Es wirkt nur auf die Parts 1 bis 7 (`maxParts = 7`): mit allen 16 lief der Step-Handler laut
Autor in den Watchdog. Ein WRITE während eines Accents speichert die Accent-Werte. Im Simulator geprüft, laut Autor am Gerät.

**Easy Slides** (von alarykko, aus dem BLECH-Discord) läuft im Hintergrund unter TOOLS: ein TIE-Step (Gate über 96) und der
Step danach bekommen 35 mehr Glide, die zwei Noten gleiten ineinander. SHIFT + PITCH/GLIDE setzt das Grund-Glide des
gewählten Parts, STOP stellt es wieder her. Im Katalog wirkt es nur auf die Parts 1 bis 8, deren Glide es sich beim Start und
bei einem Patternwechsel merkt (`maxParts = 8`): das Original schrieb bei jedem Step auch die Parts 9 bis 16 und setzte
deren Glide auf 0. Im Simulator geprüft (`test/script-community-catalog.test.mjs`), laut Autor am Gerät.

**PLAY-Takt** braucht API 11 und läuft im Hintergrund. Solange der Sequencer läuft, blinkt die PLAY-LED (rot und blau) im
Tempo des Patterns: das Ereignis `beat` macht sie auf jeder Viertel an, `korg.afterSteps(2, ...)` zwei Schritte später aus,
mit BEAT 8 also auf jeder halben Note. Bei STOP und in der Pause leuchtet sie ruhig; `korg.cancel` räumt dann den Timer ab.
In der Pause blinkt die Firmware die PLAY-LED selbst, das Plugin setzt sie dort in jedem Rahmen wieder an: im Emulator
bleibt sie danach höchstens einen Umlauf der LED-Matrix dunkel (5,5 ms im Modell von `tools/emu/panel_leds.py`), bei STOP
bis zum nächsten Rahmen (40 ms). Es ist zugleich das Beispiel des Katalogs für die Timer. Im Simulator
(`test/script-play-takt.test.mjs`) und im Emulator (`tools/emu/timer_cases.py`, Hacktribe) geprüft, am Gerät nicht.

## Die Seite Plugins im Editor

Der Eintrag Plugins hat vier Seiten: Katalog, Meine Plugins, Editor und Dokumentation. Der Titel in der
Brotkrumenleiste führt immer zurück zum Katalog.

**Katalog:** die Plugins der App als Karten (die Apps BLECH Clicker, Snake, Tetris, Game of Life, Pong, Simon
und Mandelbrot unter GAMES, Set-Timer, GIF Player und Image Viewer unter TOOLS, dazu Lauflicht, Pulsieren, PLAY-Takt, Momentary Mute, Gate Hold, Step Copy, 303Pattern, EUCLID FLOW, LIVE RELOAD, RANDOM SLOT, Better Accent und Easy Slides (TOOLS), Quelle
`data/script/presets.mjs`). Jede Karte zeigt das Display des Plugins nach ein paar Rahmen, darunter Titel,
Kategorie, Beschreibung und Ersteller. Die ganze Karte führt auf die Seite des Plugins: Bild oben links, daneben Titel, Beschreibung und die Details (Kategorie, Ersteller, Datum, Steuerung), dazu
Herunterladen, Aufs Gerät und „Als eigenes Plugin öffnen“. Darunter schalten „Vorschau“ und „Code“ zwischen dem
laufenden Plugin auf der Zeichnung der Electribe und seinem Quelltext. Ein neues Plugin kommt per Pull Request auf
GitHub in den Katalog, mit seinem Eintrag in `data/script/presets.mjs`.

**Meine Plugins:** die Plugins dieses Browsers als Karten wie im Katalog, dazu Neues Plugin, Öffnen und
Alle speichern. Eine Karte öffnet das Plugin im Editor.

**Editor:** der Editor über die ganze Seite, mit Zeilenspalte und dem Ergebnis des Übersetzens (Fehler mit
Zeile und Spalte, ein Klick setzt den Cursor dorthin). Öffnen und Speichern stehen oben rechts in der Leiste,
unter dem Editor Vorschau, Herunterladen und Aufs Gerät. Die Vorschau legt sich über den abgedunkelten Editor;
ein Klick daneben oder das X schließt sie.
Die Konsole ist ein eigener Eintrag unter Gerät. Eigene Plugins liegen im Browser (`localStorage`)
und verlassen ihn nicht. Ein Plugin-Name ist der Blockname: ASCII, ein Buchstabe
am Anfang, höchstens 15 Zeichen.

**Neues Plugin:** fragt nach dem Namen und dann nach der Art. „App in GAMES“ und
„App in TOOLS“ legen eine App mit `korg.app(name, gruppe)` an, „Hintergrund“ ein Plugin
ohne Display und ohne Menüeintrag. Der gewählte Name ist auch der Name der App im Menü
BLECH. Jede Vorlage ist ein kurzes, lauffähiges Plugin mit den Handlern `frame` und
`buttonPress` (die Apps zusätzlich mit `open`), Namen wie `korg.key.TAP` und ein paar
deutschen Kommentaren. Die Quelle ist `data/script/templates.mjs`;
`test/script-templates.test.mjs` übersetzt jede Vorlage, lässt sie die Probe bestehen
(mit ein paar TAP-Drücken laufen alle Zeilen) und prüft, dass sie den Namen und die
Gruppe anmeldet.

**Der Editor** ist CodeMirror 6 (`site/app/script-editor.mjs`). Das Paket liegt fertig
gebaut in `site/vendor/codemirror.mjs`, die Seite lädt nichts aus dem Netz und
läuft auch offline in der App. Neu bauen: `npm install`, dann `npm run build:codemirror`
(`tools/build-codemirror.mjs`; esbuild und die CodeMirror-Pakete sind Entwicklungsabhängigkeiten,
die Lizenztexte liegen in `site/vendor/codemirror.LICENSE.txt`, siehe NOTICE). Er kann:

- **Farben und Zeilennummern:** JavaScript-Wörter, Texte, Zahlen und Kommentare, `korg` und
  die Namen nach `korg.key.` und `korg.led.` abgesetzt (`src/script/highlight.mjs`, ein kleiner
  Tokenizer statt der JavaScript-Grammatik, das spart knapp 100 KiB). Die Farben sind die Tokens
  des Designs. Die Zeilennummern zeigen wie bisher die Probe: grün gelaufen, gelb nie gelaufen,
  rot Fehler. Ein Beispiel-Plugin ist schreibgeschützt (`aria-readonly`), man kann
  darin markieren und kopieren.
- **Vervollständigung:** tippt man `korg.disp`, bietet der Editor alle Funktionen an, die so
  anfangen, jede mit ihren Parametern, einem deutschen Satz, den erlaubten Bereichen und
  der Angabe, wo sie aufgerufen werden darf (aus dem `events`-Eintrag des Vertrags). Enter
  setzt den Aufruf mit seinen Parametern als Felder ein, Tab springt zum nächsten. Nach
  `korg.key.` und `korg.led.` kommen alle Namen mit Nummer und Bezeichnung, in
  `korg.onEvent("` alle Ereignisse mit den Werten ihres Handlers (Enter setzt den
  Handler gleich mit ein), im zweiten Argument von `korg.app` die Gruppen. Im Objektbaum kommen nach
  jedem Punkt die Namen, die dort weitergehen: nach `korg.menu.blech.` die Zweige darunter, an einem Blatt
  sein Bereich, ob es sich setzen lässt und ab welcher API-Version es da ist. Die Timer (`korg.after`,
  `korg.every`, `korg.afterSteps`) setzen gleich einen Pfeil `() => { }` ein, in den man schreibt.
  Strg+Leertaste ruft die Liste von Hand, Escape schließt sie.
- **Parameterhinweis und Hover:** steht der Cursor in einem Aufruf, zeigt ein Hinweis über
  dem Cursor die Schreibweise und den Parameter, den man gerade tippt, mit seinem Bereich.
  Fährt man mit der Maus über einen Namen, eine Ereignisbezeichnung oder einen Handler-Wert,
  steht dort dieselbe Beschreibung; über einer Zahl, die nach Taste oder LED aussieht,
  steht ihr Name.
- **Fehler im Text:** der Fehler des Übersetzers wird im Text unterstrichen (Zeile und Spalte
  des Fehlers), unter dem Editor steht er weiter als Liste, ein Klick setzt den Cursor hin. Das gilt
  beim Tippen auch für den Objektbaum: ein falsch geschriebener Pfad, ein Blatt, das sich nicht setzen
  lässt, und ein fester Wert außerhalb des Bereichs (`...display.intensity = 300`) sind rot, mit derselben
  Meldung wie beim Übersetzen.
- **Tastatur:** Tab verlässt den Editor (er fängt Tab nicht ab, damit niemand darin
  stecken bleibt), eingerückt wird mit Strg+] und Strg+[ (am Mac Cmd statt Strg), rückgängig mit Strg+Z. Der Editor
  hat die Beschriftung „Plugin-Code“, die Vervollständigung ist eine Liste, die Hilfsmittel
  vorlesen.

**Woher die Texte kommen:** die Funktionen, Ereignisse und Werte stehen in
`data/script/contract.mjs`, ihre deutschen Beschreibungen in `data/script/describe.mjs`,
die Namen der Tasten und LEDs in `data/script/names.mjs`, der Objektbaum in `data/script/objects.mjs`. `src/script/editor-model.mjs` macht daraus
Vervollständigung, Hinweis und Hover als reine Funktionen von Text und Cursor
(`test/script-editor-model.test.mjs`). `test/script-describe.test.mjs` schlägt fehl, wenn
eine Funktion oder ein Ereignis des Vertrags keine Beschreibung hat: wer einen Eintrag
in den Vertrag aufnimmt, schreibt den Satz dazu. Ein neues Blatt des Objektbaums steht ohne weiteres in der
Vervollständigung; ein Test geht jedes Blatt Punkt für Punkt ab.

**Vorschau** (`src/script/sim.mjs`): ein simuliertes Gerät auf der Referenz-VM mit
Display (128 mal 64, Vorschau-Schrift, nicht die der Firmware), LED-Buch und
Millisekundentakt, ein Rahmen alle 40 ms. Tasten, Pads, Regler, Encoder und
Touchpad schicken ihre Ereignisse an die Laufzeit. Das Display zeigt, was das Gerät
zeigen würde: das Bild der offenen App oder des Plugins, das das Display nahm, sonst
nichts (am Gerät steht dort der Hauptbildschirm der Firmware). Hat das Plugin eine App,
öffnet die Vorschau sie wie ENTER im Menü; unter dem Display stehen die Apps wie im Menü
BLECH ("GAMES > Snake: öffnen") und eine Taste EXIT, die wie am Gerät die App schließt,
bevor das Plugin die Taste sieht. Das ist nicht die Firmware: ihr Zeitverhalten zeigt
die Vorschau nicht (im Browser gilt nur das Rechenbudget, kein Zeitlimit). Die Laufzeit in
der Firmware läuft im Emulator, siehe Stand.

**Eingaben und Probe:** Aufnehmen speichert die Eingaben mit ihrem Rahmen beim
Plugin, Proben lädt den Block in ein frisches simuliertes Gerät, spielt die
Eingabefolge ab (mindestens 100 Rahmen) und sagt, welche Zeilen mit Code nie
gelaufen sind. Hat das Plugin eine App, öffnet die Probe sie zuerst. Ohne Eingaben
laufen nur `ready`, `open` und `frame`.

**Export:** `.blech` (ein Plugin mit Quelltext) und `e2sPlugin.all` (alle eigenen
Plugins) gibt es erst nach einer Probe genau dieses Textes (`src/script/gate.mjs`).
Jede Änderung am Text wirft die Probe weg. Bleiben Zeilen ohne Lauf, fragt die
Seite einmal nach und nennt sie. Ein Fehler in der Probe sperrt den Export.

**Konsole:** `run("name")` startet ein eigenes Plugin oder eines aus dem Katalog in der
Vorschau; eine Zeile, die mit `korg.` beginnt (zum Beispiel
`korg.display.text("Hi", 0, 0)`), läuft dort als Plugin-Code sofort einmal, als App
„einzeiler“ in TOOLS, die die Vorschau öffnet.
Alles andere ist wie bisher JavaScript mit `KORG` für den Emulator. Die Konsole spricht immer mit dem
Emulator, `start` schaltet ihn ein. Der Schalter „An echtes Gerät weiterleiten“ oben rechts lässt ein
Skript nach bestandener Probe im Emulator an die verbundene Electribe gehen.

## Stand

Marker wie in den Messungen: gemessen, hergeleitet, offen.

### Im Emulator

Alles hier lief in der echten Firmware (2.02 mit Hacktribe) im Emulator mit
virtueller Karte oder in Unicorn ohne Firmware, nicht am Gerät.

- Compiler, Prüfer und Referenz-VM in JavaScript (`src/script/`), die Seite
  Plugins mit Lauf, Probe und Export (`site/app/scripts.mjs`), Tests in
  `test/script-*.test.mjs`. Blockformat 2, API Version 25
  (`data/script/contract.mjs`).
- ARM-VM (`tools/patch/script_vm.s`): alle 34 Opcodes, 506 Vergleichsfälle gegen
  die JS-VM stimmen ([Messung](messungen/2026-10-14-skript-arm-vm.md)).
- Eingangsfilter (`0xC002837C`) und Rahmenhaken (`0xC00836FC`,
  `tools/patch/script_hooks.s`): Ring mit 64 Plätzen, 25 Hz, gemeinsames Budget von
  5 ms, ein Fehler schaltet nur das auslösende Plugin ab, die Firmware bleibt
  bedienbar ([Messung](messungen/2026-10-14-skript-haken.md)).
- `korg.led` (`tools/patch/script_led.s`): im Firmwarelauf sendet `ready` den
  Nullwert einmal, ein Tastendruck 255 und 0 je ein Paket, alle 88 LEDs auf einmal
  ergeben 88 Pakete ([Messung](messungen/2026-10-14-skript-led.md)).
- Display (`tools/patch/script_display.s`): 70 Fälle Byte für Byte gleich dem
  Browsermodell, auch das Fehlerbild, Menüs der Firmware bleiben sichtbar
  ([Messung](messungen/2026-10-14-skript-display.md)).
- Kartenlader (`tools/patch/script_card.s`): eine Datei mit zwei Blöcken lädt und
  läuft, ein einzelner kaputter Block wird übersprungen. Falsche Prüfsumme, falsche
  Kennung, eine abgeschnittene Datei und EXIT beim Einschalten lassen die Firmware
  wie im Original starten ([Messung](messungen/2026-10-14-skript-karte.md)).
- Dauerhafte Werte (`tools/patch/script_store.s`): ein Zählerstand übersteht Aus-
  und Einschalten über die virtuelle Karte
  ([Messung](messungen/2026-10-14-skript-speicher.md)).
- Steps schreiben (`tools/patch/script_seq.s`): ein Plugin schreibt Steps in Part 1, während das Pattern läuft, und der
  Sequencer spielt sie (MIDI-Ausgang des Emulators: die Noten in der Reihenfolge der Steps), die Bytes im Pattern sind die
  des Browsermodells, die Pads zeigen danach die geschriebenen Steps; am Gerät nicht gehört
  ([Messung](messungen/2026-10-26-plugin-steps.md)).
- Uhr, Lesen, Handeln, Sequencer-Ereignisse, Hintergrundlicht und LED-Sperre
  (`tools/patch/script_hw.s`, `tools/patch/script_events.s`). Befund: die Firmware
  kennt für Mute nur Umschalten, `korg.mute` liest darum den Zustand zuerst
  ([Messung](messungen/2026-10-14-skript-hardware.md)).
- Snake läuft als App aus dem Menü: 150 Rahmen in der Firmware, das Display-RAM ist
  danach Byte für Byte gleich dem Browsermodell, `frame` braucht höchstens 0,103 ms
  ([Messung](messungen/2026-10-14-skript-snake.md), [Apps](messungen/2026-10-14-plugin-apps.md)).
- Apps und Display (`tools/patch/script_app.s`, [Messung](messungen/2026-10-14-plugin-apps.md)):
  das Laden ändert das Display nicht, eine App öffnet im Menü unter GAMES oder TOOLS und
  zeichnet erst dann, EXIT schließt sie und der Hauptbildschirm ist danach Pixel für Pixel
  der eines Geräts ohne App, EXIT lässt sich nicht abfangen (App und `korg.display.take()`),
  ein Plugin ohne Display zeichnet nichts.
- Blechy ist in BLECHTRIBE eingebaut, die letzte Seite des Rings: im Emulator ohne Karte geladen, winkt nach etwa einer
  Sekunde einmal je Landung, geht dann über das Display, redet an den Rändern, antippen, streicheln, bei PLAY in die Mitte,
  zuhören und Schranz, EDIT und EXIT blättern weg, mit EXIT beim Einschalten fehlt er; der teuerste Rahmen braucht 0,40 ms
  ([Messung](messungen/2026-10-15-blechy.md)).
- Menü BLECH (`tools/patch/script_menu.s`): zwei Ebenen mit Gruppen, Zähler und Schild je
  Gruppe, EXIT geht eine Ebene zurück, WRITE, MENU als ENTER, Einstellungen, Plugin-Seiten,
  Apps, EXPORT ALL PLUGINS und SET INIT PATTERN in DATA UTILITY, PLUGIN RUNTIME in GLOBAL PARAMETERS, SYNC GROUP
  hinter CHAIN REPEAT, die Liste in MANAGE PLUGINS, fremde Plugins, `korg.menu.add`; jede Seite ist ohne dritte
  Zeile gezeichnet, ein Fall prüft alle auf Überlappung
  ([Messung](messungen/2026-10-14-blech-menue.md)).
- Firmwaredatei: das Patch-Set `data/patches/blech.json` (Startbild-Editor, MFX 2,
  Plugin-Laufzeit mit Menü, Kartenordner `blechtribe`, Blech-Startbild) ist gebaut
  und im Emulator geprüft ([Gerätedatei](geraetetests/blech-datei.md)).

Der Platz im Abbild: VM und aller Code der Laufzeit ab `0xC0150300`, Laufzeit ab `0xC01AE000`, Pool
`0xC01D7000` bis `0xC01F7000`, alles in dem Bereich, der in den eigenen Abbildern
FF ist (offline gemessen). Der Block von Blechy liegt außerhalb davon bei `0xC0184000`
(12668 Byte), im FF-Lauf `0xC01720B0` bis `0xC01A0000`, in dem auch der Patternwechsel und
der Ladebalken liegen; dort ist am Gerät noch nichts geprüft.

### Am Gerät

Die Firmwaredatei mit der Laufzeit läuft am eigenen Gerät. Das Menü BLECH, das Laden aus
PLUGIN EDIT, EXPORT ALL (bis 1.3.7 so benannt und unter PLUGINS, seit 1.3.8 MANAGE PLUGINS und EXPORT ALL PLUGINS
in DATA UTILITY; die neue Anordnung ist am Gerät noch nicht bedient) und `korg.store` haben dort Dateien auf der Karte gelesen und geschrieben
(`e2sPlugin.all`, `store.a.bin`, `store.b.bin`), die Anpassung, die Seiten von FEATURES und
SPLASH IMPORT und DRAW sind am Gerät bedient. Die Wünsche aus diesen Tests stehen in den Messungen
ab dem 18.10. ([Plugin bleibt aus](messungen/2026-10-18-plugin-bleibt-aus.md),
[Importliste](messungen/2026-10-19-plugin-import-liste.md),
[Sync und Menüs](messungen/2026-10-22-sync-und-menues.md)). Was eine Messung nur im Emulator
gespielt hat, sagt sie selbst. Die Schrittlisten für einen eigenen Test:
[Kartentest](geraetetests/karte.md) und [Firmwaredatei](geraetetests/blech-datei.md).

### Offen

- **Am Gerät nicht eigens gemessen:** die Zeit je Rahmen gegen das Budget von 5 ms
  (hergeleitet etwa 0,17 ms je Snake-Rahmen), ein Hörtest auf Aussetzer bei Musik und
  Snake, das Hintergrundlicht auf Batterie mit Power Save "Auto", die LED-Sperre.
- **Timer3:** die Periode von einer Sekunde ist im Emulator gemessen, am Gerät nicht
  gelesen.
- **Haken `save`:** im Emulator eingehängt, dort aber nicht ausgelöst (WRITE auf
  Global schreibt Flash). Die Wirkung ist nur im Unit-Test geprüft.
- **Karte:** ein Schreibvorgang auf einer echten Karte kann länger als ein Rahmen
  dauern, gemessen ist das nicht. Gegen gleichzeitigen Kartenzugriff der Firmware
  schützt nur der offene Hauptbildschirm. Was die Firmware tut, wenn
  `KORG/blechtribe/` auf der Karte fehlt, ist im Emulator nicht gespielt.
- **Echte `e2sSample.all`:** der Kartenlader wird im Test nicht mit einer echten
  Datei gespielt, weil keine Korg-Daten im Repository liegen dürfen. Der Haken sitzt
  an der Stelle, die ein früherer Prototyp mit einer echten Datei gemessen hat
  ([Recherche zur virtuellen SD](hintergrund/virtuelle-sd.md)).
- **LEDs:** die Grenze von 400 Paketen je Sekunde gilt nur bei etwa 25 Hz Aufrufen
  des Rahmens, ein dauerhaft abgelehnter Index blockiert die übrigen LEDs ohne
  Meldung, und das Ausschalten der Interrupts setzt einen privilegierten Modus
  voraus ([Messung](messungen/2026-10-14-skript-led.md)).
- **Menü:** kein Schalter für das Startbild, lange Namen werden abgeschnitten, die Liste
  von MANAGE PLUGINS zeigt höchstens 64 Plugin-Dateien und sagt mit LIST FULL, wenn es mehr gibt
  ([Messung](messungen/2026-10-14-blech-menue.md), [64 Dateien](messungen/2026-10-30-plugin-liste-64-entfernen.md)); wie lange das Öffnen mit vielen Dateien
  am Gerät dauert, ist offen (im Emulator 0,9 s bei 64).
- **Seiten in GLOBAL PARAMETERS und DATA UTILITY:** sie sind Seiten des Bildschirms BLECH, die EDIT an den Rändern
  der Firmware-Seiten erreicht (Haken auf die Slots EDIT links und rechts von Bildschirm 9 und 15). Die Funktionsliste
  von DATA UTILITY selbst ist eine Zustandsmaschine mit einer Sprungtabelle von 40 Zuständen in einer einzigen Funktion
  (`0xC0061A24`); Seiten darin wären eigene Zustände, ein eigener Auftrag
  ([Messung](messungen/2026-10-14-blech-menue.md), Abschnitt "DATA UTILITY").
  `e2sCustom.all` von EXPORT ALL CUSTOMIZATIONS liest beim Start noch nichts; einen Lader dafür gibt es nicht.
- **Apps am Gerät:** das Öffnen und Schließen, der Neuzeichner des Hauptbildschirms
  (Byte `0xC06C226C`) und die Tasten der offenen App sind nur im Emulator gespielt.
- **Format 2:** der Aufschlag der 16-Bit-Operanden ist hergeleitet (Abschnitt
  "Format 2 und die Kosten"), in den genannten Messungen nicht gesondert
  nachgemessen.

### Quelltext

Im Quelltext und in den Tests heißt das Ganze noch `script`: `src/script/`,
`data/script/`, `site/app/scripts.mjs`, `tools/patch/script_*.s`. `korg.*` ist die
Schnittstelle. Messungen tragen `skript` im Dateinamen
(`docs/messungen/2026-10-14-skript-*.md`). Auf dem Gerät, im Editor und in der
Doku heißt es Plugin.
