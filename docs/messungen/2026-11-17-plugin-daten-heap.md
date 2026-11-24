# Plugin API 39: ein Ordner mit 16 Datendateien je Plugin, 32 KiB je Datei

Stand 17. November 2026. **Gemessen** im [Emulator](../glossary.md#emulator) mit [Hacktribe](../glossary.md#hacktribe) 2.02, Korgs Original 2.02 rot und blau, jeweils mit dem
BLECH-Satz. Fälle: `tools/emu/plugin_api32_cases.py` (Name aus API 32 behalten, Gruppe `plugin_api32`). Heap:
`tools/emu/heap_headroom.py`. **Am Gerät nicht geprüft.** Ersetzt das Layout aus
[API 32](2026-11-11-plugin-api32-data-file.md); 1.5 ist noch nicht erschienen, darum ohne Übernahme alter Dateien.

## Frage

Wie viele Dateien und wie viele Bytes je Datei kann ein Plugin bekommen, ohne dass der Heap der Firmware (operator `new`) bei
normaler Benutzung knapp wird?

## Weg

- `korg.file.read(feld, offset, datei)` und `korg.file.write(feld, offset, datei)` arbeiten auf
  `SD:KORG/blechtribe/Plugin/Data/<name>/<datei>.bin`, `<datei>` zweistellig `00` bis `15`. `<name>` wird wie bisher bereinigt
  (`dataFileName` in `data/script/contract.mjs`). Ein Plugin kommt nur an seinen eigenen Ordner. (gelesen, eigener Code)
- `datei` außerhalb 0 bis 15 hält das Plugin mit API_ARG an, wie jedes andere Argument außerhalb seines Bereichs. (gelesen)
- `card_create` legt fehlende Ordner auf dem Weg an, `Data/<name>/` entsteht beim ersten Schreiben. Modus 0x0A
  (CREATE_ALWAYS) kürzt eine Datei beim Schreiben, ohne f_truncate. (gelesen, `script_card.s`)
- Der Block im Heap hält eine Datei eines Plugins: 16 Byte Name, 4 Byte Dateinummer, dann die Daten. Wechselt ein Plugin die
  Datei oder greift ein anderes Plugin zu, solange eine Änderung noch nicht auf der Karte ist, geben beide Aufrufe -1.
  (gelesen, `tools/patch/script_data.s`)
- `script_data_flush` ist unverändert: Schreiben auf die Karte nur auf dem Hauptschirm oder in BLECH, frühestens 2 s nach dem
  letzten Schreiben. (gelesen, Diff)
- Heap: Zeiger der Firmware auf das Ende des belegten Bereichs gelesen (rot und Hacktribe `0xC03404AC`, Pool `0xC06A2940` bis
  `0xC08A2940`; blau `0xC034069C`, Pool `0xC0573CFC` bis `0xC0773CFC`, aus der Wachstumsroutine `0xC002A060`), jede Anfrage an
  `new` mitgeschrieben. Schritte: Start mit Karte, fünf Patternwechsel, Sample-Import (nur Sampler), Plugin mit Datendatei,
  drei Patternwechsel mit Plugin. Am Ende das größte `new`, das noch gelingt, von 1 MiB abwärts probiert. (gemessen)

## Heap

Belegt und frei im Pool, in Byte, mit dem neuen Block (32 788 Byte). Pool je 2 MiB. (gemessen)

| Schritt | Hacktribe belegt / frei | rot belegt / frei | blau belegt / frei |
|---|---|---|---|
| nach dem Start | 169 664 / 1 927 488 | 169 664 / 1 927 488 | 148 228 / 1 948 924 |
| fünf Patternwechsel | unverändert, größte Anfrage 25 | unverändert, größte Anfrage 25 | unverändert, größte Anfrage 25 |
| Sample-Import (ein WAV) | unverändert, größte Anfrage 1 172 | unverändert, größte Anfrage 1 172 | kein Import auf blau |
| Plugin mit Datendatei | 206 528 / 1 890 624 | 206 528 / 1 890 624 | 185 092 / 1 912 060 |
| Patternwechsel mit Plugin | unverändert | unverändert | unverändert |
| größtes `new` am Ende | 1 MiB gelingt | 1 MiB gelingt | 1 MiB gelingt |
| Asserts der Firmware | keine | keine | keine |

| Befund | Marker |
|---|---|
| Patternwechsel und Sample-Import holen nur kleine Blöcke und geben sie zurück; der Pool wächst dabei nicht | gemessen |
| Der Pool wächst in Schritten von 4 KiB: der 32 788-Byte-Block kostet 36 864 Byte, der alte 4 112-Byte-Block 8 192 (Hacktribe mit der Laufzeit von develop: 169 664 auf 177 856) | gemessen |
| Nach dem Plugin sind auf allen drei Builds noch über 1,89 MB frei, und 1 MiB am Stück geht | gemessen |

## Fälle

Alle 8 Fälle von `plugin_api32_cases.py` bestehen auf Hacktribe, rot und blau. (gemessen)

| Fall | Was geprüft wird |
|---|---|
| `write_power_off_read` | schreiben, Neustart mit dem Kartenabbild, Werte kommen zurück |
| `card_missing` | ohne Karte geben `read` und `write` -1 |
| `short_file_and_gap` | kurze Datei lesen, Lücke beim Schreiben hinter dem Ende ist 0 |
| `several_files` | Dateien 5 und 15 auf der Karte lesen je ihren Inhalt, Datei 7 fehlt und gibt 0; Datei 2 nimmt ein Schreiben, Datei 3 gibt -1, bis 02 auf der Karte ist, dann ihr eigenes; am Ende 02, 03, 05 und 15 getrennt, kein 07 |
| `file_out_of_range` | Datei 16 und -1 halten das Plugin mit API_ARG an, bevor es die Karte anfasst; kein Ordner der beiden auf der Karte |
| `two_plugins_apart` | alpha schreibt Datei 0, beta liest seine Datei 0: -1, solange alphas Änderung wartet, dann sein eigenes Byte, nie alphas; `alpha/00.bin` und `beta/00.bin` bleiben getrennt |
| `size_limit_edge` | Schreiben an 0, 16 000 und 32 000 füllt die Datei genau auf 32 768 Byte (das letzte nimmt 768 von 1 000), Lesen ab 32 760 gibt 8 |
| `write_timing` | Karte bei 1,5 s mit Stand 01, bei 3,5 s mit 02 (Abstand 2,0 s); auf DATA UTILITY bleibt 02, zurück auf dem Hauptschirm kommt 03 |

`several_files` brauchte auf Hacktribe 50 Versuche (einen je Frame), bis Datei 3 frei war. (gemessen)

## Entscheidung

| Befund | Marker |
|---|---|
| 16 Dateien je Plugin, höchstens 32 768 Byte je Datei; der Block im Heap ist 32 788 Byte | Urteil |
| Der Block sind rund 1,7 % des nach dem Start freien Heaps (gut 1,9 MB) | hergeleitet aus den Zahlen oben |
| Mit dem Spettro-Dienst (103 424 Byte, wenn ein Plugin Spektrum oder Wellenform nutzt) bleiben über 1,75 MB frei | hergeleitet (Heap-Pool: [Systemspeicher offline](2026-10-08-systemspeicher-offline.md)) |
| Kurze Blöcke der Firmware: Pattern-Liste 16 KiB, Migration 32 KiB; sie kommen und gehen, der Block bleibt bis zum Ausschalten | gelesen |
| Mehr als 32 KiB bringt einem Plugin wenig: alle Variablen eines Plugins zusammen sind 128 KiB, also 32 768 Plätze | Urteil |
| Eine größere Datei braucht beim ersten Lesen und beim Schreiben länger; wie lange auf einer echten Karte, ist nicht gemessen | Urteil |
| Die Zahl der Dateien kostet keinen Heap, nur Einträge im Ordner; 16 passt in zwei Ziffern und hält den Ordner übersichtlich | Urteil |

## Offen

- Gerät: wie lange Lesen und Schreiben von 32 KiB auf einer echten Karte dauern und ob es hörbar ist.
- Heap nach vielen großen Sample-Importen: ob er sich zerstückelt, ist nicht gemessen; der Emulator importiert ein kurzes WAV.
- Heap mit laufendem Spettro-Dienst im selben Lauf: hier nur hergeleitet.
