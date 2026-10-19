# Blechy: drei Richtungen für Start und Laden

Stand 19.10.2026. Die [Übergabe](uebergabe-2026-10-19.yaml) ist die Grundlage. Noch keine Auswahl und kein
Firmware-Patch. Die [Vergleichsseite](vergleich.html) zeigt alle Richtungen, feste Standbilder und die echte
Auflösung von 128 × 64 Pixeln. Sie nutzt dieselben Farben, Schriften und Bedienelemente wie die App.

## Ansehen

| Richtung | Gestaltung | Abwägung |
|---|---|---|
| [Werkbank](vorschau/neu/werkbank.gif) | BLECH oben, Blechy an der Tischkante. Drei kurze Striche bleiben auf der Unterlage; er folgt ihnen selbst, hebt das Rohr dazwischen ab und setzt wieder an. | Die Handlung ist am deutlichsten, der bewegte Kopf schaltet aber mehr Pixel um. |
| [Typenschild](vorschau/neu/typenschild.gif) | Ganze Originalfigur links, große Marke rechts, feste Fortschrittssegmente und Prozent. Das Rohr bleibt sichtbar in der Hand, abseits des Gesichts. | Die ruhigste Variante. Das Ziehen der Striche entfällt; Augen und Anzeige tragen den Fortschritt. |
| [Prägung](vorschau/neu/praegung.gif) | Blechy über einer festen Kante, große Wortmarke darunter. Der Umriss von BLECH füllt sich ohne Dither. | Der Titel ist selbst die Anzeige. Die Figur steht ruhig; dafür ändern sich größere Teile der Buchstaben. |

### Werkbank

![Werkbank](vorschau/neu/werkbank.gif)

### Typenschild

![Typenschild](vorschau/neu/typenschild.gif)

### Prägung

![Prägung](vorschau/neu/praegung.gif)

### Gemeinsamer Abschied

![Ausschalten](vorschau/neu/ausschalten.gif)

Blechy winkt, „Haus'te / rin mein / Akh“, das Bild zieht sich zur Röhre zusammen und geht aus. Dieselbe helle
Gesichtsfläche auf dunklem Grund wie beim Start. Die eigentliche Folge dauert 1000 ms. Die zusätzlichen 1400 ms
Schwarz am Ende sind nur eine Pause für das wiederholte GIF, keine zusätzliche Wartezeit am Gerät.

## Was sich an der Zeichnung geändert hat

**Blechy bleibt Blechy.** Gesicht, Augenabstand, Augenringe und Braue stammen aus den vorhandenen 56×56-Sprites.
Das Gesicht bleibt hell und die Pupillen dunkel. Eine Lichtkante von einem Pixel trennt den dunklen Körper vom
dunklen Hintergrund. Die Figur wird nicht gestreckt. Die Originaldateien in `assets/blechy/sprites/` werden nicht
verändert. Der Rohrkontakt sitzt am unteren Rand des bestehenden Gesichtsfelds; eine neue vorstehende Nase gibt
es nicht. Das ist ein Vorschlag für diese Bildschirme, keine endgültige Entscheidung für alle Blechy-Sprites.

**Die Hand umschließt das Rohr.** Nasenanker, Rohrspitze und Griffpunkt gehören zu derselben Pose. Der Griff sitzt
bei 63 Prozent der Achse, beide Armstücke sind neun Pixel lang und schließen an der ursprünglichen Schulter an.
Das Rohr hat in jeder Pose denselben Vektor von 12×12 Pixeln, also rund 17 Pixel Länge. Eine dunkle Aussparung
hinter dem hellen Rohr trennt es vom Gesicht. Es gibt kein XOR und damit keine zufälligen Farbwechsel beim
Überlagern. Eine kleine Fingerkerbe macht den Griff sichtbar.

