# Meter: RAINBOW auch bei LOUD, im Tempo (24.10.)

Wunsch am Gerät: der volle Meter (METER LOUD) soll wie METER STILL auf RAINBOW stehen können, die Geschwindigkeit
dabei abhängig vom Tempo.

## Umsetzung

`tools/patch/script_menu.s`: LOUD hat jetzt wie STILL den Wert RAINBOW hinter der Palette. Der Farbton von LOUD
läuft in 1/256-Schritten, je 40-ms-Takt um `Tempo · 1,0923` (Tempo in Zehntel BPM aus `HW_TEMPO`), das ist eine
Runde je Takt (vier Schläge): bei 128 BPM rund 1,9 s. Die Farbe beider Regenbögen wird jetzt beim Abfragen aus dem
Farbton berechnet; die drei Bytes `MX_RGB` dafür sind frei geworden und halten die zwei Bytes der LOUD-Phase.

Gespeichert wird LOUD RAINBOW als Bit 0 von Byte 5 der Einstellungsdatei, die drei Bits von LOUD in den Flags
bleiben 0. Byte 5 war bisher immer 0 und wurde beim Lesen geprüft: eine ältere BLECH-Version verwirft eine Datei
mit LOUD RAINBOW und nimmt die andere Datei oder die Grundeinstellungen.

## Emulator

`tools/emu/menu_cases.py`, Fall `led_meter_loud_rainbow` (hacktribe 1.3 mit allen BLECH-Patches): Seite
`METER LOUD / RAINBOW`, laut zwei verschiedene Farben auf dem Farbkreis im Abstand von 0,5 s; Farbton-Schritte in
1 s bei 60 BPM 16375, bei 120 BPM 32750 (genau doppelt); nach WRITE Byte 5 = 1, Flags `0x3` (LOUD-Bits 0); nach
einem Neustart die Meter-Bytes `[0, 0, 0, 8]`. Alle 76 Fälle der LED- und Look-Gruppe bestehen.

Am Gerät noch nicht geprüft.
