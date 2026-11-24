# Plugin LED-Ausgabe

Kein Gerätezugriff.
Alle [Plugins](../glossary.md#plugin) kommen ausschließlich ins [Emulator](../glossary.md#emulator)-RAM, nicht in die VSB.
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
Wert erneut setzen.

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

Gemessen (Firmware im Emulator, `tools/emu/script_cases.py`):
READY sendet den Nullwert einmal; TAP sendet 255 und 0 jeweils einmal
trotz doppeltem Plugin-Aufruf. Der Burst erzeugt genau 88 Pakete mit 88
verschiedenen Indizes. Weitere Frames laufen ohne Assertion.

Restrisiken, alle am Gerät zu prüfen: das Ausschalten der Interrupts setzt voraus, dass der Rahmen
in einem privilegierten Modus läuft; der Sender prüft das Panelobjekt über
`0xC033E6FC` (Zeiger), der Rahmen über `0xC033E6F8` (Flags); die Grenze von
400 Paketen je Sekunde gilt nur bei etwa 25 Hz Aufrufen des Rahmens; ein
dauerhaft abgelehnter Index blockiert die übrigen LEDs ohne Meldung.

## Grenzen

Gerätebetrieb und Hardwarebudgets sind unbestätigt. Haken, Kartenlader und Display:
[`2026-10-14-skript-haken.md`](2026-10-14-skript-haken.md), [`2026-10-14-skript-karte.md`](2026-10-14-skript-karte.md),
[`2026-10-14-skript-display.md`](2026-10-14-skript-display.md). Die unteren RGB-LEDs und ihre Sperre: [`2026-10-14-skript-hardware.md`](2026-10-14-skript-hardware.md).
