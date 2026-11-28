# Updatepfad der laufenden BLECH-Firmware: KORG/blechtribe/System/SYSTEM.VSB

Gemessen an einer roten Electribe 2 Sampler (Korg 2.02, Hacktribe), nur lesend über [SysEx](../glossary.md#sysex): kein EXEC, kein Schreiben
in Karte, [DSP](../glossary.md#dsp) oder Flash. Anlass war die Meldung `No file` beim Update von einer Testkarte, auf der die neue
`SYSTEM.VSB` ([VSB](../glossary.md#vsb)) nur unter `KORG/hacktribe/System/` lag, während schon BLECH lief.

## Gemessen

Eine lesende Geräteprüfung liefert:

| Bereich | Gelesener Text |
|---|---|
| `0xC00A5656` | `blechtribe` |
| `0xC00A5678` | `KORG/blechtribe/` |
| `0xC00A5690` | `System` |

Die Codebereiche `0xC00307B0` mit 212 Byte und `0xC0035720` mit 112 Byte stimmen mit dem eigenen Hacktribe-Original überein.

## Hergeleitet

Der native Updatepfad ruft den Basisordner-Helfer und den System-Helfer auf und ergänzt `/SYSTEM.VSB`. Aus diesem Code und den
gelesenen Pfadtexten folgt: eine Firmware, auf der BLECH mit dem umgestellten Ordner läuft, sucht ihr Update unter
`KORG/blechtribe/System/SYSTEM.VSB`, nicht mehr unter `KORG/hacktribe/System/` und nicht unter `KORG/electribe sampler/System/`.
Eine Firmware ohne BLECH sucht weiter ihren eigenen Ordner. Ein Update tauscht die Firmware und löscht keine Datei der Karte.

## Offen

Der erneute Updateversuch am Gerät mit der Datei am BLECH-Pfad. Die Kartenanleitung der App nennt den Pfad der Firmware, die gerade
läuft ([Patcher](../patcher.md)).
