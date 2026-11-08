# Effekte aus e2sFx.all beim Start und Dateiliste von SPLASH IMPORT

Stand 5. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei) und Korgs Original 2.02 rot, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/fx_card_cases.py` (`boot_effects`, `version_text`) und
`tools/emu/menu_cases.py` (`splash_menu_cases`). **Am Gerät nicht geprüft.** Die blaue Electribe hat weder die
Effektdatei noch den Startbild-Editor.

## Effekte beim Start

Lädt der Start `KORG/blechtribe/Presets/e2sFx.all`, stehen die neuen Presets im RAM, der DSP spielt aber noch die
Effekte, die das Pattern beim Laden geschickt hat. Nach dem Laden setzt `fx_reapply` (`tools/patch/fx_card.s`) darum den
MFX des Patterns und den IFX jedes der 16 Parts einmal auf Typ + 1 und zurück, beide Male mit Meldung an den DSP: MFX über
den Setter des Pattern-Menüs, IFX über die Part-Bearbeitung, Feld 26. Mit gleichem Wert und ohne Meldung schickt die
Firmware nichts.

Beleg: ein Datensatz IFX bzw. MFX Nummer 5 in der Datei, der als Folge von drei DSP-Übertragungen genau so beim Wählen dieses
Typs ohne Datei entsteht, ist unter den Übertragungen des Starts mit Datei (`boot_ifx_sent`, `boot_mfx_sent`, beide
Firmwares). **Offen:** ob das Umschalten das Pattern als geändert markiert.

## Dritte Zeile von VERSION

BLECH > VERSION zeigt unter der Firmware, was der Start mit der Datei gemacht hat (Status bei `HOOK_CARD+0xFE0`):

| Status | Zeile 3 |
|---|---|
| geladen | `effects loaded` |
| beim Start übersprungen (Sperrtasten) | `effects skipped` |
| Datei für eine andere Firmware | `e2sFx.all wrong fw` |
| Kopf, Eintrag, Prüfsumme oder Lesen falsch | `bad e2sFx.all` |
| keine Datei | leer |

Gemessen: keine Datei, gute Datei, falsche Firmware, falsche Prüfsumme (`version_*`, beide Firmwares).

## SPLASH IMPORT als Liste

SPLASH IMPORT zeigt statt eines festen `splash.bmp` die `.bmp`-Dateien direkt in `KORG/blechtribe/`, in der Reihenfolge
des Ordners. Es filtert wie die Plugin-Liste (`menu_dir_next`, jetzt mit der Endung als Argument): keine Ordner, keine
versteckten oder Systemdateien, kein Punkt vorn, höchstens 31 Zeichen. Das Rad blättert und bleibt an den Enden stehen,
ENTER übergibt den Pfad in `r0` an `splash_import` (`tools/patch/splash_editor.py`; unter `0x10000` nimmt es wie bisher
`splash.bmp`).

Gemessen (`splash_list`): Karte mit `splash.bmp`, `splash (1).bmp`, `._splash.bmp` und `notes.txt`. Das Rad zeigt nur die
zwei Bilder, ENTER auf `splash (1).bmp` speichert genau dessen Pixel. Ohne Bild zeigt die Seite `no .bmp file`.
