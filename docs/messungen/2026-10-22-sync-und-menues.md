# Sync Group, MENU-Taste, Menüs und Kalibrierung (22.10.)

Wünsche vom Gerät, im Emulator gebaut und geprüft (Hacktribe, eigener Flash vom 09.10.). Am Gerät noch nicht geprüft.

## Sync Group: der ganze Stand geht mit

Vorher ging beim Wechsel innerhalb einer Gruppe nur mit, was live vom gespeicherten Stand des alten Patterns abwich. Am Gerät:
Pattern A ohne Kick, Pattern B mit Kick. Der Wechsel A nach B schaltete die Kick an, der Wechsel zurück wieder aus.

Jetzt geht der Stand des Patterns, das gespielt hat, immer mit, ob verändert oder nicht. Mitgenommen werden dieselben Werte wie
vorher: Part-Mutes und Klang der Parts, Tempo, Swing, Lautstärke und MFX. Die Steps bleiben die des neuen Patterns, so spielen die
Patterns einer Gruppe wie eines mit längerer Sequenz. Der Vergleich mit dem Bank-Platz (`S_LOADED`) entscheidet nur noch, ob es
ein Wechsel ist. Lädt man den Platz, aus dem das Pattern kam, geht nichts mit.

`pswitch_cases.py`, `case_sync_group`:

- `group_carries_the_state`: ein nicht angefasster Cutoff kommt jetzt aus dem alten Pattern (vorher blieb er der des neuen).
- `group_carries_back`: ein Mute, der im zweiten Pattern geändert wurde, kommt beim Wechsel zurück mit.

## Pad-Druck beim Wechsel

Der Druck ging nicht verloren. Mit dem alten Abgleich sprang der Mute beim Wechsel auf den gespeicherten Wert des neuen Patterns.
Ein Druck kurz danach schaltete dann diesen neuen Wert um und kam so beim Ausgangszustand an: es sah aus, als hätte er nicht
gewirkt.

Gemessen im Emulator: PART MUTE, Pad 1 zu zehn Zeitpunkten zwischen 0,3 s vor und 0,4 s nach dem Wechsel. Part 1 stand im
ersten Pattern auf 1, im zweiten gespeichert auf 0.

| Stand | vor dem Wechsel gedrückt | ab dem Wechsel gedrückt |
|---|---|---|
| develop (alter Abgleich) | 0 | 1 |
| jetzt | 0 | 0 |

Mit dem neuen Abgleich springt nichts mehr, der Druck wirkt zu jedem Zeitpunkt gleich. Das prüft
`pad_at_the_switch_toggles_what_played`: auf develop rot, jetzt grün.

## MENU blinkt, wo man drücken muss

Die LED-Verwaltung der Firmware kann Blinken selbst: `0xC0087710` (Verwaltung, LED, Modus, Dauer) mit Modus 2. Der Takt
`0xC0087740` kippt die Helligkeit dann alle Dauer-Takte von 40 ms. MENU ist LED 7. Gemessen auf dem Hauptbildschirm beim
Spielen: Modus 1, Helligkeit 0, also dunkel. Das Modus-Byte allein sagt nicht, ob eine LED leuchtet.

Der Patch pattern-switch setzt die LED nach jedem Wechsel seines Zustands:

- blinkend (Modus 2, Dauer 7, also 280 ms an, 280 ms aus), solange ein Pattern nur angesehen ist (VIEW:), auch gestoppt mit
  ungespeicherten Änderungen;
- leuchtend, sobald es bestätigt ist (NEXT:), auch durch die Sync Group;
- danach bekommt sie ihren Eintrag zurück, so wie die Firmware ihn hatte (Modus, Helligkeit, an), gesendet mit `force`.

Die drei Bytes vorher zu sichern war nötig: Mit Modus 1 und Helligkeit 255 blieb MENU nach dem Wechsel an. Gesetzt wird beim
Drehen, bei MENU, EXIT und STOP, bei Pad und Program Change und am Sequenzende (dort im Takt der Engine, wo die Firmware das
TAP-Blinken auch setzt).

`menu_led_shows_where_to_press`, als (Modus, Helligkeit):

| Moment | Wert |
|---|---|
| Spielen | (1, 0) |
| angesehen | (2, 0) |
| 0,3 s später | (2, 255) |
| bestätigt | (1, 255) |
| gewechselt | (1, 0) |

