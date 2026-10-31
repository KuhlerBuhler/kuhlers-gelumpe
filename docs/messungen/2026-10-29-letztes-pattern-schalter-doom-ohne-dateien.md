# Schalter LAST PATTERN und Doom ohne Dateien

Stand 29.10.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau), kein Gerät. Zu
[Letztes Pattern beim Einschalten](2026-10-28-letztes-pattern.md) und dem Doom-Lader
(`data/patches/doom-loader.json`, `tools/doom/bootstrap.c`).

## Wann was beim Start passiert

BLECH-Satz auf Hacktribe 2.02, Karte mit `KORG/blechtribe`, Zeit seit dem Einschalten (Emulator):

| Zeit | Was | Marker |
|---|---|---|
| 73 ms | `0xC003FD20(1)`, die Karte wird angemeldet | gemessen (Emulator) |
| 99 ms | `0xC00005A0(8)`, die SD-Task läuft | gemessen (Emulator) |
| 117 ms | `0xC002AE64`, der Haken des Doom-Laders | gemessen (Emulator) |
| 140 ms | `0xC002AF40`, die Startfunktion lädt ihr erstes Pattern (`lp_boot`) | gemessen (Emulator) |
| 144 ms | `0xC0025754(0)`, `0xC00005A0(2 bis 10)`, `0xC0025A14(1)`: der normale Start | gemessen (Emulator) |
| 346 ms | `settings.a.bin`, `settings.b.bin` werden gelesen | gemessen (Emulator) |
| 380 ms | die erste Patternwahl (`0xC0079DC8`, `lp_select`) | gemessen (Emulator) |

## LAST PATTERN

- Die Einstellungsdatei kommt nach dem ersten Laden des Patterns und vor der ersten Wahl. `lp_boot` kann den
  Schalter also nicht sehen, `lp_select` schon: mit OFF nimmt die erste Wahl Pattern 0 statt der gemerkten Nummer
  und lädt damit 001 wie die Firmware. Die gemerkte Nummer bleibt in Global-Byte 248. **gemessen (Emulator)**
- Das Einstellungswort liegt bei `0xC014FEFC`, dem letzten Wort der Fläche von last-pattern (`FF` im Abbild aller
  drei Builds, [Messung](2026-10-28-letztes-pattern.md)); `FFFFFFFF` (nie geschrieben) oder 1 ist ON, 0 OFF. In der
  Einstellungsdatei steht OFF als Bit 3 von Byte 5. **offline (Code)**
- Rad auf 004, aus, an mit OFF in der Datei: das Display zeigt 001, das Wort ist 0; aus, an mit ON: 004. Auf
  Hacktribe, Korg rot und Korg blau gleich (`tools/emu/last_pattern_cases.py`, `switch_off`, `switch_on`).
  **gemessen (Emulator)**
- Die Seite in BLECH > FEATURES, WRITE, Neustart und EXIT beim Einschalten: `tools/emu/menu_cases.py`,
  `last_pattern_menu_cases`. **gemessen (Emulator)**

## Doom ohne Dateien, vor der Änderung

SHIFT + TAP beim Einschalten, BLECH-Satz vom 29.10. (develop):

| Karte | Was passierte | Marker |
|---|---|---|
| ohne `KORG/blechtribe/Doom` | `DOOM BOOT`, sechs Versuche `doom.bin` zu öffnen im Abstand von 0,5 s, dann `DOOM ERROR`, `POWER OFF`, Code `00000205`; das Gerät bleibt dort stehen, nur Ein/Aus führt heraus | gemessen (Emulator) |
| nur `doom.bin` | der Lader springt in Doom, nach 2 s steht der Zustand auf Fehler (Stufe `0x80000000`), kein Sampler | gemessen (Emulator) |
| keine Karte | sofort `DOOM ERROR`, Code `00000100` | gemessen (Emulator) |

Vor dem Lesen schaltete der Lader den Systemtakt für Doom um (`0xC0025754(1)`, `0xC00005A0(8)`,
`0xC0025A14(1)`, `0xC003FD20()`); danach startet kein Sampler mehr.

## Doom ohne Dateien, nach der Änderung

Der Lader öffnet `doom.wad` und `doom.bin` jetzt vor diesen Aufrufen. Die Karte ist an der Stelle schon lesbar
(siehe 73 ms und 99 ms oben). Antwortet FatFs mit "keine Datei", "kein Pfad", "kein Laufwerk" oder "kein
Dateisystem" (4, 5, 11, 13), oder ist keine Karte angemeldet, kehrt der Lader zurück und der Start läuft weiter wie
ohne SHIFT + TAP. Andere Fehler (Karte noch nicht bereit) gehen den alten Weg mit sechs Versuchen und `DOOM ERROR`.

| Karte | Ergebnis | Marker |
|---|---|---|
| ohne `KORG/blechtribe/Doom` | Hauptbildschirm, Sampler | gemessen (Emulator) |
| nur `doom.bin` | Hauptbildschirm, Sampler | gemessen (Emulator) |
| keine Karte | Hauptbildschirm, Sampler | gemessen (Emulator) |
| `doom.bin` und `doom.wad` | Doom startet, lädt die WAD | gemessen (Emulator) |

Fälle: `tools/emu/doom_loader_cases.py`; die Fehlercodes mit nachgebautem FatFs: `tools/doom/bootstrap_tests.py`.

## Offen

- Am Gerät nicht geprüft, beides nicht.
- Ob die Karte am Gerät zu diesem Zeitpunkt immer schon antwortet. Antwortet sie noch nicht, bleibt es beim alten
  Weg mit `DOOM ERROR`.
