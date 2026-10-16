# Global-Menü: welches Byte, welche Werte, welches Label

Stand 2026-10-14. Alles im Emulator (`tools/emu/machine.py`, Unicorn 2.1.4) mit der eigenen `SYSTEM.VSB`
(Sampler 2.02 mit Hacktribe) und dem eigenen Flash-Dump vom 9.10. Am Gerät nichts getan, nichts
geschrieben (kein WRITE, nichts im Flash, nur der Arbeitsspeicher des Emulators). Markierungen:
**gemessen** (Emulator), **offen**.

## Methode

- **Gemessen:** Boot, 6 s Gerätezeit, MENU, Edit ► bis zum Global-Eintrag, MENU (Bildschirm 9). Auf
  jeder Seite VALUE (Panel-Nachricht `01 00 00 delta`) zuerst bis zum kleinsten, dann bis zum größten
  Wert gedreht, nach jedem Schritt das lebende Globals-Objekt (`*0xC033E6A0 + 4`, 256 Byte, beginnt mit
  `GLST`) und das Display (`m.fb`) festgehalten. Ein Bereich ist zu Ende, wenn sich nach zwei Schritten
  weder Block noch Display ändern. Das Display wurde als Bild gelesen, die Anzeigetexte unten stehen
  so da, wie sie erscheinen.
- **Gemessen:** Das Menü hat im Global-Eintrag **20 Seiten** ("n/20" im Kopf, Seitenindex ab 0 ist n minus 1).
  Die 29 ist die Zahl der Menüeinträge insgesamt (Pattern 15, Part 8, dazu Global, Event,
  Data Util, Step, Part Util, Sample je ein Eintrag; Edit ► ging 29 Schritte bis zum Anfang zurück). Seite 20
  heißt XY CALIBRATION.
- **Gemessen:** Jede der Seiten 1 bis 19 ändert **genau ein Byte** des Blocks, die Seite 20 keines. Über alle
  Schritte aller Seiten hat sich sonst kein einziges Byte verändert (Vergleich über alle 256 Byte, auch `GLST`
  und `GLED` blieben).
- **Gemessen:** Das Display zeigt "ORIG" bei dem Wert, der beim Start im Block stand. Auf allen 19 Seiten
  erschien es bei genau einem Schritt, und zwar bei dem Byte aus dem Dump vom 9.10. (zum Beispiel Seite 4 beim Byte 9,
  angezeigt Kanal 10). Das ist die Gegenprobe, dass das gelesene Byte das ist, das die Seite anzeigt.

## Tabelle

Offset als Hex und dezimal (so steht er in `data/map/global.mjs`). Werte: Byte, danach die Anzeige.

| Seite | Anzeige | Offset | Bereich des Bytes | Byte, Anzeige |
|---:|---|---|---|---|
| 1 | TRIGGER MODE | `0x1d` (29) | 0 bis 2 | 0 Normal, 1 Seq 1st, 2 Seq Play |
| 2 | VELOCITY CURVE | `0x1b` (27) | 0 bis 3 | 0 Heavy, 1 Normal, 2 Light, 3 Const96 |
| 3 | CLOCK MODE | `0x28` (40) | 0 bis 4 | 0 Internal, 1 Auto, 2 External USB, 3 External MIDI, 4 External Sync |
| 4 | GLOBAL MIDI CH. | `0x29` (41) | 0 bis 15 | Byte plus 1, angezeigt 01 bis 16 (0 gibt 01, 8 gibt 09, 15 gibt 16) |
| 5 | MIDI RECEIVE FILTER | `0x2b` (43) | 0 bis 2 | 0 Off, 1 Short, 2 Short + Program |
| 6 | MIDI SEND FILTER | `0x2a` (42) | 0 bis 2 | 0 Off, 1 Short, 2 Short + Program |
| 7 | SYNC POLARITY | `0x11` (17) | 0 bis 1 | 0 Hi, 1 Lo |
| 8 | SYNC UNIT | `0x12` (18) | 0 bis 1 | 0 "1 Step", 1 "2 Steps" |
| 9 | METRONOME | `0x10` (16) | 0 bis 4 | 0 Off, 1 Rec 0, 2 Rec 1, 3 Rec 2, 4 On |
| 10 | TEMPO LOCK | `0x24` (36) | 0 bis 1 | 0 Off, 1 On |
| 11 | KNOB MODE | `0x1c` (28) | 0 bis 2 | 0 Jump, 1 Catch, 2 Value Scale |
| 12 | TOUCH SCALE RANGE | `0x26` (38) | **1 bis 4** | Byte = Oktaven, angezeigt "1 Oct" bis "4 Oct" |
| 13 | LCD CONTRAST | `0x1e` (30) | **18 bis 42** | Byte minus 17, angezeigt 1 bis 25 (18 gibt 1, 19 gibt 2, 30 gibt 13, 41 gibt 24, 42 gibt 25) |
| 14 | AUDIO IN THRU | `0x14` (20) | 0 bis 1 | 0 Off, 1 On |
| 15 | BATTERY TYPE | `0x20` (32) | 0 bis 1 | 0 Ni-MH, 1 Alkali |
| 16 | AUTO POWER OFF | `0x21` (33) | 0 bis 1 | 0 Disable, 1 4 hours |
| 17 | POWER SAVE MODE | `0x25` (37) | 0 bis 2 | 0 Disable, 1 Auto, 2 Enable |
| 18 | PTN. CHANGE LOCK | `0x13` (19) | 0 bis 1 | 0 Off, 1 On |
| 19 | CHAIN MODE | `0x1f` (31) | 0 bis 1 | 0 Off, 1 On |
| 20 | XY CALIBRATION | keines | | Anzeige "press [ Enter ]", eine Aktion, kein Wert |

