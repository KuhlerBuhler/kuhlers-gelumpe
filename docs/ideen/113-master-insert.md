# Idee 113: Master-Insert vor dem Soft-Clipper

Stand 2026-11-17. Aufgeschrieben, nichts gebaut.

## Wunsch

Ein fester Effekt über den ganzen Mix, zum Beispiel ein Röhren-Drive, ohne den Master-Effekt zu belegen. Der Klang der
electribe 2 gilt oft als dünn; ESX-1 und EMX-1 haben dafür eine Röhrenstufe im Ausgang.

## Wo es ginge

Gelesen im DSP-Programm der roten Firmware (gleich Hacktribe), siehe
[Natives Aufnehmen](../messungen/2026-11-17-native-aufnahme.md#1-master-abgriff):

- Der Master-Effekt wird über einen Funktionszeiger aus einer Liste gerufen (`0xFFA016AC`), das ist der austauschbare Platz.
- Danach folgt fest ein Soft-Clipper `0xFFA0135C`. Er hat keine Parameter: Schwelle `0x361962E9` (etwa 0,42) und
  Nachverstärkung (etwa 1,24) stehen als Konstanten im Code, über der Schwelle wird kubisch abgerundet. Kein Schalter
  und kein Wert vom ARM erreicht ihn.
- Gerufen wird er über eine fest geladene Adresse (`0xFFA01742`/`0xFFA01746`, `CALL (P0)`). Diese zwei Befehle lassen
  sich auf eigenen Code umbiegen, der erst den Insert rechnet und dann in den Clipper springt.

**Hergeleitet:** der Insert sitzt nach Master-Effekt und Dry/Wet, vor Clipper und Endstufe, wirkt auf alle Parts und
landet mit auf einer nativen Aufnahme (Abgriff `0xFF802888` liegt danach), was gewollt ist.

## Kosten

- DSP-Patch wie stage2-memory ([Stufe 2](../messungen/2026-11-13-stufe2-speicher.md)), prüfbar im QEMU-DSP-Kern.
- Rechenzeit je Sample: der DSP hat nach bisherigem Stand wenig Luft; gemessen ist die Auslastung nicht. Der Insert muss
  billig sein (Kennlinie plus Filter, kein Oversampling) oder etwas anderes einsparen.
- Eigener Speicher für den Zustand, ein Weg für Werte (Drive, Pegel, an/aus), etwa ein Wort, das der ARM über den
  Host-Port schreibt.
- Katalog-Effekte laufen in Korgs Effekt-Engine mit Einheit und Steuerzeilen und lassen sich dort nicht einsetzen: der
  Insert ist eigener Code.
- Blau: eigene Adressen, Clipper bei `0xFFA01348`.

## Offen

- DSP-Auslastung am Gerät oder im QEMU-Kern mit Zyklen.
- Klangziel und Bedienung (an/aus, Drive, unter BLECH oder als Plugin-API).
