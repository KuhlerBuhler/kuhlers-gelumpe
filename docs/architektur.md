# Architektur

Wie der Editor Änderungen prüft und zum Gerät bringt. Die Karte der Felder steht
in [geraetekarte.md](geraetekarte.md), der Linter in [linter.md](linter.md), die
Grundlagen der Patches in [patcher.md](patcher.md).

## Bauweise

Eine statische Seite ohne Server, verteilt nur als App (Tauri). Die App lädt die Seite
und startet den Emulator-Dienst selbst.

- Die Electribe hängt am Rechner, das MIDI läuft im Browser über Web MIDI mit SysEx.
  Das braucht Chrome oder Edge auf dem Desktop, Safari kann es nicht.
- Die Firmware kommt von der eigenen Platte und verlässt den Rechner nie. Es
  liegt nirgends Korg-Firmware auf einem Server.
- Der Kern in `src/` läuft ohne Node-Bibliotheken im Browser, mit Ausnahme von
  `src/node.mjs`. Die Simulation kann sich als MIDI-Port ausgeben.

## Drei Wege aufs Gerät

Die Oberfläche trennt sie, weil sie sich verschieden anfühlen und verschieden
lange halten.

| Weg | Hält | Wofür |
|---|---|---|
| Live ins RAM | bis zum Ausschalten | FX ausprobieren, Expertenmodus für Firmware-Felder |
| Pattern senden | bis zum nächsten Pattern-Wechsel, dauerhaft erst mit Write am Gerät oder über die Backup-Datei | Patterns, Expertenmodus für Pattern-Felder |
| Firmware schreiben | dauerhaft | alles, was in der Firmware liegt |

Dazu kommt Laden und Speichern der Backup-Dateien `.e2sallpat` ganz ohne Gerät.
Patterns und Globals gehen über Korgs eigene Nachrichten und brauchen weder
Hacktribe noch eine Firmware-Datei. RAM- und Firmware-Funktionen gibt es nur, wenn
das Gerät eigene Befehle dafür kennt: BLECHs (`0x60` bis `0x63`, auch auf Korgs
Original) oder Hacktribes (`0x52` bis `0x57`). Ohne beide kommt Schweigen, darum wird
bei der Gerätesuche zuerst BLECHs INFO gefragt, dann Hacktribes Lesen, und die
Funktionen werden sonst ausgeblendet. Flash lesen und Code ausführen gibt es nur über
Hacktribe, und der Effekt-Editor braucht Hacktribes Preset-Tabellen, nicht nur das RAM.

**Modulationsarten (Seite Modulationen).** Die Seite ändert Name, Vorgabe-Tiefe, Vorgabe-Speed,
Kurve und die Slots 0 bis 4 der 72 Modulationsarten auf einer Kopie der geladenen Firmware. Sie
schreibt nur in die Tabellenkopie, die die Firmware liest, und welche das ist, entscheidet
`src/modtable.mjs` am Abbild (siehe [geraetekarte.md](geraetekarte.md)). Die Kopie geht durch
dieselbe Prüfung im Emulator wie beim Patcher, mit genau den geänderten Bytes als erlaubten
Läufen, und wird erst danach zum Download angeboten. Für die Vorgaben gibt es keinen Weg live ins RAM: beim
Einschalten füllen die Vorgaben einen Speicher je Part und Art, ein Schreiben in die Tabelle
wirkt danach nicht mehr (`measure:2026-10-14/offene-fragen`). `test/emulator-modtable.test.mjs`
hält am Emulator fest, dass eine geänderte Vorgabe am Part ankommt und eine Änderung der
ungelesenen Kopie nicht, und dass die Stärke eines geänderten Slots so am Part ankommt, wie die
gemessene Rechnung sie ergibt. Das Byte "Ziel" liest die Firmware nie, die Seite zeigt es nur als Etikett
und schreibt es nicht (`exportModTypes` lehnt eine Änderung ab). Was eine Art moduliert, steht in den
Slots: Quelle (Hüllkurve, LFO, aus), Ziel (Pitch, OSC, Filter, Level, Pan, IFX, die Codes 4 bis 7 nur als
Expertenwerte mit dem Hinweis, dass ihre Wirkung am Klang offen ist), Stärke von und bis (-63 bis 63) und
ein Schalter, ob die Tiefe MOD. DEPTH folgt ([Stufe 2](messungen/2026-10-15-modulation-stufe2.md)). Die Kurve
ist eine Auswahl der sieben gemessenen Wellenformen. Alles ist im Emulator an Engine-Werten gemessen,
nicht gehört. Die Regeln in `src/modtable-rules.mjs` warnen, wo ein Wert die gemessenen Bereiche
verlässt ([Linter](linter.md)).

