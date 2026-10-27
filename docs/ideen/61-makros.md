# Idee 61: Makros für die Bedienung

Stand: Grundlagen im Emulator gemessen, Makrofunktion noch nicht gebaut. Zurück zu den [Ideen](../ideen.md).

Ein Makro nimmt Handgriffe an der Electribe auf und führt sie später wieder aus. Dazu gehören Tastenfolgen, Regler, Drehgeber, Pads, Touchpad, Part-Mutes, Part-Wechsel, Patternwechsel und die Bedienung des Sequencers. Es gilt für das ganze Gerät, nicht nur für einen Part.

Das wird ein natives Modul im BLECH-Firmware-Patch. Es läuft nicht als Plugin und braucht weder geladene Plugins noch deren eingeschaltete Laufzeit. Das vorhandene BLECH-Menü und die Eingabeverarbeitung werden gemeinsam genutzt.

## Bedienung

- **SHIFT + MFX HOLD** öffnet die Übersicht. Derselbe Einstieg liegt unter **Menü -> BLECH -> MAKROS**.
- **VALUE** wählt das Makro. **MENU**, die Enter-Taste, führt es einmal aus. Vor dem Start kehrt die normale Geräteansicht zurück.
- **NEU AUFNEHMEN**, mit MENU gewählt, macht die Aufnahme bereit. Erst die erste Bedienaktion startet sie. Diese Aktion gehört bereits zur Aufnahme und liegt bei Zeit null. Warten vor der ersten Aktion kostet keine Makrozeit.
- **STOP** hält den Sequencer wie gewohnt an und beendet während einer Makroaufnahme zusätzlich den Mitschnitt. Danach bekommt das Makro einen Namen und wird auf der SD-Karte gespeichert. STOP gehört nicht zum aufgezeichneten Ablauf. Während einer Makrowiedergabe ist STOP kein Makro-Abbruch.
- **EXIT** bricht die Wiedergabe ab. Ein in der Aufnahme enthaltenes EXIT bleibt dagegen eine normale Bedienaktion, etwa um ein Menü zu verlassen.

REC allein, TAP Motion und MFX HOLD ohne SHIFT behalten ihre Funktionen. Die Tasten der Makro-Steuerung und ihr Loslassen dürfen nicht versehentlich in der Aufnahme landen.

Ein vor der Bereitschaft bereits gehaltenes Pad oder eine gehaltene Taste wird nicht nachträglich als Druck aufgezeichnet. Deren bloßes Loslassen startet den Mitschnitt nicht. Bestehende musikalische Modi und gehaltene Zusatztasten gehören zum aktuellen Ausgangskontext; das Makro erfindet dafür keine Handgriffe.

## Änderungen bleiben

Der am Ende erreichte Zustand bleibt bestehen. Das gilt auch beim Abbruch für alles, was bis dahin ausgeführt wurde. Es wird kein Ausgangspattern geladen und kein vorheriger Klang wiederhergestellt.

Ein Beispiel für einen Übergang: eine aufgezeichnete Bearbeitung am Kick-/Bass-Klang ausführen, mit dem Touchpad Echo einstellen, den Crash-Sound auslösen oder einschalten und die Hi-Hats an der aufgenommenen Stelle wegnehmen. Das Echo, die Mutes und die übrigen Änderungen dürfen nach dem Makro nicht wieder zurückspringen. Welche Reglerbewegung den gewünschten Klang ergibt, entscheidet die Aufnahme, nicht das Makro.

Noch gehaltene Eingaben werden am Ende oder beim Abbruch sauber losgelassen. Das ist kein Zurücksetzen von Mutes, MFX HOLD, Klangparametern oder angeforderten Patternwechseln. Eine tatsächlich weiter gehaltene Taste oder ein Pad darf dabei nicht als losgelassen gelten.

## Wiedergabezeit und Startposition

Die Aufnahme behält die ursprüngliche Reihenfolge und musikalischen Zeitabstände. Für die Wiedergabe bekommt jedes Makro eine Einstellung:

| Einstellung | Ablauf |
|---|---|
| Original | Die aufgenommenen Abstände folgen dem aktuellen Tempo. Ein Übergang behält seine musikalische Dauer. |
| Fester Abstand | Zwischen den Bedien-Schritten liegt eine gewählte Zeit, zum Beispiel 40 ms. Die beim Aufnehmen benötigten Pausen entfallen. |
| Sofort | Keine künstlichen Pausen zwischen den Schritten. Die Firmware verarbeitet die Folge geordnet so schnell wie zuverlässig möglich. |