Die Firmware allein bleibt durchgehend bei (1, 0).

## SYNC GROUP ins Pattern Menü

Die Seite ist aus FEATURES herausgenommen und steht jetzt als Ebene 4 des BLECH-Bildschirms im Ring, gleich vor der ersten Seite
des Pattern Menüs:

- Das Schild sagt "Pattern", der Zähler 32/32.
- EDIT links auf der ersten Seite des Pattern Menüs führt zu ihr, EDIT rechts von Blechy auch.
- WRITE öffnet dort das Speichern des Patterns (Bildschirm 18) wie auf den Seiten des Pattern Menüs. Vorher speicherte WRITE im
  Menü BLECH nur die Einstellungen, nicht die Gruppe.

Die Firmware-Seiten des Pattern Menüs sind nicht angefasst, es gibt keinen neuen Haken. Auf der blauen gibt es die Seite nicht
(`HAS_SYNC`).

## SPLASH als eigene Gruppe

SPLASH IMPORT, SPLASH DRAW und SPLASH RESET sind Seiten der Gruppe SPLASH (Gruppe 9), eine Zeile in CUSTOMIZATION wie DISPLAY,
LED, PAD COLOR und POWER SAVE. EXIT führt auf diese Zeile zurück.

## Plugin-Menü wie Sample Edit

Vorbild ist SAMPLE EDIT der Firmware, im Emulator mit Samples von der Karte angesehen:

- die Seite `press  [ Enter ]`, ohne Sample "No Sample";
- ENTER öffnet die Seiten 1/10 bis 10/10, die im Kreis blättern: SELECT SAMPLE (das Rad wählt, große Schrift), RENAME, START
  POINT und weitere, DELETE SAMPLE zuletzt;
- EXIT führt zurück.

PLUGINS hat jetzt die Seiten RUNTIME, PLUGIN EDIT, EXPORT ALL und IMPORT PLUGIN. ENTER auf PLUGIN EDIT öffnet Ebene 5:

- SELECT PLUGIN mit dem Namen, das Rad wählt;
- STATE mit ON, OFF, Fehler oder WRITE=ALLOW, wie vorher die Seite des Plugins;
- die Seiten, die das Plugin mit `korg.menu.add` angelegt hat;
- DELETE PLUGIN.

DELETE PLUGIN fragt beim ersten ENTER ("Enter = delete"), das zweite löscht:

- Das Plugin hält an.
- Sein Block bekommt im RAM Bit 15 der Kopf-Flags. Damit lassen ihn die Liste, das Zählen und EXPORT aus.
- `e2sPlugin.all` wird neu geschrieben. Ist es das letzte Plugin, wird es eine Datei ohne Block. Der Lader nimmt sie an: Größe
  16, Prüfsumme 0, beides wie beim Schreiben.
- Die `*.blech` im Ordner bleibt.

Bekannte Grenze: Eine App des gelöschten Plugins steht bis zum nächsten Start noch unter GAMES oder TOOLS, mit dem Wert OFF.

## SHIFT + PART ERASE

Im Emulator würfelt die Kombination mit dem ganzen Satz (`dice_cases.py`, 13 von 13). Eine Rückmeldung über die LED von PART
ERASE war gebaut (Modus 3, einmal 320 ms) und ist wieder herausgenommen:

- Läuft Modus 3 ab, setzt der Takt Modus und Helligkeit auf 0.
- Die Firmware schreibt bei PART ERASE dann nur die Helligkeit und behält Modus 3.
- Im Emulator ging PART ERASE danach nicht mehr an.

Offen am Gerät: ob gewürfelt wird. Im TRIGGER-Modus zeigen die Pads keine Steps, zu hören ist es nur beim Spielen.

## Calibrate Display

Die Kalibrierung zeichnet jedes Bild direkt in den Bildspeicher. Wechselt man mit EDIT die Seite, zeichnet die Firmware nur ihre
eigenen Felder neu, die Kugeln blieben stehen. Jetzt merkt sich `M_CAL_ON` (Byte `0xFA` im Menüzustand), dass gezeichnet wurde.
Im ersten Bild ohne die Seite setzt `calibrate_off` einmal `UI_REDRAW`.

`next_page_clean`: Die nächste Seite ist in den Pages 1 bis 6 gleich der Firmware allein. Ohne den Fix weichen sie ab, schon die
ersten 8 Bytes von Page 1.
