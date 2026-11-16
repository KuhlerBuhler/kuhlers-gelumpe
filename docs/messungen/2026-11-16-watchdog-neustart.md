# Neustart über den Watchdog (rot, 16.11.)

Vorbereitung für einen Menüpunkt RESTART auf der Seite `Menü -> BLECH -> DEV MODE` (Idee
[77 Neustart](../ideen/77-neustart.md)). Die blaue Electribe hat keine DEV-MODE-Seite und kein EXEC, sie bleibt außen vor.
Stand: Emulator und Stub fertig, **am Gerät noch nicht probiert**.

| Befund | Status |
|---|---|
| Auf dem AM1808 setzt nur der Watchdog von Timer64P1 (`0x01C21000`) den Chip per Software zurück | hergeleitet (TRM) |
| Scharf machen: TGCR Timer-Modus 2, Periode in PRD34:PRD12, dann WDTCR (`0x01C21028`) mit WDEN und Schlüssel `0xA5C6`, danach `0xDA7E`. Der 64-Bit-Zähler läuft ab da mit 24 MHz, beim Erreichen der Periode Reset | hergeleitet (TRM) |
| Im scharfen Zustand: `0xA5C6` dann `0xDA7E` setzt den Zähler zurück, jeder andere Schlüssel löst sofort den Reset aus | hergeleitet (TRM) |
| Die Firmware stellt Timer 1 auf TGCR `0xB` (Watchdog-Modus, beide Hälften aktiv), Periode 1 s, schreibt aber nie WDTCR; der Zähler bleibt 0 | gemessen (Emulator, Gerät: Zähler 0), [vm-tempo](2026-10-12-vm-tempo.md) |
| Hacktribe 163d1d8d startet im Emulator und läuft 8 s, ohne den Watchdog scharf zu machen | gemessen (Emulator), `test_watchdog.py` |
| Der Stub über BLECH WRITE und EXEC macht ihn scharf, EXEC antwortet 1, der Chip setzt 85,4 ms nach der Antwort (100 ms nach dem Scharfmachen, die Antwort braucht auf der DIN-Leitung rund 15 ms) zurück | gemessen (Emulator) |
| Nach dem Reset startet der Emulator aus seinem Flash neu, BLECH INFO antwortet wieder | gemessen (Emulator) |
| Ob das Gerät nach dem Reset wieder hochfährt oder ausgeht | offen |

## Das Modell im Emulator

`tools/emu/machine.py` führt WDTCR als Zustandsautomat: aus, vorbereitet (`0xA5C6` mit WDEN), scharf (`0xDA7E`),
Bedienung (`0xA5C6` im scharfen Zustand). Schlüssel außerhalb des Watchdog-Modus oder in falscher Reihenfolge vor dem
Scharfmachen ändern nichts. Scharf zählt TIM34:TIM12 ab dem Wert, den es beim Scharfmachen hatte; der Zeitpunkt, an dem
die Periode erreicht ist, ist ein Ereignis wie eine Timerkante, die Scheibe endet genau dort. Der Reset beendet den Lauf
(`Machine.reset` mit Ursache `timeout` oder `key` und Gerätezeit). `Machine.reboot()` baut eine neue Maschine aus dem, was
der Flash jetzt hält, mit derselben Karte. Nicht modelliert: ob die Stromhaltung (GPIO 7.11) den Reset übersteht, und RAM,
das der Reset stehen lässt. Der Emulator-Dienst (`server.py`) behandelt einen Reset wie Ausschalten; der Ein/Aus-Schalter
startet ihn wieder aus dem Flash.

Hergeleitet ist die Reihenfolge der Schlüssel und das Verhalten bei falschem Schlüssel im vorbereiteten Zustand (dort
ändert sich im Modell nichts). Die Firmware schreibt WDTCR nie, das Modell betrifft also nur den Stub.

## Der Stub

`tools/device/watchdog_restart.py`, 84 Bytes an `0xC1000000`, mit `tools/patch/arm.py` gebaut:

1. TGCR (`0x01C21024`) lesen. Ist er nicht `0xB`: nichts schreiben, TGCR mit Bit 31 zurückgeben.
2. TIM12 und TIM34 auf 0, PRD12 auf 2 400 000 (100 ms bei 24 MHz), PRD34 auf 0.
3. WDTCR `0xA5C64000`, dann `0xDA7E4000`. 1 zurückgeben.

