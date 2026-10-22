# Doom am Gerät: Zwischenanzeigen und der Cache-Befehl, an dem es hing (22.10.)

Am Gerät (Hacktribe, BLECH von develop `145fa90`, neue `doom.bin` `7bfb6282…`) blieb Doom nach SHIFT + TAP zehn Minuten bei
`DOOM START` stehen. Im Emulator spielte derselbe Stand.

## Zwischenanzeigen in der Engine (`tools/doom/runtime.c`)

Bis zum ersten Bild zeigt das Display jetzt, wie weit die Engine ist:

| Anzeige | Wann |
|---|---|
| `DOOM ENGINE` | erste Anweisung der Engine, vor allem anderen |
| `DOOM ERROR ABI 00000700` | Lader und Engine passen nicht zusammen (vorher eine stumme Schleife) |
| `DOOM ENGINE INIT` mit Zahl | der Tickzähler der Firmware beim Start der Engine (Hex) |
| `DOOM` und die letzten zwei Zeilen der Engine | bei jeder Ausgabe, zum Beispiel `M_INIT: ...` |
| `DOOM OPEN WAD`, `DOOM WAD FEHLT` mit Code `0x800 + Fehler` | vor dem Öffnen der WAD, und wenn es scheitert |
| `DOOM LADE WAD` mit MB und Balken | wie bisher, beim Lesen |

Die Schrift kann jetzt A bis Z, 0 bis 9 und `: . - /`. Neue `doom.bin` `d3c35e89…`, 451572 Byte, aus dem Quellarchiv bytegleich
neu gebaut (`rebuild_runtime.py`, gemessen). Im Emulator (Hacktribe, eigenes Flash) erscheinen die Anzeigen, nach 150 s steht
`LADE WAD 8 MB`; der Stand von develop steht nach 70 s an derselben Stelle (`M_Init`, 2,9 MB), der Emulator ist langsamer als
das Gerät.

Am Gerät blieb auch damit `DOOM START` stehen: nicht einmal die erste Anweisung der Engine lief.

## Der RAM der Engine (gemessen am Gerät, nur gelesen)

`0xC1000000` bis `0xC1800000` ist eigener Speicher: der RAM hat 64 MiB, erst `0xC4000000` zeigt dasselbe wie `0xC0000000`. Im
normalen Betrieb steht dort nur das Bitmuster vom Einschalten (Stichproben alle 512 KiB), die Firmware nutzt den Bereich nicht
(hergeleitet).

## Der Cache-Befehl (gemessen am Gerät)

Vor dem Sprung reinigt der Lader die D-Cache-Zeilen der Engine (`c7, c10, 1`), leert den Schreibpuffer (`c7, c10, 4`),
invalidiert den I-Cache (`c7, c5, 0`) und leerte bisher den Prefetch-Puffer (`c7, c5, 4`). Den letzten Befehl beschreibt das
ARM926EJ-S TRM nicht, er stammt aus ARMv6. Unicorn führt ihn aus, als wäre nichts.

Test am Gerät, nur im RAM: ein Stück Code bei `0xC1000000`, über Hacktribes Execute-Befehl aufgerufen, zählt vor und nach dem
Befehl in ein Wort.

| Befehl | Ergebnis |
|---|---|
| `c7, c10, 1` und `c7, c10, 4` | kommt zurück (`0x11`), zweimal |
| `c7, c5, 4` | keine Antwort mehr, Display schwarz, LEDs an; nur Ausschalten hilft |

Der Lader ohne `c7, c5, 4` (3028 Byte), neu gepinnt auf dieselbe `doom.bin`.

## Offen

- Ob Doom am Gerät mit dem neuen Lader startet.
