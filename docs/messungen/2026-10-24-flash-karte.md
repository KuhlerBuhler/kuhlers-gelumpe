# Flash-Karte aus dem Code (24.10.)

Stand 2026-10-24. Sampler 2.02 mit Hacktribe (`hacktribe-original.VSB`), dazu der eigene Dump vom 9.10.
([Ganzer Flash](2026-10-09-flash-dump.md)). Kein Gerätezugriff. Ziel: die Karte des 16-MiB-Flash auf den Code
stützen, nicht nur darauf, wie der Dump aussieht. Ein Bereich aus `FF` im Dump beweist nicht, dass ihn niemand
beschreibt. Disassemblierung und Skripte liegen außerhalb des Repositories.

Statuswörter: **gelesen** = im disassemblierten Abbild verfolgt, **gemessen** = im Dump oder Emulator gezählt,
**hergeleitet** = aus gelesenem Code geschlossen, nicht ausgeführt, **offen** = nicht geklärt.

## Der Weg zum Chip

Drei Schichten, alles andere geht durch sie hindurch:

1. **Treiber** `src/SerialFlash/SerialFlash.cpp` (Name aus dem Assert-String), SPI1 `0x01F0E000`, Chip-Select GPIO 2.14
   (wie im Emulator). Funktionen: Lesen `0xC001E4AC` (Befehl `0x03`), Sektor schreiben `0xC001E57C`, Seite programmieren
   `0xC001E6B0` (`0x02`, 256 Byte), Sektor löschen `0xC001E7BC` (`0x20`, 4 KiB), Status `0xC001E9CC` (`0x05`), Schreiben an
   `0xC001EA70` (`0x06`), Schreiben aus `0xC001EAF4` (`0x04`), Adresse senden `0xC001E894`.
2. **Flash-Objekt** (Singleton, Zeiger bei `0xC034028C`, Getter `0xC0029A40`): `read(obj, ziel, adresse, länge)`
   `0xC0029A74`, `write(obj, adresse, länge, quelle)` `0xC0029AB8`, beide unter der Sperre `0xC0000D80(2)`.
   `write` macht für Anfang und Ende Lesen, Ändern, Schreiben über einen 4-KiB-Puffer bei `0xC033F28C`, volle Sektoren dazwischen
   direkt. `region(id)` `0xC0029C14` gibt `id << 16` (64-KiB-Einheiten). `writeVerify(id, länge, quelle)` `0xC0029CBC`
   schreibt und vergleicht danach in 64-KiB-Stücken.
3. **Bereichsfunktionen** `0xC0029D78` bis `0xC002A244`, je eine pro Bereich (Tabelle unten).

| Aussage | Status | Beleg |
|---|---|---|
| Die Firmware sendet an den Flash nur die Befehle `0x03`, `0x02`, `0x20`, `0x05`, `0x06`, `0x04`. Kein `0x9F` (ID), kein `0x52`/`0xD8` (32/64-KiB-Block), kein Chip-Erase | gelesen | alle Aufrufe der SPI-Sendefunktionen `0xC0018A2C`/`0xC00186D4` mit ihrem Befehlsbyte aufgelistet |
| Löschblock, wie die Firmware ihn nutzt: 4 KiB. Jedes Schreiben löscht den ganzen 4-KiB-Sektor und programmiert ihn in 16 Seiten zu 256 Byte neu | gelesen | `0xC001E57C`: Sektor löschen, dann 16 × `0xC001E6B0` |
| Logische Größe 16 MiB: Treiber prüft Adresse `< 0x1000000`, Sektor `< 0x1000`, Seite `< 0x10000` (sonst Assert) | gelesen | `0xC001E4CC`, `0xC001E5A8`, `0xC001E6D8` |
| Physische Größe und Chiptyp | offen | Die Firmware liest keine ID. Die ID im Emulator (`01 20 18`) ist dessen eigener Wert |
| Ein Schreiben von wenigen Byte (Kalibrierung, Panel-ID) löscht nur den 4-KiB-Sektor, in dem es liegt; Nachbarsektoren bleiben | gelesen | `0xC0029AB8`, Teilsektor über Puffer `0xC033F28C` |
| Keine Funktionszeiger auf Treiber, Flash-Objekt oder Bereichsfunktionen; alle Aufrufe sind direkte `bl` | gelesen | Suche aller 32-Bit-Werte im Abbild nach diesen Adressen: nur der Singleton-Zeiger |
| Außerhalb der Bereichsfunktionen rufen nur zwei Stellen `read`/`write` direkt: Hacktribes Haken `0xC0170710` (SysEx `0x55`, lesen) und `0xC017073C` (SysEx `0x56`, schreiben) | gelesen | Aufrufer von `0xC0029A74`/`0xC0029AB8` |

