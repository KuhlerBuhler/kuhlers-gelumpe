# BLECH Anpassung: untere LEDs und Display-Licht

Stand 2026-10-14. Alles im Emulator gemessen oder aus dem Maschinencode gelesen (Firmware 2.02 mit
Hacktribe, eigene `SYSTEM.VSB`, virtuelle Karte, Netzteil eingesteckt), am Gerät nichts geprüft.
Markierungen: **gemessen** (Lauf im Emulator), **hergeleitet** (aus dem Code), **offen**.
Code: `tools/patch/script_menu.s` (Haken und Seiten, Teil des Patches `script-runtime`), Prüfungen:
`tools/emu/menu_cases.py` (`look_cases`), Anwendersicht: `docs/plugins.md`, "Das Menü BLECH am Gerät".

## Was angepasst werden kann

Die Gruppe CUSTOMIZATION im BLECH Menü (neun Seiten):

| Seite | Wert | Wirkung |
|---|---|---|
| CUSTOMIZATION | Titelseite | sagt, dass WRITE speichert |
| BOTTOM LEDS | METER, COLOR, OFF | Pegelanzeige, feste Farbe, dunkel |
| LED RED, GREEN, BLUE | 0 bis 15 | Farbe für METER und COLOR; 0 0 0 ist die Farbe der Firmware |
| BACKLIGHT RED, GREEN, BLUE | 0 bis 15 | Farbe des Display-Lichts; 0 0 0 ist das Weiß der Firmware |
| DISPLAY INVERT | OFF, ON | Display umkehren, siehe unten (Stand 15.10.) |
| PATTERN CONFIRM | ON, OFF | der Patternwechsel wartet auf MENU, siehe [Patternwechsel](2026-10-15-patternwechsel.md) (Stand 15.10.) |

Alles gilt sofort beim Drehen. WRITE legt es in `settings.a/b.bin` auf die Karte (Version 2 der Datei,
24 bis 88 Byte, das Wort `look` hinter den Schaltern). Es wird nichts in den Flash geschrieben.
Ohne Karte oder Datei gelten die Werte der Firmware.

## Untere LEDs

- **Hergeleitet** (Maschinencode `0xC0088284`): die vier RGB-LEDs (`0x4c` bis `0x57`, je ein rotes,
  grünes und blaues Element: `0x4c`/`0x4d`/`0x4e`, `0x4f`/`0x50`/`0x51`, `0x52`/`0x53`/`0x54`,
  `0x55`/`0x56`/`0x57`) bekommen im 40-ms-Takt je einen Helligkeitswert von 0 bis 255 und werden über
  `0xC00875F4` an das Bedienfeld gesendet. Die Firmware ruft die Funktion mit einem Schalter: 0 setzt alle
  zwölf auf 0 (Global Power Save: "Always", oder "Auto" mit Batterie), 1 ist die Pegelanzeige.
  Die Paare `0x4c` bis `0x51` folgen dem einen Pegel, `0x52` bis `0x57` dem anderen.
- **Gemessen** (Pegel in die Glättung `0xC0088220` eingespeist, Netzteil): die Firmware sendet keine
  Schaltwerte, sondern einen Verlauf. Stille (Pegel 0): alle zwölf 120. Pegel 2: 43, 212, 0 (Grün). 80: 0,
  245, 10. 120: 0, 177, 78. 160: 0, 83, 172. 200: 40, 0, 0. 254: 248, 0, 0 (Rot). Jedes Element
  kommt also in vielen Stufen vor, die Pegelanzeige ist ein Farbverlauf von Grün über Blau nach Rot.
