# Ladebalken im Startbild (Idee 41): gebaut und im Emulator geprüft

Stand 2026-10-15. Alles im Emulator (`tools/emu`, Unicorn 2.1.4) mit der eigenen `SYSTEM.VSB`
(Hacktribe 2.02), Code offline mit Capstone gelesen. Karte: eine virtuelle mit einer
`e2sSample.all` aus `tools/emu/sampleset.py` (20 Samples, 392 304 Byte, eigene Testdaten, kein Korg-Material).
**Am Gerät nichts geprüft.** Idee: [Idee 41](../ideen/41-startbild-ausbauen.md). Markierungen:
**gemessen**, **offline**, **hergeleitet**, **offen**.

## Was beim Laden passiert (Firmware ohne Patch)

| Emulator-ms | Was |
|---:|---|
| 52 bis 73 | Startbild gezeichnet (die Firmware früh, der Startbild-Editor nach den Rettungswegen) |
| 75,6 | der Start fragt, ob `e2sSample.all` da ist (`0xC0035440` über `0xC002AE60`), das mountet die Karte; das Ergebnis wird nicht gebraucht |
| 146 | der Bildschirm-Verwalter steht (Bildschirm 0) |
| 170, 318, 346 | der Befehlsausführer (`0xC002D684` über `0xC002D840`) führt drei Befehle aus: zwei andere und als dritten den Sample-Lader (`0xC0038D34`, ruft `0xC00364F0`) |
| 222 | die Oberfläche zeichnet zum ersten Mal und löscht das Display: das Startbild ist weg |
| 352 | das Fenster "Loading nnn%" (Fensterart `0x1A`) erscheint, die Anzeige ändert sich nach jedem Sample |
| 1504 | der Lader ist fertig, 1523 schließt das Fenster, 1528 kommt der Hauptbildschirm |

**Offline:** der Lader `0xC00364F0` öffnet die Datei, liest 4096 Byte Kopf, sucht den größten Offset (`r7`)
und setzt je Sample den Text "Loading nn%" über `0xC002D8EC`, mit `Prozent = Offset * 100 / größter Offset`.
Das Produkt läuft über 32 Bit, sobald ein Offset über etwa 42 MB liegt: dann stimmt die Prozentzahl der
Firmware nicht mehr (der Balken hier rechnet mit herunterskalierten Werten und ist davon nicht betroffen).

Die Anzeige läuft über einen Bildspeicher bei `0xC031B310` (1024 Byte, acht Seiten zu 128 Spalten, Bit 0 ist die
oberste Zeile einer Seite; eine zweite Kopie bei `0xC031B710`). **Gemessen:** schreibt man ein Muster hinein und
ruft `0xC001531C(0, 0, 128, 64)` ("Bereich geändert"), zeigt das Display es und behält es. Gesendet werden nur
die als geändert gemeldeten Seiten (`0xC0015FA0`).

## Was gebaut ist

Der Patch `data/patches/load-bar.json`, erzeugt von `tools/patch/load_bar.py` (1228 Byte Code ab `0xC0181000`,
Bild und Zustand dahinter, nur RAM). Vier Haken, alle im Start, alle hinter den Rettungswegen:

| Haken | Stelle | Wirkung |
|---|---|---|
| Frage nach der Datei | der Aufruf `0xC0035440` bei `0xC002AE60`, im Start-Task, nur auf dem normalen Weg | merkt "es kommt ein Laden", wenn die Datei da ist und EXIT beim Einschalten nicht gehalten wurde |
| Lader | der Aufruf bei `0xC0038D60` | merkt, dass der Lader fertig ist |
| Textupdate | der Aufruf `0xC002D8EC` bei `0xC00366D4` in der Schleife des Laders | merkt den Dateioffset (`r4`) und den größten (`r7`); lässt das Update weg, solange die Überlagerung zeichnet |
| Rahmen | der Sprung `0xC0015DD0` am Ende der Rahmenfunktion, `0xC008370C` | legt Bild, Balken und Augen über den Bildspeicher, bevor der Rahmen rausgeht |

Der Balken ist der Strich unter BLECH (Zeilen 61 und 62, x 20 bis 107): ungefüllt gepunktet (jeder zweite
Pixel), gefüllt durchgezogen, mit 100 Prozent gleich dem Bild der VSB. Die Augen (Pupillen 3 mal 3 Pixel bei
x 50 und 77, Zeile 15) wandern in 24 Schritten, einer alle vier Rahmen, 5 Pixel nach rechts und wieder zurück, nach
links und zurück. Das BLECH-Bild wird an der CRC-32 erkannt (`assets/blechy/splash.bin`); jedes andere Bild, etwa
ein gezeichnetes, bleibt stehen und bekommt eine einzelne Pixelzeile ganz unten als Balken, keine Augen.

