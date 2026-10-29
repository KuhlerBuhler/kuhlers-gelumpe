# Sample-Swap: Stimmen, Part-Auswahl und Moduswechsel

Stand: 28.10.2026. Fortsetzung der
[Slot-Speicherung](2026-10-27-sample-store.md).
Beleg: `measure:2026-10-28/sample-swap-stimmen`.

Die Emulatorversuche laufen mit eigenen roten Firmwaredateien und erzeugten
Samples. Klang, DMA und der tatsächliche Abschluss einer DSP-Stimme werden
dabei nicht nachgebildet. Die passive Geräteprüfung ist unten getrennt
beschrieben.

## Gemessen im Emulator: alte Stimmen behalten ihre Belegung

Zwei erzeugte Slots 500 und 600 zeigen zunächst über die Importnummer 550
auf dieselbe PCM. Zwei native Stimmen werden gestartet. Danach bekommt
Slot 600 vollständig übertragene eigene PCM in einer vorher unbenutzten
Zeile. Erst anschließend werden seine CPU-Tabellen umgebunden. Dieser
Grundversuch benutzt Mono mit 16 Bit.

| Prüfung | Ergebnis |
|---|---|
| Alte Stimmen nach der Umbindung | behalten Importnummer 550 |
| Neue Stimme für Slot 600 | benutzt die neue Importnummer 651 |
| PCM des alten Alias 500 | unverändert |
| Vorher unbenutzter logischer Slot 601 | bleibt ungeladen |
| Tauschkandidat bei weiter belegten alten Stimmen | keiner |
| Tauschkandidat nach nativer CPU-Stimmenfreigabe | Slot 500 |
| Part-Zeiger der freigegebenen Stimmen | bleiben ungleich null |

Die Stimmenfreigabe wird ausdrücklich durch Aufruf der nativen CPU-Routine
simuliert. Der Versuch beweist nicht, wann eine reale DSP-Stimme fertig ist.
Die getrennte Veröffentlichung der neuen Belegung geschieht bei angehaltener
Emulation. Sie ist ein Forschungsaufbau, kein fertiger neuer Slot-Verwalter.

Wiederholbar mit `tools/emu/sample_residency_probe.py --patched DATEI
--check-eviction` sowie dem Stimmenfall in `tools/emu/swap_cases.py`.
Die beiden erzeugten Ersatzzeilen sind gültige Tabellenzeilen. Index 999
wird nicht als Ersatzplatz verwendet.

## Gemessen im Emulator: freie Schlüssel und native Veröffentlichung

Ein weiterer Start mit den drei erzeugten Slots 500, 600 und 998 zeigt in
beiden roten Builds 499 unabhängige Nutzerketten. Bei allen stimmen der
Schlüssel sowie die Indizes in den drei Tabellen überein. 496 dieser
Ketten sind in diesem Aufbau inaktiv. Das beschreibt den getesteten
Startzustand; eine spätere Änderung muss die Voraussetzungen erneut prüfen.

Mit `--native-publication` benutzt derselbe Stimmenversuch für die
Veröffentlichung die native CPU-Registrierung `0xC004EDF0`. Nach dem
vollständigen PCM-Transfer wird bei maskierten IRQs der Importverweis des
Zielnamens auf den vorher unbenutzten Schlüssel gestellt und die native
Registrierung aufgerufen. Sie schreibt dadurch den neuen physischen Platz
und den Zielnamen. Bei Verweigerung wird der alte Importverweis wieder
hergestellt. Der alte Frei-Zeiger wird durch einen kleineren neuen Wert
nicht zurückgesetzt.

In beiden roten Builds liefert die Registrierung Erfolg: neue Stimme auf
Importnummer 651, alte Stimmen weiter auf 550, alte Alias-PCM unverändert,
der unbenutzte logische Slot 601 weiterhin ungeladen. Nach simulierter
nativer Freigabe ist der alte Platz wieder ein Kandidat. Mono mit 16 Bit
und Mono mit 24 Bit liefern jeweils 800 Byte geprüfte DSP-PCM nach der
Normalisierung. Der Stereo-Versuch mit 16 Bit liefert 1600 Byte.

Beim Übergang von Mono zu Stereo kann die native Part-Aktualisierung
Stimmen des betroffenen Part-Paars freigeben. Der Stereo-Versuch legt die
weiter zu schützende Alias-Stimme deshalb auf Part 3, außerhalb des
geänderten Paars. Diese Stimme behält Importnummer 550, während eine neue
Stimme auf dem Stereo-Part 651 bekommt. Eine freigegebene Stimmenadresse
wird dabei wiederverwendet. Derselbe Zeiger bedeutet folglich nicht
dieselbe fortbestehende Stimme. Der Nachweis betrifft CPU-Bindungen und
PCM-Inhalt; tatsächlicher Ausklang und DSP-Freigabe bleiben Gerätetests.

