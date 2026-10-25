# Sync Group auf der blauen Electribe (24.10.)

Bisher nur rot, weil auf der blauen das Laden eines Patterns nicht gemessen war. Gemessen im Emulator mit Korgs Synth-Firmware
2.02 und dem BLECH-Satz für Blau. **Am Gerät nicht geprüft.**

## Das Laden eines Patterns

- Die Funktion, die ein Pattern lädt, liegt auf der blauen bei `0xC0044C64` (rot `0xC004AB84`). Ihre Kopie ins Pattern im RAM,
  `bl memcpy`, liegt bei `0xC0044D24` (rot `0xC004AC44`) und ruft `0xC0005814`, das `memcpy` der blauen. fwmap findet beide
  Stellen mit 16 gleichen Wörtern, eingetragen in `data/synth-map/sync-groups.json`.

## Wo die Gruppe steht

- Wie auf der roten bei Byte `0x3B80` des Pattern-Blocks, u16. Geprüft wie dort mit Lese- und Schreibwächtern auf `0x3B03` bis
  `0x3BFB` im Pattern im RAM und in allen 250 Bank-Plätzen der unveränderten Firmware: Abspielen, ein Wechsel beim Spielen, ein
  Wechsel im Stand, das MENU 30 Seiten weit, EXIT. Zugegriffen hat nur `memcpy` (`0xC0005838` bis `0xC000585C`), 372 Zugriffe,
  genauso viele wie auf der roten mit demselben Ablauf.

## Ergebnis (Emulator, blau)

| Fall | Ergebnis |
|---|---|
| `pswitch_cases.py`, `case_sync_group`: bestätigt sofort, nimmt Mutes, Klang, Tempo mit und zurück, Steps bleiben, eine andere Gruppe blättert nur, nichts aus der Gruppe hinaus | 10 von 10 |
| `menu_cases.py`, Ring: SYNC GROUP nach Blechy (30/31), setzt die Gruppe, WRITE öffnet das Speichern des Patterns, EXIT zum Hauptbildschirm, EDIT links und rechts | alle |
| aus den übrigen Fällen des Patternwechsels Blättern, Bestätigen, im Stand und ungespeichert (die anderen nicht neu gelaufen) | bestanden |

## Was die blaue Firmware selbst anders macht

Wechselt die unveränderte Synth-Firmware das Pattern selbst (EXIT beim Einschalten gehalten), weichen danach Byte `0x0B` und
`0x24` von Part 1 vom Bank-Platz ab. Das macht Korgs Firmware, es ist auch ohne Patch so. Der Fall nimmt diese zwei Bytes auf der
blauen deshalb aus.
