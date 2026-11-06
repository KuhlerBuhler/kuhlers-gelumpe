# Byte-Ziele der Plugin-Steuerungen

Stand: 2026-11-06. [English version](PARAMSET-BYTE-FINDINGS.en.md).

Dieses Blatt sammelt die bekannten Pattern-Bytes der dreizehn schreibbaren `korg.parts[i]`-Felder, der sechs Tasten, der Encoder CUTOFF, Sample/OSC, Modulation und IFX Type sowie der Zweitfunktion SHIFT + OSC PITCH fuer Glide.

Alle Offsets sind relativ zum Zeiger auf das aktive Pattern. Die Werte in der Tabelle der schreibbaren Felder gelten fuer Part 0, den ersten Part. Bei diesen dreizehn Feldern liegt das Part-Byte fuer Part n bei `Feld-Offset + 0x330 * n`; die zugehoerige Kopie liegt bei `Kopier-Offset + 0x24 * n`. Diese Schrittweiten sind fuer den Writer durch den nativen Test belegt. Die Tasten sowie Sample/OSC, Modulation und IFX Type wurden nur fuer Part 0 verglichen. CUTOFF und Glide wurden fuer alle Parts im Emulator geprueft.

## Schreibbare Part-Eigenschaften

Der Writer setzt das Hauptbyte und die angegebene Kopie auf denselben Wert. Die Kopieradresse ist pro Feld einzeln angegeben, denn der Abstand zum Hauptbyte ist nicht fuer alle Felder gleich.

| Nr. | Zuweisung | Hauptbyte Part 0 | Kopie Part 0 |
|---:|---|---:|---:|
| 1 | `korg.parts[0].level = value` | `0x81C` | `0x404A` |
| 2 | `korg.parts[0].pan = value` | `0x81D` | `0x404B` |
| 3 | `korg.parts[0].pitch = value` | `0x828` | `0x4052` |
| 4 | `korg.parts[0].resonance = value` | `0x812` | `0x4040` |
| 5 | `korg.parts[0].egInt = value` | `0x813` | `0x4041` |
| 6 | `korg.parts[0].modDepth = value` | `0x816` | `0x4044` |
| 7 | `korg.parts[0].modSpeed = value` | `0x815` | `0x4043` |
| 8 | `korg.parts[0].attack = value` | `0x818` | `0x4046` |
| 9 | `korg.parts[0].decay = value` | `0x819` | `0x4047` |
| 10 | `korg.parts[0].ifxEdit = value` | `0x826` | `0x4050` |
| 11 | `korg.parts[0].oscEdit = value` | `0x80F` | `0x403D` |
| 12 | `korg.parts[0].cutoff = value` | `0x811` | `0x403F` |
| 13 | `korg.parts[0].glide = value` | `0x829` | `0x4053` |

Die Offsets stammen aus dem Emulatorvergleich der Reglerbewegungen. Die Kopieradressen sind ausserdem im internen Writer und seinem nativen Test festgehalten. Siehe [Reglerbewegungen](docs/messungen/2026-10-15-tap-motion.md), [Writer](tools/patch/script_hw.s) und [Writer-Test](tools/patch/test_script_hw.py).

### CUTOFF und Glide, Mirror fuer alle Parts

Die Spiegeladressen und Schrittweiten wurden fuer alle 16 Parts durch Eingaben am Panel im Emulator geprueft. Der Laufzeit-Writer synchronisiert fuer beide Felder das Hauptbyte und den Mirror. Die Messung belegt RAM-Aenderungen, keine Klangwirkung am Geraet.

| Feld | Hauptbyte Part 0 | Mirror Part 0 | Hauptbyte Part n | Mirror Part n |
|---|---:|---:|---|---|
| `cutoff` | `0x811` | `0x403F` | `0x811 + 0x330 * n` | `0x403F + 0x24 * n` |
| `glide` | `0x829` | `0x4053` | `0x829 + 0x330 * n` | `0x4053 + 0x24 * n` |

CUTOFF wurde mit einer Bewegung des Encoders CUTOFF (Encoder-Index `2`) um einen Schritt nach unten geprueft. Hauptbyte und Mirror wechselten auf jedem Part gemeinsam von 127 auf 126. Fuer Glide blieb SHIFT (`0x0A`) gedrueckt, waehrend der Regler OSC PITCH (Regler-Index `2`) bewegt wurde. Der Eingabewert war `200 + 2 * Part`; die Firmware setzte Glide auf `100 + Part`. In beiden Proben wechselten auf jedem Part genau Hauptbyte und Mirror auf denselben Wert. Siehe [CUTOFF- und Glide-Mirror](docs/messungen/2026-11-06-glide-mirror.md).

Nach dem Schreiben eines der dreizehn Werte ruft der Sampler-Laufzeitcode den Firmwarepfad zur Parameter-Aktualisierung auf: `0xC0048460` mit Ziel-Part und feldspezifischem Code, danach `0xC0059720` mit Part, Setter-ID und Wert. Fuer PAN, EG INT und OSC PITCH wird der signierte Wert fuer den Setter um 64 verschoben. Die Zuordnung ist aus Hacktribe-Firmware 2.02 hergeleitet und im Emulator an den Pattern-Bytes geprueft; der Emulator bildet den DSP nicht ab. Die Klangwirkung muss am Geraet geprueft werden. Fuer Synth ist dieser Firmwarepfad noch nicht zugeordnet. Siehe [Parameter-Aktualisierung](docs/messungen/2026-11-06-part-param-refresh.md).

