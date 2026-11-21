# Idee 113: Röhrenkurve statt Soft-Clipper

Stand 2026-11-17. Entschieden als Richtung, nichts gebaut. Ziel: Folgeversion von 1.5, unabhängig von der Aufnahme.

## Wunsch

Mehr Charakter über den ganzen Mix, ähnlich der Röhrenstufe im Ausgang von ESX-1 und EMX-1, ohne den Master-Effekt
zu belegen. Der Klang der electribe 2 gilt oft als dünn.

## Wo

Gelesen im DSP-Programm der roten Firmware (gleich Hacktribe), siehe
[Natives Aufnehmen](../messungen/2026-11-17-native-aufnahme.md#1-master-abgriff):

- Nach Master-Effekt und Dry/Wet läuft fest ein Soft-Clipper `0xFFA0135C` (rund 190 Byte bis `0xFFA01418`), für L und R
  gleich, in place auf `[P4 + 0x10]`/`[P4 + 0x14]`.
- Er hat keine Parameter: Schwelle `0x361962E9` (etwa 0,42) und Nachverstärkung (etwa 1,24) stehen als Konstanten im
  Code, über der Schwelle wird symmetrisch kubisch abgerundet. Kein Schalter und kein Wert vom ARM erreicht ihn.
- Gerufen wird er über eine fest geladene Adresse (`0xFFA01742`/`0xFFA01746`, `CALL (P0)`), nicht über die Effektliste.

## Plan

Den Clipper durch eine einstellbare Röhrenkurve ersetzen, statt einen zweiten Effekt einzuhängen:

- **Kurve:** glattes Polynom niedriger Ordnung mit einstellbarer Asymmetrie. Symmetrisch gibt es nur ungerade Obertöne
  (wie heute), die Asymmetrie bringt gerade Obertöne dazu. Ein einpoliger Hochpass nimmt den Gleichanteil weg, den die
  Asymmetrie erzeugt.
- **Werte:** Drive, Asymmetrie, Ausgangspegel als Wörter, die der ARM über den Host-Port schreibt. Eingestellt auf einem
  eigenen Punkt im BLECH-Menü, global für das Gerät (Entscheidung 17.11.). AUDIO IN und VOLUME scheiden als Regler aus:
  sie sind analog vor dem Wandler und schicken keine Panel-Nachricht. Die Grundstellung rechnet
  bit-gleich wie Korgs Clipper; wer nichts einstellt, hört keinen Unterschied.
- **Begrenzen bleibt:** die Kurve schützt den Ausgang weiter vor hartem digitalem Clipping.
- **Einbau:** Aufruf umbiegen oder die Funktion an Ort und Stelle ersetzen, wenn der Code in den Platz passt. DSP-Patch
  wie stage2-memory ([Stufe 2](../messungen/2026-11-13-stufe2-speicher.md)), bit-genau prüfbar im QEMU-DSP-Kern.

**Hergeleitet:** der Clipper rechnet ohnehin jedes Sample; ein Ersatz mit ähnlich vielen Befehlen kostet kaum mehr
DSP-Zeit. Das ist der Grund für Ersetzen statt Hinzufügen, weil der DSP nach bisherigem Stand wenig Luft hat (Auslastung
nicht gemessen). Die Kurve wirkt vor dem Aufnahme-Abgriff `0xFF802888` und landet mit auf einer nativen Aufnahme.

## Nicht gewählt

- Zweiter Effekt vor dem Clipper: kostet zusätzliche Rechenzeit.
- Limiter oder Kompressor mit Hüllkurve: mehr Zustand und Rechenzeit.
- Tape-Sättigung mit Hysterese oder harte Kurven mit Oversampling: zu teuer.
- Katalog-Effekte an dieser Stelle: sie laufen in Korgs Effekt-Engine mit Einheit und Steuerzeilen.

## Offen

- DSP-Auslastung am Gerät oder mit Zyklen im QEMU-Kern.
- Klangziel, Grenzen der Regler.
- Name und Platz des Menüpunkts.
- Blau (wird mitgebaut): eigene Adressen, Clipper bei `0xFFA01348`.
