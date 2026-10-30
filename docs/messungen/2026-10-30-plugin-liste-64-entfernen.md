# MANAGE PLUGINS: 64 Dateien statt 16, REMOVE löscht die Datei, OFF behält sie (30.10.)

Befund am Gerät (1.3.8 develop): mit 16 und mehr `*.blech` im Ordner `KORG/blechtribe/Plugin/` taucht ein neues Plugin in der Liste
nicht auf, und REMOVE lässt die Datei liegen, das Plugin steht danach wieder als OFF in der Liste. Gewünscht: die Liste zeigt alle,
REMOVE entfernt wirklich, OFF tut, was REMOVE bisher tat.

Gebaut und im Emulator geprüft (Hacktribe, Korg rot, Korg blau; `tools/emu/script_cases.py`, `manage_cases` und `import_cases`). Am
Gerät **ungeprüft**.

## Was jetzt gilt

- **Die Liste hält 64 Dateien** (so viele, wie die Prüfsummenliste der Einstellungen seit Version 3 hält, `MENU_MAX_TRUST`). Hat der
  Ordner mehr Plugin-Dateien, steht hinter dem letzten Plugin die Seite LIST FULL mit "64 files shown"; nichts fehlt mehr still.
- **OFF**, die Seite vor REMOVE: ENTER fragt ("Enter = off"), ein zweites ENTER hält das Plugin an und schreibt `e2sPlugin.all` ohne
  es; die `*.blech` bleibt, das Plugin steht beim nächsten ENTER auf MANAGE PLUGINS als OFF in der Liste. MANAGE PLUGINS meldet
  "off, file kept". Das ist genau das REMOVE bis 1.3.8 develop.
- **REMOVE**: ENTER fragt ("Enter = remove"), ein zweites ENTER tut, was OFF tut, und löscht danach die `*.blech` des Plugins von der
  Karte; das Plugin ist aus der Liste. Ein Plugin, das nur eine Datei ist (nicht geladen), hat jetzt DESCRIPTION und REMOVE; REMOVE
  löscht die Datei. Ein Plugin nur in `e2sPlugin.all` (ohne Datei) wird nur entfernt.
- **Blaue Electribe 2:** ihr FatFs hat kein `f_unlink` (siehe unten). REMOVE entfernt das Plugin aus `e2sPlugin.all`, die Datei bleibt,
  MANAGE PLUGINS meldet "file stays on card".

## Löschen auf der Karte (gemessen)

| Was | Ergebnis | Stand |
|---|---|---|
| `f_unlink` der Firmware | `0xC009E9B8(r0 = Pfad)`, Pfad mit `SD:` wie bei `f_open`; dieselbe Stelle in Hacktribe und Korg rot | **hergeleitet** aus [virtuelle SD](../hintergrund/virtuelle-sd.md) und `tools/patch/blech_sysex.py:FS_UNLINK` (FILE DELETE), dort schon gemessen |
| REMOVE auf `a.blech` (125 Byte), Hacktribe und Korg rot | Rückgabe 0, Status 0x51 "removed"; im Ordner danach kein Eintrag mehr, der Cluster der Datei ist frei (512 Byte mehr frei) | **gemessen** im Emulator mit virtueller Karte (`fat32.Volume`), 30.10. |
| REMOVE auf der blauen | kein Aufruf, Status 0x56 "file stays on card", Datei und freier Platz unverändert | **gemessen** im Emulator; dass das Abbild kein `f_unlink` hat, ist **hergeleitet** aus `fwmap` (FILE DELETE der SysEx, [Sample-Datei](../hintergrund/sample-datei.md)) |
| Ordner seit dem Lesen der Liste geändert | die Stelle der Datei wird neu gelesen und ihr Plugin-Name mit dem der Liste verglichen; weicht er ab, wird nichts gelöscht und nichts geladen, Status 0x57 "folder changed" | **gemessen** im Emulator (Stelle im RAM umgebogen) |
| Löschen am Gerät, Prüfung der Karte danach am Rechner | | **ungeprüft** |

## Wie die Liste ohne Namen auskommt

Bis jetzt lagen je Datei der Dateiname (32 Byte) und der Plugin-Name (16 Byte) im Arbeitsbereich des Kartenladers (`HOOK_CARD`, 16 mal
48 Byte). 64 mal 48 Byte passen dort nicht hin. Jetzt bleiben nur der Plugin-Name (64 mal 16 Byte ab `HOOK_CARD + 0x300`, wo vorher
Ordnerobjekt, Dateiinfo, langer Name, Pfad und die Dateinamen lagen) und ein Byte je Datei: ihre Stelle unter den Namen, die wie eine Plugin-Datei
aussehen, in der Reihenfolge des Ordners (`LIST_ORD`). Ordnerobjekt, Dateiinfo, langer Name, Pfad, die Stellen und das Zeichen für
LIST FULL liegen in `LIST_WORK`, 0x150 Byte hinter der Prüfsummenliste in der Reserve MORE2 (`0xC0188D40`, FF in allen drei Abbildern,
`tools/patch/script_hooks.py`). Wer die Datei braucht (Laden, Beschreibung, REMOVE), liest den Ordner bis zu ihrer Stelle noch einmal
(`menu_find_listed`) und prüft ihren Plugin-Namen.

| Was | Wert | Stand |
|---|---|---|
| ENTER auf MANAGE PLUGINS, 16 Dateien | etwa 75 ms bis die Liste offen ist | **gemessen** im Emulator (Schritt 5 ms; die virtuelle Karte hat nicht die Zeiten einer echten) |
| 64 Dateien | etwa 0,9 s; das Öffnen jeder Datei sucht ihren Namen im Ordner von vorn, die Zeit wächst schneller als die Zahl | **gemessen** im Emulator |
| 70 und 200 Dateien | etwa 0,93 s, 64 gelistet, LIST FULL; nach der 65. Plugin-Datei liest die Liste nicht weiter | **gemessen** im Emulator |
| Dauer am Gerät | | **ungeprüft** |

## Geprüft

`tools/emu/script_cases.py`, `manage_cases`: 70 Dateien (64 in der Liste in der Reihenfolge des Ordners, LIST FULL als letzte Seite,
ENTER dort tut nichts, die 64. lädt mit dem Hauptrad), 20 Dateien (alle, kein LIST FULL), REMOVE eines geladenen Plugins mit Datei
(rot: Datei weg, die andere bleibt, Liste ohne es; blau: Datei bleibt, Meldung), REMOVE eines Plugins, das nur eine Datei ist, Ordner
geändert. `import_cases`: OFF behält die Datei, das Plugin lädt danach wieder. Hacktribe, Korg rot und Korg blau.
