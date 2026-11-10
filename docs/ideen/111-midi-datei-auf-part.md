# 111. Noten aus einer MIDI-Datei auf einen Part

Wunsch (Discussion #337, auch in #296): die Noten einer `.mid`-Datei als Steps in einen Part schreiben, damit der Part die
Melodie im Pattern spielt, ohne sie vorher als Loop zu sampeln oder über KEYBOARD einzuspielen.

Stand 2026-11-10: **aufgeschrieben, nichts gebaut, nichts gemessen.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.
Zurück zu den [Ideen](../ideen.md).

## Was es schon gibt

- `korg.seq.writeSteps` schreibt ganze Steps in einen Part des laufenden Patterns: an, Gate, Velocity, Trigger und vier
  Notenplätze, also auch Akkorde ([Plugin-API](../plugins.md)).
- Ein Part hat höchstens 64 Steps, ein Step vier Noten. Gate über 96 bindet an die nächste Note (Tie).

## Vorschlag

- In der App eine `.mid`-Datei wählen, eine Spur, einen Part und den ersten Takt. Die App rastert die Noten auf das
  Step-Raster des Patterns (16tel, oder was BEAT sagt) und schreibt sie mit `writeSteps` live ins Gerät oder den
  Emulator. (hergeleitet)
- Mehr als vier gleichzeitige Noten fallen weg, mit Hinweis welche. Notenlänge wird Gate, lange Noten werden Ties.
  (hergeleitet)
- Velocity aus der Datei übernehmen. (ungeprüft)

## Offen

- Was mit Noten zwischen den Steps passiert: runden, oder ablehnen und den Takt nennen.
- Mehr als 64 Steps (4 Takte bei 16teln): abschneiden oder auf mehrere Patterns verteilen.
- Ob der Part dafür einen Synth- oder Sample-Klang mit KEYBOARD-Tonhöhe braucht, damit Noten überhaupt als Tonhöhe klingen.
