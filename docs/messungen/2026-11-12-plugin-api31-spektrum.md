# Plugin API 31: Spektrum und Wellenform, im Emulator

`korg.audio.capture`, `korg.audio.spectrum` und `korg.audio.wave` laufen auf den
Sampler-Firmwares (Hacktribe, Korg rot) über einen Dienst in der Laufzeit.
Erfassung, Ring-Leser, FFT und Spaltentabellen stammen aus Spettro von Luigi
(GitHub reflectiveboi, PR #429). Er wollte den Worker von Anfang an als
Schnittstelle der Firmware haben, in 1.5 ist er das.
Spettro selbst ist jetzt ein Plugin im Katalog, das auf diesen Aufrufen sitzt.

Grundlage für Adressen und native Routinen: [Spettro](2026-11-07-spettro.md)
aus #429, Platz und Heap: [Spettro-Worker als Dienst](2026-11-11-spettro-worker-platz.md).

## Aufbau

**Gelesen:** Der Worker läuft in CommandTask hinter dessen Aufruf bei
`0xC002A628` (ursprüngliches Ziel `0xC002D844` bleibt, wird zuerst gerufen).
Er läuft nie im Frame-Haken. Die drei Aufrufe schreiben nur eine Anfrage und
kopieren, was der Worker zuletzt fertig hat.

| Teil | Datei |
| --- | --- |
| Erfassung, Ring, FFT, Tabellen (aus #429) | `tools/patch/spectrum/` |
| Dienst, Lease, Glue der drei Aufrufe | `tools/patch/script_audio_service.s` |
| blau: alle drei geben 6 zurück | `tools/patch/script_audio_service_none.s` |

**Gelesen:** Der Dienstzustand (16 Byte: Kontextzeiger, Anfrage, Lease-Tick,
Status) liegt am Anfang der MORE-Reserve, `0xC018D000`. In allen drei Images
ist der Bereich FF. In MORE2 waren vor dem Tap-Motion-Zustand bei `0xC0188F00`
nur noch 4 Byte frei.

**Gelesen:** Den Kontext (103424 Byte) holt der Dienst bei der ersten Anfrage
einmal vom Heap und behält ihn bis zum Ausschalten. Fehlt der Speicher, ist
der Status 5 (noMemory).

**Hergeleitet:** Lease 2048 Ticks, also etwa 2 s (1 Tick = 1 ms, siehe
[Plugin-Timer](2026-10-29-plugin-timer.md)). 2000 ist kein ARM-Immediate.
Ruft ein Plugin 2 s lang weder `capture` noch `spectrum` noch `wave`, schließt
der Worker die native Erfassung. Spettro hatte 200 Zählerschritte.

## Aufrufe

| Aufruf | Rückgabe |
| --- | --- |
| `korg.audio.capture(quelle)` | 1 bis 16 Part, 17 bis 24 Part-Paar, 0 oder -1 aus. Status |
| `korg.audio.spectrum(array, bins, bereich)` | bei 0: die ersten `bins` Plätze in dB 0 bis 96, je Platz die lauteste der 128 Spalten. Bereich 0 = 20 Hz bis 20 kHz, 1 = 20 Hz bis 2 kHz |
| `korg.audio.wave(array)` | bei 0: die neuesten Frames, oberes Byte, -128 bis 127, höchstens 256 |

Status: 0 ok, 1 aus, 2 belegt, 3 warten (Fenster füllt sich), 4 Lücke
(verloren oder veraltet), 5 kein Speicher, 6 auf dieser Electribe nicht da.

**Hergeleitet:** 96 dB entspricht einem Vollaussteuerungs-Sinus, 0 dB liegt
96 dB darunter. Die Umrechnung nimmt Spettros Log2 in Q8 (7680 = 2^30).

## Messung im Emulator

`tools/emu/plugin_api31_spectrum_cases.py`. Firmware, Laufzeit und Plugin
sind echt; die DSP-Seite der nativen Erfassung ist ein erzeugter Sinus im
Ring, wie in Spettros eigenem Fall. Das ist keine DSP-Emulation.

| Fall | Hacktribe | rot | blau |
| --- | --- | --- | --- |
| 1 kHz, -6 dB: lautester Platz von 32 (erwartet 18) | 18, 89 dB | 18, 89 dB | |
| Wellenform des Sinus (erwartet ±64) | ±64 | ±64 | |
| 100 Hz, -18 dB: lautester Platz (erwartet 7) | 7, 76 dB | 7, 76 dB | |
| Plugin hört auf zu rufen: begin(3), nach Lease end, Anfrage -1 | ja | ja | |
| capture, spectrum, wave | | | 6, 6, 6 |

**Gemessen.** Rechnerisch wären 90 dB und 78 dB; die 1 bis 2 dB weniger
passen zum Hann-Fenster und zur Verteilung auf Nachbar-Bins.

```bash
PYTHONPATH=tools/patch tools/emu/.venv/bin/python tools/emu/plugin_api31_spectrum_cases.py --vsb BLECH.VSB
```

Die Zahlentests aus #429 (FFT gegen Python) sind nicht übernommen. **Urteil:**
Der Emulatorfall prüft denselben Code auf der echten Firmware mit bekannten
Tönen, Platz und Pegel.

## Offen

- **Gerätetest:** noch nicht gemacht. Last mit vielen Stimmen, Latenz und der
  genaue Abgriff relativ zu den Effektstufen sind nur aus #429 übernommen.
- **Quellen (Plan 6.5):** bekannt sind nur 1 bis 16 (Parts) und 17 bis 24
  (Paare). Ein Abgriff für den Master-Ausgang oder AUDIO IN ist nicht gefunden.
- **Belegt oder Aufnahme:** Laut #429 übernimmt die Erfassung keine schon
  belegte Erfassung und keine laufende Aufnahme (Status 2). **Gelesen** in
  `capture.s`, nicht im Emulator geprüft.
- **blau:** dort fehlt der native Erfassungsstart, das DSP-Programm ist ein
  anderes. Die Aufrufe geben 6 zurück.
- **Stereo eines Pads:** laut #429 lieferte der Part-Abgriff bei STEREO 1 PAD
  zwei gleiche Komponenten; nicht neu geprüft.
