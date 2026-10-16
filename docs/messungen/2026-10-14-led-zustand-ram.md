# LED-Zustand im RAM: wo die Firmware merkt, was leuchtet

Stand 2026-10-14. **Nur im Emulator gemessen** (`tools/emu/machine.py`, eigene
`SYSTEM.VSB`, SHA-256 `b0890899cbe5951d0709724c46d38350a35a6134a4a01d3a5bad63e51ac22ae7`,
leerer Flash), kein Zugriff aufs Gerät. Gilt nur für diesen Firmware-Build (2.02 mit
Hacktribe); ein anderer verschiebt alle Adressen. Markierungen: **gemessen** (Lauf im
Emulator), **hergeleitet** (aus dem Maschinencode gelesen), **offen**. Keine Firmware-Bytes
im Repo, nur Adressen.

## Ergebnis

**Gemessen:** Die Firmware hält den Zustand aller LEDs im RAM, in einem LED-Manager-Objekt.
Ein Zeiger darauf steht bei `0xC0345A1C` (im Emulator-Lauf `0xC06C2288`, auf dem Heap; dass
das Objekt nur einmal beim Start angelegt wird, ist hergeleitet). Das Objekt hat zwei Tabellen mit je 88 Einträgen zu 8 Byte, ein Eintrag
je LED-Nummer `0x00` bis `0x57`:

| Tabelle | Ort | Inhalt |
|---|---|---|
| Sollwert | Manager `+ 0x4c + 8 * LED` | was die Firmware will |
| Kopie des Gesendeten | Manager `+ 0x88c + 8 * LED` | was sie zuletzt für das Bedienfeld eingereiht hat |

Aufbau eines Eintrags (beide Tabellen): Byte 0 die LED-Nummer, Byte 1 Modus, **Byte 2 die
Helligkeit (0 bis 255)**, Byte 3 Ein-Flag, Byte 4 und 5 Blinkdauer in Takten, Byte 6 und 7
Zähler. **Hergeleitet** aus `0xC0087710` (Modus setzen) und `0xC0087740` (Takt, Modus 2 blinkt,
Modus 3 einmal), Bedeutung der Modi nicht einzeln geprüft.

**Zum Anzeigen taugt die Kopie, nicht der Sollwert.** Gemessen: Der Sollwert der VALUE-LED
(`0x00`) steht im Stand auf 255, gesendet und in der Kopie ist 0. Die Kopie stimmt dagegen für
jede LED `0x00` bis `0x4b` mit dem überein, was als Panel-Nachricht `00 LED Helligkeit` an
die UART ging (Messreihen unten).

## Weg einer LED (hergeleitet, im Lauf bestätigt)

1. Firmware-Code setzt Modus oder Sollwert eines Eintrags und ruft `0xC00875F4(Manager, LED, 0)`.
2. Die Funktion vergleicht Sollwert und Kopie. Sind sie gleich, ist nichts zu tun. Sonst kopiert
   sie den 8-Byte-Eintrag in die Kopie, baut die Nachricht `{LED, Flag, Helligkeit}` bei
   Manager `+ 0xB4C` und ruft `0xC0087578`.
3. `0xC0087578` ruft den LED-Setzer `0xC0028600` (`docs/messungen/2026-10-08-led-execute.md`),
   der `00 LED Helligkeit` in die Sendequeue `0xC0024BF4` des Bedienfelds stellt.

Der LED-Setzer ist in der unveränderten Firmware nur über `0xC0087578` erreichbar (die einzige
direkte Verzweigung auf `0xC0028600` liegt bei `0xC00875B8`; Aufrufe über Zeiger sind so nicht
ausgeschlossen, im Lauf fand sich keiner). Die Kopie wird beim Einreihen aktualisiert, die
Nachricht verlässt die UART wenige Millisekunden später (5 Byte bei 115200 Baud: 0,43 ms je
LED, alle 76 hintereinander rund 33 ms).

Die ältere Notiz in `2026-10-08-led-execute.md` nennt die Sollwert-Tabelle "ab Panel-Objekt
`+ 0x4c`". Gemeint ist dieser LED-Manager; das Objekt bei `0xC033E6FC` ist ein 8-Byte-Sender
mit Sperrbyte, auf dem der Setzer arbeitet.

## Messreihen (Emulator)

- **Gemessen:** Nach 8 s Gerätezeit (2817 Panel-Nachrichten) leuchten laut Kopie `0x01` bis
  `0x04`, `0x0c`, `0x0f`, `0x16`, `0x1b`, `0x22`, `0x28`, `0x2d`; dasselbe hat die UART
  zuletzt für jede LED bekommen.
