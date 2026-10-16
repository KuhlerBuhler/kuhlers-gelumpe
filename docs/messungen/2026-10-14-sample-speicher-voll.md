# Voller Samplespeicher: schreibt die Firmware in BLECHs RAM?

Stand 2026-10-14. Alles im Emulator gemessen (Firmware 2.02 mit Hacktribe, eigener Flash-Dump vom
9.10., virtuelle Karte), am Gerät nichts geprüft. Markierungen: **gemessen** (im Emulator ausgeführt
und gesehen), **hergeleitet**, **offen**. Der Emulator hat keinen Klang und keinen DMA, der DSP ist
eine Attrappe ([Emulator](../emulator.md)). Die Samples sind selbstgebaut, die Audiodaten eine
Formel, nichts davon ist von Korg.

Frage: Wenn der Samplespeicher ganz voll ist (alle Nutzerplätze 501 bis 999 belegt, bis an die
Grenze des Speichers), schreibt die Firmware dann in die RAM-Bereiche, die BLECH benutzt (Code im
freien Block des Abbilds, Laufzeitzustand, Plugin-Pool, LED-Zustand, Einstellungspuffer)? Oder
überlappt etwas, was die Firmware für Samples, Heap oder Puffer braucht?

## Ergebnis

- **Nein, in keinem Lauf.** Über alle Läufe stehen rund 8 Millionen beobachtete Schreibzugriffe ins
  Abbild, kein einziger fremder in einen BLECH-Bereich (Tabelle unten). Auch über die 64-MiB-Spiegelung
  schrieb nichts. Nach jedem Lauf sind alle 37.176 Byte Code, Tabellen und geänderte Firmware-Wörter
  von BLECH Byte für Byte die der gepatchten Datei.
- **Kein BLECH-Bereich muss verschoben werden.** Das Layout bleibt.
- Klicker und Snake laufen mit vollem Speicher (Snake: 150 Rahmen, Anzeige gleich dem Browsermodell),
  Muster spielen, die Firmware-Menüs und DATA UTILITY gehen.
- Warum das so ist (hergeleitet aus der Messung): die Sample-Daten gehen gar nicht durch das CPU-RAM.
  Jedes Sample liegt kurz im Arbeitspuffer ab `0xC0D3A940` und geht von dort über den Host-Port in den
  Speicher des DSP. Im CPU-RAM ändern sich nur drei kleine Tabellen und die Stelle im Abbild, an der die
  Firmware ihren Zeiger auf den nächsten freien DSP-Platz hält. Das Abbild reicht nur bis `0xC0200000`,
  alles, was die Firmware beim Start löscht oder für Samples braucht, liegt dahinter.

## Aufbau

- **Dateien:** eigene `SYSTEM.VSB` (Hacktribe 2.02) mit dem BLECH-Satz (`apply.mjs --set
  data/patches/blech.json`, sha256 `f4f6ead6...`), eigener Flash-Dump vom 9.10., virtuelle Karte mit
  `KORG/blechtribe/Sample/e2sSample.all` und `KORG/blechtribe/Plugin/e2sPlugin.all` (Klicker oder
  Snake).
- **Die `e2sSample.all`** baut `tools/emu/sampleset.py`. Format (gemessen am Export der Firmware und
  an einer eigenen Datei, nur die Struktur): 16 Byte `e2s sample all`, `0x1A`, `0`; 1020
  Little-Endian-Offsets, einer je Slot (0 = leer), zusammen 4096 Byte Kopf; danach je Sample eine
  RIFF/WAVE-Datei mit `fmt`, `data` und dem Block `korg` (1180 Byte, darin `esli` mit Name, Schleife,
  Rate). Je Sample 1232 Byte plus Audio. Die Firmware lädt die Slots 501 bis 999 (nullbasiert 500 bis
  998), 499 Stück.
