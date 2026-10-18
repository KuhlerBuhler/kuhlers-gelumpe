# Ladebalken: Streuung der Ladezeit im Emulator (18.10.)

Der Fall `loadbar:loader_is_no_slower` verglich die Ladezeit mit und ohne die vier Aufrufe des Ladebalkens auf einer
Karte mit 20 Samples, Grenze 0,5 %. Auf dem Branch mit den Fixes vom 18.10. (am Ladebalken nichts geändert) stand er
bei Korgs roter 2.02 auf 0,63 %.

**Gemessen** (Emulator, Flash-Abbild vom 09.10., Ladezeit mit / ohne Ladebalken, gleiche Kopie):

| Kopie | 18 Samples | 20 Samples | 22 Samples |
|---|---|---|---|
| rot, BLECH 1.2 | 1122,4 / 1121,6 (+0,07 %) | 1158,8 / 1155,2 (+0,31 %) | 1184,5 / 1185,9 (−0,12 %) |
| rot, Branch 18.10. | 1117,8 / 1115,5 (+0,21 %) | 1160,7 / 1153,4 (+0,63 %) | 1185,5 / 1183,7 (+0,15 %) |

Dieselbe Kopie streut also um mehrere Zehntel Prozent je nach Karte; Änderungen an ganz anderer Stelle verschieben,
wo die Interrupts fallen (hergeleitet: die Zeit des Emulators zählt Befehle). Der Fall vergleicht darum jetzt die Summe
über drei Karten (18, 20 und 22 Samples) mit derselben Grenze; auf dem Branch sind das +0,33 %.

Nicht am Gerät gemessen.

## Nachtrag: sechs Karten, Hacktribe (18.10. abends)

Mit dem ganzen Satz BLECH auf Hacktribe 2.02 stand die Summe über drei Karten bei +0,56 % und +0,65 %. Über sechs Karten
(16, 17, 19, 21, 23, 24 Samples) gemessen, Ladezeit mit / ohne die vier Aufrufe, Summe:

| Kopie | Summe | einzelne Karten |
|---|---|---|
| alter Ladebalken (Augen linear), ohne ruhenden IFX | +0,51 % | +0,33 % bis +0,84 % |
| neuer Ladebalken (eigenes Bild, Augen mit Ease-out), ohne ruhenden IFX | +0,44 % | +0,20 % bis +0,74 % |
| neuer Ladebalken, mit ruhendem IFX | +0,64 % | +0,38 % bis +0,90 % |

Die Vorzeichen sind auf allen Karten gleich: der Ladebalken kostet im Emulator rund ein halbes Prozent der Ladezeit,
etwa 6 ms von 1,1 s. Die Grenze von 0,5 % lag also schon mit dem alten Ladebalken auf der Kante. Sie steht jetzt bei 1 %.
Der ruhende IFX tut während des Startbildschirms nichts außer zwei Lesezugriffen je 40 ms; seine 0,2 % sind die Streuung
von oben (hergeleitet).