- **Hergeleitet, am Gerät offen:** weil die Firmware selbst Zwischenwerte schickt und die VALUE-LED
  nach dem Drehen in Zehnerstufen ausblendet (`2026-10-14-led-zustand-ram.md`), nimmt das Bedienfeld
  Helligkeitsstufen an. Ob jedes Element der unteren LEDs am Gerät wirklich alle Stufen zeigt und nicht
  nur an und aus, ist nicht geprüft. Bei nur an und aus würde jede Stufe über einer Schwelle leuchten, die
  Farbe wäre dann gröber, die Seiten ändern daran nichts. Die Pegel 0 bis 15 der Seiten ergeben
  17 mal Pegel (0 bis 255).
- **Wirkung der Modi** (Haken `led_meter_hook` am Anfang von `0xC0088284`): nur wenn das Menü scharf ist,
  die Firmware die Anzeige will (Schalter 1) und kein Plugin die LED-Sperre (`LM + 0xB98`) hält. Dann
  schreibt der Haken die zwölf Helligkeiten wie die Firmware (in den Sollwert, danach `0xC00875F4`).
  - COLOR: feste Farbe (die drei Pegel mal 17); ohne Farbe (0 0 0) das Weiß 120 der Firmware im Stillstand.
  - METER mit Farbe: derselbe geglättete Pegel wie in der Firmware (derselbe Aufruf von `0xC0088220`),
    die Helligkeit der Farbe ist `64 + ((pegel * pegel / 256) * 191 / 256)`, also 25 Prozent in der Stille
    bis fast 100 Prozent beim Maximum, wie die Firmware quadratisch im Pegel.
  - OFF: alles 0.
  - METER ohne Farbe: der Haken gibt die Firmware sofort zurück, nichts ändert sich.
- **Gemessen** (`menu:look_led_*`): COLOR 15, 7, 0 ergibt zwölfmal 255, 119, 0 in dieser Reihenfolge;
  METER in der Farbe 63, 29, 0 in der Stille und 249, 116, 0 beim Pegel 254; OFF null; METER ohne
  Farbe mit Pegel 254 die Farben der Firmware (244, 0, 0); die LED-Sperre eines Plugins hält die zuletzt gesetzten Werte; Global Power Save "Always"
  macht alle zwölf 0, auch bei COLOR.

## Display-Licht

- **Hergeleitet** (`0xC0016C98`, `0xC0016CE0`, `0xC0016D28`, `0xC0016BB4`): das Licht sind drei Pins,
  GP6P3, P4, P5 für Rot, Grün, Blau, die die Firmware über Setz- und Löschregister schaltet. Die Hardware
  kennt je Kanal nur an und aus, die Firmware hat keine Stufen, nur eine Software-PWM für Power Save
  (siehe unten). Ob an diesen Pins ein PWM-Baustein (Hardware) des Prozessors liegt, ist nicht
  nachgeschlagen (Pinbelegung des AM1808 nicht geprüft), die Firmware nutzt ihn nicht.
- **Wo die Firmware ihr normales Licht setzt** (hergeleitet): einmal beim Start in der StartupTask
  (`0xC002ABE4` bis `0xC002AC04`, weiß), und in `0xC0028AB4`, wenn das Dimmen endet (Power Save aus,
  Netzteil gesteckt). Dort ruft sie die drei Setzer mit 1. Beim Ausschalten setzt `0xC0038B9C` alle auf 0.
  Der Absturzbildschirm (`0xC00299D8`) setzt sie ebenfalls.
- **Power Save** (gemessen, unverändert): das Flag `0xC00F9310` (Wert aus `0xC0028AB4`) schaltet die
  Dimm-Routine `0xC00289F4` im 2-kHz-Timer-Interrupt ein; sie setzt Rot oder Grün je 2 von 18 Takten, im
  Wechsel, Blau nie. Gemessen mit und ohne unseren Patch: Rot 3,7 Prozent, Grün 3,7 Prozent, Blau 0.
  Solange das Flag gesetzt ist, tun unsere Haken nichts: Power Save bleibt genau, wie die Firmware es macht.
