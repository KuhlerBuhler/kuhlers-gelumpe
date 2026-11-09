# Sample-Swap: direkte PCM-Schreibpfade

Stand: 05.11.2026. Ergänzung zum [physischen Sample-Schutz](2026-11-05-sample-schutz.md).
Untersuchung der eigenen roten Originale mit Firmware 2.02. Keine
Gerätemessung, kein Audio und kein DMA-Nachweis.

## Hergeleitet: nativer Blockschreiber

`0xC0014284` erhält ein DSP-Byteziel in `r0`, eine ARM-Quelle in `r1`
und eine Halbwortanzahl in `r2`. Die Anzahl wird bei `0xC001429C`
auf 16 Bit gekürzt. Der Ressourcenerwerb steht bei `0xC00142D4`,
der Schreibaufruf bei `0xC00142F0`, die Freigabe bei `0xC00142F8`.
Die erste native Fortsetzung nach dem Erwerb ist `0xC00142D8`.

Der nachgelagerte Treiber `0xC0014C34` schreibt bei null bis 15
Halbwörtern nichts. Ab 16 Halbwörtern führt er Transfers mit 16 Halbwörtern aus.
Bei einer Restmenge schreibt er zuerst 16 Wörter am Anfang, rückt um die
Restmenge vor und überträgt dann die volle verbleibende Gruppenzahl.
So überlappen etwa bei 17 Wörtern zwei Gruppen um 15 Wörter; die gesamte
Zielspanne umfasst trotzdem genau 34 Byte. Eine pauschale Aufrundung auf
volle 32-Byte-Gruppen beschreibt diese direkte API nicht richtig.
Die genannten Wrapper und dieser Treiber sind in beiden roten Originalen
bytegleich. Die separate Emulatorgegenprobe unten verwendet 32 Halbwörter.

Der Sample-Schreiber `0xC004EF28` erhält ARM-Quelle, DSP-Byteziel und
Halbwortanzahl. Bei höchstens 15 Halbwörtern liest er zuerst 16 Halbwörter,
ersetzt den angeforderten Anfang und schreibt den ganzen 32-Byte-Block.
Die Schutzgrenze muss daher den tatsächlich geschriebenen Block verwenden.
Die Parser-Aufrufer des Sample-Schreibers liegen bei `0xC003631C`
und `0xC00363E0`.

Die Aufrufer bei `0xC003DDE0` und `0xC00762E8` beschreiben interne Bereiche
bei `0xFF900018` beziehungsweise `0xFF900A38`, außerhalb der Nutzerbank.
Der Aufruf bei `0xC004FA74` gehört zur L/R-Zusammenführung in `0xC004F490`.
Die drei gefundenen Aufrufer dieser Zusammenführung stehen nach dem
Werksbanklader `0xC004D860`: Start, Werksrücksetzung und Rückfall nach
fehlgeschlagenem Gesamtladen. Der normale erfolgreiche WAV-Import nimmt
diesen Weg nicht.

Das ist keine allgemeine Ausnahme für physische Nutzerzeilen. Die
Schleifengrenze stammt aus dem MSVS-Kopf, wird nur gegen 999 geprüft
und ist nicht durch die unterschiedlichen Konstanten 421 beziehungsweise
274 begrenzt. Diese Konstanten gehören zu anderen Teilen der Funktion.
Eine rein nach Funktionsnamen gewählte Ausnahme wäre unbelegt.

## Gemessen im Emulator: gleiche Tabellen, andere PCM

Die Gegenprobe benutzt erzeugte Samples und eine daraus gebaute Karte.
Nach dem Start entfernt sie ihre modellierten Part-Bindungen und ruft den
echten Blockschreiber für 64 Byte eines bereits geladenen Nutzer-Samples
auf. Die Quelle enthält eine berechnete Bytefolge.

Die Gegenprobe reproduziert auf Stock und Hacktribe denselben Fehler.
Der bisherige Schutz erkennt diese Änderung nicht: Die emulierten DSP-Daten
ändern sich, Metadaten, PLAYBACK und Namenszeile bleiben bytegleich.
Die physische Änderungsmarke bleibt null, die Signatur gilt weiter als
sauber und `can_evict` erlaubt die Freigabe. Die Bibliothek auf der
emulierten Karte bleibt unverändert. Dieser Befund ist eine Schutzlücke,
kein erfolgreicher Swap-Test.

Die dauerhafte Gegenprobe steht in
`tools/emu/sample_protection_cases.py`, Funktion `pcm_write_cases`:

```sh
tools/emu/.venv/bin/python tools/emu/sample_protection_cases.py --patched OWN_PATCHED.VSB --pcm-write
```

