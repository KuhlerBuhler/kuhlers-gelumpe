# Startinitialisierung, Interrupt-/Loader-Stacks und Patternbank

Stand: 8. Oktober 2026. **Gemessen offline** an den originalen ARM-Routinen
im vorhandenen RAM-Dump, SHA256
`c114f10457b1dabc3ad6f8694aa3af9be63c5429da627c6358490ce781e0f26a`.
Keine Gerätebefehle. Intervalle sind halb offen.

## Initialisierter Systembereich

**Gemessen offline:** 0xC00296B0 löscht wortweise
`[0xC0200000, 0xC08A2940)`, 6.957.376 Byte. Anschließend werden die zehn
Task-Stacks aus ihren Deskriptoren mit unterschiedlichen Prüfmustern
gefüllt. Die Ausführung wurde bei 0xC002984C vor den Hardware-Initialisierern
angehalten. Der gesamte Bereich nach den Task-Stacks bis zur oberen Grenze
ist null; alle zehn Stackfüllungen passen vollständig zu ihren Deskriptoren.
Sentinels vor und hinter dem Löschbereich bleiben erhalten.

**Schutzvorschlag:** Das gesamte Intervall gehört zur Systeminitialisierung
und bleibt gegen generische Writes gesperrt. Darin liegen die zuvor
zugeordneten Task-Stacks, Runtime-Strukturen, Sample-Tabellen und der Heap.
Gezielte Parameterausnahmen benötigen weiterhin ihre eigenen Feldprüfungen.
Der Löschbereich ist kein Beleg für ausführbaren Code oder freie Bytes.

## Interrupt-/Idle-Stack und Start-SP

**Gemessen offline:** Die Startfunktion füllt
`[0xC274AA40, 0xC274EA3C)` mit einem Prüfmuster, 16.380 Byte.
Interrupt-Einstieg 0xC0001560 sichert zunächst den Kontext auf dem bisherigen
SVC-Stack und schaltet beim ersten Interrupt bei 0xC00015A8 auf
0xC274EA3C um. Der vorherige Kontextzeiger wird dort abgelegt.
Der Scheduler verwendet denselben oberen Stackzeiger bei 0xC00017F4 im
Idle-Pfad.

**Gemessen offline:** Zwei ausgeführte IRQ-Einstiegstests mit Tiefe 0 und 1:
Der äußere Einstieg wechselt auf 0xC274EA38 und sichert den bisherigen
Zeiger; der verschachtelte Einstieg bleibt auf dem aktuellen Stack.
Beide erhöhen den Zähler bei 0xC06A2894. Ausführung endet vor dem ersten
Interruptcontroller-Zugriff bei 0xC00015B0; kein IRQ-Handler wurde ausgeführt.

**Gemessen offline:** Der Resetpfad 0xC0000070 setzt SP auf 0xC274AA40.
Seine Startaufrufe wachsen damit unterhalb des Interrupt-Stackbereichs.
**Schutzvorschlag:** Auch das unmittelbar davor liegende 64-KiB-Intervall
`[0xC273AA40, 0xC274AA40)` sperren. Dies ist eine konservative Reservierung
zwischen Datei-Arbeitspuffer und Start-SP, keine gemessene maximale Stacktiefe.

## Hochgeladener Loader

**Gemessen offline:** Der bestehende Loader-Pfad bei 0xC01705DC kopiert
0xD70 Byte von 0xC017127C nach 0xFFFF0000. Die originale Kopierroutine
wurde ausgeführt; sämtliche Zielbytes stimmen überein, das Wort dahinter
bleibt unverändert. Vor dem Sprung zum Loader wurde angehalten.

**Gemessen offline:** Der Initialisierungsteil ab 0xC0171280 löscht
`[0xFFFF0D70, 0xFFFF1158)` und füllt
`[0xFFFF115C, 0xFFFF125C)` mit einem Stackprüfmuster.
Er richtet die folgenden bankierten Stackzeiger ein:

| CPU-Modus | Anfangs-SP |
|---|---|
| Undefined (0x1B) | `0xFFFF1258` |
| Abort (0x17) | `0xFFFF1250` |
| FIQ (0x11) | `0xFFFF1248` |
| IRQ (0x12) | `0xFFFF1240` |
| Supervisor (0x13) | `0xFFFF1200` |
| System (0x1F) | `0xFFFF11C0` |

Alle sechs Zuweisungen und sämtliche Füllbytes wurden in Unicorn geprüft.
Der Test überspringt die vorgeschaltete Peripherieinitialisierung und endet
vor dem Loader-Hauptprogramm. **Schutzvorschlag:** Den vollständigen Bereich
`[0xFFFF0000, 0xFFFF125C)` sperren, einschließlich des Zwischenwortes.
Die SP-Abstände sind keine garantierten maximalen Stackgrößen.

## RAM-Patternbank und Globals

**Gemessen offline:** 0xC0047180 liefert 0xC08A2940. Dort steht im Dump
GLST; Initialisierung 0xC004BE90 behandelt die ersten 0x100 Byte als Globals
und füllt weitere 0xFF00 Byte ab +0x100 mit 0xFF. Damit ist der zugehörige
Initialisierungsbereich `[0xC08A2940, 0xC08B2940)`.
Die Globals-Initialisierung ist hier durch Disassemblierung und Kennung,
nicht durch vollständige Ausführung ihrer Dateizugriffe belegt.

