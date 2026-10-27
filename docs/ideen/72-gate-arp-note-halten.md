# 72. Plugin Gate Arp: Note halten, X wählt den Rhythmus

Wunsch: beim Gate Arp bleibt die gedrückte Note fest, X auf dem Touchpad steuert die Gate-Arp-Einstellung
aus dem Menü.

Stand 2026-10-27: **untersucht, im Emulator gemessen (rot und blau), nichts gebaut, am Gerät nichts.** Marker: **gemessen**,
**hergeleitet**, **ungeprüft**.

## Befund

- Gate Arp + Touch Scale: X wählt die Note, Y die Notenlänge, der Rhythmus kommt aus dem Menü. Nur Touch Scale: X ist die
  Note, Y nichts. Nur Gate Arp (Pad gehalten): X ist die Rate. (gemessen, 120 BPM)
- Menü: Pattern-Seite GATE ARP (oder SHIFT + GATE ARP), 50 Muster. Gespeichert im Pattern an **+0x35**, Werte 0 bis 49, rot
  und blau gleich. Noch nicht in der Gerätekarte, liegt im unbekannten Bereich `pattern.touchScale`
  (`data/map/pattern.mjs`). (gemessen)
- Wert direkt schreiben wirkt sofort im laufenden Spiel. (gemessen)
- Touchpad: Finger auf und ab sind Taste `0x22`, Bewegung ist Ereignistyp 5 mit x und y 0 bis 1023. Plugins bekommen
  `touch` schon heute. Maskenbit 5 verwirft nur die Bewegung, die Note spielt weiter, aber Y friert mit ein. (gemessen)
- Note festhalten durch Auslösen: `0xC004596C(x, y)` aus dem Bild-Hook hält die Note, Y ändert die Länge (blau
  `0xC003FC38`). Kosten: Y hinkt bis zu 40 ms nach. (gemessen)

## Fehlt in der Laufzeit (zusammen mit Idee 70, eine Plugin-API, API 10)

- `korg.gateArp(wert)` (0 bis 49), oder ein geprüftes Schreiben eines Pattern-Bytes.
- `korg.touchLockX(x | -1)`: der Eingangsfilter ersetzt X durch einen festen Wert, Y bleibt echt. Besser als Auslösen, weil
  nichts nachhinkt. (hergeleitet, nicht gemessen)
- Gemeinsam mit 70: abfangen, auslösen, beim Beenden alles zurückgeben (wie `ledHold`).

## Plan

1. `pattern.gateArp` (+0x35, 0 bis 49) in die Gerätekarte, mit Messung.
2. `korg.gateArp`.
3. X festhalten im Eingangsfilter, beim Beenden frei.
4. Plugin: Schalter im Plugin-Menü. Erste Berührung merkt die Note, danach X auf 0 bis 49. Alter Wert zurück bei Finger weg,
   Patternwechsel und Plugin-Ende.

## Risiken und am Gerät zu testen

- Speichert WRITE den geänderten Rhythmus mit? (ungeprüft)
- Eine offene GATE-ARP-Menüseite aktualisiert sich nicht.
- Schnelles Wischen kann den Ring mit 16 Einträgen überlaufen lassen.
- BLECH macht Gate Arp allein zu Gate Arp + Touch Scale (`docs/entscheidungen.md`), beide Modi prüfen.