Sie prüft die gewünschte Schutzwirkung und endet beim derzeitigen Fehler
mit Status 1. Sie ist bewusst eine separate Forschungsprobe; der normale
Falllauf darf nicht als Nachweis ihrer bestandenen Abnahme gelesen werden.
Das DSP-Peripheriemodell zeichnet die übertragenen Wörter auf. Es beweist
weder Klang noch reale Stimmenlebensdauer.

## Gemessen im Emulator: tatsächliche Zielspanne

Eine zweite Probe zählt die Host-Port-Datenwörter während des echten
Blockschreibers und hält die tatsächlich beschriebenen DSP-Adressen fest.
Die Quelle und das geladene Sample sind erzeugt. Stock und Hacktribe
liefern für alle acht Aufrufe dieselben Werte:

| Übergebene Halbwortanzahl | Wirksame Anzahl | Übertragene Halbwörter | Verschiedene Ziel-Halbwörter | Zielspanne |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 Byte |
| 1 | 1 | 0 | 0 | 0 Byte |
| 15 | 15 | 0 | 0 | 0 Byte |
| 16 | 16 | 16 | 16 | 32 Byte |
| 17 | 17 | 32 | 17 | 34 Byte |
| 31 | 31 | 32 | 31 | 62 Byte |
| 32 | 32 | 32 | 32 | 64 Byte |
| `0x10010` | 16 | 16 | 16 | 32 Byte |

Die erfassten Adressmengen stimmen jeweils exakt mit der hergeleiteten
Zielspanne überein; die Probe meldet keine Firmware-Assertion. Das sind
Funktionsaufrufe mit Peripheriemodell, keine Messungen eines kompletten
Normalize- oder Truncate-Menüablaufs und keine Gerätedurchsatzmessung.

## Hergeleitet: Anforderungen an den Anschluss

Ein Marker nur am Funktionseinstieg genügt nicht. Der native
Ressourcenerwerb kann warten; danach muss der Schutz die dann gültigen
physischen Belegungen und den tatsächlich geschriebenen Bereich verwenden.
Ein eigener Swap-Auftrag kann denselben Bereich bereits reserviert haben,
ohne seine Metadaten veröffentlicht zu haben. Auch dieser Auftrag muss
vor weiterem Schreiben beziehungsweise Veröffentlichen ungültig werden.

Der eigene begrenzte Transport erwirbt die Ressource ohne blockierendes
Warten. Zwischen der Prüfung im Chunk-Aufrufer und dem Erwerb fehlt ihm
aber eine erneute Bindung an die Auftragsgeneration. Der Anschluss muss
deshalb auch nach seinem Erwerb prüfen, ob der Auftrag noch gilt, und
veraltete Aufträge ohne Erfolgsmeldung beenden.

Der native Startparser schreibt über denselben Blockpfad. Eine pauschale
Erhöhung des Änderungszählers je PCM-Block würde seinen bereits geprüften
Ladestempel entwerten. Eine Ausnahme muss dem tatsächlichen Parseraufruf
und seinem eigenen Zielbereich gehören. Ein globales `INSTEP` oder ein
globales Startkennzeichen belegt diese Zugehörigkeit nicht.

## Hergeleitet: Task-Zugehörigkeit des Aufrufs

`0xC06A2894` ist die IRQ-Eintrittstiefe. Null identifiziert keine bestimmte
Task und beweist auch keinen Kontext außerhalb einer Task.
Die Kernelroutine `0xC0001480` schreibt bei Erfolg die Tasknummer in das
Wort, auf das `r0` zeigt.
Sie liest den aktuellen Kontrollblock über `0xC06A289C` und berechnet
`((Kontrollblock - 0xC06A24E4) >> 5) + 1`. Die
[zehn Kontrollblöcke](2026-10-08-systemspeicher-offline.md) sind jeweils
32 Byte groß. Die Routine verlangt Tiefe null und erlaubte IRQs.

Der Ressourcenerwerb `0xC0000D80` verlangt ebenfalls Tiefe null und erlaubte
IRQs, zusätzlich einen gestarteten Kernel. Ist der Ressourcen-Zähler null,
reiht `0xC0001D14` den aktuellen Kontrollblock als Wartenden ein; danach
ruft der Erwerb den Scheduler `0xC0001760` und liest später den Rückgabewert
vom eigenen Stack. Die geprüften Kernelspans sind in beiden roten Originalen
bytegleich. Das belegt den blockierenden Codepfad, noch keine Wartezeit am Gerät.

Ein nativer Schreibauftrag braucht daher eine Kennung in seinem eigenen
Aufrufrahmen, die nach dem Erwerb noch zu Task und Bibliothek passt.
Der bestehende Job-/Cache-Zähler allein ist keine Bibliothekskennung:
Auch Cache-Abbruch und Pufferübergabe verändern ihn. Wie die native
Fehlerweitergabe eine abgelehnte Fortsetzung bis zum Parser meldet, ist
vor dem Anschluss zu prüfen; ein still übersprungener Void-Aufruf genügt nicht.

