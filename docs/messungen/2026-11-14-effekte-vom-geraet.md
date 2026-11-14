# Effekte und Modulationen vom Gerät lesen

Stand 14. November 2026. **Gemessen** an der roten Electribe 2 Sampler mit Hacktribe und BLECHTRIBE samt Kartenlader,
über `ssh linux`, nur mit BLECH READ (0x61). Kein WRITE, kein EXEC. Code: `src/device-fx.mjs` (`readDeviceFx`),
`src/presets.mjs` (`readPresetsLive`), Leser auf dem Linux-Rechner `~/gelumpe-probe/fx_read.py`. Tests:
`test/device-fx.test.mjs`, `test/e2e/fx-device.e2e.mjs`.

## Frage

Der Export von e2sFx.all im Baukasten brauchte bisher eine Firmware-Datei: Korgs Zip über die App oder eine Datei, die man
reinzieht. Die Namen in der Platzliste kamen aus der Firmware im Emulator. Kann die App stattdessen lesen, was das
verbundene Gerät gerade hat, also die Presets nach dem Kartenlader und die Menüs so lang, wie er sie gemacht hat?

## Was gelesen wird

Die App baut ein leeres Abbild der Firmware-Datei (0x200100 Bytes) und füllt nur die Stellen, die der Export braucht, aus dem
RAM. Datei-Offset = RAM - 0xC0000000 + 0x100, wie überall.

| Was | RAM | Länge |
|---|---|---|
| Hacktribe-Lauf, sagt den Build (`buildOf`) | 0xC0170000 | 0x40 |
| Getter von `presets.ifx` und `presets.mfx`: Literal auf das Zeigerfeld und `cmp r0,#n` | aus `POINTER_TABLES` | je 4 |
| Zeigerfelder und alle Preset-Einträge (0x20C je Eintrag), in zusammenhängenden Stücken | aus den Zeigern | |
| Menülängen: `menu.ifxCount`-Stellen, IFX_ROW (Datei 0x98184), mfx `where.offset` (Datei 0x3f0e4) | | je 1 bis 4 |
| Modulationstabelle, 72 × 0x58: Hacktribe `table.modType` / Korg `table.modTypeStock` | 0xC019FFFC / 0xC00D81EC | 0x18C0 |
| Status des Kartenladers (Status, Anzahl geladen) | 0xC01F7FE0 | 8 |

- **Offline:** Stehen die Getter nicht dort, wo sie gemessen sind, bricht das Lesen ab (`presets`). Passt der Build nicht zu
  dem, den die Sitzung beim Verbinden erkannt hat, auch (`build`).
- **Gemessen im Simulator:** Aus diesem Abbild baut `collectionFor` Byte für Byte dieselbe e2sFx.all wie aus der
  SYSTEM.VSB selbst, für Hacktribe und für Korgs Original (`test/device-fx.test.mjs`).

## Ergebnis am Gerät

| Wert | gemessen |
|---|---|
| Build | hacktribe |
| Insert-Effekte im Menü | 88 |
| Master-Effekte im Menü | 60 |
| Kartenlader | Status 2 (ok), 203 Einträge geladen |
| Modulationstabelle | `table.modType` |
| Lesevorgänge / Bytes | 26 / 112308 |
| Zeit am Gerät (Summe der READs) | 0,72 s |
| Zeit gesamt über ssh | 1,85 s |

- **Gemessen:** Die Namen kommen sauber raus, etwa Insert 1 Punch bis 88 Mix Clean Up, Master 1 Mod Delay bis 60 Master
  Warmth, Modulation 1 EG+ Filter bis 72 Random IFX. Die gewachsenen Menüs (Plätze über Hacktribes eigenen) liest die App mit.
- **Hergeleitet:** Plätze, die e2sFx.all beim Start gefüllt hat, tragen im RAM den Eintrag von der Karte. Die Liste zeigt dort
  den Namen von der Karte, und ein verschobenes Werks-Preset (`factory:N`) nimmt diesen Eintrag mit. Welche Plätze von der
  Karte kamen, sagt das RAM nicht, nur wie viele.

## e2sFx.all von der Karte

Kann die Firmware e2sFx.all über FILE READ lesen (Bits 30 und 29, siehe [e2sFx.all über USB lesen](2026-11-14-fx-datei-lesen.md)),
holt die App die Datei mit und legt ihre Einträge auf die Plätze, wie beim Reinziehen der Datei. Eine Firmware ohne Doom-Flag
fragt sie gar nicht erst, eine ältere, die außerhalb des Bereichs antwortet, wird übersprungen.

- **Gemessen im Simulator und im Browser-Test:** Datei da, Datei fehlt, alte Firmware.
- **Offen:** am Gerät, weil die Firmware darauf FILE READ für e2sFx.all noch nicht hat.

## Grenzen

- Nur die rote Electribe. Auf der blauen liest die Sitzung BLECH INFO nicht, also bietet die App das Lesen dort nicht an.
- Der Export baut auf das Gelesene nur, solange dieselbe Sitzung besteht und der gewählte Build der gelesene ist.
