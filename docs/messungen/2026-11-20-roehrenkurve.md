# Röhrenkurve statt Soft-Clipper am Ausgang, im QEMU-DSP-Kern und im Emulator

Belegt: DSP-Patch `tube-curve` (rot, Hacktribe und Korgs 2.02) und `tube-curve-synth` (blau) im QEMU-DSP-Kern,
BLECH > FEATURES > TUBE und TUBE DRIVE im Emulator. **Keine Gerätemessung**, der Klang am Gerät ist **offen**.

## Was der Patch tut

Korgs Soft-Clipper am Master-Ausgang (rot `0xFFA0135C`, blau `0xFFA01348`) hat keine Parameter. Der Frame-Code ruft ihn
je Sample über eine feste Adresse auf (`P0.L = <Clipper>; CALL (P0)`, rot `0xFFA01746`, blau `0xFFA01738`), R0 zeigt
auf das Stereopaar. **offline**

Der Patch ändert drei Stellen im DSP-Bootstrom:

1. Der Aufruf zeigt auf eine eigene Routine (rot `0xFFA02186`, blau `0xFFA020F6`). Dort liegt eine Funktion, die nichts
   im DSP-Programm aufruft: kein Aufruf, Sprung, keine Konstante zeigt hin, und eine dort gesetzte Ausnahme kam im
   QEMU-DSP-Kern über Start und Spielen nie. **gemessen** (QEMU), **offline** (Programm gelesen)
2. Die Routine liest den Parameterblock bei `0xFF803FE0` (Ende von L1-Datenbank A, kein DSP-Code greift dorthin). Ist
   das Wort `on` 0, springt sie in Korgs Clipper: TUBE OFF ist Korgs Ausgabe Bit für Bit. Sonst rechnet sie die Kurve
   auf beiden Kanälen.
3. Die letzte Nullfüllung von Bank A im Bootstrom endete vor dem Block (rot `0xFF803FD0`, blau `0xFF803F5C`); sie
   reicht jetzt bis `0xFF804000`. Der Block steht nach jedem Start auf 0 (OFF), egal was das RAM vorher hielt.

Die ARM-Seite (`tools/patch/script_menu.s`, `tube_tick`) schickt den Block über den Host-Port (`0xAB`, 16 Halbwörter,
rot `0xC0014284`, blau `0xC000FB44`), sobald sich das TUBE-Feld ändert. Korg schreibt L1 selbst auf diesem Weg.

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

## QEMU-DSP-Kern

`tools/dsp/tube_qemu.py` lädt den DSP-Bootstrom einer gepatchten SYSTEM.VSB in den QEMU-Kern (#671) und ruft die
Ausgangsfunktion so auf wie der Frame-Code, je 4000 Stereopaare (Randwerte und Zufall, Seed 1). Gleiche Zahlen auf
Hacktribe 2.02, Korgs roter 2.02 und Korgs blauer 2.02. **gemessen** (QEMU)

| Prüfung | Ergebnis |
|---|---|
| Parameterblock nach dem Start | alles 0 |
| OFF gegen Korgs ungepatchten Clipper | 0 Abweichungen |
| TUBE DRIVE 1 bis 7 gegen `tube_model.model()` | je 0 Abweichungen |
| CYCLES je Aufruf: Korgs Clipper / OFF / ON | 76 / 86 / 105 |

ON kostet 29 Takte je Stereopaar mehr als Korgs Clipper, OFF 10 (der Test auf `on` und der Sprung).

## Emulator

`tools/emu/tube_cases.py` auf Hacktribe 2.02, Korgs roter 2.02 und Korgs blauer 2.02 mit BLECH, je 7/7 grün.
**gemessen** (Emulator)

- Die Seiten TUBE und TUBE DRIVE stehen vor KEY PADS, TUBE steht auf OFF, nichts geht an den DSP.
- TUBE ON schickt den Block der Vorgabe (4), TUBE DRIVE 4, 6, 7, 1 schickt jeden Schritt sofort.
- TUBE OFF schickt den OFF-Block; TUBE DRIVE bleibt dabei einstellbar (3) und gilt beim nächsten ON.
- WRITE legt das Feld in Byte 7 einer Version-4-Einstellungsdatei ab (Bits 5 bis 7: 0 OFF, 1 bis 7 ON mit dieser Stufe).
- Der nächste Start mit dieser Datei schickt den Block genau einmal und zeigt TUBE ON, TUBE DRIVE 3.
- Eine Kopie ohne DSP-Patch (Korgs Aufruf zurückgesetzt) zeigt die Seiten nicht und schickt nichts, auch mit TUBE ON
  in der Datei.

Bei OFF ist TUBE DRIVE nur im RAM: nach einem Neustart mit TUBE OFF zeigt die Seite wieder die Vorgabe 4.

## Offen

- Klang und Pegel am Gerät (rot, blau), ob Stufe 4 als Vorgabe passt.
- Ob 29 Takte je Paar am Gerät zu Aussetzern führen, wenn der DSP schon voll ist (QEMU zählt Takte, nicht die Last).
