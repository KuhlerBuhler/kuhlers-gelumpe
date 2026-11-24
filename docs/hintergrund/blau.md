# Die blaue Electribe

Was über die blaue Electribe 2 (Synth) bekannt ist und wie BLECH auf ihr läuft. Eine blaue Electribe gab es für keine
dieser Messungen: alles ist im [Emulator](../glossary.md#emulator) gemessen oder offline gelesen, am Gerät ist nichts
davon bestätigt. Die Messnotizen, aus denen Abschnitte stammen, sind in der Git-Geschichte lesbar
(`git show origin/develop:docs/<pfad>`).

Weiter: [Emulator, blaue Electribe 2](../emulator.md#die-blaue-electribe-2-synth),
[Die blaue Electribe 2 im Emulator](../messungen/2026-10-15-blaue-electribe.md),
[BLECHTRIBE mit Hacktribe auf der blauen](../messungen/2026-10-26-blech-hacktribe-blau.md),
[Rettung](../rettung.md), Gerätetest [Rote Electribe mit blauer Firmware](../geraetetests/offene-geraetetests.md#3-rote-electribe-mit-blauer-firmware).

## Was die blaue ist

- **Derselbe Code wie der Sampler, nur verschoben**, ohne Sample-Verwaltung. Korgs [`SYSTEM.VSB`](../glossary.md#vsb)
  2.02 der blauen hat die SHA-256 `41fc5f1c...`. Gemessen.
- **Kennung der Nutzerdaten** im Flash bei `0x220000`: die blaue `KORGelec2USR`, der Sampler `KORGele2sUSR`. Mit der
  Kennung des Samplers zeigt die blaue Firmware SOFTWARE UPDATE statt des Hauptbilds. Gemessen.
- **Updateordner** `KORG/electribe/System/`. Die Firmware fragt dort der Reihe nach `BOOT.VSB`, `USER.VSB`, `PCM.VSB`
  und `SYSTEM.VSB` ab. Was sie mit den ersten drei tut, ist nicht gemessen, deshalb liegt im Ordner nur die eine Datei.
  Gemessen (Haken auf `f_open`).

Quelle: Messung 2026-10-15/blaue-electribe

## Was SOFTWARE UPDATE auf der blauen schreibt

Im Emulator schreibt das Update der blauen genau den Firmwarebereich `[0x020000, 0x220000)`: 512 Löschbefehle zu 4 KiB
und 8192 Seiten zu 256 Byte. Nutzerbereich `[0x220000, 0x800000)` und PCM-Bank ab `0x800000` bleiben byteweise gleich,
hin wie zurück. Gemessen im Emulator.

**Offen am Gerät:** ob das echte Gerät beim Update ebenfalls nur diesen Bereich schreibt. Das gehört vor jeden
Gerätetest einer Firmware für die blaue.

Quelle: Messung 2026-10-15/blaue-electribe

## Welche Datei der Updater der blauen annimmt

Gelesen aus dem Code (`0xC003AD00` bis `0xC003AE5C`): der Updater prüft

- die 16 Byte Kennung `KORG SYSTEM FILE` am Anfang,
- einen Vergleich von 6 Byte ab `0x20` (welchen Text er erwartet, ist nicht nachgesehen),
- die Versionsbytes `0x2A` und `0x2B` gegen eine Tabelle je Typ,
- die Länge bei `0x3C` gegen die Flash-Größe.

Gemessen auf Korgs blauer Firmware mit der Hacktribe-Datei:

| Änderung an der Datei | Ergebnis |
|---|---|
| anderer Wert bei Byte `0x3C` | abgelehnt |
| ein Byte im freien Lauf der Nutzlast geändert | angenommen, über die Nutzlast gibt es keine Prüfsumme |
| 16 Byte mehr oder weniger | angenommen, darauf nicht verlassen |

Die Kopfbytes `0x12` und `0x2E`, die über Sampler oder Synth entscheiden, stehen in
[BLECHTRIBE mit Hacktribe auf der blauen](../messungen/2026-10-26-blech-hacktribe-blau.md) und in der
[Rettung](../rettung.md).

Quelle: Idee 65

## Entscheidungen zur blauen im Emulator und in der App

| Entscheidung | Grund |
|---|---|
| Der Build heißt `synth`, nicht `blue` | die Farbe ist ein Handelsname, der Unterschied ist, dass es der Synth ist |
| Eigener Flash `flash-synth.bin` für die blaue | die Nutzerdaten beider Geräte sind verschieden, ein gemeinsamer Flash würde bei jedem Wechsel der Firmware die Daten des anderen überschreiben |
| Kartenordner `electribe` | der Pfad steht im Abbild; für das Update ist der Ordner gemessen (oben), für andere Kartenzugriffe hergeleitet |
| Die Seite erkennt den Synth am Kopf der Datei, nicht am Code | die Seite braucht dann keinen Python-Dienst, um eine Datei zu beschriften; der Dienst prüft zusätzlich den Code, und nur er entscheidet, ob die Firmware startet |
| Bereich "Gerät" und Seitenleiste "Am Gerät" bleiben für den Synth leer | beide brauchen die SysEx-Befehle von Hacktribe |

Quelle: Messung 2026-10-15/blaue-electribe

## Eigene Insert- und Master-Effekte auf der blauen

Der Satz `blech-synth.json` bringt `preset-tables` und `fx-catalog` auf die blaue. Gemessen im Emulator:

- Menüs mit 48 Insert- und 40 Master-Effekten.
- `e2sFx.all` lädt beim Start. EXPORT ALL EFFECTS schreibt den RAM in die geladene Datei (die Texte bleiben), ohne
  Datei eine neue mit 160 Einträgen (48 Insert, 40 Master, 72 Modulation), die der nächste Start lädt. Eine nicht
  geladene oder geänderte Datei bleibt stehen.
- Jeder neue Platz schickt dem DSP dieselben Übertragungen wie auf der roten: Insert 39 bis 48 je 14, Master 33 bis 40
  je 11 (`tools/emu/blue_red_dsp.py`).
- Mit EXIT beim Einschalten lädt die blaue nichts: ihr Startwrapper überspringt BLECH ganz.
- VERSION zeigt `KORG BLUE FX`, `FX fw?` oder `FX bad`.
- Der Startwrapper der blauen (`tools/patch/script_start_synth.s`) ruft den Lader `fx_card_load` an derselben Stelle wie
  auf der roten auf, hinter `script_card_load`.

Adressen, rot gegen blau. Gefunden mit `fwmap.py`, an jeder Stelle steht in der blauen dasselbe Befehlswort wie in der
roten (gemessen, Wort für Wort gelesen). Alle stehen mit Beleg im Feld `why` in `data/synth-map/preset-tables.json`.

| Sampler (rot) | blau | was |
|---|---|---|
| `0xC00981B4` | `0xC00857AC` | fünftes Literal des Reglergedächtnisses |
| `0xC0098084` | `0xC008567C` | Zeilenlänge des Insert-Menüs |
| `0xC009809C`, `0xC00980E8`, `0xC00980EC`, `0xC009811C`, `0xC0098138`, `0xC009814C`, `0xC0098150`, `0xC0098188`, `0xC0098194` | `0xC0085694`, `0xC00856E0`, `0xC00856E4`, `0xC0085714`, `0xC0085730`, `0xC0085744`, `0xC0085748`, `0xC0085780`, `0xC008578C` | Stellen der Insert-Menülänge (38 und 37) |
| `0xC0048F80`, `0xC0049EF0`, `0xC004A1F8` | `0xC0043140`, `0xC004400C`, `0xC00442F8` | Stellen der Insert-Menülänge außerhalb des Menüs |
| `0xC00D81EC` | `0xC00C1E64` | Modulationstabelle, 72 Records zu `0x58` (`FX_MODS`) |

Adressen der blauen selbst: Insert-Feld `0xC009898C`, Master-Feld `0xC0099D88` (`data/map/firmware.mjs`, Build
`synth`), Reglergedächtnis `0xC056C3A0` (`tools/patch/preset_tables.py`). Die Flächen des Patches (`0xC0174000` bis
`0xC017CC00`) sind in der blauen frei wie in der roten.

**Offen:** Live-Bearbeitung der Effekte über SysEx auf der blauen (`stockReady` verlangt den Build `stock`), der Klang
am Gerät.

Quelle: Messung 2026-11-08/blau-effekte-port

## Die rote als blaue

Die rote Electribe kann Korgs blaue 2.02 laufen lassen, wenn das Wort an `0xC0027114` (Datei `0x27214`) auf
`0x059F000C` steht und die Datei den Sampler-Kopf trägt (`0x12 = 0x53`, `0x2E = 0x24`). Gemessen im Emulator mit
`tools/emu/red_as_blue_probe.py`. Die Datei wird nie weitergegeben, sie enthält Korgs Firmware. Ohne das Wort zeigt die
blaue beim Start "SOFTWARE UPDATE / press ENTER"; auf dem Rückweg nimmt sie nur eine Datei mit blauem Kopf und lehnt eine
andere vor dem ersten Schreibbefehl mit "Error / Invalid File" ab. Die Schritte am Gerät stehen in
[Offene Gerätetests](../geraetetests/offene-geraetetests.md#3-rote-electribe-mit-blauer-firmware).

Quelle: Messung 2026-11-08/rot-als-blau
