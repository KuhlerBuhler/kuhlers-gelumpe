# TAP Motion: einmal abspielen, TOUCH SCALE wie MASTER FX

Stand 2026-10-17. Alles im Emulator (`tools/emu/tap_motion_cases.py`, Gruppen `case_once` und `case_touch_scale`), mit BLECH auf
Hacktribe (eigene `SYSTEM.VSB`) und auf Korgs Original der blauen Electribe 2. Am Gerät ist nichts geprüft.
Baut auf [TAP Motion](2026-10-15-tap-motion-patch.md) auf. Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Einmal (Einstellung 2)

Mit dem Einstellungswort `TM_SETTING` auf 2 spielt eine Bewegung, die TAP eingeschaltet hat, bis zum Ende des Patterns und geht dann
von selbst aus. Gemerkt wird je Part der Schrittzähler (`0xC06904B0 + 0x48 * Part`) beim Einschalten. In jedem Bildschirm-Takt der UiTask
vergleicht der Patch: ist der Zähler kleiner als beim letzten Blick, hat das Pattern neu angefangen, und der Part geht aus wie mit TAP
(gemerkter Modus, Setter der Firmware). Steht der Sequencer, wird nicht verglichen.

- **Gemessen (`once_plays_to_the_end`):** Regler in den Schritten 16 bis 31 aufgenommen, TAP aus bei Schritt 2, an bei Schritt 8: der erste
  Durchlauf spielt 16 von 16 Schritten, der zweite und dritte keinen, danach ist das Byte 0 (und die Kopie).
- **Gemessen (`once_comes_back_with_tap`):** TAP danach schaltet wieder ein, mit dem gemerkten Modus.
- **Gemessen (`on_keeps_playing`):** mit der Einstellung 1 (an) spielt auch der zweite Durchlauf.
- **Hergeleitet:** Master FX hat keinen eigenen Zähler, der Patch nimmt den von Part 1. Hat Part 1 einen kürzeren LAST STEP als das
  Pattern, gehen die Master-FX-Spuren früher aus. **Offen** am Gerät.
- **Am Gerät (Besitzer, 17.10.):** mit ONCE ging die Bewegung der Master-FX-Spuren am Patternende aus, der Effekt (Highpass,
  Looper) blieb aber an; mit MASTER FX gehalten plus TAP geht er aus. Der Emulator zeigt das nicht (das Pad steht dort danach auf aus).
- **Behoben (hergeleitet):** TAP läuft in der UiTask, ONCE lief im Takt des LED-Managers. ONCE schaltet jetzt im Bildschirm-Takt der
  UiTask ab (Haken am Aufruf `0xC00836F0` der Bildschirm-Schleife, beim blauen `0xC0073CF4`), also im selben Task wie TAP. Im Emulator
  bestehen alle 36 Prüfungen auf beiden Builds; ob der Effekt am Gerät jetzt ausgeht, ist **offen**.
- **Offen:** ob beim Ausschalten am Patternanfang der Wert von Schritt 1 noch einmal kurz anliegt (der Vergleich läuft im 40-ms-Takt,
  ein Schritt dauert bei 160 BPM 94 ms).

## TOUCH SCALE gehalten plus TAP

Mit MFX 2 auf TOUCH SCALE ([MFX 2](2026-10-10-mfx-umschalter.md)) schaltet TOUCH SCALE gehalten plus TAP die Master-FX-Spuren, genau wie
MASTER FX gehalten plus TAP. Der Patch fragt beide Tasten (Tastenzustand der UiTask, Taste 5 und 6).

- **Gemessen (`touch_scale_tap_switches_mfx`):** Geste aufgenommen, TOUCH SCALE gehalten, TAP: Byte `+0x44` von 1 auf 0, nochmal TAP auf 1,
  der Part bleibt an.
- **Gemessen (`touch_scale_led_shows_mfx`):** solange TOUCH SCALE gehalten ist, zeigt die TAP-Lampe die Master-FX-Spuren (an, nach dem
  Ausschalten aus, obwohl der Part an ist).
- **Gemessen:** mit dem Patch von 1.0.0 fallen beide Prüfungen durch (TAP schaltete dort den Part).
