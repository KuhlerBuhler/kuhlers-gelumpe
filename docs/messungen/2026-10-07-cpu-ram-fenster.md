# Vollständiges CPU-RAM-Adressfenster

- **Gemessen am Gerät:** 8.192 Blöcke à 0x4000 Byte, insgesamt 134.217.728
  Byte, von 0xC0000000 bis einschließlich 0xC7FFFFFF. Alle beantwortet,
  ausschließlich RAM-Lesen. Vorher SimDevice-Kanal-9-Prüfung des Lesers.
- **Gemessen:** Zeitlich zusammengesetzt aus 89,28125 MiB und späteren
  38,71875 MiB. Kein atomarer Zustand. SHA256:
  `c114f10457b1dabc3ad6f8694aa3af9be63c5429da627c6358490ce781e0f26a`.
- **Gemessen offline:** 4.074 von 4.096 Blockpaaren im Abstand 64 MiB sind
  identisch, insgesamt 6.925 abweichende Byte zwischen den Hälften.
- **Vermutet:** Spiegelung von 64 MiB. Kein Beleg für 128 MiB physisches
  RAM oder eine abschließend bestimmte obere Lesegrenze. Aliase bei
  Schutzregeln berücksichtigen, nicht die zweite Hälfte als frei ansehen.
- **Gemessen offline:** Kein Treffer für geprüfte Audiomitten der aktuellen
  SD-Bank: drei Samples in 84 Varianten einschließlich LE/BE, 8 Bit und
  48 kHz; außerdem 166 glatte Mitten als PCM16 LE und 174 weitere
  Integer-/Float-/Resampling-Darstellungen. Negative Suchen sind keine
  vollständige Abwesenheitsprüfung beliebiger Audiokodierungen.
- **Gemessen am Gerät:** Beim Sampler ist das überprüfte 64-KiB-Fenster
  ab 0xC3000000 kein bestätigtes PCM-Audio: Nachbarkorrelation rund 0,02,
  keine geprüften Sampletreffer. Die vom blauen Synth bekannte Zuordnung
  darf nicht auf den Sampler übertragen werden.
- **Vermutet/offen:** Laufende Sampledaten sind im geprüften CPU-Dump nicht
  lokalisiert. Der [DSP-Pfad](2026-10-08-dsp-audiopfade.md) beschreibt einen
  anderen Adressraum und einen CPU-Arbeitspuffer, keine direkte PCM-Basis.

Rohdumps und Referenz-Sampledateien bleiben außerhalb des Repositories.