Die Typ-12-Benachrichtigung wird beim Schreiben nicht mehr gesendet. Sie koennte weiterhin nuetzlich sein, wenn die UI eine Parameteranzeige aktualisieren soll; sie ist kein bestaetigter DSP-Refresh. Siehe [Erinnerung](PARAMETER-REFRESH-REMINDER.md).

## Tasten und Encoder

Die folgenden Ergebnisse stammen aus einem Pattern-RAM-Vergleich im Emulator mit der eigenen Hacktribe-`SYSTEM.VSB`, leerem Flash und dem Startpattern. Pro Probe wurde ein frischer Emulatorzustand verwendet. Die Tasten wurden einmal gedrueckt; bei den Encodern wurden beide Richtungen getestet. Die Tabelle nennt alle stabil geaenderten Bytes im gelesenen Pattern-Block.

| Nr. | Bedienung | Hauptbytes Part 1 | Weitere Bytes Part 1 | Beobachtung |
|---:|---|---|---|---|
| 12 | LPF-Taste `0x12` | Filtertyp `0x810`: `1 -> 2` | `0x403E`: `1 -> 2` | Hauptbyte und Kopie gleich |
| 13 | HPF-Taste `0x14` | Filtertyp `0x810`: `1 -> 7` | `0x403E`: `1 -> 7` | Hauptbyte und Kopie gleich |
| 14 | BPF-Taste `0x16` | Filtertyp `0x810`: `1 -> 12` | `0x403E`: `1 -> 12` | Hauptbyte und Kopie gleich |
| 15 | MFX-Send-Taste `0x1A` | MFX Send `0x81F`: `1 -> 0` | `0x404D`: `1 -> 0` | Hauptbyte und Kopie gleich |
| 16 | Amp-EG-Taste `0x20` | EG an `0x81E`: `0 -> 1` | `0x404C`: `0 -> 1` | Hauptbyte und Kopie gleich |
| 17 | IFX-On-Taste `0x21` | IFX an `0x824`: `0 -> 1` | `0x404E`: `0 -> 127` | Kopie hat eine andere Kodierung |
| 18 | Sample/OSC-Encoder `1`, Richtung `+1` | Sample, Low-Byte `0x80C`: `0 -> 1` | `0x403A`: `0 -> 1` | Nur das Low-Byte aendert sich |
|  | Sample/OSC-Encoder `1`, Richtung `-1` | Sample `0x80C-0x80D`: `0, 0 -> 17, 1`; OSC Edit `0x80F`: `0 -> 32` | Sample `0x403A-0x403B`: `0, 0 -> 17, 1`; OSC Edit `0x403D`: `0 -> 32` | Sample wird little-endian `0x0111` |
| 19 | Modulation-Encoder `3`, Richtung `+1` | Mod-Typ `0x814`: `0 -> 1`; Speed `0x815`: `23 -> 32`; Depth `0x816`: `0 -> 97` | `0x4042`: `0 -> 1`; `0x4043`: `23 -> 32`; `0x4044`: `0 -> 97` | Alle drei Bytes und ihre Kopien aendern sich |
|  | Modulation-Encoder `3`, Richtung `-1` | Mod-Typ `0x814`: `0 -> 71`; Speed `0x815`: `23 -> 42`; Depth `0x816`: `0 -> 127` | `0x4042`: `0 -> 71`; `0x4043`: `23 -> 42`; `0x4044`: `0 -> 127` | Alle drei Bytes und ihre Kopien aendern sich |
| 20 | IFX-Type-Encoder `4`, Richtung `+1` | IFX-Typ `0x825`: `0 -> 1` | `0x404F`: `0 -> 1` | Hauptbyte und Kopie gleich |
|  | IFX-Type-Encoder `4`, Richtung `-1` | IFX-Typ `0x825`: `0 -> 48` | `0x404F`: `0 -> 48` | Hauptbyte und Kopie gleich |

Die Encoderwerte haengen vom Startzustand des Patterns ab. Insbesondere aendern Sample/OSC und Modulation mehrere Felder bei einer Bewegung. Die IFX-Kopie liegt bei `0x404E` beziehungsweise `0x404F`, nicht an derselben relativen Stelle wie die meisten anderen Kopien.

Bedienfeldnummern: [Bedienfeldmessung](docs/messungen/2026-10-08-panel-bedienung.md). Der Emulator bildet den DSP nicht ab. Diese neun Ergebnisse bestaetigen daher Pattern-Schreibvorgaenge, nicht die Audioaenderung am Geraet.

## Nicht bestaetigt

- Die Ergebnisse fuer die sechs Tasten und drei Encoder wurden im Emulator ermittelt, nicht am Geraet.
- Fuer die sechs Tasten sowie Sample/OSC, Modulation und IFX Type ist die Kopieradresse weiterer Parts nicht geprueft.
- CUTOFF und SHIFT + OSC PITCH wurden im Emulator fuer alle Parts geprueft, nicht am Geraet.
- Ein geaendertes Byte allein belegt nicht, dass die zweite Stelle die Klangaktualisierung am Geraet bewirkt.
- Sample/OSC und Modulation wurden mit dem Startpattern geprueft. Andere Presets koennen andere Ausgangswerte und damit andere resultierende Bytes haben.
