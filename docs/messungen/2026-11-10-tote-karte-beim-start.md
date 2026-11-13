# Tote Karte beim Start (10.11.)

Gefunden mit dem Fehlermodell der Karte (`tools/emu/sdcard.py`): mit BLECH blieb der Start beim BLECH-Startbild stehen, wenn
die Karte kein Dateisystem hat (alles Nullen) oder auf keinen Befehl antwortet. Ohne BLECH läuft das Gerät mit beiden weiter.
Alles hier ist **gemessen im Emulator**, nicht am Gerät.

## Gemessen (Emulator, eigene Dateien: Hacktribe, Korgs rot und blau, 2.02)

| Karte | Hacktribe, Korg rot ohne BLECH | BLECH auf Hacktribe und rot, bisher | BLECH jetzt | BLECH blau |
|---|---|---|---|---|
| ohne Dateisystem | Hauptbildschirm, kein Kasten | bleibt auf Bildschirm 46 (Startbild) | Hauptbildschirm, kein Kasten | Hauptbildschirm |
| antwortet auf nichts | Hauptbildschirm, kein Kasten | bleibt auf Bildschirm 46 | Hauptbildschirm, kein Kasten | Hauptbildschirm |

In allen Fällen schreibt BLECH nichts auf die Karte und macht keinen Ordner. Einen Kasten "Card Error" zeigt die Firmware
ohne BLECH in beiden Fällen nicht, BLECH jetzt auch nicht. Fall: `cardfault:dead_card_no_filesystem` und
`cardfault:dead_card_answers_nothing` in `tools/emu/card_error_cases.py`, verglichen mit demselben Start mit EXIT beim
Einschalten (alle Patches aus).

Ohne den Ladebalken (`load-bar.json` aus dem Satz genommen) läuft auch die alte BLECH-Fassung auf Hacktribe durch. Die blaue
hat den Ladebalken nicht und hing nie.

## Ursache

Der Ladebalken hängt an der Frage nach `e2sSample.all` (`0xC002AE60`). Bisher fragte er nach, wenn die Karte steckt, ihr
Volume danach aber nicht gemountet ist: bis zu drei Mal, mit dem Schlaf des Betriebssystems (`0xC0000B78`, 500 ms) dazwischen
([Kartenfehler beim Start](2026-10-19-kartenfehler-beim-start.md)).

Der Schlaf endet nie. Der Takt des Betriebssystems läuft an dieser Stelle noch nicht:

- Den 1-ms-Timer (TIMER64P0, Periode `0x5DBF`) richtet die Firmware bei `0xC0019088` erst nach der Frage ein: ohne Antwort
  der Karte kommt die Frage nach 2,78 s zurück, der Timer wird bei 2,81 s eingerichtet; mit guter Karte 0,116 s und 0,14 s.
- Der Tickzähler `0xC06A292C` steht bis dahin auf 1. Mit der alten Fassung stand er auch 14 s nach dem Einschalten noch auf 1,
  die Aufgabe im Schlaf, der Prozessor in der Leerlaufschleife (`0xC000180C`).

**hergeleitet:** Die Reihenfolge ist die der Firmware, nicht des Emulators (der Timer läuft, sobald die Firmware ihn
einrichtet). Am Gerät hängt das Nachfragen darum genauso, sobald es einmal zum Schlaf kommt. Funktioniert hat es also nie.

## Geändert

`tools/patch/load_bar.py`: das Nachfragen ist raus. Ist die Karte nach der Frage nicht gemountet, geht der Start weiter wie
in der Firmware. Der Rest des Hakens (Overlay nur, wenn die Datei da ist und EXIT nicht gehalten) bleibt.

## Offen

- Am Gerät nicht geprüft: eine Karte ohne Dateisystem und eine, die nicht antwortet.
- Eine Karte, die beim Start zu spät antwortet (Rückmeldung 18.10.), bekommt jetzt keinen zweiten Versuch, wie in der Firmware.
  Ein Nachfragen ginge nur mit einer Wartezeit, die ohne den Takt des Betriebssystems auskommt.
