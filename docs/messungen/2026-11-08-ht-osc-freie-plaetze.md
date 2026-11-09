# Hacktribe-Oszillatoren auf den freien Plätzen (08.11.)

Stand 08.11.2026, Emulator mit Korgs Original 2.02 (rot), Hacktribe 2.02 und Korgs blauer 2.02. Wunsch: auf der roten
Firmware die leeren Plätze zwischen den Werks-Samples und den eigenen Samples mit Hacktribes Oszillatoren füllen, in
Hacktribes Reihenfolge und Schreibweise. Patch `data/patches/ht-osc.json`, gebaut von `tools/patch/ht_osc.py`. Am Gerät
nicht geprüft.

Zählweise: "Platz" ist nullbasiert wie in der Firmware, "Anzeige" ist Platz plus 1. Platz 421 bis 499 ist Anzeige 422 bis 500.

Marker: **gemessen** (im Emulator ausgeführt oder in den Dateien verglichen), **hergeleitet** (aus Code oder Messung
geschlossen), **offen**.

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Korg rot ohne Karte: Platz 0 bis 17 DSP-Oszillatoren, 18 bis 420 die 403 Werks-Samples, 421 bis 998 leer (`SampleNNN`, Import-Nr. = Platz + 50); frei zwischen Werk und eigenen Samples sind Platz 421 bis 499, 79 Plätze | gemessen | Namen `0xC047B08C + platz * 0x20`, Import-Nr. bei +0x12, Probe über die Namenstabelle nach dem Start |
| Ein Eintrag mit Import-Nr. unter 50 ist ein DSP-Oszillator: die Nummer ist die Welle, +0x14 bis +0x1B die Parameter, keine Sample-Daten, kein PCM | hergeleitet | Code `0xC0040D60` bis `0xC0040D7C`, `0xC004E2F0`; alle 274 Einträge Hacktribes haben Import-Nr. unter 50 (gemessen) |
| Der DSP-Code ist in Korg rot und Hacktribe Byte für Byte gleich; Hacktribe liefert nur die Einträge, die Oszillatoren laufen auf Korgs eigenem ARM- und DSP-Code | gemessen (Vergleich `0xC00F9E10` bis `0xC013C0B0`), hergeleitet (Schluss) | Bytevergleich der beiden VSB |
| Die 76 Einträge des Patches: DUAL, OCT, CHIP, RING je 4, X-SAW, X-SQUARE, X-TRI, X-SINE je 7 Stufen (-24, -12, -7, 0, +7, +12, +24), VPM-SAW, VPM-SQUARE, VPM-TRI, VPM-SINE je 8 Stufen (0.5, 1, 2, 3, 4, 8, 16, 32), auf Platz 421 bis 496 | gemessen | `ht_osc.py --hacktribe HACKTRIBE.VSB`: "76 entries match Hacktribe's table"; Fall `ohne-karte-oszillatoren` |
| Die Einträge kommen aus einer Feldtabelle (Name, Kategorie, Welle, Parameter, Stufe), nicht als Block aus Hacktribe kopiert | hergeleitet | `ENTRIES` in `tools/patch/ht_osc.py` |
| Stufen-Bytes X: -24 `c1`, -12 `d4`, -7 `e4`, 0 `00`, +7 `1c`, +12 `30`, +24 `3f`; VPM: 0.5 ergibt 0, 1, 2, 3, 4, 8, 16, 32 sich selbst | gemessen | Hacktribes Tabelle `0xC00D9AB0`, Vergleich mit `--hacktribe` |
| Anzeige 498 bis 500 (Platz 497 bis 499) bleiben leere Sample-Plätze | Urteil | 79 Plätze, 76 Einträge; drei Stufen mehr hätten eine Familie ungleich gemacht |
| Platz im Code: 2708 Byte (276 Byte Code, 2432 Byte Tabelle) bei `0xC014F000`; `0xC014F000` bis `0xC014FC00` ist `FF` in Korg rot, Korg blau und Hacktribe 2.02 | gemessen | `ht_osc.py` prüft das Gebiet vor dem Bauen; Bytevergleich der drei VSB |
| Fünf Stellen rufen den Code: `0xC004F5A8` und `0xC004E354` (`ldr r4, =0x1A5`, Werksstart und Start aus `e2sSample.all`), `0xC0040D64` (`cmp r4, #0x1A4` im OSC-Auswähler `0xC0040D50`), `0xC00997A4` (`cmp r0, #0x1A4` in der Platzsuche der Stimme `0xC0099788`), `0xC00362A4` (`moveq r3, #0x24` im Import eines Samples) | gemessen (Wörter in der VSB), hergeleitet (Rolle aus dem Code) | `ht_osc.py` prüft jedes Wort vor dem Bauen |
| Ohne Patch überspringt der Auswähler einen DSP-Eintrag über Platz 420, und die Stimme bekommt für Platz 421 bis 499 keinen Eintrag | gemessen | Probe mit DUAL-SAW auf 421 ohne die zwei Stellen: Auswähler überspringt, `0xC0099788(421)` gibt 0 |
| OSC-Rad über den Panel-Weg: von 420 aufwärts 421, 422, ... 496, dann 500, 501; von 501 abwärts 500, 496, 495 | gemessen | Fälle `regler-hoch`, `regler-runter` |
| Die Stimme bekommt für Platz 421 den Eintrag DUAL-SAW | gemessen | Fälle `stimme-findet-421`, `note-wie-oszillator-0` |
| Welche Welle der DSP spielt, sagt der Emulator nicht: die Arten der Nachrichten an das Postfach `0xFF900A34` sind für Platz 421 (DUAL-SAW), Hacktribes DUAL-SAW auf 18 und TRIANGLE auf 2 dieselben, die Welle steht in keiner | gemessen | Probe `v0`, `v18`, `v421` über das Postfach; der DSP ist im Emulator ein Platzhalter |
| Wie jeder Oszillator am Gerät klingt | offen | nur am Gerät |
| Der Stock-Lader bricht die ganze Datei ab, wenn der Import (`0xC004EDF0`) ein Sample ablehnt: `0xC0035B10` gibt `0x24` zurück, die äußere Schleife (`0xC00366FC`) hört auf | gemessen | Korg rot ohne Patch: ein Eintrag auf Platz 5 (DSP), danach 18 und 600: 18 und 600 werden nicht geladen |
| Mit dem Patch gibt `ho_skip` für Platz 421 bis 496 statt `0x24` eine 0 zurück: der Eintrag wird abgelehnt, der Rest der Datei lädt | gemessen | Fall `datei-eintrag-450-abgelehnt-rest-geladen`: echte Datei mit 18 bis 420, 449 und 500 bis 998, alles außer 449 geladen, 449 bleibt X-SQUARE +12 |
| Ohne Patch (und mit EXIT beim Einschalten) lädt ein Eintrag auf 449 wie bisher als Sample | gemessen | Fall `exit-wie-firmware` |
| EXPORT ALL SAMPLE (DATA UTILITY) schreibt keinen Eintrag für 421 bis 499, die eigenen Samples schon | gemessen | Fall `export-ohne-421-bis-499` |
| Ein Part auf Platz 430 bleibt nach WRITE und Neustart auf 430, mit CHIP-TRI 2 dort | gemessen | Fälle `pattern-430-geschrieben`, `pattern-430-nach-neustart` |
| Werks-Plätze 18 bis 420 und eigene Plätze 500 bis 998 bleiben unberührt | gemessen | Fälle `ohne-karte-rest-wie-firmware`, `datei-eintrag-450-abgelehnt-rest-geladen` |
| Kein Schalter: wo der Satz den Patch hat, sind die Oszillatoren immer da; FEATURES hat keine Seite HT OSC | gemessen | Fall `alte-einstellung-datei-gelesen` (Seitenliste ohne HT OSC) |
| Eine Einstellungsdatei mit Bit 6 von Byte 5 (ein Zwischenstand schrieb dort HT OSC AUS) lädt weiter, das Bit wird übergangen: die Oszillatoren sind da, die übrigen Einstellungen gelten (KEY PADS OFF aus Bit 4) | gemessen | Fälle `alte-einstellung-bit-6-oszillatoren`, `alte-einstellung-datei-gelesen` |
| EXIT beim Einschalten: alle fünf Stellen tun, was die Firmware tut | gemessen | Fall `exit-wie-firmware` |
| Ein älteres BLECH (bis 1.4) liest eine Einstellungsdatei mit Bit 6 nicht und nimmt dann alle Voreinstellungen; das jetzige BLECH schreibt Bit 6 nie | hergeleitet | `menu_file_read`: dort war die Maske `0x3F`; `menu_settings_save` setzt Bit 6 nicht |
| Der Hacktribe-Satz und der blaue Satz sind mit und ohne ht-osc Byte für Byte gleich | gemessen | Satz aus `blech.json` mit und ohne den Patch gebaut, `cmp` |
| Auf dem Hacktribe- und dem blauen Satz ruft keine der fünf Stellen in den Code, das Gebiet bleibt `FF`, der Start läuft ohne Assertion | gemessen | `ht_osc_cases.py --vsb` auf beiden Sätzen (Fall `ohne-patch-unberuehrt`) |
| Der Sample-Editor der App schreibt nur Plätze ab 500, und die App hat keine Namensliste der Oszillatoren; dort war nichts zu ändern | hergeleitet | `src/sample-file.mjs` (`FIRST_USER`) |

