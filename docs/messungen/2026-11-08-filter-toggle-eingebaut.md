# FILTER TOGGLE fest eingebaut

Stand 08.11.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau), kein Gerät. Zu
[Idee 81](../ideen/81-filter-schnellschalter.md). Vorher gab es das als Plugin Filter Toggle im Katalog (API 14); das
Plugin ist aus dem Katalog genommen. Marker: **gemessen** (im Emulator), **offline gelesen** (Disassembly), **hergeleitet**.

## Was es tut

SHIFT gehalten + LPF, HPF oder BPF: das Filter des gewählten Parts geht aus (Typ 0, OFF). Dieselbe Kombination schaltet es
wieder an, mit dem Typ, den diese Taste zuletzt hatte. SHIFT + eine andere Filtertaste gibt deren letzten Typ, ohne
Speicher den ersten der Familie (LPF 1, HPF 7, BPF 12, je electribe). Jeder Part hat je Familie einen eigenen Speicher bis
zum Ausschalten, nicht auf der Karte. Die Taste allein dreht wie immer weiter. BLECH > FEATURES > FILTER TOGGLE (letzte
Seite) schaltet es aus, WRITE behält das in Bit 5 von Byte 5 der Einstellungsdatei. Mit EXIT beim Einschalten ist es aus.

## Wie es gebaut ist

Die Filtertaste geht immer an die Firmware. FILTER TOGGLE ersetzt nur den neuen Typ (r4) auf dem Weg ihres Handlers, der den
Typ schreibt und das Fenster "FILTER TYPE" öffnet. Darum sehen LEDs, Fenster und Parameter-Nachricht genau so aus wie beim
Drücken der Taste ohne SHIFT.

| Teil | Wo | Marker |
|---|---|---|
| Eingang: LPF, HPF, BPF (Tasten 0x12, 0x14, 0x16) im Eingangsfilter; notiert in `FT_KEY` (MENU_STATE + 0x164), ob SHIFT gehalten ist (Familie plus 1) oder nicht (0), und lässt die Taste durch | `tools/patch/script_shortcuts.s:ft_input` (im Startphasen-Abschnitt `kp_input`) | gemessen |
| Typ ersetzen: Haken auf dem Befehl `mov r0, #8` im Handler, r4 = neuer Typ der Firmware, r5 = alter; merkt r5 und den Typ der Firmware je Part und Familie in `FT_LAST` (48 Byte ab MENU_STATE + 0x168), setzt r4 neu und springt zurück | `ft_select`, `script_hooks.py` (SITES, `FILTER_TOGGLE_HACKTRIBE`) | gemessen |
| Schalter: `M_FT` (MENU_STATE + 0x160), Seite 49 der Liste FEATURES | `tools/patch/script_menu.s` | gemessen |

Adressen des Hakens (dahinter geht es bei Adresse + 4 weiter):

| Build | Haken | Marker |
|---|---|---|
| Korg rot 2.02 | `0xC006FDEC` | offline gelesen, gemessen |
| Korg blau 2.02 | `0xC0062F14` | offline gelesen, gemessen |
| Hacktribe 2.02 | `0xC01501F0`, eigener Filter-Handler von Hacktribe; der Korg-Weg bei `0xC006FDEC` läuft dort nie (Sonde: Haltepunkt nicht erreicht, der Typ wird aus `0xC0150xxx` geschrieben) | gemessen |

Der Bereich MENU_STATE + 0x160 bis + 0x1B7 war vorher unbenutzt (offline gelesen in `script_*.s`).

## Prüfung

`tools/emu/shortcut_cases.py` (Gruppe `case_filter_toggle`) und `tools/emu/menu_cases.py` (`filter_toggle_menu_cases`), je
Hacktribe, rot und blau. Zwillings-Probe: jeder Druck von SHIFT + Taste wird auf einem zweiten Gerät (FILTER TOGGLE aus) gegen
einen Druck der echten Filtertaste gestellt, von dem Typ aus, dessen Schritt der Firmware auf denselben Typ führt.

| Fall | Ergebnis | Marker |
|---|---|---|
| Typ nach jedem SHIFT + Taste, ab MS20 LPF (2): `0, 2, 7`, Taste HPF allein `8`, dann `2, 8, 0, 12`; Part 4 ab MG LPF (3): `0, 3`; zurück auf Part 1: `2` | wie erwartet, gleich dem Zwilling | gemessen |
| LEDs von LPF, HPF, BPF nach jedem Druck | gleich dem Zwilling | gemessen |
| Fenster: Texte im Bildspeicher, "FILTER TYPE" und der Name (z. B. "OFF", "MS20 LPF", "electribe HPF") | gleich dem Zwilling | gemessen |
| Parameter-Nachricht der Firmware und das ganze Bild | gleich dem Zwilling | gemessen |
| FILTER TOGGLE OFF und EXIT beim Einschalten: ab MS20 LPF zweimal SHIFT + LPF gibt dasselbe wie zweimal LPF (Hacktribe und blau `[3, 4]`, rot mit EXIT `[0, 1]`) | wie die Firmware | gemessen |
| Seite FILTER TOGGLE: ON ohne Datei, das Rad schaltet sofort, WRITE schreibt Bit 5, der nächste Start liest OFF und ON | wie erwartet | gemessen |
| Am Gerät | Am Gerät nicht geprüft | offen |

## Wer das alte Plugin noch auf der Karte hat

Das Plugin Filter Toggle (`.blech` auf der Karte) läuft weiter, beide zusammen sind aber unnötig:

- **App geschlossen:** die Firmware sieht SHIFT + Filtertaste, FILTER TOGGLE setzt den Typ. Das Plugin rechnet im nächsten
  Rahmen aus dem Typ beim Druck auf SHIFT denselben Wechsel und setzt denselben Typ noch einmal (hergeleitet aus dem
  Quelltext des Plugins, nicht gemessen).
- **App offen:** das Plugin hält mit `korg.passKeys` die Filtertasten zurück, solange SHIFT gehalten ist. Die Firmware und
  damit FILTER TOGGLE sehen die Kombination nicht, nur das Plugin schaltet, ohne Fenster (hergeleitet).
- Auf der blauen schreibt das Plugin nichts (`korg.seq.setPartValue`), dort wirkt nur FILTER TOGGLE.

Empfehlung: das Plugin von der Karte nehmen oder FILTER TOGGLE ausschalten.

## Grenzen

- Ein BLECH vor dieser Version lehnt eine Einstellungsdatei mit Bit 5 in Byte 5 ab und startet mit den Vorgaben, wie bei
  den früheren Bits (hergeleitet aus `menu_load`).
- Ob der Weg mit `mov r0, #8` auch von etwas anderem als der Filtertaste erreicht wird (etwa vom Rad auf der Seite FILTER
  TYPE), ist nicht geprüft. Ohne vorherigen Druck mit SHIFT steht `FT_KEY` auf 0, dann bleibt der Typ der Firmware und wird
  nur gemerkt (hergeleitet).
- Im Objektbaum der Plugin-API (`korg.object`) gibt es noch keinen Eintrag für FILTER TOGGLE.