**Die Werkbank bewegt die Figur.** Tisch, Unterlage und alle übrigen Striche stehen still. Verbrauch verschwindet
direkt an der Rohrspitze. Zwischen zwei Strichen hebt nur der Arm das Rohr vom Gesicht und von der Unterlage;
die Figur rückt über die kurze leere Lücke weiter. Der Kopf wandert insgesamt 21 Pixel, ohne die Titelzeilen zu
berühren. Drei Striche geben ihm mehr Platz als die vorige lange Reihe. Die Prozentzahl bleibt rechts unten.

**Start und Laden gehören zusammen.** Anfangs steht TRIBE neben BLECH. LADEN erscheint einmalig nach dem
ersten Stück Fortschritt, ohne schiebende Buchstaben. Bei bestätigtem Abschluss steht LAEUFT. In Werkbank und
Typenschild bleibt die ganze BLECH-Fläche unverändert; bei Prägung bleiben Position und Außenform fest, während
die Innenflächen absichtlich gefüllt werden. Sechs Pupillenstufen bleiben, ohne Zittern.

## Neu erzeugen

Python 3.10 oder neuer und Pillow genügen. Keine macOS-Schrift erforderlich: `blech-titel.png` wird auf allen
Systemen nur gelesen. Die kleinen Schriften kommen weiter aus `render.py` und `data/script/font.mjs`.

```bash
python3 entwuerfe/design-1.3/geraet/anim.py
python3 entwuerfe/design-1.3/geraet/anim.py --direction werkbank
python3 entwuerfe/design-1.3/geraet/anim.py --palette mono --output /tmp/blechy-review
python3 -B entwuerfe/design-1.3/geraet/test_anim.py -v
```

| Ausgabe | Inhalt |
|---|---|
| `vorschau/neu/<name>.gif` | 4×-Vorschau, genau zwei LCD-Farben, ohne Kantenglättung |
| `vorschau/neu/<name>-1x.gif` | Dieselbe Folge in nativen 128×64 Pixeln |
| `vorschau/neu/<name>-strip.png` | Fünf Schlüsselbilder nebeneinander |
| `vorschau/neu/<name>-start.png`, `-mitte.png`, `-ende.png` | LCD-Standbilder für den Vergleich |
| `png/neu/<name>/000.png` und folgende | Alle nativen 1-Bit-Einzelbilder; Schwarz bedeutet sichtbar dunkel |
| `png/neu/<name>-start.png`, `-mitte.png`, `-ende.png` | Native 1-Bit-Schlüsselbilder |
| [manifest.json](vorschau/neu/manifest.json) | Beispielzeiten, Zustände, Bildanzahl und Änderungsumfang |

Die einzelnen Folgeframes und die optionalen BIN-Dateien werden beim Rendern neu erzeugt und nicht versioniert.
GIFs, Ablaufstreifen und Schlüsselbilder liegen direkt im Repo.

Die Vergleichsseite lässt sich direkt als Datei öffnen. Alternativ im Repo `python3 -m http.server 8742`
starten und `http://127.0.0.1:8742/entwuerfe/design-1.3/geraet/vergleich.html` aufrufen. Animation aus zeigt
jeweils ein festes Standbild, keine pausierte GIF-Zeitposition. Bei reduzierter Bewegung startet sie mit Standbildern.

## Echten Fortschritt anschließen

`render_frame(direction, progress, pose=..., travel=..., started=..., done=...)` erzeugt ein neues Pillow-Bild
ohne Uhr, Zufall oder Dateiausgabe. Fortschritt, verbleibendes Material und Pupillen hängen am vom Aufrufer
übergebenen Fortschritt zwischen 0 und 1. `pose` wählt Kontakt, Abheben, Umsetzen oder Ruhe. `travel` bewegt
nur über eine schon leere Lücke zwischen zwei Strichen. Stillstand verbraucht keine weiteren Striche.

Ohne `done=True` erscheint höchstens 99 Prozent und es bleibt Material übrig. Ein Fortschrittssprung braucht
keine nachgeholten Bewegungen. Das Hauptbild darf sofort übernehmen. Die 8,6 Sekunden in `demo_timeline()` sind
ein Beispiel zum Anschauen, kein Ablauf, den die Firmware abwarten müsste. Beim Einbauen muss der Aufrufer bei
Fehler oder Abschluss die Überlagerung freigeben.