```sh
python3 tools/emu/sample_residency_probe.py --patched ../eigene/NEU.VSB \
  --check-eviction --native-publication
```

Für die beiden weiteren Formate kommt `--kind pcm24` beziehungsweise
`--kind stereo16` dazu. `protected_voices_before` nennt die Stimmen, die
der jeweilige Versuch über die Veröffentlichung hinaus erhält.

Die native Routine ermittelt ihren Zielplatz aus dem bisherigen
Namensverweis, nicht allein aus dem neuen Deskriptor. Das erklärt den
früheren Alias-Fehler und die nötige gemeinsame Veröffentlichung. Der
Aufbau arbeitet weiterhin mit vorher gewählten freien Schlüsseln und
angehaltener Emulation. Ein laufender Verwalter braucht zusätzlich
Dateibesitz, Versionsprüfung, eine atomare Schlüsselreservierung und
Abbruchbehandlung; dieser Versuch installiert ihn nicht.

## Hergeleitet: welche Belegung geschützt werden muss

Die native Stimmenliste beginnt bei `0xC06916A0`, enthält 24 Einträge mit
Abstand `0x48`. Der Part-Zeiger bei `+4` allein ist kein Belegt-Merkmal:
Die native Freigabe `0xC0091AD0` lässt ihn stehen. Die Abfrage
`0xC009115C` liefert den nativen Belegtzustand. Eine belegte Stimme hält
ihre Importnummer bei `+0x40`; ihre logische Slotnummer bei `+0x3A` kann
nach einer Namensumbindung bereits auf andere PCM zeigen.

Der Part-Zugriff `0xC009AF20` liefert die 16 tatsächlichen Parts. Deren
Sample bei `+0x34` ist zusätzlich zu den gewünschten Samples des aktuellen
Patterns und des Wechselziels zu schützen. Nicht auflösbare belegte Stimmen
verhindern eine Verdrängung. Ein Nutzeralias macht eine Factory-Zeile nicht
zu einem freigebbaren Nutzerplatz.

Die Suche nach einem Kandidaten läuft mit unverändertem Interruptzustand.
Unmittelbar vor dem nativen CPU-Löschen `0xC004E558` werden Modus, Parts,
Aliase und Stimmen nochmals geprüft. Nur diese letzte Prüfung und das
Löschen maskieren IRQs. Die ARM-Prüfung setzt einen Kandidaten ganz ans
Tabellenende und verlangt weniger als 5000 emulierte Befehle mit neu
maskierten IRQs. Das ist keine gemessene Zeitgrenze am Gerät und kein
Nachweis über FIQ-Zugriffe.

## Gemessen im Emulator: Part-Auswahl wartet auf PCM

Ein Part spielt Slot 500 und verlangt den noch ungeladenen Slot 505.
Vor der Korrektur übernimmt der native Aktualisierer die neue Slotnummer
vorzeitig; nach dem Nachladen bleibt seine Spielart ungültig. Der neue
Fall prüft den vollständigen Übergang:

1. Gewünschte Auswahl 505 setzen und nativen Aktualisierer aufrufen.
2. Tatsächliche Auswahl 500 während des Ladens erhalten.
3. PCM vollständig übertragen und Tabellen eintragen.
4. Genau die wartenden Parts über den nativen Aktualisierer nachziehen.
5. Tatsächliche Auswahl 505 mit gültiger Spielart prüfen.

Die Haken bei `0xC0099FFC` und `0xC0099D88` sichern sowohl den äußeren
Aktualisierer als auch direkte Aufrufe der Bindung. Leere, nicht indizierte
Auswahlen und Factory-Auswahlen behalten ihr natives Verhalten. Ein
gesperrter DSP-Transport veröffentlicht keine neue Part-Bindung.

## Gemessen mit erzeugten ARM-Tabellen: Moduswechsel pausieren

Nur die unverdeckte Hauptseite in einem der sechs Sequencer-Zustände 0 bis
5 erlaubt Ladeabschnitte. Fenster, andere Seiten, Aufnahmezustand 11 und
das gesetzte Transportmerkmal bei `+0x312` pausieren Aufträge. Die Prüfung
läuft vor jedem Abschnitt sowie nach Kartenlesen, DSP-Transfer und
Deskriptorkopie. Ein verworfener Auftrag erhält keine fertige Cache- oder
DSP-Belegung. Seine Generation wird beim Pausieren einmal geändert.