Er schreibt nur diese sechs Register von Timer 1: kein Flash, kein Aufruf in die Firmware, kein anderes Register
(`test_watchdog.py` prüft das an jeder Registeradresse, die der Lauf anfasst). Die Antwort auf EXEC geht vor dem Reset raus,
die Periode ist darum auf 50 bis 2000 ms begrenzt (`--ms`). Der Stub-Puffer wird nach einem Reset nicht zurückgeschrieben.

Gemessen im Emulator (Hacktribe 163d1d8d mit dem BLECH-Satz, `watchdog_restart.py --emu ... --reboot`):

| Schritt | Ergebnis |
|---|---|
| vor EXEC (4 s nach dem Start) | kein Reset, Watchdog aus, keine Assertion |
| EXEC | Antwort Status 0, Rückgabe 1 (scharf) |
| Reset | Ursache Ablauf, bei 4255,4 ms Gerätezeit, 85,4 ms nach der Antwort |
| Neustart aus dem Flash | Hauptbild nach 400 ms, keine Assertion, Watchdog aus, BLECH INFO Flags `0xbff` |

Laufzeit 11,9 s. Die Modellfälle ohne Firmware (`tools/emu/test_watchdog.py`): Zähler bei 50 ms auf 1 200 000, Reset bei
100,0 ms; falscher Schlüssel sofort; Bedienen bei 80 ms schiebt den Reset auf 180 ms; Stub ohne Watchdog-Modus liest nur
TGCR und schreibt nichts.

## Gerätetest heute Abend (Batterie, kein Netzteil)

Vorher: Gerät frei (keine andere Session am MIDI-Port), installierte VSB bekannt, kein Sample klingt. EXEC ist eine
Änderung, kein Lesen; nach [Hänger nach EXEC](2026-11-15-remote-exec-haenger.md) kann schon ein zweiter Werkzeugstart nach
einem EXEC hängen, darum nur ein Lauf.

1. `python3 tools/device/watchdog_restart.py --dry-run`: INFO, Flags mit WRITE und EXEC, nichts geschrieben.
2. `python3 tools/device/watchdog_restart.py --arm`. Erwartet: `armed`, danach verschwindet der MIDI-Port.
   Kommt `not armed: TGCR ...`: der Timer war nicht im Watchdog-Modus, nichts geschrieben, Puffer zurück.
3. Hinsehen, die ersten 10 s:
   - Display und Licht: gehen sie aus? Kommt das Startbild von selbst wieder?
   - Bleibt das Gerät aus: es braucht den Ein/Aus-Schalter. Das heißt, die Stromhaltung fällt mit dem Reset und auf
     Batterie hält nichts sie. Dann ist RESTART auf Batterie nur ein "Aus".
   - Hängt es mit dunklem oder stehendem Display: 10 s warten, dann Ein/Aus lang drücken, notieren.
4. Nach dem Start (selbst oder per Schalter), nur Lesen:
   - `python3 tools/device/watchdog_restart.py --after`: INFO antwortet (BLECH läuft), und ob der Stub noch bei `0xC1000000`
     im RAM steht (`stub_still_in_ram`: der Reset hat das RAM stehen lassen und der Start hat die Stelle nicht überschrieben).
   - Am Gerät: Pattern, Einstellungen und Displayfarbe wie vorher. Der Stub speichert nichts, was vor dem Reset nicht
     gespeichert war, ist weg.
5. Später einmal am Netzteil wiederholen: dort kann die Stromhaltung anders aussehen.

Was der Test entscheidet: Startet das Gerät selbst neu, wird RESTART im DEV MODE ein Menüpunkt, der vorher speichert wie
das Ausschalten und dann den Watchdog scharf macht. Geht es aus, bleibt nur "Aus", oder der Neustart muss die Stromhaltung
anders überbrücken (offen).

## Offen

- Verhalten am Gerät, auf Batterie und am Netzteil.
- Ob der Watchdog-Reset ein Merkmal hinterlässt, das der Start lesen kann (z. B. RSTYPE der PLLC), um nach einem Update
  direkt ins Update zu gehen. BLECH READ liest nur RAM, Register nicht.
