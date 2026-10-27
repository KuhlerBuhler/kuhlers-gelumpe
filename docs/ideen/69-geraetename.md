# 69. Gerätename "Electribe 3"

Wunsch (27.10.): der Rechner zeigt die Electribe als "Electribe 3" statt mit Korgs Namen. Entschieden: der Name ist
"Electribe 3" (nicht "Blechtribe 3").

Stand 2026-10-27: **gebaut, im Emulator geprüft, am Gerät offen.** Gelesen in der Firmware (rot, Hacktribe, blau 2.02)
und im Code. Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Befund

- Die USB-Beschreibungen liegen als Daten in der Firmware. Herstellername ist String 1, Gerätename String 2, die beiden
  MIDI-Ports nehmen ihre Namen aus String 3 und 4. Jeder String hat genau einen Verweis, aus einer Tabelle mit 5 Einträgen.
  (gemessen)
  - Rot (Korg und Hacktribe gleich): Tabelle `0xC00A40A0`, Gerätename `0xC00A4120`, Ports `0xC00A4148` und `0xC00A4180`.
  - Blau: Tabelle `0xC008EB00`, Gerätename `0xC008EB80`, Ports `0xC008EB98` und `0xC008EBC0`.
- Platz (2 Byte Kopf plus UTF-16): "Electribe 3" braucht 24 Byte und passt auf beiden. "Electribe 3 _ SOUND" (40) passt auf
  beiden. "Electribe 3 _ PAD/KNOB" (46) passt auf der roten, auf der blauen fehlen 2 Byte, danach folgt direkt die nächste
  Beschreibung. (gemessen)
- "KORG INC." als Hersteller und die USB-Kennungen (VID 0944, PID 012E rot, 012D blau) bleiben. (hergeleitet)
- Die App findet die Ports mit `/electribe/i` (`src/session.mjs:34`), rot oder blau über SysEx. "Electribe 3" passt weiter.
  Jeder Portname muss "Electribe" behalten. (gemessen, Code gelesen)
- Der Rechner liest die Namen nur beim Einstecken. Deshalb ist es eine Wahl beim Patchen, kein Menüpunkt am Gerät.
  (hergeleitet)

## Was es für Nutzer heißt (ungeprüft)

- DAW-Zuordnungen und Controller-Skripte, die am alten Portnamen hängen, müssen neu verknüpft werden. Deshalb abschaltbar.
- Windows kann den alten Namen behalten, bis man das Gerät im Geräte-Manager einmal entfernt.
- Welcher String wo erscheint: macOS und Linux zeigen Gerätename und Portnamen, Windows je nach Treiber (Klassentreiber,
  Windows MIDI Services, Korgs Treiber).

## Plan

1. Patch als Datenpatch: die drei Strings an Ort und Stelle ersetzen, je eine Datei für Sampler (Hacktribe und Korg) und
   Synth. Kein ARM-Code.
2. Blau: **entschieden (27.10.)**, kürzere Portnamen "Electribe 3 SOUND" und "Electribe 3 PAD/KNOB" an Ort und Stelle. Die
   rote behält "Electribe 3 _ SOUND" und "Electribe 3 _ PAD/KNOB".
3. Ein Häkchen pro Patch im Patcher der App (gibt es noch nicht) für diesen Patch, aus per Voreinstellung.
4. Prüfung im Emulator nur auf Bytes, der Emulator kennt kein USB. Prüfen, ob die Startprüfung des Patchers den Bereich
   als Startphase erklärt haben will.

## Gebaut

- Datenpatch `usb-name`: `data/patches/usb-name.json` (Hacktribe und Korgs rote 2.02, gleiche Adressen und Bytes) und
  `data/patches/usb-name-synth.json` (blau), gebaut von `tools/patch/usb_name.py` aus der eigenen `SYSTEM.VSB`. Jede
  Änderung ist ein ganzer Platz: neue Beschreibung, der Rest Nullen wie in der Firmware. Der Builder prüft vorher den
  Tabelleneintrag und die alten Bytes. (gemessen an den drei Dateien)
- Plätze: rot Gerätename 40 Byte, Ports 56 und 60; blau 24, 40 und 44. Nach dem jeweils letzten Port folgt direkt die
  nächste Beschreibung (Typ 6), nach den anderen zwei Byte Nullen. "Electribe 3" füllt den Platz auf der blauen genau. (gemessen)
- Nicht in den Sätzen `blech.json` und `blech-synth.json`. Im Patcher der App ein Häkchen "Gerätename: Electribe 3" in
  Schritt 2, aus per Voreinstellung, mit dem Hinweis auf DAW-Zuordnungen und Windows. Es geht auch auf eine mitgebrachte
  `BLECH.patch`. Von Hand: `apply.mjs --set data/patches/blech.json --patch data/patches/usb-name.json`.
- Emulator (Kurzprüfung, Start und Rettungswege): besteht allein auf Hacktribe, Korgs roter und der blauen 2.02 und mit
  dem ganzen BLECH-Satz auf Hacktribe und der blauen. Die Startprüfung will keinen Bereich erklärt haben, die Firmware
  liest die Strings beim Start nicht. Der Emulator kennt kein USB, die Namen selbst prüfen nur die Tests der Bytes
  (`test/usb-name.test.mjs`). (gemessen)

## Am Gerät zu testen (rot und blau)

- Name unter Linux (`amidi -l`, `aconnect -l`), macOS (Audio-MIDI-Setup), Windows mit Klassentreiber und mit Korgs Treiber.
- Die App verbindet, SysEx geht in beide Richtungen.
- Korgs Editoren finden das Gerät noch.
- Windows: zeigt es nach dem Umstecken den neuen Namen, oder erst nach Entfernen im Geräte-Manager?
