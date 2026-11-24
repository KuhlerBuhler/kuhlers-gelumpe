# Display-Helligkeit: die Firmware schaltet nur an und aus

Gemessen im [Emulator](../glossary.md#emulator) (`tools/emu/machine.py`), [`SYSTEM.VSB`](../glossary.md#vsb) mit eigenem Flash,
jeder LCD-Schreibzugriff mitgeschrieben. Die Zeitkonstanten stammen aus einem Video vom Gerät (unten).
Markierungen: **gemessen**, **hergeleitet**, **angenommen**, **offen**.

Am Gerät zeigt das Display beim Musterwechsel gedimmte Teile; der Emulator blinkt ohne die Zeitkonstanten hart.

## Was die Firmware dem LCD schickt

- **Gemessen:** Über alle Befehle, die die Firmware ans LCD schickt (Boot, Spielen, Musterwechsel,
  MENU, Edit, Pad, PART MUTE, REC, STOP, PATTERN SET, WRITE, rund 30 s Gerätezeit), kommen nur
  `0xB0` bis `0xB7` (Seite), `0x00`/`0x10` (Spalte), `0x40` (Startzeile 0) und einmal bei 138 ms
  `0x81 0x22` (Kontrast). Kein Grau-Modus, kein Invertieren (`0xA6`/`0xA7`), kein Hell- oder
  Dunkelstufen-Befehl. (Mit dem [Patch](../glossary.md#patch) BLECH schickt die Seite DISPLAY INVERT einmal `0xA7`, siehe
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

- **Gemessen** (Zeitlupenvideo, Abschnitt "Gemessen am Gerät" unten): Die Firmware schickt nur
  an und aus; der Name des wartenden Patterns wird trotzdem nicht hart umgeschaltet. Jeder
  Bildpunkt folgt dem Schalten mit einer Flanke von rund 60 bis 100 ms und erreicht innerhalb
  der 280 ms vollen Kontrast. Was gedimmt wirkt, sind diese weichen Flanken.
- **Gemessen:** die Zeitkonstante eines Verzögerungsglieds erster Ordnung je Bildpunkt beim
  Dunkelwerden: 0,040 s (`tools/emu/lcd.py`, `TAU_ON`).
- **Geschätzt** (am Gerät mit bloßem Auge, keine Messung): ein Bildpunkt wird schnell dunkel,
  aber nur langsam wieder hell, läuft Blechy dunkel auf hellem Grund, zieht er eine Schliere. Im Emulator
  steht `TAU_OFF` auf 0,17 s; 0,30 s wirkte zu träge, 0,20 s noch etwas zu hoch.

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

  Zwischen Hell und Dunkel bleibt der Hub bei 4 bis 14 von 15.
- Die Konstanten sind einstellbar: `--lcd-tau-on` und `--lcd-tau-off` am Dienst, sonst
  `E2_LCD_TAU_ON` und `E2_LCD_TAU_OFF` (Sekunden), sonst die Vorgaben in `lcd.py`
  (`TAU_ON` 0,040 s, `TAU_OFF` 0,17 s geschätzt). Beispiel: `E2_LCD_TAU_ON=0.12 E2_LCD_TAU_OFF=0.30 npm start`.
- Tests: `tools/emu/test_lcd.py` (Verlauf, Blinken mit 280 ms bleibt zwischen 3 und 5 und
  13 und 14, Schrittweite, nur geänderte Bildpunkte), `tools/emu/test_server.py`
  (Ereignis `shade`), `test/lcd-shade.test.mjs` (Mischen der Farben).

## Gemessen am Gerät

- **Gemessen:** Zeitlupenvideo vom eigenen Gerät (Handy, 358 Bilder,
  Wiedergabe 30 Bilder/s), Pattern läuft, mit VALUE das nächste gewählt, der große Name
  blinkt. Ausgewertet: Displayrand je Bild gesucht (die Kamera wackelt), Bild auf ein
  festes Raster gelegt, Helligkeit der Schrift-Bildpunkte gegen den dunklen Balken,
  normiert auf ganz an und ganz aus. Das Video liegt nicht im Repository.
- **Gemessen:** Die Periode des Blinkens sind 134 Bilder. Mit den bekannten 560 ms der
  Firmware ergibt das 239 Bilder/s, also eine Aufnahme mit 240 Bildern/s.
- **Gemessen:** Schrift verschwindet (Bildpunkte werden dunkel), 10 bis 90 %:
  96, 83 und 88 ms. Schrift erscheint (Bildpunkte werden hell): 54 und 67 ms, danach ein
  langer flacher Rest bis ganz hell.
- **Hergeleitet:** Für ein Verzögerungsglied erster Ordnung ist tau = (10 bis 90 %) / 2,2, also
  `TAU_ON` rund 0,040 s. Für das Hellwerden taugt dieser Weg nicht: die 10 bis 90 % erfassen nur den
  schnellen Anfang der Flanke, der lange flache Rest fehlt darin. Darum ist `TAU_OFF` eine Schätzung.
- **Offen:** Beim Dunkelwerden gibt es nach etwa 40 % eine kurze Stufe von rund 35 ms;
  das Modell erster Ordnung bildet sie nicht ab. Ob das am LCD liegt oder an
  Hintergrundlicht und Kamera, ist offen.
- **Offen:** `TAU_OFF` genau bestimmen. Aus einem Video mit 240 Bildern/s und gesperrter Belichtung,
  Gerät am Netzteil (auf Batterie dimmt die Firmware das Licht durch schnelles Ein und Aus, siehe
  [Startphase](2026-10-10-startphase.md)): im eingeschwungenen Blinken die Höchst- und Tiefstwerte
  `H` (Ende der Dunkelphase) und `L` (Ende der Hellphase) der Dunkelheit eines Strichs des großen Namens
  lesen, mit `T = 0,28 s`, `a = (1 - H) / (1 - L)` und `b = L / H` ist `TAU_ON = -T / ln(a)` und
  `TAU_OFF = -T / ln(b)` (der Test `test_the_constants_follow_from_the_extremes_of_the_280_ms_blink`
  prüft die Herleitung am Modell). Ist `H` über 0,97 oder `L` unter 0,03, sieht man die jeweilige Konstante
  im Blinken kaum; dann die Flanke einzeln anpassen.