**Samples (Seite Samples).** Die Seite liest die Namenstabelle aus dem RAM des Emulators oder des
verbundenen Geräts, öffnet ein Sample mit den gelesenen Werten und ändert Name und Tune. Mehr
schreibt sie nicht: das Namensfeld (16 Byte) und das Tune-Byte je Sample sind die zwei Felder der
Karte, die am Gerät geschrieben wurden ([Namen](messungen/2026-10-07-sample-name-ram.md),
[Metadaten](messungen/2026-10-07-sample-metadaten-ram.md)). Der Weg ist der der Effekte: Plan mit
Sicherung, Schreiben und Zurücklesen, Türsteher, bei einem echten Gerät zuerst der Emulator, ein Klick
nimmt zurück. Die Regeln in `src/sample-rules.mjs` sind alle Warnungen, weil nichts davon über das
hinausgeht, was einmal am Gerät gesehen wurde: ein leerer oder ganz gefüllter Name, ein Tune außerhalb
von -16 bis 0, ein Platz, der unbenutzt aussieht (PCM-Länge 0). Tune zeigt die Seite als Rohwert, die Skala ist nicht
gemessen. **Gemessen ist nur, dass die Änderung im RAM wirkt** (Display, Tonhöhe) und dass die
SD-Datei dabei unverändert blieb. Ob sie einen Neustart überlebt oder ob EXPORT ALL SAMPLE sie auf die
Karte schreibt, ist nicht gemessen; die Seite sagt das und rät, mit einem Verlust zu rechnen.

## Der Türsteher

Jede Änderung läuft vor dem Senden durch zwei Stufen.

**1. Linter.** Die Regeln aus [linter.md](linter.md), erweitert von FX auf alle
Bereiche. Jede Regel stammt aus einem Fehler, der schon etwas gekostet hat.

**2. Probelauf.** Die Simulation bekommt exakt den Byte-Strom, der gleich ans
Gerät ginge, und spielt ihn gegen eine Kopie durch. Das fängt, was der Linter
nicht sehen kann: falscher Kanal, eine Schreibnachricht ohne Adresse davor, der
Kodierfehler bei Längen mit Rest sechs.

| Ergebnis | Verhalten |
|---|---|
| tödlich, stumm, Fehler | Senden gesperrt, mit Begründung |
| Warnung | angezeigt, Senden nach Bestätigung |
| sauber | wird gesendet, danach zurückgelesen und verglichen |

Was der Türsteher nicht kann, steht in der Oberfläche dabei: er prüft Form, nicht
Klang. Ob ein Preset auf echter Hardware klingt, sagt nur das Ohr.

### Ein einziger Weg zu den Bytes

"Exakt derselbe Byte-Strom" gilt nur, wenn genau eine Stelle ihn erzeugt. Das ist
`src/plan.mjs` mit einer reinen Funktion:

```
plan(änderung, stand) -> [Nachricht, Nachricht, ...]
```

Die Simulation und der echte Sender bekommen beide dieselbe Liste. Kein anderer
Teil der App baut SysEx. Ein Test prüft das für die App-Module; die Simulation
selbst, das Kommandozeilenwerkzeug und die Tests sind ausgenommen.

