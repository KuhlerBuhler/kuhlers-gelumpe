# Die PCM-Bank der blauen Electribe 2 aus WAV-Dateien nachgebaut

Stand 2026-10-15. Im Emulator, kein Gerät. Eingabe: die `SYSTEM.VSB` 2.02 der blauen Electribe 2 (Synth) und eine Zip-Datei mit
408 WAV-Dateien in Kategorie-Ordnern (kick, snare, instrument und so weiter, eine Datei je Oszillator, der Dateiname beginnt mit
der Nummer). Beides sind Korg-Daten und liegen nicht im Repository, die Zip wird an Ort und Stelle gelesen und das Image
außerhalb des Repositorys geschrieben (das Werkzeug lehnt einen Pfad darin ab). Hier stehen nur Zahlen und Aufbau. Markierungen:
**gemessen** (im Emulator ausgeführt), **hergeleitet**, **nicht ableitbar**. Aufbau von Bank und Tabellen:
[Samples auf der blauen Electribe 2](2026-10-15-synth-samples.md).

Das Werkzeug ist `tools/emu/synth_pcm_flash.py`, die Tests ohne Korg-Daten stehen in `tools/emu/test_synth_pcm_flash.py`:

```bash
tools/emu/.venv/bin/python tools/emu/synth_pcm_flash.py --zip SAMPLES.zip --vsb SYSTEM.VSB [--out FILE] [--strict] [--no-verify]
```

Es baut ein 16-MiB-Flash-Image: die PCM-Bank bei `0x800000` im Format, das die Firmware beim Start liest, und die Kennung
`KORGelec2USR` bei `0x220000`, die die Firmware des Synths prüft. Danach bootet es die blaue Firmware auf diesem Image und
vergleicht, was sie liest und an den DSP schickt (Abschnitt "Prüfung").

## Kurzfassung

1. **Das Format lässt sich aus den WAVs allein aufbauen, mit drei Einschränkungen**: Schleifen, Wurzeltasten und Tastenzonen
   stehen in diesen Dateien nicht (kein `smpl`-Abschnitt), die Pegel sind neu gesetzt, und die Wellen passen im Rohblock-Format
   nicht ganz in 8 MiB (unten).
2. **Die Firmware nimmt die Bank an** (gemessen): die PCM-Ladung endet mit Erfolg (`r6` ist 1) bei 4899 ms Gerätezeit, das Hauptbild
   steht bei 5100 ms, keine Assertion.
3. **Alle 361 PCM-Oszillatoren zeigen auf die richtige Welle** (gemessen): über die Tabelle der Firmware im RAM, die Kette der
   Tabellen bis zur DSP-Adresse, und die Bytes dort im DSP-Speicher sind die der Datei.
4. **Der DSP-Transfer ist unauffällig** (gemessen): 85 Übertragungen, eine zusammenhängende Strecke von `0x365AE0` bis `0xE03E60`
   (11.133.824 Byte), bitgleich mit den Werten, die aus den WAVs gemacht sind, nichts unterhalb des Wellenanfangs, die Grenze
   der Sampler-Bank (`0x133F5C0`) wird nicht erreicht.

## Was aus den WAVs kommt und was nicht

| Wert | Quelle | Status |
|---|---|---|
| Welche Datei zu welchem Oszillator gehört | die Nummer im Dateinamen ist die 1-basige Stelle in der Oszillator-Tabelle der Firmware, der Name stimmt in allen 361 Fällen mit dem Eintrag überein | gemessen |
| Instrument eines Oszillators | Wellen-Nummer des Eintrags minus `0x32`. Einträge mit kleinerer Nummer erzeugt der DSP selbst: 47 der 408 Dateien (Gruppe Synth) gehören dazu und kommen nicht in die Bank | gemessen |
| Eine Lücke: Wellen-Nummer 100 (Instrument 50) wird von keinem Eintrag benutzt | stilles Füll-Instrument von 32 Werten, damit die Nummern stimmen | hergeleitet |
| Rate | 44100 Hz in allen Dateien. Die Firmware addiert beim Laden 375 zum Tonhöhenwort (der Abstand von 44,1 zu 48 kHz), das Wort in RAM ist `0x4977` bei Wort `0x4800` in der Bank | gemessen |
| Bitbreite | die WAVs sind 24 Bit, die Bank hat 12-Bit-Werte. Eine gemeinsame Verstärkung für alle Wellen: der lauteste Spitzenwert (`0x24DDFC`) wird 2047, die Pegel zwischen den Wellen bleiben, gerundet | Entscheidung, leisere Wellen verlieren Auflösung |
| Anfang und Ende | Länge der Datei, Nullen am Ende abgeschnitten (mindestens 32 Werte bleiben) | hergeleitet |
| Schleife | **nicht ableitbar**: die Dateien tragen keine. Jede Welle ist ein One-Shot in der Form der Firmware selbst (Schleifenanfang gleich Ende, Bit 16 im Schalterwort). Gehaltene Klänge (Streicher, Orgeln) enden also | nicht ableitbar |
| Wurzeltaste | **nicht ableitbar**: Tonhöhenwort `0x4800`, wie die Werksdaten es zeigen. Ob das die Taste ist, bei der die Wellen in der Bank der blauen liegen, ist nicht gemessen | nicht ableitbar |
| Tastenzonen und Anschlagstärke | **nicht ableitbar**: eine Zone über die ganze Tastatur, größte Anschlagstärke 127, Pegelwort `0x8000` (1,0) | nicht ableitbar |
| Stereo-Instrumente der Bank | nicht untersucht, alle Dateien sind mono | offen |

