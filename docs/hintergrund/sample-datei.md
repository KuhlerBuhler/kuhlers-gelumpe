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
- **Als Datei speichern** holt die ganze Datei der Karte über USB auf den Rechner, mit Audio, als Sicherung oder zum Bearbeiten
  ohne Gerät. Jeder Block kommt mit seinem CRC-32, die Größe wird am Ende nochmal gefragt, und die Bytes müssen sich als Sample-Datei
  lesen lassen. Abbrechen geht zwischen zwei Stücken von 256 KiB. Eine volle Datei (26,8 MB) dauert rund zwei Minuten
  ([Messung](../messungen/2026-10-26-sample-datei-sysex.md#am-gerät-lesegeschwindigkeit)).

## Der Plan einer Änderung

`planChange` gibt zurück, was die Datei ändert, so wenig wie nötig: den neuen Kopf, die Einträge, die bleiben und wohin sie
rücken (aufsteigend, jeder nur nach unten, also liest ein einfaches Kopieren nie schon überschriebene Bytes), und die neuen Einträge
am Ende. Übertragen werden müssen nur der Kopf und die neuen Samples, das Verschieben macht der Besitzer der Datei. Aus dem
Kartenleser läuft der Plan im Speicher (`applyPlan`).

## Der Weg übers Kabel (SysEx)

**gemessen im Emulator** ([Messung](../messungen/2026-10-26-sample-datei-sysex.md)), am Gerät **nicht** gemessen. Die FILE-Befehle von
BLECH (`0x65` FILE READ, `0x66` FILE BEGIN, `tools/patch/blech_sysex.py`) erreichten vorher nur `SYSTEM.VSB` und `ORIGINAL.BIN` im
Ordner der Firmware (Bit 31 des Offsets wählt), dazu `0x67` PLUGIN BEGIN eine Plugin-Datei, mit Offset plus Länge bis `0x200100`.
`e2sSample.all` war in keinem der Ordner `electribe sampler`, `hacktribe` und `blechtribe` erreichbar. Jetzt gilt:

| Befehl | Was er tut |
|---|---|
| Bit 30 im Offset von FILE READ und FILE BEGIN | `KORG/<Ordner>/Sample/e2sSample.all`; mit Bit 31 dazu die Tauschdatei `e2sSample.tmp` daneben. Der Ordner ist der, den das Update nimmt (die eigene Funktion der Firmware), Offset plus Länge bis 256 MiB |
| `0x71` FILE COPY, Antwort `0x79` | Quelle, Ziel (je Selektor und Offset, die zwei Sample-Dateien, nicht dieselbe) und Länge 1 bis 256 KiB: kopiert auf der Karte in Stücken von 16 KiB, beide Dateien offen. Antwort: Status, kopierte Bytes, CRC-32 davon. Ist die Quelle kürzer als verlangt, wird abgelehnt, bevor das Ziel angelegt wird |
| `0x72` FILE DELETE, Antwort `0x7A` | löscht eine der beiden Sample-Dateien mit `f_unlink` der Firmware. SYSTEM.VSB, ORIGINAL.BIN und Plugins sind abgelehnt |
| `0x73` FILE CRC, Antwort `0x7B` | liest bis 256 KiB einer Sample-Datei von der Karte und schickt nur Status, Offset, Länge und CRC-32 |

Ein Block bei Offset 0 schneidet `e2sSample.all` nicht ab (er schreibt den Kopf an Ort und Stelle, `FA_OPEN_ALWAYS`), bei der Tauschdatei
macht er sie neu. INFO meldet Bit 7 der Flags, wenn die Befehle da sind. Auf der blauen Electribe 2 fehlt `f_unlink` im Abbild, dort
antwortet DELETE mit 6 und INFO meldet Bit 7 nicht. Der Code liegt in einem zweiten Abschnitt bei `0xC017B950` (1116 Byte), weil der
erste bis `0xC0173000` reicht, wo der Puffer der Sync Group anfängt.

### Warum die Datei über eine Tauschdatei kleiner wird

Das FatFs in der Firmware hat kein `f_truncate` und kein `f_rename` (**offline** gelesen: `f_getfree` `0xC009E85C` steht direkt vor
`f_unlink` `0xC009E9B8`, `follow_path` `0xC009CF2C` wird nur von `f_open`, `f_opendir`, `f_stat`, `f_unlink` und `f_mkdir` gerufen). Eine
Datei lässt sich also nicht kürzen und nicht umbenennen. Eigene Eingriffe in die FAT-Kette kommen nicht in Frage: ein Absturz darf Daten
kosten, die Karte darf er nicht beschädigen. Entfernen geht deshalb so, und die Seite macht es von selbst:

1. Kopf und neue Samples der neuen Datei kommen als Tauschdatei auf die Karte; was bleibt, kopiert die Electribe auf der Karte
   (FILE COPY, aneinanderliegende Samples in einem Zug).
2. Die Seite prüft die Tauschdatei: Größe und CRC-32, den das Gerät selbst von der Karte liest (FILE CRC), gegen die Teil-CRCs der
   Antworten (`src/crc-combine.mjs`).
3. Erst dann wird die alte Datei gelöscht, die Tauschdatei zurückkopiert, wieder geprüft und die Tauschdatei gelöscht.

Bis zum Löschen der alten Datei ist an ihr nichts verändert, ein Fehler davor löscht nur die Tauschdatei. Bricht es danach ab (Kabel
gezogen, Strom aus), liegt die fertige Tauschdatei auf der Karte; beim nächsten Lesen über USB bietet die Seite an, sie fertigzustellen,
oder sie zu löschen, wenn ihr Kopf nicht zu ihrer Größe passt. Fehlt `e2sSample.all` dazwischen, lädt die Electribe beim Start keine
Samples, die Karte ist heil. Eine Wiederherstellung beim Einschalten, ohne die App, gibt es **nicht**.

Nur Hinzufügen braucht das nicht: die neuen Samples kommen hinter die alten, der Kopf zuletzt, ein Abbruch dazwischen lässt Samples
zurück, die niemand listet, nie einen Kopf ohne seine Samples.

### Wie die Seite listet

Sie liest den Kopf und von jedem Sample die ersten 44 Byte und den Namen im Satz hinter dem Audio, nicht das Audio. Ein Eintrag mit
anderem Aufbau als fmt, data, korg steht mit seiner Länge aus dem RIFF-Kopf und dem Vermerk `Aufbau nicht erkannt` da und lässt sich
entfernen. Fehlt die Datei, ist die Liste leer, und ein erstes Sample legt sie an.
