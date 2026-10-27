# Display-Helligkeit: die Firmware schaltet nur an und aus

Stand 2026-10-12. Gemessen im Emulator (`tools/emu/machine.py`), `SYSTEM.VSB` mit eigenem Flash,
jeder LCD-Schreibzugriff mitgeschrieben. Kein Gerätezugriff.
Markierungen: **gemessen**, **hergeleitet**, **angenommen**, **offen**.

Beobachtung am Gerät: beim Musterwechsel zeigt das Display gedimmte Teile, der
Emulator blinkt hart.

## Was die Firmware dem LCD schickt

- **Gemessen:** Über alle Befehle, die die Firmware ans LCD schickt (Boot, Spielen, Musterwechsel,
  MENU, Edit, Pad, PART MUTE, REC, STOP, PATTERN SET, WRITE, rund 30 s Gerätezeit), kommen nur
  `0xB0` bis `0xB7` (Seite), `0x00`/`0x10` (Spalte), `0x40` (Startzeile 0) und einmal bei 138 ms
  `0x81 0x22` (Kontrast). Kein Grau-Modus, kein Invertieren (`0xA6`/`0xA7`), kein Hell- oder
  Dunkelstufen-Befehl. (Mit dem Patch BLECH schickt die Seite DISPLAY INVERT einmal `0xA7`, siehe
  [Anpassung](2026-10-14-blech-anpassung.md).)
- **Gemessen:** Die Firmware schreibt nur Seiten, die sich ändern. Im Leerlauf und beim Spielen
  ohne Bedienung: 0 Schreibzugriffe. Der kürzeste Abstand zwischen zwei Änderungen derselben
  Seite ist 40 ms, und das sind Bildwechsel (Menü auf, EXIT, WRITE), kein Hin und Her desselben
  Inhalts. Ein Wechseln zweier Bilder, um Stufen zu erzeugen (Frame-Rate-Control), gibt es nicht.
- **Gemessen:** Das einzige schnelle Wechselspiel ist das Blinken beim Musterwechsel: Spielt das
  Gerät und wird mit VALUE das nächste Pattern gewählt, blendet die Firmware den großen Namen des
  wartenden Patterns („002 Init Pattern“, Seiten 2 bis 5, rund 390 Bildpunkte) alle 280 ms ein
  und aus (Periode 560 ms, 1,8 Hz), bis der Takt endet. Es wird jeweils nur die geänderte Seite
  geschrieben, zum Beispiel 288,1 ms, 568,1 ms, 848,1 ms nach dem Drehen.
- **Gemessen:** Der Emulator hat das auch vorher richtig geliefert: der Dienst veröffentlicht
  alle 20 ms Gerätezeit das Display, wenn es sich geändert hat; die Seite zeichnet sofort. Hart
  war nicht die Abtastung, sondern dass ein Bildpunkt nur an oder aus kennt.

## Was am Gerät gedimmt aussieht

- **Gemessen** (Zeitlupenvideo, Abschnitt „Gemessen am Gerät“ unten): Die Firmware schickt nur
  an und aus; der Name des wartenden Patterns wird trotzdem nicht hart umgeschaltet. Jeder
  Bildpunkt folgt dem Schalten mit einer Flanke von rund 60 bis 100 ms und erreicht innerhalb
  der 280 ms vollen Kontrast. Was gedimmt wirkt, sind diese weichen Flanken.
- **Gemessen:** die Zeitkonstante eines Verzögerungsglieds erster Ordnung je Bildpunkt beim
  Dunkelwerden: 0,040 s (`tools/emu/lcd.py`, `TAU_ON`).
- **Geschätzt** (am Gerät mit bloßem Auge, 2026-10-27, keine Messung): beim Hellwerden rund
  0,30 s (`TAU_OFF`). Ein Bildpunkt wird schnell dunkel, aber nur langsam wieder hell: läuft
  Blechy dunkel auf hellem Grund, zieht er eine Schliere. Die 0,028 s aus dem Video (unten)
  waren zu niedrig.

## Wie es dargestellt wird

