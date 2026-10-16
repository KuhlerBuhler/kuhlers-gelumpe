# USB-Sampleimport ohne SD: Offline-Machbarkeit

## Unveränderter WAV-Importer

- **Gemessen offline:** Originaler ARM-WAV-Importer 0xC0035B10:
  `(FILE*, Metadatenpuffer*, Zielindex, Namenspfad*)`, r0-r3.
  Metadatenpuffer 0x494 Byte. FILE-Position +8, Dateigröße +12.
  Dateilesen 0xC009DD74, Seek 0xC009E404.
- **Gemessen offline:** In Unicorn ersetzen Speicher-WAVs die beiden
  Dateioperationen. Abfragen der Sample-Manager-Kapazität sind simuliert;
  originaler Parser, Reservierung 0xC004EDF0 und RAM-Tabellenupdates
  werden ausgeführt. Ein WAV-Puffer allein ist kein gültiges FILE-Objekt.
- **Gemessen offline:** Fünf erfolgreiche Tests mit selbst erzeugten WAVs:
  Mono 64 Byte, Mono sechs Byte, Mono 65.570 Byte über zwei Blöcke,
  Stereo, 44.100 Hz. Status 0, PCM-Übergabe exakt, Name, Offset, Länge,
  aktive Markierung und Samplerate korrekt. Testindex 742 in kontrolliertem
  Emulatorzustand; keine Aussage über einen freien Slot am echten Gerät.
- **Gemessen offline:** Audioübergabe zunächst als DSP-API simuliert;
  der originale [DSP-Schreibpfad](2026-10-08-dsp-audiopfade.md) wurde
  separat mit emulierten Ports und Nachbarbyte-Prüfung ausgeführt.
- **Gemessen offline:** Platzmangel Status 0x21 vor Reservierung und ohne
  DSP-Schreiben. Audio-Lesefehler Status 4 nach Reservierung lässt den
  erhöhten Allocatorzeiger und aktive Metadaten zurück. Kein Rollback im
  geprüften Originalpfad; dieser Fehler muss vor einer neuen Integration
  behandelt werden.

## Folgerung und offene Umsetzung

- **Vermutet:** CPU-Uploadpuffer plus RAM-Helfer könnte validierte PCM-Daten
  und Metadaten über vorhandenen Allocator/Schreibwrapper in einen freien
  User-Slot laden. Der gefundene Pfad benötigt kein Flash-Schreiben.
- **Vermutet:** Ein gezielter Speicherdatei-Adapter könnte den ganzen
  WAV-Importer bedienen. Direkte Dateiaufrufe sind aber keine vorhandene
  austauschbare Schnittstelle. Globale Dateifunktions-Patches wären eine
  zusätzliche Änderung mit Auswirkungen auf andere Dateioperationen.
- **Vermutet/offen:** Cache-sichere Ausführung, Task-Kontext und
  Serialisierung, aktuelle freie Slotwahl, strenge Adress-/Längengrenzen,
  Backup und vollständiger Fehler-Rollback fehlen. Execute allein stellt
  keinen fertigen USB-Import bereit.
- **Vermutet/offen:** Import wäre zunächst flüchtig. Persistenz benötigt
  separat reguläres Speichern/Exportieren; Boot-/Autoload-Verhalten wurde
  durch diese Tests nicht geprüft.
- **Gemessen:** Nur lokale Emulation, keine Geräte-, SD- oder Flash-
  Schreibbefehle. Kein realer USB-Sampleimport durchgeführt. Die Tests
  ersetzen keine vorherige SimDevice-Prüfung zukünftiger Transportskripte.

[Schutzgrenzen](../speicherbereiche.md). Keine Firmware oder WAV-Fixtures
im Repository; Test-WAVs wurden selbst erzeugt und liegen außerhalb.