## Karte

Intervalle halb offen. "Schreiber" heißt: ein Codepfad, der dort Flash löscht oder programmiert.

| Bereich | Größe | Inhalt / Eigner | Liest | Schreibt | Im Dump | Status |
|---|---|---|---|---|---|---|
| `[0x000000, 0x020000)` | 128 KiB | Bootloader (AIS), Region-ID 0 | Boot-ROM; Firmware nicht | `BOOT.VSB`-Update `0xC002F5A8` → `writeVerify(0)`, Länge aus der Datei, höchstens `0x20000` (`0xC0029C1C`) | Daten bis `0x5E74`, dann `FF`, 2 Byte bei `0x1FFFE` | gelesen; Bedeutung der 2 Byte offen |
| `[0x020000, 0x220000)` | 2 MiB | Firmware-Abbild (SYSTEM.VSB-Nutzlast) | Bootloader; Firmware liest die letzten 16 Byte `0x21FFF0` als Version (`0xC0029DEC`, Infoseite und Update-Abfrage) | `SYSTEM.VSB` `0xC003A8A0`/`0xC003AC74` → `writeVerify(2)`, höchstens `0x200000` (`0xC0029C44`) | Daten mit `FF`-Lücken, die zum Abbild gehören | gelesen |
| `[0x220000, 0x220010)` | 16 B | Kennung `KORG` + `ele2sUSR`/`elec2USR` | Start `0xC00288EC` → `0xC0029D78`; Infoseite `0xC0029EDC` | nur `USER.VSB` | Daten | gelesen, Startlesen gemessen (Emulator) |
| `[0x230000, 0x230100)` | 256 B | Nutzer-Globals (GLST) | Start `0xC004BE8C` → `0xC002A0F8` | WRITE/Ausschalten `0xC004C1B4` → `0xC002A128` (5 Aufrufer) | Daten | gelesen, Startlesen gemessen |
| `[0x240000, 0x628000)` | 4000 KiB | 250 Nutzer-Patterns à `0x4000` | Start `0xC004BF8C` → `0xC002A090` (ein Lesen über alles) | `0xC004C28C`/`0xC004C2E4` → `0xC002A0C4` (Pattern schreiben, Werkspattern laden) | voll | gelesen, Startlesen gemessen |
| `[0x630000, 0x630100)` | 256 B | Werks-Globals | `0xC0031128` → `0xC002A158` (Werkszustand) | nur `USER.VSB` | Daten | gelesen |
| `[0x640000, 0x660017)` | 128 KiB | Werks-Patterns (SQEZ) | `0xC0030FFC` → `0xC002A188` | nur `USER.VSB` | Daten | gelesen |
| `[0x6B0000, 0x750000)` | 640 KiB | Sample-Info-Sicherung (gleiche Größe wie der SIST/SIED-Cache im RAM) | `0xC004C0E0` → `0xC002A1E8`, Länge `0xA0000`; Aufrufer Start `0xC002AB7C`, Sample-Import `0xC0038D80`, Werkszustand `0xC0031234` | `0xC004C3D4` → `0xC002A218`; Aufrufer `0xC004FB6C` (nach Import/Löschen von Samples), `0xC004FDB8` (Werkszustand) | voll | gelesen; im Startlauf des Emulators nicht gelesen |
| `[0x750000, 0x7E0000)` | 576 KiB | SLICE-Daten der Werks-Samples, Region `0x75` bis `0x7E` | `0xC004F494` → `0xC002A1B8`; Infoseite liest 2 Byte bei `0x7C0000` (`0xC0029E98`) | `SLICE.VSB` `0xC003A388` → `writeVerify(0x75)`, höchstens `0x90000` (`0xC0029C94`) | `00` und Daten, 2 Byte bei `0x7C0000`, 2 Byte bei `0x7DFFFE`, sonst `FF` | gelesen; Bedeutung von `0x7DFFFE` offen |
| `[0x7EF000, 0x7EF008)` | 8 B in einem 4-KiB-Sektor | Panel-Kennung (64 Bit vom Bedienteil) | `0xC003B1E8` → `0xC0029F90`, Länge `< 0x1000` | `0xC003B1E8` → `0xC0029FD0`, nur wenn der gelesene Wert 0 oder alle Bits 1 ist | Daten | gelesen, Startlesen gemessen |
| `[0x7FF000, 0x7FF008)` | 8 B in einem 4-KiB-Sektor | Touchpad-Kalibrierung | Start `0xC002A248` → `0xC002A010` | `0xC002A2F0` → `0xC002A050` (Kalibriermenü, `0xC006D9B8`, `0xC0074218`) | Daten | gelesen, Startlesen gemessen |
| `[0x800000, 0x1000000)` | 8 MiB | Werks-Samplebank `KORGelec2PCM` | Kopf 64 Byte `0xC0029E20`; PCM `0xC0029F54` (Basis + Offset), Aufrufer `0xC004D1E4`, `0xC004D860`, Selbsttest `0xC0076060` | `PCM.VSB` `0xC003845C` → `writeVerify(0x80)`, Länge aus der Datei, höchstens `0x800000` | Daten bis `0xE5F013`, dann `FF` | gelesen |

