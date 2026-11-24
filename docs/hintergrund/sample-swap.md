# Sample-Swap: wie Samples in den DSP und wieder heraus kommen

Hintergrund zum Patch `sample-swap` ([Sample-Swap](../glossary.md#sample-swap)): welche Regeln für Stimmen, Verdrängung, Warten, Namen und Speichern gelten und wie sie bekannt sind. Der Aufbau des Patches steht in [Sample-Swap: der Bau](../messungen/2026-10-26-sample-swap-bau.md), die Zeitgrenzen des Transports in [Sample-Swap: RAM-Besitz und Zeitgrenze](../messungen/2026-10-25-sample-swap-timeout.md), die Schutzfälle in [Sample-Swap: Schutz der Daten](../messungen/2026-10-30-sample-swap-schutz.md), das Speichern eines Slots in [Sample-Sammlung](../messungen/2026-10-27-sample-store.md).

Die Rohmessungen hinter diesen Fakten sind aus dem Baum gelöscht. Sie bleiben in der Git-Historie lesbar: `git show 03c7827adc7b:docs/messungen/<datei>`. Jeder Abschnitt nennt seine Quelle.

Beleg-Wörter: **gemessen am Gerät**, **gemessen im Emulator** (ARM-Emulator mit eigenen Firmwaredateien und selbst erzeugten Samples, der DSP ist dort eine Attrappe), **hergeleitet** (aus gelesenem ARM-Code), **offen** (nicht versucht).

## Inhalt

- [Wann der Swap an ist](#wann-der-swap-an-ist)
- [Stimmen und Belegung](#stimmen-und-belegung)
- [Platz im DSP: der Allocator der Firmware](#platz-im-dsp-der-allocator-der-firmware)
- [Verdrängen und Veröffentlichen](#verdrängen-und-veröffentlichen)
- [Wann geladen wird: Bereitschaft, Pausen, Rennen](#wann-geladen-wird-bereitschaft-pausen-rennen)
- [Verlorene Benachrichtigung und neue Zielwahl](#verlorene-benachrichtigung-und-neue-zielwahl)
- [Start: EXIT, Journal, Kartenfehler](#start-exit-journal-kartenfehler)
- [Part-Auswahl und OSC-Drehgeber](#part-auswahl-und-osc-drehgeber)
- [Namen vor dem Laden](#namen-vor-dem-laden)
- [Der DSP-Anfragepfad und das Warten](#der-dsp-anfragepfad-und-das-warten)
- [Aufnahme und Einzelexport nach einem DSP-Fehler](#aufnahme-und-einzelexport-nach-einem-dsp-fehler)
- [Einzelnes Sample dauerhaft speichern (Snapshot)](#einzelnes-sample-dauerhaft-speichern-snapshot)
- [Festgelegt für das Speichern auf der Karte](#festgelegt-für-das-speichern-auf-der-karte)
- [DSP-Befund: Ring und Speicher-DMA](#dsp-befund-ring-und-speicher-dma)
- [Fallen der Gerätemessung](#fallen-der-gerätemessung)
- [Offene Schutzlücken](#offene-schutzlücken)
- [Randthema: Vorschau, Part holen](#randthema-vorschau-part-holen)

## Wann der Swap an ist

Der Swap ist nur an, wenn die ganze Datei größer ist als `ss_cap + 0x1000`. Der Vorgabewert von `ss_cap` ist 25 MiB, also 26.218.496 Byte. Verglichen wird die ganze Datei mit ihren Record-Headern, nicht die Summe der PCM-Daten. Kleinere Dateien lädt der native Gesamtlader. Gemessen im Emulator ist der Start mit nur Index und aktivem Pattern damit nicht für jede Bibliotheksgröße umgesetzt. Folge für Tests: Sitzungen mit einer 24-MB-Datei prüfen den nativen Modus mit installierten Haken, nicht die dynamische Auslagerung.

Quelle: Messung 2026-11-09/sample-swap-pruefung

Die Dateiverarbeitung `src/sample-file.mjs` hat keine Grenze bei 25 MiB: Ein Eintrag lässt sich an eine über 48 MiB große `.all` anhängen, vorhandene Daten bleiben unverändert, 25 Namen und Formate lesen mit weniger als 16 KiB Daten. Die native Probe `case_long_set` (über 50 Millionen Byte, echtes DSP-Budget, beide roten Builds) lädt beim Start nur den Slot des ersten Patterns und danach beim Patternwechsel die neu benötigten Slots. Gemessen im Emulator.

Quelle: Messung 2026-11-09/sample-swap-develop

Die Besitzer im oberen RAM im vollen Build (gemessen im Emulator): Dateipuffer ab `0xC274F000`, Index `0xC2768000`, Cache-Verzeichnis `0xC2769000`, Schutzdaten `0xC276CE80`, Signaturen `0xC3FFF000`. Der Schutzcode bei `0xC019C520` liest Wörter bei `0xC276CEBC`. Ein erfolgreiches Modusergebnis gibt diese Bereiche nicht zur Wiederverwendung frei, und echtes DMA ist dort nicht geprüft.

Quelle: Messung 2026-11-09/sample-swap-pruefung

## Stimmen und Belegung

Ein Sample darf nur verdrängt werden, wenn keine Stimme es mehr liest. Die Belegung kommt aus der nativen Stimmenliste.

| Teil | Wert | Beleg |
|---|---|---|
| Stimmenliste | ab `0xC06916A0`, 24 Einträge, Abstand `0x48` | hergeleitet |
| Part-Zeiger bei `+4` | **kein** Belegt-Merkmal: die native Freigabe `0xC0091AD0` lässt ihn stehen | hergeleitet, am Gerät bestätigt (neun freie Einträge behalten ihn) |
| Belegtabfrage | `0xC009115C` | hergeleitet |
| Importnummer einer belegten Stimme | `+0x40` | hergeleitet |
| logische Slotnummer | `+0x3A`, kann nach einer Namensumbindung schon auf andere PCM zeigen | hergeleitet |
| Part-Zugriff | `0xC009AF20` liefert die 16 tatsächlichen Parts, ihr Sample liegt bei `+0x34` | hergeleitet |

Eine freigegebene Stimmenadresse wird wiederverwendet: derselbe Zeiger heißt nicht dieselbe Stimme. Beim Wechsel von Mono auf Stereo kann die native Part-Aktualisierung Stimmen des betroffenen Part-Paars freigeben.

Quelle: Messung 2026-10-28/sample-swap-stimmen

### Gemessen am Gerät: Stimmen nur lesen

Passive Ausgangslage am 28.10.: zehn Sekunden, zwei Leseproben je Sekunde. Alle 20 Beobachtungen stabil, alle 24 Stimmen frei, keine geänderte Bindung. Eine doppelte Leseprobe dauert 21,96 bis 28,12 ms.

PLAY, STOP und Einzelanschlag am 29.10. (rotes Gerät, nur Suche, INFO und CRC-geprüftes RAM-Lesen):

| Lauf | Ergebnis |
|---|---|
| 2 Minuten Ausgangslauf, 5 Hz | 600 stabile Doppelproben, alle Stimmen frei |
| PLAY, 90 s | 450 Beobachtungen, 294 mit identischen Doppelproben, in 416 Beobachtungen Stimmen belegt, höchstens sieben gleichzeitig, die Part-Slotwerte betreffen acht User-Slots |
| nach STOP | die letzten zehn Beobachtungen ohne belegte Stimme, neun freie Einträge behalten einen Part-Zeiger |
| ein Pad-Anschlag, nicht geloopt, 60 s | 300 stabile Doppelproben, eine Stimme zu internem Slot 743 (angezeigt 744) in 33 aufeinanderfolgenden Beobachtungen belegt, etwa 9,41 bis 15,85 s des Laufs, also rund 6,4 s, danach frei |

Das Ende des hörbaren Ausklangs wurde am Gerät bestätigt. Die Bestätigung ist kein genauer Zeitstempel. Unterschiedliche Doppelproben im laufenden Pattern bleiben instabil, sie sind keine atomare Momentaufnahme. Hergeleitet: Die native Belegtabfrage ist für diese Abläufe brauchbar. Offen: ob bei Release, Loop, geänderter Tonhöhe und Stereo-Wechsel die letzte DSP-Nutzung der PCM genau mit der Freigabe zusammenfällt.

Quelle: Messung 2026-10-28/sample-swap-stimmen

### Geräteprobe wiederholen (nur lesen)

Werkzeug: `tools/device/sample_voice_watch.py`. Es beobachtet beide Flag-Arrays, Part-Zeiger, logischen Slot und Importnummer aller 24 Stimmen. Es sendet nur Suche, INFO und CRC-geprüftes RAM-Lesen: keine Taste, kein Transportstart, kein EXEC, kein Schreiben in DSP, Karte oder Flash. Ohne `--observe` bleibt es offline. Vor der Beobachtung vergleicht es drei Code-Fingerabdrücke mit der eigenen Original-VSB (rotes Gerät, Korg 2.02).

```sh
python3 tools/device/sample_voice_watch.py --observe \
  --vsb ../eigene/SYSTEM.VSB --json ../berichte/stimmen.json --seconds 60 --hz 5
```

1. Den MIDI-Port für die Beobachtung freihalten. Ein Pattern mit bekanntem Sample benutzen, die Beobachtung verändert dessen Daten nicht.
2. Mit STOP beginnen, nach einigen Sekunden PLAY drücken, später STOP. Bis zum Ende weiter beobachten, damit die Freigabe sichtbar wird.
3. In einem zweiten Lauf bei stehendem Sequencer ein einzelnes Sample am Pad auslösen und natürlich ausklingen lassen. Ein endloses Loop-Sample eignet sich nicht.
4. Beide Berichte außerhalb des Repos aufbewahren. Ein Berichtspfad muss neu sein, eine vorhandene Datei wird nicht überschrieben.

Jeder Zeitpunkt enthält zwei Leseproben. Unterscheiden sich Flags oder Bindungen, ist `stable` falsch. Gleiche Proben sind keine atomare Aufnahme: Eine zwischendurch freigegebene und wieder belegte Stimme mit gleichen Werten fällt nicht auf. Die tatsächliche Lesedauer steht im Bericht, die angeforderte Rate ist keine garantierte Auflösung.

Quelle: Messung 2026-10-28/sample-swap-stimmen

## Platz im DSP: der Allocator der Firmware

Acht Prüfungen im isolierten ARM-Emulator (originale Reservierungs-, Lösch- und Kapazitätsroutinen, selbst erzeugte Tabellen, beide geprüften Builds, kein Boot, kein DSP-Ersatz):

1. 1024 Byte für Index 500 beginnen bei `0x00365EC0`.
2. 2048 Byte für Index 501 folgen bei `0x003662C0`.
3. Erneutes Reservieren eines aktiven Platzes wird ohne Tabellenänderung abgewiesen.
4. Löschen von Index 500 deaktiviert ihn, lässt den Frei-Zeiger aber bei `0x00366AC0`.
5. Erneutes Laden von 512 Byte in denselben Slot beginnt bei `0x00366AC0`, nicht im Loch.
6. Löschen dieses letzten Samples setzt den Zeiger auf dessen Anfang zurück.
7. Danach das Löschen von Index 501 lässt das erste Loch von 1024 Byte verloren.
8. Eine Reservierung bis genau `0x01C65EC0` geht, weitere 32 Byte werden abgewiesen.

Hergeleitet: Nur das letzte physische Sample gibt Platz an den normalen Allocator zurück. Die Löschroutine `0xC004E558` nimmt den Schlüssel, löst ihn über `0xC004E2F0` auf, verschiebt keine PCM und löscht den DSP-Inhalt nicht. Der Swap muss einen vorhandenen DSP-Bereich selbst überschreiben und die Tabellen konsistent halten. Die normale Reservierung ist dafür keine fertige Schnittstelle.

Hilfsroutinen: `0xC004E208` liefert den nächsten freien Offset, `0xC004E218` die freien Bytes (`0x01C65EC0` minus Zeiger, ein Rest unter 4 Byte zählt 0). `0xC004F2B4` setzt beim vollen Laden die aktiven Marken und den DSP-Frei-Zeiger auf `0x00365EC0` zurück. Ein volles Laden ist also kein schrittweiser Swap.

Quelle: Messung 2026-10-25/sample-swap

## Verdrängen und Veröffentlichen

Regeln (hergeleitet, im Emulator und im ARM-Modell geprüft):

- Geschützt sind die `+0x34`-Samples der 16 Parts, dazu die Samples des laufenden Patterns und des Wechselziels.
- Belegte Stimmen, die sich nicht auflösen lassen, verhindern eine Verdrängung.
- Ein Nutzeralias macht eine Werks-Zeile nicht zu einem freigebbaren Nutzerplatz.
- Die Suche nach einem Kandidaten läuft mit unverändertem Interruptzustand. Erst die letzte Wiederholung der Prüfung (Modus, Parts, Aliase, Stimmen) und das native CPU-Löschen `0xC004E558` laufen mit maskierten IRQs.
- Die ARM-Prüfung setzt einen Kandidaten ans Tabellenende und verlangt weniger als 5000 emulierte Befehle mit neu maskierten IRQs. Das ist keine Zeitgrenze am Gerät und kein Nachweis über FIQ-Zugriffe.

Quelle: Messung 2026-10-28/sample-swap-stimmen

Veröffentlichen eines geladenen Samples (hergeleitet, im Emulator geprüft): Die letzte Generationsprüfung, die Kontextprüfung, das vorübergehende Setzen des DSP-Frei-Zeigers und die native CPU-Reservierung liegen in einem kurzen IRQ-geschützten Abschnitt. Danach wird der IRQ-Zustand wiederhergestellt. DSP-Übertragung und Part-Aktualisierung bleiben außerhalb. Ein veralteter Auftrag erreicht die native Reservierung nicht, ein verbotener Kontext wird davor abgefangen. Bei nativer Verweigerung bleiben Stack, IRQ-Maske und Frei-Zeiger erhalten. 1215 emulierte Befehle laufen dabei mit maskierten IRQs, die native Funktion gibt zwischendurch nichts frei.

Cache-Integrität: Die Prüfsumme beim Vorausladen beginnt mit dem ursprünglichen Deskriptor, danach kommen die normalisierten PCM-Wörter. Beim Laden aus dem Cache wird der Deskriptor zuerst in das getrennte Ziel kopiert, die Summe läuft über diese kopierten Metadaten plus PCM. Bei Abweichung wird die Cache-Generation verworfen, der Slot bleibt von der Karte ladbar und gilt nicht als dauerhaft fehlerhaft. Das Format der vier Wörter je Verzeichniseintrag bleibt.

Quelle: Messung 2026-10-29/sample-swap-korrektur

Kopieren nach einer Pufferübergabe: Gibt eine andere Task den unteren Cache-Bereich (Geber `0xC00369F0`) an sich, überschrieb ein alter Auftrag 24 Wörter PCM und 296 Wörter Deskriptorkopie, obwohl die Metadatentabelle unverändert war. Eine gesperrte Veröffentlichung schützt davor also nicht. `copy32` prüft deshalb vor jedem 32-Byte-Schritt die Auftragsgeneration bei kurz gesperrten IRQs und stellt den IRQ-Zustand zwischen den Schritten wieder her. Eine 64-KiB-Kopie läuft nie am Stück mit gesperrten IRQs, der Test erlaubt höchstens 16 aufeinanderfolgende maskierte Befehle (keine Zeitmessung am Gerät). Gemessen im Emulator.

Quelle: Messung 2026-10-29/sample-swap-puffer

Codebereich: Der Splash-Editor belegt `0xC01A2500` bis `0xC01A2FD4`. Ein Swap-Code ab `0xC01A2FD0` überlappt ihn um 4 Byte, der Patcher verweigert den Satz. Der Swap-Code beginnt deshalb ausgerichtet bei `0xC01A2FE0`, die Reservierung endet weiter bei `0xC01A3C00`, der Code ist 2.896 Byte groß, 208 Byte bleiben frei. Gemessen im Emulator.

Quelle: Messung 2026-11-09/sample-swap-develop

## Wann geladen wird: Bereitschaft, Pausen, Rennen

Bereitschaft gegen Planung (gemessen im ARM-Modell und im Emulator):

- Gescheiterte oder fehlende Nutzerslots halten den Wechsel auf. Die Ladeplanung darf gescheiterte Aufträge überspringen, die Bereitschaft nicht. Ein Ziel ist erst bereit, wenn jeder benötigte Nutzerslot über die drei Zuordnungen als aktiv im DSP gefunden wird, auch wenn er im aktuellen Dateikopf fehlt. Eingebaute Klänge und leere Part-Einträge sind keine Ladeaufträge.
- Beide Wechselhaken prüfen auch in `MODE = 2` weiter. Vollständig residente Ziele dürfen weiter wechseln, sie brauchen keinen DSP-Transfer.
- Ein gelatchter Transportfehler stoppt weitere Ladeaufträge, die Kette behält ihren letzten Wiederholungszähler. Ein gescheiterter Ladeversuch macht einen Slot nie spielbar.
- Mit einem DSP-Fehler verweigert die Bereitschaft auch residente, leere und nur mit Werkssamples belegte andere Patterns, das laufende bleibt. Gemessen im Emulator: Ohne diese Regel wechselt die Nummer von 0 auf 5 trotz DSP-Fehler. Vorhandene PCM beweist nicht, dass die Stimmen- und Parameterkommandos des neuen Patterns laufen können. Ein reiner Kartenfehler bleibt davon getrennt.

Quelle: Messung 2026-10-27/sample-swap-1-4, Messung 2026-10-29/sample-swap-wartepfade

Pausenregeln (hergeleitet, mit erzeugten ARM-Tabellen gemessen):

- Ladeabschnitte laufen nur auf der unverdeckten Hauptseite in einem der Sequencer-Zustände 0 bis 5.
- Fenster, andere Seiten, Aufnahmezustand 11 und das Transportmerkmal `+0x312` pausieren Aufträge. Geprüft wird vor jedem Abschnitt und nach Kartenlesen, DSP-Transfer und Deskriptorkopie. Ein verworfener Auftrag bekommt keine fertige Cache- oder DSP-Belegung, seine Generation ändert sich beim Pausieren einmal.
- Das Pausieren behält den zuletzt beobachteten PLAY-Zustand. Sonst würde die Rückkehr aus einem Menü einen neuen Füllstart auslösen.
- Ein vorübergehend voller DSP markiert den Zielslot nicht als fehlerhaft, das Pattern bleibt aktiv und der Auftrag kann später erneut laufen. Ein Protokollfehler bleibt gesperrt.

Quelle: Messung 2026-10-28/sample-swap-stimmen

Rennen beim Start (gemessen im ARM-Modell, alle Fälle schlugen vor der Korrektur fehl):

- Beide Auftragsstarter nehmen ihre Generation vor der Cache-Suche und vor dem Parseraufruf. Nach einem Generationswechsel brechen sie ab, bevor sie einen Slot als gescheitert markieren oder etwas veröffentlichen. Ohne diese Reihenfolge gilt ein alter Cache-Zeiger nach einer Invalidierung während der Platzsuche als Auftrag der neuen Generation.
- Das Datei-Handle behält die Generation seines Öffnens. Die nächste Generation schließt und öffnet es neu. Sonst würde ein älteres Handle als neues markiert.
- Die Datei-Routine liegt im zweiten statt im dritten reservierten Codebereich, kein zusätzlicher RAM.
- Ältere schreibende Messwerkzeuge verweigern ihren Arbeitsbereich auch bei `MODE = 2`. Der Fall lief nicht am Gerät.
- Generationsprüfungen vor dem Schreiben aus dem Zwischenpuffer, nach einem Block und nach der Deskriptorkopie. Das erlaubt keine Aussage über DMA oder beliebige Unterbrechungen im Block.

Quelle: Messung 2026-10-27/sample-swap-1-4

## Verlorene Benachrichtigung und neue Zielwahl

Gemessen im Emulator: Ging die Swap-Benachrichtigung absichtlich verloren, bleibt ein einfacher `POSTED`-Merker für immer stehen und der Ladeauftrag läuft nie wieder an. Deshalb zählt ein Ablaufzähler, der Bildschritt benachrichtigt nach 50 Aufrufen erneut (25 Hz, rund 2 s, gemessen 1,99 s Emulatorzeit). Bis zum Laden bleibt das alte Pattern. Erst der Beginn von `ss_step` bestätigt, dass eine Nachricht angenommen wurde, nicht der Rückgabewert des nativen Nachrichtenaufrufs.

Ein gescheitertes Ziel blieb nach einer neuen, bestätigten Patternwahl als alter Auftrag eingetragen. Der Haken bei `0xC008205C` läuft, nachdem der native Wähler die Auswahl angenommen und seine Felder gesetzt hat. Nur im aktiven Swap-Modus löst er einen alten Auftrag samt Fehlermarker. Das Auswählen des laufenden Patterns verwirft damit das alte Ziel, eine neue Wahl geht wieder über den normalen Lade- und Bereitschaftsweg. Cache-Generation und vorhandene PCM bleiben. Abgelehnte native Auswahlen und der Karten- oder DSP-Fehlermodus benutzen den Haken nicht.

Quelle: Messung 2026-10-29/sample-swap-wartepfade

## Start: EXIT, Journal, Kartenfehler

EXIT beim Einschalten muss vor der Journal-Wiederherstellung entschieden werden. Gehaltenes EXIT führt zum nativen Öffnen und bleibt bis zur Rückgabe in Modus 0, auch wenn die Taste beim Öffnen der Sammlung losgelassen wird. Eine frühe EXIT-Prüfung ohne festgehaltene Entscheidung erreichte Modus 1, übersprang die Wiederherstellung und ließ das beschädigte Journal liegen (ARM-Fall und native Probe reproduzieren das). Der Lader schließt weiter einen offenen Swap-Leser und beachtet einen gespeicherten DSP-Fehler. Gemessen im Emulator. Der Test braucht eine Sammlung über dem verkleinerten Swap-Schwellwert, eine kleine Datei zeigt den Fehler nicht.

Der Kartenfehlermodus (Modus 1 und 2) gilt in beiden Part-Haken gleich:

- Ein gesetzter DSP-Fehler verweigert die native Aktualisierung vor jeder Auswahl und schreibt nichts an den DSP-Port.
- Bei intaktem DSP bleiben Werkssamples, leere Plätze und bereits geladene Nutzersamples nutzbar.
- Ein indizierter, nicht geladener Nutzerplatz bleibt gesperrt.

Gemessen im Emulator: Werksplatz 400 und geladener Platz 500 gehen, nicht geladener Platz 501 wird verweigert. Mit DSP-Fehler werden alle drei verweigert.

Der native Namensvergleich liest das gemessene Namensfeld, nicht die festen Kopfdaten am Anfang des Namensrecords.

Quelle: Messung 2026-10-29/sample-swap-exit-parts

## Part-Auswahl und OSC-Drehgeber

Der OSC-Drehgeber überspringt ungeladene indizierte Slots (gemessen im Emulator, sechs indizierte Slots 500 bis 505, kleines Budget, nur 500 geladen): Der Iterator `0xC0040D50` sucht ab `r0` einschließlich in Richtung `r1` (plus oder minus eins) mit Umlauf über die logischen Nummern 0 bis 998. Der Aufruf bei `0xC0040DB4` übergibt den nativen Importschlüssel an `0xC004E3CC`. Die Funktion löst die Zuordnungstabellen auf und liest bei `0xC004E3E0` das Geladen-Flag `META + 11`. Null führt über `0xC0040DBC` zum nächsten Kandidaten. Im normalen OSC-Pfad folgt kein Kategoriefilter, die getrennte Kategorie-Navigation ist nicht geprüft. Der Namenscache zeigt beim übersprungenen Slot weiter `Sample502` statt des Dateinamens.

Der Haken `ss_choice` umschließt nur diesen Auswahlaufruf und behält das ursprüngliche Ergebnis. Nur bei bisheriger Rückgabe null darf im Swap-Modus 1 ein logischer Nutzerslot 500 bis 998 mit vorhandenem Indexeintrag gewählt werden. Andere Modi, Werkssamples, leere und ungültige Slots behalten den nativen Weg. Der Haken liest nur den Index. Die Part-Sperre verweigert die Übernahme, bis die PCM vollständig übertragen und veröffentlicht ist. Der Dauerfall (fünf Einträge, Lücke bei 502, kleines Budget) wählt 500, 501, 503 und zurück 501.

Part-Auswahl wartet auf PCM (gemessen im Emulator): Verlangt ein Part, der Slot 500 spielt, den ungeladenen Slot 505, übernimmt der native Aktualisierer die neue Nummer vorzeitig und die Spielart bleibt nach dem Nachladen ungültig. Der Patch erzwingt diesen Ablauf: gewünschte Auswahl 505 setzen, Aktualisierer aufrufen, tatsächliche Auswahl 500 während des Ladens behalten, PCM übertragen und Tabellen eintragen, genau die wartenden Parts nachziehen, tatsächliche Auswahl 505 mit gültiger Spielart prüfen. Die Haken bei `0xC0099FFC` und `0xC0099D88` sichern den äußeren Aktualisierer und direkte Aufrufe der Bindung. Leere, nicht indizierte und Werks-Auswahlen behalten ihr natives Verhalten. Ein gesperrter DSP-Transport veröffentlicht keine neue Part-Bindung.

Quelle: Messung 2026-10-30/sample-swap-oszillator, Messung 2026-10-28/sample-swap-stimmen

## Namen vor dem Laden

Gemessen im Emulator (Slots 501, 502, 504 und 999, intern 500, 501, 503, 998, nur 501 im Startpattern): Mit der Namenserweiterung liefert die native Namensabfrage die Namen der nicht residenten Samples, ohne deren Audio vorzuladen. Die 27 beobachteten Datei-Leseanforderungen überlappen keinen PCM-Bereich.

Aufbau (hergeleitet aus beiden Originalen und dem Patch):

- Katalog ist die vorhandene RAM-Namenstabelle `0xC047B080 + Slot * 0x20 + 12`, je 16 Byte. Importnummer, Kategorie und Belegung bleiben unverändert. Es gibt keinen zweiten RAM-Katalog.
- Reihenfolge beim Start: Kopf, PCM des aktiven Patterns, danach die Metadaten der übrigen indizierten Slots, vor dem Schließen der Startbibliothek. Der 4-KiB-Index wird vor dem Namensdurchlauf erneut gelesen und geprüft. Der Parser läuft mit der Probe `PREP=1` und endet vor dem Eintragen oder Übertragen von PCM.
- Die Veröffentlichung eines Namens prüft Generation und Residenz unter kurzer IRQ-Sperre, Dateioperationen laufen außerhalb dieser Sperre.
- Die native Namensabfrage `0xC0099788` verwirft Namen, wenn `0xC0099634` keine residente physische Zeile findet. Nur der Aufruf an `0xC00997CC` bekommt im Swap-Modus eine zusätzliche Prüfung des indizierten, nicht gescheiterten Slots.
- Die native Löschung `0xC004E558` lässt die Namenszeile stehen, ein Sicherungspuffer für Namen ist nicht nötig.
- Nach einer geprüften Dateiänderung werden die Namen nicht residenter Einträge neu gelesen, geladene und womöglich bearbeitete Namen bleiben.

Falle Phantomname: Bei leerem Index (große Datei, alte PCM-Blöcke, älterer nicht leerer Index im RAM) kopierte der alte Durchlauf den Index erst beim ersten belegten Slot. Die Namensabfrage zeigte dann einen Phantomnamen aus dem alten RAM-Katalog. Die native Probe reproduziert das. Der erneute Header-Read behebt es. Seek-, Read-, Kurzlese- oder Headerfehler schließen die Datei und sperren den Katalog. Ein gültiger leerer Index bleibt leer.

Falle Kurzlese: Der Originalparser lässt eine zu kurze Leseantwort mit Erfolgsstatus als gültigen Metadateninhalt weiterlaufen. Die Prüfung sitzt an den sieben Lesestellen des Metadatenteils: `0xC0035B3C`, `0xC0035BA4`, `0xC0035C08`, `0xC0035CF8`, `0xC0035DA8`, `0xC0035DE8`, `0xC0035E18`. Bei `PREP=1` muss die tatsächliche Länge der angeforderten entsprechen, sonst geht ein I/O-Fehler an den Parser. Ein schon gemeldeter nativer Fehler bleibt. Die zwei späteren PCM-Lesestellen gehören zum Ladebalken und bleiben unverändert.

Probe bei großer Bibliothek: Eine feste Wartezeit nach dem Start ist keine gültige Fertigmeldung mehr (Metadatenlesungen laufen, die Bedienseite ist nicht frei, PLAY wird ignoriert). Die Probe wartet begrenzt auf die freie Bibliotheksleihe und ein geschlossenes Fenster, dann PLAY. Bei gehaltener Dateileihe fragt die UI nach OSC-Rad-Drehen bereits den richtigen Namen von Slot 501 ab, der tatsächliche Slot bleibt 500, bis 501 geladen ist (Emulator, kein Displaytest).

Offen: Installation am Gerät, physischer Displaytest, zusätzliche Startzeit durch viele kleine SD-Lesungen.

Quelle: Messung 2026-11-06/sample-swap-namen

## Der DSP-Anfragepfad und das Warten

### Port, Sperre, Status (hergeleitet, im Emulator geprüft)

- Die native Part-Aktualisierung schreibt selbst an den DSP-Port: Mono 48 Datenwörter und 7 Steuerwörter, Stereo 240 und 77. Sie ist kein reiner CPU-Tabellenzugriff und lässt sich nicht ungeprüft in den IRQ-Abschnitt der Namensregistrierung ziehen.
- Der Steuernachrichtensender nimmt die DSP-Sperre mit Index 1 bei `0xC00137FC` und gibt sie bei `0xC0013948` frei.
- Die Statusroutine `0xC001462C` wartet unbegrenzt auf Bit `0x80` und liefert danach die Bits `0x50`. Ihr Aufrufer bei `0xC00138F0` wiederholt, solange sie gesetzt sind. `0x50` als Fehlerrückgabe hängt dort erneut, null täuscht Bereitschaft vor.
- Lesen `0xC00141F8` und Schreiben `0xC0014284`: Leser bekommt DSP-Adresse, ARM-Ziel, Anzahl 16-Bit-Wörter und Speicherbereich in `r0` bis `r3`. Schreiber bekommt DSP-Adresse, ARM-Quelle und Anzahl in `r0` bis `r2`, Bereich 2.
- Im Bereich `0xC0011000` bis `0xC001462C` liegen 35 Paare aus Anforderung und Freigabe der DSP-Sperre 1. Alle haben denselben FP-basierten Prolog, vor der Anforderung verändert keiner `r4` bis `r10`.
- Die Sperrfreigabe funktioniert nur mit eingeschalteten IRQs. Mit maskierten IRQs liefert die Anforderung `0xFFFFFFE7`, ein erster Abbruch mit maskierten IRQs ließ die Sperre belegt.
- Drei Funktionen (`0xC0012758`, `0xC001430C`, `0xC00143E4`) geben ihren Frame ohne vorheriges Zurücksetzen von SP frei. Der Abschluss muss das Besitzmerkmal, den ursprünglichen SP und alle Rückkehrregister lesen, bevor SP den Frame freigibt, sonst liegt der gesicherte Kontext unterhalb des freigegebenen Stacks. Eine Unterbrechung kann dort Daten ablegen und den Kontextzeiger auf null setzen.

Quelle: Messung 2026-10-28/sample-swap-stimmen

### Der Baustein `native_dsp_scope`

`tools/patch/native_dsp_scope.py` verlässt bei Zeitüberschreitung den ganzen betroffenen nativen Auftrag, setzt einen bleibenden DSP-Fehler, sperrt den Swap und entwertet die Generation einmal. Stack, erhaltene Register und IRQ-Steuerung des Aufrufers werden wiederhergestellt. Eine selbst erworbene Sperre wird genau einmal freigegeben, eine nur geliehene bleibt beim äußeren Besitzer. Eine verweigerte Anforderung schreibt nicht an den Port und gibt nichts frei. Bei verweigerter Sperre veröffentlicht der Baustein keinen eigenen Rückkehrpunkt und löscht nur den eigenen.

Grenzen: 100 ms bei gültiger Timer-Konfiguration plus unabhängig eine Million Warteprüfungen (Emulatorversuche 128). Das ist keine gemessene Abbruchzeit am Gerät. Die Fälle in `tools/emu/native_dsp_scope_cases.py` setzen ihre Haken nur im Emulator-RAM. Sie decken die Steuernachricht der Part-Aktualisierung (`0xC00137A8`, nach Anforderung `0xC0013800`, vor Freigabe `0xC0013948`), DSP lesen (`0xC00141F8`, `0xC001424C`, `0xC0014274`) und DSP schreiben (`0xC0014284`, `0xC00142D8`, `0xC00142F8`). Die erweiterte Matrix hat 72 Fälle in beiden roten Builds. Ein Mono-auf-Stereo-Wechsel führt elf DSP-Aufträge aus, alle elf werden erfasst (317 Port-Schreibzugriffe). Die vollständige Stock-Ablauffolge erfasst 29.629 native DSP-Aufträge ohne abgelehnte Sperre, die Hacktribe-Folge 28.605 mit 45.328 Byte Gesamtexport. Gemessen im Emulator, kein DMA, kein Bootvorgang mit den neuen Haken.

Der Baustein ist im Swap-Patch eingebunden: 35 native Paare aus Erwerb und Freigabe, fünf gemeinsame Statuslesestellen und sechs GPIO-Aufrufe benutzen die Timeout-Helfer. Der Zeiger auf den aktiven Aufruf liegt im freien Wort `STATE + 0x1E0`, kein zusätzlicher Sample-Puffer. Der kalte Bibliothekseinstieg initialisiert ihn atomar, gehaltenes EXIT lässt ihn bei `0xFFFFFFFF`. Ohne Sampledatei kann der Einstieg entfallen, dann ist der Schutz nicht aktiv. Ein Aufruf aus ungeeignetem, maskiertem Kontext beginnt keinen Transfer.

Gemessen im Emulator (`native_dsp_scope_cases.py`): Die Frist von 100 ms gilt nur, solange MODE 1 ist und der Befehlsschritt des Swaps läuft (Statuswort `INSTEP`). Außerhalb läuft ein langer Status ohne Fehler durch. Der Statusport meldet dabei 1.200.000 Abfragen "beschäftigt", das dauert im Emulator rund 123 ms.

Quelle: Messung 2026-10-28/sample-swap-stimmen, Messung 2026-10-29/sample-swap-wartepfade

### Das Wortzähler-Limit

Die Funktionen `0xC00141F8` und `0xC0014284` speichern die Wortzahl als 16 Bit. Ein einzelner "2-MiB-Aufruf" läuft auf 0 über und ist kein Durchsatztest. 2 MiB gehen in 17 Aufrufen mit höchstens 65520 Halbwörtern, die PCM stimmt überein, kein Timeout (Emulatorzeit rund 200 ms, keine Übertragungszeit am Gerät). Gemessen im Emulator.

Quelle: Messung 2026-10-29/sample-swap-wartepfade

### Der Erwerb von Ressource 1 mit Frist

Die unveränderte Firmware hat: Zähler von Ressource 1 bei `0xC06A2480`, aktueller Task `0xC06A289C`, Erwerb `0xC0000D80` (wartet unbegrenzt), Freigabe `0xC0000CA8` (bedient wartende Schlangen), Verzögerung `0xC0000B78`, OS-Zähler in Millisekunden `0xC06A292C`. Die Funktionen haben in beiden Originalen dieselben Prüfsummen. Datei-Adressen: `file = ram - 0xC0000000 + 0x100`.

Warum ein eigener Erwerb nötig ist: Ein Wartender könnte weiterlaufen, nachdem Bibliothek oder Generation sich geändert haben, und ein neuer Aufruf könnte einen aktiven Wiederherstellungsrahmen ersetzen. `tools/patch/native_dsp_acquire.py` (hergeleitet, im Emulator geprüft):

- Vor dem Warten wird der Task festgehalten. Bibliotheksgebundene Aufträge halten Betriebsart, Generation, Sitzung, Schrittfreigabe, Schrittbesitzer und die vier Wörter des Dateibesitzers fest. Vor jedem Versuch und nach dem Erwerb müssen sie noch passen. Ein unabhängiger nativer Steuerauftrag bindet nur Task, gültigen Aufrufkontext und Fehlerzustand.
- Bei belegter Ressource wartet der Task je eine Millisekunde über die native Verzögerung. Nach 1000 OS-Ticks oder spätestens 1000 Versuchen endet das Warten (981 Verzögerungsaufrufe in den zwei Läufen). Das setzt einen laufenden Scheduler voraus.
- Nur der freie Zählerwert 1 wird unter gesperrten IRQs auf 0 gesetzt. Der Aufrufer prüft danach den globalen Rahmen erneut, veröffentlicht den eigenen Stapelrahmen und stellt den IRQ-Zustand wieder her. Ein vorhandener Rahmen wird nicht ersetzt. Die Freigabe läuft über die native Funktion.
- `INSTEP_TASK` nutzt das letzte freie Wort vor der Fehlertabelle bei `0xA0`. Eine gesetzte globale Schrittfreigabe gilt für einen fremden Task nicht als Freigabe.
- Drei Abbruchklassen: Vor dem DSP-Zugriff nur den eigenen Aufruf abbrechen, ein nativer Sample-Aufruf liefert Fehler 4. Erworben, aber nicht veröffentlichbar: die eigene Belegung einmal bei freigegebenen IRQs zurückgeben. Echter Fehler nach Protokollbeginn: den eigenen Rahmen abwickeln, den bisherigen verriegelten Fehler erhalten, nur die eigene Belegung freigeben.
- Der Fehlerzustand 1 nach 0 ist kein verriegelter Fehler, erst Werte ab 2 sperren weitere Zugriffe.
- Die Erwerbsgrenze von einer Sekunde ist getrennt von den 100 ms des DSP-Protokolls. Der Ersatz gilt nach der Initialisierung, vorher bleibt der native Startpfad.

Quelle: Messung 2026-11-09/native-dsp-besitz

### BUSY unter Wiedergabe

Gemessen am Gerät: Beim ersten Wiedergabeversuch kam Status 2 mit 0 übertragenen Wörtern (BUSY auf dem DSP-Port). Der Host wiederholt nur bestätigtes BUSY mit 0 Wörtern, höchstens 8 Aufrufe im Abstand von 10 ms. TIMEOUT, FAULT, Teilübertragung oder unbestätigte EXEC-Rückgabe werden nie wiederholt. Zwei 32-KiB-Läufe bei 25 MHz brachen nach acht belegten Portzugriffen ab, ein vollständiger 25-MHz-Zeitvergleich unter Wiedergabe liegt daher nicht vor. Ein späterer Ladeweg muss den Portzugriff einplanen und den Patternwechsel auslassen, wenn er nicht bereit ist. BUSY rechtfertigt keine lockereren Zeitgrenzen.

Quelle: Messung 2026-10-27/sample-swap-transfer

### Importnummer 49 und kleiner sind eingebaute Oszillatoren

Gemessen am Abbild, am Gerät gegengeprüft: Die Routine `0xC004EBD4` liest die Importnummer, vergleicht sie bei `0xC004EBF4` mit 49 und kehrt für Werte bis 49 ohne Sample-Zuordnung zurück. Erst Importnummern ab 50 betreten die drei Sampletabellen. Die Live-Prüfung des Werkzeugs umfasst `0xC004EBD4` bis `0xC004EDDC` einschließlich der ausgelagerten Zeiger im Literalpool.

Quelle: Messung 2026-10-27/sample-swap-transfer

Offen laut dieser Messung: Native FatFs-Aufrufe haben keine eigene Zeitgrenze. Offen sind auch 25 MHz unter Wiedergabe, längere Transfers, die Stimmenlebensdauer, die Slot-Neubindung, die echte DSP-Speichergrenze und der RAM-Besitz bei Sampling und Resampling. Die Rohmessung hat den Swap-Modus nicht mitgeschrieben, dem Werkzeug fehlte damals die MODE-Wache (`0xC0188530`).

## Aufnahme und Einzelexport nach einem DSP-Fehler

Gemessen im Emulator (beide roten Builds):

- Nach einem DSP-Fehler beim Stop-Kommando liest `0xC004E23C` unveränderte Stackdaten als Audio-Endzeiger. Der Finalisierer `0xC004F128` veröffentlicht daraus eine Länge von 3218685176 Byte, setzt den DSP-Frei-Zeiger auf eine CPU-Adresse und den CPU-Zustand auf 12 (Aufnahme fertig). Normale 2050 PCM-Bytes werden richtig finalisiert.
- `tools/patch/capture_fault.py` prüft den gemeinsamen Fehler vor dem Aufnahme-Start, vor Statusabfragen und um die kritischen Abschlussstellen. Ein Fehler nach dem Endzeiger-Lesen nimmt den ursprünglichen Stack-Abschluss des Finalisierers, weil der `r11` als Metadatenzeiger benutzt. Bei Fehler bleiben Sample-Tabellen und Frei-Zeiger unverändert, der alte Slot bleibt, Zustand 12 wird nicht veröffentlicht, ein neuer Aufnahme-Start wird abgelehnt.
- Der native Einzelexport `0xC0039CC4` ruft den RIFF-Schreiber `0xC0039B2C`. Dessen PCM-Schleife (`0xC0039C2C` über `0xC004EDDC`) wertete einen DSP-Fehler nicht aus und meldete Erfolg mit falscher PCM. Ein erzeugtes Mono-Sample mit 2001 Frames (4002 Byte PCM) ergibt normal eine WAV mit 5234 Byte.
- `tools/patch/sample_export_fault.py` verweigert den Export vor dem Öffnen bei gesetztem Fehler. Der Schreiber prüft vor dem ersten Schreiben und nach jedem PCM-Lesen. Ein Fehler läuft über den vorhandenen Aufräumpfad und gibt Fehlerwert 4 statt 0 zurück. Bei einem Fehler im ersten Lesen bleiben nur die 44 Kopfbytes stehen (keine PCM, kein Sample-Datensatz). Puffer einmal freigegeben, Dateiobjekt geschlossen, DSP-Sperre frei, Kontextzeiger null. Der Export ist nicht transaktional, eine zuvor neu angelegte WAV kann unvollständig stehen bleiben und gilt nicht als Export.
- Der Gesamtexport und die dauerhafte Speicherung sind damit nicht ersetzt.

Stereo-Aufnahme: Der native Parser macht aus 100 Stereo-Frames mit 16 Bit eine PCM-Länge von 400 Byte, Stereo-Flag 1, Loop-Ende und Sample-Ende bei Byte 396, der native Import belegt 400 Byte im DSP. Der Erzeuger `tools/emu/sampleset.py` muss Stereo-Flag und volle PCM-Länge setzen (bei 5000 Stereo-Frames laden beide Lader 20000 Byte, mit nur einem Kanal wären es 10000). `entryFromWav` zählt beide Kanäle und setzt Loop und Ende auf den letzten vollständigen 16-Bit-Frame, für neu erzeugte Datensätze. Ein Klangvergleich am Gerät fehlt.

Quelle: Messung 2026-10-28/sample-swap-stimmen, Messung 2026-10-29/sample-swap-wartepfade

## Einzelnes Sample dauerhaft speichern (Snapshot)

Gemessen im Emulator und hergeleitet, mit erzeugten Samples, ohne Klang oder Aufnahme-DMA:

- Der native Snapshot `0xC004EBD4` liefert mit fünftem Stackargument 0 die volle physische PCM-Belegung aus Basis und Länge der Metadatenzeile. Ein bearbeiteter Wiedergabestart verkürzt sie nicht. Argument 1 (normaler Einzelexport) kann einen Wiedergabe- oder Slice-Ausschnitt speichern.
- Deskriptor: `+56` wird 0, `+40` relativ zur PCM-Basis, `+60` ist eine Byteanzahl, `+65 == 1` heißt Stereo, `+72` ist die Samplerate.
- Der WAV-Schreiber `0xC0039B2C` setzt 16 Bit und liest über `0xC004EDDC` höchstens 32768 Halbwörter je Block, ohne Kanalumordnung. Ein Frame hat 2 Byte (Mono) oder 4 Byte (Stereo).
- Acht Fälle mit unterschiedlichen linken und rechten Kanalwerten über 64 KiB bestehen auf beiden roten Builds (Import und erzeugte Aufnahmeabschlüsse, Mono und Stereo).
- Der gebaute Rückleser `tools/patch/sample_snapshot.py` baut blockweise RIFF, fmt, data und den vollständigen korg/esli-Datensatz. Slot und Metadatenindex werden auf den logischen Zielslot normalisiert, die Importnummer ist Slot plus 50. Der Aufrufer muss den Dateibesitz halten und `0x10600` Byte getrennten Arbeitsspeicher geben, überlappungsfrei zum Schreibpuffer und zur Zustandsfläche des Kartenschreibers. Nicht 32-Byte-ausgerichtete Belegungsgrenzen bleiben erhalten (ausgerichteter Zwischenpuffer). Ein Teilfehler veröffentlicht keinen neuen Index, ein geschriebener Teilblock bleibt höchstens unerreichbar am Ende.
- Unveränderter Inhalt wird nicht erneut angehängt: Der gemeinsame ARM-Schreiber und der Browser-Schreiber vergleichen den bestehenden Eintrag blockweise (gleiche Länge, alle Bytes inklusive PCM und Metadaten) und schreiben dann weder Daten noch Journal noch Index. Schon ein anderer letzter PCM-Wert oder ein anderer Name reicht für eine neue Version. Ein fehlgeschlagenes Vergleichslesen ist ein Fehler ohne Anhang. Der Vergleich liegt vor der Kapazitätsprüfung, ein unveränderter Eintrag lässt sich also auch in einer Datei mit `0xFFFFFFFF` Byte bestätigen.
- Verschobene Belegung nach Neustart: Liegt logisch 500 im RAM über Import 651 in Zeile 601, zeigt der Slot nach dem Neustart bei unverändertem Dateiwert 651 auf die ungeladene Zeile. Nur das Dateifeld `+20` auf 550 geändert stellt Name und PCM wieder her. Der Adapter normalisiert dieses Feld. Die nativen Fälle prüfen die identische Zuordnung und logisch 500 über Import 651 in Zeile 601, jeweils Mono und Stereo. Nach Speichern und Neustart stimmen Name und PCM, der andere Slot bleibt unverändert, die alte PCM-Belegung bleibt.
- Das gleiche Speichern direkt danach lässt die Datei bytegleich und ruft `f_write` keinmal auf.

Offen: Der Adapter ist nicht an die Sample-Menüs angeschlossen. Ein Adapterversuch belegt kein Sample-WRITE über die normale Bedienung. Reale Aufnahme, Resampling, Stimmenausklang und DMA fehlen.

Quelle: Messung 2026-10-30/sample-snapshot

## Festgelegt für das Speichern auf der Karte

Entschieden vor dem Bau (Plan, der Stand der Umsetzung steht in [Sample-Sammlung](../messungen/2026-10-27-sample-store.md)):

- Die Karte ist der dauerhafte Sample-Speicher, der DSP hält nur den gerade nötigen Satz. Ein voller DSP verhindert keinen Kartenimport. Es gibt keine zusätzliche Grenze aus DSP-Größe oder Dateigröße. Die Nutzerplätze bleiben 501 bis 999. Die einzelne Datei bleibt durch 32-Bit-Offsets auf 4294967295 Byte begrenzt. Für eine spätere gemeinsame Projektdatei gibt es kein vorweggenommenes Containerformat.
- Auslöser: Sample-WRITE speichert den geänderten Slot (Name, Loop, Slice und destruktive Bearbeitung zusammen). Import, bestätigtes Löschen und fertige Aufnahme oder fertiges Resampling sind direkte Speicheraufträge. Abspielen, Sample-Auswahl, Patternwechsel und Swap schreiben nie. WRITE ohne Änderung hängt nichts an. Ein einzelner Drehgeberschritt oder das bloße Verlassen der Bearbeitung speichert nicht. Das normale Pattern-WRITE schreibt keine Sample-Bibliothek.
- Erfolg melden Sample-WRITE, Import und Löschen erst, wenn der gemeinsame Schreibweg den neuen Kartenstand geprüft hat. Bei Fehler bleibt der Zustand als ungesichert erkennbar, ein nur im DSP geänderter Slot gilt nicht als gespeichert.
- `EXPORT ALL SAMPLE` entfällt erst, wenn alle diese Wege samt Aufnahme und Resampling ersetzt und geprüft sind. Den Menüpunkt allein auszublenden reicht nicht, auch direkte Aufrufe des nativen Überschreibwegs müssen geschützt sein. Ein Wegfall vor dem Ersatz würde Daten verlieren.
- Beim künftigen Projektladen wird Cache-RAM dynamisch und exklusiv ausgeliehen. Übergabe und Rückgabe müssen vor der Projektanbindung gebaut sein, der Cache wird nicht dauerhaft verkleinert.
- Anbindung geladener Zeilen an den Dateioffset: Nur Status 0 bei `0xC0036700` (nach dem Parseraufruf) darf eine Bindung veröffentlichen. Nach einem Parserfehler kann der Deskriptor noch den vorherigen Slot enthalten. Deskriptor-Slot und Header-Slot dürfen nicht ungeprüft gleichgesetzt werden.
- Der Boot-Aufruf `0xC002AE58` erzeugt den nativen Standardpfad unabhängig von der Datei. Die frühe EXIT-Entscheidung muss erhalten bleiben.
- Alte Clients müssen über klar erkennbare Fähigkeiten begrenzt sein, damit kein alter Volllese- oder Vollschreibweg eine aktive Bibliothek kürzt.

Quelle: Plan 2026-10-27/sample-store

## DSP-Befund: Ring und Speicher-DMA

Gemessen im DSP-Simulator mit dem Hacktribe-Kandidaten, auch mit unveränderter roter Originalfirmware und ohne Swap:

- Ein Speicher-DMA auf Kanal `0x100` (Konfiguration `0x7607`, Wortbreite 2 Byte, Anzahl 2, Schrittweite 2) schreibt 4 Null-Bytes ab `0x00365EBE` und überschreibt das erste User-Halbwort. Der ARM hat bei `0xC0014848` das richtige Halbwort `0xECDA` übertragen, der DSP-Kern schreibt es in der Gegenprobe nicht selbst. Das erzeugt ohne Swap die ersten zwei Bytes von Slot 500 als null.
- Die Überlappung bleibt mit richtigen Deskriptorzeigern, Kanalabschaltung und begrenzten Quellzeilen bestehen (nach 800 ms Modellzeit).
- Der Ring endet exakt bei `0x00365EC0`: nach echtem Reset und RTOS-Start liest die Diagnose `B2 = 0x003082C0` und `L2 = 0x0005DC00`. Die DSP-Funktion `0xFFA04A94` schreibt den Auftragsstart.
- Die Platzsuche des Prototyps beginnt einen ausgerichteten 32-Byte-Block darüber (`0x00365EE0`). Bestehende Bereiche werden ab der physischen Untergrenze eingesammelt, ein alter Bereich über dem neuen Anfang bleibt belegt, leere alte Einträge setzen keinen Kandidaten unter die Grenze. Beim Öffnen der Bibliothek im Swap-Modus wird der Frei-Zeiger nach oben geklemmt. Das Budget zählt Datenbytes und wird vor der Adressaddition begrenzt.

Nach dem korrigierten Simulator liest der DSP nach dem Pad-Anschlag das verschobene Sample 502 per DMA bis zum letzten Wort (`dsp_reads_relocated_sample`, `dsp_reaches_sample_end`). Ein Gerätevergleich dieser Lesezugriffe fehlt. Offen: Ursache und Gerätevergleich des überlappenden DMA-Auftrags, natürliche Stimmenenden, große reale Bibliotheken am Gerät. Weitere Simulatorfakten stehen in [DSP im Simulator](../messungen/2026-11-12-dsp-im-simulator.md).

Quelle: Messung 2026-11-14/sample-swap-nativer-dsp

## Fallen der Gerätemessung

Gemessen am Gerät (rotes Gerät, BLECH, USB am Linux-Laptop mit ALSA und `mido`, Messung am 25.10.):

- Timer 3: Die Periode steht auf `149999999` (Zähler 0 bis PRD, 150 MHz). Die Probe muss gegen `TIMER_HZ - 1` prüfen, ein Test auf 150000000 bricht vor jedem DSP-Zugriff ab.
- Nicht beschriebenes RAM nach dem Einschalten ist nicht null, sondern zeigt vereinzelte gesetzte Bits (in beiden Puffern fast gleich). Die Puffer `0xC274F000` und `0xC275F000` müssen vor dem Test per BLECH WRITE in 2-KiB-Blöcken genullt werden.
- ALSA am Linux-Laptop verschickt keine SysEx-Nachricht mit 32 KiB (`MidiOutAlsa::sendMessage`). Die abgebrochene Nachricht lässt das Gerät mit "MIDI receive error" zurück. 2 KiB gehen.
- Dreimal kam auf EXEC keine Antwort mehr und das Gerät musste neu starten: einmal direkt nach der abgebrochenen 32-KiB-Nachricht, zweimal mit dem vollen Testcode, jeweils in einer anderen Sitzung nach dem Einschalten. Danach liefen Testcode und alle Teilschritte in über 20 Läufen ohne Hänger. Ursache offen. Der Host-Port-Pfad wartet ohne Zeitgrenze, ein Swap-Patch braucht dort eine Zeitgrenze oder einen Weg, der nicht aus EXEC kommt.
- Die Zeit eines 64-KiB-Blocks beim Abspielen (5,451 bis 6,276 ms) war nach Aussage am Gerät nur bei gezieltem Hinhören als kurze Verzögerung hörbar. Der Ziel-Slot war 645 (115346 Byte PCM, DSP-Offset `0x8E4F40`, Pattern 020 spielte), alle 499 Nutzerplätze waren belegt, ein synthetisches Sample ließ sich nicht importieren.
- Rechnung aus der Messung: Die 157 KB/s des Emulators gelten nicht für das Gerät, die Karte ist rund 20 mal schneller. 10 MB von der Karte brauchen etwa 3 s, aus dem RAM-Cache in den DSP etwa 1 s (hergeleitet).
- Gemessen am Gerät (32 KiB RAM zu DSP 13,2 bis 14,5 MiB/s, Karte zu DSP 2,19 bis 2,80 MiB/s, bei 12,5 und 25 MHz, ruhend und spielend): RAM ist 5 bis 6 mal schneller als die Karte. Ein RAM-Cache vermeidet Kartenlatenz, beweist aber keinen freien Dauer-Cache. Die Zeiten enthalten kein Öffnen, Seek und Schließen und laufen mit warmen Karten-Caches.
- Ein MMCCLK-Direktlesen über SysEx bei `0x01C40004` gab RANGE 3 und wurde zunächst als CRC-Problem gelesen. Der eigene Kartentreiber meldet ein erfolgreiches Öffnen mit `R_OPEN=1`, Lesen und Schließen mit 0.
- Unbenutzte geladene Kandidaten begannen nicht auf einer 32-Byte-Grenze, der Transport verlangt sie. Das Werkzeug nimmt einen ausgerichteten Ausschnitt innerhalb des geprüften Bereichs.

Sicherheitsregeln der Probe `tools/device/sample_swap_probe.py` (Ablauf 25.10. ausgeführt): Ohne `--execute` entsteht nur ein Offline-Plan. Der Zielslot muss ein selbst erzeugtes, entbehrliches Sample sein, in keinem Part und von keiner ausklingenden Stimme benutzt. Gestoppt beginnen, mit 1 KiB anfangen, 4, 16 und 64 KiB einzeln mit eigenen Ergebnisdateien. Beim Beobachtungswerkzeug und bei der Probe gilt: Bei fehlender Antwort abbrechen und das Gerät neu starten, nicht erneut starten und nichts manuell weiterschreiben, solange die Wiederherstellung ungeklärt ist (Sicherung ab `0xC274F000`). Die Probe prüft per XOR `0x01010101` und vergleicht die Bereiche `0xC00141F8` plus `0xD10`, `0xC004EDDC` plus `0x14` und `0xC004EF28` plus `0x6C` gegen die Originaldatei. Die Karte wird nicht angefasst.

Quelle: Messung 2026-10-25/sample-swap, Messung 2026-10-27/sample-swap-transfer

Ein Gerätetest mit dem minimalen Messbuild (nur BLECH-SysEx) am 9.11. bestätigt am Gerät: Der EXEC-Kontext ist SVC, IRQ frei, FIQ gesperrt, IRQ-Tiefe 0, Task 3, Eintrittsstack `0xC0208F60`. Beim nativen Start wandert der IRQ-Vektor von `0xC000007C` nach `0xC0001560`, das ist erwartet. Der Ablauf Sample Edit auf Slot 540 (angezeigt 541, Sample `import`, 100.000 PCM-Byte, DSP-Bereich 27.563.200 bis 27.663.200): Sechs bestätigte EXEC-Aufrufe liefen (Sample Edit öffnen, Startpunkt 0 auf 1, erstes EXIT verlässt die Feinbearbeitung). Das zweite EXIT, das die native Rücknahme auslösen soll, bekam keine EXEC-Rückkehr, das Werkzeug beendete alle Kommunikation, WRITE wurde nicht gedrückt, ein Neustart war nötig, das RAM-Prüfmuster ist ungültig. Die Ursache ist offen, ein DSP-Hänger ist nicht bewiesen.

Quelle: Messung 2026-11-09/sample-swap-pruefung

## Offene Schutzlücken

Stand der Messung 9.11., Emulator, nur dort belegt:

- Reine PCM-Änderungen ohne Metadatenänderung müssen vor der Signaturprüfung markiert werden, sonst bleibt die physische Zeile verdrängbar (`tools/emu/sample_protection_cases.py --pcm-write`, Stock und Hacktribe, am Gerät kein Datenverlust gesehen). Der gemeinsame native Schreiber beginnt bei `0xC00146B4`, ein Haken dort markiert überlappende aktive Nutzerzeilen vor dem Schreiben, die Probe besteht damit (Commit `207c3df5`).
- Gemessen im Emulator: `native_dsp_scope.py` allein prüft den Modus vor dem Erwerb der Ressource 1, nicht Bibliothek, Generation und Aufrufzuordnung nach der möglichen Wartephase (isolierter Lauf: Generation 7 auf 8, Modus 1 auf 2, Schrittsperre 1 auf 0, der native Aufruf läuft weiter). Frist und Nachprüfung liefert der [Erwerb mit Frist](#der-erwerb-von-ressource-1-mit-frist).
- Die Veröffentlichung einer neuen Aufnahme bei `0xC004F128` macht die inaktive physische Zeile 600 aktiv, ohne die Schutzrevision zu ändern: Eine vorher vorbereitete Verdrängungsprüfung lässt die Zeile zu, eine neu aufgebaute sperrt sie. Ersatzfunktionen der Probe: DSP-Endzeiger `0xC004E23C`, native Initialisierung `0xC004DF90`. Ob das später geschlossen wurde, ist hier nicht geprüft.
- Offen sind außerdem der gesamte obere RAM für jeden Besitzer und jede DMA-Lebensdauer, der vollständige Swap-Build am Gerät (dynamisches Startpattern, Namen ungeladener Samples, Slotwechsel, fortlaufende Stimmen, Karten- und DSP-Fehler), das dauerhafte Speichern nativer Sample-Änderungen und der Ersatz des Gesamtexports, der eine große Bibliothek nicht auf den DSP-Ausschnitt kürzen darf.

Quelle: Messung 2026-11-09/sample-swap-pruefung

## Randthema: Vorschau, Part holen

Entscheidung vom 02.11. zur Vorschau (Rad auf B, PART MUTE, ein Pad holt den Part nach A, siehe [Vorschau: Part reinholen](../messungen/2026-10-30-vorschau-part-reinholen.md)). Gebaut, im Emulator geprüft (Hacktribe, blau), am Gerät nichts:

- Geholte Parts bleiben über SHIFT + PART MUTE gemerkt (`V_BACK`-Logik in `tools/patch/pattern_switch.py`). Sie werden erst vergessen, wenn die Vorschau endet oder das Rad ein anderes Pattern zeigt.
- Auf der Seite von A blinken die Pads der geholten Parts, die an sind. Der erste Druck holt A seinen eigenen Part zurück, aus dem Bank-Block von A, ungemutet. Das Pad leuchtet dann fest, danach schalten die Drücke wie ohne Vorschau.
- Zurück auf B blinkt ein so zurückgegebener Part wieder wie jeder Part, der in B an und nicht geholt ist. Ein Druck holt ihn neu. Ohne Druck hin und her bleibt der Part geholt, sein Pad leuchtet fest, der Druck schaltet ihn aus.
- Beim Umschalten mit SHIFT bleibt `V_COPY` erhalten, nur `V_PEND` und `V_BACK` werden geleert (`vn_end`).

Test am Gerät, noch nicht gelaufen:

1. Pattern spielt, ein anderes am Rad ansehen, PART MUTE, ein Pad drücken (stumm oder leuchtend in B): Spielt der Part sofort mit dem Klang aus B, und bleibt das Pad an?
2. Hört man beim Kopieren einen Knacks oder eine Lücke, in diesem Part oder in anderen?
3. Zweiter Druck: stumm, dritter: wieder an.
4. EXIT: Der Part bleibt. Danach MENU auf B: B lädt, mit den Mutes der Pads.
5. Dasselbe mit Sync Group, mit einem Stereo-Sample, mit Motion im Quell-Part.
6. Blaue Electribe: dasselbe.
7. In der Vorschau SHIFT + PART MUTE: normale Farben, die Pads schalten A, nichts wird kopiert. Noch einmal: Vorschaufarbe, der erste Druck holt den Part. Rad weiter: Die Seite bleibt. EXIT, neu ansehen: wieder B.
8. 7a: Part auf B holen, SHIFT + PART MUTE: sein Pad blinkt. Druck: A spielt seinen eigenen Part wieder, das Pad leuchtet. Zurück auf B: Das Pad blinkt wieder. Ohne Druck zweimal umschalten: Das Pad leuchtet fest.
9. Ohne Vorschau hebt SHIFT + PART MUTE weiter alle Mutes auf.
10. Blinken: In der Vorschau blinken die Pads der Parts, die in B an sind, im Takt von MENU, auch nach MENU (`NEXT:`). Ein Druck: Das Pad leuchtet fest, der Part spielt. Noch ein Druck: dunkel. Die Pads der in B stummen Parts bleiben dunkel bis zum Druck.
11. Blinken: Flackert ein Pad kurz auf, wenn man ein anderes drückt? Wie sieht es mit eigenen Pad-Farben aus (nur die rote LED blinkt)?
12. Blinken: Nach EXIT, nach dem Wechsel und mit SHIFT + PART MUTE leuchten alle Pads wieder normal, keins bleibt dunkel.

Quelle: Idee 82
