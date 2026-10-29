# Uhr und Timer der Plugin-Laufzeit

Stand 29. Oktober 2026. Gemessen im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz; auf den roten 20 Samples zu je 4 s auf der Karte, damit der Sample-Lader gut eine Sekunde läuft.
Fälle: `tools/emu/timer_cases.py`. **Am Gerät nicht geprüft.** Beschreibung für Nutzer: [Timer](../plugins.md).

## Frage

Timer3 läuft mit 150 MHz und die Firmware lässt ihn jede Sekunde überlaufen. Die Laufzeit zählt daraus die Millisekunden
nur, wenn sie aufgerufen wird (`script_clock_update`). Hängt der Rahmenhaken länger als eine Sekunde, gehen ganze Sekunden
verloren. Wann hängt er, und gibt es einen Zähler, der ständig gleichmäßig steigt?

## Rahmen (gemessen)

Zähler der Rahmen der Laufzeit, jede Millisekunde Gerätezeit gelesen, 5 bis 7 s ab dem Einschalten.

| | Hacktribe | Korg rot | Korg blau |
|---|---|---|---|
| erster Rahmen nach dem Einschalten | 1371 ms | 1363 ms | 302 ms |
| Abstand der Rahmen danach, Median | 40 ms | 40 ms | 40 ms |
| größter Abstand danach | 46 ms | 45 ms | 45,7 ms |

Der Sample-Lader läuft vor dem ersten Rahmen. Ein Plugin auf der Karte startet erst danach (sein Rumpf lief bei
1390 ms, Hacktribe, und 1382 ms, Korg rot, nach dem Einschalten), es sieht das Laden also nicht. Ein Pattern-Wechsel aus
einem Plugin (`korg.pattern(5)`) lässt keinen Rahmen länger als eine Sekunde warten.

## Tick-Zähler des Betriebssystems (gemessen)

`0xC06A292C` (blau `0xC0573CE8`, aus der Karte der blauen) zählt eine Millisekunde je Tick
(`tools/patch/power_off.py`). Gegen die Gerätezeit:

| | Hacktribe | Korg blau |
|---|---|---|
| Stillstand beim Start, länger als 20 ms, bei | 21 ms, 72 ms | 21 ms, 65 ms |
| längster Stillstand | 89 ms | 258 ms |
| geht nach, bis zum Ende des Starts | 149 ms | 306 ms |
| geht nach, ab dem ersten Rahmen über rund 4 s | 0,5 ms | 5,5 ms |

Der Zähler steigt also nicht ganz gleichmäßig: beim Start steht er kurz, danach geht er ein wenig nach. Timer3 ist
genauer. **Hergeleitet:** die Laufzeit nimmt die Millisekunden weiter aus Timer3 und den Tick-Zähler nur für die ganzen
Sekunden, die Timer3 nicht sehen konnte: liegt der Tick-Zähler zwischen zwei Aufrufen 500 ms oder mehr vor dem, was
Timer3 zählt, kommen so viele ganze Sekunden dazu. Geprüft ohne Firmware in `tools/patch/test_script_hw.py` (2,4 s Lücke,
Timer3 zeigt 400 ms, die Uhr zählt 2400 ms).

## Timer (gemessen)

| Fall | Hacktribe | Korg rot | Korg blau |
|---|---|---|---|
| `korg.after(1000)` aus `ready`: Gerätezeit vom Aufruf bis zur Funktion | 1039 ms | 1038,2 ms | 1039,5 ms |
| dasselbe, drei Rahmen nach dem Aufruf `korg.pattern(5)` | 1035 ms | 1034,2 ms | 1000,5 ms |
| `korg.after(1000)` aus dem Rumpf eines Plugins auf der Karte, beim Start | 1001,2 ms | 1040 ms | 1000,2 ms |
| Uhr des Plugins (`korg.millis()`) dabei, gleiche Fälle | 1039, 1035, 1001 ms | 1039, 1035, 1039 ms | 1040, 1001, 1000 ms |
| `korg.afterSteps(4)` beim zweiten Schritt nach PLAY: die Funktion läuft beim Schritt | 6 | 6 | 6 |

Alle Fälle liegen zwischen 1000 und 1040 ms (die Gerätezeit ist auf 1 ms gelesen). Eine Abweichung durch das
Sample-Laden gibt es im Emulator nicht, weil kein Plugin vor dem Laden läuft.

## Offen

- Am Gerät messen, ob ein Rahmen beim Speichern eines Patterns (WRITE) oder beim Import von Samples länger als eine
  Sekunde ausbleibt; die Uhr holt die Sekunden dann über den Tick-Zähler, ein Timer läuft im ersten Rahmen danach.