- **Speichergröße (gemessen):** Der Zeiger auf den nächsten freien Platz im DSP-Speicher
  (`0xC00F9C80`) steht nach einem Start ohne Samples auf `0x365EC0` (Werksbank). Der Lader legt jedes
  Sample ohne Zwischenraum dahinter. Bis zur Grenze `0x01C65EC0` (aus dem Importer, siehe
  [virtuelle SD](../hintergrund/virtuelle-sd.md)) bleiben **26.214.400 Byte, genau 25 MiB** Audio für
  die Nutzerplätze. Der Zeiger endete in den Läufen mit vollem Speicher auf genau `0x1C65EC0`.
- **Die Wache** (`tools/emu/ramwatch.py`): ein Unicorn-Haken auf jeden Schreibzugriff ins ganze
  Abbild `[0xC0000000, 0xC0200000)` und in seine 64-MiB-Spiegelung. Zu jedem Zugriff kommt der
  Programmzähler des Schreibenden. Ein Zähler im freien Block (`0xC01A2100` bis `0xC0200000`) ist
  eigener Code, jeder andere die Firmware. Als BLECH-Bereich zählt der ganze freie Block (in den
  benannten Teilen unten, auch der unbenutzte Rest) und jedes Wort, das die Patches im Abbild geändert
  haben (aus dem Vergleich der Dateien).
- **Positivkontrolle (gemessen):** Die Wache sieht eigene Schreibzugriffe (390.000 je Lauf, vor allem
  Ring und LED-Zustand) und sie sieht fremde: die Dateifunktionen der Firmware, die der Kartenlader
  von BLECH beim Start aufruft, schreiben 403 Mal in den Dateipuffer und den FIL-Bereich von BLECH, in
  einem Fenster von 20 ms bei 170,6 s Gerätezeit, genau zwischen Haken und Rücksprung des Laders. Das
  sind angeforderte Schreibzugriffe (Ziel ist der Puffer, den BLECH übergibt) und sie stehen in der
  Zeile "angefordert", nicht unter "fremd".

## Die RAM-Karte

Adressen halb offen. "Wache" heißt: gemessen mit dem Haken auf die Schreibzugriffe, "Seiten": Vergleich
der nicht leeren 4-KiB-Seiten nach einem Start ohne Samples mit einem Start mit vollem Speicher, beide
Male nach dem Spielen eines Musters.

