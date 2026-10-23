# Effekte aus dem Katalog fest in der Firmware (23.10.)

Wunsch vom 23.10.: Die Effekte aus dem Katalog sollen nach dem Patchen schon in den Menüs stehen. Man kann sie ändern oder über
die Sammeldatei auf der Karte überschreiben. Im Emulator geprüft, **am Gerät nicht**.

## Was gebaut ist

- `data/patches/fx-catalog.json` (erzeugt von `node tools/fx-catalog-patch.mjs` aus `data/fx/catalog.mjs`): die 8 Insert- und 8
  Master-Effekte des Katalogs als .e2fx-v2-Werte, dazu die Parameterlisten ihrer Bausteine aus `data/units.json`. Kein
  Firmwarebyte darin.
- `src/fx-append.mjs`: Beim Anwenden des BLECH-Satzes hängt `applyPatches` sie hinter das letzte Preset jedes Menüs. Jeder Platz
  bekommt eine Kopie von Preset 1 derselben Firmware, darin der Effekt (`fxToRecord`, wie bei der Sammeldatei). Die
  Menülängen gehen um je 8 hoch.
- Ein Effekt, dessen Name im Menü schon steht, wird ausgelassen. Zweimal angewendet kommt nichts dazu.
- Die Plätze hängen davon ab, wie viele Presets die Firmware schon hat. Was der Katalog schreibt, bleibt deshalb Nutzerdaten
  der Patch-Datei (`src/patchfile.mjs`), ihre Fingerabdrücke hängen nicht davon ab.
- Nur rot (Hacktribe und Korgs Original), die blaue hat andere Bausteine.

## Gemessen (`tools/emu/preset_cases.py`, Basis: BLECH-Satz ohne Katalog)

| | Hacktribe 2.02 | Korg rot 2.02 |
|---|---|---|
| Insert-Menü | 49 auf 57 | 38 auf 46 |
| Master-Menü | 32 auf 40 | 32 auf 40 |
| INSERT-Regler läuft alle Einträge durch und springt zurück | ja | ja |
| jeder neue Platz mit eigenem Record und Namen | ja | ja |
| Wahl jedes neuen Platzes schickt dem DSP Übertragungen, keine Assertion | Insert je 14, Master 10 bis 11 | ebenso |

Mehr als 15 Zeichen zeigt die Firmware nicht, deshalb heißt `Triplet Ping Pong` jetzt `Tri Ping Pong`.

**Offen:** Klang am Gerät, wie bei allen Katalogeinträgen ([FX-Katalog neu](2026-10-22-fx-katalog-neu.md)). Der Short Delay
steht auf demselben Grund-Record (Master 1, Mod Delay) wie die am Gerät gehörte Fassung vom ESX-Nachbau.
