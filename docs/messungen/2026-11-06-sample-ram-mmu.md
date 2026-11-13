# Sample-RAM: CPU-Register und Speicherabbildung

Stand: 06.11.2026. Rote Electribe 2 Sampler, Korg 2.02 mit Hacktribe,
minimaler Messbuild mit ausschließlich BLECH SysEx. Eigene Testkarte mit
erzeugten Samples. Voraus ging die [verweigerte RAM-Probe](2026-11-06-sample-ram-cache.md).

## Gemessen

Ein bestätigter Diagnoseaufruf liest CPU-Register, ohne MMU- oder
Cache-Einstellungen zu ändern. Der Arbeitsbereich wird danach vollständig
zurückgeschrieben und geprüft.

| Register | Wert |
|---|---|
| CPU-ID | `0x41069265` |
| Steuerregister c1 | `0x0005107D` |
| Translation Table Base c2 | `0x8001C000` |
| Domain Access Control c3 | `0x00000003` |
| FCSE c13 | `0x00000000` |
| Cache Type | `0x1D152152` |
| DTCM Region | `0x0000001C` |
| ITCM Region | `0x0000001C` |

MMU, Daten- und Befehlscache sind eingeschaltet. Die Domäne 0 hat
Managerrechte. Aus den TCM-Rohwerten wird keine Speicherfreigabe abgeleitet.

Der Bootloader-Ausschnitt `0x5000..0x6000` wurde zweimal rein lesend erfasst.
Die beiden Inhalte stimmen überein. Die Tabellenroutine beginnt bei `0x51D8`.
Rohdaten bleiben außerhalb des Repos.

Ein weiterer Versuch liest die erste 16-KiB-Tabelle aus dem SRAM in 74
bestätigten Teilaufrufen. Vor dem ersten Aufruf des zweiten Durchgangs
weicht der hochgeladene Diagnosecode an der Spiegeladresse `0xC5000000` ab.
Diese Adresse ist im Bootloader-Modell ungecachet abgebildet.
Die Vorprüfung verweigert EXEC. Es folgen weder Wiederholung noch weitere
Aufrufe oder Wiederherstellung des Arbeitsbereichs. Ein Neustart ist nötig.
Die erste Tabelle wurde noch nicht als separater Rohdatensatz gesichert;
ein Vergleich beider Tabellen und eine Bestätigung ihrer Einträge fehlen.
Es gab keine Schreibprobe im oberen RAM und keinen DSP-Zugriff.

## Gemessen nach dem Upload-Fix

Nach Installation und vollständigem Neustart des neuen minimalen
Hacktribe-Messbuilds stimmen alle fünf SysEx-Patchbereiche sowie die sieben
Original-Vergleichsbereiche. Der Bildschirmwert ist 1, das Fensterfeld 0
und der Transportzustand 0. Es besteht keine weitere Verbindung zum
MIDI-Port. Neun verwendete Quelldateien stimmen lokal und auf dem
Messrechner mit dem zuvor geprüften Stand überein.

Die Diagnose beendet alle 150 Aufrufe bestätigt: CPU-Register vorher,
zweimal 74 Teile der 16-KiB-Tabelle und CPU-Register danach. Beide
vollständigen Tabellen stimmen überein. Auch die CPU-Register bleiben
unverändert. Jeder Codeupload besteht den Vergleich über die
Spiegeladresse vor EXEC. Es gibt keinen Timeout und keine Wiederholung.
Der Arbeitsbereich wird nach den bestätigten Abschnitten zurückgeschrieben
und geprüft; der Abschluss meldet `scratch_restored=true`.

Die gelesenen Einträge ergeben für die 25 betroffenen Sections:

| Virtueller Bereich | Physisches Ziel | Attribute |
|---|---|---|
| `0xC274F000..0xC4000000` | identisch | Write-back, gepuffert, Domäne 0, Manager |
| `0xC674F000..0xC8000000` | Adresse minus `0x04000000` | ungecachet, ungepuffert, Domäne 0, Manager |

Der eigene Tabelleneintrag für den SRAM passt zu `TTBR = 0x8001C000`.
Der Spiegel zeigt laut gelesener Tabelle auf dieselben physischen Ziele
wie der obere RAM-Bereich. Die vorher nur aus dem Bootloader-Modell
abgeleiteten Attribute stimmen damit mit den gelesenen Einträgen überein.

Geschrieben wird nur der bestehende erste KiB des Diagnosearbeitsbereichs.
Kein Schreiben in den oberen RAM, DSP, Karte oder Flash und keine Änderung
von MMU-, Cache- oder Domänenkonfiguration gehört zu diesem Lauf.

## Hergeleitet

Die gelesene Bootloader-Routine wurde außerhalb des Repos im Emulator
ausgeführt. Ihr Tabellenmodell ergibt:

| Virtueller Bereich | Physisches Ziel | Cache-/Pufferattribute |
|---|---|---|
| `0xC0000000..0xC4000000` | identisch | Write-back, gepuffert |
| `0xC4000000..0xC8000000` | Adresse minus `0x04000000` | ungecachet, ungepuffert |
| `0x80000000..0x80100000` | identisch | Write-back, gepuffert |

Grenzangaben rechts sind jeweils exklusiv. Der Tabellenbeginn `0x8001C000`
liegt damit im SRAM. Die frühere Annahme einer ausgeschalteten MMU war
unvollständig, weil sie nur das Firmwareabbild berücksichtigte.

Das Modell erklärt einen ungecacheten Spiegel des Diagnosearbeitsbereichs
bei `0xC5000000`. Die getrennte Sichtprüfung erkennt einen Upload, dessen
gecachtes Zurücklesen erfolgreich ist, während der RAM noch andere Bytes
enthält. Der [begrenzte Upload-Fix](2026-11-06-exec-upload-cache.md) setzt
an diesem Schreibpfad an.

Die Registerauslegung folgt dem [ARM926EJ-S Technical Reference Manual](https://documentation-service.arm.com/static/5e8e3d1088295d1e18d3a9b2),
Abschnitte zum System Control Coprocessor und zur MMU.

## Offen

Das Bootloader-Modell bestätigt keine aktiven TLB-Einträge. Die Diagnose
kennzeichnet Tabellen daher als Kandidaten. CP15-Werte und Spiegelung
werden im Emulator eingespeist; eine echte MMU oder ein echter Datencache
werden damit nicht nachgebildet.

Die bestätigten Tabellenlesungen ersetzen keine Prüfung der aktiven
TLB-Einträge oder des RAM-Besitzes. Die bisherige Füllprobe verweigert bei
eingeschalteter MMU und eingeschaltetem Datencache weiterhin. Eine neue
Probe muss beide Cache-Sichten berücksichtigen, damit schmutzige
Cachezeilen weder Änderungen verdecken noch alte Inhalte zurückschreiben.
Die Modusfolge mit Sampling, Resampling, Import, Export und USB steht
noch aus. Weder CPU- noch DMA-Besitz des oberen Bereichs sind vollständig
geklärt; ein freier Swap-Cache ist damit noch nicht nachgewiesen.
