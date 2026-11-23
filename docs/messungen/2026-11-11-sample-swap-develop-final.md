# Sample Swap auf der Grundlage von 1.4.5

## Hergeleitet

Die Grundlage ist der aktuelle Entwicklungsstand für 1.4.5. Sample Swap wird
darauf für 1.5 weiterentwickelt. Das Sampleformat bleibt vorerst `e2sSample.all`.
Die Zusammenführung ist keine Releasefreigabe und kein Nachweis am Gerät.

Die SysEx-Routinen für die Doom-Dateien und die Veröffentlichung hochgeladenen
EXEC-Codes bleiben beide enthalten. Der Cache-Helfer liegt im ersten
SysEx-Codeabschnitt. Der zweite Abschnitt endet vor der Preset-Tabelle bei
`0xC017C000`; seine Größenprüfung hält diese Grenze ein.

TAP Motion, Note Assistant und Dice belegen in der Grundlage mehr Code.
Der Swap-Zustand beginnt deshalb bei `0xC0188540`, seine beiden betroffenen
Codeabschnitte bei `0xC018A4E0` und `0xC0189770`. Die übrigen Aufgaben und
Adressen innerhalb eines Zustandssatzes bleiben relativ zu seiner Basis.
Alte Messungen und Testbuilds behalten ihre damaligen Adressen.

Der Blechy-Compiler hält seinen Block unterhalb `0xC0186800`. Dort beginnt
der Code für native Sample-Speicherung. Ein Überschreiten dieser Grenze wird
beim Bauen abgewiesen. Der vorhandene Block und die daraus erzeugten
Runtime-Patches ändern dadurch keine Bytes gegenüber der Grundlage.

Die Geräte-Messwerkzeuge prüfen auch die frühere MODE-Adresse `0xC0188530`.
Ein dort aktiver oder fehlerhafter Swap darf seine Puffer ebenfalls behalten.

## Gemessen im Emulator und mit erzeugten Daten

Die Speicherverträge bestehen mit 50 Prüfungen bei sieben ausgelassenen
Prüfungen. Die gezielten ARM-Prüfungen für Sample-Speicherung und SysEx
bestehen mit 27 Fällen. Die Offlineprüfungen der Geräte-Messwerkzeuge
bestehen mit 44 Fällen. Die zentrale SysEx-Guardprüfung besteht mit elf Fällen. Ihre Node-Aufrufe
bestehen zusammen mit den Emulator-Modellen mit 35 Prüfungen.
Die aktuelle Browserprüfung besteht mit 339 Fällen bei einem ausgelassenen.
Der korrigierte Hacktribe-Lauf besteht mit 177 Swap- und Startprüfungen.
Im Stock-Langlauf bleibt ein Fehler offen: Ein gewöhnlicher nativer DSP-Aufruf
außerhalb des User-Sample-Bereichs hängt an der Epoche eines unbeteiligten
Dateilesers. Bei dessen Wechsel von 328 auf 329 wird der DSP-Fehlerzustand
gelatcht, obwohl Task, Bibliotheksgeneration und Sitzung unverändert sind.
Zeitgrenze und Pollbudget sind dabei nicht erschöpft.
Die 32 bestehenden Scope-Prüfungen bestehen. Zwei gezielte Teilfälle einer
neuen Gegenprobe bestätigen die falsche Bindung sowohl nach Ressourcenerwerb
als auch während des Protokolls. Die vollständige Prüfung ist damit noch rot.

Die SysEx-Gegenprobe hält alle deklarierten Swap-Codebereiche aus ihrem
vergifteten freien Prüfraum heraus. Unerlaubte Datenzugriffe und sämtliche
Schreibzugriffe auf diese Codebereiche werden weiterhin abgefangen; zusätzlich
bleiben ihre Bytes über jede Nachricht unverändert. Der übrige freie Prüfraum
bleibt vergiftet. Ein Test mit erzeugten Codebytes prüft auch den zweiten
betroffenen Bereich.

Alle drei Runtime-Patches sind nach dem Neubau bytegleich mit der Grundlage.
Versions- und Releasedateien wurden aus der Grundlage übernommen.

Die Startvorbereitung der Swap-Fälle wartet innerhalb der bestehenden
Startfrist auf die Hauptseite und einen beobachteten Bildschirmtakt.
Eine volle Testkarte unter Hacktribe erreichte diese Bereitschaft nach
3,35 Sekunden. Eine bereits sichtbare Hauptseiten-ID und ein freier
Bibliotheksbesitz reichen dafür nicht aus. Die sieben gezielten Start-,
Journal- und Kartenfehlerfälle bestehen mit dieser Bedingung.

## Offen

Der beschriebene Fehler wurde nach Abstimmung korrigiert. Die Gegenproben
und die anschließende kombinierte Prüfung stehen in
[Native DSP-Aufträge und die Sample-Bibliothek](2026-11-12-native-dsp-bibliotheksbindung.md).
Sample-Daten und der eigene Swap-Schritt behalten ihre vollständige
Besitzprüfung; gewöhnliche Registerzugriffe behalten Task-, IRQ-, Ressourcen-
und Zeitgrenzen.

Gerätetests mit der neuen kombinierten Firmware bleiben nötig. Bisherige
Ergebnisse mit einem anderen Testbuild geben diese neue Kopie nicht frei.
Klang, vollständiger RAM- und DMA-Besitz sowie Live-Spiel werden durch
Emulator- und Speichertests nicht bestätigt.