| Bereich | Besitzer | Beleg |
|---|---|---|
| `0xC0000000` bis `0xC01A2100` | Firmware: Code, Konstanten, Daten. Von der Firmware beschrieben nur `0xC00F8E00` bis `0xC00F9E00` (Variablen, darunter der DSP-Zeiger `0xC00F9C80`), `0xC013C200` bis `0xC013C600` und ein Wort bei `0xC0170E00`. Dazu die 36 Stellen, die BLECH ändert | Wache, `static_ranges` im Bericht |
| `0xC01A2100` bis `0xC01A3C00` | BLECH: Startbild-Editor, Code | Wache: 0 fremde |
| `0xC01A3C00` bis `0xC01A4A00` | BLECH: Klassentabelle des Startbild-Editors, Zustand, Puffer | Wache: 65 eigene, 0 fremde |
| `0xC01A5000` bis `0xC01A5E20` | BLECH: MFX 2, Code, Zustand, Record | Wache: 1 eigener, 0 fremde |
| `0xC01A6000` bis `0xC01AC158` | BLECH: Plugin-Laufzeit (VM, Haken, Karte, Menü) | Wache: 0 fremde |
| `0xC01ADE00` bis `0xC01ADF48` | BLECH: Kopie der Bildschirmtabelle und der Klassentabelle des Menüs | Wache: 0 fremde |
| `0xC01AE000` bis `0xC01D6B54` | BLECH: Laufzeitzustand, Ring, LED | Wache: 390.000 eigene, 0 fremde |
| `0xC01D6C00` bis `0xC01D7000` | BLECH: Menüeinträge, Menüzustand, Einstellungspuffer | Wache: 136 eigene, 0 fremde |
| `0xC01D7000` bis `0xC01F7000` | BLECH: Plugin-Pool, 128 KiB | Wache: 593 eigene, 0 fremde |
| `0xC01F7000` bis `0xC01F8000` | BLECH: Arbeitsbereich des Kartenladers (FIL, Zustand) | Wache: 9 eigene, 171 angeforderte |
| `0xC01F8000` bis `0xC01FFFF0` | BLECH: Blockpuffer für Dateilesen | Wache: 6 eigene, 232 angeforderte |
| `0xC0200000` bis `0xC08A2940` | Firmware: Task-Stacks, Kernel, Heap. 636 von 1698 Seiten nicht leer ohne Samples, 645 mit vollem Speicher, höchste beschriebene Seite endet bei `0xC06CD000` | Seiten |
| darin neu mit Samples | `0xC034A000` bis `0xC0350000` (24 KiB, nicht benannt), `0xC0364000` bis `0xC0367000` (12 KiB, Wiedergabetabelle `0xC0362EE8 + i * 0x10` für die Plätze 501 bis 999), `0xC06CC000` bis `0xC06CD000` (4 KiB) | Seiten; Tabellen laut [Speicherbereiche](../speicherbereiche.md) |
| `0xC08A2940` bis `0xC08B2940` | Firmware: Globals | alle 16 Seiten nicht leer, in beiden Läufen |
| `0xC08B2940` bis `0xC0C9A940` | Firmware: 250 Pattern-Slots | alle 1000 Seiten nicht leer |
| `0xC0C9A940` bis `0xC0D3A940` | Firmware: Cache der Sample-Infos | eine von 160 Seiten, mit vollem Speicher unverändert |
| `0xC0D3A940` bis `0xC273AA40` | Firmware: Datei- und Sample-Arbeitspuffer, 27,3 MB | ohne Samples 0 von 6656 Seiten nicht leer, mit vollem Speicher 14 Seiten bis `0xC0D48000` (56 KiB, das größte Sample hat 52,5 KB). Alle 499 Schreibaufrufe an den DSP nehmen ihre Quelle ab `0xC0D3A940`, Aufrufer `0xC004EF8C` |
| `0xC273AA40` bis `0xC274AA40` | Firmware: Startstack | 0 Seiten beschrieben |
| `0xC274AA40` bis `0xC274EA3C` | Firmware: Interrupt- und Leerlaufstack | 4 Seiten, in beiden Läufen |
| ab `0xC274F000` bis `0xC8000000` (gemapptes Fenster des Emulators) | im Emulator von nichts benutzt | in keinem Lauf eine Seite beschrieben. Am Gerät zeigt der RAM-Dump hier belegte Seiten unbekannter Herkunft ([RAM-Fenster](2026-10-07-cpu-ram-fenster.md)); das ist hier nicht erklärt, liegt aber hinter BLECH und der 64-MiB-Spiegel ist unten besprochen |
| Sample-Audio | nicht im CPU-RAM, sondern im DSP-Speicher ab Byteoffset `0x365EC0` bis `0x1C65EC0` | alle 499 Schreibaufrufe, zusammen 26.214.400 Byte, höchste Stelle `0x1C65EC0` |

Die Tabellen der Sample-Verwaltung (Wiedergabe ab `0xC0362EE8`, Metadaten ab `0xC036AD88`, Namen ab
`0xC047B080`) liegen alle hinter `0xC0200000`. Selbst bei einem Index außerhalb von 0 bis 999 landeten
Schreibzugriffe dort erst weit hinter dem Abbild (hergeleitet aus den Adressen und den Strides, nicht
ausprobiert). **Offen und nicht BLECHs Sache:** Rechnet man die Metadaten mit Stride `0x45C` für 1000
Plätze durch, überlappen die Einträge ab Platz 985 die Namenstabelle. Im Lauf mit allen 499 Plätzen
blieben die Namen der Plätze 1 bis 40 gleich (verglichen mit dem Start ohne Samples), die Tabellen
liegen also anders, als die einfache Rechnung sagt.

## Die Läufe

Gerätezeit je Lauf 170 bis 420 s (das Laden der 26,8 MB Datei dauert 171 s, rund 157 KB/s). Ein
Lauf besteht aus: Start mit der Datei, dann das jeweils Genannte. Schreibzugriffe sind die ins Abbild.

