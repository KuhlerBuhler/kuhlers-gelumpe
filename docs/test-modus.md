# Test-Modus und Fernbedienung über USB

Ab BLECHTRIBE 1.3.8 lässt sich die Electribe vom Rechner aus ganz bedienen: jede Taste, die fünf Drehgeber, die elf
Regler, die 16 Pads und das Touchpad. Dazu kommt der Test-Modus: das Gerät sieht aus wie ausgeschaltet und läuft weiter.
So kann man am Gerät testen, ohne davorzusitzen und ohne dass ein leuchtendes Gerät im Raum stört.

Gemessen im Emulator mit Hacktribe 2.02, Korgs Original 2.02 rot und blau, jeweils mit dem BLECH-Satz
([Messung](messungen/2026-10-29-test-modus-fernsteuerung.md)). **Am Gerät noch nicht geprüft.**

## Was der Test-Modus macht

- Das Display ist aus (der Display-Controller bekommt den Befehl zum Abschalten). Die Firmware zeichnet weiter in ihren
  Bildpuffer, der Rechner liest das Bild also wie sonst über USB.
- Das Display-Licht ist aus, auch wenn Power Save dimmen will, ein Plugin `korg.backlight` ruft oder die Firmware nach
  dem Netzteil-Stecken das Licht neu setzt.
- Jede LED (Pads, Tasten, die unteren RGB-LEDs) steht auf 0. Die Firmware sendet keine LEDs, `korg.led` und
  `korg.ledHold(0)` eines Plugins ändern daran nichts.
- Auto Power Off schaltet nicht ab: solange der Test-Modus an ist, beginnen die 4 Stunden in jedem Bild neu. Steht Auto
  Power Off in den Globals auf aus, bleibt es aus. Die Einstellung selbst wird nicht verändert.
- Tasten, Regler und Pads am Gerät wirken weiter, auch Ton und MIDI.

Beim Ausschalten kommt alles zurück, wie es ohne Test-Modus wäre: Display an, Licht nach den Einstellungen von
`Menü -> BLECH -> CUSTOMIZATION`, die Firmware sendet alle LEDs neu, und eine LED, die ein Plugin inzwischen gesetzt hat,
zeigt dessen Wert. Der Test-Modus lebt nur im RAM, nach einem Neustart ist er aus.

## Ein und aus

Nur über USB:

- mit `tools/device/remote_press.py`: `testmode=on` und `testmode=off`,
- in der Konsole des Editors: `KORG.testMode(true)` und `KORG.testMode(false)`.

Ein Plugin liest den Zustand über `korg.system.testMode` ([Plugins](plugins.md)), setzen kann es ihn nicht: ein Plugin,
das ihn beim Start einschaltet, ließe das Gerät bei jedem Einschalten dunkel.

## Fernbedienung

`tools/device/remote_press.py` spricht BLECHs eigene SysEx-Befehle (READ, WRITE, EXEC). Ein kleiner Code-Schnipsel im
EXEC-Puffer legt einen Befehl in den Arbeitsbereich der Laufzeit; die Laufzeit gibt ihn im nächsten Bild (40 ms) als
Nachricht des Panels in die Warteschlange der Firmware. Die Firmware nimmt ihn also genau so wie einen Druck am Gerät, mit
allem, was daran hängt (Plugins, EXIT-Kurzbefehle, Tastenumleitung). Nur RAM, nichts im Flash, der Puffer bekommt nach dem
Lauf seine alten Bytes zurück.

```bash
python3 tools/device/remote_press.py --dry-run menu
python3 tools/device/remote_press.py testmode=on menu edit_next +1 exit --screen
python3 tools/device/remote_press.py level=200 cutoff-2 pad5 pad3:64 touch=400,300 shift:down edit_next shift:up
python3 tools/device/remote_press.py testmode=off
```

| Schritt | Wirkung |
|---|---|
| `menu`, `play`, `bar1`, `edit_next` | Taste drücken und loslassen (Namen aus `data/panel.mjs`, `_` statt Großbuchstaben) |
| `+3`, `-1` | Hauptrad drehen |
| `cutoff+2`, `osc-1`, `mod_type+1`, `ifx_type-1` | einen Drehgeber drehen |
| `level=200`, `mod_depth=0` | einen Regler auf 0 bis 255 stellen |
| `pad5`, `pad5:64` | Pad anschlagen (Anschlag 100 oder die Zahl) und loslassen |
| `pad5:down`, `pad5:up` | Pad gedrückt halten, loslassen |
| `touch=400,300` | Touchpad bei x, y (0 bis 1023) berühren und loslassen |
| `shift:down`, `shift:up` | eine Taste nur drücken oder nur loslassen, etwa SHIFT für Kombinationen |
| `testmode=on`, `testmode=off` | Test-Modus |
| `release` | alles loslassen, was der Rechner gedrückt hält |
| `--screen` | danach das Display als Text (auch im Test-Modus) |

Nach jedem Schritt steht, wo das Gerät ist (Bildschirm, Seite, Part). Die Konsole des Editors hat dieselben Wege:
`KORG.press`, `KORG.turn(n, "cutoff")`, `KORG.knob("level", 200)`, `KORG.pad(5)`, `KORG.touch(400, 300)`,
`KORG.hold("shift", true)`, `KORG.release()`, `KORG.testMode(true)`.

Ein Befehl gilt erst als ausgeführt, wenn die Laufzeit ihn genommen hat. Nimmt sie ihn nicht binnen 500 ms (mit EXIT
eingeschaltet, Warteschlange voll), meldet das Werkzeug einen Fehler, und das Gerät führt ihn auch später nicht aus.
Was der Rechner gedrückt hält (eine Taste mit `:down`, ein Pad mit `:down`), lässt das Werkzeug bei einem Fehler los;
reißt die Verbindung ab, lässt das Gerät es nach 10 s ohne Befehl selbst los. Tasten, Drehgeber, Pads und Werte außerhalb
ihres Bereichs lehnen Werkzeug und Konsole ab, bevor etwas ans Gerät geht.

## Grenzen

- **Die blaue Electribe** nimmt über USB keine Schreibbefehle an (BLECHs Tabelle erlaubt dort kein Schreiben, also auch kein
  EXEC). Im Emulator laufen alle Fälle auch auf der blauen; über USB geht dort nur das Lesen. **Offen.**
- Firmware mit BLECH bis 1.3.7 nimmt nur Tasten und das Hauptrad an; das Werkzeug bricht für alles andere vor dem
  Schreiben ab.
- Mit EXIT beim Einschalten ist BLECH still und die Laufzeit aus: dann geht weder die Fernbedienung noch der Test-Modus.
- Ob das Display am Gerät beim Abschaltbefehl wirklich ganz dunkel ist, ist **offen** (im Emulator gemessen ist nur, dass
  der Befehl beim Controller ankommt).
