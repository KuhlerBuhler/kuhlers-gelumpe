# Sample-Swap: der Bau

Stand: 26.10.2026. Dritter Teil zu [Mehr Sample-Speicher](../ideen/25-mehr-sample-speicher.md), nach dem
[Ladepfad](2026-10-25-sample-swap.md) und dem [RAM-Besitz](2026-10-25-sample-swap-timeout.md).
Beleg: `measure:2026-10-26/sample-swap-bau`.

**Gemessen** heißt hier im ARM-Emulator mit eigenen Firmwaredateien (Hacktribe und Korgs Original, 2.02) und
selbst erzeugten Samples, oder in Unicorn mit selbst gebauten Tabellen. **Hergeleitet** heißt aus dem gelesenen
ARM-Code geschlossen. **Offen** heißt: am Gerät nicht versucht. Kein Gerät wurde angesprochen.

## Was der Patch tut

Builder: [sample_swap.py](../../tools/patch/sample_swap.py), Patch `data/patches/sample-swap.json`, im BLECH-Satz
für beide roten Builds. Der blaue Synth wird verweigert, seine Adressen sind für diese Wege nicht kartiert.

| Teil | Verhalten |
|---|---|
| Ein | nur wenn `e2sSample.all` größer ist als der Nutzerbereich des DSP (25 MiB) plus 4 KiB Kopf und EXIT beim Einschalten nicht gehalten war; sonst laufen alle Haken sofort weiter und die Firmware lädt wie immer |
| Start | der Lader liest den Kopf und nur die Samples, die das aktuelle Pattern benutzt; die anderen Plätze überspringt er |
| Im DSP | was das laufende Pattern braucht, dazu das als nächstes kommende: das gewählte, sonst das Kettenziel |
| Wechsel | sind die Samples des neuen Patterns noch nicht alle im DSP, wechselt das Pattern nicht, das laufende spielt eine Runde mehr; bei einer Kette bleibt der Wiederholungszähler auf der letzten Runde |
| Platz | ein neues Sample bekommt die niedrigste freie Stelle im Nutzerbereich, notfalls werden Samples entfernt, die weder das laufende noch das kommende Pattern benutzt |
| Dynamisch | ein Part, der im laufenden Pattern ein anderes Sample bekommt, lädt es nach |
| RAM-Cache | während ein Pattern auf dem Hauptbildschirm spielt, liest der Patch die Samples des Kettenziels und der beiden Nachbarpatterns in freies ARM-RAM; ein späterer Wechsel kopiert dann RAM in den DSP statt von der Karte |
| Cache verwerfen | jeder andere Bildschirm, ein Fenster auf dem Hauptbildschirm (der Sampling-Modus ist eines) und jeder Aufruf des Arbeitspuffer-Gebers `0xC00369F0` verwerfen den Cache; gefüllt wird erst wieder nach dem nächsten PLAY auf dem Hauptbildschirm |
| Prüfsumme | eine Summe über jedes Sample im Cache wird vor dem Eintragen in den Slot geprüft; stimmt sie nicht, wird nichts eingetragen, der Cache verworfen und das Sample von der Karte geladen |

Die Tabellen trägt die Firmware selbst ein: der Patch ruft ihren Parser bis kurz vor die Platzvergabe
(Haken `0xC003621C`), stellt den Frei-Zeiger `0xC00F9C80` auf die gewählte Stelle und ruft die Platzvergabe
`0xC004EDF0` mit dem Deskriptor des Parsers. Entfernen ist der Löschweg der Firmware `0xC004E558`. Das PCM
schreibt der begrenzte Transfer aus der [vorigen Runde](2026-10-25-sample-swap-timeout.md) (100 ms je Aufruf,
64 KiB), bevor der Slot eingetragen wird; ein halb geladenes Sample ist also nie spielbar.

## In welcher Task

**Gemessen im Emulator:** Die UI-Task läuft mit 25 Bildern je Sekunde (Stack um `0xC020B000`), alle Kartenzugriffe
der Firmware und der BLECH-Laufzeit laufen in der Command-Task (Stack um `0xC030A000`): Laden beim Start, die
Plugin-Dateien. Zwei Tasks, die gleichzeitig über FatFs auf die Karte gehen, könnten deren Sektorpuffer
durcheinanderbringen.

**Gebaut:** Der Rahmen der UI-Task (Haken `0xC00836F4`) prüft nur Bildschirm und Transport und schickt der
Command-Task ein eigenes Kommando (`0x7E`, die Tabelle der Firmware endet bei 44). Dessen Ausführung (Haken an
der Verteilung `0xC002D684`) macht die ganze Arbeit, höchstens 15 ms je Kommando, je Schritt ein Block bis 64 KiB.
So liegt jeder Kartenzugriff des Patches in derselben Task wie die der Firmware.