Das Pausieren erhält den zuletzt beobachteten PLAY-Zustand. Sonst würde
allein die Rückkehr aus einem Menü einen neuen Füllstart auslösen. Der
native Fall prüft: Cache beim Menüwechsel verworfen, nach der Rückkehr
weiter leer, nach STOP und PLAY wieder gefüllt.

Ein vorübergehend voller DSP markiert den Zielslot nicht dauerhaft als
fehlerhaft. Das aktuelle Pattern bleibt aktiv, der Auftrag kann später
erneut versucht werden. Ein Protokollfehler bleibt dagegen gesperrt.

`tools/patch/test_sample_swap.py` enthält 51 ARM-Fälle, einschließlich
eines nachträglich benutzten Tauschkandidaten, der letzten Stimme,
Register- und Stack-Rückgabe sowie der Moduswechsel während eines Auftrags.
Der zuvor vollständig geprüfte Laufzeitstand besteht mit 604 Prüfungen für
Stock und 579 für Hacktribe. Die geprüften Firmwaredateien und die Quellen
des eingebauten Laufzeitcodes stimmen zwischen beiden Rechnern überein.
Die 39 Swap-Prüfungen bestehen außerdem getrennt mit beiden Builds.

Die spätere [Leserbereinigung](2026-10-29-sample-dateibesitz.md) ändert den
gebauten Laufzeitcode erneut. Die obigen vollständigen Prüfungen gelten
für den davor geprüften Stand.

`npm test` besteht nach den Stereo-, Aufnahme- und Export-Fehlerprüfungen
mit 1157 bestandenen und 153 übersprungenen Tests. Die vollständige
Browserprüfung besteht auf Linux mit 220 bestandenen und einem
übersprungenen Test. Sie verwendet den vorhandenen Chromium und denselben
unveränderten Zeitrahmen. Ein früherer Lauf auf dem schlafenden Rechner
brach mit Netzwerk- und Zeitfehlern ab; beim ersten Linux-Lauf fehlte der
angeforderte Chrome. Diese abgebrochenen Läufe gelten nicht als bestanden.

Ein fehlgeschlagener Browserstart ließ außerdem den HTTP-Testserver
offen. Der Prüfaufbau schließt ihn jetzt auch bei diesem Fehler. Ein
eigener Test erzwingt einen unbekannten Browserkanal und verlangt, dass
der Kindprozess ohne Abbruch von außen endet. Zuvor lief er in sein
Zeitlimit, jetzt gibt er den Startfehler weiter und endet selbst.

Frühere sporadische Timeouts vor der Sample-Liste gelten damit weiterhin
als offen. Ein später bestandener Gesamtlauf allein wäre kein Nachweis
für ihre Behebung.

## Gemessen im Emulator: vollständige Stereo-Datensätze

Bei einer WAV ohne Sample-Datensatz erzeugt der native Parser für 100
Stereo-Frames mit 16 Bit eine PCM-Länge von 400 Byte, Stereo-Flag 1 und
Loop-Ende sowie Sample-Ende bei Byte 396. Der fertige native Import belegt
400 Byte im DSP. Beide roten Builds liefern diese Werte ohne Assertion.

Der Erzeuger `tools/emu/sampleset.py` setzte zuvor weder das Stereo-Flag
noch die vollständige PCM-Länge. Die Prüfung verglich damit zwei gleich
falsche Ladevorgänge. Sie prüft jetzt zusätzlich die vollständige erzeugte
PCM und das Stereo-Flag. Bei 5000 Stereo-Frames waren zuvor nur 10000 Byte
registriert; mit dem korrigierten Datensatz laden beide Lader 20000 Byte.

Auch die App erzeugte bei einer WAV ohne vorhandenen Sample-Datensatz
nur die Länge eines Kanals. `entryFromWav` berücksichtigt jetzt beide
Kanäle und setzt Loop und Ende auf den letzten vollständigen 16-Bit-Frame.
Die Korrektur gilt für neu erzeugte Datensätze. Die Prüfung umfasst
Stereo-WAVs mit 16 und 24 Bit; deren DSP-Länge ist nach Normalisierung
dieselbe. Ein Klangvergleich am Gerät ist damit nicht ersetzt.

## Gemessen im Emulator: native DSP-Aufträge begrenzt abbrechen

