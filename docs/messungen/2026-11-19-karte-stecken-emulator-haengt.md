# Karte im laufenden Emulator gesteckt: "hängt" war ein Fehlalarm (19.11.)

Stand 19.11.2026, Emulator mit develop (8f8953d3, BLECH-Satz auf Hacktribe 2.02 rot). Kein Gerät.
Anlass: Meldung auf PR #690, im Emulator stürzt develop beim Stecken der SD-Karte ab.
Marker: **gemessen**, **hergeleitet**, **offen**.

## Ergebnis

Die Firmware hängt nicht. Der Emulator-Dienst (`tools/emu/server.py`) meldete "hängt", weil er nur die Nachrichten an das
Bedienfeld als Lebenszeichen nahm. Seit #595 (Pegel-LEDs nur bei Änderung) schickt ein ruhiger Hauptbildschirm dem Bedienfeld
nichts mehr. Ohne Karte blinkt LED 0x14 und hält den Zähler am Laufen; mit Karte ist es still, nach 2 s stand "hängt" da.

Fix im Dienst: Lebenszeichen sind jetzt Nachrichten ans Bedienfeld **oder** Warten der CPU auf einen Interrupt (WFI). Eine
Firmware, die in einer Schleife hängt, wartet nie.

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Nachgestellt: develop, Start ohne Karte, `POST /sd/insert`, nach rund 2 s Zustand "hung" und bleibt; release/1.4.7 läuft weiter | `test/support/emu.mjs` `startEmulator` + `/sd/insert`, Status jede Sekunde | gemessen |
| Erster schlechter Merge ist #595 (b1e64992), davor gut | First-Parent-Bisect über develop seit dem Merge-Base mit release/1.4.7 | gemessen |
| Nach dem Stecken bleibt die Firmware bedienbar: MENU öffnet Bildschirm 3, OS-Tick +500 je 0,5 s | Python-Probe mit `menu_cases.boot(card=False)`, `insert_card`, `press("menu")` | gemessen |
| Nach einem Start ohne Karte liest die Firmware die gesteckte Karte nicht (0 Sektoren), so gewollt | `sectors_read` 0; `start_without_card_reads_none` ([Karte später](2026-11-12-karte-spaeter-einstellungen.md)) | gemessen |
| Ohne Karte gehen 4 Nachrichten je Sekunde ans Bedienfeld (`00 14 ff/00`, LED 0x14 blinkt), mit Karte 0 | Spion auf `Machine.panel` | gemessen |
| Auch ein Start **mit** Karte schickt im Leerlauf 0 Nachrichten (dort hätte der alte Dienst ebenso "hängt" gemeldet), und das Display wird nicht neu geschrieben (`frames` +0) | Python-Probe, 3 s Leerlauf | gemessen |
| Ruhige Firmware wartet rund 3000-mal je Sekunde auf einen Interrupt; mit einer Endlosschleife in der LED-Sendefunktion (0xC00875F4 auf `b .`) 0-mal | `Machine.idle_waits`, Probe mit gepatchtem Befehl | gemessen |
| Das Gerät selbst hängt mit #595 und Karte nicht | develop-Builds mit #595 liefen am 18.11. am Gerät (LOAD METER abgelesen), kein Hänger gemeldet | hergeleitet |
| Ob das echte Bedienfeld ohne Nachrichten der CPU etwas anders macht (eigenes Senden, eigener Wächter) | Emulator modelliert Antworten des Bedienfelds nur auf Nachrichten der CPU | offen |

## Prüfungen

- `tools/emu/test_server.py`: `test_a_quiet_firmware_that_waits_for_interrupts_is_not_hung`, mit dem alten Dienst rot, neu grün;
  `test_a_firmware_that_stops_talking_to_the_panel_is_reported_as_hung` bleibt grün.
- `tools/emu/menu_cases.py`: `card_later_card_put_in_keeps_running` (Start ohne Karte, Karte stecken: in 2 s über 1000 Waits,
  MENU öffnet eine Seite). Der Fall war auch vorher grün, weil die Firmware nie hing; er hält fest, dass sie nach dem Stecken weiter
  ruht und bedienbar bleibt.
