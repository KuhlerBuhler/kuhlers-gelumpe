# DSP-Audiopfade und Ausführungsgrenzen, offline

Die ARM-Routinen stammen aus dem bereits gelesenen RAM-Dump. Sie wurden
lokal disassembliert und mit Unicorn ausgeführt; DSP-Ports/GPIO, USB-Ausgang
und Dateiausgabe wurden je Test ersetzt. Kein Geräteaufruf dieser Routinen.

## Lesen und Export

- **Gemessen offline:** Wrapper 0xC004EDDC..0xC004EDEC einschließlich
  Tail-Branch: `(CPU-Zielpuffer, logischer DSP-Byteoffset, count16)`;
  Aufruf 0xC00141F8 → 0xC0014AFC → 0xC001488C, Breite 2.
- **Gemessen offline:** Lesekommando `[0xA9, Offset_low16, Offset_high16,
  count16, 2, 0, 0]` am Port 0x60000002; Daten am Port 0x60000000.
  Frühere Annahme eines Steuerports bei Basis+4 ist falsch.
- **Gemessen offline:** Normaler Wrapper mit freien Sperren gibt Testwerte
  korrekt zurück. Interrupt-Kontext führt zur Assertion; ausgeschaltete
  IRQs liefern beim Sperren Fehler -25, den der Wrapper ignoriert;
  belegte Semaphore führt vor Portzugriff zum Scheduler-Warten.
- **Gemessen offline:** Einzel-/Gesamtexport 0xC0039CC4/0xC0039E68 rufen
  WAV-Schreiber 0xC0039B2C. Puffergeber 0xC00369F0 liefert 0xC0D3A940;
  Freigabe 0xC0036A08 löscht ihn in diesem Pfad nicht.
- **Gemessen offline:** Vier Exportfälle: 17.662 Byte Referenz-PCM,
  66 Byte, leer, 131.074 Byte. RIFF-Ausgaben exakt; große Dateien laufen
  in 65.536-Byte-Blöcken. Der Arbeitsplatz enthält zuletzt den letzten
  Block, nicht notwendigerweise die ganze Datei.
- **Gemessen offline:** Beim geprüften kurzen Referenz-Sample liegt der
  64-Byte-Mittenausschnitt im Exportbuffer bei 0xC0D3CB9E. Die originale
  SysEx-Leseantwort packt ihn korrekt, ohne ihn zu verändern.
- **Vermutet/offen:** Regulärer Export am Gerät und direktes CPU-Lesen
  könnten Audio ohne eigenen RAM-Code sichtbar machen. Export schreibt
  eine WAV auf SD; Bufferlebensdauer und echter Treffer sind ungeprüft.

## Schreiben

- **Gemessen offline:** Sample-Wrapper 0xC004EF28:
  `(CPU-Quelle, DSP-Byteoffset, count16)` → 0xC0014284 →
  0xC0014C34 → 0xC00146B4. Kommando 0xAB, sonst gleicher
  sieben-Wort-Kopf mit Breite 2, Audio am Datenport.
- **Gemessen offline:** Originaler ARM-Schreibpfad mit 3, 16, 17, 32 und
  33 Wörtern: PCM exakt und umliegende Bytes unverändert im simulierten
  DSP. Unter 16 Wörtern Read/Modify/Write eines 16-Wort-Blocks. Größere
  Restblöcke verwenden überlappende 16-Wort-Transfers: bei 17 Wörtern
  zwei Transfers à 16 ab Offset und Offset+2 Byte.
- **Vermutet/offen:** Portmodell beweist weder echtes DSP-Timing noch die
  Sicherheit paralleler Aufnahme/Wiedergabe. Kein generischer Direktzugriff.

## Cache, Hook und Codeausführung

- **Gemessen offline:** Normaler SysEx-Parser 0xC0026B00 verzweigt zum
  Hook 0xC0170540. Execute 0x57 springt über 0xC017074C an eine
  übermittelte Adresse, ohne passende Import-/DSP-Argumente einzurichten.
  Bootloader 0x58 ist ein anderer, hier nicht freigegebener Pfad.
- **Gemessen offline:** CP15-/Cache-Code im Hauptprogramm und eingebetteten
  Loader gefunden. Fehlende direkte Aufrufer einiger Kernel-Initfunktionen
  beweisen keinen deaktivierten Cache im realen Betrieb.
- **Vermutet/offen:** Loaderzustand, indirekte Startpfade, tatsächliche
  Cache-Kohärenz nach USB-Upload und sichere Task-/IRQ-Bedingungen für
  RAM-Helfer nicht nachgewiesen. Kein cache-sicherer Bootstrap freigegeben.

[Speicherkarte und Schutzvorschläge](../speicherbereiche.md).
Keine Firmwarebytes, Emulator-Fixtures oder Audiodaten im Repository.