**Gesichter (Stand 15.10., später):** beim BLECH-Bild blendet je ein kleines Gesicht (8 mal 9 Pixel, dunkel auf dem hellen Rand, eigene
Zeichnung in `tools/patch/load_bar.py:FACE`) am Rand ein und aus. Ein Zyklus sind 16 Schritte zu 4 Rahmen (64 Rahmen, rund drei
Sekunden): Stufe 0 0 0 4 8 12 16 16 16 16 12 8 4 0 0 0 von 16, das Einblenden ist ein geordnetes 4-mal-4-Raster (Bayer), bei Stufe n
werden die Pixel mit einem Schwellwert unter n gezeichnet. Je Zyklus sitzt das Gesicht an einem anderen von vier Plätzen
(links oben, rechts unten, rechts oben, links unten; x 2 oder 118, y 10 oder 38), alle in den glatten Rändern des Bildes (x 0 bis 13
und 114 bis 127), weder auf dem Schriftzug noch auf dem blassen Kuhler's. Zustand: `S_FACE` (Platz mal 256 plus Stufe, zuletzt
markiert) und `S_FACE_NOW` bei `STATE + 36` und `+ 40`, innerhalb der schon erklärten 64 Byte, also kein neuer RAM. Wie die
Pupillen wird nur markiert, was sich ändert (das Gesicht beim alten und beim neuen Platz). Bild: `docs/images/blech-ladebalken-gesicht.png`
(`loadbar_cases.py shots`, ein Rahmen mit einem Gesicht auf voller Stufe, 5fach vergrößert).

Die Überlagerung beginnt mit dem ersten Rahmen der Oberfläche und endet mit dem Hauptbildschirm (oder nach 8000
Rahmen, rund sechs Minuten, falls er nie kommt). Ohne Karte, ohne `e2sSample.all`, mit EXIT beim Einschalten und
auf jedem Rettungsweg (Panel-Update, Startmodi) wird nie ein Laden erwartet und alle Haken geben die Firmware zurück.
Ein Schalter im Menü ist nicht vorgesehen.

## Zeit: die erste Fassung hat den Start um 59 Prozent verlängert

Der Auftrag war, dass der Start nicht länger dauert. Gemessen als Gerätezeit bis zum Hauptbildschirm (Abtastung
alle 5 ms, gleiche Karte, gleiche Datei):

| Fassung | Hauptbildschirm | gegen unveränderte Firmware |
|---|---:|---:|
| unverändert | 1518,6 ms | |
| Bild je Rahmen mit der Zeichenroutine der Firmware | 2418,5 ms | +59 % |
| ebenso, nur jeden zweiten Rahmen gesendet | 1858,0 ms | +22 % |
| jeden vierten | 1673,0 ms | +10 % |
| jeden achten | 1587,8 ms | +4,6 % |
| jeden sechzehnten | 1548,6 ms | +2,0 % |
| Bildspeicher direkt, alles als geändert gemeldet | 1524,5 ms | +0,4 % |
| Bildspeicher direkt, nur Geändertes gemeldet (gebaut) | 1518,5 ms | 0,0 % |

Warum: die Zeichenroutine der Firmware für ein ganzes Bild (`0xC003F650`) braucht **2 503 273 Befehle** (gemessen,
etwa 12,5 ms bei 5 ns je Befehl), ein einzelner Pixel (`0xC0015824`) 403, die Bereichsmeldung `0xC001531C` 329. Der
Lader läuft in einer anderen Task, die Oberfläche bremst ihn (hergeleitet aus den Zahlen oben). Die gebaute Fassung
braucht je Rahmen rund **6300 Befehle** eigenen Codes (38 Rahmen, gezählt) und meldet nur die Seiten als geändert, deren Inhalt sich
wirklich ändert (Balkenstück, Pupillen). Der Lader selbst läuft in der Prüfung `loadbar:loader_is_no_slower` 1156,6 ms
mit gegen 1159,8 ms ohne den Patch (EXIT beim Einschalten), der Hauptbildschirm kommt bei 1484,6 gegen 1495,5 ms.

## Auf Korgs Original (Prüfung gegen die Kopie ohne Überlagerung)

Auf Korgs Build ließ der Prüfstand die ersten 300 Millisekunden (ohne Karte sechs Sekunden) von Korgs eigenem Laden der
Benutzerdaten ungesehen ablaufen (`Machine.finish_boot`), und die Prüfungen verglichen mit einem Lauf, in dem EXIT beim
Einschalten den ganzen Satz abschaltet. Drei Prüfungen schlugen deshalb dort fehl, ohne dass der Patch sich auf Korgs Build
anders verhält als auf Hacktribe (gemessen, beide Builds):