### Wogegen geprüft wird

**Der Linter vergleicht mit dem Ausgangszustand.** Einige Werks-Presets von Korg
lösen einen Fehler aus, weil Wissen fehlt. Würde das Senden gesperrt, ließe sich
dort nicht einmal der Name ändern. Darum gilt, eng begrenzt: ein Fehler, der schon
im unveränderten Preset da war, wird zur Warnung herabgestuft und als
"Werkszustand, Wissenslücke" markiert. Das gilt nur für Werks-Slots, die Byte für
Byte dem Original gleichen (Prüfsummen in `data/originals.mjs`, je Slot verglichen).
Tödlich und stumm bleiben immer gesperrt, auch wenn sie schon vorher da waren.

**Schreiben nur in erlaubte Bereiche.** Ins RAM wird nur geschrieben, wo die Karte
etwas erklärt: in Tabellen nur auf ganze Records ausgerichtet, bei Feldern mit
`sites` genau die erklärten Bytes, in den Sample-Tabellen nur das Namensfeld und das Tune-Byte
eines Samples, nie ein ganzer Eintrag. Alles andere sperrt der Türsteher, bevor die
Simulation es sieht.

**Felder mit mehreren Stellen werden als Einheit geschrieben.** Alle Stellen in
einem Durchgang, danach alle zurückgelesen. Passt eine nicht, werden alle aus der
Sicherung zurückgespielt.

### Was der Probelauf braucht

**Live ins RAM geht nur mit geladener Firmware-Datei.** Ohne sie hat die Simulation
kein Abbild und der Linter kein Werksprofil, gegen das er Auswahlwerte prüfen
kann. Ohne Datei bleiben Patterns und Globals.

**Die Simulation arbeitet mit zwei Kopien.** Eine Sitzungskopie, die den Stand des
Geräts kennt und jede bestätigte Sendung nachspielt, und für jeden Probelauf eine
Wegwerfkopie davon. Die geladene Datei bleibt in beiden Fällen unberührt.

### Senden

- Eine Warteschlange, eine Nachricht zur Zeit. Jede wartet auf ihre Antwort, bevor
  die nächste rausgeht. Bei RAM-Schreiben heißt das: erst die Bestätigung auf die
  Adresse, dann die Daten.
- Feste Wartezeiten. Kommt keine Antwort, ist das ein Ergebnis und wird gemeldet.
  Auf dem Gerät heißt Schweigen jede Art von Nein.
- Nie blind wiederholen. Nach einem Abbruch wird erst zurückgelesen, was
  angekommen ist, dann entschieden.
- Vor jedem RAM-Schreiben wird der alte Inhalt gelesen und gehört zur Sitzung,
  damit Rückgängig auch live geht.
- Je Sitzung läuft genau eine Operation, eine zweite wird abgelehnt.
- Es zählt nur die Antwortart, die der Schritt erwartet, mit genau der erfragten
  Länge. Nach einer Zeitüberschreitung wartet der nächste Schritt, bis die Leitung
  ruhig ist.

Passt das Zurücklesen nicht, wird die Abweichung angezeigt, das Zurückspielen der
Sicherung angeboten, und an dieses Ziel geht nichts mehr, bis entschieden ist.

RAM-Schreiben verlangt eine gültige 0x21-Bestätigung, Pattern-Senden wartet auf
die gemessene 0x23-Bestätigung und liest danach zurück. Vor einer MFX-Menüänderung
und beim Rückgängig muss das gesamte ARM-Instruktionswort stimmen.

### Geräteerkennung und Schreibfreigabe

Ein unbekannter Firmwarestand heißt: nur lesen. Der vermessene Sampler 2.02 mit
Hacktribe wird an der Suchantwort (2/2) und an zwei SHA-256 über Programmcode im
laufenden RAM erkannt (`data/devices.mjs`). Erst wenn beide passen, ist Schreiben
erlaubt, auch beim Pattern-Senden. Für RAM-Änderungen kommen eine passende
Firmware-Datei, die Gerätekarte, der Linter, der Probelauf und die Sicherung
hinzu. Messung: [Gerätesuche und Grenzen](messungen/2026-10-08-geraeteprotokoll.md).