- **Haken:** die drei Setzer fangen den Aufruf mit 1 ab und machen einen Kanal, dessen Pegel 0 ist, zu 0
  (nur wenn das Menü scharf ist und die Firmware nicht dimmt). Beim Drehen und beim Start setzt das Menü
  die drei Pins selbst über diese Funktionen. Der Haken `bl_pwm_hook` am Anfang der Dimm-Routine fährt eine
  Software-PWM, wenn ein Pegel zwischen 1 und 14 liegt: 16 Takte des 2-kHz-Interrupts (8 ms, 125 Hz), im
  Takt 0 gehen alle Kanäle mit Pegel über 0 an, ein Kanal geht aus, wenn der Takt seinem Pegel gleicht.
  Pegel 0 und 15 und das Standardweiß brauchen keine PWM, der Haken tut dann nichts als zu prüfen.
- **Gemessen** (Pin-Wechsel mit Gerätezeit mitgeschrieben): Pegel 15 für ein Kanal: Anteil 1,0 und kein
  Wechsel. Pegel 5 für Rot: 0,312 (5/16). 3, 8, 12: 0,187, 0,5, 0,75. 1 und 14: 0,062 und 0,875.
  Das Dimmen mit einer Mischfarbe: Rot 0,037, Grün 0,037, Blau 0, wie die Firmware ohne uns; danach
  kommt die gemischte Farbe von selbst wieder, das Standardweiß nach 0 0 0 auch.
- **Kosten** (gemessen im Emulator, Befehle, nicht Zeit): im Leerlauf 9 Befehle je Takt für die Prüfung
  (18 000 je Sekunde). Mit PWM rund 27 Befehle je Takt, dazu 40 je Pin-Aufruf: eine Farbe mit drei
  Kanälen kostet etwa 54 000 plus 20 000 Befehle je Sekunde, bei 2000 Takten je Sekunde. Auf dem Prozessor
  (hergeleitet, 300 MHz, im Emulator gezählt) sind das weit unter einem Promille der Zeit. Der Interrupt
  läuft je Takt höchstens 110 Befehle länger, gegen 500 Mikrosekunden Takt.
- **Grenze, ehrlich:** 125 Hz Software-PWM ist von der Art der Firmware selbst (111 Hz beim Dimmen), das
  Flimmern sieht man aber erst am Gerät. Bleibt es sichtbar (Kamera, schnelle Augenbewegung), ist die
  Abhilfe, nur die Pegel 0 und 15 anzubieten (acht Farben, keine PWM, kein Haken am Interrupt). Die PWM
  läuft nur bei Pegeln zwischen 1 und 14, die Vorgabe und die acht Farben der Pegel 0 und 15 berühren
  den Interrupt nicht.
- **Grenze für Plugins:** `korg.backlight` setzt die Pins direkt. Wählt der Nutzer im Menü eine Mischfarbe mit Pegeln
  zwischen 1 und 14, überschreibt die PWM die Farbe des Plugins bei jedem Takt. Bei Pegeln 0 und 15 und beim Standardweiß
  bleibt die Farbe des Plugins stehen.
- **Offen:** Flimmern am Gerät, Wirkung auf das Netzteil und die Batterie, ob Blau bei Pegel 1 noch
  sichtbar ist.

## Display umkehren (15.10.)

- **Hergeleitet** (`0xC0015DD0` und die Seitenschreiber `0xC001613C`, `0xC00160C4`): das Display hängt an SPI0, die Datenleitung
  (GPIO 8.1) unterscheidet Befehl und Daten. Die Firmware schickt dem Baustein nur `0xB0` bis `0xB7` (Seite), `0x00`/`0x10`
  (Spalte), `0x40` (Startzeile) und `0x81` mit dem Kontrast (Befehle 0 bis 7 des Treibers, keiner davon schaltet die Polarität).
  Befehle der Einrichtung (Ein, Ausrichtung, Spannung) fehlen im Treiber (im Maschinencode `0xC0015500` bis `0xC0016300` kein
  Befehlswert `0xA0` bis `0xAF`, `0xC0`, `0xE2`); wer den Baustein einrichtet, ist nicht geklärt (im Emulator geschieht es nie).
  **Gemessen** über Start, Hauptbildschirm und Menüs: kein `0xA6`, kein `0xA7`
  ([Display-Helligkeit](2026-10-12-lcd-helligkeit.md)).
