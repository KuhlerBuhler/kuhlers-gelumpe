# Sample-RAM: Geräteprobe verweigert bei aktiver MMU und Datencache

Stand: 06.11.2026. Gemessen auf der roten Electribe 2 Sampler mit Korg 2.02,
Hacktribe und dem minimalen Messbuild mit ausschließlich BLECH SysEx.
Die [Vorprüfung und Kartenkorrektur](2026-11-06-sample-ram-vorpruefung.md)
gehen dieser Sitzung voraus. Die Testkarte enthält erzeugte Samples.
Es gibt keinen Nachweis freier RAM-Flächen aus dieser Probe.

## Gemessen: Messbuild läuft und Kontext passt

Nach dem bestätigten Neustart stimmen die sieben Vergleichsbereiche mit
dem eigenen minimalen Hacktribe-Messbuild überein. Die zuvor gefundenen
Doom- und Plugin-Codebereiche entsprechen wieder dem Original.
Der Bibliothekslader trägt keinen Swap-Haken. Der Bildschirmwert ist 1,
das Fensterfeld 0 und der Transportzustand 0. Es besteht keine weitere
ALSA-Verbindung zum Geräteport. Acht übertragene Quelldateien der Probe
stimmen nach SHA-256 mit den lokal geprüften Dateien überein.

## Gemessen: bestätigter Abbruch vor dem oberen RAM

Der erste Füllaufruf gibt einen bestätigten Abschluss mit verweigertem
CPU-/Kontextstatus zurück. Die Schleife für den oberen RAM läuft nicht an.
Es gibt keinen EXEC-Timeout. Der erste Bericht speichert den konkreten
Status und das Steuerregister noch nicht und meldet `scratch_restored=false`.

Die Auswertung des Werkzeugs zeigt zwei Fehler im Bericht: Die
Wiederherstellung erfolgt bei bestätigter Verweigerung im Abschlussblock,
das Berichtsflag wird aber erst nach einer vollständig erfolgreichen
Messung gesetzt. Außerdem fehlt die Ergebniszeile bei einer Verweigerung.
Diese Fehler werden mit zwei zunächst fehlschlagenden synthetischen Tests
nachgestellt und korrigiert. Der erste Bericht bleibt unverändert erhalten.

Ein anschließender begrenzter Prüfaufruf verwendet dieselbe ARM-Prüfung,
ohne das Füllen zu wiederholen. Er liefert:

| Wert | Ergebnis |
|---|---|
| Status | 1, CPU-Steuerzustand verweigert |
| CP15 c1 | `0x0005107D` |
| Bit 0 | 1, MMU aktiv |
| Bit 2 | 1, Datencache aktiv |
| Oberer RAM | vor dem ersten Zugriff abgebrochen |
| Scratch-RAM | vollständig zurückgeschrieben, CRC-geprüft |

Die Bedeutung von Bit 0 und Bit 2 steht im
[ARM926EJ-S-Handbuch, Abschnitt 2.3.2, Tabelle 2-11](https://documentation-service.arm.com/static/5e8e3d1088295d1e18d3a9b2).
Der Prüfaufruf verändert weder MMU noch Cache-Konfiguration. Die Probe
fordert keine Karten-, DSP- oder Flash-Schreiboperation an. Nur der
vorübergehende Code-, Ergebnis- und Tabellenbereich im bereits erlaubten
ersten KiB des Arbeitspuffers wird hochgeladen und wiederhergestellt.

## Hergeleitet: die bisherigen Canaries sind noch kein Gerätebeleg

Bei aktiver MMU muss die Abbildung der virtuellen Testadressen auf physische
Adressen bekannt sein. Ein aktiver Datencache allein verrät noch nicht,
ob gerade diese Seiten cachebar sind. Ohne Seitenattribute und passende
Kohärenzbehandlung könnten gelesene Werte aus dem Cache stammen, während
DMA den tatsächlichen RAM verändert hat. Die Schutzprüfung einfach zu
entfernen würde daher keinen belastbaren Freigabenachweis liefern.

Im eigenen Original enthalten die Instruktionsfolgen bei `0xC00016EC`
das Setzen der Übersetzungstabelle, bei `0xC000170C`, `0xC0001714` und
`0xC000171C` Cacheoperationen nach Adresse und bei `0xC0001724` das Leeren
des Schreibpuffers. Das sind statisch gelesene Instruktionen. Aufrufer,
Laufzeitadressen und sichere Verwendung dieser Routinen sind hier nicht
nachgewiesen; sie werden am Gerät nicht aufgerufen.

## Gemessen im Modell

Alle 15 synthetischen Tests der Probe bestehen. Die neuen Gegenproben
verlangen eine Statuszeile auch bei verweigertem Zugriff und ein korrektes
Wiederherstellungsflag nach erfolgreichem Abschluss des Zurückschreibens.
Die Protokollprobe mit 225 Seiten, einem absichtlich geänderten letzten
Wort und Scratch-Wiederherstellung besteht erneut auf beiden minimalen
Emulator-Builds. MMU und Cache werden in diesen Modellen nicht tatsächlich
nachgebildet. Die früheren vollständigen Unit- und Browserläufe gehören
zum vorherigen Prüfstand; nach der Diagnoseänderung wurden die gezielten
Proben wiederholt.

## Offen und nächster Messaufbau

Zuerst sind TTBR, Domainsteuerung und gegebenenfalls die FCSE-Verschiebung
sowie die Übersetzungseinträge für den oberen Bereich rein lesend zu
erfassen. Physische Ziele und Cache-/Pufferattribute müssen bekannt sein.
Erst dann lässt sich eine Probe über eine belegte ungecachte Abbildung
oder mit begrenzter Cachepflege entwerfen und prüfen. Globale MMU- oder
Cache-Umschaltungen sind kein Bestandteil des vorbereiteten Versuchs.

Die Modusfolge mit Sampling, Resampling, Import, Export und USB hat noch
nicht begonnen. Die RAM-/DMA-Freigabe und damit die Gerätefreigabe des
neuen Swap-Caches bleiben offen. Der Abbruch widerlegt die Swap-Idee nicht;
er zeigt eine notwendige Ergänzung des Messaufbaus.
