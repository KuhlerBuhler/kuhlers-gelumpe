# Blechy beim Ausschalten: Bild statt "Power Off"

Stand 2026-10-15. Kein Gerätezugriff, alles im Emulator gemessen (Hacktribe 2.02 und Korgs Original 2.02, beide mit dem eigenen
Flash-Abbild und einer virtuellen Karte). Zu [Idee 45](../ideen/45-blechy-ein-aus.md), ohne den Ton: Plugins
und Patches spielen keine Samples.

## Wo die Firmware das Fenster zeichnet

| Was | Wert | Art |
|---|---|---|
| Handler der Ausschaltmeldung `0x18` | `0xC0038A54`, CommandTask (Auslöser: Ein/Aus-Taste nach rund 2 s, Auto Power Off) | gemessen ([Plugin-Laufzeit](../hintergrund/skript-laufzeit.md), 4.3 und 5.4) |
| Ablauf | Fenster `0x1C` über `0xC0083DB0(0x1C, 0)` öffnen, `0xC0000B78(1000)` warten, Einstellungen über `0xC004C1B4` speichern, Stromhaltung loslassen | gemessen (Reihenfolge der Aufrufe), offline gelesen |
| Fenster `0x1C` | Fabriktabelle `0xC00F9CD8`, Eintrag `0x1C` zeigt auf `0xC00692B4`; der Konstruktor `0xC0069208` legt zwei Widgets an, einen Kasten und den Text "Power Off" an Spalte 20, Zeile 22 | gemessen (Tabelleneintrag), offline gelesen (Konstruktor) |
| Aussehen | weißer Kasten mit Rahmen über die ganze Breite, Mitte des Hauptbildschirms; Kopf- und Fußzeile bleiben sichtbar. Nach 50 ms ein weißes Rechteck, nach 100 ms der Kasten mit Text | gemessen |
| Die Firmware malt Teile des Kastens immer wieder neu | mit einem Bild, das nach den ersten 80 ms nur alle 100 ms neu geschrieben wurde, kam der Kasten in einer Sekunde achtmal für 40 bis 160 ms zurück (Teile des Bildes überschrieben) | gemessen |
| Zählung der Wartezeit | die Wartefunktion rechnet auf den Tickzähler `0xC06A292C` (ein Tick je Millisekunde) | gemessen (250 Ticks in 250 ms) |
| Gleich in Korgs Original | Code des Handlers (`0xC0038A40` bis `0xC0038C20`), der Wartefunktion (`0xC0000B78` ff.) und die Adresse des Tickzählers stimmen in beiden Builds überein | gemessen (Vergleich der Bytes und der Literale) |

## Was der Patch tut

`data/patches/power-off.json`, gebaut von `tools/patch/power_off.py` aus dem Sprite
`assets/blechy/sprites/blechy-sad.png` und der Schrift des Plugin-Displays (`data/script/font.mjs`). In den Patch-Satz BLECH
aufgenommen, für beide Builds (`hacktribe`, `stock`).

- **Der traurige Blechy:** `blechy-sad` ist die Idle-Pose mit geändertem Gesicht, mehr nicht: schwere Lider, Pupillen
  unten, Brauen innen oben, kein Mund (`tools/art/make_blechy.py`, Pose `sad`). Das Bild für den Bildschirm setzt
  ihn links (56 mal 56) und rechts drei Zeilen: "Na dann," / "tschüss" / "atze...". Es ist ein ganzer Bildschirm,
  1024 Byte im Format des Anzeigepuffers (Byte `(y / 8) * 128 + x`, Bit `y % 8`).
- **Ein Haken:** der Aufruf der Wartefunktion bei `0xC0038A74` (`bl 0xC0000B78`) geht über unseren Code
  (220 Byte bei `0xC01A4A00`, das Bild bei `0xC01A4C00` bis `0xC01A5000`, genau die Lücke zwischen Startbild-Editor
  und MFX 2). Er wartet die übergebene Zeit in Stücken (die ersten 60 ms zu 2 ms, danach zu 10 ms) und schreibt dazwischen das Bild in den
  Anzeigepuffer `0xC031B310`. Gezählt wird gegen den Tickzähler, damit die Summe eine Sekunde bleibt, und gegen die Summe der
  Stücke, damit die Schleife auch bei stehendem Zähler endet. Der Aufruf des Fensters, das Speichern und das
  Loslassen der Stromhaltung bleiben die der Firmware.
