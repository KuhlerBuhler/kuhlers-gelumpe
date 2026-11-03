# 102. Gate Arp: Y wählt den Rhythmus

Wunsch (02.11.): mit Gate Arp + Touch Scale wählt Y auf dem Touchpad die Einstellung GATE ARP aus dem Pattern-Menü (den
Rhythmus), X bleibt die Tonhöhe.

Stand 2026-11-02: **aufgeschrieben, nichts gebaut, nichts gemessen.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.
Zurück zu den [Ideen](../ideen.md).

## Was heute ist

- Gate Arp + Touch Scale: X wählt die Note, Y die Notenlänge, der Rhythmus kommt aus dem Menü. (gemessen, [Idee 72](72-gate-arp-note-halten.md))
- Der Rhythmus liegt im Pattern an `+0x35`, Werte 0 bis 49, rot und blau gleich. Ein geschriebener Wert wirkt sofort im
  laufenden Spiel. (gemessen, Idee 72)
- Y ist also nicht frei: wer Y auf den Rhythmus legt, verliert die Notenlänge am Touchpad.

## Vorschlag

- Schalter unter BLECH > FEATURES, etwa ARP Y: LENGTH (wie Korg, Standard) oder TYPE.
- Auf TYPE teilt Y die 50 Rhythmen in Bänder (0 bis 1023 auf 0 bis 49), mit etwas Hysterese, damit an einer Grenze nichts
  flattert. Die Notenlänge bleibt dabei auf dem Wert, den Y vor der Berührung hatte, oder auf einem festen Mittelwert.
  (hergeleitet)
- Finger weg: der alte Rhythmus kommt zurück, damit das Pattern nicht verändert gespeichert wird. Ob er stattdessen
  bleiben soll, ist eine zweite Stellung des Schalters. (ungeprüft)

## Wege

1. Firmware-Patch im Touchpad-Pfad von Modus 3 (Gate Arp + Touch Scale): Y vor der Längenberechnung abfangen und nach
   `+0x35` schreiben. Kein Nachhinken, rot und blau. Die Stelle ist noch nicht gesucht.
2. Plugin: geht heute nicht sauber. Maskenbit 5 verwirft die ganze Bewegung, X fällt mit weg. Bräuchte `korg.gateArp`
   (Idee 72) und ein Filter, das nur Y abnimmt. (gemessen für das Maskenbit, Rest hergeleitet)

Weg 1 ist der bessere.

## Am Gerät zu testen

- Fühlt sich die Bänderung bei 50 Rhythmen auf der Höhe des Touchpads spielbar an, oder braucht es weniger Stufen?
- Speichert WRITE den Rhythmus mit, wenn er auf TYPE bleibt?
- BLECH macht Gate Arp allein zu Gate Arp + Touch Scale (`docs/entscheidungen.md`), beide Wege prüfen.