Mit einem eigenen, getakteten ALSA-Sender wurden unter Linux bis zu 52.400
MFX-Nutzbytes je RAM-Nachricht bestätigt. Über Hacktribes Befehle verwendet der Editor
weiter konservativ 256 Byte. Über BLECHs Befehle ([Messung](messungen/2026-10-15-blech-sysex.md))
sind es bis zu 4096 Byte je Schreib-Block und bis 32768 je Lese-Block, jeder mit
CRC-32; der Sender bildet die Schritte des Plans (Adresse, dann Daten) auf einen Block
ab, wiederholt einen Block mit falscher Prüfsumme zweimal und bricht dann mit der
Meldung ab. Die Pläne, der Türsteher und die Aufzeichnungen bleiben dieselben für
beide Wege. Auf Korgs Original mit BLECH erkennt `data/devices.mjs` das Gerät an eigenen
Signaturen; Display und Sample-Namen sind dort schreibbar, der Effekt-Editor nicht. Das Linux-Werkzeug ersetzt den Web-MIDI-Sender nicht, siehe
[tools/alsa-sysex.md](../tools/alsa-sysex.md).

## Terminal und echtes Gerät: erst der Emulator, dann das Gerät

Die Terminalseite (`site/app/terminal.mjs`, Bibliothek `src/korg.mjs`) kennt drei
Ziele. Mit dem Emulator verbunden läuft ein Skript dort wie jeder andere Befehl
durch Planer und Türsteher. Mit der echten Electribe verbunden läuft es immer
zuerst im Emulator (Probe), und nur ein dort bestandenes Skript kann ans Gerät. Es
gibt keinen Schalter, der die Probe ausschaltet. `KORG` bekommt nur die Sitzung am
Emulator, das Gerät nur `DeviceSession.replay()`, und das nimmt nur versiegelte
Proben an (`src/rehearsal.mjs`).

**Probe.** Das Skript läuft gegen die Sitzung am Emulator. Jede Änderung ist eine
Einheit: eine geplante Nachrichtenliste, die durch den Türsteher ging. Aufgezeichnet
werden die gesendeten Rahmen in Reihenfolge und die Antworten. Bestanden ist die
Probe, wenn

- das Skript ohne Fehler durchlief und keine Einheit scheiterte, auch nicht eine,
  deren Fehler das Skript abgefangen hat;
- der Türsteher jede Einheit zugelassen hat und das Zurücklesen stimmte;
- die Firmware danach läuft (kein Absturz, keine Assertion, kein Hänger), nicht neu
  gestartet ist und noch auf die Gerätesuche antwortet.

Nach Code wartet die Probe 2,5 s, weil der Emulator einen Hänger erst nach 2 s ohne
Meldung ans Bedienfeld erkennt. Eine Probe ohne Einheit (nur Lesen) oder mit
Tastendrücken ist ausführbar, aber nicht sendbar.

**Senden.** Erst dann gibt es "An das Gerät senden". Das Gerät bekommt genau die
aufgezeichneten Rahmen, der Reihe nach; nur das Kanalbyte im Kopf wird auf den Kanal
des Geräts gesetzt. Vorher geht jede Einheit noch einmal durch den Türsteher, diesmal
mit dem Kontext des Geräts. Jede Bestätigung wird mit der aus der Probe verglichen,
jedes Zurücklesen mit dem Geschriebenen. Weicht etwas ab, stoppt der Lauf sofort, und
das Gerät ist gesperrt, bis entschieden ist (Sicherung zurückspielen oder so lassen).

Entscheidungen dabei:

