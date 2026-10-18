# Plugin bleibt aus (18.10.)

**Rückmeldung vom Gerät (Pascal, 18.10.).** Plugins ausgeschaltet, EXPORT ALL, Gerät neu gestartet: die Plugins waren
wieder an.

**Ursache (Code gelesen).** Der Aus-Zustand stand nur im RAM (`SCRIPT_ENTRY_STATE` LOADED statt ARMED). Weder die
Einstellungsdatei noch `e2sPlugin.all` hielten ihn, und der Lader (`card_start` in `tools/patch/script_card.s`) startet
beim Einschalten jedes erlaubte Plugin.

**Neu.**

- Die Prüfsummenliste der Einstellungsdatei hält neben den erlaubten fremden Blöcken für jedes ausgeschaltete Plugin
  seine Blockprüfsumme invertiert (`mvn`). Das Format bleibt Version 2; ein älteres BLECH liest die Einträge als
  erlaubte Prüfsummen, die nie passen. Die Liste teilt sich die 16 Plätze.
- Vor jedem Speichern gleicht `menu_off_sync` die Marken mit den geladenen Plugins ab. EXPORT ALL speichert die
  Einstellungen nach einem gelungenen Export mit (ohne Plugins schreibt es weiter nichts, `menu:export_without_scripts`),
  WRITE auf der Seite eines Plugins wie bisher.
- Der Lader startet ein Plugin mit Marke nicht (`menu_is_off`). Wird es eingeschaltet und hat seinen Start nie gerufen
  (für `EV_START` keine Kosten notiert), läuft der Start dann nach.
- Platz: der Menücode war 228 Byte zu groß. Die Kopien der Bildschirmtabelle und der Klassentabelle liegen jetzt am
  Ende des Codebereichs (`0xC01ADF00` und `0xC01ADFB8` statt `0xC01ADE00` und `0xC01ADF00`), die Lücke dahinter war
  ungenutzt.

**Gemessen (Emulator, `test/script-runtime.test.mjs` mit Pascals Hacktribe-Datei und dem Flash-Abbild vom 09.10.).**
`menu-plugin-bleibt-aus-nach-neustart`: Plugin aus, EXPORT ALL ("2 exported"), Neustart mit derselben Karte: Zustand 1
(aus), eine Taste zählt nicht, für den Start keine Kosten, die Seite zeigt OFF; eingeschaltet Zustand 2 und die Taste
zählt. `menu-plugin-an-mit-write-gespeichert`: danach WRITE auf der Seite, Neustart: an, die Taste zählt. Alle übrigen
Fälle der Datei blieben grün.

Nicht am Gerät geprüft.
