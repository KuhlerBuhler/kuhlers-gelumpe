# Sample-Swap: Grenzen des Verdrängungs- und Wiederherstellungsschutzes

Stand: 31.10.2026. **Gemessen mit erzeugtem ARM-Code** und eigenen Tabellen,
ohne Korg-Testdaten, Gerät, Klang oder DMA. Geprüft wurden die Schutzänderungen
aus PR 309, Stand `86707e2`. Der ausführbare Schutzcode entspricht `a661ea5`;
der letzte Commit aktualisiert nur `verified.json`. Der Vergleich beginnt
nach dem darin enthaltenen Develop-Merge bei `be6918a`.

Ergänzung zur Schutzuntersuchung in PR 309 und zum
[gemeinsamen Dateibesitz](2026-10-31-sample-dateibesitz.md).
Die Schutzänderungen und der neue Dateibesitz liegen noch auf getrennten
Entwicklungsständen. Es wurde nichts zusammengeführt oder auf ein Gerät gespielt.

## Ergebnis

Der Gesamtexport-Schutz ist sinnvoll: Bei aktivem oder fehlerhaftem Swap wird
das überschreibende Öffnen verweigert, bevor die große Sammlung verändert wird.
Die beiden neuen Sperren gegen Datenverlust sind jedoch noch unvollständig.
Es bestehen drei hohe und ein mittlerer Befund im Schutzcode. Ein weiterer
mittlerer Befund betrifft erst dessen Verbindung mit dem neuen Schreibweg.

## Gemessen: Wiedergabepunkte fehlen im Verdrängungsschutz

`slot_sig` in `tools/patch/sample_swap.py`, Zeilen 1518 bis 1539 des geprüften
Stands, erfasst die Metadatenzeile und den Namen. Die getrennte 16-Byte-Zeile
in `PLAYBACK` fehlt. Native Start- und Loop-Bearbeitungen ändern zunächst
diese Tabelle, wie die [nativen Speichergrenzen](2026-10-30-sample-speichergrenzen.md)
belegen.

Eine eigene erzeugte Belegung verwendet den logischen und physischen Slot
600. Dann wird `PLAYBACK + 600 * 16 + 4` verändert:

| Ergebnis | vorher | nachher |
|---|---:|---:|
| Signatur | 1762925391 | 1762925391 |
| `slot_clean(600)` | 1 | 1 |
| `victim()` | 600 | 600 |

**Hergeleitet, hoch:** Eine solche Bearbeitung kann weiterhin verdrängt werden.
Der bestehende Modellfall `ChangedRows` verändert stattdessen `META + 0x30`
und deckt diese echte Schreibstelle nicht ab. Der Schutz muss den tatsächlichen
Wiedergabezustand oder eine ausdrückliche Änderungsmarke berücksichtigen.

## Gemessen: sauberer Alias schützt den veränderten Alias nicht

Die Slots 600 und 601 werden auf dieselbe physische Zeile 600 abgebildet und
zunächst sauber markiert. Danach ändert sich nur der Name von Slot 601.

| Ergebnis | nach der Namensänderung |
|---|---:|
| `slot_clean(600)` | 1 |
| `slot_clean(601)` | 0 |
| `can_evict(600)` | 1 |
| `victim()` | 600 |

`can_evict`, Zeilen 853 bis 857, prüft nur die Signatur des gewählten
logischen Kandidaten. **Hergeleitet, hoch:** Der saubere Alias erlaubt die
Freigabe der gemeinsamen physischen Belegung, obwohl ein anderer Alias
ungesicherte Änderungen hat. Der Schutz muss alle betroffenen Aliase auf
derselben physischen Zeile berücksichtigen.

## Gemessen: Kartenfehler können als harmlos abgelehntes Journal gelten

Die neue Rückgabe 3 unterscheidet Fehler beim Öffnen des Journals von einer
Ablehnung ohne Schreiben. Fehler beim Lesen und Schließen des Journals sowie
beim Prüfen der Bibliothek oder ihrer angehängten PCM liefern dagegen weiterhin
1. `ss_fopen`, Zeilen 367 bis 369, akzeptiert diesen Wert und lädt die Sammlung.

Gegenprobe mit einem gültigen erzeugten Journal und einem Lesefehler beim
Prüfen der angehängten PCM:

| Ergebnis | Wert |
|---|---|
| `store_recover` | 1 |
| Schreibzugriffe der Wiederherstellung | keine |
| Journal bleibt erhalten | ja |
| nachfolgendes `ss_fopen` mit diesem Ergebnis | 0, Erfolg |
| Swap-Modus danach | 1 |

Ein Fehler beim Schließen des Journals liefert ebenfalls 1.
**Hergeleitet, hoch:** Kein Schreibzugriff in diesem Aufruf beweist keinen
gesunden Index. Eine frühere unterbrochene Transaktion kann ihn bereits
verändert haben. Lese- und Schließfehler müssen den Kartenstand ungeklärt
lassen. Der Schreibweg darf deshalb seine bisherige Ablehnung solcher
Ergebnisse nicht lockern.