Die native Part-Aktualisierung schreibt selbst an den DSP-Port. Ein
Mono-Aufruf erzeugt im untersuchten Fall 48 Datenwörter und sieben
Steuerwörter, eine Stereo-Aktualisierung 240 Datenwörter und 77
Steuerwörter. Die Aktualisierung ist deshalb kein reiner CPU-Tabellenzugriff.
Sie lässt sich nicht ungeprüft in den IRQ-geschützten Abschnitt der
Namensregistrierung verschieben.

Der Steuernachrichtensender nimmt die gemeinsame DSP-Sperre mit Index 1
bei `0xC00137FC` und gibt sie bei `0xC0013948` frei. Er umgeht diese
Sperre also nicht. Die Statusroutine `0xC001462C` wartet unbegrenzt auf
Bit `0x80` und liefert anschließend die Bits `0x50`. Ihr Aufrufer bei
`0xC00138F0` wiederholt, solange diese Bits gesetzt sind. `0x50` als
Fehlerrückgabe würde dort erneut hängen; null würde Bereitschaft vortäuschen.

Der getrennte Baustein
[`native_dsp_scope.py`](../../tools/patch/native_dsp_scope.py) verlässt
stattdessen bei Zeitüberschreitung den gesamten betroffenen nativen
Auftrag. Er setzt einen bleibenden DSP-Fehler, sperrt den Swap und
entwertet die Generation einmalig. Der Stack, die erhaltenen Register
und die Interruptsteuerung des Aufrufers werden wiederhergestellt.
Eine selbst erworbene Sperre wird genau einmal freigegeben. Eine nur
geliehene Sperre bleibt beim äußeren Besitzer. Eine verweigerte
Sperranforderung darf weder am Port schreiben noch eine Sperre freigeben.

Ein erster Abbruch mit maskierten IRQs kehrte zwar zurück, ließ im echten
Kernelcode jedoch die Sperre belegt. Die Freigabe funktioniert in diesem
Versuch nur mit eingeschalteten IRQs. Der Baustein schaltet sie dafür ein
und stellt vor der Rückkehr den gespeicherten Zustand wieder her. Ein
eigener ARM-Test verweigert die Freigabe ausdrücklich bei maskierten IRQs,
damit dieser Fehler nicht durch die Ersatzfunktion verdeckt wird.

Ein weiterer erzeugter Unterbrechungsaufruf trifft einen bereits laufenden
Auftrag. Seine Sperranforderung wird verweigert. Anfangs löschte dieser
Abbruch auch den gesicherten Rückkehrpunkt des Besitzers. Der korrigierte
Weg veröffentlicht bei verweigerter Sperre keinen eigenen Rückkehrpunkt
und löscht nur den eigenen. Der äußere Auftrag erkennt anschließend
denselben Fehler, kehrt sauber zurück und gibt genau eine Sperre frei.
Die Generation wird bei beiden Abbrüchen zusammen nur einmal erhöht.
Das prüft diesen kontrollierten Wiedereintritt; eine allgemeine
Absicherung aller Unterbrechungswege ist damit nicht nachgewiesen.

Die Begrenzung hat standardmäßig 100 Millisekunden bei gültiger
Timerkonfiguration sowie eine davon unabhängige Grenze von einer Million
Warteprüfungen. Die kleinen Emulatorversuche verwenden 128 Prüfungen.
Das ist keine gemessene maximale Abbruchzeit auf dem Gerät.

[`native_dsp_scope_cases.py`](../../tools/emu/native_dsp_scope_cases.py)
setzt die Haken ausschließlich im Emulator-RAM. Es untersucht diese
Aufträge in beiden roten Builds:

| Auftrag | Native Funktion | Nach Sperranforderung | Vor Freigabe |
|---|---|---|---|
| Steuernachricht der Part-Aktualisierung | `0xC00137A8` | `0xC0013800` | `0xC0013948` |
| DSP-Speicher lesen | `0xC00141F8` | `0xC001424C` | `0xC0014274` |
| DSP-Speicher schreiben | `0xC0014284` | `0xC00142D8` | `0xC00142F8` |

Im Bereich `0xC0011000` bis `0xC001462C` liegen 35 Paare aus Anforderung
und Freigabe der DSP-Sperre 1. Alle haben denselben FP-basierten
Registerprolog; vor der Sperranforderung verändert keiner `r4` bis `r10`.
Die geprüften Stack-Schreibzugriffe nach der Anforderung benötigen nur
das erste ausgehende Argumentwort. Drei Funktionen geben ihren Frame
ohne vorheriges Zurücksetzen von SP frei. Der Abschluss stellt deshalb
den ursprünglichen SP vor der nativen Freigabe wieder her.

