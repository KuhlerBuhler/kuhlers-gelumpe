# Gerätetest: Dateien auf der SD-Karte lesen und schreiben

Stand 2026-10-14. Anleitung für Tester. Im Emulator gemessen, am Gerät noch nicht geprüft.
Siehe auch die [Übersicht](README.md).

## 1. Worum es geht

Die Plugin-Laufzeit von BLECH liest und schreibt Dateien auf der SD-Karte (`e2sPlugin.all`,
Einstellungen, gespeicherte Werte) und benutzt dafür die Dateifunktionen der Firmware (FatFs).
Dieser Test prüft das vorher, ohne Firmware zu ändern: ein kleiner Probe-Code liest eine
Datei von der Karte und schreibt eine zweite.

Am Ende ist belegt: `f_open`, `f_read`, `f_write` und `f_close` arbeiten am Gerät so wie im
Emulator. Das Lesen liefert 200 Byte mit der erwarteten CRC-32, die geschriebene Datei ist
Byte für Byte gleich dem, was gesendet wurde, und das Dateisystem der Karte bleibt heil.

## 2. Warnung

**Das Gerät wird verändert.** Über SysEx wird eigener ARM-Code in den RAM geschrieben und
einmal ausgeführt (derselbe Weg wie bei `tools/device/led_show.py` und `tools/device/backlight.py`),
und auf der SD-Karte entsteht eine neue Datei. Es wird kein Flash beschrieben, keine
Firmwaredatei gespielt und nichts gelöscht.

Du machst das auf eigenes Risiko, ohne Gewähr. Was passieren kann:

- Das Gerät antwortet nicht mehr oder hängt. Dann aus- und wieder einschalten. Der Probe-Code
  läuft nur einmal, der Flash wird nicht berührt, und nach dem Einschalten nutzt die Firmware
  den Puffer wieder selbst.
- Das Dateisystem der Karte nimmt Schaden. FatFs hat keine Sperre, deshalb darf die Firmware
  während des Tests nichts anderes mit der Karte tun (siehe Voraussetzungen). Ist eine Datei
  beschädigt, kopierst du die gesicherte Karte zurück.
- Ein Absturz der Firmware durch unbekannten Code im RAM ist nicht ausgeschlossen.

Korg-Daten werden nie hochgeladen. Für diesen Test brauchst du keine Firmwaredatei zu
verschicken. Gemeldet werden nur die Textausgaben der Werkzeuge.

## 3. Voraussetzungen

- Electribe 2 Sampler mit Firmware 2.02 und Hacktribe, Netzteil angeschlossen.
- Eine SD-Karte im Gerät.
- Rechner mit Python 3 und `mido`, das Gerät per USB. Die Werkzeuge in `tools/device/` laufen
  mit dem System-Python, nicht in der Python-Umgebung des Emulators (die hat `mido` nicht).
  Es muss genau ein MIDI-Port mit "electribe" und "SOUND" im Namen da sein.
- Das Gerät ist ruhig: Hauptbildschirm offen, keine DATA UTILITY, kein Sample-Laden, kein
  Event Rec/Play.
- Optional für den Probelauf vorab: die eigene `SYSTEM.VSB` und die Python-Umgebung des Emulators
  (`npm run setup:emu`).

## 4. Vorher sichern

1. **Die ganze SD-Karte** auf den Rechner kopieren.
2. **Den Global-Block** lesen (nur Lesen, nie ab Adresse `0x1000000`):

   ```bash
   python3 tools/device/flash_dump.py --out <Datei> --start 0x230000 --length 0x4000
   ```

   Das Werkzeug liest zweimal und schreibt die Datei nur, wenn beide Durchgänge gleich sind.
   Die ersten 256 Byte sind der Global-Block. Die Datei bleibt bei dir.
3. **Die Patterns** sichern, wenn du sie noch nicht gesichert hast: am Gerät EXPORT ALL PATTERN
   in DATA UTILITY, das legt eine `.e2sallpat`-Datei im Kartenordner ab. Der Test fasst
   Patterns nicht an, die Sicherung ist Vorsicht.

Warum die Globals: am 13.10. standen sie nach Arbeit am Gerät auf der Vorgabe, die Ursache
ist offen ([Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md)). Vergleiche nach dem
Test den Global-Block mit der Sicherung (erneut lesen, die ersten 256 Byte vergleichen).

## 5. Der Weg zurück

Eine Firmware wird hier nicht geändert, es gibt also kein Update zurückzuspielen.

- **Gerät hängt:** aus und wieder an.
- **Karte beschädigt:** die Sicherung aus Abschnitt 4 zurückkopieren.
- **Globals weichen ab:** im Global-Menü nachsehen und nicht ausschalten, nicht WRITE drücken. Den
  gesicherten Block als Global-Dump (`0x51`) an das Gerät senden, das speichert sofort. Den
  globalen MIDI-Kanal danach von Hand einstellen, der Dump setzt ihn nicht. Ein fertiges Werkzeug
  dafür liegt nicht bei (offen).
- **Gerät startet nach dem Test nicht normal:** Karte entnehmen, aus und wieder an. Hilft das
  nicht, gilt der Weg aus Abschnitt 5 der [BLECH-Anleitung](blech-datei.md) mit der eigenen
  Original-`SYSTEM.VSB`. Zu erwarten ist das nicht, der Flash bleibt unberührt.

## 6. Die Schritte

