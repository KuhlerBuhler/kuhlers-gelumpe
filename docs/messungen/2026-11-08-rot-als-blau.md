# Die rote Electribe als blaue: Korgs Synth-Firmware auf dem Sampler und zurück, im Emulator

Probe im [Emulator](../glossary.md#emulator), **am Gerät nichts**. Frage: kann die rote Electribe, auf der BLECH mit Hacktribe läuft
([Hacktribe](../glossary.md#hacktribe)-Basis `163d1d8d`, Kennung im Flash `KORGele2sUSR`), für Tests Korgs blaue Firmware 2.02 (`41fc5f1c`) laufen lassen und danach
ohne Verlust zurück zu BLECH? Die Gegenrichtung (Sampler-Code auf der blauen) steht in
[BLECH mit Hacktribe auf der blauen](2026-10-26-blech-hacktribe-blau.md).

Eingaben, alle außerhalb des Repositorys: BLECH aus `data/patches/blech.json` auf der Hacktribe `163d1d8d` (Ergebnis `d91d959d`),
Korgs blaue 2.02 unverändert, und der eigene ganze Flash der roten vom 9.10. ([Flash-Dump](2026-10-09-flash-dump.md)) mit seinen
Patterns, Globals und der Werks-Samplebank. Keine Firmware-Bytes im Repository.

Marker: **gemessen** (im Emulator ausgeführt, Befehl unten), **hergeleitet** (aus Code oder Messung geschlossen, nicht laufen
gesehen), **offen** (geht nur am Gerät oder ist nicht geprüft).

## Kurzfassung

1. **Hin geht.** Die laufende BLECH nimmt Korgs blaue Datei mit Sampler-Kopf (`0x12 = 0x53`, `0x2E = 0x24`) aus
   `KORG/blechtribe/System/` und schreibt sie, unverändert sagt sie "Error / Invalid File" und schreibt nichts. (gemessen)
2. **Korgs blaue bleibt auf dem roten Flash bei "SOFTWARE UPDATE / press ENTER" stehen.** Mit einem Wort geändert startet sie bis
   zum Hauptbild, mit den Patterns und Globals der roten und ohne einen Schreibbefehl. Das Wort besteht die Kurzprüfung bis auf die
   Startphase, in der es liegt. (gemessen)
3. **Die blaue liest die Nutzerdaten der roten, schreibt sie aber nur bei WRITE und beim Ausschalten.** WRITE schreibt das Pattern
   im Format der blauen zurück und ändert dabei in allen 16 Parts zwei Werte. Die Samples auf der Karte fasst sie nicht an, die
   Werks-Samplebank nimmt sie als ihre PCM-Bank: ihre Oszillatoren spielen dann Werks-Samples des Samplers. (gemessen, Klang hergeleitet)
4. **Zurück geht.** Die blaue mit dem Wort nimmt BLECH mit blauem Kopf aus `KORG/electribe/System/` und schreibt es, BLECH startet,
   der Nutzerbereich des Flashs ist bis auf das mit WRITE gespeicherte Pattern derselbe wie vorher. Auch aus dem Stopp in Punkt 2
   führt ein Weg zurück. (gemessen)
5. **Die eigenen Sicherungen bringen alles zurück.** Nach dem Rückweg schreibt BLECH mit IMPORT ALL PATTERN alle 250 Patterns
   genau wie in der Pattern-Datei, und lädt `e2sSample.all` beim Start in dieselben 171 Plätze wie vor der blauen. (gemessen)

**Urteil:** im Emulator geht der Test hin und zurück ohne Verlust. Alles, was nur das Gerät zeigt (Klang, DSP, Leiterplatte), ist offen.

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| BLECH fragt im SOFTWARE UPDATE nach `KORG/blechtribe/System/SYSTEM.VSB` (vorher `USER.VSB`, `PCM.VSB`, `SLICE.VSB`) | gemessen | `red_as_blue_probe.py`, Schritt 1, Liste der geöffneten Dateien |
| BLECH mit Korgs blauer, unverändert: "Error / Invalid File", null Lösch- und Schreibbefehle | gemessen | Schritt 1 |
| BLECH mit Korgs blauer, Sampler-Kopf: 512 Löschbefehle (4 KiB), 8192 Seiten, der Firmwarebereich `[0x20000, 0x220000)` ist danach die blaue, der Rest der 16 MiB unverändert | gemessen | Schritt 1 |
| Korgs blaue auf dem roten Flash: Bildschirm "SOFTWARE UPDATE / press ENTER", sie liest nur `0x220000`+16 und `0x7EF000`+8, schreibt nichts | gemessen | Schritt 2, Bild des Laufs |
| Die Kennungsprüfung der blauen (`0xC00270BC`) gibt für `elec2USR` das Literal `0x123` bei `0xC0027128` zurück und für `ele2sUSR` den Befehl `moveq r0, #0x124` bei `0xC0027114`; der Start nimmt nur `0x123` | gemessen | Disassembly der blauen 2.02; das Spiegelbild von Hacktribes Wort `0xC0029DE4` (siehe [BLECH mit Hacktribe auf der blauen](2026-10-26-blech-hacktribe-blau.md)) |
| `0x123` passt nicht in einen ARM-Sofortwert. Das kleinste Wort: `0xC0027114` von `0x03A00F49` auf `0x059F000C` (`ldreq r0, [pc, #0xc]`, lädt das Literal `0x123`); Datei-Offset `0x27214` | gemessen (Lauf), hergeleitet (Kodierung) | `red_as_blue_probe.mark_fix`, `test_red_as_blue.py` |
| Mit dem Wort: Hauptbild ("001", Pattern der roten), PCM-Ladung mit `r6` 1, keine Assertion, null Lösch- und Schreibbefehle beim Start | gemessen | Schritt 2 |
| Mit dem Wort liest der Start `0x220000`+16, `0x230000`+256 (Globals), `[0x240000, 0x628000)` (250 Patterns), `0x7EF000`+8, `0x7FF000`+8 und die ganze Bank `[0x800000, 0x1000000)` | gemessen | Schritt 2, Haken auf das Flash-Lesen |
| Kurzprüfung der blauen mit dem Wort (`check.py --quick`): 20 von 21 Punkten, durchgefallen nur `start_phase` mit genau `0x27214`+4; mit `--allow-code 0x27214:4` alle bestanden, auch Start mit dem roten Flash, Update-Abfrage ohne Kennung, Panel-Update, alle Startmodi, EXIT | gemessen | Befehle unten |
| Die blaue baut aus der Werks-Samplebank der roten 411 Instrumente (alle Tabellen 411, `DRMP` 1); ihre Oszillatorliste hat 409 Einträge, davon 361 PCM | gemessen | `synth_probe.Probe.tables`, `parse_bank`, `osc_table` |
| Die PCM-Oszillatoren der blauen spielen damit Werks-Samples des Samplers statt ihrer eigenen Wellen | hergeleitet | Instrumentnummer = Wellennummer minus `0x32` ([Samples der blauen](2026-10-15-synth-samples.md)); der Emulator hat keinen Klang |
| Ein Part-Oszillator der roten Patterns (Sample-Nummer) erscheint auf der blauen als leeres "OSC:" | gemessen | Bild des Hauptbilds |
| WRITE auf der blauen (Pattern 001): 4 Sektoren gelöscht, 64 Seiten, nur `[0x240000, 0x244000)`; je Part ändern sich Byte 11 (Osc Edit, 25 auf 255) und Byte 36 (Osc Pitch, -63 auf -1), in allen 16 Parts | gemessen | Schritt 3, Vergleich vorher und nachher |
| Ausschalten auf Batterie ohne Änderung: ein Sektor gelöscht und neu geschrieben, die Globals bei `0x230000` danach Byte für Byte wie im Dump der roten | gemessen | Schritt 3 |
| Was die blaue in die Globals schreibt, wenn man dort etwas ändert | offen | nicht geprüft |
| Die blaue öffnet beim Start und bei WRITE keine Datei auf der Karte, die Karte bleibt unverändert (Probe mit `KORG/blechtribe/Sample/e2sSample.all`, `settings.a.bin`, `KORG/hacktribe/Sample/e2sSample.all`) | gemessen | Schritt 2, Haken auf `f_open` |
| Die blaue mit dem Wort fragt im SOFTWARE UPDATE nach `KORG/electribe/System/SYSTEM.VSB` | gemessen | Schritt 4; der Gerätetyp ist jetzt `0x123`, der Ordner folgt ihm ([Messung blau](2026-10-26-blech-hacktribe-blau.md)) |
| Dort: BLECH mit Sampler-Kopf abgelehnt (null Befehle), mit blauem Kopf (`0x12 = 0x00`, `0x2E = 0x23`) geschrieben, Rest des Flashs unverändert, BLECH startet bis zum Hauptbild | gemessen | Schritt 4 |
| Nach Hin und Zurück unterscheidet sich der Nutzerbereich `[0x220000, 0x1000000)` vom Stand vor der blauen nur in den 28 Bytes, die WRITE in Pattern 001 geändert hat | gemessen | Schritt 4 |
| Aus dem Stopp (unveränderte blaue zeigt "SOFTWARE UPDATE / press ENTER"): ENTER sucht `KORG/electribe sampler/System/SYSTEM.VSB`, BLECH mit Sampler-Kopf dort wird geschrieben und startet; unter `KORG/blechtribe` oder `KORG/electribe` findet sie nichts | gemessen | `red_as_blue_probe.from_the_stop`; passt zu [Rettung](../rettung.md), zweite Tabelle, Zeile 1 |
| Nach dem Rückweg: DATA UTILITY 4/18 IMPORT ALL PATTERN mit der eigenen Pattern-Datei (`KORG/blechtribe/`): 1001 Löschbefehle, danach sind alle 250 Pattern-Blöcke im Flash Byte für Byte die der Datei, auch das mit WRITE auf der blauen veränderte Pattern 001 | gemessen | Probe über `Rig` auf dem Flash nach dem Rückweg, Vergleich Block für Block |
| Die eigene `e2sSample.all` (22,5 MB) als `KORG/blechtribe/Sample/e2sSample.all`: BLECH belegt beim Start 171 Plätze (ab 500), gleich auf dem Flash vor der blauen, nach dem Rückweg und nach dem Pattern-Import | gemessen | Probe über `Rig`, Belegt-Byte der Sample-Tabelle `0xC036AD88` |
| Die 48 Oszillatoren mit Wellennummer unter `0x32` erzeugt die blaue im DSP, sie brauchen keine Bank; die übrigen 361 spielen Instrumente der Bank | gemessen (Liste), hergeleitet (Klang) | `osc_table` |
| Panel, Tasten, Display der roten gehorchen der blauen Firmware | hergeleitet | gleiches Panel-Abbild und gleiche Tastennummern; im Emulator kein "00" |
| Klang, DSP-Programm der blauen auf der roten Platine, Hintergrundlicht | offen | nur am Gerät |

## Was die blaue mit den Daten der roten macht

| Bereich | Beim Start | Beim Benutzen | Folge |
|---|---|---|---|
| Kennung `0x220000` | liest | schreibt nie (nur `USER.VSB`) | bleibt rot; BLECH und Hacktribe nehmen sie danach wieder an |
| Globals `0x230000` | liest | Ausschalten schreibt sie zurück, unverändert gleich | Änderungen in GLOBAL auf der blauen: offen, nicht machen |
| Patterns `[0x240000, 0x628000)` | liest alle 250 | WRITE schreibt das eine Pattern im Format der blauen | ein mit WRITE gespeichertes Pattern ist für den Sampler verändert |
| Sample-Info `[0x6B0000, 0x750000)`, SLICE | liest nicht | kein Schreiber in der blauen gesehen | unberührt (gemessen für Start, WRITE, Ausschalten) |
| Werks-Samplebank `[0x800000, 0x1000000)` | liest ganz, nimmt sie als PCM-Bank | schreibt nur `PCM.VSB` | Oszillatoren klingen nach Werks-Samples (hergeleitet); kein PCM-Update machen, es löscht die Werks-Samples und wird für den Test nicht gebraucht |
| Karte `KORG/blechtribe`, `KORG/hacktribe` | öffnet nichts | öffnet nichts | Samples (`e2sSample.all`), Einstellungen, Plugins bleiben |

Die eigenen Samples der roten liegen auf der Karte, nicht im Flash; die blaue hat keine Sample-Plätze und sieht sie nicht.

Oszillatoren: getestet wird nur die Firmware (Effekte, Menüs), dafür reichen die 48 DSP-Oszillatoren (Wellennummer unter `0x32`).
Die blaue PCM-Bank wird nicht geschrieben. Ohne gültige Bank blieben die 361 PCM-Oszillatoren stumm; auf der roten liegt die
Werks-Samplebank des Samplers, die blaue nimmt sie an, die PCM-Oszillatoren spielen dann Werks-Samples statt ihrer Wellen.

## Was nur das Gerät zeigt

Offen bleibt, ob das [DSP](../glossary.md#dsp)-Programm der blauen auf der roten Platine läuft und klingt, wie die Werks-Samples als Oszillatoren
klingen, ob das Hintergrundlicht stimmt und ob die Patterns nach dem Rückweg am Gerät so sind wie im Emulator. Die blaue Datei mit dem
Wort und dem Sampler-Kopf (`red_as_blue_probe.mark_fix`, `hacktribe_blue_probe.with_head`) enthält Korgs Firmware und wird nicht weitergegeben;
für Dateien, die andere bekommen, gelten die Regeln aus [Patcher](../patcher.md). Auf der blauen darf für einen Test nichts gespeichert
werden, was bleiben soll (WRITE, GLOBAL, FACTORY RESET, PCM-Update). Der Weg zurück nach dem Test: [Rettung](../rettung.md).

## Wie gemessen

Alle Läufe mit den eigenen Dateien, außerhalb des Repositorys:

```
node tools/patch/apply.mjs --vsb HACKTRIBE-163d1d8d.VSB --set data/patches/blech.json --out BLECH.VSB
tools/emu/.venv/bin/python tools/emu/red_as_blue_probe.py --blech BLECH.VSB --korg-blue BLAU.VSB --flash FLASH-ROT.bin --shots BILDER/
tools/emu/.venv/bin/python tools/emu/check.py --base BLAU.VSB --patched BLAU-MIT-WORT.VSB --quick --hardware blue
tools/emu/.venv/bin/python tools/emu/check.py --base BLAU.VSB --patched BLAU-MIT-WORT.VSB --quick --boot-flash FLASH-ROT.bin --allow-code 0x27214:4
cd tools/emu && PYTHONPATH=../patch .venv/bin/python -m unittest test_red_as_blue
```

`red_as_blue_probe.py` geht die vier Schritte durch und endet mit 0, wenn jeder so ausgeht wie in der Belegtabelle. Es nutzt `Rig`,
`run_update` und `reboot` aus `synth_update_probe.py` und `with_head` aus `hacktribe_blue_probe.py`.