Der Versuch umschließt beide Sperraufrufe gemeinsam. Die ursprüngliche
erste Anweisung nach der Anforderung bleibt an ihrer Adresse; sie wird
nicht in den zusätzlichen Code verschoben. Ein Code-Fingerabdruck und
die Prüfung aller 70 Aufrufziele sichern die bekannten Stellen ab.

Ein tatsächlicher Wechsel von Mono auf Stereo mit zwei zuvor gestarteten
Stimmen führt elf DSP-Aufträge aus. Der erste, auf drei Sender begrenzte
Versuch erfasste davon nur drei. Der erweiterte Versuch erfasst im ersten
Stock-Lauf alle elf: elf erfolgreiche Anforderungen, elf Freigaben,
317 Port-Schreibzugriffe, keine Assertion, korrekter Rückkehr-Stack und
Stereo-Spielart des Ziel-Parts. Die weitere Matrix umfasst zusätzlich
die drei Funktionen `0xC0012758`, `0xC001430C` und `0xC00143E4`, deren
normaler Abschluss SP nicht selbst zurücksetzt.

Der Leser bekommt DSP-Adresse, ARM-Ziel, Anzahl der 16-Bit-Wörter und
Speicherbereich in `r0` bis `r3`. Der Schreiber bekommt DSP-Adresse,
ARM-Quelle und Anzahl in `r0` bis `r2`; sein Bereich ist 2. Der Test
benutzt jeweils 32 selbst erzeugte Wörter. Die Status- und GPIO-Schleifen
werden vor dem Protokollkopf und vor den Nutzdaten angehalten.
Bei maskierten IRQs liefert die Sperranforderung in diesen Aufrufen
`0xFFFFFFE7`. Der neue Abbruchweg lässt dann den unverändert freien
Sperrzähler auf eins und schreibt kein Portwort.

Die erweiterte Matrix besteht mit 72 Fällen in beiden roten Builds.
Die vollständige Stock-Ablauffolge nach dem Booten erfasst nach der
Korrektur der Stack-Freigabe 29629 native
DSP-Aufträge ohne abgelehnte Sperre oder Abbruch. Der Testcode bleibt
dabei unverändert. Er liegt für diese längere Prüfung im unbenutzten
Ende des bereits reservierten Patch-Codebereichs, außerhalb des
Arbeitspuffers. Der gesicherte Kontext endet auf null, die DSP-Sperre
ist am Ende frei. Dies prüft keinen Bootvorgang mit den neuen Haken
und weiterhin kein DMA.

Bei Hacktribe besteht der einzeln geprüfte Gesamtexport mit 7330
DSP-Aufträgen. Die längere Folge scheiterte zunächst später an einer
leeren Exportdatei, ohne DSP-Abbruch oder abgelehnte Sperre. Dieselbe Folge
ohne die zusätzlichen Haken bestand und schrieb 45328 Byte. Die zusätzliche
Einbindung hatte damit eine belegte Abweichung im längeren Ablauf.

### Gemessen im Emulator: Stack erst nach dem letzten Lesen freigeben

Die Sperrbeobachtung zeichnet keine abgelehnte Kernel-Freigabe auf. Sie
zeigt eine erfolgreiche Anforderung bei `0xC0014248`, danach eine weitere
Anforderung desselben Tasks bei `0xC0012FAC`, ohne Freigabe dazwischen.
Ein zweiter Task wartet ebenfalls. Der Sperrzähler steht auf null,
der gesicherte Kontextzeiger dagegen bereits auf null.

Im zusätzlichen Abschlussweg wurde SP vor dem Lesen des Besitzmerkmals
wieder auf den nativen Wert gesetzt. Der gesicherte Kontext lag damit
bereits unterhalb des freigegebenen Stacks. Auch der Abbruchweg setzte
SP zurück, bevor er alle gesicherten Register geladen hatte.

Zwei erzeugte ARM-Fälle überschreiben die alten Kontextbytes genau dann,
wenn SP den Bereich freigibt. Vor der Korrektur fehlt die Sperrfreigabe
bei beiden nativen Frame-Arten; im Abbruchfall werden Register falsch
wiederhergestellt. Jetzt werden Besitzmerkmal, ursprünglicher SP und alle
benötigten Rückkehrregister vor der Freigabe gelesen. Der Kontextzeiger
wird ebenfalls vorher entfernt. Es kommt keine zusätzliche IRQ-Sperre hinzu.
Alle 17 ARM-Modelltests bestehen.