### Zwei Bitreihenfolgen und Display-Invert

Mit `--pack` werden zusätzlich drei Schlüsselbilder je Richtung in beiden vertikalen Bitreihenfolgen geschrieben.
Das sind Bilddaten zum Prüfen, keine Firmwaredateien und keine fertigen Patches.

```bash
python3 entwuerfe/design-1.3/geraet/anim.py --pack --controller-inverted
```

| Format | Byte | Bit |
|---|---|---|
| `*-msb.bin`, wie `assets/blechy/splash.bin` | `(y // 8) * 128 + x` | `0x80 >> (y & 7)` |
| `*-lsb.bin`, wie der Anzeigepuffer | `(y // 8) * 128 + x` | `1 << (y & 7)` |

Jedes Bild hat genau 1024 Byte. Der Renderer denkt in sichtbaren Pixeln, der Export rechnet
`RAM-Bit = sichtbar-dunkel XOR controller_inverted`. Bei `DISPLAY INVERT` mit Controllerkommando A7 werden die
Bits deshalb genau einmal komplementiert. Sonst würde der bereits dunkel entworfene Hintergrund wieder hell.
Der Default der vorhandenen Firmware wird durch das Rendern nicht umgestellt.

## Geprüft und noch offen

**Abgeleitet aus den erzeugten Pixeln**, jeweils zwischen unterschiedlichen aufeinanderfolgenden Bildern:

| Entwurf | Einzigartige Bilder | Geänderte Pixel maximal | Geänderte Pixel im Mittel | LCD-Seiten maximal |
|---|---:|---:|---:|---:|
| Voriges `rotzen.gif` | 71 | 600 | 132,04 | 7 |
| Werkbank | 24 | 415 | 263,48 | 7 |
| Typenschild | 17 | 103 | 39,94 | 5 |
| Prägung | 17 | 257 | 101,06 | 7 |

Werkbank hat weniger Posen und längere Standzeiten, bewegt pro Wechsel aber mehr Fläche als der vorige Entwurf.
Typenschild ist nach diesen Zahlen die günstigste Richtung für ein träges LCD. Die normale Demo aktualisiert
frühestens nach 280 ms; diese Taktung ist eine Designannahme. Sie ist keine gemessene Grenze des Geräts.

Die neun Python-Prüfungen sichern native 1-Bit-Frames, feste Titel, wiederholbare Ausgabe, starre Rohr-/Armgeometrie,
Griff auf der Rohr-Achse, Stillstand und Sprünge, beide Bitreihenfolgen samt simulierter Controllerinvertierung
und das 1000-ms-Ausschaltfenster. Die gespeicherten GIF-Bilder wurden außerdem pixelgenau mit dem Renderer
verglichen. Die Vergleichsseite wurde bei 1440 und 390 Pixel Breite, mit Tastatur, Originalmaßstab und reduzierter
Bewegung im Browser angesehen.

**Offen:** welche Richtung gefällt, die endgültige Nasenform, Nachziehen des echten LCDs, ARM-Befehle pro Bild,
Startzeit und Speicherplatz. Die frühere Zahl von ungefähr 6300 ARM-Befehlen pro Bild ist eine
[Messung des vorigen Lade-Patches](../../../docs/messungen/2026-10-15-ladebalken.md), keine Zusage für diese Entwürfe.
Auch die kompakten Bildtabellen im Manifest sind nur Größenabschätzungen ohne Rendercode. Eine vollständige
Bildtabelle von 17 oder 24 KiB passt nicht in das bisherige einzelne 1024-Byte-Bildfeld. Die spätere Firmwarefassung
sollte Grundbild, Pupillen und wenige Arm-/Kopfposen gezielt zusammensetzen und im Emulator gemessen werden.

Für die Designarbeit fehlt aus der Übergabe nichts. Eigene Firmware und Hardwaremessungen sind erst für diesen
nächsten Integrationsschritt erforderlich.