- **Annahme, am Gerät offen:** die Befehle sind die der ST7565-Familie (Seite `0xB0`, Spalte `0x10`/`0x00`, Startzeile `0x40`, Kontrast
  `0x81`, Reihenfolge und Werte passen dazu). In dieser Familie heißt `0xA6` normal und `0xA7` umgekehrt (Display reverse, jeder
  Punkt kehrt sich um, ohne dass der Anzeigespeicher sich ändert). Welcher Baustein tatsächlich verbaut ist, steht nirgends im
  Repository und ist nicht geprüft. Nimmt er `0xA7` nicht an, bleibt die Seite wirkungslos (das Display bleibt normal).
  Ersatz dann: den Anzeigespeicher in der Seitenschreib-Stelle bitweise umkehren (Software, kostet einen Durchlauf je
  Seite).
- **Haken** `lcd_invert_hook` an `0xC00161A4` (Kette `lcd-invert`, `data/hooks.mjs`): in der Seitenschreib-Funktion der Firmware nach den
  vier Befehlen für Seite und Spalte, die Datenleitung ist noch auf Befehl. Das Menü merkt sich, was es dem Baustein zuletzt
  schickte (`M_INV_HW`). Weicht der Wunsch (`M_INV`) davon ab, geht einmal `0xA7` (ON) oder `0xA6` (OFF) hinaus, sonst nichts. Mit
  OFF und ohne Datei (und Karte) wird dem Baustein nie ein Befehl geschickt, mit EXIT beim Einschalten ebenfalls nicht (der
  Haken prüft zuerst, ob das Menü scharf ist). Kein Flash, die Einstellung liegt in der Einstellungsdatei der Karte.
- **Datei:** Bit 28 des Worts `look` (siehe oben). Ältere Dateien (Version 1, oder Version 2 ohne das Bit) lesen sich als OFF, die
  Dateigröße bleibt. Wirkung: nach dem Lesen beim Start und beim Drehen sofort, mit dem nächsten geschriebenen Seitenstück des Displays
  (Seiten schreibt die Firmware nur, wenn sie sich ändern, beim Drehen ändert sich die Seite sofort).
- **Emulator:** `tools/emu/machine.py` nimmt `0xA6` und `0xA7` (`lcd_reverse`, `shown()` ist das Bild des Bausteins, im Speicher
  `fb` bleibt das Bild der Firmware), `tools/emu/lcd.py` rechnet mit der umgekehrten Anzeige weiter (die Punkte folgen mit ihrer
  Trägheit), der Dienst veröffentlicht und die Seite zeigt das umgekehrte Bild.
- **Gemessen** (`menu:look_invert_*`): Vorgabe OFF mit und ohne Karte, kein Befehl an den Baustein; die Seite ("DISPLAY INVERT",
  "Custom 8/9"); ON schickt genau einen `0xA7` und kehrt Menü und Hauptbildschirm um (jedes Bit des Bildes ist das Gegenteil des
  Speichers); OFF schickt `0xA6`; WRITE legt Bit 28 in die Datei; der nächste Start liest es und zeigt das Bild umgekehrt;
  Dateien ohne das Bit und beschädigte bleiben OFF; EXIT beim Einschalten: kein Befehl, Bild normal, auch wenn die Datei ON sagt.
  Bilder: `docs/images/blech-menue-v14/` (20 bis 24 und 28, nur lokal).

## Wo die Prüfung steht

`tools/emu/menu_cases.py` (`look_cases`): Vorgaben, Seiten, jede Option, Karte fehlt, Datei lesen und
schreiben, Version 1 der Datei, EXIT beim Einschalten, Power Save, LED-Sperre.
