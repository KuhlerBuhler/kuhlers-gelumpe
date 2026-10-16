# Ganzer Flash in einem Stand

Stand 2026-10-09. Eigenes Gerät, Sampler 2.02 mit Hacktribe, USB am
Linux-Laptop, Python mido. Skript: `tools/device/flash_dump.py`, vorher
gegen den Emulator geprüft (zwei Blöcke ab `0x220000`, Ergebnis gleich dem
emulierten Flash; Bereichsschutz lehnt `0xFFC000 + 0x8000` vor dem Senden
ab). Nur Lesebefehle: Gerätesuche und `0x55`. Die Datei liegt außerhalb des
Repositories.

## Lauf

- **Gemessen am Gerät:** Gerätesuche auf Kanal 10, Stand 2.2. Danach
  `[0x000000, 0x1000000)` in 1024 Blöcken à `0x4000` gelesen, zweimal
  hintereinander, keine fehlende Antwort. Kein Zugriff ab `0x1000000`.
- **Gemessen:** Je Durchgang 107,7 s, also rund 152 KiB/s. Am 7.10. lagen
  8 MiB bei 40,8 s (rund 200 KiB/s, `2026-10-07-werks-sample-flash.md`).
  **Nicht untersucht:** woher der Unterschied kommt. Dieses Skript fragt
  alle 5 ms nach Eingängen und hat immer nur einen Block unterwegs.
- **Gemessen:** Beide Durchgänge haben denselben SHA-256
  `e177a321c28a756c10f76228c686dbbf2666c644706db238abec4c46cd25452c`,
  nach der Übertragung auf den Mac unverändert.

- **Gemessen im Emulator:** Die Antwort auf ein Flash-Lesen trägt in Byte 6
  bis 8 `54 55 00`, also das gefragte Kommando wie beim RAM-Lesen
  (`54 52 00`).
- **Gemessen am Gerät, 9.10. abends:** Ein Flash-Lesen von 16 Byte ab
  `0x220000` antwortet ebenfalls mit `F0 42 39 00 01 24 54 55 00`.

## Vergleich mit den drei älteren Teilen

- **Gemessen:** Gegen die zusammengesetzten Teile `flash_0M_4M`,
  `flash_4M_8M` und `flash_8M_16M` unterscheiden sich 48 von 256
  64-KiB-Blöcken: `0x050000-0x070000`, `0x0B0000-0x0E0000`,
  `0x230000-0x3E0000`, `0x480000-0x4C0000`, `0x520000-0x560000`,
  `0x5A0000-0x5C0000`, `0x5D0000-0x630000`. Ab `0x800000` (Werks-Samples)
  ist alles gleich.
- **Zuordnung (aus `2026-10-07-werks-sample-flash.md`):** `0x230000` ist
  GLST (Globals), ab `0x240000` liegen die Nutzer-Patterns. Was bei
  `0x050000-0x0E0000` steht, ist nicht untersucht.

## Im Emulator

- **Gemessen:** Mit diesem Dump bootet die Firmware im Emulator zum
  Hauptbildschirm und beantwortet die Gerätesuche auf Kanal 10 wie das
  Gerät. Alle Tests in `npm run test:emu` laufen mit ihm als `E2_FLASH`.

## Freie Bereiche hinter den Nutzerdaten

- **Gemessen am Dump:** Große Bereiche nur aus `FF` außerhalb der Firmware:
  `0x660017` bis `0x6B0000` (319 KiB, direkt hinter den Werks-Patterns),
  `0x7C0002` bis `0x7DFFFE` (127 KiB) und `0xE5F013` bis `0x1000000`
  (1,6 MiB, direkt hinter den Audiodaten der Werks-Samplebank, die laut
  `2026-10-07-werks-sample-flash.md` bei `0xE5F013` enden). Dazu
  `0x750000` bis `0x7A9944` (358 KiB) aus `00`, Bedeutung offen.
- **Gemessen am Dump:** Im Vergleich mit den drei älteren Teilen
  (verschiedene Tage, dazwischen Pattern-Speichern und Firmware-Änderungen)
  ist keiner der drei `FF`-Bereiche anders.
- **Angabe, nicht gemessen:** Eigene Samples liegen auf der SD-Karte in
  `KORG/electribe/sampler/e2sSample.all` und werden bei jedem Start in den
  RAM geladen. Die Sample-Plätze 422 bis 500 sind eine Lücke im Dateiformat
  (Oe2sSLE, Issue 14), kein Speicherbereich.
- **Nicht gemessen:** dass die Firmware die drei Bereiche nie beschreibt.
