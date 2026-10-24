# Sync Groups: Patterns verketten, Live-Änderungen mitnehmen (19.10.)

Wunsch: Patterns bekommen eine Sync Group (OFF, 1 bis 999). Patterns derselben Gruppe wechseln ohne MENU-Bestätigung am Ende
der Sequenz, und was live verändert wurde, geht beim Wechsel mit (nur im RAM): wer eine Melodie hochpitcht oder die Modulation
dreht und dann wechselt, hört keinen Sprung. Zuerst als Mute Group gebaut (nur die Part-Mutes), am selben Tag erweitert und
umbenannt. Gebaut und im Emulator geprüft (Hacktribe und rot), am Gerät nicht. Auf der blauen seit 24.10. ([Messung](2026-10-24-blau-sync-group.md)); bis dahin nicht, weil dort das Laden eines
Patterns nicht gemessen.

## Wo die Gruppe steht

- Als u16 little endian bei Byte `0x3B80` des Pattern-Blocks. OFF ist 0: keine Gruppe, kein Abgleich.
- Der Bereich `0x3B03` bis `0x3BFB` ist in allen 250 Patterns des Flash-Dumps 0. Dass dort kein Feld liegt, dessen Vorgabe 0 ist,
  zeigt die Firmware selbst:
  - Im Code (Hacktribe und rot, gleich) greift die Firmware am Ende des Blocks nur auf `0x3B00` (Chain To, u16), `0x3B02`
    (Chain Repeat) und `0x3BFC` (Endkennung `PTED`) zu. Gesucht: jede Konstante zwischen `0x3AF0` und `0x3C10` als Operand oder
    im Literal-Pool. Auch der Vergleich von Pattern und Bank bei `0xC004C84C` liest dort nur Chain To und Chain Repeat.
  - Im Emulator (unveränderte Hacktribe-Firmware, Flash vom 09.10., Lese- und Schreibwächter auf `0x3B03..0x3BFB` im Pattern im
    RAM und in allen 250 Bank-Plätzen): Abspielen, Wechseln, Menü durchdrehen, Stoppen lesen dort nichts. Geschrieben wird nur
    vom `memcpy` des Ladens.
  - Nicht geprüft: ob der Bereich im `.e2spat`-Export und im Pattern-SysEx mitgeht.
- Speichern und Laden kopieren den ganzen Block (`0xC004C28C` und `0xC004AB84` je `0x4000` Byte), die Gruppe geht also mit
  dem Pattern in die Bank und den Flash.
- Eingestellt wird sie im Menü BLECH, FEATURES, SYNC GROUP. Sie gilt sofort im Pattern im RAM; das Pattern ist damit
  ungespeichert, WRITE oder EXIT + WRITE behält sie.

## Der Patch (`tools/patch/pattern_switch.py`)

- **Rad beim Spielen:** liegt das gewählte Pattern in der Gruppe des laufenden (Gruppe im RAM, die des anderen in der Bank,
  beide nicht 0), ist es sofort bestätigt wie mit MENU: unten NEXT:, Program Change geht raus, Start am Sequenzende. Der
  nächste Dreh nimmt diese Bestätigung zurück (`S_AUTO`), ein Pattern außerhalb der Gruppe wartet wieder mit VIEW: auf MENU.
- **Der Abgleich:** das Laden eines Patterns kopiert mit `memcpy(Pattern + 4, Quelle, 0x4000)` an `0xC004AC44`. Der Haken
  dort merkt sich bei jedem Laden aus der Bank den Bank-Platz (`S_LOADED`, auch beim Laden während des Starts). Beim Wechsel
  zwischen zwei Patterns derselben Gruppe vergleicht er das Pattern im RAM mit diesem Platz. Jeder Wert, der dort abweicht,
  kommt ins neue Pattern, die übrigen behält das neue Pattern, wie es gespeichert ist. Übernommen wird der Wert, wie er gerade
  klingt, nicht der Abstand. Das geschieht, bevor die Firmware das neue Pattern anwendet; sie übernimmt die Werte also, als
  wären sie gespeichert.
- **Was mitgeht:** Byte 1 bis `0x2F` jedes Parts (Mute und Klang: Sample, Filter, Cutoff, Resonance, EG, Modulation, Amp,
  Pan, Groove, IFX, Pitch, Glide und die übrigen Part-Werte), dazu Tempo, Swing, Lautstärke, MFX mit Pad X und Y, Byte 64,
  HOLD und Alternate. Tempo und Sample-Nummer werden als ganze 16-Bit-Werte übernommen: byteweise ergäbe ein geändertes
  unteres Byte mit dem oberen des neuen Patterns einen falschen Wert.
- **Was nicht mitgeht:** Steps und Noten, Motion-Daten, Name, Länge, Beat, Tonart, Tonleiter, Chord Set, Chain, die Gruppe
  selbst, Byte 0 der Parts (Last Step) und Byte `0x3C` (Pad berührt, das setzt die Firmware beim Laden selbst).
- Puffer: `0xC0180C00`, 763 Byte zwischen Code und Zustand, nur im RAM.
- Gilt bei jedem Laden innerhalb einer Gruppe, auch wenn ein Pad oder MIDI das Pattern wählt. Nicht mit EXIT beim Einschalten.
- Grenze: wird ein Pattern mit WRITE an einen anderen Platz gespeichert, vergleicht der nächste Wechsel noch mit dem Platz, aus
  dem es geladen wurde.

## Geprüft (`tools/emu/pswitch_cases.py`, `case_sync_group`; `tools/emu/menu_cases.py`)

Nach dem Start ist der geladene Bank-Platz gemerkt. Gruppe 7 nach 7: sofort bestätigt (NEXT:, ein Program Change), am
Sequenzende gewechselt. Live geändert waren zwei Mutes, Pitch und Mod Depth von Part 1, die Sample-Nummer (nur das untere Byte),
das Tempo und ein Step: alle Werte bis auf den Step kommen an, die Sample-Nummer als 0x0106 und nicht gemischt, ein nicht
angefasster Cutoff bleibt der des neuen Patterns, der Step auch. Weiter auf ein Pattern ohne Gruppe: nur VIEW:, auf das nächste
der Gruppe wieder bestätigt, zurück nimmt es zurück. Mit MENU in ein Pattern ohne Gruppe: es gleicht seinem Bank-Platz. Mit EXIT
beim Einschalten: die Firmware wie immer. Die Menüseite schreibt die Gruppe ins Pattern im RAM (3, dann OFF).
