# Native Aufnahme für 1.6

**Offline geprüft:** Die Aufnahme läuft im DSP-Simulator und im ARM-Emulator auf beiden Sampler-Builds,
Korg 2.02 und Hacktribe, sowie auf Korgs blauer Electribe 2 als Mono-Aufnahme. **Offen:** Geräteabnahme,
Kartenschreibzeiten und lange Sets. Ein Tester für die blaue Electribe ist vorhanden; sein Bericht steht aus.
Dieser Stand ist noch keine Freigabe für das Gerät.

## Passender App-Prüfer

Ein Aufnahme-Patch verändert das DSP-Programm absichtlich. Der Prüfer einer älteren installierten GELUMPE-App
kennt diesen Abgriff noch nicht und meldet deshalb einen Fehler bei „DSP-Programm unverändert“.
Die Dateiendung `.patch` oder `.bsdiff` ändert daran nichts: Import und Emulatorprüfung sind getrennte Schritte.
Für diesen Teststand braucht die Desktop-App auch den aktuellen gebündelten Emulator mit dem kanonischen
Aufnahme-DSP-Prüfer. Ein bloßes Laden der Patch-Datei aktualisiert ihn nicht. Die DSP-Prüfung bleibt eingeschaltet.

## Aufnehmen

1. In Menü -> BLECH -> FEATURES -> NATIVE RECORDING auf ON stellen. Die Vorgabe ist OFF; WRITE behält die Einstellung.
2. SHIFT+REC öffnet beim Sampler die Sampling-Ansicht. Mit EDIT rechts zur Quelle wechseln und RECORD wählen.
   Auf Korgs blauer Electribe öffnet SHIFT+REC direkt die eigene RECORD-Ansicht im BLECH-Menü.
3. PLAY startet das Pattern und die Aufnahme. Die Ansicht schließt sich, Korgs eigenes Sampling startet nicht.
4. STOP beendet das Pattern und die Aufnahme und schließt die WAV. Vor dem Herausnehmen der Karte den Abschluss abwarten.

Pause (PLAY während das Pattern läuft) und REC während der Aufnahme lassen sie weiterlaufen. REC bleibt dabei die normale
Pattern- und Motion-Aufnahme, die REC-LED gehört ihr: die Aufnahme lässt die LED aus, ihr Zeichen ist der Punkt auf dem
Bildschirm. REC in der Ansicht startet keine Aufnahme. Ohne laufende Aufnahme schließt REC die Ansicht wie bei Korg, mit
laufender Aufnahme beendet REC in der Ansicht sie. PLAY in der Ansicht startet keine zweite Aufnahme.
REC und PLAY außerhalb dieser Ansicht bleiben die normalen Tasten.

Außerhalb der Ansicht blinkt während der Aufnahme ein Punkt oben auf dem Hauptbildschirm zwischen BPM und LOAD METER
(Spalten 78 bis 82). Nach dem Abschluss verschwindet er. Im Emulator geprüft, am Gerät noch nicht.

## Was in der Datei steht

Die Sampler schreiben Stereo-WAV, Korgs blaue Electribe Mono-WAV mit 48 kHz und 16 Bit nach
`Recordings/REC0001.WAV` auf der SD-Karte. Mono bildet den Mittelwert beider Ausgangskanäle; auch rechts
gepannte Klänge werden erfasst. Hacktribe auf blauer Hardware verwendet weiterhin den Sampler-Code mit Stereo.
Weitere Namen steigen bis `REC9999.WAV`; vorhandene Dateien werden nicht überschrieben. Kurz vor 4 GiB beginnt
eine Folgedatei. Name und Dauer in der Anzeige gehören zur aktuellen Datei.

Aufgenommen wird der Mastermix nach MFX und dem vorhandenen Soft-Clipper, einschließlich AUDIO IN/THRU. Das Metronom bleibt hörbar,
steht aber nicht auf der Aufnahme. Der Signalweg ist im DSP-Simulator geprüft, noch nicht am Gerät abgenommen.

Während der Aufnahme sind SAMPLING, RESAMPLING und Apps mit eigener Audioerfassung wie Spettro gesperrt.
Gepufferte Plugin-Daten und Einstellungen warten bis zum Abschluss. Dateiaktionen wie Plugin-Import und -Export
zeigen währenddessen `recording`; ein wartendes Speichern zeigt `after recording`.

## Wenn etwas abbricht

