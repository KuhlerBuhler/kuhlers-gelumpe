# Effekt-Katalog: Bass, Kick, Verzerrer und Mastering

Der Katalog im Baukasten (`BLECHTRIBE -> Baukasten -> Katalog`) hat neben den Delays jetzt Effekte für Bässe, Kicks,
Verzerrung und Mix. Die Insert- und Master-Effekte stehen nach dem Patchen fest in den Menüs (hinter den Presets der Firmware),
die Modulationen gehen über den Export auf die Karte. Alle Werte sind die Parameter der 66 DSP-Bausteine, die schon in der
Firmware stecken: es gibt keine neuen Bausteine, ein Effekt ist eine Einstellung davon.

**Am Gerät ist keiner dieser Effekte gehört.** Der Emulator rechnet kein Audio, er zeigt nur, dass die Presets sauber in die
Menüs kommen und dem DSP ihre Werte schicken ([Messung](messungen/2026-11-11-neue-effekte.md)). Die Werte sind aus den
Werkspresets derselben Bausteine hergeleitet. Wenn dir einer zu laut, zu leise oder anders vorkommt, ist das der Hörtest, der noch fehlt.

## Bässe, die springen

Das Problem: die Hüllkurve des Verstärkers klingt zu lang aus und setzt zu langsam ein, die Bassline schiebt statt zu springen. Die
Firmware hat dafür keinen Regler im Effekt, aber zwei Wege:

| Name | Art | Was er tut |
|---|---|---|
| Bounce Gate 16 | Insert | Eine Hüllkurve auf jeder Sechzehntel: schneller Anschlag, kurzes Abklingen. Regler von sanft bis hart, Play setzt den Takt neu an. |
| Bounce Gate 8 | Insert | Dasselbe auf Achtel. |
| Bounce Pluck | Modulation | Jede Note öffnet den Filter kurz und gibt einen kleinen Lautstärke-Schub. Aus einem langen Bass wird ein Pluck. |
| Bounce Pitch | Modulation | Jede Note springt kurz etwa einen Halbton hoch und fällt zurück. Federt. |

Das Gate hängt am Takt der Maschine, nicht an der Note: Noten, die neben dem Raster liegen, werden angeschnitten. Die
Modulationen hängen an der Note und gehen mit jedem Rhythmus. Die Modulationen legst du auf einen Platz der EG+-Arten (1 bis 6):
die Zeit der Hüllkurve (MOD. SPEED) kommt vom Platz, den du überschreibst.

## Bass sauber lauter

| Name | Art | Was er tut |
|---|---|---|
| Bass Enhancer | Insert, zwei Stufen | EQ mit Tiefen-Regal und etwas weniger Tiefmitten, dahinter ein Limiter. Regler: mehr Bass, weniger Eingangspegel. |
| Glue Comp | Insert, zwei Stufen | Kompressor (SR1) mit Limiter dahinter. Regler: Schwelle runter, Pegel ausgleichen. |

## Kicks

| Name | Art | Was er tut |
|---|---|---|
| Hardtekk Kick | Insert, zwei Stufen | Hart verzerrt: Bass vor der Verzerrung hoch, danach wieder aufgefüllt, Limiter dahinter. |
| Tekk Kick Soft | Insert, zwei Stufen | Acid Drive mit EQ dahinter (Bass hoch, Klick oben). Weicher. |
| Kick Drop | Modulation | Die Tonhöhe startet hoch und fällt in Millisekunden ab, dazu ein Lautstärke-Schub. |
| Kick Click | Modulation | Ein sehr kurzer, hoher Pitch-Sprung vorn: der Klick. |

## Verzerrer

| Name | Art | Was er tut |
|---|---|---|
| Warm Drive | Insert, zwei Stufen | Wenig Drive, EQ dahinter: wärmer und dichter. |
| Bass Drive | Insert | Verzerrung, die den Tiefbass stehen lässt. |
| Scream Drive | Insert | Mitten kräftig angehoben, für Leads und Acid. |
| Tight Fuzz | Insert | Fuzz ohne Bass, eng und bissig. |
| Bit Grinder | Insert | Bittiefe zerhackt. |
| Alias Crush | Insert | Abtastrate runter, Aliasing. |

## Mix und Master

| Name | Art | Was er tut |
|---|---|---|
| Tilt EQ | Insert | Kippt den Klang: links heller, rechts dunkler, Mitte unverändert. |
| Mix Clean Up | Insert | Rumpeln unten und Dröhnen in den Tiefmitten raus, oben etwas Luft. |
| Master Glue | Master | Kompressor auf der Summe. X dreht die Schwelle runter. |
| Master Tilt | Master | Die Summe um sechs Stufen kippen: X nach links heller, nach rechts dunkler. |
| Master Warmth | Master | Leichte Röhrensättigung auf der Summe. |

## Was nicht geht

- **Kein Falten, keine neue Verzerrer-Art.** Die Firmware hat im Insert zwei Verzerrer (Distortion, Acid Drive) und den Decimator, im
  Master Distortion, Decimator und die Röhrenvorstufe. Die Effekte oben sind verschiedene Einstellungen davon.
- **Keine Hüllkurve des Verstärkers im Effekt.** Attack und Decay des Verstärkers sind Werte des Parts, ein Effekt kommt nicht an sie
  heran. Ein Effekt kann nur im Takt formen (Bounce Gate), eine Modulation nur an der Note (Bounce Pluck).
- **Kein Kompressor als Modulation.** Eine Modulation bewegt Tonhöhe, Oszillator, Filter, Lautstärke, Pan und den Insert-Effekt,
  sie misst keinen Pegel.
- **Zwei Stufen nur mit gemessenen Bausteinen.** In Stufe 2 stehen hier nur EQ, Limiter, Acid Drive und Filter, die in der
  [Messreihe](messungen/2026-09-21-stage2-sweep.md) ohne Absturz liefen. Der Decimator läuft nur allein, der Kompressor SR1 nur in Stufe 1.

Die Namen sind höchstens 15 Zeichen lang, so viele zeigt die Firmware.