- **Gemessen:** Elf Tasten nacheinander gedrückt und losgelassen (PLAY, REC, STOP, MENU, EXIT,
  GATE ARP, MASTER FX, Taste 1 und 2, AMP EG, TRIGGER), danach je 0,3 und 0,4 s Pause: Kopie
  und UART stimmen in jedem Schritt für alle LEDs `0x00` bis `0x4b` überein. PLAY zeigt `0x09`
  und `0x15` an, STOP löscht beide.
- **Gemessen:** Zufallsbedienung (Tasten, Drehgeber, Pads, Regler, ein Schritt alle 30 ms),
  danach alles loslassen und ausschwingen lassen: bei 500 und 800 Schritten in 20 von 20
  Prüfungen null Abweichungen zwischen Kopie und UART. Mitten in der Bedienung war in 14 von
  600 Abtastungen eine LED laut Kopie schon geändert, aber noch nicht gesendet; sie zog nach.
  Gesehene Werte: 0, 192, 255 und die Zehnerstufen 5 bis 245 (die VALUE-LED blendet aus).
- **Gemessen:** Mit der eigenen Testfirmware (400 Schritte) dieselbe Adresse und
  dasselbe Ergebnis. Mit der MFX-2-Variante der Testfirmware weichen `0x1b` und `0x1c` ab: der MFX-2-Haken
  setzt sie direkt über `0xC0028600` (`2026-10-10-mfx-umschalter.md`), am Manager vorbei. Die
  Kopie zeigt dort TOUCH SCALE aus und MASTER FX an, das Bedienfeld das Gegenteil (behoben in der
  fünften Fassung des Patches, Abschnitt "Der MFX-2-Haken über den Weg der Firmware").

## Aktualisierungsrate

- **Gemessen:** Der Manager läuft im 40-ms-Takt. Die VALUE-LED blendet nach einem Dreh in
  Zehnerstufen alle 40 ms von 255 auf 0 (rund 1,0 s). Beim Tempo des leeren Flashs blitzt TAP
  (`0x14`) alle 500 ms für 75 ms, das laufende Schritt-Pad (`0x3c`) für 90 ms.
- Die Seite liest alle 250 ms. Zustände unter 250 ms Dauer gehen deshalb teilweise verloren;
  ein 75-ms-Blitz ist (hergeleitet) in etwa jedem dritten Lesen zu sehen. Schneller lesen
  belegt die Verbindung, weil jedes Lesen den Port für andere Aufträge sperrt.

## Lesen am Gerät

Ein 0x52-Lesen von **603 Byte** (`0x4b * 8 + 3`) ab Manager `+ 0x88c` liefert Nummer und
Helligkeit der 76 LEDs `0x00` bis `0x4b`, also alles, was die Zeichnung der Seite hat. Davor
einmal die 4 Byte bei `0xC0345A1C`; die Adresse wird gemerkt und danach nur noch das eine
Lesen gebraucht. Jeder Eintrag beginnt mit seiner Nummer: stimmt das nicht für alle 76, wird
die Adresse einmal neu gesucht, sonst gemeldet. So fällt ein anderer Build auf, ohne dass die
Seite etwas Falsches zeigt. Code: `src/leds.mjs`, Karte: `data/map/screen.mjs` (`ledState`).

Nicht gelesen werden die vier RGB-LEDs `0x4c` bis `0x57`. **Gemessen:** Ein Flag bei Manager
`+ 0xB78` steht im Emulator auf 1; dann geht dort immer 0 ans Bedienfeld, in der Kopie bleibt
der Standardwert 120. Ob und wann es am Gerät 0 wird (Pegelanzeige, `0xC0088380`), ist
**offen**; die Seite zeichnet diese LEDs nicht.

## Grenzen und offen

- **Offen:** Am Gerät nicht gelesen. Der Zeiger `0xC0345A1C` ist dort nur durch den
  MFX-2-Patch belegt (er liest `*0xC0345A1C + 8 * LED + 0x4e`), die Kopie bei `+ 0x88c`
  nicht. Erster Test am Gerät: ein einziges Lesen, es verändert nichts.
- LEDs, die Code direkt über `0xC0028600` setzt (die Execute-Stubs von
  `tools/device/led_show.py`), tauchen in der Kopie nicht auf. Der MFX-2-Haken setzt `0x1b` und
  `0x1c` seit der fünften Fassung nicht mehr so (Abschnitt unten).
- **Behoben im MFX-2-Patch (14.10., im Emulator gemessen):** Der Haken schreibt den gewollten
  Wert in den Sollwert des Managers (`+ 0x4c + 8 * LED + 2`) und ruft `0xC00875F4(Manager, LED, 0)`,
  den Weg der Firmware selbst. Kopie und Bedienfeld stimmen danach überein. Den Weg über
  `0xC0087710` gibt es auch (Modus setzen, Helligkeit 0 oder 255 aus dem Modus), die Modus-LEDs
  setzt die Firmware aber nicht darüber, siehe unten.

