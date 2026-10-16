# Idee 28: Pseudo-Reverb als Insert-Preset

Stand: als Vorschlag im Bereich Presets gebaut, am Gerät ungehört. Zurück zu den [Ideen](../ideen.md).

Nativen Hall gibt es nur als Master-FX (Touchpad), keinen Insert-Reverb ([Master-Preset und DSP](../messungen/2026-10-09-mfx-dsp.md)). Aus `I_short_delay` (kurzes Delay mit Feedback und dunklem Filter) lässt sich ein Ambience-Preset pro Part bauen, ohne das Touchpad zu belegen.

- Am Gerät testen, Audio ist im Emulator nicht prüfbar.
- `short_delay` als Effekt der Stufe 2 ist „fatal“: er lässt den Ton geräteweit verstummen und braucht einen Neustart ([Ketten](../messungen/2026-09-14-stage2-chains.md)). Als primärer Insert ist er ungeprüft.

## Was gebaut ist

Ein Vorschlag, keine eigene Preset-Datei: `data/suggestions.mjs` hält sechs Parameterwerte (`tempo_sync` 0, `off_delay_time` 19, `fb_depth` 64, `high_damp` 72, `low_damp` 8, `wet_level` 56). Wer im Bereich Presets ein Insert-Preset mit Short Delay in Stufe 1 öffnet, sieht den Kasten "Vorschlag: Pseudo Reverb" mit dem Hinweis "am Gerät ungetestet" und dem Knopf "Werte übernehmen". Der setzt diese sechs Werte auf den offenen Datensatz und berührt kein anderes Byte, auch den Namen nicht: ein Datensatz wird bearbeitet, nie aus Nullen gebaut. Danach geht er wie jede Änderung durch den Türsteher.

- **Die Werte sind nicht gehört.** Sie liegen innerhalb dessen, was die Werks-Presets desselben Bausteins benutzen, das Feedback unter der Grenze von 90 ([Pegel](../messungen/2026-09-21-loudness.md)). Ob das nach Raum klingt, ist offen.
- **Stufe 2 bleibt gesperrt.** Steht `short_delay` in Stufe 2, zeigt der Kasten statt des Knopfs den Grund, und der Linter nennt den Datensatz weiter `fatal` (Regel `stage2-fatal`, [Linter](../linter.md)); der Türsteher sperrt das Senden. Eine neue Regel war dafür nicht nötig, sie gab es schon und ein Test hält sie fest. Hinter dem Baustein in Stufe 1 darf keine zweite Stufe stehen, das ist nicht gehört.

## Offen

- Am Gerät hören und die Werte danach nachstellen; erst dann sind sie mehr als eine Vermutung.
- Ein eigener Name für das Preset ist nicht gesetzt.
