# Idee 34: TAP-Taste als frei belegbarer Shortcut

Stand: **TAP hat jetzt eine Belegung, den Patch TAP Motion** ([Idee 39](39-automationen-tap.md), [Messung](../messungen/2026-10-15-tap-motion-patch.md), im Emulator geprüft, am Gerät nichts bestätigt): TAP schaltet die aufgenommene Bewegung des Parts, das Tap-Tempo ist weg, SHIFT + TAP bleibt die Seite BPM; Menüseite TAP MOTION (OFF gibt die alte TAP-Taste zurück). Ein frei belegbarer Shortcut ist das nicht, die Idee bleibt offen für andere Aktionen, die den Haken mitbenutzen würden. Davor: Recherche im Emulator gemacht ([Messung](../messungen/2026-10-15-tap-motion.md)), der Weg über ein Plugin ist skizziert ([Idee 39](39-automationen-tap.md)), nichts gebaut. Gehört zu Idee 22. Zurück zu den [Ideen](../ideen.md).

TAP (Panel-Index `0x03`) macht nur Tap-Tempo, sonst nichts. Ein Firmware-Patch kann die Taste zu einem Hotkey machen, der eine vorhandene Firmware-Aktion auslöst, zum Beispiel die Sequenz des aktiven Parts löschen oder Samples exportieren.

- **Einstieg:** ein fester Remap auf eine RAM-Aktion wie Clear Sequence, im Emulator prüfbar.
- **Größer:** frei belegbar (Menü und Konfiguration) und DSP- oder SD-Aktionen wie der Export.
- **Zwei Hotkeys,** weil kaum jemand den Taster nutzt: TAP löst Aktion 1 aus, SHIFT + TAP Aktion 2, beide frei belegbar. Tap-Tempo liegt entweder auf SHIFT + TAP oder fällt ganz weg.

Plugins können Tasten abfragen (`buttonPress`, [Plugins](../plugins.md)); der Klicker in `test/fixtures/scripts/klicker-store.js` zählt mit TAP.

## Was im Emulator gemessen ist

- **Ein Plugin sieht TAP, aber die Firmware bekommt es auch.** Mit der echten Laufzeit und einem Plugin, das Tasten zählt: vier TAP im Abstand von 0,65 s zählt das Plugin vier Mal und die Firmware stellt trotzdem 92,3 BPM ein. Die Fangmaske des Eingangsfilters gilt für eine ganze Klasse von Nachrichten: sperrt man die Tasten, gehen alle verloren (die Part-Taste wirkt nicht mehr), nicht nur TAP. Eine einzelne Taste fangen kann die Laufzeit heute nicht.
- **Eine Maske je Taste reicht.** Ein Prototyp am selben Haken verschluckt nur TAP ohne SHIFT: das Tempo bleibt, alle anderen Tasten kommen durch, ohne gesetzten Schalter ist alles wie bei der Firmware. Der Vorschlag für die Funktion (`korg.capture(taste, an)`) steht in Idee 39.
- **SHIFT + TAP ist nicht frei.** In der Firmware öffnet es das Pattern-Menü auf der Seite BPM (derselbe Bildschirm wie SHIFT + MENU) und stellt kein Tempo. Wer SHIFT + TAP als Hotkey belegen will, nimmt den Weg zur Seite BPM weg; wer es durchlässt, behält ihn.
- **Das Tap-Tempo kann ein Plugin selbst übernehmen.** Das Tempo setzen mit dem Mittel der Abstände über die Funktion hinter `korg.tempo` ergibt bei vier Schlägen im Abstand von 0,65 s genau 92,3 BPM, wie die Firmware. Auf SHIFT + TAP läuft es, ohne dass die Taste verschluckt werden muss: die Firmware öffnet dabei die Seite BPM und zeigt das Tempo, das sich einstellt.

Offen ist am Gerät alles, auch ob das Plugin TAP so schnell sieht, dass das Tap-Tempo sauber ist (die Ereignisse kommen im 40-ms-Raster, das ist bei Abständen um 0,3 bis 1 s fein, aber nicht gemessen).

Die Vorbereitung für Code auf dem Gerät (`KORG.exec`) steht in Idee 36 und in der [Architektur](../architektur.md#terminal-und-echtes-gerät-erst-der-emulator-dann-das-gerät).
