# Original-Doom als alternativer Start: Machbarkeit

**Historischer Befund vor der Integration von `integ/overnight`.** Die hier
genannten BLECH-v8-Artefakte und alten Speicheradressen sind kein aktueller
Gerätekandidat. Neue Firmware muss separat gebaut und geprüft werden.

Stand: 15.10.2026, Branch `feature/doom-start`. Kein Gerätezugriff.
Die Prüfergebnisse beziehen sich auf lokale ARM- und Firmwareemulatoren.
Es gibt noch keine Doom-Gerätedatei und keinen vollständigen gemeinsamen
Engine-/Firmwarelauf.

## Ergebnis

Gemessen: Die originale Doom-Engine läuft als ARM926-Programm. Ein
separater nativer Startversuch betreibt SD, Display und Panel mit den
Firmwaretreibern, ohne die Sampleranwendung zu starten. Damit sind die
wesentlichen technischen Voraussetzungen einzeln belegt. Eine native
Doom-Anwendung im vorgeschlagenen Startmodus ist hergeleitet machbar.
Das ist noch keine Freigabe oder Leistungszusage für das Gerät.

## Engine

Gemessen: `doomgeneric` Commit
`e257a09527062bfb986b6e5e0780839b6cbd5b71`, ARMv5TEJ, EABI5, Softfloat,
ohne undefinierte Symbole. Die Enginequellen bleiben unverändert und liegen
außerhalb des Repos. Newlib und eigene Systemadapter sind eingebunden.
Getestete Spieldaten sind Freedoom 0.13.0, keine kommerzielle Doom-WAD.

E1M1 läuft bis Spieltick 46 und erzeugt 120 Ausgaben einschließlich des
anfänglichen schwarzen Übergangs. Die rechte Richtungstaste ändert den
tatsächlichen Blickwinkel und das gerenderte Bild. Zusätzlich zum
Standardlauf ohne Gegner besteht ein Lauf mit aktivierten Gegnern und
Eingabe. Alle bisherigen Läufe sind ohne Ton. Ein vollständiger Kampf und
andere Level sind dadurch nicht belegt.

Hergeleitete Zielreserve: 8 MiB für Engine, getesteten Heap und einen
eigenen 64 KiB Stack. Im Lauf mit Gegnern werden 6646320 Byte Heap und
1256 Byte Stack-Hochwasser beobachtet; Code, Daten und BSS ergeben
689612 Byte. Mit der vorgeschlagenen Stackreserve sind das 7401468 Byte.
Treiber kommen hinzu. Diese Rechnung gibt keine Geräteadresse frei und
beweist nicht das Maximum für andere Karten.

Die Engine zeichnet weiterhin intern 320 mal 200 Pixel. Der eigene
Ausgabeadapter rechnet auf 128 mal 64 Pixel mit einem Bit je Pixel um.
Dateizugriff, Zeit und Eingabe dieser Engineprobe sind Testadapter.
Unicorn-Wandzeit wird nicht als Hardwarebildrate ausgegeben.

Details und Reproduktion:
`docs/messungen/2026-10-15-doom-engine-build.md`, [Buildanleitung](../../tools/doom/README.md).

## Nativer Treiberstart im Firmwareemulator

Gemessen mit eigener ARM-Diagnose, 469 Byte einschließlich Literalen und
Pfaden. Eine temporäre Änderung im Emulator ersetzt den Aufruf bei
`0xC002ADB0`. Der Originalaufruf `0xC002A35C` bleibt ausgeführt. Danach
wählt exakt SHIFT + TAP, ohne weitere gehaltene Taste und ohne aktiven
Start-/Panelupdatemodus, den Diagnosezweig. Der Normalzweig erhält Register,
Flags und die ursprüngliche Fortsetzung.

Der vorhandene Bootloader und die frühen Rettungsentscheidungen sind
unverändert. Es wird weiterhin das ganze BLECH-Abbild geladen; Doom wäre
eine alternative Anwendung innerhalb dieses Starts.

Gemessen im ausgewählten Zweig:

- Ausschließlich StartupTask 1 und SDCardDriverTask 8 betreten.
- Keine Periodic-, CentralService-, UI-, Command-, Voice- oder SeqTask betreten.
- Keine beobachteten Globals-, Patternbank- oder Samplelader-Einstiege.
- Kein Bildschirmmanager angelegt, keine Assertion.
- FatFs registriert und mountet die virtuelle SD-Karte; Öffnen, Lesen von
  1024 Byte und Schließen liefern Erfolg. Die Daten stimmen Byte für Byte.
- Der echte Firmware-SPI-LCD-Weg sendet dieselben 1024 Byte ans LCD-Modell.
- Eine TAP-Nachricht wird über UART und die echte Panel-Empfangsqueue gelesen.

Die Dateiaufrufe werden nicht durch Python ersetzt. Die Karte ist ein
schreibgeschütztes virtuelles Medium. Der Test besitzt weder MIDI-Zugriff
auf ein Gerät noch einen Pfad zum Flashen.

Aus Code gelesen und durch den Versuch gestützt: `0xC0025754(1)` startet
den benötigten Systemtakt ohne die Sampler-Rückrufe. Danach wird nur
Task 8 aktiviert. `0xC003FD20` registriert den SD-Diskdienst;
`0xC009DAD8` mountet ein eigenes FATFS-Objekt. Die Panelqueue liegt bei
`0xC033E57C`. Ein früher direkter Dateiaufruf ohne diese Initialisierung
lieferte `FR_NOT_ENABLED`; bloßes Aktivieren der SD-Task genügte nicht.

