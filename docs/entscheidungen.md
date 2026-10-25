# Entscheidungen

Was entschieden ist und warum. Gilt, bis hier etwas anderes steht.

## Projekt

| Frage | Entscheidung |
|---|---|
| Name | **Kuhler's GELUMPE**: Grafischer Electribe-Leser und -Modifizierer plus Emulator. Kuhler kommt vom Künstlernamen Kuhler_Buhler. Repo und Paket heißen `kuhlers-gelumpe`. |
| Lizenz | AGPL-3.0, passend zu hacktribe-editor und Hacktribe selbst. Herkunft der Teile: [NOTICE](../NOTICE). |
| Korg-Daten | Keine im Repo, nie: keine Firmware, keine Werks-Patterns, keine Samples, auch nicht als Testdaten. Tests bauen ihre Daten selbst. |
| Firmware-Stand | Alles ist an Firmware 2.02 mit Hacktribe gemessen. Ein unbekannter Stand heißt: nur lesen. |
| Unbekannte Felder | Expertenmodus hinter einem Schalter, Änderungen gehen zuerst den flüchtigsten Weg ([Gerätekarte](geraetekarte.md)). |
| Pattern-Parser | Aus Electribe Studio übernommen, soweit er passt (Container-Werte, Hülle der Einzelpattern-Datei, nur geänderte Felder über die Originalbytes schreiben). Die festen Feld-Konstanten ersetzt die Karte. |
| Sprache der Oberfläche | Klartext und echte Einheiten, keine Bytes. |
| Design | Eigenes Design in `site/design/`, unter AGPL veröffentlicht. Der Editor bekommt keine Design-System-Seite. |
| Eigene Patterns und Dateien | Der Editor hat keinen eigenständigen Datei- oder Pattern-Editor. Patterns kommen über die Karte in die Firmware und werden an der emulierten Electribe bedient. Parser und Datenprüfungen bleiben im Kern. |
| Pattern-Werkzeuge | Die Seite Pattern-Werkzeuge ist kein Pattern-Editor: sie erzeugt aus vorhandenen Patterns Übergänge und gewürfelte Parts und gibt sie als Datei, als Kopie einer Sicherung oder durch Türsteher und Bestätigung ans Gerät. Sie liest dafür eine Sicherung oder Einzeldatei, die der Nutzer auswählt, und verändert sie nie ([Seite](set/pattern-werkzeuge.md)). Der Bereich Patterns bleibt aus der Navigation. |

## Navigation

| Frage | Entscheidung |
|---|---|
| Pattern-Werkzeuge und Samples | Beide Seiten stehen nicht in der Navigation und sind auch über `#ptools` und `#samples` nicht zu erreichen. Code und Tests bleiben. Nur mit `?labs` an der Adresse erscheinen die Tabs wieder, so laufen die Browser-Tests. Warum: Übergänge braucht der Editor vorerst nicht, und das Würfeln soll in die Firmware ([Idee 29](ideen/29-wuerfeln.md)). Samples umbenennen und stimmen taugt erst etwas, wenn gemessen ist, ob es dauerhaft bleibt. |
| Sichtbare Seiten | Start, Emulator, Patcher, Presets, Modulationen, Plugins, Rettung. |

## Release und App

| Frage | Entscheidung |
|---|---|
| Erste Version | 1.0.0 |
| Release-Ablauf | `npm run release` zählt die Version hoch, legt Tag und Release an, lädt die Dateien hoch und löscht ältere Releases ([Entwicklung](development.md#release)). |
| Update | Der Knopf "Neue Version verfügbar" lädt die passende Datei in den Downloads-Ordner und startet die Installation (`src-tauri/src/update.rs`). Die App ersetzt sich nicht selbst im Hintergrund, das bräuchte einen eigenen Signaturschlüssel. |
| App-Icon | Das Startbild BLECH mit einem G und den Augen. |
| Signierung | Die Apps sind nicht signiert, das steht in der README. |
| Patches | `data/patches/` und `tools/patch/` sind öffentlich und bleiben im Repo. |

## Firmware und Patches

| Frage | Entscheidung |
|---|---|
| Umbenennung `hacktribe` zu `blechtribe` | Als Patch gebaut. Die Karte zieht mit um, der Emulator hat dafür einen Knopf. |
| Startbild-Editor | Wird mit dem aktuellen MFX-2-Stand gebaut. |
| Gate Arp allein | Mit dem Patch nur noch mit EXIT beim Start erreichbar. GATE ARP allein soll sich wie GATE ARP plus TOUCH SCALE verhalten. |
| Regler beim Einschalten | Sie bleiben in der Aus-Stellung, bis einer gedreht wird. Der Regler bestimmt den Wert, nicht umgekehrt. |
| Rand der Pads | Bei leuchtendem Pad nimmt der Rand die LED-Farbe an. |
| Patterns laden | Die `.e2sallpat` liegt auf der Karte, im Emulator geht IMPORT ALL PATTERN. Die Seite legt die Datei nicht auf die Karte. |
| LEDs im Modus "Echtes Gerät" | Ihr Zustand im RAM wird gesucht ([Messung](messungen/2026-10-14-led-zustand-ram.md)). |

## Plugins

| Frage | Entscheidung |
|---|---|
| Weg aufs Gerät | Plugins werden von der Karte geladen, mit Import und Export in eine `.all`-Datei. Nicht in die VSB. Wer vor dem Sample-Laden laufen muss, läuft erst beim nächsten Start. |
| Ordner auf der Karte | `KORG/blechtribe/Plugin/` neben `Sample` |
| Dateiendung | `.blech` für eigene Plugins |
| Grenzen | Kein Limit für die Zahl der Plugins, 128 KiB Gesamtgröße |
| Fremde Plugins | Beim ersten Laden am Gerät einmalig bestätigen |
| Dauerhafte Werte | Pro Plugin über den Plugin-Namen getrennt |
| Terminal | Bleibt, soll Plugins auch ausführen können (Pfad angeben) |
| Gerätetest | Dateien lesen und schreiben werden vor dem Bau am Gerät getestet ([Gerätetests](geraetetests/README.md)) |
| Patches als Plugins | Nicht vorgezogen. Die Sprache wird erst vollständig umgesetzt. |

Siehe [Plugins](plugins.md).
