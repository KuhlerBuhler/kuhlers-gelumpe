# Röhrenkurve statt Soft-Clipper am Ausgang, im QEMU-DSP-Kern und im Emulator

Belegt: DSP-Patch `tube-curve` (rot, Hacktribe und Korgs 2.02) und `tube-curve-synth` (blau) im QEMU-DSP-Kern,
BLECH > FEATURES > TUBE, TUBE DRIVE und TUBE ASYM im Emulator. **Keine Gerätemessung**, der Klang am Gerät ist **offen**.

## Was der Patch tut

Korgs Soft-Clipper am Master-Ausgang (rot `0xFFA0135C`, blau `0xFFA01348`) hat keine Parameter. Der Frame-Code ruft ihn
je Sample über eine feste Adresse auf (`P0.L = <Clipper>; CALL (P0)`, rot `0xFFA01746`, blau `0xFFA01738`), R0 zeigt
auf das Stereopaar. **offline**

Der Patch ändert vier Stellen im DSP-Bootstrom:

1. Der Aufruf zeigt auf eine eigene Routine. Sie liegt in zwei Funktionen, die nichts im DSP-Programm aufruft: Kopf rot
   `0xFFA02186`, blau `0xFFA020F6`, Schluss (Tiefpass und Schleifenende) rot `0xFFA0A974`, blau `0xFFA0A75C`. Am alten
   Platz allein ist für den Tiefpass kein Raum. Kein Aufruf, Sprung, keine Konstante zeigt hin, und eine am ersten
   Befehl gesetzte Ausnahme kam im QEMU-DSP-Kern über Start und Spielen nie (8 s, Pad gedrückt). **gemessen** (QEMU),
   **offline** (Programm gelesen)
2. Die Routine liest den Block bei `0xFF803FD0`, 12 Wörter am Ende von L1-Datenbank A: zwei Wörter Tiefpass-Zustand
   (gehört dem DSP), dann die Parameter. Ungepatcht greift kein DSP-Code und kein DMA auf `0xFF803FD0` bis
   `0xFF804000` zu: 0 Lese- und Schreibzugriffe in 8 s Start und Spielen, Hacktribe, rot und blau. **gemessen** (QEMU)
   Ist das Wort `on` 0, springt sie in Korgs Clipper: TUBE OFF ist Korgs Ausgabe
   Bit für Bit. Sonst rechnet sie Kurve und Tiefpass auf beiden Kanälen.
3. Die letzte Nullfüllung von Bank A im Bootstrom endete vor dem Block (rot `0xFF803FD0`, blau `0xFF803F5C`); sie
   reicht jetzt bis `0xFF804000`. Block und Tiefpass-Zustand stehen nach jedem Start auf 0 (OFF), egal was das RAM
   vorher hielt.

Die ARM-Seite (`tools/patch/script_menu.s`, `tube_tick`) schickt die 10 Parameterwörter ab `0xFF803FD8` über den
Host-Port (`0xAB`, 20 Halbwörter, rot `0xC0014284`, blau `0xC000FB44`), sobald sich TUBE, TUBE DRIVE oder TUBE ASYM
ändert. Den Tiefpass-Zustand fasst sie nie an. Korg schreibt L1 selbst auf diesem Weg.

## Die Kurve

Vorbild ist die Valve-Force-Stufe der ESX/EMX: eine 12AX7 als Differenzpaar, etwa 8,7 V an jeder Triode, 100 µA
Tail-Strom. Mit der Gitterspannung u ist sie symmetrisch und tanh-ähnlich, 50 % bei ±0,14 V, gesättigt ab ±0,34 V.
**hergeleitet** (Koren-Triodenmodell, von Hand bei 9 V angepasst; die Form stimmt, dB-Werte nicht)

Im DSP ist sie ein ungerades Polynom 7. Grades in v = u / 0,37 V, jenseits |v| = 1 geklemmt, größter Fehler 0,0045
gegen das Koren-Modell. TUBE DRIVE legt fest, welche Gitterspannung Vollaussteuerung bedeutet; der Ausgang ist auf
jeder Stufe so normiert, dass Vollaussteuerung Vollaussteuerung bleibt (kein Pegelregler). Rechnung und Rundung:
`tools/dsp/tube_model.py`.

| TUBE DRIVE | 1 | 2 | 3 | 4 (Vorgabe) | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Gitter bei Vollaussteuerung | 0,05 V | 0,08 V | 0,13 V | 0,2 V | 0,32 V | 0,5 V | 0,8 V |
| Tiefpass-Ecke | 16 kHz | 14 kHz | 12,5 kHz | 11 kHz | 10 kHz | 9 kHz | 8 kHz |

### Tiefpass

Nach der Kurve glättet ein einpoliger Tiefpass je Kanal die Höhen: y = y + a (t - y), a = 1 - e^(-2π f / 48 kHz). Die
Ecke f hängt fest an TUBE DRIVE (Tabelle oben): mehr Drive, weichere Höhen, wie bei einer Röhrenstufe mit Miller-Kapazität
und Ausgangsübertrager. Kein eigener Regler. **hergeleitet** (Werte von Hand gewählt, am Gerät nicht angehört)

