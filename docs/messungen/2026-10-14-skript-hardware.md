# Plugin Hardware: Uhr, Lesen, Handeln, Ereignisse

Stand 2026-10-14. Kein Gerätezugriff. Alles im
Emulator gemessen oder aus dem Code hergeleitet. Zur Herkunft der Adressen siehe
[`../hintergrund/skript-laufzeit.md`](../hintergrund/skript-laufzeit.md).

## Timer3 läuft mit einer Sekunde Periode (Fehler behoben)

Der Zähler `0x01F0D010` zählt mit 150 MHz, aber das Periodenregister (`+0x18`)
steht auf `0x8F0D17F`: er läuft alle 150 000 000 Ticks (eine Sekunde) wieder bei
null los, nicht erst bei 2^32. Gemessen im Emulator (PRD gelesen, Zähler in 5 ms
Schritten 750 029 Ticks weiter). Die Zeitprüfungen der VM und des Rahmenhakens
rechneten bisher mit einer Differenz modulo 2^32. Fiel ein Überlauf in ein Handler
Fenster, sah die Laufzeit eine riesige Zeit und schaltete das Plugin mit `TIME` ab,
hergeleitet etwa alle 3 Minuten bei einer Last von 0,2 ms je Rahmen. Behoben an
den fünf Rechenstellen (Zeitprüfung im Lauf, Ende des Laufs, Höchstzeit, Rahmen
Kandidat und Rahmen nach Handler): ist der Zähler kleiner als der Start, kommt die
Periode dazu (`SCRIPT_TIMER_PERIOD`, Vertrag `TIMER3.period`). Die Unit Tests laufen
jetzt mit Start 149 999 984 und Überlauf bei der Periode. Am Gerät ist die Periode
nicht gelesen.

## Uhr und Lesen

- `korg.millis()` zählt aus Timer3 mit dem Rest je Tick, nach jedem Rahmen
  nachgeführt, damit zwischen zwei Aufrufen nie mehr als eine Periode liegt. Im
  Emulator 1241 ms Pluginzeit gegen 1250 ms Emulatorzeit (gemessen, `hw-uhr`).
- Lesen: Transport `0xC06BC318`, Tempo `0xC0691518` (32 Bit, Zehntel BPM, 1600 im
  Leerlauf), Pattern `0xC06B2420`, Part `0xC06B2428`, Schritt `0xC06904B0 + 0x48 *
  Part`, Mute `0xC06B2F9D + 0x330 * Part`. Reglerwerte hält der Eingangsfilter je
  Index (20 Wörter, `RT_KNOBS`), weil die Firmware sie nicht lesbar ablegt.
- Gemessen im Emulator (Firmware mit Plugin von der virtuellen Karte): im Leerlauf
  Transport 0, Tempo 1600, Pattern 0, Part 0, Schritt 0; nach PLAY Transport 1 und
  Schritt 13 nach 1,2 s; Regler 3 mit Rohwert 500 (Nachricht `[2, 3, 1, 244, 0]`)
  wird als 500 gelesen.
- API Version 3 (`since` 3) für alle Lesefunktionen; `korg.millis` bleibt 1.

## Handeln

Die Aktionen rufen die Funktionen der Firmware aus dem Rahmenhaken, also aus der
UiTask, in der die Recherche sie als sicher gemessen hat:
`korg.play` und `korg.stop` drücken und lösen die Taste über `0xC0042BB8`,
`korg.pattern` ruft `0xC0081F50(MODEL, index, 1)`, `korg.tempo`
`0xC004A80C(Patternobjekt, Zehntel BPM, 1)`, `korg.part` `0xC0081BB4(MODEL, part)`,
`korg.mute` das Mute-Pad `0xC0060C74(Objekt, part, flag)`. Die VM prüft die
Bereiche (Pattern 0 bis 249, Tempo 100 bis 3000, Part 0 bis 15), die Glue Funktion
prüft sie noch einmal.

