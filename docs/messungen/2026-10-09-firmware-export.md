# Geänderte Firmware als Datei, im Emulator gebootet

Stand 2026-10-09. Gemessen im Emulator mit der eigenen SYSTEM.VSB und dem
eigenen Flash (`2026-10-09-flash-dump.md`), über die Editor-Seite
(Playwright) und `tools/emu/machine.py`. Kein Gerät, nichts geflasht.

- **Gemessen:** In der Sidebar MFX 2 von „Tape Delay“ in „GELUMPE Delay“
  umbenannt und live gesendet (Rücklesen stimmt). Die Änderungsliste zeigt
  „MFX 2 Name: Tape Delay → GELUMPE Delay“. Der Export unterscheidet sich
  von der geladenen Datei in 13 Byte, alle im Namensfeld von MFX 2
  (Record-Offset `+0x1` bis `+0xD`), und besteht die Firmware-Erkennung
  (`identify`).
- **Gemessen:** „Im Emulator starten“ lädt die Kopie und startet neu, mit
  demselben Flash. Nach MENU und fünfmal Edit ► steht im Display
  „02 GELUMPE Delay“, ohne dass etwas live geschrieben wurde: der Name
  kommt aus der Datei.
- **Gemessen:** Ohne Flash-Dump spielt das leere Pattern Master 1
  („01 Mod Delay“). Der lokale Test benennt deshalb MFX 1 um und vergleicht
  das Display der Seite MFX TYPE mit und ohne Änderung.

**Nicht gemessen:** dass eine so geschriebene Datei am Gerät startet. Vor
dem Firmware-Schreiben für andere muss der Rückweg erprobt sein
(`2026-10-10-rueckweg-geuebt.md`, `2026-10-08-firmware-rueckweg.md`).
