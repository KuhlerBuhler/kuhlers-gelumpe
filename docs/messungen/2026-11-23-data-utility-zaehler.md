# DATA UTILITY: der Seitenzähler eines Fensters zeigt die Nummer der Funktion (23.11.)

Bericht am Gerät: in DATA UTILITY steht SOFTWARE UPDATE an Platz 14. Nach ENTER zeigt die Leiste oben 13, die Nummer von
FACTORY RESET. Wer das sieht, glaubt, er hat das Falsche gewählt.

Markierungen: **gemessen** (Emulator, Haken am Zähler-Konstruktor), **hergeleitet** (Disassembly), **offen** (nicht am Gerät).

## Ursache: Korgs Firmware, nicht BLECH

- Der Seitenzähler oben ist ein Objekt mit Index und Gesamtzahl. Konstruktor `0xC008A83C` (r1 Index ab 0, r2 Gesamtzahl),
  Setter `0xC008A8A8`; blau `0xC007A110` / `0xC007A17C` (hergeleitet, gemessen).
- BLECHs `menu_counter_fix` (`script_menu.s`) vergrößert nur die Gesamtzahl (14 auf 18 mit unseren Seiten), den Index lässt
  er stehen (hergeleitet).
- Die Fenster der DATA-UTILITY-Funktionen bauen ihren Zähler mit einem festen Index. Bei zwei Fenstern ist er um eins zu
  klein, auf der roten wie auf der blauen, mit und ohne Hacktribe, also schon in Korgs Original (gemessen):

| Build | Fenster | Stelle | Befehl | zeigt | richtig |
|---|---|---|---|---|---|
| Hacktribe / rot | SOFTWARE UPDATE | `0xC006C58C` | `mov r1,#12` | 13 | 14 |
| Hacktribe / rot | IMPORT SAMPLE (Bildschirm 39) | `0xC006AD64` | `mov r1,#7` | 8 | 9 |
| blau | SOFTWARE UPDATE | `0xC005FC50` | `mov r1,#7` | 8 | 11 |

Alle übrigen Funktionen zeigen ihren Platz richtig (gemessen: jede Funktion einmal mit ENTER geöffnet, HT 0 bis 13, blau 0 bis 10).

## Fix

`tools/patch/script_hooks.py`, Tabelle `WORDS` und das Wortpaar des blauen Profils: die drei Befehle bekommen den richtigen
Index (`#13`, `#8`, blau `#10`). Reine Wortänderung, kein Sprung, kein Code. Die Wörter laufen nur im jeweiligen Fenster, nicht
beim Start, deshalb ohne Startphasen-Spanne.

## Prüfung

Fall `menu:du_window_counter_*` (`tools/emu/menu_cases.py`, `du_window_counter_part`): Funktion in DATA UTILITY wählen, ENTER,
der Konstruktor muss mit (Index der Funktion, Gesamtzahl) laufen (gemessen):

| Build | Fall | vorher | nachher |
|---|---|---|---|
| Hacktribe | IMPORT SAMPLE | (7, 14) rot | (8, 14) grün |
| Hacktribe | SOFTWARE UPDATE | (12, 14) rot | (13, 14) grün |
| rot | beide | wie Hacktribe | grün |
| blau | SOFTWARE UPDATE | (7, 11) rot | (10, 11) grün |

Am Gerät: **offen**.
