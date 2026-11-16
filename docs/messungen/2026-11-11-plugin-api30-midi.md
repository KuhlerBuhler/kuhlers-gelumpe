# Plugin API 30: MIDI senden, empfangen und halten

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api30_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft, an keiner DAW geprüft.**

## Frage

Kann ein Plugin Control Change, Note On/Off und Program Change über die Sendewege der Firmware schicken, jede empfangene
Kanalnachricht als Ereignis bekommen und einzelne Nachrichtentypen von der Firmware fernhalten?

## Weg

**Senden.** Zwei Sendefunktionen der Firmware schreiben ihre Bytes auf DIN und USB:

| Funktion | Hacktribe/rot | blau | Marker |
|---|---|---|---|
| drei Bytes `(_, status, d1, d2)` | `0xC002775C` | `0xC002316C` | gemessen (DIN-Ausgang im Emulator) |
| zwei Bytes `(_, status, d1)` | `0xC002779C` | `0xC00231AC` | gemessen |

Kein Running Status: jede Nachricht geht mit Statusbyte hinaus (gemessen). Die Pads der Firmware senden `90 3c 60` und
`80 3c 40`, Note Off also mit Velocity 64 (gemessen); `korg.midi.noteOff` macht es genauso.

Das globale Objekt liegt bei `[0xC033E6A0]` (blau gleich): `+0x2D` der globale MIDI-Kanal (0 bis 15), `+0x2E` der MIDI SEND
FILTER (gelesen und gemessen).

**Plan-Abweichung 5.1:** der Plan nannte `0xC00405EC`. Diese Funktion bildet paramIds auf CCs ab und nimmt keine rohen
CC-Nummern (gelesen). Die Laufzeit nutzt deshalb die Drei-Byte-Funktion direkt und prüft den Filter selbst.

**Filter.** Wie bei der Firmware:

| Filter | CC, Note | Program | Marker |
|---|---|---|---|
| 0 Off | geht hinaus | geht hinaus | gemessen |
| 1 Short | gehalten | geht hinaus | gemessen; Program-Funktion `0xC00406A0` bricht nur bei 2 ab (gelesen: `bl 0xC0047484; cmp r0,#2`) |
| 2 Short + Program | gehalten | gehalten | gemessen |

**Empfangen.** Die Empfangsschleife ruft für jede Kanalnachricht den Handler der Firmware: Hacktribe/rot `bl 0xC003BB00` bei
`0xC002B2D8`, blau `bl 0xC0036540` bei `0xC002843C` (gemessen mit eingespeisten Bytes; blau per Probe gefunden, der Code
unterscheidet sich). Der Hook an dieser Stelle meldet `midiIn(status, data1, data2)` und ruft danach den Handler, außer der
Typ ist gehalten. Status unter `0x80` und ab `0xF0` gehen unverändert durch: SysEx, Clock und Echtzeit melden nichts.

**Halten.** `korg.midi.hold(typ, an)` setzt Bit 8 bis 14 im Pad-Wort des Plugins; `holds_sync` faltet alle Plugins und schreibt
die freien Typen in ein bisher ungenutztes Wort (`KEY_HOLD + 16`, beim Einschalten FF = alles frei).

## Ergebnisse

| Befund | Marker |
|---|---|
| Alle vier Fälle grün auf Hacktribe 2.02, rot 2.02 und blau 2.02 mit BLECH, keine Assertion | gemessen |
| `cc(-1,20,64)`, `noteOn(3,60,100)`, `noteOff(3,60)`, `program(15,5)` geben auf DIN `B<g> 14 40 93 3c 64 83 3c 40 cf 05`, alle Rückgaben 1 | gemessen |
| Filter 1: CC und Note geben 0 und senden nichts, Program gibt 1 und sendet; Filter 2: alles 0 | gemessen |
| `B0 07 41` und `95 30 22` von DIN: je ein `midiIn` mit den drei Bytes, der Handler der Firmware bekommt beide | gemessen |
| Plugin hält CC (Typ 3): CC kommt im Plugin an, nicht im Handler; eine Note kommt in beiden an | gemessen |

## Offen

- Gerät und DAW: nichts davon am Gerät oder über USB an einem Rechner geprüft.
- Das Plugin sendet aus dem UI-Task, die Firmware aus ihren eigenen Tasks. Dass die Sendefunktion dabei nicht kollidiert, ist
  hergeleitet (sie schreibt in die Sendepuffer der Ports), nicht unter Last gemessen.
- SysEx und Echtzeitnachrichten werden weder gesendet noch gemeldet.
