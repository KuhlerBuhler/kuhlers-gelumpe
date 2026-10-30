# 79. Gate Arp: Start auf dem Raster

Meldung (Community, 30.10., blaue Electribe): Mit Gate Arp auf 2 oder 4 Steps startet der Kick genau in dem Moment, in dem das
Pad berührt wird, nicht auf dem Schlag. Wunsch: der Start soll auf dem Raster liegen, auch wenn man daneben tippt. Stand
2026-10-30: **aufgeschrieben, nichts gebaut, nichts gemessen.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was es schon gibt

- Gate Arp ist heute ein Muster aus 50 Einträgen (Pattern-Byte `+0x35`), gespielt ab dem Moment der Berührung. (gemessen,
  [Idee 72](72-gate-arp-note-halten.md))
- Ob die Firmware die Phase des Arps auf den Sequencer-Takt legt oder auf den Berührungszeitpunkt, steht nirgends. Die Meldung
  sagt Berührungszeitpunkt. (ungeprüft, nur die Meldung)
- Plugins sehen das Touchpad (`touch`, Ereignis bis zu 40 ms verspätet) und können Noten auslösen (`0xC005AD44`). Ein Takt-Ereignis
  oder die Position im Pattern ist in der API nicht bekannt (`data/script/contract.mjs`, nicht im Detail geprüft).

## Offen

- Läuft die Messung am Gerät ohne laufenden Sequencer anders als mit? Ohne Play gibt es kein Raster, nur BPM.
- Soll der Start auf den nächsten Step, den nächsten Schlag oder den nächsten Arp-Zyklus fallen (Verzögerung bis zu einem
  Zyklus, bei 2 Steps im Pattern sehr kurz)?
- Menüpunkt "Gate Arp quantisieren" (aus, Step, Schlag), wie bei anderen BLECH-Schaltern.
- Rot und blau, beide Modi (Gate Arp allein wird mit BLECH zu Gate Arp + Touch Scale, `docs/entscheidungen.md`).

## Plan (grob, hergeleitet)

1. Im Emulator messen: Berührung zwischen zwei Steps, Zeit bis zur ersten Note, mit und ohne Play.
2. Die Stelle suchen, an der die Firmware den Arp startet (Idee 72 hat die Note-Auslösung schon kartiert).
3. Start bis zum nächsten Step zurückhalten (Warteschlange im Bild-Hook oder Patch in der Firmware).
4. Als Schalter im BLECH-Menü, Standard aus.