19 Felder in 19 Bytes gemessen. Die Offsets stimmen mit der zweiten Tabelle in
`2026-10-13-globals-zurueckgesetzt.md` überein (dort ohne Labels und Werte).

## Was gegenüber der alten Karte anders ist

- **Neu (3 Felder):** Offset 19 (PTN. CHANGE LOCK), 31 (CHAIN MODE) und 36 (TEMPO LOCK) standen nicht in der Karte.
- **Falscher Bereich, LCD CONTRAST (Offset 30):** die Karte nahm 0 bis 24 mit "Byte plus 1" an. Gemessen ist
  das Byte 18 bis 42, die Anzeige Byte minus 17. Neuer Umwandler `contrast`.
- **Falscher Bereich, TOUCH SCALE RANGE (Offset 38):** die Karte nahm 0 bis 3 an. Gemessen ist 1 bis 4, 0 ist am
  Gerät nicht einstellbar. Der Umwandler `octaves` zählt jetzt ab 1.
- **Vertauscht, MIDI-Filter:** die Karte legte den Empfangsfilter auf Byte 42 und den Sendefilter auf 43.
  Gemessen ist es umgekehrt: Seite MIDI RECEIVE FILTER ändert Byte 43, MIDI SEND FILTER Byte 42. Die Karte ist
  angepasst. Siehe die nächste Gegenprobe.
- **Anzeigetexte, die von den deutschen Namen der Karte abweichen** (Karte bleibt, die Zuordnung der Werte stimmt):
  SYNC POLARITY zeigt Hi und Lo (die Karte sagt steigend und fallend; welches welches ist, ist nicht gemessen),
  AUTO POWER OFF Disable und 4 hours, POWER SAVE Disable, Auto und Enable.

## Gegenprobe der MIDI-Filter (Verhalten, nicht nur Label)

Weil sich die Notiz vom 16.9. (`2026-09-16-global-dump.md`: "Byte 42 (Receive Filter)") und diese Messung
widersprechen, wurde geprüft, welches Byte was tut. Im Emulator die beiden Bytes im lebenden Block gesetzt
(die anderen auf 0), dann:

- **Gemessen, Empfang:** Controller 7 mit wechselndem Wert auf MIDI-Kanal 1, 5 und 10 in den DIN-Eingang geschickt,
  Pattern-Puffer (16 KiB) vorher und nachher verglichen. Byte `0x2a` auf 0, 1 oder 2: der Wert steht danach
  in Part 1, 5 und 10 (Part-Byte 24, Pufferstellen 2072, 5336 und 9416). Byte `0x2b` auf 0: gleich. Byte `0x2b`
  auf 1 oder 2: keine Änderung im Puffer. Der Empfangsfilter ist also `0x2b`.
- **Gemessen, Senden:** den PAN-Regler und den LEVEL-Regler bewegt, die Bytes am DIN-Ausgang mitgeschrieben
  (ohne Clock-Byte `F8`). Byte `0x2a` auf 0: eine Controller-Meldung (`B0 0A xx`) sowie Bank-Select und Programmwechsel
  auf Kanal 10 (`B9 00 00`, `B9 20 00`, `C9 xx`). Auf 1: der Controller fehlt, Bank und Programm kommen. Auf 2: gar
  nichts. Byte `0x2b` auf 0, 1, 2: immer Bank und Programm, kein Unterschied. Der Sendefilter ist also `0x2a`.