Die Diagnose wird bei diesem Test vor dem Boot vom Host ins emulierte RAM
gelegt. Der spätere Loader für das große Engineprogramm von SD ist damit
noch nicht gebaut. Auch die gemeinsame Speicherbelegung des Ports ist
noch nicht festgelegt.

## Reale Enginepixel über SD und LCD

Gemessen: Das letzte 128 mal 64 Bild der Engineprobe wurde außerhalb des
Repos in das Seitenformat umgepackt und als `PROBE.IN` auf die virtuelle
Karte gelegt. Der alternative Start in BLECH v8 liest es per FatFs und
sendet es mit dem LCD-Treiber. Gelesener Puffer und tatsächlich gesendetes
LCD-Bild haben denselben SHA256:

`ee8f776b9fcb8c050f9515f6bfc8694006a0924303387bcf0ae13311c5db8a76`.

Das ist eine Übertragung eines zuvor berechneten Enginebildes, noch kein
gemeinsamer laufender Doom-Port. WAD, abgeleitete Bilder und Firmware
liegen ausschließlich außerhalb des Repos.

## Regression und Logs

Gemessen: Die endgültige Matrix ergänzt die vorhandenen 14 Tastenfälle um
vier Vergleiche mit Updateangebot oder abweichender Panelversion, jeweils
mit und ohne Doom-Kombination. Beide Firmwarestände bestehen 25 Prüfungen.
Im Updatefall bleibt der Diagnosezweig unbetreten und der beobachtete
Originalzustand gleich. Das beweist diese Startentscheidungen, nicht das
Durchführen eines vollständigen Firmware- oder Panelupdates.
Ein `check.py`-Nachweis für eine
neue Gerätedatei ist noch nicht möglich: Es wurde keine erzeugt.

Bereits gemessen:

| Prüfung | Ergebnis | Log unter `$doom_feasibility/` |
| --- | --- | --- |
| Basisfirmware, erste Matrix | 21 bestanden | `boot/matrix-base.json` |
| BLECH v8 und Enginebild, erste Matrix | 21 bestanden | `boot/matrix-blech-engine-frame.json` |
| gerichteter Node-Firmwaretest, endgültige Matrix und BLECH v8 | bestanden | `boot/node-boot-final.log` |
| Basisfirmware, endgültige Matrix | 25 bestanden | `boot/matrix-base-with-update.json` |
| BLECH v8 und Enginebild, endgültige Matrix | 25 bestanden | `boot/matrix-blech-with-update.json` |
| `E2_ARM_REQUIRED=1 npm test` | 417 bestanden, 63 ohne lokale Daten übersprungen, null Fehler | `unit-final-after-update-cases.log` |
| Engine mit Gegnern und Eingabe | bestanden | `engine/run-monsters/result.json` |

Der Basisstand hat SHA256
`b0890899cbe5951d0709724c46d38350a35a6134a4a01d3a5bad63e51ac22ae7`,
BLECH v8
`584f5b7a057adf23c04f07da09c8669c5410a68c494bdd19a66245fc8cfab9cb`.
Die Diagnose lehnt andere Abbilder ab.

## Nächster Schritt und Grenzen

Empfehlung: Die belegten Teile verbinden: eigener SD-Lader für das native
Programm, endgültige RAM-/Stackgrenzen, native C Dateiadapter auf FatFs,
Echtzeit und Panelinput sowie fortlaufende LCD-Ausgabe. Danach wird die
Engine im tatsächlichen Firmwarekontext mit derselben WAD geprüft.

Noch offen: Hardwarebildrate und LCD-Reaktionszeit, Ton/DSP-Anbindung,
langes Spiel und weitere Level, zuverlässiges Ausschalten, Fehleranzeige
und Rückweg der späteren Anwendung. Die Diagnose hält bei fehlender Karte
oder Datei ausdrücklich mit Fehlerstatus an; sie ist kein auslieferbarer
Loader mit Rückkehr in den Sampler. Eine neue Gerätedatei braucht danach
`check.py` und des Gerätebesitzers manuellen Test samt vorheriger Sicherung.

Unabhängige enge Nachprüfung: PASS ohne konkrete Findings. Bericht:
der damaligen unabhängigen Machbarkeitsprüfung. Das ist keine
Freigabe einer vollständigen Doom-Integration oder Gerätedatei.

SHA256 der Abschlussbelege:

- `boot/matrix-base-with-update.json`: `d87b5f1afcb5bc058fa739c0c9cf3e91e9a8c6d512f1f0eb56abcd3022374f72`.
- `boot/matrix-blech-with-update.json`: `e918b16e37fb26d5817f3fb5bea7d997dabbd00a6b14bffb8fd146b32446ecf3`.
- `boot/node-boot-final.log`: `ef0a779530fc7150fd22f0cdf280017862a062c32105e8e28beafbe8db610569`.
- `unit-final-after-update-cases.log`: `037a951f3c16ec0fdc95f90d5c4ff89e1e087d91a80f94ede22b9e6426a0201d`.
- `engine/run-monsters/result.json`: `2cc5ade658478e8f855c46739e1d6ea3d95694eddb7f47c6a0325f48aee48e66`.