| Anzeige | Bedeutung |
|---|---|
| No card | Es steckt keine Karte. Die Aufnahme startet nicht. |
| Card full | Die Karte ist voll. Hat die Aufnahme bereits begonnen, bleibt ihr gültiger Anfang als WAV erhalten. |
| Card error | Ein Kartenzugriff ist fehlgeschlagen oder die Karte wurde entfernt. Der letzte gesicherte Zwischenstand bleibt erhalten. |
| `REC 00:01:23 #2` | Zweimal kam der Ton nicht rechtzeitig vom DSP. Die fehlende Zeit ist als Stille in der Datei, die Aufnahme läuft weiter. Die Zahl bleibt nach dem Speichern stehen (`Saved 00:01:30 #2`). |
| Capture gap, Capture lost, Ring full | Die Erfassung konnte nicht fortgesetzt werden. Die Aufnahme stoppt mit sichtbarem Zähler und einem benannten cue-Punkt am Ende des gültigen PCM-Anfangs. |
| No memory | Für den Aufnahmering war kein ausreichender Speicherblock frei; die Aufnahme hat nicht begonnen. |

Bricht eine Aufnahme ab, bevor sie ein Sample geschrieben hat, löscht der Sampler die leere WAV wieder und vergibt ihre
Nummer neu. Der electribe sampler kann das; der electribe synth hat in seiner Firmware kein Löschen, dort bleibt die
leere Datei liegen. Für die Fehlersuche hält der Zustand der Aufnahme den ersten Abbruch seit dem Einschalten und den
letzten fest: welche Prüfung des Lesers fehlschlug, die DSP-Werte, die er dabei sah, und den Zeitpunkt
(`recording_runtime.py`, Felder ab `FAULTS`). Ein einfaches READ liest sie aus.

Der Schreiber sichert alle fünf Sekunden Aufnahme einen gültigen Zwischenstand. Bei Stromausfall oder Kartenentnahme können noch
gepufferte Daten fehlen. Geprüft sind SD-Abbilder an den Grenzen der Dateiaufrufe, kein Stromausfall mitten in einem
physischen Sektorschreibvorgang. Kommt der Ton zu spät vom DSP, steht die fehlende Zeit als Stille in der Datei und der
Zähler hinter `#` zeigt es an; die Stille verdeckt den Fehler also nicht.

## Was noch fehlt

Die endgültige Ringwahl wartet auf die Schreib- und Laufzeitmessungen am Gerät. Der Schreiber schreibt in Stücken von
8 KiB, und neben dem CommandTask liest auch der UI-Frame den DSP-Ring; im Emulator übersteht eine Aufnahme so eine Karte,
die 400 ms hängt (`native_stall_*`). Am Gerät ist das noch nicht geprüft. Die Kartenzugriffe von Sample Swap werden nach
dessen Integration geprüft. Plugins lesen den Stand der Aufnahme über `korg.record` (läuft, Sekunden, Lücken, API 41);
starten oder stoppen können sie sie nicht. Der spätere WAV-Player gehört nicht zu diesem Aufnahmestand. Die geplante neue Röhrenkurve ist ebenfalls noch nicht enthalten.

Belege und offene Messwerte: [native Aufnahme](messungen/2026-11-17-native-aufnahme.md).

## Geräteprüfung auf der blauen Electribe

Nur nach eigener Freigabe des Teststands am Gerät prüfen. Die bisherigen Fälle verwenden die eigene Originaldatei
im Emulator. Sie belegen weder Schreibzeiten der Karte noch die tatsächliche DSP- und Task-Laufzeit.

1. Mit NATIVE RECORDING OFF muss SHIFT+REC weiterhin das ursprüngliche Verhalten behalten.
2. Auf ON stellen, mit SHIFT+REC die RECORD-Ansicht öffnen. REC allein darf keine WAV erzeugen.
3. Mit PLAY starten, links und rechts gepannte Klänge sowie AUDIO IN/THRU spielen. Die REC-LED bleibt aus. Mit STOP
   beenden; SHIFT+REC zeigt dann `Saved`.
4. Die WAV am Rechner prüfen: ein Kanal, 48 kHz, 16 Bit, hörbare linke und rechte Klänge, kein Metronom.
5. Bei laufender Aufnahme PLAY (Pause), REC und EXIT verwenden. Die Aufnahme muss weiterlaufen. Mit STOP beenden.
6. Gerätetyp, Firmware, Karte, Aufnahmedauer, angezeigte Fehler und hörbare Aussetzer in der
   [Messdatei](messungen/2026-11-17-native-aufnahme.md) festhalten. Einen langen Lauf erst nach den offenen
   Schreib- und Leserzeitmessungen bewerten.