Der Test arbeitet mit einem Stub von 604 Byte, den `tools/device/fatfs_probe.py` nach `0xC1000000`
schickt, einmal ausführt und dessen Ergebnisse es aus einem freien RAM-Bereich bei `0xC01F7000`
liest (1280 Byte). Danach stellt es beide Bereiche wieder her. Gelesen wird
`KORG/blechtribe/Plugin/FSTEST.IN` (bis 256 Byte, CRC-32), geschrieben `FSTEST.OUT` (64 Byte, in
jedem Lauf neu erzeugt), dann wieder geöffnet, zurückgelesen und verglichen. Vor dem Schreiben prüft
das Werkzeug die ersten 64 Byte von `f_open`, `f_read`, `f_write` und `f_close` gegen die gemessene
Firmware und bricht ohne Schreiben ab, wenn sie abweichen. Es löscht und benennt nichts um und legt
keine Ordner an.

0. **Optional: Probelauf im Emulator.**
   `python3 tools/device/fatfs_probe.py --emu <eigene SYSTEM.VSB>`
   Erwartet: alle Rückgaben 0, 200 Byte mit richtiger CRC gelesen, 64 Byte geschrieben und
   zurückgelesen, die Datei auf dem Kartenabbild gleich dem Gesendeten. Am 14.10. so gemessen
   (`test/fatfs-probe.test.mjs`).
   Melden: ok oder die Ausgabe.

1. **Eingabedatei bauen.**
   `python3 tools/device/fatfs_probe.py --make-input <Ordner>`
   Erwartet: `<Ordner>/FSTEST.IN`, 200 Byte, CRC-32 `53d45279`.
   Melden: ok oder die Ausgabe.

2. **Karte vorbereiten.** Auf der Karte den Ordner `KORG/blechtribe/Plugin/` anlegen, neben
   `KORG/hacktribe` (die Firmware legt ihn nicht selbst an), und `FSTEST.IN` hineinkopieren. Karte in
   das ausgeschaltete Gerät stecken, einschalten, warten bis der Hauptbildschirm da ist.
   Erwartet: Hauptbildschirm, normaler Start.
   Melden: ok oder was anders ist.

3. **Trockenlauf.**
   `python3 tools/device/fatfs_probe.py --dry-run`
   Erwartet: "checks passed" und "dry run: nothing written". Weicht eine Prüfsumme der Firmware ab,
   hier abbrechen.
   Melden: ok, bei Abweichung die ganze Ausgabe.

4. **Lesetest.**
   `python3 tools/device/fatfs_probe.py --read`
   Erwartet: "all checks passed", `open_in`, `read_in` und `close_in` alle 0, `bytes_in` 200,
   `crc_in` 1406423673 (das ist `53d45279`). Danach läuft das Gerät normal weiter.
   Melden: ok, sonst die Ausgabe mit den Ergebniswörtern.

5. **Schreibtest.**
   `python3 tools/device/fatfs_probe.py --write`
   Erwartet: "all checks passed" und die Zeile `FSTEST.OUT sent (hex): ...`. Die Hex-Zeile
   aufheben.
   Melden: ok, sonst die Ausgabe. Ein Rückgabewert ungleich 0 steht in den Ergebniswörtern
   (`open_in` und verwandte).

6. **Karte prüfen.** Gerät ausschalten, dann die Karte ziehen, am Rechner ansehen. `FSTEST.OUT` ist
   64 Byte groß, sein Inhalt in Hex gleicht der Zeile aus Schritt 5
   (`xxd -p KORG/blechtribe/Plugin/FSTEST.OUT | tr -d '\n'`), und die Dateisystemprüfung
   (`fsck_msdos` oder die Datenträgerprüfung des Betriebssystems) meldet keinen Fehler.
   Erwartet: Größe, Inhalt und Prüfung wie beschrieben.
   Melden: ok, sonst Größe, Hex und Meldung der Prüfung.

7. **Aufräumen.** `FSTEST.IN` und `FSTEST.OUT` von der Karte löschen, wenn sie nicht mehr gebraucht
   werden. Das Werkzeug löscht nichts.
   Erwartet: nichts weiter. Danach den Global-Block erneut lesen und mit der Sicherung vergleichen.
   Melden: ok oder die Abweichung.

Was danach geprüft wird: das Laden der `e2sPlugin.all` beim Start. Das ist im Emulator mit der
echten Firmware und einer virtuellen Karte gemessen
([Messung](../messungen/2026-10-14-skript-karte.md)) und kommt in der
[BLECH-Anleitung](blech-datei.md) an die Reihe.

## 7. Ergebnisse

| Punkt | Stand | Beleg |
|---|---|---|
| Probe-Code liest 200 Byte mit richtiger CRC, schreibt 64 Byte, liest zurück und vergleicht (virtuelle Karte) | im Emulator gemessen am 14.10. | `test/fatfs-probe.test.mjs` |
| Datei auf dem Kartenabbild gleich dem Gesendeten | im Emulator gemessen am 14.10. | `test/fatfs-probe.test.mjs` |
| Lader der `e2sPlugin.all` mit echter Firmware und virtueller Karte | im Emulator gemessen am 14.10. | [Messung](../messungen/2026-10-14-skript-karte.md) |
| Stub aus dem RAM ausführen (LED, Hintergrundlicht) und Originalbytes zurückschreiben | am Gerät bestätigt, 10.10. | [Startphase](../messungen/2026-10-10-startphase.md), [Speicherbereiche](../speicherbereiche.md) |
| Lesen über FatFs am Gerät (Schritte 3 und 4) | offen | |
| Schreiben über FatFs am Gerät (Schritte 5 und 6) | offen | |
| Dateisystem der Karte nach dem Schreiben unbeschädigt | offen | |
| Verhalten, wenn die Firmware während des Tests selbst auf die Karte zugreift | offen, nicht getestet (FatFs hat keine Sperre) | |
| Stapelbedarf des Laders am Gerät | offen | [Messung](../messungen/2026-10-14-skript-karte.md) |
