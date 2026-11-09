# Firmwarepfad fuer Part-Parameter

Stand 2026-11-06. Im Emulator mit eigener Hacktribe-`SYSTEM.VSB` und Firmware 2.02 geprueft, ohne Flash-Abbild. Der Emulator bildet den DSP nicht ab. Eine Geraeteprobe bestaetigte am 2026-11-06 die sofortige Klangaktualisierung ueber den Firmwarepfad.

## Parameterpfad

**Offline, aus der Firmware gelesen.** Die Reglerbehandlung ruft fuer einen Part zuerst `0xC0048460` mit Part, feldspezifischem Aktualisierungscode und Wert auf. Danach ruft sie `0xC0059720` mit Part plus eins, Setter-ID, Reglerwert und Flag `1` auf. CUTOFF folgt demselben Aktualisierungspfad, den sein Encoder-Handler intern verwendet. Der Part wird dabei explizit uebergeben; die Auswahl des Parts am Geraet muss sich nicht aendern.

| Feld | Aktualisierungscode fuer `0xC0048460` | Setter-ID fuer `0xC0059720` | Wert fuer den Setter |
|---|---:|---:|---|
| `cutoff` | `0x0B` | `5` | Part-Wert |
| `resonance` | `0x0C` | `6` | Part-Wert |
| `egInt` | `0x0D` | `7` | Part-Wert plus `64` |
| `modSpeed` | `0x0F` | `9` | Part-Wert |
| `modDepth` | `0x10` | `8` | Part-Wert |
| `attack` | `0x11` | `12` | Part-Wert |
| `decay` | `0x12` | `13` | Part-Wert |
| `level` | `0x13` | `10` | Part-Wert |
| `pan` | `0x14` | `11` | Part-Wert plus `64` |
| `ifxEdit` | `0x1B` | `14` | Part-Wert |
| `pitch` | `0x1C` | `2` | Part-Wert plus `64` |
| `glide` | `0x1D` | `3` | Part-Wert |
| `oscEdit` | `0x06` | `4` | Part-Wert |

Die Codes stammen aus der Zuordnung der physischen Regler in der Firmware. Die Werte fuer PAN, EG INT und OSC PITCH werden fuer den Reglerpfad auf den Bereich `0` bis `127` verschoben. Die getrennte Typ-12-Benachrichtigung wird von den Part-Zuweisungen nicht verwendet. Physische Regler stellen sie mit Parameter-ID und Wert in die UiTask-Queue; sie koennte nuetzlich sein, wenn die Parameteranzeige oder ein anderer UI-Zustand aktualisiert werden soll. Sie enthaelt keine Part-Nummer und ist kein bestaetigter DSP-Refresh.

## Emulatorprobe

Fuer jedes der dreizehn Felder wurde Part 3 im Emulator ueber das Paar `0xC0048460` und `0xC0059720` aktualisiert. Hauptbyte und Mirror enthielten danach denselben gewuenschten Wert. Part 0 blieb unveraendert, der ausgewaehlte Part blieb 0, und es trat keine Assertion auf.

Diese Probe bestaetigt die Argumente, den Ziel-Part und die geschriebenen RAM-Werte in der Hacktribe-Firmware. Am Geraet wurde bestaetigt, dass die Zuweisung ueber den Firmwarepfad den Klang sofort aktualisiert. Ein Schreiben in den Pattern-RAM allein reicht dafuer nicht. Fuer Synth sind die entsprechenden Firmware-Adressen nicht zugeordnet.

## Setter isoliert

**Offline im Emulator, 2026-11-07.** `0xC0059720` wurde aus einem sicheren UiTask-Tick direkt auf Part 1 aufgerufen, ohne vorher `0xC0048460` aufzurufen: Setter-ID `5` (CUTOFF) mit Wert `64` und Setter-ID `6` (RESONANCE) mit Wert `40`, jeweils Flag `1`. Beide Aufrufe liessen den Pattern-RAM unveraendert und loesten keine Assertion aus. Neben zwei auch im Leerlauf auftretenden 16-Wort-Transfers an `0xFF900A34` erschien jeweils ein zusaetzlicher `0xAB`-Schreibtransfer mit 16 Woertern und neuer Payload.

Das ist ein Hinweis, dass `0xC0059720` selbst einen Parameterwert an den DSP-Host-Port uebertraegt und nicht nur einen Pattern-Byte-Mirror aktualisiert. Isoliert geprueft wurden hier nur CUTOFF und RESONANCE. Fuer die uebrigen elf Setter-IDs ist bisher der gemeinsame Pfad mit `0xC0048460` belegt; die Einzelwirkung jedes Setters und die Uebernahme durch den echten DSP sind offen.