- **Lesen im Skript** (`ram.read`, `screen.get`, `screen.state`, Namen) läuft nur im
  Emulator und liefert Emulatorwerte. Beim Senden werden sie nicht am Gerät
  wiederholt. Am Gerät lesen nur die Teile, die zu einem Schreiben gehören: die
  Sicherung davor, das Zurücklesen danach, die Prüfung von Firmware-Code vor dem
  Ausführen.
  Das gilt auch für `ram.snapshot`, `ram.diff` und `ram.search` (Idee 11): ein Skript, das nur liest, ist
  probierbar und nicht sendbar.
- **Tastendrücke** (`KORG.press`, `KORG.turn`) gehen mit dem BLECH-Satz über `KORG.exec` und damit auch ans
  Gerät ([Messung](messungen/2026-10-22-tasten-vom-laptop.md)); ohne ihn drückt `KORG.press` nur im Emulator.
- **Zurückschreiben** nach Code nimmt die Bytes, die das Gerät vorher hatte, nicht
  die des Emulators.
- **Firmware.** Das Gerät muss bestätigt sein, dieselbe Version melden wie der
  Emulator, und eine am Gerät geladene Firmware-Datei muss dieselbe sein wie im
  Emulator (SHA-256).
- **Eine Änderung am Text verwirft die Probe**, auch wenn der Text zurückgesetzt
  wird. Eine Probe geht höchstens einmal raus.

**Code ausführen.** `KORG.exec(code, { at, guard })` plant Hochladen, Befehls-Cache
leeren, Ausführen und Zurückschreiben als eine Einheit, so wie
`tools/device/led_show.py` es von Hand macht: Firmware-Code, den der Stub aufruft,
wird vorher gegen die Firmware-Datei verglichen, die Bytes unter dem Stub werden
gesichert, der Stub wird geschrieben und zurückgelesen, dann Execute `0x57` auf die
Cache-Routine und auf den Stub, danach kommen die Originalbytes zurück. Der Stub muss
mit r0 = 1 zurückkehren, sonst kommt keine Bestätigung. Der Türsteher lässt Ausführen
nur dort zu, wo er es erklärt (`data/exec.mjs`): im Stub-Puffer ab `0xC1000000`
(nur das erste KiB) und bei der Cache-Routine, und nur Code, der vorher zurückgelesen
wurde. Ausführen geht nur über den Emulator. Der Stub-Puffer liegt im gemeldeten
Shared Buffer von Import und Export ([Speicherbereiche](speicherbereiche.md)); dass
beide sich nicht überschneiden, ist nicht geklärt, darum wird jedes Mal
zurückgeschrieben. Jedes Schreiben und Ausführen blendet am Gerät etwa 48 ms
"Working..." ein.

**Grenzen.** Der Emulator kennt den Zustand des Geräts nicht: nicht seine Patterns,
nicht die offene Seite, solange er nicht mit dem Flash vom Gerät läuft. Eine Probe,
die im Emulator bestand, belegt die Nachrichten und die Firmware, nicht den Zustand
am Gerät. Ein Neustart, den die Firmware selbst auslöst und den der Emulator nicht
nachbildet, fällt der Probe nicht auf.

Dauerhafter Code auf dem Gerät (Plugins) läuft nicht über diesen Weg, sondern als
Patch, siehe [patcher.md](patcher.md) und [plugins.md](plugins.md).

## Fehlerkatalog

Jeder bekannte Fehler ist eine Zeile und ein Test, durch den Web-MIDI-Ersatz, damit
der echte Weg mitgetestet ist. Die Spalte nennt die Stufe, die ihn fängt, und genau
diese Stufe wird getestet (`test/live.test.mjs` in Node, `test/e2e/` im Browser).