**Befund, gemessen im Emulator:** `0xC0060C74` mit Flag 1 schaltet den Mute eines
Parts **um**, Flag 0 (Loslassen) tut nichts. Die Recherche beschrieb Flag 1 als
"stumm" und 0 als "spielt"; das stimmt nicht (Part 4: 0 gleich 1 mit Flag 1, Part 2:
1 gleich 0 mit Flag 1, Flag 0 ohne Wirkung). `korg.mute(part, stumm)` liest deshalb
den Zustand (`0xC06B2F9D + 0x330 * part`) und drückt das Pad nur, wenn er vom
gewünschten abweicht.

Gemessen im Emulator (Plugin von der Karte, Auslösung über Pads): Tempo 1200 steht im
Zustandswort, Pattern 5, Part 3, Part 2 von gemutet auf spielt, PLAY gibt Transport 1,
STOP Transport 0, keine Assertion. Unit Tests mit aufzeichnenden Stümpfen an den
Firmwareadressen prüfen die Argumente.

## Ereignisse

Statt Haken in der SeqTask vergleicht der Rahmenhaken die Zustandswörter von Frame zu
Frame (`script_events_poll`, Beschreibung in `docs/plugins.md`). Das erspart fünf
Haken an Stellen, die die Musik verschieben können, und kostet 40 ms Raster. Nur
`save` hat einen Haken (`0xC004C1B4`, erster Befehl `push {r4, r5, r6, lr}`, CommandTask),
der nur in den Ring schreibt und den verdrängten Befehl selbst ausführt.

Gemessen im Emulator: 2 s Wiedergabe bei 160 BPM ergeben `plays` 1, 21 Schritte
(erwartet 21,3) und 5 Beats, STOP ergibt `stops` 1 und keine weiteren Schritte; über
die Aktionen kommen `tempo` 1200, `patternChange` 5, `partChange` 3 und `mute` für
Part 2 mit Zustand 0 zurück. Unit Tests: Übergänge des Transports (`rec` nur beim
Eintritt in 3 oder 4), Werte je Ereignis, ein Ereignis je geändertem Mute in
Part-Reihenfolge, Schritte mit Beat bei jedem vierten und beim Überlauf auf 0, der
Haken (Register, Stapel, Notschalter, nicht scharf). Der Haken am Speicherer ist im
Emulator eingehängt; ausgelöst wurde er dort nicht (WRITE auf Global schreibt
Flash), seine Wirkung ist nur im Unit Test geprüft.

## Hintergrundlicht und LED-Sperre

- `korg.backlight(r, g, b)` ruft für jede Farbe `0xC0016BB4(0x01E26000, an, 3, maske)`
  mit den Masken `0x08`, `0x10`, `0x20`, die Funktion, die das Werkzeug
  `tools/device/backlight.py` am Gerät benutzt hat. Gemessen im Emulator: die drei
  Aufrufe mit den Werten des Plugins kommen an. Die Firmware ruft dieselbe Funktion
  im Emulator rund 1500 Mal in 2 s selbst (Dimm Routine); wie lange die Farbe sichtbar
  bleibt, ist wie in der Recherche auf Batterie mit Power Save "Auto" offen und
  am Gerät nicht geprüft.
- `korg.ledHold(an)` setzt das Byte `LM + 0xB98` (LM aus `0xC0345A1C`), das
  `0xC00875F4` und alle Firmware LED Wege prüfen. Gemessen im Emulator: mit gesetztem Byte
  schaltet PLAY die LED 9 nicht mehr (Transport läuft, LED bleibt 0), nach dem Lösen
  steht sie auf 255, weil die Laufzeit `0xC00875F4(LM, i, 1)` für alle 88 LEDs aufruft.
  Eine Schutzprüfung im Rahmenhaken gibt die LEDs zurück, wenn kein Plugin mehr läuft.
  Ohne die Sperre überschreibt die Firmware die unteren RGB LEDs `0x4C` bis `0x57`
  alle 40 ms mit der Pegelanzeige; mit ihr bleiben die Pluginwerte stehen
  (Recherche, am Gerät nicht geprüft).