Startlesen im Emulator (Hacktribe 2.02, eigener Dump, Karte mit 20 und mit 0 Samples, bis 10 s, Hauptbild erreicht):
`0x220000`+16, `0x7FF000`+8, `0x230000`+256, `0x240000`+`0x3E8000`, `0x7EF000`+8. Kein Löschen, kein Programmieren,
kein Lesen von `0x6B0000`, `0x750000` oder `0x800000` in diesem Lauf. **gemessen** (Skript `trace_card.py` im Scratch,
Haken auf `Machine._flash_read` und `Flash.erase`).

## Was kein Code der Firmware berührt

Bereiche, die außerhalb jeder Bereichsfunktion liegen und auch in keinem Update-Bereich:

| Bereich | Größe | Status | Anmerkung |
|---|---|---|---|
| `[0x7E0000, 0x7EF000)` | 60 KiB | hergeleitet (kein Schreiber, kein Leser im Abbild) | 15 Sektoren. Hier legt der MFX-2-Patch seinen Satz ab (`0x7E8000`, `tools/patch/mfx_switch.py`) |
| `[0x7F0000, 0x7FF000)` | 60 KiB | hergeleitet | Hier lag der erste Startbild-Editor (`0x7F0000`), seit 15.10. auf der Karte |

Bereiche, die im Dump `FF` sind, aber in einem Update-Bereich liegen, sind **nicht** frei:

| Bereich | Größe | Wer überschreibt | Status |
|---|---|---|---|
| `[0x221000, 0x230000)`, `[0x231000, 0x240000)`, `[0x628000, 0x630000)`, `[0x631000, 0x640000)`, `[0x660017, 0x6B0000)` | zusammen rund 530 KiB | `USER.VSB` (`0xC003B2CC`) schreibt ab `0x220000` bis zu `0x490000` Byte, also bis `0x6B0000`, und lädt danach die Globals neu | gelesen |
| `[0x6000, 0x20000)` | 104 KiB | `BOOT.VSB` | gelesen |
| `FF`-Lücken in `[0x750000, 0x7E0000)` | rund 140 KiB | `SLICE.VSB` | gelesen |
| `[0xE5F013, 0x1000000)` | 1,6 MiB | `PCM.VSB`, sobald eine Datei länger als `0x65F013` ist | gelesen; Größe der Korg-Datei offen |

