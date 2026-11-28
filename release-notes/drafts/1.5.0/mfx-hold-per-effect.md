BLECHTRIBE 1.5.0 und die App 1.5.0.

**Geändert**
- MFX HOLD bei MFX 2 gilt für jeden Effekt einzeln
  - Was: bisher teilten sich MFX 1 und MFX 2 den Hold: ein in MFX 1 gehaltener Effekt lief nach TOUCH SCALE als MFX 2 weiter und umgekehrt. Jetzt merkt sich jeder der beiden seinen eigenen Hold-Zustand und seine Pad-Position (X und Y). Beim Umschalten wird ein gehaltener Effekt losgelassen und der Zustand des anderen kommt zurück.
  - Gut zu wissen: im DSP läuft weiter nur ein Effekt, es klingt immer einer von beiden. Der Hold von MFX 2 liegt nur im RAM, ein geladenes Pattern startet MFX 2 losgelassen. WRITE in MFX 2 speichert Hold und X/Y von MFX 1, das gespeicherte Pattern ist also wie bei Korgs Firmware. Rot; für die blaue nicht neu gebaut und nicht gemessen.

## English

**Changed**
- MFX HOLD with MFX 2 is kept per effect
  - What: until now MFX 1 and MFX 2 shared the hold: an effect held in MFX 1 kept running as MFX 2 after TOUCH SCALE, and the other way round. Now each of the two remembers its own hold state and pad position (X and Y). When you switch, a held effect is released and the state of the other one comes back.
  - Good to know: the DSP still runs one effect, only one of the two sounds at a time. The hold of MFX 2 lives in RAM only, a loaded pattern starts MFX 2 released. WRITE in MFX 2 stores the hold and X/Y of MFX 1, so the saved pattern is what Korg's firmware would write. Red; not rebuilt or measured for the blue.
