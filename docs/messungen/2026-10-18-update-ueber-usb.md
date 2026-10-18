# Update über USB (18.10.)

Wunsch vom 18.10.: Kabel ran, GELUMPE holt die Firmware-Datei von der Karte, patcht sie mit dem neuesten BLECH und legt
sie zurück, ohne die Karte umzustecken.

## Weg

- **Der Flash wird nicht über MIDI geschrieben.** Ein abgebrochenes Schreiben der Firmware wäre ein kaputtes Gerät, und
  BLECH kann bewusst keinen Flash schreiben. GELUMPE schreibt nur die Datei auf die Karte; den Flash schreibt Korgs eigenes
  Update (DATA UTILITY > SOFTWARE UPDATE), wie bisher.
- **Zwei neue BLECH-Befehle** (`tools/patch/blech_sysex.py`): `0x65` FILE READ (Offset, Länge, Antwort mit Größe) und `0x66`
  FILE BEGIN (Offset, Länge, CRC, danach WRITE DATA wie für RAM). Sie erreichen genau zwei Dateien:
  `KORG/<Ordner>/System/SYSTEM.VSB` und daneben `ORIGINAL.BIN` (Bit 31 des Offsets). Der Pfad kommt aus der Funktion der
  Firmware, mit der auch ihr Update ihn baut (`0xC0035720`, Synth `0xC003256C`): "KORG/blechtribe/" bzw. "KORG/electribe/".
  Ein erster Block bei Offset 0 legt die Datei neu an, jeder Block wird von der Karte zurückgelesen und seine CRC geschickt.
  Offset plus Länge höchstens `0x200100`.
- **ORIGINAL.BIN:** Eine schon gepatchte Datei kann der Patcher nicht noch einmal patchen. Beim ersten Update über USB legt
  GELUMPE die unveränderte Datei als `ORIGINAL.BIN` neben die neue `SYSTEM.VSB`; jedes weitere Update startet von ihr. Keine
  Endung `.VSB`, damit kein Updater sie nimmt (der blaue liest auch `BOOT.VSB`, `USER.VSB`, `PCM.VSB`).
- **App:** Patcher-Seite, "Vom Gerät über USB holen" und nach bestandener Prüfung "Über USB aufs Gerät schreiben"
  (`src/usb-update.mjs`, `src/sender.mjs`, `src/protocol.mjs`). Auch eine hineingezogene Datei kann so aufs Gerät; dann kommt
  sie selbst als `ORIGINAL.BIN` mit.

## Gemessen

| Aussage | Status | Beleg |
|---|---|---|
| Im Datei-Objekt von FatFs steht die Größe bei `+0x0C` (0x224 Byte groß) | gemessen, beide Builds | Datei mit 123457 Byte geöffnet, Objekt gelesen |
| Die Firmware nutzt die Funktionsbytes `0x0E`, `0x10`, `0x11`, `0x1C`, `0x40`, `0x41`, `0x4C`, `0x51`, Hacktribe `0x52` bis `0x57`; `0x65` und `0x66` sind frei | gelesen | Sortierfunktion `0xC0026A8C` |
| Lesen, Schreiben in Blöcken, Zurücklesen, neu anlegen, Grenzen, ORIGINAL.BIN, ohne Karte Status 6, mit EXIT keine Antwort | gemessen im Emulator | `sysex:file_*`, Hacktribe 8 von 8, Blau im Satz 24 von 24 |
| Die blauen Stellen fand das Werkzeug (`tools/patch/fwmap.py`) genau dort, wo ich sie im Code gelesen hatte (FatFs `0xC008A6B8`, `0xC008A8CC`, `0xC008AB10`, `0xC008AF34`, `0xC008AF5C`, Ordner `0xC003256C`, Freigabe `0xC008CF4C`) | gemessen | `blech_sysex.py --build synth --listing` |

Nicht am Gerät geprüft. Das USB-Update geht erst, wenn ein BLECH mit diesen Befehlen drauf ist; die erste Installation bleibt
der Weg über die Karte.