Im Modus Original dauern vier bei 120 BPM aufgenommene 4/4-Takte acht Sekunden, bei 150 BPM dauern dieselben vier Takte 6,4 Sekunden. Tempoänderungen während der Aufnahme oder Wiedergabe müssen in deren musikalischer Zeit berücksichtigt werden. Patternwechsel setzen diese Zeit nicht zurück. Ein fester Abstand in Millisekunden bleibt dagegen unabhängig vom BPM. Das Umschalten der Einstellung verändert die ursprüngliche Aufnahme nicht.

Der Startpunkt ist eine eigene Entscheidung: Für einen Übergang reicht es nicht, nur seine Abstände zu wiederholen, wenn er an einer anderen Taktposition beginnt. Die erste Bedienaktion bleibt Ereignis null; ihre Position im laufenden Takt muss zusätzlich erfasst werden. **Festgelegt:** MENU wartet für den musikalischen Start bis zum nächsten Erreichen der aufgenommenen Taktposition. Beginnt die erste Aktion auf Zählzeit 3, startet die Wiedergabe wieder auf Zählzeit 3; auch die Position zwischen den Zählzeiten gehört dazu. **Offen:** der genaue Bezug bei mehrtaktigen Patterns sowie das Verhalten bei stehendem Sequencer oder fehlender externer Clock. Die bisherige Festlegung auf einen unmittelbaren Start ist für diesen Anwendungsfall ersetzt.

**Offen und vor der Umsetzung zu prüfen:** Was als Bedien-Schritt zählt. Tastendruck, Loslassen, gehaltene Zusatztasten und zusammengehörige Touchpad-Bewegungen dürfen durch verkürzte Pausen nicht versehentlich eine andere Aktion auslösen. Ebenso muss ein benötigter Menüwechsel verarbeitet sein, bevor der folgende Schritt ankommt. Sofort verspricht keine gleichzeitige Ausführung und keine bestimmte Laufzeit. Bewusst aufgezeichnete Haltegesten brauchen eine ausdrücklich festgelegte Behandlung.

## Ausgangszustand

Drei Rastungen am Sample-Rad bleiben drei Rastungen vom jeweils aktuellen Wert aus. Ein aufgezeichneter Mute-Tastendruck schaltet den aktuellen Zustand um. Unterschiedliche Ausgangszustände dürfen deshalb unterschiedliche Ergebnisse liefern. Das Makro stellt keinen versteckten Ausgangszustand her. Normale Regler liefern ihre erfassten absoluten Werte; relative Drehgeber bleiben relativ.

## Warum ein eigener Mitschnitt

Korgs Event Recorder ist für das Aufnehmen und Abspielen einer Performance gedacht. Für Bedienmakros muss geprüft sein, ob jede benötigte Handbewegung erhalten bleibt und ob der aktuelle Zustand des Geräts bestehen bleibt. Der vorhandene Player darf nicht als Ersatz verwendet werden, wenn er dafür zunächst ein gespeichertes Pattern lädt oder am Ende den vorherigen Zustand wiederherstellt.

Die Plugin-Ereignisse werden teilweise nur alle 40 ms aus dem Gerätezustand abgeleitet. Sie sind deshalb keine vollständige Aufnahmespur für Tastenfolgen und schnelle Bewegungen. Grundlage ist der normale Eingangsweg des Bedienfelds, siehe [Panel-Bedienung](../messungen/2026-10-08-panel-bedienung.md) und [Zeitverhalten](../hintergrund/sequencer-timing.md).

## Noch zu messen oder festzulegen

- **Gemessen im Emulator:** ein begrenzter Weckweg von der PeriodicTask zur CsTask funktioniert auf allen drei Builds. Normale Bedienfunktionen bleiben in ihren vorgesehenen Tasks. [Aufbau und Grenzen](../messungen/2026-10-25-makro-grundlagen.md).
- **Gemessen im Emulator:** ein fester Kandidat für Code, 512 Ereignisse und Zustand überschneidet keine aktuelle Patch-Belegung. Die native Einbindung muss diesen Bereich noch deklarieren. Die rund 47 MiB aus der [RAM-Messung](../messungen/2026-10-22-ram-frei.md) werden nicht benutzt.
- **Gemessen im Emulator:** die wirksame Taktgeber-Periode folgt auch externer MIDI-Clock und ist bei gestopptem Sequencer verfügbar. Die bisherigen BPM-Felder allein reichen dafür nicht. **Offen:** Ausfallerkennung und vollständige tempoabhängige Wiedergabe.
- **Festgelegt für den ersten Ausbau:** 512 Ereignisse. Daraus folgt keine feste Dauer in Sekunden. Volle Puffer müssen die Aufnahme sichtbar beenden, nicht einzelne Aktionen verlieren.
- **Offen:** welche nichtmusikalischen Datei- und Systemaktionen ausdrücklich ausgeschlossen werden. Ein- und Ausschalten, Update und Kartenformatierung gehören nicht automatisch zum vereinbarten musikalischen Umfang.

Am echten Gerät ist von den Makros noch nichts geprüft.