Die beiden Sperren laufen in der Sequenzer-Task und lesen nur: am Sequenzende vor dem Aufruf `0xC0079AA8`
(Haken `0xC005F1D4`) und im Kettenschritt an der Stelle, die das Ziel schreibt (Haken `0xC0079A74`).
Beide liegen vor jeder Änderung der Patternnummer, wie die [vorige Runde](2026-10-25-sample-swap-timeout.md)
verlangt hat.

## Speicher

| Bereich | Inhalt | Status |
|---|---|---|
| `0xC01A2FD0`, `0xC018A4C0`, `0xC0189760`, `0xC018BF40` | Code, 4908 Byte in vier FF-Läufen beider Builds, die kein anderer Patch des Satzes nutzt | gemessen am Abbild |
| `0xC0188530` bis `0xC0188730` | Zustand: Modus, Cache-Generation, laufender Auftrag, gescheiterte Plätze, Dateipfad | gemessen am Abbild |
| `0xC274F000` bis `0xC276F000` | 96 KiB Zwischenpuffer, Dateiobjekt, zwei Deskriptoren, Dateikopf, Cache-Verzeichnis | in keiner gemessenen Phase von der Firmware benutzt ([RAM frei](2026-10-22-ram-frei.md)) |
| `0xC276F000` bis `0xC4000000` | oberer Cache, rund 24,5 MiB | wie oben |
| `0xC0D3A940` bis `0xC273AA40` | unterer Cache, rund 26 MiB, der Arbeitspuffer der Firmware: nur geliehen, solange der Cache gilt | siehe nächster Abschnitt |

Der Bereich über dem Interrupt-Stack steht jetzt als `HIGH_RUNS` in `data/patch-ram.mjs`; die Prüfung der
RAM-Plätze lässt dort erklärte Bereiche zu. Der Arbeitspuffer bleibt in `data/protected.mjs` geschützt und
wird nicht als Bereich des Patches erklärt.

## Der Cache gehört nur dem normalen Spielen

**Gemessen im Emulator**, je Ablauf ein eigener Start: Cache füllen (PLAY auf dem Hauptbildschirm, bis ein
Sample eines Nachbarpatterns darin liegt), STOP, dann der Ablauf. Jeder Schreibzugriff in beide Cache-Bereiche
von Code außerhalb des Patches wurde mit der Cache-Generation in diesem Moment festgehalten.

| Ablauf | fremde Schreibzugriffe in den Cache | davon vor dem Verwerfen |
|---|---|---|
| IMPORT SAMPLE | 10432 | keiner |
| EXPORT ALL SAMPLE | 80000 | keiner |
| EXPORT ALL PATTERN | 0 | keiner |
| IMPORT ALL PATTERN (nach einem EXPORT ALL PATTERN im selben Lauf) | 1041408 | keiner |
| SAMPLING mit Durchschalten der Quellen (darunter RESAMPLING), zweimal REC, STOP, EXIT | 0 | keiner |

Verworfen wird in allen Abläufen schon beim Verlassen des Hauptbildschirms, beziehungsweise beim Öffnen des
Sampling-Fensters; der Geber-Haken ist die zweite Sicherung für Wege, die ohne Bildschirmwechsel an den
Puffer gehen.

**Offen:** Sampling und Resampling mit echtem Audio und DMA. Der Emulator hat keinen DMA; dass dort keine
CPU-Schreibzugriffe kamen, sagt über DMA nichts. Dafür sorgt die Prüfsumme: ein Sample, das jemand anderes im
Cache verändert hat, wird nie eingetragen.

## Fälle im Emulator

[swap_cases.py](../../tools/emu/swap_cases.py), von `tools/emu/check.py` auf jeder Kopie mit den Haken gerufen.
Die meisten Fälle setzen in ihrer eigenen Kopie das Budget (`ss_cap`) herab, damit eine Datei größer als das
Budget nur einige hundert KiB hat. Alle Samples sind Formeln aus `sampleset.py`.