Die anschließend wiederholte vollständige Hacktribe-Folge besteht mit
28605 DSP-Aufträgen. Die zuvor leere Exportdatei enthält wieder 45328 Byte,
der Kontextzeiger endet auf null und die DSP-Sperre ist frei. Die
72 nativen Einzelfälle sowie die acht Aufnahme- und sechs
Einzelexport-Fehlerfälle bestehen nach dieser Korrektur erneut.

Hergeleitet: Eine Unterbrechung darf unterhalb des freigegebenen SP wieder
Stackdaten ablegen. Das Besitzmerkmal kann dadurch verloren gehen, obwohl
der DSP-Auftrag selbst keinen Fehler meldet. Die gezielte Überschreibung
prüft diesen Fall im ARM-Modell; ein entsprechender Stackzugriff am echten
Gerät ist damit nicht gemessen.

Der Baustein ist noch nicht in `data/patches/sample-swap.json` eingebunden.
Die Initialisierung des gesicherten
Kontexts, verschachtelte oder unterbrechende Aufträge, die sichtbare
Fehlermeldung und das Verhindern einer nachfolgenden Slot-Veröffentlichung
bleiben vor dieser Einbindung zu prüfen. Der Emulator ersetzt außerdem
weder einen unterbrochenen echten DSP-Transfer noch den abschließenden
Gerätetest.

## Gemessen im Emulator: Aufnahmeabschluss nach einem DSP-Fehler

Die begrenzte Speicherabfrage allein verhindert keinen falschen Abschluss.
Nach einem Fehler beim Stop-Kommando liest `0xC004E23C` unveränderte
Stackdaten als Audio-Endzeiger. Der native Finalisierer `0xC004F128`
veröffentlicht daraus in beiden roten Builds eine angebliche Länge von
3218685176 Byte und setzt den DSP-Frei-Zeiger auf eine CPU-Adresse.
Der CPU-Zustand wechselt dabei auf 12, also Aufnahme fertig. Die normalen
2050 erzeugten PCM-Bytes werden dagegen korrekt finalisiert.

[`capture_fault.py`](../../tools/patch/capture_fault.py) prüft den gemeinsamen
Fehler vor dem Aufnahme-Start, vor Statusabfragen sowie vor und nach den
kritischen Abschlussstellen. Ein Fehler nach dem Endzeiger-Lesen nimmt
den ursprünglichen Stack-Abschluss des Finalisierers. Das ist nötig,
weil dieser `r11` als Metadatenzeiger benutzt, nicht als Frame-Pointer.
Der äußere Stop-Ablauf setzt seinen Erfolgszustand erst ohne DSP-Fehler.

[`capture_fault_cases.py`](../../tools/emu/capture_fault_cases.py) prüft in
beiden Builds vier Verläufe: Erfolg, bereits gesetzter Fehler, Fehler beim
Stop-Kommando und Fehler beim Lesen des Audio-Endes. Alle acht bestehen.
Bei Fehler bleiben die vollständigen Sample-Tabellen und der Frei-Zeiger
unverändert, der bisherige Slot bleibt erhalten, und Zustand 12 wird nicht
veröffentlicht. Eine folgende Statusabfrage mit absichtlich passenden
alten Registerdaten meldet ebenfalls keinen Abschluss. Ein weiterer
Aufnahme-Start liefert Ablehnung. Der normale Abschluss behält seine
2050 Byte. Fünf ARM-Modelltests prüfen zusätzlich Prologe, Rückkehr-Stack
und die Weitergabe der nativen Vergleichsflags.

Die Haken liegen weiter ausschließlich im Emulator-RAM. Eine sichtbare
Fehlermeldung und die kontrollierte weitere Bedienung nach einem solchen
Fehler gehören noch zur Einbindung in die Firmware. Die Prüfung erzeugt
weder Klang noch DMA und ersetzt keinen echten Aufnahmeversuch.

## Gemessen im Emulator: Einzelexport nach einem DSP-Fehler

Der native Einzelexport `0xC0039CC4` ruft den RIFF-Schreiber `0xC0039B2C`
auf. Dessen PCM-Schleife liest bei `0xC0039C2C` über `0xC004EDDC` aus dem
DSP und schreibt danach ohne Fehlerprüfung den Arbeitspuffer auf die
Karte. Ein gesetzter DSP-Fehler wird dabei nicht ausgewertet.

