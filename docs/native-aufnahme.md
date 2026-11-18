# Native Aufnahme für 1.6

**Offline geprüft:** Die Aufnahme läuft im DSP-Simulator und im ARM-Emulator auf beiden Sampler-Builds,
Korg 2.02 und Hacktribe. **Offen:** Geräteabnahme, Kartenschreibzeiten und lange Sets. Die blaue Mono-Aufnahme
braucht noch ihre Umsetzung und einen Tester. Dieser Stand ist noch keine Freigabe für das Gerät.

## Aufnehmen

1. In Menü -> BLECH -> FEATURES -> NATIVE RECORDING auf ON stellen. Die Vorgabe ist OFF; WRITE behält die Einstellung.
2. SHIFT+REC öffnet die Sampling-Ansicht. Mit EDIT rechts zur Quelle wechseln und RECORD wählen.
3. REC startet die Aufnahme. Die Anzeige nennt die Datei und ihre aufgenommene Dauer.
4. REC beendet die Aufnahme und schließt die WAV. Vor dem Herausnehmen der Karte den Abschluss abwarten.

PLAY steuert das Pattern unabhängig von der Aufnahme. PLAY startet keine Aufnahme und beendet eine laufende Aufnahme
nicht. Schließt PLAY oder EXIT die Ansicht, öffne sie zum Stoppen wieder mit SHIFT+REC und drücke REC.
REC außerhalb dieser Ansicht bleibt die normale Pattern-Aufnahme.

## Was in der Datei steht

Die Sampler schreiben Stereo-WAV mit 48 kHz und 16 Bit nach `Recordings/REC0001.WAV` auf der SD-Karte.
Weitere Namen steigen bis `REC9999.WAV`; vorhandene Dateien werden nicht überschrieben. Kurz vor 4 GiB beginnt
eine Folgedatei. Name und Dauer in der Anzeige gehören zur aktuellen Datei.

Aufgenommen wird der Mastermix nach MFX und Röhrenkurve, einschließlich AUDIO IN/THRU. Das Metronom bleibt hörbar,
steht aber nicht auf der Aufnahme. Der Signalweg ist im DSP-Simulator geprüft, noch nicht am Gerät abgenommen.

Während der Aufnahme sind SAMPLING, RESAMPLING und Apps mit eigener Audioerfassung wie Spettro gesperrt.
Gepufferte Plugin-Daten und Einstellungen warten bis zum Abschluss. Dateiaktionen wie Plugin-Import und -Export
zeigen währenddessen `recording`; ein wartendes Speichern zeigt `after recording`.

## Wenn etwas abbricht

| Anzeige | Bedeutung |
|---|---|
| Card full | Die Karte ist voll. Hat die Aufnahme bereits begonnen, bleibt ihr gültiger Anfang als WAV erhalten. |
| Card error | Ein Kartenzugriff ist fehlgeschlagen oder die Karte wurde entfernt. Der letzte gesicherte Zwischenstand bleibt erhalten. |
| Capture gap, Capture lost, Ring full | Die Erfassung konnte nicht lückenlos fortgesetzt werden. Die Aufnahme stoppt mit sichtbarem Zähler und einem benannten cue-Punkt am Ende des gültigen PCM-Anfangs. |
| No memory | Für den Aufnahmering war kein ausreichender Speicherblock frei; die Aufnahme hat nicht begonnen. |

Der Schreiber sichert regelmäßig einen gültigen Zwischenstand. Bei Stromausfall oder Kartenentnahme können noch
gepufferte Daten fehlen. Geprüft sind SD-Abbilder an den Grenzen der Dateiaufrufe, kein Stromausfall mitten in einem
physischen Sektorschreibvorgang. Ein Fehler wird nicht durch eingefügte Stille verdeckt.

## Was noch fehlt

Die endgültige Ringwahl wartet auf die Schreib- und Laufzeitmessungen am Gerät. Das aktuelle Emulatormodell überschreitet
bei einem vollen 64-KiB-Schreibblock die vorläufige Leserfrist; dieser Fall prüft den sichtbaren Abbruch, kein langes Set.
Die Kartenzugriffe von Sample Swap werden nach dessen Integration geprüft. Die optionale Plugin-API und der spätere
WAV-Player gehören nicht zu diesem Aufnahmestand.

Belege und offene Messwerte: [native Aufnahme](messungen/2026-11-17-native-aufnahme.md).
