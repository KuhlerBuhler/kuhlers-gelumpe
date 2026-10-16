# Plugin LED-Ausgabe

Stand 2026-10-14. Kein Gerätezugriff.
Alle Plugins kommen ausschließlich ins Emulator-RAM, nicht in die VSB.
Die folgenden Zahlen beziehen sich auf lokale Tests, nicht auf das Gerät.

## Vorgabe und Umsetzung

Vorgabe: `korg.led(index, level)` prüft Argumente, fasst
Aufträge zusammen und begrenzt die Ausgabe gegen eine volle Warteschlange.
API Kennung 1 und API Version 1 bleiben bestehen.

Hergeleitet: Ein gemeinsamer Zustand von 356 Byte hält für alle 88 LEDs
gewünschten Wert, zuletzt vom Transport akzeptierten Wert, Auftrag und Gültigkeit sowie
einen fair umlaufenden Cursor. Der Zustand gehört zur Runtime, außerhalb
des gemeinsamen 128-KiB-Plugin-Pools. Gleiche Aufträge werden innerhalb
eines Rahmens zusammengefasst. Zum nächsten Rahmen verfällt die Kenntnis
des gelieferten Werts: Firmwareausgaben können ihn überschrieben haben.
Das erzeugt keinen automatischen Auftrag; ein expliziter Aufruf kann den
Wert erneut setzen. Dauerhafte Kontrolle der unteren RGB LEDs folgt später.

Hergeleitete Politik: maximal 16 Pakete je Rahmen und mindestens 256 Byte
Reserve nach einem vollständigen 5 Byte Paket. Bei 25 Hz sind das maximal
400 Plugin-Pakete je Sekunde. Die Reserve und Grenze sind keine Messung
eines maximal sicheren Gerätedurchsatzes.

Die JS Referenz verwendet einen explizit angeschlossenen Transport mit
atomarer Erfolgsmeldung. Freier Platz allein zählt nicht als Zustellung.
Abgelehnte Aufträge bleiben ausstehend. Der Rahmenbesitzer stellt das
Zeitbudget bereit.

Offline gelesen und im Emulator geprüft: Der Factory Mehrbytewriter hält
Semaphore 5 auch bei einem teilweise geschriebenen Paket. Der eigene
Transport wartet nie darauf: Im kurzen IRQ Abschnitt muss deren Zähler
exakt 1 sein. Er prüft Queueform, Index-/Zählerkonsistenz, Platz, Panel,
Puffer und den bekannten UART0 Callback, schreibt dann das komplette
Paket und stößt bei zuvor leerer Queue den Sender an. Ein Paket gilt hier
als in die Queue übernommen, nicht als physisch quittiert.

Der Writer liest Queueindizes ausschließlich unter IRQ Schutz. Vor einem
Warten wegen vollem Puffer hält er keine alten Indizes fest. Alle
gefundenen Writer, TX Leser und Resetpfade verwenden denselben IRQ Schutz.
Die aktive Interruptkonfiguration und der FIQ Vektor wurden geprüft.
Diese Aussage gilt nur für das geprüfte Firmwareabbild.

## Prüfstand

Gemessen, gezielt rot vor dem Transport: Der neue Firmwarefall erzeugt
keine LED Pakete bei READY, zweimal TAP oder der Anforderung aller 88 LEDs.
Die übrigen Eingabe-, Rahmen- und Fehlerfälle bleiben grün.

Gemessen: Der erste Firmwarelauf mit Transport besteht 22 Prüfungen.
READY sendet den Nullwert einmal; TAP sendet 255 und 0 jeweils einmal
trotz doppeltem Plugin-Aufruf. Der Burst erzeugt genau 88 Pakete mit 88
verschiedenen Indizes. Weitere Frames laufen ohne Assertion.

Gemessen beim Build: Code 10632 Byte, Runtime 165636 Byte, Plugin-Pool
131072 Byte. Hergeleitete Summe: 307340 Byte. Die Runtime endet bei
`0xC01D6704`, der Pool beginnt unverändert bei `0xC01D7000`.

Abschlussprüfungen (14.10., gemessen, Basis eigene `SYSTEM.VSB`, eigener
Flash-Dump vom 9.10., kein Gerät):

| Prüfung | Ergebnis |
|---|---|
| `E2_ARM_REQUIRED=1 npm test` | 437 Tests, 396 bestanden, 41 ohne Firmware übersprungen, 0 Fehler |
| `tools/patch` Unit (LED, Haken, VM, Assembler) | 48 Tests bestanden, 2 übersprungen |
| `script_cases.py` über `test/script-runtime.test.mjs` | 5 LED Prüfungen und alle bisherigen Firmwarefälle grün |
| `check.py` auf Startbild + MFX 2 + Laufzeit | 37 von 37 Prüfungen, 66 s |
| `test/mfx-switch.test.mjs`, `test/splash-editor.test.mjs` | 21 von 21 (Regression) |
| `test:emu` mit Flash | 26 von 26 |

Die gebaute Kopie hat dieselbe SHA256 wie die vorige Kontrollkopie
(`f6a2d93c432b51d37c3e13288d2081a7add9c5fe5d5f7c1b1338d99236a910a7`).
Ein einziger Lauf der MFX Prüfung gegen die Originalfirmware endete einmal
mit `ETIMEDOUT` nach 2771 s Wanduhrzeit bei 1800 s Grenze (vermutlich Ruhezustand
des Rechners, hergeleitet); allein dauert derselbe Ablauf 295 s und besteht,
und der Wiederholungslauf beider Dateien besteht.

Unabhängiges Review (nur Lesen) ohne bestätigten Fehler. Restrisiken, alle am
Gerät zu prüfen: das Ausschalten der Interrupts setzt voraus, dass der Rahmen
in einem privilegierten Modus läuft; der Sender prüft das Panelobjekt über
`0xC033E6FC` (Zeiger), der Rahmen über `0xC033E6F8` (Flags); die Grenze von
400 Paketen je Sekunde gilt nur bei etwa 25 Hz Aufrufen des Rahmens; ein
dauerhaft abgelehnter Index blockiert die übrigen LEDs ohne Meldung.

## Grenzen

Gerätebetrieb und Hardwarebudgets sind unbestätigt. Produktiver Bootstart,
Kartenlader, Displayfehler und dauerhafte LED-Übernahme folgen danach
(`2026-10-14-skript-haken.md`, `2026-10-14-skript-karte.md`, `2026-10-14-skript-display.md`).