- **Hinter den Rettungswegen und mit Notschalter:** der Haken läuft erst beim Ausschalten, nie im Start. Ist EXIT beim
  Einschalten gehalten (oder fehlt das Panel-Objekt), ruft er ohne Umweg die originale Wartefunktion auf. Nichts davon
  steht in der Startphase, der Patch hat kein `startPhase`.
- **Kein neuer Flash-Schreibzugriff, keine Einstellung:** nichts wird gespeichert, es gibt keinen Menüpunkt zum
  Abschalten des Bildes (EXIT beim Einschalten reicht als Notschalter).
- **Keine Firmware im Patch:** das Bild und der Code sind unsere, der Patch trägt nur die Prüfsummen der ersetzten Bytes.

## Im Emulator geprüft

`tools/emu/power_off_cases.py`, über `tools/emu/check.py` für jede Kopie mit dem Haken und über
`test/power-off.test.mjs`. Jeder Fall schaltet das Gerät aus (Panel-Meldung Typ 6, Netzteil ab) und sieht dabei alle 5 ms
auf das Display. Verglichen wird mit derselben Kopie, in der nur das Wort des Hakens auf den Original-Aufruf
zurückgesetzt ist.

| Fall | Ergebnis (Hacktribe, eigenes Flash) | Ergebnis (Korgs Original) |
|---|---|---|
| Bild gezeigt | Hauptbildschirm, ab 20 ms das Bild, bis das Display aus ist; der Kasten der Firmware kommt nie auf das Display | ab 50 ms das Bild, davor ein Zwischenbild der Firmware (das weiße Rechteck, in das ihr Kasten gemalt wird, 40 ms im Anzeigepuffer), danach bleibt es |
| Ohne Haken | der Kasten (2 Bilder), nie das Bild | ebenso |
| Zeit bis Strom aus | 1003,6 ms mit und ohne Haken | 1003,9 ms mit und ohne Haken |
| Speichern | ein Erase (4096 Byte bei `0x230000`) und 4096 programmierte Byte, mit und ohne Haken gleiche Befehle, gleiche Daten, gleiches Flash-Abbild; auf der Karte kein Schreibzugriff in beiden Fällen | ebenso |
| Speichern mit geänderter Einstellung | gleich, auch wenn das Ausschalten eine geänderte Global-Einstellung (Power Save) schreibt und die BLECH-Einstellungen zuvor auf die Karte gingen | ebenso |
| EXIT beim Einschalten gehalten | der Kasten wie ohne Haken, nie das Bild, gleicher Zeitpunkt und gleiche Schreibzugriffe | ebenso |
| Netzteil an | die Firmware übergeht die Taste, Gerät läuft weiter, Bild nicht zu sehen | ebenso |

`check.py` besteht mit dem eigenen Flash-Abbild für beide Builds (115 von 115, darin die acht Fälle des Patches) und mit leerem Flash
(114 von 114; beim leeren Flash und Hacktribe zeigte der erste Blick schon das Bild statt des Hauptbildschirms, die Prüfung nimmt das an
und wurde für diesen Fall einzeln wiederholt).

Bilder aus dem Display-RAM, rund 0,5 s nach der Taste:

| | |
|---|---|
| mit dem Patch | ![Blechy beim Ausschalten](../images/blechy-power-off-emu.png) |

## Offen

- **Am Gerät nichts geprüft.** Ob die Firmware dort ihren Kasten ebenso oft neu malt wie im Emulator, ob 10 ms Redraw
  genügen, bis das LCD (träge, grob 100 ms) das Bild zeigt, und ob die Polarität stimmt (gesetztes Bit ist ein dunkler
  Punkt, wie bei den übrigen Bildern), ist offen.
- **Der Ton fehlt:** `blechy-sad` als Sample kann ein Patch nicht abspielen. Offen bleibt, ob die Sound-Engine beim
  Ausschalten noch läuft.
- **Karte beim Ausschalten:** das Ausschalten schreibt in keinem gemessenen Fall auf die Karte. Ein Plugin, das im selben
  Moment `korg.store.save()` anfordert, ist nicht gemessen; der Haken ändert daran nichts, er rührt weder das Fenster noch die
  Reihenfolge der Aufrufe an.
- **Andere Wege zum Ausschalten:** Auto Power Off geht durch denselben Handler, ist aber nicht ausgelöst worden
  (4 Stunden Gerätezeit); die zwei weiteren Absender der Meldung `0x18` auch nicht.