| Fehler | Code | Stufe |
|---|---|---|
| falscher globaler Kanal | `channel` | Probelauf |
| Flash-Adresse am RAM-Befehl | `not-ram` | Türsteher, Probelauf einzeln |
| Adresse außerhalb des Abbilds | `out-of-range` | Türsteher, Probelauf einzeln |
| Adresse im Abbild, aber außerhalb erlaubter Bereiche | `region` | Türsteher |
| Zugriff auf Firmware, Systemdaten, Stacks, Loader, DSP-Ports, Flash oder RAM außerhalb des vermessenen Fensters | `region`, mit der Id des Bereichs | Türsteher, Sender ([Sperrliste](speicherbereiche.md)) |
| Befehl, den der Editor nicht kennt | `unknown-command` | Türsteher, Sender |
| Daten ohne Adresse davor | `write-without-header` | Probelauf |
| zu kurz angekommen, Rest sechs | `short-write` | Probelauf |
| Flash-Lesen ab `0x1000000` | `region` (`flash-beyond`), die Simulation meldet es einzeln als `hang` | Türsteher, Sender |
| Code ausführen | `execute` | Probelauf |
| MIDI ohne SysEx angefragt | `no-sysex` | Seite |
| `0x18` in Stufe 2 | `stage2-fatal` | Linter |
| `0x16` in Stufe 2 | `stage2-silent` | Linter |
| Decimator mit zweiter Stufe | `stage1-needs-solo` | Linter |
| Master-Baustein im Insert | `master-unit-in-insert` | Linter |
| Record aus der falschen Tabelle | `wrong-table` | Linter |
| Master-Preset ohne Einblendung | `no-switch-on-fade` | Linter |
| Stufenblock in die andere Stufe | Ausnahme in `adoptStage` | Kern |
| Mehrfachstelle halb geschrieben | | Sender, Rückspielen |
| Pattern senden ohne Sicherung des Puffers | | Türsteher |
| Pattern-Dump mit falscher Länge oder falschem Rahmen | | Probelauf |
| Pattern an falschen Kanal | `channel` | Probelauf |
| Step mit "An" ohne "Trigger" | Warnung | Linter |
| keine Antwort innerhalb der Wartezeit | | Sender |
| Zurückgelesen passt nicht | | Sender |
| BLECH-Block mit falscher Prüfsumme, auch nach drei Versuchen | `crc` | Sender |
| BLECH verweigert den Zugriff (Schutzliste der Firmware) | `protected`, mit dem Status des Geräts | Gerät, Sender |
| BLECH liest nach dem Kopieren etwas anderes zurück | `verify` | Gerät, Sender |
| Gerät mitten in einer Sendung abgezogen | | Sender |
| Global-Dump mit falscher Länge oder falschem Rahmen | | Probelauf |

Fehler-Injektion und Gerätefreigabe für Tests liegen nur unter `test/`, der
Test-Server liefert sie über eigene Routen, und sie kommen nicht in die
ausgelieferte Seite.

## Oberfläche und Design

Die Oberfläche entsteht aus der Karte (`site/app/fields.mjs`): Auswahl bis fünf
Werte als `ui-segmented`, mehr als `ui-select`, An/Aus als `ui-switch`, Zahlen als
`ui-range`, der Klartext im `output` und in `aria-valuetext`. Ein Gerätewert
außerhalb des bearbeitbaren Bereichs wird angezeigt, wie er ist, und erst ersetzt,
wenn jemand den Regler bewegt.

Das Design liegt in `site/design/` (Tokens, Komponenten, Schriften). Regeln:

- Tokens statt roher Farben oder Pixelwerte.
- Standard-Klassen (`ui-*`) werden nicht umdefiniert, eigene Klassen tragen das
  Präfix `cee-`.
- Keine Farbverläufe, Status nie nur über Farbe (der Türsteher sagt immer das Wort
  dazu), Tippflächen mindestens 44 px.
- Der Editor bekommt keine Design-System-Seite, keine Übersicht aller Komponenten.
  `test/design.test.mjs` hält das fest.
- Das Gerät im Emulator ist eine flache Zeichnung aus Tokenfarben (`site/app/panel.mjs`),
  ohne Foto, Logo oder Markennamen; auch das prüft ein Test.
