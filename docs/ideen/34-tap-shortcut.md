# Idee 34: TAP-Taste als frei belegbarer Shortcut

Status: offen. Zurück zu den [Ideen](../ideen.md).

TAP (Panel-Index `0x03`) hat im Patch TAP Motion eine feste Belegung: TAP schaltet die aufgenommene Bewegung des Parts, das
Tap-Tempo ist weg, SHIFT + TAP bleibt die Seite BPM, und OFF auf der Menüseite TAP MOTION gibt die alte Taste zurück
([TAP Motion](../messungen/2026-10-15-tap-motion.md), [Patch](../messungen/2026-10-15-tap-motion-patch.md)). Frei belegbar
ist die Taste nicht. Gewünscht wäre ein Hotkey, der eine vorhandene Firmware-Aktion auslöst, etwa die Sequenz des aktiven
Parts löschen oder Samples exportieren.

- **Einstieg:** ein fester Remap auf eine RAM-Aktion wie Clear Sequence, im Emulator prüfbar.
- **Größer:** frei belegbar (Menü und Konfiguration), auch mit DSP- oder SD-Aktionen wie dem Export.
- **Zwei Hotkeys:** TAP löst Aktion 1 aus, SHIFT + TAP Aktion 2. Tap-Tempo läge dann auf einer der beiden Belegungen oder
  fiele weg.

## Was im Emulator gemessen ist

- **Ein Plugin sieht TAP, aber die Firmware bekommt es auch.** Vier TAP im Abstand von 0,65 s zählt ein Plugin vier Mal,
  und die Firmware stellt trotzdem 92,3 BPM ein. Die Fangmaske des Eingangsfilters gilt für eine ganze Klasse von
  Nachrichten: sperrt man die Tasten, gehen alle verloren, nicht nur TAP.
- **Eine Maske je Taste reicht.** Ein Prototyp am selben Haken verschluckt nur TAP ohne SHIFT: das Tempo bleibt, alle
  anderen Tasten kommen durch.
- **SHIFT + TAP ist nicht frei.** Die Firmware öffnet damit die Seite BPM, wie SHIFT + MENU, und stellt kein Tempo. Wer
  SHIFT + TAP belegt, nimmt den Weg zur Seite BPM weg.
- **Das Tap-Tempo kann ein Plugin selbst übernehmen.** Das Mittel der Abstände über die Funktion hinter `korg.tempo` ergibt bei
  vier Schlägen im Abstand von 0,65 s genau 92,3 BPM wie die Firmware.

Am Gerät ist nichts davon geprüft, auch nicht, ob ein Plugin TAP schnell genug sieht (Ereignisse kommen im 40-ms-Raster,
bei Abständen um 0,3 bis 1 s fein, aber nicht gemessen). Plugins fragen Tasten über `buttonPress` ab ([Plugins](../plugins.md)).