Ein erzeugtes Mono-Sample enthält 2001 Frames, also 4002 Byte PCM. Für den
Vergleich werden die erzeugten Wörter ausdrücklich in das DSP-Lesemodell
übernommen; das Mitschneiden der DSP-Schreibzugriffe allein füllt dieses
Modell nicht. Der Arbeitspuffer wird vor dem Export mit einem anderen
Wert gefüllt, damit alte gleiche Sample-Daten keinen Erfolg vortäuschen.
Der normale Export liefert eine passende WAV mit 5234 Byte. Ein erzwungener
Lesefehler setzt den bleibenden DSP-Fehler, liefert aber ohne weitere Haken
weiterhin Erfolg und eine WAV mit falscher PCM.

`tools/patch/sample_export_fault.py` verweigert den Einzelexport vor dem
Dateiöffnen, wenn bereits ein Fehler gesetzt ist. Der gemeinsame
RIFF-Schreiber prüft den Fehler ebenfalls vor dem ersten Schreiben sowie
nach jedem PCM-Lesen. Ein Fehler nach dem Lesen benutzt den vorhandenen
Aufräumpfad und meldet einen Schreibfehler zurück. Der äußere native
Fehlerübersetzer liefert dafür den Wert 4 statt Erfolg 0.

Die drei Fälle ohne Fehler, mit vorherigem Fehler und mit Fehler beim
Lesen bestehen in beiden roten Builds. Bei vorherigem Fehler entsteht
keine Datei. Beim Fehler während des ersten Lesens bleiben nur die zuvor
geschriebenen 44 Kopfbytes stehen: keine PCM und kein Sample-Datensatz.
Der Puffer wird genau einmal freigegeben, das Dateiobjekt geschlossen,
die DSP-Sperre frei und der Kontextzeiger null. DSP-Platz und Frei-Zeiger
des Samples bleiben unverändert. Zwei ARM-Modelltests prüfen zusätzlich
Rückkehr-Stack, erhaltene Register und den Fehlerübersetzer.

Diese Haken sind weiterhin nur im Emulator eingebaut. Sie ersetzen weder
den Gesamtexport noch den geplanten dauerhaften Schreibweg. Eine vor dem
Fehler neu angelegte WAV kann als unvollständige Datei stehen bleiben;
sie gilt nicht als erfolgreicher Export.

## Vorbereiteter Gerätetest: Stimmen nur lesen

[`sample_voice_watch.py`](../../tools/device/sample_voice_watch.py) beobachtet
die beiden nativen Flag-Arrays sowie Part-Zeiger, logischen Slot und
gehaltene Importnummer aller 24 Stimmen. Es sendet ausschließlich Suche,
INFO und CRC-geprüftes RAM-Lesen. Keine Taste, kein Transportstart, kein
EXEC, kein DSP-, Karten- oder Flash-Schreiben. Ohne `--observe` bleibt es
offline. Die eigene Originaldatei muss zum roten Gerät mit Korg 2.02 passen;
drei Code-Fingerabdrücke werden vor der Beobachtung verglichen.

```sh
python3 tools/device/sample_voice_watch.py --observe \
  --vsb ../eigene/SYSTEM.VSB --json ../berichte/stimmen.json --seconds 60 --hz 5
```

1. Den MIDI-Port für die Beobachtung freihalten. Ein Pattern mit bekanntem
   Sample benutzen; die Beobachtung verändert dessen Daten nicht.
2. Mit STOP beginnen, nach einigen Sekunden PLAY drücken, später STOP.
   Bis zum Ende weiter beobachten, damit die Freigabe sichtbar werden kann.
3. In einem zweiten Lauf bei stehendem Sequencer ein einzelnes Sample am
   Pad auslösen und natürlich ausklingen lassen. Ein endloses Loop-Sample
   eignet sich dafür nicht.
4. Beide Berichte außerhalb des Repos aufbewahren. Ein Berichtspfad muss
   neu sein; eine vorhandene Datei wird nicht überschrieben.

Jeder Zeitpunkt enthält zwei Leseproben. Unterscheiden sich Flags oder
Bindungen, ist `stable` falsch. Gleiche Proben sind keine atomare Aufnahme:
Eine zwischenzeitlich freigegebene und wieder belegte Stimme mit gleichen
Werten kann unbemerkt bleiben. Die tatsächliche Lesedauer steht im Bericht;
die angeforderte Rate ist keine garantierte zeitliche Auflösung. Der Test
liefert Beobachtungen zur Freigabe, keinen Beweis über jede Unterbrechung.
Ein passiver Lauf am Gerät ist inzwischen ausgeführt; der gezielte
Vergleich mit PLAY, STOP und natürlichem Ausklang bleibt offen.

