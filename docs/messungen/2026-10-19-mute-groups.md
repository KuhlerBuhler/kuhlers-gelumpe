# Mute Groups: Patterns verketten, Part-Mutes behalten (19.10.)

Wunsch: Patterns bekommen eine Mute Group (0 bis 999). Patterns derselben Gruppe wechseln ohne MENU-Bestätigung am Ende der
Sequenz, und die live gesetzten Part-Mutes gehen beim Wechsel mit (nur im RAM). So lassen sich mehrere Patterns live
aneinanderhängen. Gebaut und im Emulator geprüft (Hacktribe und rot), am Gerät nicht. Nicht auf der blauen: dort ist das Laden
eines Patterns nicht gemessen.

## Wo die Gruppe steht

- Als u16 little endian bei Byte `0x3B80` des Pattern-Blocks. Gemessen an den 250 Patterns des Flash-Dumps (Hacktribe, im
  Emulator aus der Bank gelesen): die Bytes `0x3B03` bis `0x3BFB` sind in allen 0, danach steht die Endkennung `PTED`. Der
  Bereich liegt innerhalb der `0x3C00` Byte des Records.
- Byte 15105 (`0x3B01`), der erste Kandidat, scheidet aus: es folgt direkt auf Chain To und ist vermutlich dessen oberes Byte.
- Speichern und Laden kopieren den ganzen Block (`0xC004C28C` und `0xC004AB84` je `0x4000` Byte), die Gruppe geht also mit
  dem Pattern in die Bank und den Flash. Ob sie auch in Pattern-Backups, `.e2spat` und den Pattern-SysEx mitgeht, ist nicht
  geprüft.
- Eingestellt wird sie im Menü BLECH, FEATURES, MUTE GROUP (OFF ist 0). Sie gilt sofort im Pattern im RAM; das Pattern ist
  damit ungespeichert, WRITE oder EXIT + WRITE behält sie.

## Der Patch (`tools/patch/pattern_switch.py`)

- **Rad beim Spielen:** liegt das gewählte Pattern in der Gruppe des laufenden (Gruppe im RAM, die des anderen in der Bank,
  beide nicht 0), ist es sofort bestätigt wie mit MENU: unten NEXT:, Program Change geht raus, Start am Sequenzende. Der
  nächste Dreh nimmt diese Bestätigung zurück (`S_AUTO`), ein Pattern außerhalb der Gruppe wartet wieder mit VIEW: auf MENU.
  Eine mit MENU gegebene Bestätigung bleibt wie bisher.
- **Mutes:** das Laden eines Patterns kopiert mit `memcpy(Pattern + 4, Quelle, 0x4000)` an `0xC004AC44` (gemessen: über diese
  Stelle laufen der Wechsel am Sequenzende und der Wechsel im Stand). Der Haken davor merkt sich die 16 Mute-Bytes (Byte 1
  jedes Parts) des Patterns im RAM, wenn altes und neues dieselbe Gruppe haben, kopiert und schreibt sie zurück, bevor die
  Firmware das Pattern anwendet. Die Firmware übernimmt die Mutes also, als wären sie gespeichert. Nicht mit EXIT beim
  Einschalten.
- Die Mutes werden bei jedem Laden innerhalb einer Gruppe übernommen, auch wenn ein Pad oder MIDI das Pattern wählt.

## Geprüft (`tools/emu/pswitch_cases.py`, `case_mute_group`; `tools/emu/menu_cases.py`)

Gruppe 7 nach 7: sofort bestätigt (NEXT:, ein Program Change), am Sequenzende gewechselt, alle 16 Mutes wie live gesetzt. Weiter
auf ein Pattern ohne Gruppe: nur VIEW:, auf das nächste der Gruppe wieder bestätigt, zurück nimmt es zurück. Mit MENU in ein
Pattern ohne Gruppe: dessen gespeicherte Mutes. Mit EXIT beim Einschalten: die Firmware wie immer. Die Menüseite schreibt die
Gruppe ins Pattern im RAM (3, dann OFF).