## Der MFX-2-Haken über den Weg der Firmware (fünfte Fassung)

**Vorher gemessen** (Patch vor der Korrektur, Emulator): TOUCH SCALE bei MFX 2: UART `0x1b` = 255,
`0x1c` = 0, Kopie `0x1b` = 0, `0x1c` = 255. GATE ARP (Modus 3): UART TOUCH SCALE 0, Kopie 255. Der
Gerätemodus der Seite hätte beide vertauscht gezeigt.

**Gelesen** (Maschinencode, offline):

| Adresse | Was |
|---|---|
| `0xC00875F4(Manager, LED, 0)` | Vergleich Sollwert und Kopie, kopiert den Eintrag, reiht die Nachricht ein. Im Vergleich steht Kopie Byte 2 gegen Sollwert Byte 1 (Modus, nicht Helligkeit); bei diesen LEDs (Modus 1, Helligkeit 0 oder 255) ist das nie gleich, also sendet der Aufruf immer. |
| `0xC0088118(Manager, Touch-Pad-Modus)` | die Firmware setzt GATE ARP, TOUCH SCALE, MASTER FX für einen Modus: Tabelle bei `0xC00E5030`, 3 Byte je Modus (`01 00 00`, `00 01 00`, `00 00 01`, `01 01 00`), LED-Nummern `1a 1b 1c` bei `0xC00E50FF`, je Sollwert Byte 2 = 0 oder 255, dann `0xC00875F4`. Gemessen als Schreiber von `0x4e` der drei Einträge bei einem Tastendruck (Schreib-Hook im Emulator). Aufrufer (hergeleitet): ein Zweig bei `0xC00896EC`, der bei einem Moduswechsel läuft, und ein Auffrischen bei `0xC0089A3C`, das den aktuellen Modus liest. |

**Patch:** `led_assert` (MFX 2: TOUCH SCALE 255, MASTER FX 0) schreibt die beiden Sollwerte und ruft
`0xC00875F4`. `led_restore` (nach MASTER FX, GATE ARP, SHIFT + TOUCH SCALE und beim Verlassen von
MFX 2) ruft für die Modi 0 bis 2 `0xC0088118` mit dem aktuellen Modus, also die eigene Funktion
der Firmware statt einer kopierten Tabelle. Für Modus 3 setzt er GATE ARP 255, TOUCH SCALE 0,
MASTER FX 0 auf demselben Weg. Der Sollwert der Firmware ist damit nach MFX 2 nicht mehr "Modus 2",
sondern was angezeigt wird; beim nächsten Moduswechsel schreibt `0xC0088118` alle drei neu.

**Nachher gemessen** (Emulator, `mfx_cases.py`, `SYSTEM.VSB` + Startbild-Editor + MFX 2 + Blech-Startbild):

- Prüfung `mfx:led_copy` (in `check.py`): Folge TOUCH SCALE, TOUCH SCALE, MASTER FX, TOUCH SCALE,
  GATE ARP, TOUCH SCALE, SHIFT + TOUCH SCALE, GATE ARP, Rad, TOUCH SCALE, Rad, MASTER FX: nach
  jedem Schritt ist die Kopie für `0x1a` bis `0x1d` gleich dem, was zuletzt an die UART ging,
  und jeder Eintrag beginnt mit seiner Nummer. Im Modus 3 steht nur GATE ARP an. Gegen die alte
  Fassung schlägt dieselbe Prüfung fehl.
- Alle 64 Dreierfolgen aus GATE ARP, TOUCH SCALE, SHIFT + TOUCH SCALE, MASTER FX und die neun
  Zweierfolgen mit EXIT gehalten: Kopie gleich UART in jedem Schritt (Schritt in `mfx_cases.py run`).
- **Nebenwirkung:** nach GATE ARP geht jetzt eine Nachricht mehr an das Bedienfeld (drei statt zwei
  LED-Nachrichten vom Patch). Die TOUCH-SCALE-LED, die die Firmware für Modus 3 anschaltet, ist
  bis zur dunklen Nachricht 1,3 ms an (vor dem Fix 0,9 ms; Zeitstempel der UART-Nachrichten im
  Emulator, 0,43 ms je Nachricht), kein sichtbarer Unterschied.
- **Offen:** am Gerät nicht geprüft, auch nicht, ob die Seite im Gerätemodus die LEDs jetzt richtig
  zeigt.
- Hätte die Firmware keinen Zustand geführt, wäre die Alternative gewesen, die LED-Nachrichten
  in einen festen RAM-Bereich zu spiegeln (ebenfalls Patchsatz). Das ist hier nicht nötig.