| Lauf | Inhalt | Schreibzugriffe | fremd in BLECH | angefordert | Spiegel |
|---|---|---|---|---|---|
| full | 499 Plätze, 26.214.400 Byte (ganz voll), Klicker, Tap, Menü, Muster 8 s mit Pads | 728.234 | 0 | 403 | 0 |
| snake | wie full, Snake 150 Rahmen mit den Tasten des Browsermodells, Muster | 1.271.941 | 0 | 1001 | 0 |
| map | wie full, Seitenvergleich mit einem Start ohne Samples | 685.135 | 0 | 403 | 0 |
| sampling | ganz voll, ohne Plugin, SHIFT + REC (SAMPLING), REC, 10 s warten, STOP, EXIT | 358.637 | 0 | 3 | 0 |
| sampling_free | nur 2 MB belegt, sonst wie sampling | 120.101 | 0 | 3 | 0 |
| over | 100.000 Byte mehr als hineinpassen, Klicker | 700.553 | 0 | 403 | 0 |
| import | 200.000 Byte frei (im ersten Lauf 100.000), dann IMPORT SAMPLE von WAVs | 1.126.095 | 0 | 403 | 0 |
| export | ganz voll, EXPORT ALL SAMPLE | 864.795 | 0 | 3 | 0 |

"angefordert" sind Schreibzugriffe der Firmware in den Dateipuffer und den FIL-Bereich von BLECH,
während BLECHs eigener Kartenlader eine Datei öffnet und liest (403 bei Klicker, 1001 bei Snake, dessen
Datei größer ist, 3 beim Öffnen einer fehlenden Datei). Sie liegen alle im Fenster des Laders.

Gemeinsame Prüfungen jedes Laufs (gemessen): Laden fertig ohne Assertion, alle 499 Plätze belegt
(`slots`), DSP-Zeiger genau am Limit, die Audiobytes gehen alle über den DSP-Port, Code und Tabellen
von BLECH gleich der Datei (36 Bereiche, 37.176 Byte).

## Was die Firmware bei voll tut (nicht BLECH, aber gemessen)

- **Zu viel Audio beim Start** (Lauf over, 100.000 Byte mehr als hineinpassen): Der Lader lädt 497 der
  499 Plätze (501 bis 997), der DSP-Zeiger bleibt bei `0x1C64964`, 5468 Byte unter dem Limit, er läuft nie
  darüber. Der Start endet normal, ohne Assertion, aber mit einem **Fenster "Error / Memory Full"** auf
  dem Hauptbildschirm (gemessen ohne Plugin, Lauf window_over). Das Fenster bleibt offen und
  schluckt den TAP, erst EXIT schließt es. Die Plugin-Laufzeit sieht die Tasten trotzdem (Klicker
  zeigte nach dem TAP die Eins). Bei genau vollem Speicher (Lauf window) kommt kein Fenster.
- **SAMPLING (SHIFT + REC) bei vollem Speicher** (Lauf sampling): sofort "Error / Memory Full" (am
  Bild gelesen), REC und STOP ändern bis EXIT nichts, kein neuer Platz, der Zeiger bleibt auf `0x1C65EC0`.
  Mit Platz (Lauf sampling_free) öffnet sich das SAMPLING-Fenster; REC wartet dann auf Audio, das die
  DSP-Attrappe nie liefert (so in einem Vorversuch mit kleinem Satz gesehen, im gespeicherten Lauf nicht
  einzeln geprüft). Eine **Aufnahme, auch RESAMPLING, ist im Emulator deshalb nicht erreichbar**; BLECH
  wurde in beiden Läufen nicht berührt.
- **IMPORT SAMPLE bei fast vollem Speicher** (Lauf import, DATA UTILITY, Seite 9, WAV von der Karte, erster Platz
  wie angeboten): Eine WAV, die nicht mehr passt, ergibt "Error / Memory Full" und lässt den DSP-Zeiger
  unverändert (gemessen dreimal: 200.000 Byte bei 100.000 frei, 300.000 bei 200.000 frei, 120.000 bei
  100.000 frei). Passende WAVs wurden angenommen (50.000 Byte bei 100.000 frei, 100.000 bei 200.000 frei:
  "OK", der Zeiger wächst um genau die Länge). **Offen:** der Fall "passt auf das Byte" (100.000 Byte in
  genau 100.000 frei) wurde im Emulator nicht angenommen, der Importer blieb auf "Working" oder die Tasten
  trafen nach dem vorigen Fehlerfenster nicht mehr den Dateibrowser; der Lauf mit längerer Wartezeit wurde
  nicht abgeschlossen, Ergebnis offen. BLECH sah in allen Importläufen keinen fremden Schreibzugriff.