### Gemessen am Gerät: passive Ausgangslage

Am 28.10. läuft die Beobachtung über den Linux-Rechner zehn Sekunden mit
zwei Leseproben pro Sekunde. Suche, INFO und die drei Code-Fingerabdrücke
bestehen. Alle 20 Beobachtungen sind stabil: keine der 24 Stimmen belegt,
keine geänderte Bindung, kein zurückgebliebener Part-Zeiger. Eine doppelte
Leseprobe dauert 21,96 bis 28,12 Millisekunden. Es gibt keine abweichende
Antwort und keinen Schreibzugriff. PLAY, STOP oder Pads werden nicht gesendet.

Das bestätigt die lesbare Ausgangslage auf dem Gerät. Es misst keine
Stimmenlaufzeit und keine Freigabe unter Wiedergabe.

### Gemessen am Gerät am 29.10.: PLAY, STOP und Einzelanschlag

Suche, INFO und die drei Code-Fingerabdrücke bestehen erneut. Die
Beobachtung sendet ausschließlich diese lesenden Befehle. Es gibt weder
EXEC noch WRITE, keinen Firmwarewechsel und keine Aufnahme der Audioausgabe.

Ein erster zweiminütiger Ausgangslauf bei fünf Beobachtungen pro Sekunde
liefert 600 stabile Doppelproben mit ausschließlich freien Stimmen. Ein
PLAY-Abschnitt war diesem Lauf nicht zugeordnet; er gilt deshalb nicht
als Wiedergabeprüfung.

Beim anschließend bestätigten PLAY erfasst ein 90-Sekunden-Lauf 450
Beobachtungen, davon 294 mit identischen Doppelproben. In 416 Beobachtungen
sind Stimmen belegt, höchstens sieben gleichzeitig. Die gelesenen
Part-Slotwerte betreffen acht User-Slots. Nach dem bestätigten STOP enden
die Belegungsflags wieder auf frei. Die letzten zehn Beobachtungen zeigen
keine belegte Stimme. Neun freie Einträge behalten dabei einen Part-Zeiger.
Ein nicht genullter Zeiger allein ist somit auch am Gerät kein Beleg für
eine weiterhin belegte Stimme.

Bei stehendem Sequencer folgt ein einziger bestätigter Pad-Anschlag eines
nicht geloopten User-Samples. Der 60-Sekunden-Lauf liefert 300 stabile
Doppelproben. Genau eine Stimme zu internem Slot 743, angezeigt als 744,
ist in 33 aufeinanderfolgenden Beobachtungen belegt. Diese Proben reichen
von etwa 9,41 bis 15,85 Sekunden des Laufs, also über eine beobachtete
Spanne von rund 6,4 Sekunden. Anschließend ist die Stimme wieder frei.
Das Ende des hörbaren Ausklangs wurde am Gerät bestätigt. Der Eingang
dieser Bestätigung ist kein präziser Zeitstempel des akustischen Endes.

Alle drei Läufe enden ohne CRC- oder Protokollfehler. Die unterschiedlichen
Doppelproben im laufenden Pattern bleiben ausdrücklich instabil, sie
werden nicht nachträglich zu atomaren Momentaufnahmen erklärt. Die
Rohberichte bleiben außerhalb des Repos.

Hergeleitet: Die native Belegungsabfrage ist für diese geprüften Abläufe
brauchbar und unterscheidet freie Einträge von zurückgebliebenen Zeigern.
Offen bleibt, ob bei jeder Spielart die letzte DSP-Nutzung der PCM exakt
mit der Freigabe zusammenfällt, insbesondere bei Release, Loop, geänderter
Tonhöhe und Stereo-Wechsel. Die Beobachtung ersetzt keinen hörbaren
Sample-Tausch mit diesen Randfällen.

## Offen vor 1.4

- Letzte DSP-Nutzung bei Release, Loop und Stereo-Wechsel sowie hörbarer Tausch.
- DMA bei Sampling und Resampling sowie konkurrierende Unterbrechungen.
- Gemeinsamer Dateibesitz für Import, Bearbeitung, Aufnahme und USB.
- Getrennte Versionsbindung bei dauerhaftem Ersetzen eines bereits geladenen Slots.
- Fehlerweitergabe über die übrigen nativen DSP-Wartepfade.
- Vollständiger Ersatz aller Speicherwege vor Entfernen des Gesamtexports.

Die Änderung ist keine Freigabe für 1.4. Der alte Gesamtexport kann eine
große Bibliothek weiterhin auf den im DSP vorhandenen Satz verkürzen.