### TUBE ASYM

TUBE ASYM 0 bis 7 fährt die positive Halbwelle schwächer an als die negative: Verstärkung k = 1 - 0,045 · ASYM
(1 bis 0,685), die negative Halbwelle bleibt. Die Kurve ist dann nicht mehr ungerade, es entsteht die 2. Harmonische
einer Triodenstufe. ASYM 0 ist die symmetrische Kurve. Die ARM-Seite rechnet gp = g · k selbst und schickt es mit.

Folge: Mit ASYM > 0 trägt der Ausgang einen kleinen Gleichanteil (die positive Halbwelle ist leiser). Bewusst so
gelassen, kein Hochpass im DSP (kostet Takte; ob der Gleichanteil am Ausgang hörbar oder messbar ist, ist offen).
**hergeleitet**

## QEMU-DSP-Kern

`tools/dsp/tube_qemu.py` lädt den DSP-Bootstrom einer gepatchten SYSTEM.VSB in den QEMU-Kern (#671) und ruft die
Ausgangsfunktion so auf wie der Frame-Code, je 4000 Stereopaare (Randwerte und Zufall, Seed 1), mit Tiefpass-Zustand
über alle Paare. Gleiche Zahlen auf Hacktribe 2.02, Korgs roter 2.02 und Korgs blauer 2.02. **gemessen** (QEMU)

| Prüfung | Ergebnis |
|---|---|
| Block nach dem Start | alles 0 |
| OFF gegen Korgs ungepatchten Clipper | 0 Abweichungen |
| TUBE DRIVE 1 bis 7 je mit TUBE ASYM 0, 3, 7 gegen `tube_model.model()` | je 0 Abweichungen (21 Paare) |
| CYCLES je Aufruf: Korgs Clipper / OFF / ON | 76 / 86 / 144 |

ON kostet 68 Takte je Stereopaar mehr als Korgs Clipper (vorher ohne Tiefpass und ASYM 29), OFF 10 (der Test auf `on`
und der Sprung). Bei 48 kHz und 516 MHz sind 68 Takte etwa 0,6 % der DSP-Zeit. **hergeleitet**

## Emulator

`tools/emu/tube_cases.py` auf Hacktribe 2.02, Korgs roter 2.02 und Korgs blauer 2.02 mit BLECH, je 9/9 grün; die
Menü-Gruppen (Liste, Seiten, Einstellungen v4/v5 9/9, Flash 17/17) ebenfalls auf allen drei. **gemessen** (Emulator)

- Die Seiten TUBE, TUBE DRIVE und TUBE ASYM stehen vor KEY PADS, TUBE steht auf OFF, nichts geht an den DSP.
- TUBE ON schickt den Block der Vorgabe (4), TUBE DRIVE 4, 6, 7, 1 schickt jeden Schritt sofort.
- TUBE OFF schickt den OFF-Block; TUBE DRIVE bleibt dabei einstellbar (3) und gilt beim nächsten ON.
- WRITE legt das Feld in Byte 7 einer Version-4-Einstellungsdatei ab (Bits 5 bis 7: 0 OFF, 1 bis 7 ON mit dieser Stufe).
- TUBE ASYM zeigt 0 bis 7 und schickt jeden Schritt sofort (3, 7, 2), solange TUBE ON ist.
- WRITE mit TUBE ASYM 2 schreibt eine Version-5-Datei: Byte 4 = 5 | ASYM << 5. Mit ASYM 0 bleibt es bei Version 4
  (oder 3 ohne Bits in Byte 7), so liest ein BLECH bis 1.4.7 die Datei weiter. Ein BLECH bis 1.4.7 liest Version 5
  nicht und nimmt die andere Kopie oder die Vorgaben.
- Version 3 und 4 mit gesetzten Bits 5 bis 7 in Byte 4 werden abgelehnt; der Flash-Rundlauf mit ASYM 6 liest 5 | 6 << 5
  zurück (menu_cases `settings_v4_cases`).
- Der nächste Start mit dieser Datei schickt den Block genau einmal und zeigt TUBE ON, TUBE DRIVE 3, TUBE ASYM 2.
- Eine Kopie ohne DSP-Patch (Korgs Aufruf zurückgesetzt) zeigt die Seiten nicht und schickt nichts, auch mit TUBE ON
  in der Datei.

Bei OFF ist TUBE DRIVE nur im RAM: nach einem Neustart mit TUBE OFF zeigt die Seite wieder die Vorgabe 4.

## Offen

- Klang und Pegel am Gerät (rot, blau), ob Stufe 4 als Vorgabe passt, ob die Tiefpass-Ecken und ASYM-Stufen gut klingen
  (Hörvergleich mit einer ESX).
- Ob 68 Takte je Paar am Gerät zu Aussetzern führen, wenn der DSP schon voll ist (QEMU zählt Takte, nicht die Last).
- Dynamischer Bias ("Atmen") kommt in 1.4.9.