## Gemessen im Emulator: eine fremde Task und INSTEP

Ein weiterer nativer Aufruf des Blockschreibers mit Länge null verfolgt
Task, FP, SP, IRQ-Tiefe und Ressourcenbesitz vor und nach dem Erwerb.
Auf beiden roten Builds läuft der Aufruf aus dem Bildschirm-Tick in Task 4.
Der SP liegt in deren Stack, die IRQ-Tiefe ist null, der FP bleibt nach
seinem Aufbau bis zum Rücksprung gleich. Die Ressource wechselt korrekt
von frei zu belegt und danach zu frei; keine Firmware-Assertion.

Für den zweiten Aufruf setzt allein die Testprobe `INSTEP` am Einstieg auf
eins und setzt es am Rücksprung zurück. Es läuft weiterhin dieselbe Task 4,
jetzt legt der bestehende Wartepfad aber einen begrenzten nativen Kontext
auf ihrem Stack an. Mit `INSTEP` null geschieht das nicht. Ein echter
paralleler Swap-Auftrag wurde dabei nicht gestartet. Die Probe bestätigt
somit die Abhängigkeit vom globalen Kennzeichen, keinen tatsächlich
aufgetretenen Timeout einer fremden Task. Die Task-Zugehörigkeit lässt
sich durch dieses Kennzeichen allein nicht absichern.

## Hergeleitet: Bearbeitung und Aufnahme

Der untersuchte Time-Slice-Weg beginnt bei `0xC00395E4` und ruft
`0xC0050208`. Er liest PCM über den Blockleser und arbeitet mit
Deskriptoren. Die Anwendung bei `0xC004FE08` verwendet die bereits
markierte Deskriptor-Rücknahme `0xC004EFF4`. In diesem untersuchten Weg
wurde kein Aufruf des Blockschreibers gefunden. Das ist kein Nachweis
sämtlicher DSP-internen Bearbeitungen. Eigene Menüeinträge namens
Normalize und Truncate wurden in der geprüften Sample-Bearbeitung nicht
gefunden; daraus folgt keine Aussage über alle internen Befehle.

Sampling wird als Fenster 42 über `0xC0083DB0` geöffnet. Bildschirm 41
hat einen anderen Objekttyp. Der Sampler-Manager aus `0xC0035AD8` hält
bei `+0x704` Mono/Stereo und bei `+0x708` Audio In/Resampling.
Die nativen UI-Handler `0xC006B3FC` und `0xC006B440` ändern diese Werte.
`0xC0082F1C(Transport, request_play)` startet die Aufnahme. Sein zweiter
Parameter wählt nicht die Quelle: Bei Resampling und einem Wert ungleich
null startet er zusätzlich PLAY.

STOP bei `0xC0082D40` liest den DSP-Endzeiger über `0xC004E23C` und
veröffentlicht über `0xC004F128`. Dabei wird kein Blockschreiber aufgerufen.
Der Aufnahmebefehl geht schon beim Start über `0xC0013D98` an den DSP.
Dessen tatsächliche Schreibspanne und Ausklanggrenze bleiben ohne echtes
Gerät offen. STOP kann das Sampling-Fenster ersetzen; ein vorheriger
Objektzeiger darf danach nicht weiterverwendet werden.

Die neu ergänzte [Fehlerprüfung](2026-11-05-sample-pcm-fehler.md) behandelt
Rückgaben und Abbrüche, noch keinen vollständigen PCM-Bereichsschutz.

## Offen

- Anschluss des Blockpfads mit Bereichsschutz, Auftragsgeneration und
  aufrufeigener Ausnahme für eine bestätigte Startladung.
- Gegenproben mit einem beim Ressourcenerwerb verdrängten Auftrag,
  Teilblöcken, Aliassen und einem fremden Schreiber während einer Startladung.
- Vollständige Bearbeitungsgrenzen, Time-Slice-Rücknahme und DSP-interne Schreibwege.
- Aufnahme und Resampling: Der Abschluss `0xC004F128` veröffentlicht Tabellen
  ohne den Blockschreiber. Sein `r0` ist ein physischer Index. Frühere
  DSP-Schreibzugriffe während der Aufnahme sind damit noch nicht zugeordnet.
- Echte RAM- und DMA-Nutzung aller Modi vor einer Geräteinstallation.

Bis diese Punkte belegt und die erforderlichen Gegenproben bestanden sind,
bleibt die vollständige Mutationsabdeckung offen.