| Beobachtung | Wert |
|---|---|
| Überlagerung allein (nur `load-bar.json`), Lader gegen EXIT | Korg 1151,4 gegen 1154,9 ms, Hacktribe 1156,2 gegen 1158,3 ms; Hauptbildschirm 10 ms früher |
| Satz BLECH, Lader mit gegen ohne die vier Aufrufe der Überlagerung (gleiche Kopie) | Korg 1159,2 gegen 1159,7 ms, Hacktribe 1158,2 gegen 1156,8 ms |
| Satz BLECH, Hauptbildschirm mit gegen ohne Überlagerung | Korg 1524,9 gegen 1524,0 ms, Hacktribe 1524,8 gegen 1525,0 ms |
| Satz BLECH gegen EXIT beim Einschalten | Hauptbildschirm rund 40 ms später auf beiden Builds, Lader auf Korg 6 ms länger |

Die 40 ms und die 6 ms kommen also vom übrigen Satz (hergeleitet: er startet später, und mit EXIT beginnt der Lader schon
9 ms später), nicht von der Überlagerung. Die Prüfungen vergleichen darum mit der Kopie, in der die vier Aufrufe der
Überlagerung zurückgesetzt sind (`without_overlay` in `loadbar_cases.py`), und schauen auf Korgs Build ab dem Einschalten.
Ohne Karte zeigt Korgs Build sein eigenes Ladefenster über dem Startbild; dort gilt nicht "nur das Startbild", sondern
`loadbar:no_card_draws_nothing`: jede Abtastung gleicht der der Kopie ohne Überlagerung. Das Gesicht im Rahmen, in dem die
Firmware ihr Fenster schließt, zählt wie die Rahmenprüfung nicht mit.

## Gemessen (Prüfungen `loadbar:*` in `check.py`, `tools/emu/loadbar_cases.py`)

| Fall | Ergebnis |
|---|---|
| Rahmen | 132 Abtastungen (alle 10 ms) ab 160 ms, ab 201 ms ist jede genau das Startbild mit dem Balken und den Pupillen, die der Zustand nennt; **keine** zeigt das Fenster |
| Balken | wächst von 0 auf 88 von 88 Pixeln, nie zurück |
| Augen | sechs verschiedene Stellungen zwischen 0 und 5 Pixeln |
| Gesichter | die Stufen 0, 4, 8, 12 und 16 kommen vor, 87 Abtastungen mit einem Gesicht, die äußeren zwei Spalten bleiben die des Bildes; die Pixel stimmen mit dem Modell überein (Teil der Rahmenprüfung); anderes Bild: keine Gesichter |
| Hauptbildschirm | 300 ms danach gleicht das Display dem des Laufs mit EXIT beim Einschalten, die Überlagerung ist vorbei |
| Fenster der Firmware | mit EXIT beim Einschalten zeigt das Display das Fenster, die Überlagerung ist es also, die es deckt |
| ohne Karte, mit EXIT, ohne Datei | nie erwartet, die Hauptbildschirmzeit gleich der Referenz, ohne Karte sind die ersten 32 Abtastungen gleich denen des Laufs mit EXIT |
| Rettungswege | Panel-Update, Startmodus 1, 8 und 11 mit Karte und Datei: nie erwartet, keine Rahmen gezählt |
| anderes Bild | jede Abtastung ist das Bild mit einer Zeile von 0 bis 128 Pixeln unten, keine Augen |
| `check.py` auf der Kopie | alle Prüfungen der Startwege bestehen |

Das Display folgt dem Zustand um bis zu einen Rahmen (die Seiten gehen mit dem nächsten Senden raus), die
Prüfung lässt darum die letzten drei Zustände gelten, Seite für Seite (die Seiten gehen nacheinander raus, ein Blick mitten
in der Übertragung sieht manche neu und manche alt; im Satz BLECH mit dem Menü v14 kam das einmal vor). Im Rahmen, in dem die Firmware ihr Fenster schließt (etwa
60 ms vor dem Hauptbildschirm), zeigt das Display kurz ihren eigenen Inhalt.

## Grenzen und offen

- **Am Gerät nichts geprüft:** die Adresse des Bildspeichers ist aus dem Pixelbefehl der Firmware gelesen und im Emulator
  bestätigt, am Gerät ist es dieselbe Firmware; ob die Software-PWM oder das Netzteil etwas daran ändern, ist nicht gemessen.
- Die Zeitangaben sind Emulatorzeit (angenommen 5 ns je Befehl, `NS_PER_INSN`), auf etwa Faktor 2 genau; die
  Verhältnisse stimmen eher als die Millisekunden. Am Gerät läuft der SD-Zugriff mit dem Takt der Karte, nicht mit
  dem Zählen von Befehlen.
- Das Auslassen des Textupdates ist am Gerät ungeprüft. Es verändert nur den Text eines Fensters, das nie zu sehen ist.
- Ein Bild, das der Nutzer gezeichnet hat und das zufällig die CRC des BLECH-Bildes hat, bekäme die Augen; unrealistisch.
