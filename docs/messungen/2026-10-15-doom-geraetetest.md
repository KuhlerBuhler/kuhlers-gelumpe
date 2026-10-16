# Doom: manueller Gerätetest für den Gerätebesitzer

Stand 15.10.2026. **Gerätetest gesperrt.** Das alte Testpaket basiert auf
BLECH v8 und überschneidet den später hinzugekommenen SysEx-Bereich.
`SYSTEM-blech-doom-v1.VSB` nicht auf eine SD-Karte oder ein Gerät übertragen.
Die folgenden Schritte dokumentieren nur die frühere Testvorbereitung.
Erst nach einem getrennt geprüften Build auf der aktuellen Firmware,
aktualisiertem Manifest und erneuter ausdrücklicher Zustimmung dürfen
sie mit den dann bestätigten Dateinamen ausgeführt werden.
Vor dem ersten Schreib-, Flash- oder Ausführungsschritt ist die ausdrückliche Zustimmung
des Gerätebesitzers erforderlich. Alle Geräteaktionen macht der Gerätebesitzer von Hand.

## Historisches Testpaket, nicht verwenden

`$doom_package/` enthält:

| Datei | Zweck |
|---|---|
| `SYSTEM-blech-doom-v1.VSB` | BLECH v8 mit eigenem Doom-SD-Lader |
| `SD/KORG/blechtribe/Doom/doom.bin` | exakt zum Lader passende ARM-Engine |
| `SD/KORG/blechtribe/Doom/doom.wad` | Freedoom 0.13.0, Phase 1 |
| `manifest.json` | vollständige Größen und SHA256 |
| `LICENSES/` | Lizenztexte der Engine und freien Spieldaten |

Firmware-SHA256:
`c217d7be660de9dba58667ca797c1aaaaace8e0a6f24faaf0633d1617d868fce`.
Engine-SHA256:
`924e4e2b8c81b675eef81cb37121ecf9c6999a5f2720e9da96d6e0b10e57a1db`.
Der Lader akzeptiert genau diese Engine. Andere `doom.bin` müssen zusammen
mit einem neuen Lader gebaut werden.

Gemessen im Firmwareemulator: Spielstart, Bewegung, Schuss mit sinkender
Munition, Benutzen-Befehl, Menü, E2M1, Quit, Ausschalten und Normalregression.
Die Emulatoruhr ist kein Beleg für Wartezeit oder Bildrate am Gerät.
Ton ist absichtlich ausgeschaltet, Speichern ist nicht verfügbar.

## Vor dem OK klären

1. Welche Firmware läuft gerade auf der Electribe und welcher bekannte
   Updateordner gehört dazu? Bei bereits installiertem BLECH ist es
   `KORG/blechtribe/System/`, bei dem vermessenen Hacktribe-Stand
   `KORG/hacktribe/System/`. Bei anderem oder unbekanntem Stand zuerst klären.
2. Ist die bisherige BLECH v8 auf diesem Gerät bereits erfolgreich geprüft?
   Die Doom-Datei baut genau auf diesem Stand auf. Die früheren offenen
   Gerätetests werden durch den Doom-Emulatorlauf nicht nachträglich belegt.
3. Liegen eine vollständige SD-Kopie, die bisherige funktionierende Firmware
   und der Rückweg aus `2026-10-08-firmware-rueckweg.md` bereit?

## Historische Schritte, derzeit gesperrt

1. **Sichern.** SD-Karte komplett auf den Rechner kopieren. Bisherige
   funktionierende Firmware und Global-Sicherung erhalten. Keine alte
   Firmware, Datei oder Sicherung löschen.
2. **Versorgung.** Netzteil und die bekannte, bisher funktionierende SD-Karte
   verwenden. Lautsprecher zunächst leise lassen.