| Fall | Ergebnis (Hacktribe) | Status |
|---|---|---|
| Datei, die der DSP hält | Modus aus, alle vier Samples wie bisher geladen | gemessen |
| Datei größer als das Budget | Modus an, nur die zwei Samples des Patterns im DSP, zwei von zehn Samples gelesen | gemessen |
| EXIT beim Einschalten | Modus aus, alle zehn geladen | gemessen |
| Echtes Budget, Datei 28.651.664 Byte (neun Samples zu 3 MiB, die kein Pattern nutzt) | Start nur mit Slot 500, Wechsel lädt 501 und 502, keines der großen Samples im DSP | gemessen |
| Wechsel auf ein Pattern mit 2 × 600000 Byte | gewählt bei 1,25 s, Sequenzende bei 2,97 s ohne Wechsel, Wechsel bei 4,98 s mit beiden Samples im DSP | gemessen |
| Kette nach Pattern 3 mit denselben Größen | Versuch bei 2,97 s abgewiesen, Wechsel bei 4,97 s | gemessen |
| Budget 512 KiB, drei Wechsel mit je zwei Samples | nach jedem Wechsel die Samples des Patterns im DSP, keine Überlappung, nichts über dem Budget | gemessen |
| Part bekommt ein anderes Sample | nachgeladen | gemessen |
| Nachbar im Cache, dann Wechsel | aus dem RAM eingetragen, PCM im DSP gleich der Datei | gemessen |
| Anderer Bildschirm | Cache verworfen, ohne neues PLAY nicht wieder gefüllt, nach STOP und PLAY wieder gefüllt | gemessen |
| Ein Wort im Cache verändert | nicht eingetragen, Cache verworfen, von der Karte geladen, PCM gleich der Datei | gemessen |
| Vergleich mit dem Lader der Firmware (16 Bit, 24 Bit, Stereo) | Namen, Metadaten und Wiedergabeeintrag gleich bis auf die DSP-Adresse, PCM gleich | gemessen |

Dazu laufen die Routinen in Unicorn gegen selbst gebaute Tabellen
([test_sample_swap.py](../../tools/patch/test_sample_swap.py)): Belegungsprüfung über die drei Zuordnungen,
Bereitschaft eines Patterns, Sperre am Sequenzende und in der Kette, Platzsuche mit Ausrichtung und Budget,
Entfernen nur ungeschützter Samples, der Geber-Haken.

## Was noch offen ist

| Punkt | Stand |
|---|---|
| Ladezeiten am Gerät, RAM zu DSP gegen Karte zu DSP, mit dem Patch selbst | offen, Werkzeug vorbereitet (unten) |
| Klang beim Entfernen: eine noch ausklingende Stimme eines entfernten Samples kann Fremdes lesen | offen; entfernt wird nur, was weder laufendes noch kommendes Pattern benutzt |
| Namen nicht geladener Samples | die Firmware zeigt für sie ihre Platzhalter `SampleNNN`; Namen erst beim Laden |
| Patternwechsel bei gestoppter Wiedergabe | lädt wie immer sofort, die Samples kommen danach in einigen Sekunden; keine Sperre |
| Ein Pattern, das mit dem laufenden zusammen nicht ins Budget passt | der Platz scheitert, der Wechsel kommt ohne die fehlenden Samples, die nach dem Wechsel nachgeladen werden |
| Last der Command-Task beim Laden während des Spielens | hergeleitet höchstens 15 ms je UI-Bild (40 ms); ob Pattern-Laden oder Stimmen das hören, ist offen |
| Ein Kartenfehler beim Öffnen | schaltet den Swap bis zum nächsten Start ab, Wechsel gehen dann ohne Sperre |
| High Speed (50 MHz) | aus; erst nach einem Versuch mit einer entbehrlichen microSD |
| DMA | aus |

## Gerätemessung vorbereitet

Werkzeug: [sample_swap_stats.py](../../tools/device/sample_swap_stats.py). Es sendet nur BLECH INFO und READ,
vergleicht den Code des Swaps im Gerät mit dem Bau für die eigene Originaldatei und meldet danach jedes fertig
geladene Sample mit Quelle (Karte oder RAM), PCM-Bytes, den Timer-3-Takten des Patches und MiB/s. Ohne `--watch`
entsteht nur ein Plan.

```bash
PYTHON=tools/emu/.venv/bin/python
"$PYTHON" tools/device/sample_swap_stats.py --plan
"$PYTHON" tools/device/sample_swap_stats.py --watch 300 --vsb "$OWN_VSB" --json "$HOME/swap-stats.jsonl"
```

Ablauf am Gerät: eine `e2sSample.all` über 25 MiB auf die Karte, starten, ein Pattern spielen. Für Karte zu DSP
ein Pattern wählen, dessen Samples weder im DSP noch im Cache liegen (weit weg, kein Nachbar, kein Kettenziel);
für RAM zu DSP auf einen Nachbarn wechseln, nachdem er einige Sekunden lang vorgeladen wurde. Dabei hören, ob die
laufenden Stimmen beim Laden aussetzen. Die älteren Werkzeuge `sample_swap_probe.py` und `sample_swap_paths.py`
verweigern, solange der Swap an ist: ihr Arbeits-RAM liegt in seinem Zwischenpuffer.

## Prüfbefehle

```bash
node --test test/sample-swap.test.mjs test/patch-ram.test.mjs test/sample-swap-paths.test.mjs
E2_VSB="$OWN_VSB" E2_STOCK_VSB="$OWN_STOCK_VSB" E2_EMU_REQUIRED=1 node --test test/sample-swap.test.mjs
tools/emu/.venv/bin/python tools/emu/swap_cases.py cases --patched "$PATCHED_VSB"
```
