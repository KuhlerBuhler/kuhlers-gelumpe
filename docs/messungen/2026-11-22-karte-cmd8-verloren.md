# Karte vom Mac zurück, Start hängt oder "No Card.": CMD8 geht verloren (22.11.)

Stand 22.11.2026. Gerät: rote Electribe mit Hacktribe 2.02 + BLECH (Firmware f53fd5b9, develop), nur READ über BLECH SysEx. Emulator:
Hacktribe 2.02, Korgs Original 2.02 rot und blau. Marker: **gemessen**, **offline gelesen** (Disassembly), **hergeleitet**, **offen**.

## Befund am Gerät

Die Karte war am Mac, eine Datei wurde geschrieben, die Karte ausgeworfen und wieder ins Gerät gesteckt. Mal mountet sie, mal nicht.
Gelesen alle 0,25 s über BLECH READ: OS-Tick `0xC06A292C`, `M_CARD` (`0xC01D6E00` + 0x1B0), Sperrwort `0xC031BEEC`, OCR `0xC031BEA4`,
Treiber "present" und "init" (`0xC031BEC0` + 0x19 und + 0x1A), FatFs `fs_type` über den Zeiger `0xC06A010C`.

| Behauptung | Beleg | Marker |
|---|---|---|
| Im Betrieb gesteckt: 0,6 s danach steht im OCR-Wort 0x00800120, die R1-Antwort mit COM_CRC_ERROR statt einer OCR. Nach etwa 2 s Sperre, `CARD_WAIT`; das zweite Lesen bekommt keine Antwort (OCR 0), sperrt wieder, `CARD_STUCK`. Ein Neustart mountet dieselbe Karte | Poll auf linux, ~/gelumpe-probe | gemessen |
| Start mit der Karte hängt auf dem Startbild. Karte gezogen: der erste lesbare Tick ist 611, der Hänger liegt also in Korgs Init, bevor der OS-Timer läuft | Poll, Gerät ohne USB während des Hängers | gemessen |
| Danach Karte wieder gesteckt: present 1, init 0, `fs_type` 0, Sperre 0, `M_CARD` 0xFE (`CARD_NEVER`): das Pin sagte beim Scharfschalten "keine Karte", danach liest BLECH keine Karte mehr bis zum nächsten Start | Poll | gemessen |
| Korgs Init (`0xC001AE04`) schickt CMD0, dann CMD8 mit 0x1AA und wirft dessen Ergebnis weg, wartet 10, setzt die OCR auf 0 und läuft dann die ACMD41-Schleife ab `0xC001AE80` mit bis zu 0xC34F Runden. CMD0 und CMD8 kommen in diesem Init nicht noch einmal | Disassembly Korg 2.02 rot und Hacktribe; blau dieselben Aufrufe 0x46D8 tiefer | offline gelesen |
| Eine SDHC-Karte, die seit ihrem letzten CMD0 kein CMD8 gehört hat, hält den Host für einen 1.x-Host und bleibt auf ACMD41 busy | SD-Spezifikation 4.2.3.1 | gelesen |
| Geht CMD8 beim Stecken oder beim Start verloren oder kommt verstümmelt an, bleibt die Karte die ganzen 50000 Runden busy: beim Start ohne laufenden Timer (kein Abbruch nach Zeit möglich), im Betrieb bis zur Sperre | aus den Zeilen darüber | hergeleitet |

## Fix

- `acmd41_round_hook` (`tools/patch/script_menu.s`) zählt die Runden der ACMD41-Schleife. Alle `SD_RESTART` (500) Runden ohne
  "fertig" schickt er CMD0, CMD8 (0x1AA) und Korgs Pause und setzt die OCR auf 0, wie Korgs eigener Anfang der Init. Nach `SD_GIVE_UP`
  (4000) Runden nimmt er Korgs Weg für die letzte Runde: -13 und Sperre. Das gilt auch beim Start, denn es hängt nicht am OS-Tick.
  Im Betrieb bleibt der Abbruch nach `CARD_INIT_MS` dazu.
- `CARD_NEVER` gibt es nicht mehr. Nach einem Start ohne Karte liest `menu_card_watch` die erste gesteckte Karte wie eine getauschte;
  der Grund für `CARD_NEVER` (#518, die erste Karte nach so einem Start hängte Korgs Init) ist dieselbe Schleife.
  Die FILE-Befehle von BLECH SysEx gehen mit so einer Karte wie mit jeder anderen um.
- Das Kartenmodell des Emulators (`tools/emu/sdcard.py`) hält sich an die Regel aus der Spezifikation: eine SDHC-Karte ohne CMD8 seit dem
  letzten CMD0 bleibt busy.

| Behauptung | Beleg | Marker |
|---|---|---|
| CMD8 beim Start verloren: die Karte mountet im selben Init, die Sperre wird nie gesetzt | `tools/emu/menu_cases.py:card_later_cases`, `cmd8_lost_at_start_mounts`, HT/rot/blau | gemessen |
| CMD8 beim Stecken im Betrieb verloren: die Karte mountet ohne Sperre, ihre Einstellungen gelten nach 3 s | `cmd8_lost_on_insert_mounts`, HT/rot/blau | gemessen |
| Mit dem BLECH-Stand vor dem Fix scheitern beide Fälle: die Sperre wird gesetzt | dieselben Fälle gegen develop b35ccc39, HT und blau | gemessen |
| Start ohne Karte, dann Karte gesteckt: ihre Einstellungen gelten, Sperre 0 | `start_without_card_reads_the_first`, HT/rot/blau | gemessen |
| FILE-Befehle schreiben und lesen eine nach einem Start ohne Karte gesteckte Karte | `tools/emu/sysex_cases.py:file_cases`, `file_card_after_start_without_one`, HT/rot/blau | gemessen |
| Am Gerät: ob der Neustart nach 500 Runden die Fälle vom Mac abdeckt, und ob die COM_CRC_ERROR-Antwort beim Stecken dieselbe Ursache hat | Gerätetest | offen |