- `lcd.py` rechnet je Bildpunkt mit; nur Bildpunkte, die noch nicht am Ziel sind, kosten Zeit.
  Der Dienst schickt die 16 Stufen (ein Byte je Bildpunkt, Zeile für Zeile) als Ereignis `shade`,
  wenn sich eine Stufe ändert. Das 1-Bit-Ereignis `display` und `Machine.fb` bleiben, ebenso
  alles, was daraus liest (`KORG.screen.get` liest den RAM des Geräts, nicht dieses Ereignis).
- Die Seite mischt je Bildpunkt die Farben `--cee-lcd-off` und `--cee-lcd-on`
  (`site/app/emulator.mjs`, `shadeImage`).
- **Gemessen:** der Pegel des Bildpunkts (16, 38) beim Blinken, 40-ms-Schritte, hart und mit
  Stufen:

| Zeit ms | hart | Stufe |
|---|---|---|
| 6500 | 1 | 8 |
| 6620 | 1 | 13 |
| 6740 | 1 | 14 |
| 6780 | 0 | 12 |
| 6900 | 0 | 6 |
| 7020 | 0 | 4 |
| 7060 | 1 | 7 |

  Zwischen Hell und Dunkel bleibt der Hub bei 4 bis 14 von 15, zu sehen in
  `before-hard.png` und `after-shaded.png` (nicht im Repository: sie zeigen
  Firmware-Bildschirmtexte).
- Die Konstanten sind einstellbar: `--lcd-tau-on` und `--lcd-tau-off` am Dienst, sonst
  `E2_LCD_TAU_ON` und `E2_LCD_TAU_OFF` (Sekunden), sonst die Vorgaben in `lcd.py`
  (`TAU_ON` 0,040 s, `TAU_OFF` 0,30 s geschätzt). Mit der Reihenfolge Option, Umgebung, Vorgabe.
  Beispiel: `E2_LCD_TAU_ON=0.12 E2_LCD_TAU_OFF=0.30 npm start`.
- Tests: `tools/emu/test_lcd.py` (Verlauf, Blinken mit 280 ms bleibt zwischen 3 und 5 und
  13 und 14, Schrittweite, nur geänderte Bildpunkte), `tools/emu/test_server.py`
  (Ereignis `shade`), `test/lcd-shade.test.mjs` (Mischen der Farben).

## Die beiden Konstanten aus einem Video bestimmen

Ziel: `TAU_ON` (Bildpunkt wird dunkel) und `TAU_OFF` (Bildpunkt wird hell), Verzögerungsglied
erster Ordnung: Dunkelheit `d(t) = Ziel + (Start - Ziel) * exp(-t / tau)`. Die Firmware wechselt
beim Blinken exakt alle 280 ms (7 Bildschirm-Takte à 40 ms, `docs/messungen/2026-10-12-emulator-takt.md`),
das ist die bekannte Zeitbasis.

### Was filmen

- Gerät am Netzteil, nicht am Akku: auf Batterie dimmt die Firmware das Licht durch schnelles
  Ein und Aus (`2026-10-10-startphase.md`), das gäbe bei Zeitlupe Streifen. Licht auf Weiß.
- Telefon auf Stativ, Zeitlupe mit 240 Bild/s (120 geht auch, 60 ist zu grob: 17 ms je Bild bei
  Zeitkonstanten um 100 ms). Belichtung, Fokus und Weißabgleich sperren (lange auf den Bildschirm
  tippen), Blitz und Bildstabilisierung aus. Das Display füllt das Bild, von vorn, kein
  Spiegeln; so nah, dass ein Display-Bildpunkt mindestens 4 Kamera-Bildpunkte breit ist (Makro).
- Ablauf am Gerät: spielen (PLAY), mit VALUE das nächste Pattern wählen, Wartezeit bis zum
  Ende des Takts filmen, den Wechsel mit aufnehmen (danach steht der Name ruhig, das ist die
  Bezugshelligkeit für "Text sichtbar"). Mindestens 8 Blinkzyklen, damit der Hub eingeschwungen
  ist (nach drei Zyklen schwankt er nicht mehr). Zwei bis drei Aufnahmen, gleicher Platz.
  Außerdem 2 s Standbild des Displays vor dem Drehen (Bezug für "dunkel").
