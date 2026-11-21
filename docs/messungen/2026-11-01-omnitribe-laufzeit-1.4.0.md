# Laufzeit 1.4.0 auf einem fremden roten Gerät (Briefing Nat333, 1.11.2026)

Nat333 (TekkForge/Omnitribe) hat die Laufzeit aus v1.4.0 (`d7b812a4`) in eigene ROMs eingebaut
(Basis Korg Sampler 2.02 und Synth), mit `MORE3_START=0xC0191000` und `MORE3_END=0xC01A0000`, und
auf einem roten Sampler gemessen (Stub-Peek), Gegenproben im Emulator mit dem Flash-Abzug seines
Geräts. **Gemessen von Nat333**, nicht von uns. Hier steht, was wir übernehmen, was wir geprüft
haben und was offen ist. Die Adressen gelten für 1.4.0; seitdem liegt der Code der Laufzeit ab
`0xC0150300` (`tools/patch/script_hooks.py:MORE3_START`).

## Start-Haken laufen nicht (offen)

- `script_early_hook` (`0xC0038D34`) und `script_card_hook` (`0xC0038D68`) liefen bei ihm nie,
  Rahmen-, Eingangs- und Licht-Haken schon. Folge: `menu_arm` wird nie gerufen, kein BLECH im Ring,
  keine Plugins. Im Emulator laufen beide.
- `0xC0038D34` ist Slot 2 der Klasse mit Vtable `0xC00A7B38`, gerufen aus der Nachrichtenpumpe der
  Bildschirmverwaltung (`0xC002D79C`): ein Nachrichten-Handler des Lade-Bildschirms, kein fester
  Startbefehl.
- Gemessen nur beim Start über DFU und GDB aus dem Bootloader, kein Kaltstart aus dem Flash. Auf
  unserem roten Gerät laufen die Plugins nach dem Kaltstart (**hergeleitet**: betrifft uns
  wahrscheinlich nicht).
- Sein Ausweg `late_arm`: im Rahmen-Haken ab 100 Rahmen, wenn der Hauptbildschirm steht und die
  Laufzeit nicht scharf ist, `menu_arm_load` versuchen, nie nach EXIT beim Start. Patch angefragt.
- Stand 17.11.: `late_arm` ist nicht übernommen. Sein Patch dafür setzt auf 1.4.5 auf und legt eine feste Adresse
  (`0xC019F800`) in einen Bereich, den kein Patch anmeldet. Sein zweiter Patch (Redraw-Zeiger) ist durch #622 erledigt.

## Redraw-Byte hing am Flash-Inhalt (behoben)

Die feste Adresse `UI_REDRAW` (`0xC06C226C`) traf bei ihm das falsche Byte, weil spätere
Heap-Objekte mit dem Flash-Inhalt wandern (bei ihm 0x3320 höher). Nach dem Schließen einer App
blieb der Hauptbildschirm stehen. Seit #622 nimmt die Laufzeit `[SCREEN_MANAGER] + 0x10 + 0x4C`;
das Tick-Argument ist im Emulator auf Hacktribe, Korgs Rot und dem Blauen `[SCREEN_MANAGER] + 0x10`
(**gemessen**, Emulator), seine Adresse `0xC06C558C` passt dazu.

## Wer die Laufzeit an eine andere Stelle legt

- `0xC0189000` kollidiert mit `NA_SETTING` (`0xC0189F00`) und `PC_CODE` (`0xC018B000`).
- Die Laufzeit liest `VERSION_TEXT` (`0xC014FCF0`), `INIT_CODE` (`0xC014FD00`), `LP_CODE`
  (`0xC014FE00`) und `SP_CODE` (`0xC014FF00`) und erkennt an `FF`, dass der Patch fehlt
  (`tools/patch/script_menu.s`). Wer die Laufzeit verlegt, darf dort nichts ablegen.
- Mit der Laufzeit ist der oberste Menü-Ring länger: EXPORT PATTERN liegt 4 statt 2 Schritte
  EDIT◄ entfernt. Nur wichtig für Skripte, die blind blättern.

## Zahlen aus seinem Emulator

15 von 15 Katalog-Plugins liefen auf Sampler und Synth, 10 rahmengenau gleich unserer Laufzeit,
5 nutzen `korg.millis()` als Zufall. Auf der Synth meldet `ready` 2 Rahmen später.
