# Snake als Plugin in der Firmware im Emulator

Stand 2026-10-14. Kein Gerätezugriff.

## Was geprüft ist (gemessen)

- Snake (`test/fixtures/scripts/snake.js`, Block 1080 Byte, 210 Variablenplätze) läuft
  als Plugin von der virtuellen Karte in der Firmware im Emulator: 150 Rahmen mit
  vier Drehungen (Part-Tasten, Rahmen 20, 60, 100, 130), keine Assertion, kein Fehler.
- Das Display-RAM `0xC031B310` nach genau 150 Rahmen ist Byte für Byte gleich dem
  Browsermodell (`src/script/sim.mjs`) nach denselben 150 Rahmen mit denselben
  Eingaben. Damit stimmen ARM-VM, Eingangsfilter, Ring, Zeichenfunktionen und die
  Kopie ins Display überein. Prüfung `snake-in-der-firmware` in
  `tools/emu/script_cases.py`, über `test/script-runtime.test.mjs`.
- Zeit je Handler im Emulator (Statusfelder des Plugin-Eintrags, Timer3 mit 150
  MHz): `frame` höchstens 15474 Ticks gleich 0,103 ms bei 542 Kosteneinheiten,
  `buttonPress` 90 Ticks, der Rumpf (`reset`) 101178 Ticks gleich 0,67 ms. Das
  Gerät ist 1,3 bis 1,6 mal langsamer als der Emulator (`2026-10-12-vm-tempo.md`),
  hergeleitet also etwa 0,17 ms je Rahmen gegen die Warngrenze von 0,5 ms und das
  Rahmenbudget von 5 ms. Die frühere Schätzung von 1 bis 2 ms je Snake-Schritt
  war zu hoch.

## Am Gerät offen

Snake, Klicker, ein Fehler-Plugin und das Hörkriterium (keine
hörbaren Aussetzer beim Spielen) brauchen das Gerät. Die Budgets sind im
Emulator gemessen, am Gerät nicht.
