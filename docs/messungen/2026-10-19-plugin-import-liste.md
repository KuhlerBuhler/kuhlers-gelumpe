# IMPORT PLUGIN als Liste mit Namen und Beschreibung (19.10.)

Wunsch: statt der Dateinamen eine Liste mit den Namen der Plugins, ENTER zeigt die Beschreibung (das Rad scrollt sie), ENTER
schaltet das Plugin ON oder OFF, darunter steht der Stand. Gebaut und im Emulator geprüft (Hacktribe, rote und blaue Firmware),
am Gerät nicht.

## Die Beschreibung in der Datei

- Der Editor schreibt sie beim Export in die `.blech`: direkt hinter dem Block `GDSC`, Länge (u32), ASCII-Text, dann wie bisher
  `GSRC` mit dem Quelltext (`packBlech` in `src/script/archive.mjs`, Format `DESC_TRAILER` in `data/script/contract.mjs`).
- Der Text sind die `//`-Zeilen ganz oben im Plugin-Code, umgebrochen auf 20 Zeichen (die Schrift des Displays ist 6 Pixel
  breit, rechts bleibt Platz für die Pfeile), Umlaute als ae, oe, ue, ss, höchstens 2047 Byte. Alle Vorlagen haben so einen
  Kopfkommentar und damit eine Beschreibung.
- Ein älteres BLECH lädt die neue Datei wie vorher: es liest nur den Block, alles dahinter ignoriert es.

## Am Gerät (`tools/patch/script_menu.s`)

- ENTER auf IMPORT PLUGIN liest den Ordner (bis 16 Dateien). Jede `*.blech` wird geöffnet und ihr Kopf gelesen; in die Liste
  kommt der Name aus dem Kopf. Dateien ohne Plugin-Kopf fehlen jetzt in der Liste (vorher standen sie drin und meldeten beim
  Laden "not a plugin").
- In der Liste: oben der Name, darunter der Stand (ON, OFF, FAULT, ENTER=ALLOW). Den Stand liefert das geladene Plugin mit
  gleichem Namen; ist keins geladen, steht OFF.
- ENTER öffnet das Plugin: die Beschreibung wird hinter dem Block aus der Datei gelesen (in Stücken von 1 KiB in den
  Kartenbereich, der Block selbst wird dabei nur überlesen). Gezeichnet wird ins Bild der Laufzeit, das `script_display_blit`
  wie bei Blechy auf dem BLECH-Bildschirm zeigt; die drei Textzeilen der Firmware bleiben leer. Beim Verlassen zeichnet die
  Firmware ihren Bildschirm ganz neu (`UI_REDRAW`).
- ENTER schaltet: nicht geladen lädt und startet (der Weg des alten Imports), läuft geht aus, aus geht an, fremd wird erlaubt.
  WRITE speichert die Einstellungen wie auf der Seite des Plugins.

## Nebenbei gefunden: das Speicherbild

Das Bild der dauerhaften Werte (`korg.store`) liegt im selben Puffer, in den der Import die Datei liest (`HOOK_INPUT`). Der
alte Import hat es überschrieben; das nächste `korg.store.save()` hätte dann die Werte aller nicht geladenen Plugins
verloren. Ohne `e2sPlugin.all` auf der Karte war das Bild sogar nie gelesen worden. Jetzt liest der Import das Bild nach dem
Laden neu von der Karte (`script_store_load` mit einem Eintrag als zweitem Argument), und das neue Plugin bekommt dabei seine
gespeicherten Werte, bevor sein Start läuft.

## Geprüft (`tools/emu/script_cases.py`, `import_cases`)

Liste mit Namen und ohne fremde Dateien, Beschreibung im Bild (8 Zeilen, das Rad scrollt bis zur letzten Seite und zurück),
Laden und Starten, das Speicherbild danach gleich der Datei auf der Karte, aus und wieder an, EXIT zurück in die Liste (dort ON)
und auf die Seite, fremdes Plugin wartet und wird erlaubt, kaputter Block abgelehnt, nach dem Verlassen läuft das Plugin, keine
Dateien, Plugins ausgeschaltet. Alle grün auf Hacktribe, rot und blau.