## Der Patch

Der Code liegt bei `0xC014F000`, vor dem Code von beat-eighth (`0xC014FC00`). Das BLECH-Menü ruft ihn nicht.

| Stelle | Vorher | Mit dem Patch |
|---|---|---|
| `0xC004F5A8` Werksstart | `ldr r4, =0x1A5`, Löschen ab 421 | `ho_fill`: Einträge auf 421 bis 496, die Firmware löscht ab 497 |
| `0xC004E354` Start aus `e2sSample.all` | wie oben | wie oben |
| `0xC0040D64` OSC-Auswähler | `cmp r4, #0x1A4` | `ho_sel`: DSP-Einträge bis 496 |
| `0xC00997A4` Platzsuche der Stimme | `cmp r0, #0x1A4` | `ho_voice`: Einträge bis 496 |
| `0xC00362A4` Import eines Samples | `moveq r3, #0x24`, Abbruch der Datei | `bleq ho_skip`: 421 bis 496 übersprungen, sonst wie vorher |

War EXIT beim Einschalten gehalten, tut jede Stelle, was die Firmware tut. Nur für Korgs Build
(rot); Hacktribe hat die Oszillatoren schon (`notNeededOn`), die blaue Firmware ist ein anderer Build.

## Fälle (`tools/emu/ht_osc_cases.py`)

