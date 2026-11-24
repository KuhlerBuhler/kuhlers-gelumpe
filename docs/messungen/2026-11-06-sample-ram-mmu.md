# Sample-RAM: CPU-Register und Speicherabbildung

Gemessen an der roten Electribe 2 Sampler, Korg 2.02 mit [Hacktribe](../glossary.md#hacktribe), mit einem minimalen Messbuild, das
ausschließlich [BLECH SysEx](../glossary.md#sysex) enthält (Diagnosecode läuft über EXEC). Eigene Testkarte mit erzeugten Samples. Es wird nichts in
den oberen RAM, den DSP, die Karte oder den Flash geschrieben und nichts an MMU, Cache oder Domänen geändert.

## Gemessen: CPU-Register

| Register | Wert |
|---|---|
| CPU-ID | `0x41069265` |
| Steuerregister c1 | `0x0005107D` |
| Translation Table Base c2 | `0x8001C000` |
| Domain Access Control c3 | `0x00000003` |
| FCSE c13 | `0x00000000` |
| Cache Type | `0x1D152152` |
| DTCM Region | `0x0000001C` |
| ITCM Region | `0x0000001C` |

MMU, Daten- und Befehlscache sind eingeschaltet. Die Domäne 0 hat Managerrechte. Aus den TCM-Rohwerten wird keine
Speicherfreigabe abgeleitet.

## Gemessen: die Seitentabelle

Die Diagnose beendet alle 150 Aufrufe bestätigt: CPU-Register vorher, zweimal 74 Teile der 16-KiB-Tabelle und CPU-Register
danach. Beide vollständigen Tabellen und beide Registersätze stimmen überein. Jeder Codeupload besteht den Vergleich über die
Spiegeladresse vor EXEC, es gibt keinen Timeout und keine Wiederholung. Der Arbeitsbereich im ersten KiB des EXEC-Fensters wird
nach den Abschnitten zurückgeschrieben und geprüft.

Die gelesenen Einträge ergeben für die 25 betroffenen Sections:

| Virtueller Bereich | Physisches Ziel | Attribute |
|---|---|---|
| `0xC274F000..0xC4000000` | identisch | Write-back, gepuffert, Domäne 0, Manager |
| `0xC674F000..0xC8000000` | Adresse minus `0x04000000` | ungecachet, ungepuffert, Domäne 0, Manager |

Der Tabelleneintrag für den SRAM passt zu `TTBR = 0x8001C000`. Der Spiegel zeigt auf dieselben physischen Ziele wie der obere
RAM-Bereich.

## Hergeleitet: das Modell des Bootloaders

Die Bootloader-Routine (Ausschnitt `0x5000..0x6000`, Tabellenroutine ab `0x51D8`, zweimal rein lesend erfasst, gleiche
Inhalte) ergibt außerhalb des Repos im Emulator ausgeführt dieses Tabellenmodell:

| Virtueller Bereich | Physisches Ziel | Cache-/Pufferattribute |
|---|---|---|
| `0xC0000000..0xC4000000` | identisch | Write-back, gepuffert |
| `0xC4000000..0xC8000000` | Adresse minus `0x04000000` | ungecachet, ungepuffert |
| `0x80000000..0x80100000` | identisch | Write-back, gepuffert |

Grenzangaben rechts sind exklusiv. Der Tabellenbeginn `0x8001C000` liegt im SRAM. Das Modell erklärt einen ungecacheten
Spiegel bei `0xC5000000`: ein Upload kann über die gecachte Sicht erfolgreich zurückgelesen werden, während der RAM noch andere
Bytes enthält. Darum schreibt BLECH SysEx RAM-Uploads mit einer begrenzten Cachepflege (Clean der 32-Byte-Zeilen im ersten KiB
des EXEC-Arbeitsbereichs, danach Schreibpuffer leeren) und prüft über den Spiegel.

Die Registerauslegung folgt dem [ARM926EJ-S Technical Reference Manual](https://documentation-service.arm.com/static/5e8e3d1088295d1e18d3a9b2),
Abschnitte zum System Control Coprocessor und zur MMU.

## Offen

- Das Bootloader-Modell bestätigt keine aktiven TLB-Einträge; die Tabellen gelten daher als Kandidaten. Im Emulator werden CP15-Werte
  und Spiegelung eingespeist, eine echte MMU oder ein echter Datencache wird nicht nachgebildet.
- Weder CPU- noch DMA-Besitz des oberen Bereichs sind vollständig geklärt; ein freier Swap-Cache ist damit nicht nachgewiesen.
  Eine Probe im oberen RAM muss beide Cache-Sichten berücksichtigen, damit schmutzige Cachezeilen weder Änderungen verdecken noch
  alte Inhalte zurückschreiben.
