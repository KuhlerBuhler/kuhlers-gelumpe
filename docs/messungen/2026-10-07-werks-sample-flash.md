# Werks-Samplebank im Flash: Struktur und vollständige Dekodierung

## Lesemessung und frühere Flash-Karte

- **Gemessen am Gerät, 7. Oktober 2026:** `[0x800000, 0x1000000)` in
  512 Blöcken à 0x4000 Byte vollständig gelesen, letzter Start 0xFFC000.
  8.388.608 Byte in 40,757 Sekunden, keine fehlende Antwort. Kanal aus
  Device Search. Leser vorher gegen SimDevice auf Kanal 9 geprüft;
  Timeoutfall stoppt beim ersten fehlenden Reply. Kein Zugriff ab 0x1000000.
- **Gemessen:** SHA256 nach Lesen und Transfer:
  `f0fe0ef0ccdd3227cfa5dd3436a9415f64dfd9ba4ac2ddba5d44c982afc68e38`.
- **Gemessen am alten Dump vom 14. September:** Kennungen bei 0x000000
  (TIPA), 0x220000 (KORGele2sUSR), 0x230000/0x630000 (GLST), Nutzer-
  Patterns ab 0x240000, SQEZ-Werksbank ab 0x640000. 250 Nutzer-Pattern-
  Blöcke à 0x4000 enden exklusiv 0x628000. SQEZ umfasst 0x20017 Byte,
  Ende exklusiv 0x660017. Die alten Dateien decken `[0, 0x800000)` ab;
  zusammen mit dem neuen Dump kein zeitgleiches Gesamtimage.
- **Gemessen am alten Dump:** Die 64-KiB-Fenster bei 0x6B0000,
  0x6C0000 und 0x700000 sind nicht identisch; als PCM16 LE Korrelation
  0,031-0,034. `[0x7F0000, 0x800000)` fast ganz FF, acht andere Bytes.
- **Vermutet/offen:** Alte Bezeichnung „PCM ab 0x6B0000“ unbelegt.
  Niedrige Korrelation allein schließt kodiertes Audio nicht aus.
  Die alte Grenze 0x1D0000 ist keine bewiesene exakte Code-Endadresse.

## Werksbank-Tabellen

**Gemessen offline:** Ab 0x800000 Kennung KORGelec2PCM; Headerverweise:

| Abschnitt | Flashadresse |
|---|---|
| DRMP | 0x800040 |
| DRUM | 0x800080 |
| MSPR | 0x8000C0 |
| MSRL | 0x801A90 |
| MSVS | 0x802790 |
| SMPR | 0x805B10 |
| SMPL | 0x8074E0 |

- **Gemessen offline:** MSPR-Namen ab 0x8000E0, 411 Records à 16 Byte,
  acht ASCII-Zeichen je Kurzname. SMPR-Records ab 0x805B30, ebenfalls
  411 × 16 Byte: u32 LE bei +0 logischer PCM-Byteoffset, +4 Loop, +8 End,
  +12 Flags. Wellenlänge ist End+2; Bit 16 der Flags passt zu One-Shot.
  Bedeutung der unteren 16 Flagbits und weiterer Headerwerte bleibt offen.
- **Gemessen offline:** Alle Tabellen passen zu 403 Referenz-Samples,
  Indizes 18-420: 395 Mono plus acht Stereo mit je zwei Waveforms = 411.
  Loop/End/One-Shot stimmen für alle Mono-Samples mit esli überein.
- **Gemessen offline:** Nach Sortierung der Starts lückenloser logischer
  PCM-Strom von 0 bis 0xFD9AB0 (16.620.208 Byte). Nur 72 von 410
  Übergängen sind auch in Indexreihenfolge lückenlos. Ein SMPR-Start ist
  kein direkter physischer Flash- oder CPU-Zeiger.

## Blockformat und Dekoder

- **Gemessen offline:** SMPL-Nutzdaten `[0x807500, 0xE5F013)`,
  4.058 Blöcke: 4.057 × 2.048 Werte, letzter Block 1.368 Werte.
  Big-Endian-u16-Kopf: obere drei Bits Modus, untere 13 Bits Wortanzahl.
  Modi 0-4: danach Big-Endian-u16-Länge der kodierten Nutzdaten.
  Modus 7: direkt MSB-gepackte vorzeichenbehaftete 12-Bit-Werte.