`--vsb` mit dem ganzen BLECH-Satz auf Korg rot, `--only` für einzelne Gruppen. Auf einem Satz ohne den Patch läuft nur
`case_without`.

| Gruppe | Fälle |
|---|---|
| `case_names` | ohne Karte: 76 Einträge, 497 bis 500 und Werks-Plätze wie Firmware |
| `case_card` | echte Datei (18 bis 420, 449, 500 bis 998): Oszillatoren bleiben, 449 abgelehnt, Rest geladen |
| `case_knob` | OSC-Rad auf- und abwärts über 421 bis 496 |
| `case_voice` | Platzsuche der Stimme für 421 |
| `case_pattern` | Part auf 430, WRITE, Neustart |
| `case_export` | EXPORT ALL SAMPLE ohne 421 bis 499 |
| `case_exit` | EXIT beim Einschalten wie Firmware |
| `case_old_setting` | Einstellungsdatei mit Bit 6 von Byte 5: Oszillatoren da, Datei gelesen |

## Nachtrag 09.11.: kein Schalter mehr

Die Seite HT OSC unter BLECH > FEATURES, das Einstellungswort `0xC014FBFC` und `ho_apply` sind entfernt. Die Plätze
waren immer leer, die Oszillatoren stören nichts, ein Schalter ist nicht nötig. Bit 6 von Byte 5 der Einstellungsdatei
ist frei: eine Datei, in der es gesetzt ist, lädt wie jede andere, das Bit wirkt nicht. Notschalter bleibt EXIT beim
Einschalten.

## Offen am Gerät

- Klang jedes Oszillators auf 422 bis 497, Vergleich mit Hacktribe.
- Osc Edit auf diesen Plätzen.
- Ein Pattern mit einem Oszillator auf 422 bis 497 spielt nach dem Neustart gleich.
- Laden einer echten `e2sSample.all` mit einem Eintrag auf diesen Plätzen am Gerät.

## Wie gemessen

```
tools/emu/.venv/bin/python tools/patch/ht_osc.py --vsb korg-red-2.02.VSB --hacktribe hacktribe-2.02.VSB --out data/patches/ht-osc.json
tools/emu/.venv/bin/python tools/emu/ht_osc_cases.py --vsb red-set.VSB [--only case_card,...]
tools/emu/.venv/bin/python tools/emu/ht_osc_cases.py --vsb ht-set.VSB      # Hacktribe-Satz: case_without
tools/emu/.venv/bin/python tools/emu/ht_osc_cases.py --vsb blue-set.VSB    # blauer Satz: case_without
```
