# 82. TOUCH SCALE RANGE 0: X spielt nur den Grundton

Wunsch (30.10.): Global > TOUCH SCALE RANGE bekommt einen Wert 0. Dann gibt es keinen Umfang mehr, X auf dem Touchpad spielt
überall den Grundton des Patterns (Vorgabe C4). Die Oktave der Tastatur (KEYBOARD + 1 und 4) verschiebt ihn, Y bleibt wie es ist,
mit Touch Scale allein und mit Gate Arp + Touch Scale.

Stand 2026-10-30: **für rot und blau gebaut, im Emulator geprüft, am Gerät offen** ([Messung](../messungen/2026-10-30-touch-scale-null.md)).

- Der Umfang ist ein Global (Byte 38), kein Pattern-Wert. Korgs Menü klemmt ihn auf 1 bis 4, die Anzeige kann `0 Oct` schon.
- Korgs eigene Rechnung gibt mit 0 schon einen festen Ton, aber eine Oktave unter der Tastatur (C3). Der Patch hebt ihn um eine
  Oktave, 11 Worte am Platz, kein eigener Code. Umfang 1 bis 4 spielen gemessen wie vorher.
- Alte Dateien tragen nie eine 0. Ein Block mit 0 auf Korgs Firmware spielt den Grundton eine Oktave tiefer, sonst nichts.

## Am Gerät zu testen

- Global > TOUCH SCALE RANGE bis 0, SHIFT + TOUCH SCALE, X an mehreren Stellen: immer C4.
- KEYBOARD + 4: C5, KEYBOARD + 1: tiefer. Tonart im Pattern auf D: D4.
- GATE ARP, Pad halten, Touchpad: Arp mit Pad-Note und Grundton, Y ändert die Länge.
- Aus- und einschalten: die 0 bleibt.