- **Gemessen offline:** Modusverteilung: 0=413, 1=685, 2=1.073,
  3=896, 4=987, 7=4. Modi 5/6 nicht beobachtet oder geprüft.
- **Gemessen offline:** Komprimierte Daten beginnen mit vier Nibbles für
  Breiten `(Nibble + 1) & 15`, dann Zweibit-Startauswahl 3 für volle
  12 Bit. Das Minimum der aktuellen signed Breite ist Escape. Bei voller
  Breite folgt 0 für den echten Wert -2.048, 1 für Wechsel/Abschluss.
  Bei einem Wechsel wählt ein Zweibitwert aus der sortierten Breitenauswahl
  einschließlich 12 Bit, unter Ausschluss der aktiven Breite. Vier
  Optionen bleiben. Ein Escape nach der letzten Ausgabe beendet den Block;
  restliche Paddingbits sind null. Breite 0 ist hier ein ungenutzter
  Tabelleneintrag, kein geprüfter Datenlauf.
- **Gemessen offline:** Verkürzte Restwerte werden zur Vorhersage addiert:
  Modus 0: 0; 1: p1; 2: 2*p1-p2; 3: 3*p1-3*p2+p3;
  4: p1 + trunc((p1-p2)/2), Richtung null. p1-p3 sind vorherige
  dekodierte Werte desselben Blocks. Volle 12 Bit sind direkte Werte.
- **Gemessen offline:** 8.310.104 Werte mit Faktor 16 ergeben PCM16.
  Jeder PCM-Payload aller 403 Referenz-Samples stimmt bytegenau, auch
  Stereo nach Zusammenführen der getrennten Kanäle. Zwei getrennte
  Decoder-Ausführungen liefern denselben gesamten logischen PCM-Strom:
  SHA256 `224f0c8c5464a37780ce9a14676a3361f42f2921cb83f153a72662658dc23e2a`.
  Referenzdatei-SHA256:
  `9bb825d3c88d0f62d1f44d412f71ea9e3c2bb589f491e2dd9858133f46450832`.
- **Gemessen offline:** Sechs ungültige Eingaben abgewiesen: leer, falsche
  Kennung, kurzer Kopf, kurzer erster Payload, kurzer letzter Payload,
  unbekannter Modus. Kein Hardware-Schreibweg daraus abgeleitet.
- **Gemessen durch Quellvergleich:** Escape-/Breitenmechanik stimmt mit
  dem [offiziellen Korg-SYRO-Encoder](https://github.com/korginc/volcasample/blob/master/syro/korg_syro_comp.c)
  überein. Electribe-Modi 1/3/4 wurden am Dump bestimmt und vollständig
  gegen die Referenz geprüft. Kein Anspruch auf alle Korg-Codecvarianten.

## Negativsuchen und Grenzen

- **Gemessen offline:** 322 glatte Referenzfenster, 2.398 direkte Varianten
  (PCM16 LE/BE, 8 Bit, 48 kHz) ohne Treffer. Weitere 2.576 12-Bit-/Delta-
  Packvarianten finden einen ganzen 2.048-Wort-Rohblock; danach gelang
  die vollständige Dekodierung. Eine negative direkte PCM-Suche beweist
  daher nicht, dass Audio fehlt.
- **Gemessen offline:** Keine SQEZ/-lh5-/RIFF/esli-Kennung im neuen Dump.
  Roher LH5-Versuch am SMPL-Beginn scheitert. Positivkontrolle: bekannte
  SQEZ-Werks-Patternbank entpackt 4.096.000 Byte, CRC16 0x81C2 korrekt.
  SMPL wird mit dem oben beschriebenen Codec vollständig dekodiert.
- **Gemessen offline:** Kennung und bestätigter kompletter gepackter
  Audio-Rohblock fehlen im zeitlich zusammengesetzten CPU-RAM-Dump.
- **Vermutet/offen:** Laufender DSP-Audiospeicher bleibt direkt ungelöst.
  Dekodierung beweist keinen sicheren Encoder, keine Flash-Schreibfreigabe
  und keine Möglichkeit, Werks-Samples risikofrei per USB zu ersetzen.

Keine Dumps, Werks-Samples, Referenzdatei oder abgeleitete Audiodaten im Repo.
[Speicherkarte und Schutzgrenzen](../speicherbereiche.md).