Sonderfall Hacktribe: SysEx `0x53` setzt Adresse und Länge, `0x56` ruft `Flash::write(0xC06C1AD0, adresse, länge, 0xC1000000)`.
`0xC06C1AD0` ist im Emulator nach dem Start genau der Singleton (`*0xC034028C`), der Weg schreibt also wirklich.
Er schreibt jeden Bereich, den Adresse und Länge treffen. Im BLECH-Satz `SYSTEM-hacktribe.VSB` sind Sprungtabelle und Aufruf
bytegleich. Der Editor kennt `0x56` nicht und sperrt unbekannte Befehle (`unknown-command`).

| Aussage | Status | Beleg |
|---|---|---|
| Sprungtabelle `0xC0170638` für die Befehle `0x51` bis `0x58`, Eintrag `0x56` → `0xC0170724`/`0xC0170728` → `bl 0xC0029AB8` | gelesen | Disassemblierung `0xC0170624` bis `0xC01707E0` |
| Singleton-Zeiger nach dem Start `0xC06C1AD0` | gemessen (Emulator, 1 s) | Wort bei `0xC034028C` |
| BLECH-Satz enthält denselben Code | gemessen (Bytevergleich) | `SYSTEM-hacktribe.VSB` und `hacktribe-original.VSB` bei `0x170624` bis `0x170740` gleich |
| `0x56` am Gerät oder im Emulator ausgeführt | offen | nicht versucht |

## Könnte freier Platz eigene Daten tragen?

Nur als Information, kein Plan: Projektregel ist, Flash-Schreiben klein zu halten, Einstellungen gehören auf die Karte.

- **Platz:** sicher frei nach dem Code sind nur die beiden 60-KiB-Blöcke `[0x7E0000, 0x7EF000)` und `[0x7F0000, 0x7FF000)`,
  zusammen 120 KiB in 30 Sektoren. Eine zweite Patternbank (250 × 16 KiB = 4000 KiB) passt nicht. Ein paar Presets oder
  ein Satz Einstellungen schon. Der 1,6-MiB-Schwanz hinter der Werksbank wäre groß genug für wenige Patterns, verschwindet
  aber bei einem längeren `PCM.VSB`. **hergeleitet**
- **Risiko Löschen:** Jedes Schreiben löscht 4 KiB. Ein Stromausfall zwischen Löschen und letzter Seite hinterlässt einen
  halb leeren Sektor. Im eigenen Block trifft das nur die eigenen Daten; in einem Sektor mit Kalibrierung oder Panel-ID
  (`0x7EF000`, `0x7FF000`) würde es diese treffen. Eigene Daten also nie in diese beiden Sektoren. **hergeleitet**
- **Risiko Updates:** `USER.VSB`, `SLICE.VSB`, `PCM.VSB`, `BOOT.VSB` und `SYSTEM.VSB` schreiben ganze Bereiche. Die beiden
  freien Blöcke liegen in keinem davon. **gelesen**
- **Risiko Sperre:** Schreiben hält die Sperre `0xC0000D80(2)` über das Löschen (bis 4 000 000 Statusabfragen) und gehört in
  die CommandTask, nicht in Takt oder Interrupt ([Skript-Laufzeit](../hintergrund/skript-laufzeit.md)). **gelesen**
- **Risiko Abnutzung:** typische NOR-Sektoren halten rund 100 000 Löschzyklen. Für den Chip hier nicht nachgelesen. **offen**

## Offen

- Chiptyp und physische Größe (keine ID-Abfrage im Code; Antwort ab `0x1000000` war ein Hänger).
- Bedeutung der 2 Byte bei `0x1FFFE` und `0x7DFFFE`.
- Ob der Bootloader selbst außer `[0x20000, 0x220000)` etwas liest oder schreibt (nur die Firmware ist verfolgt).
- Ob DSP oder DMA den Flash an der Firmware vorbei lesen. SPI1 wird auch für den DSP-Upload benutzt (zwei Getter
  `0xC0016684`/`0xC00166B4` geben `0x01F0E000`; DSP über SPI1 laut Emulator-Kommentar in `machine.py`), ein eigener Flash-Zugriff dort ist nicht gesehen.
