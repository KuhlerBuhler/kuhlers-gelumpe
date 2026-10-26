# Die Sample-Datei `e2sSample.all` und die Seite Samples

Stand 2026-10-25. Das Format ist aus dem Export der Firmware und aus eigenen Dateien im Emulator belegt
([virtuelle-sd.md](virtuelle-sd.md), [Sample-Fehler](../messungen/2026-10-15-sample-fehler.md),
[Metadaten](../messungen/2026-10-07-sample-metadaten-ram.md)). Die Samples in den Tests sind eine Formel, kein Korg-Sample.
Der Code dazu steht in `src/sample-file.mjs`, die Seite in `site/app/sampleset.mjs` (`BLECHTRIBE -> Samples`).

## Das Format (gemessen)

| Teil | Inhalt |
|---|---|
| Kopf, 4096 Byte | 16 Byte `e2s sample all`, `0x1A`, `0`; danach 1020 Offsets (32 Bit, little endian), einer je Platz, 0 heißt leer |
| Plätze | 0 bis 499 sind die Werks-Samples und stehen nicht in der Datei. Die Firmware lädt 500 bis 998, am Gerät 501 bis 999 |
| Eintrag | eine RIFF/WAVE-Datei je Sample: `fmt `, `data` und `korg` |
| `korg` | `esli` und der 1172 Byte lange Satz der Firmware: Platz (Byte 0 und 78), Name (Byte 2, 16 Byte), Kategorie, Loop, Ende, One-Shot, Rate (Byte 72), Slices |

Die Länge eines Eintrags steht nicht im Kopf, sie ist die RIFF-Größe plus 8. Ein Eintrag, den der Lader nicht nehmen kann (kein PCM, nicht 16
oder 24 Bit, mehr als zwei Kanäle, Platz belegt), wird übersprungen, wenn BLECHTRIBE den Patch `sample-errors` hat.

## Was die Seite tut

- Liest die Datei, zeigt Platz, Name, Format, Länge und Größe je Sample. Ein Eintrag, den sie nicht lesen kann, steht mit dem
  Grund da und lässt sich entfernen.
- **Hinzufügen** nimmt eine WAV (PCM, 16 oder 24 Bit, ein oder zwei Kanäle) und legt sie auf den ersten freien Platz ab 501.
  Hat die WAV einen eigenen `esli`-Satz, bleibt er und bekommt nur Platz und Name. Sonst baut die Seite den Satz, den
  `tools/emu/sampleset.py` baut. 24 Bit und Stereo lädt der Lader im Emulator, am Gerät ist das **nicht geprüft**.
- **Entfernen** lässt keine Lücke: die Einträge dahinter rücken auf, der Kopf bekommt die neuen Offsets, die Datei endet beim
  letzten Eintrag. Es gibt keinen Knopf zum Aufräumen. Ein neuer Eintrag kommt ans Ende.
- Änderungen stehen erst als Vorschlag da (`wird entfernt`, `neu`) und lassen sich zurücknehmen. **Speichern** schreibt alles
  auf einmal.
- Die Electribe liest `e2sSample.all` nur beim Start. Die Seite sagt es vor dem Speichern und im Hinweis danach.

## Der Plan einer Änderung

`planChange` gibt zurück, was die Datei ändert, so wenig wie nötig: den neuen Kopf, die Einträge, die bleiben und wohin sie
rücken (aufsteigend, jeder nur nach unten, also liest ein einfaches Kopieren nie schon überschriebene Bytes), und die neuen Einträge
am Ende. Übertragen werden müssen nur der Kopf und die neuen Samples, das Verschieben macht der Besitzer der Datei. Aus dem
Kartenleser läuft der Plan im Speicher (`applyPlan`).

## Der Weg übers Kabel (SysEx): Stand

**gemessen, offline im Code:** Die FILE-Befehle von BLECH (`0x65` FILE READ, `0x66` FILE BEGIN, `tools/patch/blech_sysex.py`)
erreichen nur zwei Dateien: `SYSTEM.VSB` und `ORIGINAL.BIN` im Ordner der Firmware (Bit 31 des Offsets wählt), dazu schreibt
`0x67` PLUGIN BEGIN eine Plugin-Datei. Offset plus Länge ist auf `0x200100` begrenzt. `e2sSample.all` ist damit in keinem der
Ordner `electribe sampler`, `hacktribe` und `blechtribe` erreichbar. Für den Weg übers Kabel braucht es eine Erweiterung der
Firmware: Lesen und Schreiben der Sample-Datei mit größeren Offsets, und einen Befehl, der nach dem Entfernen die Einträge auf der
Karte aufrücken lässt und die Datei kürzt. **offen**, noch nicht gebaut.
