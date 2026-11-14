# Platz für den Spettro-Worker in unserem Code-Bereich (6.1, nur gelesen)

Stand 11. November 2026. Nur eine Prüfung, kein Port: ob der Capture- und FFT-Worker aus Spettro (#429, Fork-Stand
`7a22d5ce`) als Dienst der Laufzeit hinter `korg.audio.*` Platz hätte. Die Erlaubnis des Autors für die Nutzung des Codes steht
aus; bis dahin wird nichts davon übernommen.

## Was Spettro belegt

| Was | Wert | Marker |
|---|---|---|
| Code-Fenster | `0xC0148880` bis `0xC014FE00` (30 080 Byte) | gelesen (`builder.py`) |
| Laufzeit-Heap | 103 424 Byte über `new` `0xC0028DCC`, bis zum Neustart gehalten | gelesen (`CONTEXT_SIZE`) |
| Aufrufstelle CommandTask | `0xC002A628`, ursprünglich `bl 0xC002D844` | gelesen |
| Display- und Eingabe-Stelle | `0xC015A4B8`, `0xC0153C94`, laut Spettro aus unserem `script_hooks.py` abgeleitet | gelesen, Herkunft nicht nachgeprüft |
| Capture-Funktionen der Firmware | Start `0xC0014368`, DSP lesen `0xC00141F8`, Stopp `0xC00143E4` | gelesen |
| Builds | nur Sampler (rot/Hacktribe); blau hat keinen nativen Capture-Start | gelesen (Spettro-Doku) |

## Code-Platz

| Befund | Marker |
|---|---|
| Das Fenster ist in unseren BLECH-Builds nicht mehr ganz frei: init-pattern `0xC014FD00` (180 Byte), beat-eighth `0xC014FC00`/`04`/`08`, blech-version `0xC014FCF0` (alle Builds); auf rot zusätzlich ht-osc ab `0xC014F000` (2 708 Byte) | gemessen (VSB-Vergleich) |
| Spettros Quellen gegen unsere aktuelle Laufzeit assembliert: 6 316 Byte für Hacktribe und rot, Ende `0xC014A12C`, also vor `0xC014F000` | gemessen |
| Freie FF-Strecken ab 4 KiB außerhalb des Fensters: Hacktribe 599 868 Byte (z. B. `0xC0161A28` 58 840, `0xC018BCF4` 82 700, `0xC01AE000` 335 856), rot 633 601, blau 674 552 | gemessen (VSB) |
| FF im VSB heißt nicht freies RAM: RAM-Bereiche, die die Firmware erst zur Laufzeit beschreibt, sehen im Image genauso aus | hergeleitet |

Ergebnis: der Worker passt in den Code-Bereich, entweder an seine alte Stelle vor ht-osc oder in eine der großen Strecken, die
`tools/patch` als Code-Bereich führt. Welche, entscheidet der Port.

## Heap

| Befund | Marker |
|---|---|
| Pool von `new` ist `[0xC06A2940, 0xC08A2940)`, 2 097 152 Byte, Cursor bei `0xC03404AC` | gemessen offline (`2026-10-08-systemspeicher-offline.md`) |
| Cursor nach Start mit BLECH (Hacktribe und rot, Emulator, 4 s, Kartenordner der Fälle): `0xC06CC000`, also 169 664 Byte gewachsen, 1 927 488 Byte bis zur Obergrenze | gemessen |
| 103 424 Byte für den Worker sind 5,4 % dieser Reserve | hergeleitet |
| Freilisten und Fragmentierung nach dem Laden großer Samples sind nicht gemessen; ebenso nicht, ob die Firmware den Pool später weiter wachsen lässt | offen |

## Konflikte für einen Port

- Die CommandTask-Stelle `0xC002A628` nutzt unsere Laufzeit bisher nicht; ein Port müsste sie in die Hook-Liste aufnehmen. (gelesen)
- Der Worker darf nur laufen, solange ein Plugin `korg.audio.capture`/`spectrum`/`wave` nutzt, sonst hält er 103 424 Byte und
  die DSP-Lesung dauerhaft. (hergeleitet)
- Blau braucht einen eigenen Capture-Start oder bleibt ohne Spektrum. (gelesen, nicht gesucht)
- Am Gerät ist nichts davon geprüft.