**Gemessen offline:** Pattern-Adressroutine 0xC004A350 akzeptiert die
nullbasierten Indizes 0 bis 249 und liefert
`0xC08A2940 + (index + 4) * 0x4000`.
Damit liegt die Bank in `[0xC08B2940, 0xC0C9A940)`;
250 Slots à 0x4000 Byte, darin jeweils ein 0x3C00-Byte-Pattern.
Alle 250 Aufrufe wurden ausgeführt. Jeder Eintrag hat im Dump passende
Start-/Endkennungen PTST/PTED. Index 250 und 0xFFFFFFFF liefern null.
Slotabstand ist nicht gleich editierbarer Recordlänge; Restbytes bleiben gesperrt.

**Schutzvorschlag:** Patternbank und Globals sind Nutzerdaten, aber keine
Freigabe für beliebige RAM-Writes. Änderungen benötigen konsistente
Patternfelder und einen geprüften Transport. System- und Stackbereiche
werden unabhängig davon gesperrt.

## Sample-Info-Cache zwischen Patternbank und Dateipuffer

**Gemessen offline:** 0xC004AEB8 liefert 0xC0C9A940.
Die Lese-/Schreibpfade bei 0xC004C0E0 und 0xC004C3D4 übergeben jeweils
0xA0000 Byte. Der Cache reicht damit genau bis 0xC0D3A940, der bereits
nachgewiesenen Dateipufferbasis. Kennungen: SIST am Anfang, SIED bei
+0x9FFFC. Dies sind Metadaten, kein Sample-Audio.

**Gemessen offline:** Die originale Routine 0xC004F340 wurde für beide
Richtungen ausgeführt: ohne gültige Endkennung baut sie den Cache aus den
RAM-Tabellen auf; mit gültiger Endkennung stellt sie diese wieder her.
Alle sechs Teilbereiche wurden vollständig bytegenau verglichen, inklusive
Wiederherstellung nach künstlicher Veränderung der Tabellen. Sentinels vor
und hinter dem Cache bleiben erhalten. Heap-Locks waren für den isolierten
Test deaktiviert; keine Dateizugriffe oder Hardware-Kommandos ausgeführt.

| Cacheoffset | RAM-Quelle/Ziel | Byte |
|---|---|---:|
| `0x10` | `0xC047B08C` | 16.000 |
| `0x3E90` | `0xC035F06C` | 8.000 |
| `0x5DD0` | `0xC0350644` | 4.000 |
| `0x6D70` | `0xC0362EE8` | 8.000 |
| `0x8CB0` | `0xC035738C` | 16.000 |
| `0xCB30` | `0xC036AD88` | 558.000 |

Die letzte Kopie umfasst 500 Metadatenrecords à 1.116 Byte, die
Playback-Kopie 500 Records à 16 Byte. Diese konkrete Cacheoperation
ist kein Beleg für eine Gesamtzahl aller verfügbaren Sample-Slots.
**Schutzvorschlag:** Das gesamte Intervall
`[0xC0C9A940, 0xC0D3A940)` gegen generische Writes sperren; veränderte
Cachebytes können später mehrere Live-Tabellen überschreiben.

[Speicherkarte](../speicherbereiche.md),
[Task-Stacks, Heap und Arbeitspuffer](2026-10-08-systemspeicher-offline.md).
Emulator-Skripte, Fixtures und Binärdaten bleiben außerhalb des Repositories.

## Firmwarebereich im vorhandenen Flash-Dump

**Gemessen offline:** Das 2-MiB-VSB-Nutzabbild (Dateikopf 0x100 Byte)
liegt im Flash bei `[0x020000, 0x220000)`.
Vollständiger Vergleich aller 2.097.152 Byte mit dem bereits veränderten
Simulationsabbild: 2.095.177 Byte stimmen überein; sämtliche 1.975
abweichenden Bytes liegen ausschließlich in den bekannten FX-Tabellen
oder Menü-Instruktionswörtern. Kein bytegleicher Gesamtstand wird behauptet.
SHA256 des Flash-Nutzabbilds:
`b6e657130a67877ff5b5520b52c732db52dd87cff5f9174a73278384c0008ce5`.

**Gemessen offline:** Das vorgeschaltete AIS-Image beginnt bei Flash 0
mit TIPA. Ab 0x1C wurden drei Section-Load-Kommandos mit Längen 0x3C,
0x55A4 und 0x84C vollständig geparst. Es endet nach Jump_Close bei
0x5E74, Einsprung 0x80000000. Die Opcode-Bedeutung entspricht der
[TI-AIS-Dokumentation](https://www.ti.com/jp/lit/pdf/spraaw2).

**Schutzvorschlag:** Den gesamten Flash-Umschlag `[0x000000, 0x220000)`
gegen Schreibzugriffe sperren: Startimage, Hauptabbild und dazwischenliegendes
Padding. Das ersetzt die unpräzise alte Markierung „Code-Ende 0x1D0000“
für die Schutzgrenze. Der Umschlag enthält auch Daten und ungenutzte Bytes;
es handelt sich nicht um 0x220000 Byte reinen Maschinencode.