- **EXPORT ALL SAMPLE bei vollem Speicher** (Lauf export, DATA UTILITY, Seite 11): die Firmware liest den
  ganzen DSP-Speicher über den Arbeitspuffer zurück und schreibt eine Datei von 26.833.330 Byte (die
  Eingabe hatte 26.833.264) auf die Karte, kein fremder Schreibzugriff, kein Assert. **Offen:** Ob die
  Datei vollständig ist (499 Einträge, 26.214.400 Byte Audio), prüft eine neue Zeile im Lauf; dieser Lauf
  war beim Abschluss nicht fertig, Ergebnis offen. Das Audio ist wegen der DSP-Attrappe sowieso nicht
  aussagekräftig.
- **Plugins bei vollem Speicher:** Klicker (Anzeige wie im Browsermodell vor und nach dem TAP, Menü der
  Firmware geht) und Snake (150 Rahmen, Anzeige bitgleich dem Browsermodell) laufen. Ein TAP wirkt nur
  verlässlich, wenn man gut eine Sekunde nach "ready" wartet; die LED 20 (TAP) blinkt die Firmware zum
  Tempo und überschreibt den Wert des Plugins, darum prüft der Test das gesendete LED-Paket.
- **Laden:** 499 Plätze mit 26,8 MB brauchten 171 s Gerätezeit, das sind rund 157 KB/s. Das ist deutlich
  langsamer als die 640 KB/s, die [virtuelle SD](../hintergrund/virtuelle-sd.md) für Sektoren schätzt.

## Die Prüfung

`test/emulator-sample-full.test.mjs` (in `npm run test:emu`, ohne `E2_VSB` übersprungen) baut den
BLECH-Satz aus der eigenen Firmware, lässt `tools/emu/sample_full.py --scenario regression` laufen
(ganz voller Speicher, Klicker, Muster, Menü) und verlangt: alle 499 Plätze belegt, der DSP-Zeiger auf
`0x1C65EC0`, kein fremder Schreibzugriff in einen BLECH-Bereich, keiner über den Spiegel, Code und
Tabellen von BLECH unverändert. Der Lauf dauerte 566 s (171 s Gerätezeit nur fürs Laden) und bestand.

## Grenzen und Offenes

- **Emulator, nicht Gerät.** Der DSP ist eine Attrappe, es gibt keinen DMA und kein Audio. Ob ein
  DMA-Weg am Gerät in den Arbeitspuffer oder anderswohin schreibt, zeigt diese Messung nicht. Dass die
  Firmware die Daten des Samples am Gerät auch durch den Host-Port schickt, ist aus dem
  Importer und dem Export hergeleitet ([DSP-Pfade](2026-10-08-dsp-audiopfade.md)), nicht am Gerät
  beobachtet.
- **Die 64-MiB-Spiegelung** ist im Emulator nicht nachgebildet (der Speicher ist dort 128 MiB
  gemappt). Die Wache sah in keinem Lauf einen Schreibzugriff auf die Adressen `+0x04000000`; schriebe
  die Firmware am Gerät dorthin, träfe es BLECH, aber nichts in der Firmware deutet auf Adressen
  oberhalb `0xC274F000` hin (hergeleitet: die Seitenkarte oben).
- **RESAMPLING als Aufnahme** ist im Emulator nicht erreichbar: ohne Audio vom DSP-Attrappe wartet die
  Aufnahme (siehe oben). Der Weg bis dorthin ist belegt.
- Nur die Belegung mit der Firmware-Version 2.02 mit Hacktribe, nur mit der eigenen Datei.