3. **Doom-Dateien kopieren.** Den Inhalt des Paketordners `SD/` auf die Karte
   kopieren. Danach müssen die zwei Dateien unter
   `KORG/blechtribe/Doom/doom.bin` und `doom.wad` liegen. Bestehende Sample-,
   System- und Scriptordner erhalten.
4. **Firmware ablegen.** Die vorhandene Update-Datei separat sichern.
   `SYSTEM-blech-doom-v1.VSB` als `SYSTEM.VSB` in den zuvor bestätigten
   Systemordner der aktuell laufenden Firmware kopieren. Die neue Datei
   liegt weiterhin auch unter ihrem eindeutigen Namen auf dem Rechner.
5. **Update von Hand.** Den bereits bekannten Weg DATA UTILITY,
   SOFTWARE UPDATE verwenden. Bestätigung und Abschluss erfolgen nur
   durch den Gerätebesitzer. Bei unbekannter Anzeige nicht improvisieren, sondern stoppen.
6. **Normalstart zuerst.** Ohne Sondertasten starten. Erwartet: bisheriger
   BLECH-Sampler samt normalem Hauptbildschirm und Bedienung. Prüfen, dass
   der Sequencer und die gewohnten Funktionen noch reagieren. Ausschalten.
7. **EXIT prüfen.** Mit EXIT einschalten. Erwartet: normaler Sampler, kein
   Doom. Ausschalten.
8. **Doom starten.** SHIFT + TAP beim Einschalten halten, nach dem Startbild
   loslassen. Bis zur ersten Doom-Ausgabe kann das bisherige Startbild stehen
   bleiben. Fünf Minuten sind das gewählte Testlimit, keine geschätzte
   Geräteladezeit. Bis dahin vergangene Zeit notieren. Bei `DOOM ERROR`
   Code notieren und mit dem Ein/Aus-Taster ausschalten.
9. **Spielen.** PART ab/auf bewegt vorwärts/rückwärts. EDIT links/rechts
   dreht. PLAY schießt, TAP benutzt, REC bestätigt, MENU oder EXIT öffnet
   das Menü. Sichtbare Änderung und Munitionsverbrauch prüfen. Nach der
   anfänglichen Übergangsanimation testen, nicht während ihres eingefrorenen
   Spielzustands.
10. **Neues Level.** MENU, NEW GAME mit REC, zweite Episode mit PART auf
    wählen, REC und nochmals REC für die voreingestellte Schwierigkeit.
    Erwartet: neue Spielszene von E2M1.
11. **Quit und Ausschalten.** Menü öffnen, zu QUIT DOOM gehen, REC und
    nochmals REC bestätigen. Erwartet: `DOOM STOP`. Ein/Aus wie gewohnt
    halten. Das Gerät muss ausschalten.
12. **Rückweg.** Erneut ohne Kombination einschalten. Erwartet: normaler
    BLECH-Sampler. Die zwei Doom-Dateien dürfen auf der Karte bleiben.
13. **Fehlende Karte erst separat.** Nur nach bestandenem Rückweg mit
    ausgeschaltetem Gerät die Karte herausnehmen und SHIFT + TAP testen.
    Erwartet: `DOOM ERROR`, anschließend bedienbares Ausschalten. Karte nie
    während eines laufenden Zugriffs ziehen.

## Abbruch und Befund

Bei Hänger, falscher Anzeige, unbedienbarem Ausschalten oder verändertem
Normalstart stoppen. Keine weiteren Firmwarevarianten ausprobieren.
Wenn noch möglich normal ausschalten und den bekannten Rückweg verwenden;
bei abweichendem Verhalten zuerst Befund klären.

Je Schritt `ok`, `anders` oder `nicht ausgeführt` notieren, dazu sichtbaren
Fehlercode, Zeit bis zum Spielbild, Tastenwirkung und groben Eindruck der
Bildrate. Es gibt aus dem Emulator keine zugesicherte Hardwarebildrate.
Ton, weitere WADs und längere Level bleiben eigene offene Prüfungen.
