# 60. Time-Stretch am Gerät

Das Tempo eines Samples ändern, ohne dass sich die Tonhöhe ändert. Übersicht in [ideen.md](../ideen.md), Zeile 60.

## Manuell mit SHIFT + Regler (Idee aus dem Ideen-Kanal, 17.11.)

SHIFT + EDIT-Regler streckt oder staucht das Sample im Pattern, bedient wie Pitch, nur ohne Änderung der Tonhöhe.

- Pitch ändert heute die Abspielgeschwindigkeit, Tonhöhe und Länge ändern sich dabei gemeinsam. Tempo ohne Tonhöhe ist
  schon der eigentliche Time-Stretch, gleich ob ein Regler oder das BPM den Faktor vorgibt. (Urteil)
- Am Regler drehen und sofort hören heißt Stretch in Echtzeit im DSP, die schwerste Stufe. (Urteil)

## Reihenfolge

1. **Offline mit manuellem Faktor:** SHIFT + Regler stellt den Faktor ein (etwa 85 bis 115 %), das Gerät rechnet das Sample
   einmal neu und spielt die neue Fassung. Das ist der Kern der Offline-Stufe, nur mit Faktor statt Ziel-BPM.
2. **Offline mit BPM:** Ausgangs- und Zieltempo statt Faktor, im Sample-Editor ([Idee 59](59-sample-editor.md)).
3. **Live:** der Loop folgt beim Spielen dem Tempo oder dem Regler, wie die Stretch-Parts der Electribe SX. Braucht
   Rechenzeit im DSP und hängt an der DSP-Forschung ([Idee 26](26-dsp-erfassen.md)).

Ob Stufe 1 und 3 auf dem Gerät gehen (Qualität, Rechenzeit, Speicher), ist nicht geprüft.