- Das blinkende Ding ist der große Name des wartenden Patterns in der dunklen Leiste (Bild
  `before-hard.png`): der Text ist hell auf Dunkel, beim Ausblenden wird er dunkel wie die Leiste.

### Wo messen

Koordinaten im Display, von links oben gezählt, Bildpunkt 0 bis 127 und 0 bis 63 (gemessen im
Emulator, `Machine.fb`, jeder dieser Punkte wechselt alle 280 ms):

- Strich: der Schaft des großen "I" von "Init", Spalten 5 und 6, Zeilen 33 bis 43
  (zwei Bildpunkte breit, elf hoch). Mittelwert über die mittleren Zeilen 36 bis 40.
- Dunkel-Bezug: ein Punkt der Leiste ohne Text, zum Beispiel Spalten 5 und 6, Zeile 25.
- Hell-Bezug: derselbe Strich, wenn der Name nach dem Wechsel ruhig sichtbar steht (der Name
  des neuen Patterns beginnt an derselben Stelle; ist die Form anders, ein anderes Stück der
  gleichen Stärke aus der Aufnahme nehmen, aber vor und nach dem Wechsel denselben).

Der Hell-Bezug nimmt die Unschärfe der Kamera mit: ein zwei Punkte schmaler Strich erreicht auch
bei vollem Hell nie die Helligkeit einer großen weißen Fläche.

### Ablesen

1. Bilder aus dem Video ziehen, zum Beispiel `ffmpeg -i clip.mov -vf "crop=W:H:X:Y,format=gray" frame_%05d.png`
   (`W:H:X:Y` der Ausschnitt um den Strich), je Bild den Mittelwert der Helligkeit `b(n)` des
   Strichs; die Zeit ist `t = n / Bildrate`. Gamma der Kamera ist hier egal, solange die
   Belichtung gesperrt war und nichts übersteuert (kein reines Weiß, kein reines Schwarz im Bild).
2. Dunkelheit des Strichs: `d(t) = (b_hell - b(t)) / (b_hell - b_dunkel)`, 0 sichtbar, 1 dunkel.
   Dazu den Dunkel-Bezug als Mittelwert der Leistenfläche (`b_dunkel`) und den Hell-Bezug als
   Mittelwert des ruhig sichtbaren Strichs (`b_hell`).
3. Im eingeschwungenen Blinken die Höchst- und Tiefstwerte je Zyklus: `H` (am Ende der Dunkelphase)
   und `L` (am Ende der Hellphase), gemittelt über die letzten 4 Zyklen, beide zwischen 0 und 1.
4. Mit `T = 0,28 s`:

   ```
   a = (1 - H) / (1 - L)          b = L / H
   TAU_ON  = -T / ln(a)           TAU_OFF = -T / ln(b)
   ```

   (Herleitung: im eingeschwungenen Zustand ist `H = 1 - (1 - L) * a` und `L = H * b` mit
   `a = exp(-T/TAU_ON)`, `b = exp(-T/TAU_OFF)`. Geprüft im Test
   `test_the_constants_follow_from_the_extremes_of_the_280_ms_blink`: aus dem Modell abgelesene `H` und
   `L` liefern die Konstanten zurück.) Beispiel mit den Vorgaben: `H = 0,95`, `L = 0,24` ergibt
   `a = 0,066`, `b = 0,25`, `TAU_ON = 0,10 s`, `TAU_OFF = 0,20 s`.
