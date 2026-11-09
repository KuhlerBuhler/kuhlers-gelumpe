# Rettung: dieselbe SYSTEM.VSB in allen drei Ordnern

Stand 2026-11-08. Probe im Emulator, **am Gerät nichts**. Frage: Die Seite [Rettung](../rettung.md) sagt bei "Weiß ich nicht"
(was läuft), man soll die `SYSTEM.VSB` in alle drei Ordner legen, das schade nicht, die Electribe lese nur den Ordner der Firmware,
die läuft (`rescue.say.cardAll`, Knoten `folder:all:*` in `data/rescue.mjs`). Stimmt das für jede Firmware, die laufen kann?

Eingaben, alle außerhalb des Repositorys: Korgs rote 2.02 (`1d0f0689`), Korgs blaue 2.02 (`41fc5f1c`), Hacktribe 2.02 (`7cb4825c`),
daraus BLECH aus `data/patches/blech.json` auf Hacktribe und auf Korgs roter, und BLECH aus `data/patches/blech-synth.json` auf
Korgs blauer. Jede Firmware startet von einem leeren Flash ihrer Farbe (`machine.hardware_flash`), auf Netzteil.

Marker: **gemessen** (im Emulator ausgeführt, Befehl unten), **hergeleitet** (aus Code oder Messung geschlossen, nicht laufen
gesehen), **offen** (geht nur am Gerät oder ist nicht geprüft).

## Kurzfassung

1. **Der Satz stimmt für DATA UTILITY, SOFTWARE UPDATE.** Alle acht Firmwares öffnen beim Update nur Dateien im Ordner der laufenden
   Firmware. Liegt dieselbe Datei zusätzlich in den beiden anderen Ordnern, schreibt das Update Byte für Byte dasselbe wie mit der
   Datei nur im eigenen Ordner. Liegt sie nur in den anderen Ordnern, kommt "Error / No File" und nichts wird geschrieben. (gemessen)
2. **Die Kopien schaden beim Einschalten nicht.** Mit der Datei in allen drei Ordnern startet jede Firmware bis zum Hauptbild, öffnet
   dabei keine `.VSB` und gibt keinen Lösch- oder Schreibbefehl. (gemessen)
3. **Ob das Update schreibt, entscheidet weiter der Kopf der Datei**, nicht die Kopien: Hacktribe und BLECH mit Hacktribe auf der
   blauen sagen zu Korgs unveränderter blauer "Error / Invalid File", Korgs blaue und BLECHs Synth-Satz zur blauen mit Sampler-Kopf
   ebenso. Geschrieben wird dann nichts. (gemessen)
4. Die Abfrage beim Einschalten (Fall 2 der Rettung) folgt der Kennung im Flash und sucht in Korgs Ordner; dafür ist die Kopie in
   Korgs Ordner nötig, die anderen beiden stören nicht. (hergeleitet aus der zweiten Tabelle in [Rettung](../rettung.md), hier nicht
   neu gemessen)

**Urteil:** Der Text kann so bleiben. Genauer wäre "beim Update liest sie nur den Ordner der Firmware, die läuft", weil BLECH beim
Start auch Einstellungen und Plugins aus `KORG/blechtribe/` liest, nur keine `.VSB`.

## Ergebnis je Firmware

Spalten: was die Firmware mit leerer Karte bei SOFTWARE UPDATE zu öffnen versucht, welche Datei auf der Karte lag, ob sie geschrieben
wurde (512 Löschbefehle zu 4 KiB, 8192 Seiten, danach steht im Firmwarebereich `[0x20000, 0x220000)` die Datei, der Rest des Flashs
gleich), ob "alle drei Ordner" denselben Flash ergibt wie "nur der eigene", und was "nur die anderen Ordner" zeigt.

| Läuft (Farbe) | Öffnet beim Update | Datei | Geschrieben | Alle = nur eigener | Nur andere Ordner |
|---|---|---|---|---|---|
| Korgs Original (rot) | `KORG/electribe sampler/System/` BOOT, USER, PCM, SLICE, SYSTEM | Korgs rote | ja | ja | No File, nichts geschrieben |
| | | BLECH (Sampler-Kopf) | ja | ja | No File, nichts geschrieben |
| Hacktribe (rot) | `KORG/hacktribe/System/` dieselben fünf | Korgs rote | ja | ja | No File, nichts geschrieben |
| | | BLECH (Sampler-Kopf) | ja | ja | No File, nichts geschrieben |
| BLECH mit Hacktribe (rot) | `KORG/blechtribe/System/` dieselben fünf | Korgs rote | ja | ja | No File, nichts geschrieben |
| | | BLECH (Sampler-Kopf) | ja | ja | No File, nichts geschrieben |
| BLECH auf Korgs roter | `KORG/blechtribe/System/` dieselben fünf | Korgs rote | ja | ja | No File, nichts geschrieben |
| | | BLECH (Sampler-Kopf) | ja | ja | No File, nichts geschrieben |
| Korgs Original (blau) | `KORG/electribe/System/` BOOT, USER, PCM, SYSTEM | Korgs blaue | ja | ja | No File, nichts geschrieben |
| | | Korgs blaue mit Sampler-Kopf | nein, Invalid File | ja | No File, nichts geschrieben |
| BLECH Synth-Satz (blau) | `KORG/blechtribe/System/` BOOT, USER, PCM, SYSTEM | Korgs blaue | ja | ja | No File, nichts geschrieben |
| | | Korgs blaue mit Sampler-Kopf | nein, Invalid File | ja | No File, nichts geschrieben |
| Hacktribe (blau) | `KORG/hacktribe/System/` BOOT, USER, PCM, SLICE, SYSTEM | Korgs blaue | nein, Invalid File | ja | No File, nichts geschrieben |
| | | Korgs blaue mit Sampler-Kopf | ja | ja | No File, nichts geschrieben |
| BLECH mit Hacktribe (blau) | `KORG/blechtribe/System/` dieselben fünf | Korgs blaue | nein, Invalid File | ja | No File, nichts geschrieben |
| | | Korgs blaue mit Sampler-Kopf | ja | ja | No File, nichts geschrieben |

