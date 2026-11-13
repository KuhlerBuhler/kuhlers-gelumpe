# EXEC: Hochgeladenen Code vor der Bestätigung in den RAM schreiben

Stand: 06.11.2026. Der Fix betrifft BLECH SysEx, noch keinen freigegebenen
Sample-Swap. Ausgangspunkt ist die [MMU-Diagnose](2026-11-06-sample-ram-mmu.md).

## Gemessen

Am Gerät wich die Sicht über die Spiegeladresse `0xC5000000` von den
übertragenen und gecacht zurückgelesenen Bytes ab. Der Bootloader legt
diesen Spiegel im Modell ungecachet an; die aktiven TLB-Einträge sind noch
nicht geprüft. Die Vorprüfung stoppte
vor EXEC. Der betroffene Arbeitsbereich wurde anschließend nicht
zurückgeschrieben; vor weiteren Aufrufen ist ein Neustart erforderlich.

Im Modell mit erzeugten Daten scheitert der alte Schreibpfad an genau
dieser Sichtprüfung. CRC und Antwort über die gecachte Sicht allein
bestätigen keine Veröffentlichung im RAM.

## Hergeleitet und umgesetzt

WRITE DATA kopiert erfolgreiche RAM-Uploads und berechnet danach die CRC.
Für Ziele vollständig innerhalb `0xC1000000..0xC1000400` liegt dazwischen
eine begrenzte Cachepflege:

1. Länge, Zielanfang, Zielende und Adressüberlauf prüfen.
2. Bei eingeschalteter MMU und eingeschaltetem Datencache die betroffenen
   32-Byte-Zeilen per Clean-by-MVA zurückschreiben.
3. Den Schreibpuffer leeren, dann CRC und Antwort erzeugen.

Jede gereinigte Zeile liegt vollständig im bereits freigegebenen ersten
KiB des EXEC-Arbeitsbereichs. Das gilt auch für ungerade Teiluploads und
das letzte Byte. Andere RAM-Ziele, Dateischreibpfade und verweigerte
Uploads führen keine solche Cachepflege aus. MMU-, Cache- und
Domänenkonfiguration bleiben unverändert. Es gibt keine neue
Flash-Schreibfunktion.

Die Wartungsbefehle und die 32-Byte-Zeilengröße folgen dem
[ARM926EJ-S Technical Reference Manual](https://documentation-service.arm.com/static/5e8e3d1088295d1e18d3a9b2),
Abschnitt Cache Operations. Der bestehende EXEC-Pfad leert zusätzlich
Schreibpuffer und Befehlscache vor dem Sprung.

## Prüfung und Grenzen

Die synthetischen SysEx-Tests prüfen vollständige und ungerade Uploads,
Zeilengrenzen, ausgeschaltete Cache-/MMU-Bits und ausgeschlossene Ziele.
Das Diagnosemodell trennt gecachte Schreibsicht und ungecacheten Spiegel;
erst Clean und Drain veröffentlichen dort die Bytes. Die defekte alte
Firmware stoppt vor EXEC. Fehlerfälle unterbrechen den Ablauf ohne
weitere Aufrufe bei unbestätigtem Abschluss.

Alle acht Diagnosefälle bestehen auf Stock und Hacktribe mit diesem
Cachemodell. Der SRAM-Fall umfasst 150 bestätigte Aufrufe einschließlich
beider vollständigen Tabellenlesungen. Nach erfolgreichem Abschluss
stimmen gecachter Arbeitsbereich und RAM-Spiegel wieder mit der Sicherung
überein. Auch ein später unbestätigter Abschluss und unterdrückte
Veröffentlichung werden gezielt geprüft.

`npm test` besteht mit 1370 bestandenen und 161 ausgelassenen Tests,
ohne Fehler. `npm run test:e2e` besteht mit 285 bestandenen und einem
ausgelassenen Test, ohne Fehler. Die Dokumentprüfung besteht ebenfalls. Die ausgelassenen
Prüfungen ersetzen keine Prüfung der eigenen Firmwareabbilder.

Die minimalen Messbuilds bestehen nur aus eigenen Originalen und dem
SysEx-Patch. `tools/emu/check.py --cases sysex_cases` besteht für Stock
und Hacktribe mit je 92, für Synth mit 75 Prüfpunkten. Start, Rettungswege
und SysEx sind dabei eingeschlossen. Firmware, Kartendaten und ausführliche Prüfprotokolle bleiben
außerhalb des Repos. Die Release-Verifikation der geänderten Patchdateien
ist erneut erforderlich.

## Gemessen am Gerät nach Installation

Der korrigierte minimale Hacktribe-Messbuild ist installiert und nach dem
Neustart anhand aller fünf SysEx-Patchbereiche rein lesend bestätigt.
Die [CPU-/Tabellendiagnose](2026-11-06-sample-ram-mmu.md) beendet 150
Aufrufe einschließlich zweier identischer vollständiger Tabellenlesungen
ohne Timeout oder Sichtbarkeitsabbruch. Alle Codeuploads bestehen den
Vergleich über den Spiegel vor EXEC. Der Arbeitsbereich ist danach
zurückgeschrieben und geprüft.

Das ist ein erfolgreicher Gerätelauf des begrenzten Upload-Fixes, noch
keine Freigabe beliebiger EXEC-Aufrufe oder einer freien RAM-Fläche.
Frühere DSP- oder EXEC-Hänger haben dadurch noch keine gemeinsame
bestätigte Ursache. Die cachebewusste RAM-Probe über die Betriebsarten
steht weiterhin aus. Der Sample-Swap bleibt bis zu diesen Prüfungen
unfreigegeben. Korg 2.02 ohne Hacktribe bleibt ebenso ein unterstütztes
Ziel; dieser echte Gerätelauf betrifft Hacktribe.