## Platz: warum Wellen gekürzt werden

Im Rohblock-Format (Modus 7, 12 Bit je Wert, das einzige, das dieses Repository schreibt) brauchen die 361 Wellen mit allen
Nullen am Ende 8.458.713 Byte, die Bank hat 8.388.608 Byte und braucht für Köpfe und Tabellen (72 Byte je Instrument) noch rund 27 KB.
Auch ohne Nullen am Ende fehlen rund 51.000 Werte. Die Werksbank packt in den Modi 0 bis 4, deren Kodierer hier nicht liegt.
Darum kürzt das Werkzeug die längsten Wellen (länger als 60000 Werte) am Ende, mit einer Blende über 1024 Werte, anteilig und nur so
viel wie nötig (`--strict` bricht stattdessen ab). Betroffen sind sieben Wellen, zusammen 72.286 von 5.639.142 Werten (1,3 Prozent):

| Instrument | Name | Werte | gekürzt um |
|---:|---|---:|---:|
| 17 | AttackEight | 112255 | 13728 |
| 18 | PureEight | 88375 | 10808 |
| 111 | Blast | 85094 | 10407 |
| 150 | JazzOpen | 82383 | 10075 |
| 179 | JazzRide1 | 67349 | 8237 |
| 295 | SynGrowl | 76067 | 9303 |
| 299 | StringsHit2 | 79567 | 9728 |

Mit einem Kodierer für die gepackten Modi bräuchte es das nicht. Das ist offen, solange der Kodierer fehlt.

## Prüfung (gemessen im Emulator)

Ein Lauf des Werkzeugs bootet die blaue Firmware auf dem Image und liest, was sie tut:

| Prüfung | Ergebnis |
|---|---|
| PCM-Ladung | erreicht, `r6` 1 (Bank angenommen), bei 4899 ms; Hauptbild bei 5100 ms; keine Assertion |
| Flash-Lesen | 16 Lesevorgänge, 12.488.992 Byte, der erste bei 66,8 ms |
| Tabellen im RAM | 362 Instrumente, 362 mal `MSPR`, `MSRL`, `SMPR`, 1 `DRMP` |
| DSP-Speicher | eine Strecke `0x365AE0` bis `0xE03E60`, 11.133.824 Byte, gleich den erwarteten Bytes (Werte mal 16 als 16-Bit-Wörter), nichts darunter |
| Oszillatoren | alle 361 PCM-Einträge der Tabelle im RAM: Kette Instrument, Zone, Lage, Sample gelesen, Ende gleich Länge der Welle, Tonhöhenwort gleich `0x4977`, die ersten 64 und letzten 32 Byte im DSP-Speicher gleich der Welle; 0 Abweichungen |
| Stimmen über das Bedienfeld | drei Oszillatoren gewählt und ein Pad gedrückt (Nummer 325 Oldie, 311 BrassHit2, 400 E.Guitar1): die Firmware schickt an den DSP die erwartete Wellen-Nummer, als Start die Adresse aus der Kette, und dort liegt die Welle; Schleifenlänge 0 |

Nicht geprüft werden kann im Emulator, ob der DSP die Wellen so spielt (er hat keinen DSP-Speicher und keinen Klang), und wie die Töne
klingen. Ein erster Lauf hatte alle Oszillatoren als falsch gemeldet: das war ein Fehler der Prüfung (die Startadresse in der `SMPR`-Zeile
im RAM ist schon die DSP-Adresse, sie enthält den Wellenanfang `0x365B00`), nicht der Bank. Die Prüfung rechnet seitdem so.

## Entscheidungen, die ohne Rückfrage fielen

1. Eine gemeinsame Verstärkung statt eines Pegels je Welle. Der Weg über das Pegelwort der Zone (`0x8000` ist 1,0, nach oben begrenzt) ginge nur
   abschwächend und ist nicht gemessen.
2. Kürzen der längsten Wellen statt Weglassen ganzer Wellen: so bleibt jeder Oszillator belegt.
3. Rate 44100 Hz, keine Umrechnung: die Firmware gleicht die Rate über das Tonhöhenwort aus.
4. Ablageort des Images außerhalb des Repositorys, Vorgabe der Ordner `electribe-flash` auf dem Schreibtisch, Dateiname `blue-pcm-from-wavs.bin`.
