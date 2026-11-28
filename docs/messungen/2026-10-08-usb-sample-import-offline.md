# USB-Sampleimport ohne SD: Offline-Machbarkeit

Der originale WAV-Importer der Firmware, offline in [Unicorn](../glossary.md#unicorn) ausgeführt.

## Unveränderter WAV-Importer

- **Gemessen offline:** Originaler ARM-WAV-Importer 0xC0035B10:
  `(FILE*, Metadatenpuffer*, Zielindex, Namenspfad*)`, r0-r3.
  Metadatenpuffer 0x494 Byte. FILE-Position +8, Dateigröße +12.
  Dateilesen 0xC009DD74, Seek 0xC009E404.
- **Gemessen offline:** Dabei ersetzen Speicher-WAVs die beiden
  Dateioperationen. Abfragen der Sample-Manager-Kapazität sind simuliert;
  originaler Parser, Reservierung 0xC004EDF0 und RAM-Tabellenupdates
  werden ausgeführt. Ein WAV-Puffer allein ist kein gültiges FILE-Objekt.
- **Gemessen offline:** Fünf erfolgreiche Tests mit selbst erzeugten WAVs:
  Mono 64 Byte, Mono sechs Byte, Mono 65.570 Byte über zwei Blöcke,
  Stereo, 44.100 Hz. Status 0, PCM-Übergabe exakt, Name, Offset, Länge,
  aktive Markierung und Samplerate korrekt. Testindex 742 in kontrolliertem
  Emulatorzustand; keine Aussage über einen freien Slot am echten Gerät.
- **Gemessen offline:** Audioübergabe zunächst als [DSP](../glossary.md#dsp)-API simuliert;
  der originale [DSP-Schreibpfad](2026-10-08-dsp-audiopfade.md) wurde
  separat mit emulierten Ports und Nachbarbyte-Prüfung ausgeführt.
- **Gemessen offline:** Platzmangel Status 0x21 vor Reservierung und ohne
  DSP-Schreiben. Audio-Lesefehler Status 4 nach Reservierung lässt den
  erhöhten Allocatorzeiger und aktive Metadaten zurück: kein Rollback im
  geprüften Originalpfad.

## Grenzen

- **Gemessen:** Nur lokale Emulation, keine Geräte-, SD- oder Flash-Schreibbefehle.
  Kein realer USB-Sampleimport durchgeführt. Der gefundene Pfad braucht kein
  Flash-Schreiben; ein Import wäre flüchtig, Persistenz ginge nur über das
  reguläre Speichern oder Exportieren.
- **Gemessen:** Der WAV-Importer lässt sich nur über ein FILE-Objekt bedienen;
  eine austauschbare Schnittstelle für Speicherdateien gibt es nicht.

[Schutzgrenzen](../speicherbereiche.md). Keine Firmware oder WAV-Fixtures
im Repository; Test-WAVs wurden selbst erzeugt und liegen außerhalb.