## Gemessen: Timeout-Gate vor wartendem Sperrerwerb

`native_dsp_scope.py`, Zeilen 319 bis 324, prüft `MODE` und `INSTEP`, bevor es
die möglicherweise wartende native DSP-Sperre erwirbt. Danach wird das Gate
nicht erneut geprüft.

Im erzeugten ARM-Modell wird das Gate während des Sperrerwerbs von 1 auf 0
gesetzt. Beim Eintritt in den begrenzten Aufruf ist es bereits null. Trotzdem
endet dieser Aufruf mit `FAULT=1`, `MODE=2`, `GEN=8` und ohne erfolgreichen
Abschluss. **Hergeleitet, mittel:** Ein währenddessen beendeter Swap kann einem
anderen wartenden Aufruf noch einen falschen DSP-Fehler hinterlassen.

Das Gate muss nach dem Erwerb zur tatsächlich besitzenden Ausführung passen.
Ein globales Aktivitätswort belegt noch nicht die Identität des aufrufenden
Tasks.

**Offen:** Normale native Import-, Aufnahme-, Export- und EXEC-Aufrufe warten
außerhalb des Swap-Schritts durch diese Änderung absichtlich wieder ohne
Frist. Der ursprüngliche gelegentliche EXEC-Hänger ist damit nicht allgemein
behoben. Die passende Frist braucht weiter eine Geräteprüfung.

## Gemessen: zusätzliche Grenze beim späteren Importanschluss

Der Schutzcode und die neuen Funktionen `catalogue_begin/end` lassen sich in
einem eigenen Modell gemeinsam assemblieren. Der Store-Code belegt dabei
7252 von 8192 Byte; 940 Byte bleiben frei. `CODE3` ist bereits vollständig
belegt. Die neue Signaturtabelle nimmt dem bestehenden Cache 4 KiB ab; eine
zusätzliche Überschneidung mit dem Dateibesitzer entstand dabei nicht.

`finish_pins` zeichnet jedoch nur bei `MODE=1` auf. Eine zunächst kleine
Bibliothek lädt bei `MODE=0` ohne diese Marken. Wächst sie durch den neuen
Schreibweg über die Grenze, aktiviert `catalogue_end` den Swap. Die alten
geladenen Zeilen behalten dann Signatur null und sind nicht verdrängbar.
Dies wurde mit kombiniertem erzeugtem ARM-Code reproduziert.

**Hergeleitet, mittel:** Vor dem Importanschluss müssen geprüfte native
Ladevorgänge auch bei kleinen Sammlungen eine Versionszuordnung erhalten.
Ein pauschales sauberes Markieren nach jedem Schreibauftrag wäre falsch:
Es würde andere ungesicherte DSP-Änderungen nachträglich als gesichert behandeln.
Dieser Befund betrifft eine noch nicht angeschlossene Funktion, keinen
bereits vorhandenen Menüablauf in PR 309.

## Umfang der Prüfungen

```sh
PYTHONPATH=tools/patch tools/emu/.venv/bin/python -m unittest \
  test_sample_swap.ChangedRows test_sample_swap.ExportAll \
  test_sample_swap.NativeGate test_sample_store.Recovery
```

13 vorhandene Modellfälle bestehen. Die oben beschriebenen Gegenproben
zeigen zusätzliche fehlende Fälle; grüne vorhandene Tests widerlegen diese
Befunde nicht. Es wurde kein neuer vollständiger Unit-, Browser- oder nativer
Firmware-Prüflauf durchgeführt, weil in dieser Prüfung kein Laufzeitcode
verändert wurde. Die aktualisierte `verified.json` ersetzt die fehlenden
Regressionen ebenfalls nicht.

## Nächster Funktionsschritt

1. Die vier Schutzlücken mit passenden Regressionen schließen und den
   Export-Schutz beibehalten.
2. Schutzcode und Dateibesitz zusammenführen, den Patch für beide roten
   Builds neu erzeugen und die erforderlichen Prüfungen ausführen.
3. Einen Wiedergabeprototyp mit vorhandener Sammlung über 25 MiB prüfen:
   dynamisches Startpattern, OSC-Auswahl ungeladener Samples, Nachbarpattern,
   Chain, Wiederholung bei Ladeverzug, Stimmenausklang und unveränderte Datei.
4. Danach den dauerhaften Import vollständig anschließen, mit sicherer
   physischer Versionszuordnung, Alias-Schutz, Quellhandle und Neustart.
   Erstimport ohne vorhandene Datei und die übrigen bestätigten Änderungen
   folgen auf demselben Schreibweg.

Der Wiedergabeprototyp ist eine begrenzte Funktionsprobe. Dauerhafter Import,
Sample-WRITE, Löschen und bestätigte Aufnahmen bleiben Anforderungen für 1.4.
Projektcontainer, echter DMA-Nachweis und Gerätetests werden dadurch nicht
als erledigt behandelt.
