# Nativer Doom-SD-Lader

Wie der [Patch](../glossary.md#patch) `doom-loader` Doom von der Karte startet. Gemessen im Firmwareemulator. Am Gerät
startet Doom und zeigt ein erkennbares Spielbild (Rückmeldung 23.10.), der Cache-Befehl unten ist am Gerät gemessen
(siehe [Doom auf der Electribe](../hintergrund/doom.md), [Doom auf BLECH v21](2026-10-15-doom-v21.md) und [Rettung](../rettung.md)).
Der Quelltext steht in `tools/doom/` ([Buildanleitung](../../tools/doom/README.md)), der Patch in `tools/patch/doom_loader.py`.

## Aufbau

- **Einsprung:** Der Lader ersetzt in der [VSB](../glossary.md#vsb) das `mov r4, r0` bei `0xC002AE64`, direkt hinter der
  Frage der Firmware nach der `e2sSample.all` (Aufruf bei `0xC002AE60`). Der Start bleibt bis dahin der der Firmware.
- **Auswahl:** Nur exakt SHIFT + TAP (Maske `0x408`, ohne andere Tasten) führt in den Lader. EXIT beim Einschalten
  ist keine solche Kombination und hält den Patch wie jeden anderen heraus. Ohne SHIFT + TAP läuft nur die Tastenprüfung.
- **Ort:** Der Lader liegt im gelöschten (`FF`) Bereich `0xC017CC00..0xC017DC00`, sein Zustand bis `0xC017F000`, gemeinsame
  Daten bis `0xC0180000` (`tools/doom/layout.json`). Die Engine wird nach `0xC1000000` geladen, ihr Stack endet bei
  `0xC1800000`.
- **Laden:** Der Doom-Zweig startet den 1-kHz-Systemtick ohne Sampler-Callbacks, aktiviert nur die SD-Task und die
  Eingabe und liest `KORG/blechtribe/Doom/doom.bin` über die FatFs-Funktionen der Firmware in 4096-Byte-Stücken.
  Länge und SHA-256 müssen zu dem Programm passen, das beim Bau eingebaut wurde, erst dann springt der Lader hinein.
- **Cache:** Vor dem Sprung reinigt er die DCache-Zeilen der Engine-Fläche, leert den Schreibpuffer und invalidiert den
  ICache. Einen Prefetch-Befehl (`c7, c5, 4`) gibt es auf dem ARM926 nicht, am Gerät hängt er, er ist nicht enthalten.
- **Fehler:** Ohne Karte oder ohne `doom.bin` und `doom.wad` kehrt der Lader zurück, bevor er etwas ändert, und der Sampler
  startet. Eine falsche Länge oder Prüfsumme und eine nicht lesbare Karte enden in `DOOM ERROR` mit Code und
  bedienbarem Ein/Aus. Nach teilweise gestarteten Treibern startet kein Sampler als stiller Ersatz.

## Grenzen

- **Hergeleitet:** Die Fläche der Engine liegt im sonstigen Arbeitspuffer des Samplers. Ihre Freiheit folgt daraus, dass
  der Samplerstart im Doom-Zweig ausgelassen wird, keine allgemeine Reservierung.
- **Offen:** Zeit bis zum ersten Bild am Gerät, Ton, weitere WADs.
- Der Lader ist für genau eine `doom.bin` gebaut. Ändert sich die Datei, ändert sich ihr eingebauter Hash, und der Patch
  muss neu gebaut werden.