Auf der roten liegen die drei Ordner `electribe sampler`, `hacktribe`, `blechtribe`, auf der blauen `electribe`, `hacktribe`,
`blechtribe` (wie die Seite sie nennt).

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Jede der acht Firmwares öffnet bei SOFTWARE UPDATE nur `.VSB` in einem Ordner: Korgs rote `electribe sampler`, Korgs blaue `electribe`, Hacktribe auf beiden Farben `hacktribe`, jede BLECH `blechtribe` | gemessen | `rescue_folders_probe.py`, Schritt `empty` und die Liste `opened` jedes Laufs (Haken auf `f_open`) |
| Mit der Datei in allen drei Ordnern öffnet das Update dieselben Pfade wie mit der Datei nur im eigenen Ordner, und der Flash danach ist Byte für Byte derselbe | gemessen | `all_equals_own` je Firmware und Datei |
| Mit der Datei nur in den beiden anderen Ordnern: "Error / No File", null Lösch- und Schreibbefehle, Flash unverändert | gemessen | `others_untouched`, Bild am Ende des Laufs |
| Ein Start mit der Datei in allen drei Ordnern erreicht das Hauptbild, öffnet keine `.VSB` und gibt keinen Befehl an den Flash | gemessen | `start_with_all_copies` |
| Hacktribe und BLECH mit Hacktribe auf der blauen lehnen Korgs unveränderte blaue ab, Korgs blaue und BLECHs Synth-Satz die blaue mit Sampler-Kopf; das hängt am Kopf, nicht an den Kopien | gemessen | `written` false, Bild "Error / Invalid File"; passt zu [BLECH mit Hacktribe auf der blauen](2026-10-26-blech-hacktribe-blau.md) |
| BLECHs Synth-Satz fragt beim Start nach dem Kopieren von `KORG/electribe`, wenn `KORG/blechtribe` fehlt; mit der Datei in allen drei Ordnern gibt es `KORG/blechtribe`, die Frage kommt nicht | gemessen | Lauf `others` von BLECH blau (Frage, mit EXIT beantwortet), Lauf `all` ohne Frage; die Frage selbst: [Ordner übernehmen, blau](2026-10-29-blau-ordner-uebernehmen.md) |
| Die Abfrage beim Einschalten sucht nur in Korgs Ordner der Kennung, die Kopien in `hacktribe` und `blechtribe` stören sie nicht | hergeleitet | [Rettung](../rettung.md), zweite Tabelle (Emulator); mit allen drei Kopien nicht neu gemessen |
| Mit Patterns, Samples und Einstellungen im Flash und auf der Karte ändert sich daran nichts | hergeleitet | das Update öffnet nur den einen Ordner; gemessen nur auf leerem Flash und leerer Karte |
| Dasselbe am Gerät | offen | nicht geprüft |

## Befehl

```bash
node tools/patch/apply.mjs --vsb HACKTRIBE.VSB --set data/patches/blech.json --out BLECH-HT.VSB
node tools/patch/apply.mjs --vsb KORG-ROT.VSB --set data/patches/blech.json --out BLECH-ROT.VSB
node tools/patch/apply.mjs --vsb KORG-BLAU.VSB --set data/patches/blech-synth.json --out BLECH-BLAU.VSB
PYTHONPATH=tools/patch tools/emu/.venv/bin/python tools/emu/rescue_folders_probe.py --korg-red KORG-ROT.VSB \
    --korg-blue KORG-BLAU.VSB --hacktribe HACKTRIBE.VSB --blech BLECH-HT.VSB --blech-stock BLECH-ROT.VSB \
    --blech-blue BLECH-BLAU.VSB [--only korg-red] [--shots ORDNER]
```

Ohne `--only` laufen alle acht nacheinander; einzeln (`--only korg-red`, `hacktribe-red`, `blech-red`, `blech-stock-red`,
`korg-blue`, `blech-blue`, `hacktribe-blue`, `blech-ht-blue`) lassen sie sich nebeneinander starten. Der Rückgabewert ist 0, wenn
für jede Firmware die Kopien nichts ändern, die anderen Ordner nie gelesen werden und der Start ruhig bleibt.
