# Hacktribes Flash-Schreibbefehl und die Pattern-Schreibvorgänge (24.10.)

Frage: Was machen Hacktribes SysEx-Befehle `0x53` bis `0x56` mit dem Flash, und hält BLECH `0x56` auf? Gemessen im Emulator
mit dem eigenen Flash-Abbild vom 9.10., Hacktribe 2.02 ohne und mit BLECH. Am Gerät nicht geprüft.

## Aufbau

Hacktribe sortiert seine Befehle in zwei Tabellen: beim Funktionsbyte (`0xC0170540`, Sprungtabelle ab `0xC0170554`) und beim
Ausführen der Nachricht (`0xC0170624`, Sprungtabelle ab `0xC0170638`). `0x53` legt Adresse und Länge in zwei Wörter bei
`0xC01707A4` und `0xC01707A8`. `0x54` und `0x56` tragen danach so viele Bytes, wie `0x53` gesagt hat: `0x54` kopiert sie an die
Adresse im RAM, `0x56` ruft mit ihnen Korgs Flash-Schreiben `0xC0029AB8` auf (Quelle `0xC1000000`, Ziel und Länge aus `0x53`).

Ein Lauf schickt die Befehle über die emulierte DIN-Leitung und zählt die Befehle an den Flash-Chip
(`tools/emu/sysex_cases.py`, `hacktribe_flash_write`), dazu ein Haken auf `0xC0029AB8`, der Ziel und Quelle festhält.

## Ergebnis

| Aussage | Status |
|---|---|
| `0x53` (`0x7F0000`, 16) und danach `0x56` mit 16 Bytes schreibt diese Bytes nach Flash `0x7F0000` | gemessen, Hacktribe ohne BLECH |
| Mit BLECH verwirft der Nachrichten-Haken `0x56`: kein Lösch- oder Schreibbefehl am Flash-Chip, `0x7F0000` bleibt `FF`, keine Antwort. Ebenso mit EXIT beim Einschalten und auf der blauen | gemessen, `sysex:hacktribe_flash_write_dropped`, `sysex:kill_switch_no_flash_write` |
| Gegenprobe: dieselbe Prüfung auf BLECH ohne die Sperre schlägt fehl (80 Seiten geschrieben, 5 Sektoren gelöscht) | gemessen |
| **Nach `0x53`, `0x54` und `0x56` schreibt Hacktribe jedes Mal einen Pattern-Platz neu in den Flash:** die drei Befehle springen am Ende nach `0xC0026554`, mitten in Korgs Fall `0x11` (PATTERN WRITE REQUEST), mit dem Funktionsbyte als Pattern-Nummer. `0x53` schreibt Pattern 84, `0x54` Pattern 85, `0x56` Pattern 87, jeweils 16 KiB (Löschen und Schreiben), die Antwort ist Korgs `0x21` | gemessen (Ziel `0x38C000`, `0x390000`, `0x398000`), Ursache gelesen |
| Der Inhalt dieser Patterns ändert sich dabei nicht: geschrieben wird ihr eigener Stand aus der Pattern-Bank im RAM | gemessen für 84 und 85 |

## Was das heißt

- Jeder RAM-Schreibvorgang über Hacktribe (`0x53` plus `0x54`) löscht und schreibt zwei Pattern-Plätze im Flash. Bei vielen
  Schreibvorgängen nutzt das diese Sektoren ab, und ein Stromausfall in dem Moment kann Pattern 84 oder 85 beschädigen
  (hergeleitet).
- BLECHs eigene Befehle (`0x60` bis `0x67`, `0x6F`) haben diesen Fehler nicht, sie antworten selbst und laufen nicht in Korgs Code.

## Die Sperre aller Hacktribe-Befehle (24.10., später)

Der Editor schreibt und liest das RAM schon über BLECH, wenn das Gerät es kann; nur Ausführen (`KORG.exec`) und Flash lesen
gingen noch über Hacktribe. Dafür gibt es jetzt BLECHs EXEC (`0x6F`), und der Sender nimmt FLASH READ (`0x64`). Damit sperrt
BLECH alle Hacktribe-Befehle `0x52` bis `0x57`, schon beim Funktionsbyte: auch `0x54` dekodiert dann nichts mehr nach
`0xC1000000`. Mit EXIT beim Einschalten gehen sie für Hacktribes eigene Werkzeuge wieder, außer `0x56`. Die Werkzeuge unter
`tools/device/`, die Hacktribes Befehle brauchen, sagen das, wenn keine Antwort kommt.

| Aussage | Status |
|---|---|
| `0x52` antwortet nicht, `0x53` und `0x54` ändern weder das Ziel noch den Stub-Puffer, `0x57` führt nichts aus | gemessen, `sysex:hacktribe_read_dropped`, `sysex:hacktribe_write_run_dropped` |
| Mit EXIT beim Einschalten antwortet `0x52` wieder, `0x56` bleibt verworfen | gemessen, `sysex:kill_switch_hacktribe`, `sysex:kill_switch_no_flash_write` |

## Offen

- Ob `0x57` (Ausführen) ebenfalls einen Pattern-Platz schreibt (mit BLECH nur noch mit EXIT beim Einschalten erreichbar).
- Bestätigung am Gerät.
