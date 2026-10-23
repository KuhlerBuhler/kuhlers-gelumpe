# BLECH: neue Vergleichsbasis nach dem Abgleich mit develop

Stand 21.10.2026. **Im Emulator gemessen.** Diese Basis enthält die bereits in
develop integrierten Optimierungen für Pad-Geometrie, Plugin-Prüfung und native
Multiplikation. Hier wird kein weiterer Geschwindigkeitsgewinn beansprucht.
Die [ältere Ausgangsmessung](2026-10-20-patch-effizienz-ausgang.md) bleibt ein
Nachweis ihres damaligen Stands und wird nicht mit diesen Profilen vermischt.

Die Firmwarequellen stammen aus `21cf0ceaada9ff6410c48b85022ad98c8bc8b939`,
nach dem Rebase auf develop `23461a04c9a26ef4366e6d5355d579dfb9e195ca`.
Generatoren und Laufzeitmanifeste entsprechen diesem develop-Stand.
Das an die aktuellen Plugin-Eingänge angepasste Messwerkzeug gehört zu
`25ab506187bec43a83ac0a97102725956910356f`. Es verändert keine Firmwarefunktion.

## Vollständige Prüfung und Platz

[check_sets.mjs](../../tools/patch/check_sets.mjs) erzeugt jeden vollständigen
Satz aus dem nach SHA-256 geprüften Original und führt `check.py` ohne
Kurzprüfung und ohne Ergebniscache aus. Alle erforderlichen Gruppen sind
abgeschlossen; die überwachten Quellen sind unverändert.

| Build | Prüfungen | Patches | Code und Daten, KiB | Reserviertes RAM, KiB | Frei, KiB | Größte Lücke, KiB |
|---|---:|---:|---:|---:|---:|---:|
| Hacktribe | 443/443 | 17 | 82,31 | 440,87 | 36,39 | 7,06 |
| Korg rot | 468/468 | 18 | 82,51 | 440,87 | 36,18 | 7,06 |
| Synth | 347/347 | 12 | 65,36 | 388,71 | 435,93 | 322,26 |

Ein KiB sind 1024 Byte. Die Reservierungen betreffen zusätzliche Patchbereiche
in den am Original bestätigten freien FF-Flächen. Sie beschreiben weder den
gesamten Arbeitsspeicher des Geräts noch dessen laufende Speicherauslastung.
Die exakten Werte, Eingangs- und Ausgabehashes stehen in der
[Messdatei](2026-10-21-patch-effizienz-basis-zahlen.json).
Originale, erzeugte Firmware und vollständige private Profile liegen außerhalb
des Repositorys.

## Gleiche Eingaben für spätere Vergleiche

[patch_performance.py](../../tools/emu/patch_performance.py) verwendet Profilformat 4.
Je Build starten Original und BLECH jeweils dreimal in unabhängigen Prozessen.
Vier Szenen des Originals und zehn von BLECH ergeben 18 Starts und 126 Messfenster.
Die normalen Szenen laufen jeweils zwei Sekunden simulierte Gerätezeit.

Die drei Apps Mandelbrot, Life und Pong erhalten je acht vollständig
abgeschlossene Vorlaufbilder und danach 50 Messbilder. Insgesamt sind das
1350 gemessene App-Bilder und 216 Vorlaufbilder. Für Life und Pong wird der
Zeitinput beim nativen millis-Aufruf im Vorlauf fest vorgegeben, damit die
Zufallseingaben beim verzögerten Öffnen gleich bleiben. Die native Funktion
wird dabei weiter ausgeführt. Nach dem Vorlauf entfällt dieser Eingriff.

Der feste App-Satz nutzt die acht Benutzerplätze. Die tatsächliche Registrierung
wird im nativen Speicher geprüft. Die Hintergrundszene ergänzt Lauflicht und
Pulsieren. Der native Lader prüft alle elf aktuellen Presets einzeln, auch den
GIF Player, der nicht zusätzlich in die volle App-Tabelle geladen wird.
Die Reihenfolge und Namen stehen in der Messdatei.

Alle drei Wiederholungen liefern identische Befehlszahlen, App-Zustände und
Bildpuffer. Die zusätzlichen drei Laderwiederholungen pro Build sind ebenfalls
gleich. Der strenge Selbstvergleich besteht auf allen drei Builds mit dem
Verhältnis 1,000 in allen 30 BLECH-Szenen. Alte Format-2-Profile werden abgelehnt.

Gezählt werden ausgeführte ARM-Instruktionen. Diese Zahlen sind keine CPU-Zyklen,
keine gemessenen Millisekunden am Gerät und kein Nachweis für schnelleren
Sample-Import oder Export. Geräteabnahme und Audiolatenzmessung bleiben offen.

## Verwendung

Künftige Decoder- und Pufferänderungen werden gegen diese geprüften Eingänge,
Quellen, Plugins und Szenen verglichen. Erst identische Ergebnisse erlauben,
eine kleinere Befehlszahl oder weniger belegten Platz als Verbesserung zu werten.
Die Werkzeugtests prüfen unter anderem die Kapazitätsgrenze, fehlende, doppelte
und unbekannte Plugin-Namen sowie das Zählen an vollständig abgeschlossenen
Bildern. Alle 17 gezielten Werkzeugprüfungen bestehen.

Nach der Werkzeuganpassung bestehen außerdem 959 Unit-Tests und
164 Browsertests, jeweils ohne Fehler. Die 143 vorgesehenen Auslassungen
der Unit-Suite und die 1 Auslassung der Browser-Suite bleiben ausgewiesen.