- **Offen:** wieso die Notiz vom 16.9. Byte 42 als Empfangsfilter führte. Dort stand Byte 42 auf Short, solange
  kein Controller ankam, und auf Off, als alle 14 Controller wirkten (`2026-09-16-cc-map.md`: Voraussetzung
  Receive Filter Off). Hergeleitet, nicht gemessen: die Zuordnung dort kann aus Korgs Tabelle statt aus der
  Anzeige stammen, oder am Gerät wurden damals beide Filter gewechselt. Am Gerät nicht nachgemessen. Zum Klären:
  auf der Seite MIDI RECEIVE FILTER Short einstellen (ohne WRITE) und `0x0E` anfragen; steht die 1 an Offset 43,
  stimmt der Emulator mit dem Gerät überein.

## Bytes, die kein Menü-Eintrag erreicht (bleiben unbekannt)

Offset 0 bis 3 ist `GLST`, 252 bis 255 ist `GLED` (beide immer gleich, `readonly`). Alles andere, was
nicht in der Tabelle steht, bleibt `source: unknown`, `edit: expert`:

| Bytes | Länge | Befund |
|---|---:|---|
| 4 bis 15 | 12 | im lebenden Block ist Byte 5 belegt (nicht null), Bedeutung offen |
| 21 bis 26 | 6 | im lebenden Block ist Byte 24 belegt, Bedeutung offen |
| 34 und 35 | 2 | beim Start null, Bedeutung offen |
| 39 | 1 | beim Start null, Bedeutung offen |
| 44 bis 251 | 208 | beim Start null, Bedeutung offen |

- **Gemessen:** Dass keine andere Bedienung diese Bytes ändert, wurde ebenfalls geprüft. Auf dem Hauptbildschirm
  Regler 0 bis 13 auf 0, 255 und 128, die vier anderen Drehgeber vor und zurück, alle Tasten 0x00 bis 0x21 außer WRITE
  (darunter PLAY und STOP): der Block blieb gleich. Danach reagierte MENU in diesem Lauf nicht mehr (Zustand der Tasten ungeklärt),
  darum ein zweiter Lauf: alle 29 Menüeinträge mit Edit ► durchgegangen, auf jedem außer Global VALUE ein und zurück
  gedreht (Pattern 15 Seiten, Part 8 Seiten, die Köpfe von Event, Data Util, Step, Part Util, Sample): der Block blieb
  gleich. Nicht geprüft: was die Menüeinträge mit MENU oder EXIT tun (zum Beispiel Data Util ausführen), und was
  das Gerät sonst im Betrieb in die Globals schreibt.
- **Offen:** der Wert der belegten Bytes 5 und 24 wird hier nicht festgehalten; er hängt von der Vorgabe der Firmware
  ab und gehört nicht in das Repository.

## Grenzen

- Nur im Emulator gemessen, nicht am Gerät. Die Seiten und das Display kommen aus derselben Firmware wie am
  Gerät, der Menüaufbau ist durch `2026-10-13-globals-zurueckgesetzt.md` für Seite 19 am Gerät gegengeprüft.
- Die Wirkung der Werte (Clock, Sync, Velocity, Strom) wurde außer bei den MIDI-Filtern nicht geprüft, nur,
  welches Byte die Seite ändert und welche Anzeige zu welchem Byte gehört.
- Der Dump meldet den gespeicherten Stand, nicht zwingend den laufenden (Notiz zu Clock Mode vom 16.9.). Hier ist das
  lebende Objekt gelesen, das die Seiten ändern; ob es dem Dump desselben Moments entspricht, ist nicht für alle Seiten
  geprüft.

## Belege

Die Messskripte liegen nicht im Repository.

| Aussage | Prüfung |
|---|---|
| 20 Seiten, je ein Byte | Emulator, VALUE bis zu beiden Enden je Seite, Vergleich aller 256 Byte nach jedem Schritt |
| Werte und Anzeigetexte | Display jedes Schritts als Bild gelesen (`Machine.fb`) |
| Empfangsfilter ist `0x2b` | Controller 7 in den DIN-Eingang, Pattern-Puffer verglichen, Byte im lebenden Block gesetzt |
| Sendefilter ist `0x2a` | Regler bewegt, `uart[UART1]["tx"]` ohne `F8` mitgeschrieben |
| Andere Menüs schreiben nicht in die Globals | 29 Einträge, VALUE ein und zurück, Block verglichen |