5. Gegenprobe an den Flanken, unabhängig von `H` und `L`: in der Dunkelphase `ln(1 - d(t))` gegen
   `t` auftragen (Start der Phase bei `t = 0`), das ist eine Gerade mit der Steigung `-1 / TAU_ON`;
   in der Hellphase `ln(d(t))` gegen `t`, Steigung `-1 / TAU_OFF`. Anpassen mit den Bildern, in denen
   `d` zwischen 0,05 und 0,95 liegt. Beide Wege sollten innerhalb von 20 % übereinstimmen; weichen
   sie stark ab, folgt der Bildpunkt keinem Verzögerungsglied erster Ordnung (dann die Kurve `d(t)`
   festhalten und das Modell anpassen) oder die Aufnahme ist zu ungenau und zählt neu.
6. Grenzen: ist `H` über 0,97, sieht man `TAU_ON` im Blinken kaum (`a` unter 0,1, jede Messung
   rauscht dort stark); dann nur die Flanke nehmen oder `TAU_ON` kleiner als `T / 2,3 = 0,12 s`
   angeben. Dasselbe für `TAU_OFF` bei `L` unter 0,03. Wärme ändert die Trägheit (kalt langsamer),
   die Raumtemperatur dazuschreiben.

### Zahlen anwenden

Beide Werte in Sekunden festhalten. Probelauf: `E2_LCD_TAU_ON=... E2_LCD_TAU_OFF=... npm start`
(oder `--lcd-tau-on`/`--lcd-tau-off` am Dienst). Dauerhaft: `TAU_ON` und `TAU_OFF` in
`tools/emu/lcd.py` ändern, dazu die Zahlen im Abschnitt "Was am Gerät gedimmt aussieht" weiter oben und in `tools/emu/README.md`.
Abgleich nach dem Eintragen: dieselbe Aufnahme gegen den Emulator ansehen; `H` und `L` aus dem Emulator
(Stufe 14 und 4 von 15 mit den Vorgaben) müssen zu den gemessenen passen.

## Gemessen am Gerät (2026-10-13)

- **Gemessen:** Zeitlupenvideo vom eigenen Gerät (Handy, 358 Bilder,
  Wiedergabe 30 Bilder/s), Pattern läuft, mit VALUE das nächste gewählt, der große Name
  blinkt. Ausgewertet: Displayrand je Bild gesucht (die Kamera wackelt), Bild auf ein
  festes Raster gelegt, Helligkeit der Schrift-Bildpunkte gegen den dunklen Balken,
  normiert auf ganz an und ganz aus. Skripte und Video liegen außerhalb des Repos.
- **Gemessen:** Die Periode des Blinkens sind 134 Bilder. Mit den bekannten 560 ms der
  Firmware ergibt das 239 Bilder/s, also eine Aufnahme mit 240 Bildern/s.
- **Gemessen:** Schrift verschwindet (Bildpunkte werden dunkel), 10 bis 90 %:
  96, 83 und 88 ms. Schrift erscheint (Bildpunkte werden hell): 54 und 67 ms, danach ein
  langer flacher Rest bis ganz hell.
- **Hergeleitet:** Für ein Verzögerungsglied erster Ordnung ist tau = (10 bis 90 %) / 2,2:
  `TAU_ON` rund 0,040 s, `TAU_OFF` rund 0,028 s. `TAU_ON` steht so in `tools/emu/lcd.py`.
  Am Gerät geht Hellwerden schneller als Dunkelwerden, anders als zuvor angenommen.
- **Nachtrag 2026-10-27:** Der Wert fürs Hellwerden war zu niedrig. Die 10 bis 90 % nahmen nur
  den schnellen Anfang der Flanke, der "lange flache Rest bis ganz hell" fehlt darin. Mit bloßem
  Auge am Gerät (keine Messung) braucht ein Bildpunkt rund 0,3 s, bis er hell ist; ein laufender
  Blechy zieht so lange eine Schliere. `lcd.py` nimmt seitdem `TAU_OFF` 0,30 s als Schätzung.
  Hellwerden ist also langsamer als Dunkelwerden, nicht schneller.
- **Offen:** Beim Dunkelwerden gibt es nach etwa 40 % eine kurze Stufe von rund 35 ms;
  das Modell erster Ordnung bildet sie nicht ab. Ob das am LCD liegt oder an
  Hintergrundlicht und Kamera, ist offen.
