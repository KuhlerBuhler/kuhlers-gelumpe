# Part-Werte schreiben wie ein Regler (API 14)

Stand 2. November 2026. Gemessen im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/plugin_edit_cases.py`. **Am Gerät nicht geprüft.** Beschreibung für Nutzer:
[Funktionen der Electribe](../plugins.md).

## Frage

`korg.seq.setPartValue` soll einen Wert eines Parts so setzen, wie es ein Regler tut: Pattern im RAM, Klang und
Parameterfenster. Welche Funktion der Firmware tut das, und schreibt sie dieselben Bytes wie der Regler?

## Der Weg des Reglers (hergeleitet aus dem Code, rot und Hacktribe gleich)

| Adresse | Was |
|---|---|
| `0xC0048460` | Setter eines Part-Werts: `r0` das Objekt aus `[0xC034886C]`, `r1` 0x10 plus Part, `r2` 0, `r3` die Nummer des Werts, auf dem Stack das Byte des Werts und 0. Schreibt das Byte ins Pattern im RAM und in die Kopie der Klangerzeugung, klemmt nicht |
| `0xC034886C` | Zeiger auf das Objekt, das der Setter bekommt |
| `0xC03487EC` | Beobachter des Parameterfensters: `[0xC03487EC] + 4` an die Melde-Funktion, die Nachricht ist ein Byte mit dem Code des Fensters, drei Füllbytes und das Byte des Werts als Wort |

Die Nummern der Werte und die Codes des Fensters stehen in `data/script/contract.mjs` (`PART_WRITES`). Auf der blauen
Electribe ist der Setter nicht vermessen, die Laufzeit hat dort 0 als Adresse und schreibt nichts.

## Vergleich mit dem Regler (gemessen)

LEVEL von Part 1 einmal mit dem Regler (Panel-Nachricht `[2, 0, 0, 60, 0]`, ergibt 30), einmal mit
`korg.parts[0].level = 30` in einem anderen Lauf. Verglichen sind 0x4900 Byte ab dem Block des Patterns im RAM.

| | Hacktribe | Korg rot | Korg blau |
|---|---|---|---|
| Bytes, die der Regler ändert | 2072, 16454 | 2072, 16454, 17060 bis 17063 | |
| Bytes, die das Plugin ändert | 2072, 16454 | 2072, 16454 | keine |
| Display danach wie nach dem Regler | ja | ja | |

2072 ist LEVEL im Pattern (Part 0 ab 2048, LEVEL an Stelle 24), 16454 die Kopie der Klangerzeugung. 17060 bis 17063 setzt
nur der Regler der roten Original-Firmware, ein Wort mit dem letzten Wert des Reglers (30); ein Plugin dreht keinen Regler
und lässt es stehen.

Ein Part, der nicht gewählt ist, ändert sich in denselben zwei Stellen, das Display bleibt. Werte außerhalb des Bereichs
werden geklemmt (`pitch` -100 ergibt -63, Byte 0xC1), negative Werte stehen als Byte (`pan` -20 ergibt 0xEC).

## Kopieren und Speichern (gemessen)

Ein Plugin liest mit `korg.read.patternBytes` 768 Byte (64 Steps) von Part 3 aus Pattern 6 der Bank, schreibt sie mit
`korg.seq.writeSteps` in Part 8 des laufenden Patterns und zieht mit `setPartValue` 13 Werte nach. Die ersten acht Bytes
jedes Steps sind danach wie in der Quelle, die Bytes 8 bis 11 unverändert. WRITE legt das Pattern in seinen Platz der Bank,
nach dem Wechsel auf das nächste Pattern und zurück ist das Pattern im RAM Byte für Byte gleich. Auf allen drei Firmwares
gleich, auf der blauen ohne die Werte.
