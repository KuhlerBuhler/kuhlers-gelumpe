# Plugin Display: native Zeichenfunktionen und Fehlermeldung

Stand 2026-10-14. Kein Gerätezugriff. Alles im
Emulator und in Unicorn ohne Firmware gemessen. Markierungen: **gemessen**, **hergeleitet**.
Hintergrund: [`../hintergrund/skript-laufzeit.md`](../hintergrund/skript-laufzeit.md).

## Umsetzung

- **Zeichnen** (`tools/patch/script_display.s`): `clear`, `text`, `number`,
  `pixel`, `rect`, `clearRect` zeichnen in ein eigenes Bild der Laufzeit
  (1024 Byte hinter dem LED Zustand, Anfang `RT_DISPLAY`). Rechtecke werden
  spaltenweise mit Seitenmasken gefüllt, Text zeichnet nur gesetzte Pixel, Zahlen
  werden mit Zehnerpotenzen ohne Division in Ziffern zerlegt. Ränder schneiden ab,
  nichts wickelt um (die Firmwarefunktionen wickeln um).
- **Schrift:** eine eigene 5 mal 7 Schrift, Zeichenabstand 6, aus
  `data/script/font.mjs`. Browsermodell und Laufzeit lesen dieselbe Tabelle
  (`script_font`, aus dem Vertrag erzeugt). Die Firmware wird nicht gerufen: ihre
  Textfunktion braucht 88 000 bis 267 000 Befehle für 15 Zeichen,
  die eigene rund 440 je Zeichen.
- **Besitz des Displays:** Nach dem ersten Zeichenaufruf kopiert der Rahmenhaken
  das Bild in jedem Rahmen über das Display RAM `0xC031B310`, nach dem Zeichnen der
  Firmware Widgets, aber nur bei geöffnetem Hauptbildschirm
  (`screen manager + 0x2C == 1`). Menüs zeigt die Firmware.
- **Fehlermeldung:** Ein Fehler beim Ereignis oder im Rumpf ersetzt das Bild durch
  Pluginname, `Zeile n` und den Fehlernamen (Tabelle `script_error_names`, 16 Byte je
  Code, aus dem Vertrag erzeugt). Rumpffehler werden mit dem ersten Rahmen gezeigt.
- **Kosten** (Vertrag, ein Byte je Eintrag, Obergrenze 250): `clear` 80, `pixel`
  4, `rect` und `clearRect` 40, `text` und `number` 250. Gemessen in Unicorn
  (Befehle): `clear` 782, `pixel` 27, `rect` 8x8 166 und Vollbild 11941, `text` 5
  Zeichen 2209 und 31 Zeichen 13203, `number` 6194. Eine Kosteneinheit entspricht
  etwa 10 Befehlen (hergeleitet aus 9 bis 10 Befehlen je VM Operation, siehe
  `docs/plugins.md`). Die Einträge gelten für kurze Aufrufe; ein Vollbild oder ein
  langer Text kostet in Echtzeit mehr, begrenzt wird das vom 5 ms Rahmenbudget.

## Prüfungen (gemessen)

| Prüfung | Ergebnis |
|---|---|
| `tools/patch/test_script_display.py`: 70 Fälle (10 feste, 60 zufällige mit je 25 Aufrufen, Ränder, Zahlen von `-2147483648` bis `2147483647`) gegen das Browsermodell | alle Bytes gleich |
| Blit nur bei offenem Hauptbildschirm und `displayActive == 1`, Schutz bei Nullzeiger | bestanden |
| Fehlerbild eines Plugins (DIV_ZERO) gegen `drawFault` | Bytes gleich |
| Firmware im Emulator, Karte mit Klicker: Anzeige nach `ready` gleich dem Browsermodell, TAP zählt (Anzeige und LED 20), MENU zeigt das Menü der Firmware, EXIT bringt das Klickerbild zurück | bestanden |
| Fehler beim Tastendruck: Fehlerbild gleich dem Modell, Firmware bedienbar | bestanden |
| Fehler im Rumpf: Fehlerbild mit dem ersten Rahmen | bestanden |
| `check.py` auf Startbild, MFX 2 und Laufzeit | 37 von 37 |
| `E2_ARM_REQUIRED=1 npm test` | 460 Tests, 419 bestanden, 41 ohne Firmware übersprungen, 0 Fehler |

## Grenzen

- Am Gerät ist nichts geprüft. Das Display RAM bei `0xC031B310` ist am Gerät
  gelesen (`2026-10-09-menuezustand.md`), dass das Schreiben dort ins Display geht,
  ist dort nur im Emulator belegt.
- Die Schrift sieht anders aus als die der Firmware.
- Der Statusblock hält die höchste Zeit je Handler; eine Warnung bei mehr als
  0,5 ms zeigt erst der Editor, nicht das Gerät.
