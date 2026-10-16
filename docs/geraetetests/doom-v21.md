# Manueller Gerätetest: BLECH v21 mit Doom

Noch nicht am Gerät geprüft. Vor dem ersten Schreib-, Flash- oder
Ausführungsschritt erst ausdrücklich freigeben. Alles von Hand.

## Seit dem Patcher: der Lader ist ein Patch des BLECH-Satzes

Die Seite Patcher erzeugt BLECH jetzt mit dem Doom-Lader (`data/patches/doom-loader.json`), auf
Hacktribe und auf Korgs Original. Die Datei für den Test muss dann nicht mehr aus dem lokalen Paket
kommen: die Firmware aus dem Patcher ist für Hacktribe bytegleich zu `SYSTEM-blech-v21-doom.VSB`
(SHA-256 `004d23cf...`, gemessen). Nach dem Patchen und der Prüfung im Emulator zeigt die Anleitung
einen Schritt für die Karte: `doom.bin` und `doom.wad` laden und nach `KORG/blechtribe/Doom/`
legen. Die Schritte unten gelten unverändert, nur Schritt 2 (Dateien auf die Karte) kommt von der
Seite statt aus `SD/`. Auf Korgs Original ist der Lader nur im Emulator geprüft.

Rückweg: EXIT beim Einschalten hält jeden Patch und damit den Lader heraus, ebenso ein Einschalten ohne
SHIFT + TAP. Eine fehlende oder falsche `doom.bin` endet mit `DOOM ERROR` und einem Code, dann mit
Ein/Aus ausschalten und ohne SHIFT + TAP neu starten ([Rettung](../rettung.md)).

## Vor der Freigabe

1. Aktuell installierte Firmware und den dazugehörigen bekannten
   Updateordner bestätigen. Bei laufendem BLECH ist der dokumentierte
   Ordner KORG/blechtribe/System/, beim vermessenen Hacktribe-Stand
   KORG/hacktribe/System/. Bei unbekanntem Stand zuerst klären.
2. Bestätigen, ob v21 auf diesem Gerät bereits normal funktioniert.
   Der Emulatorlauf ersetzt dessen Hardwareprüfung nicht.
3. Vollständige SD-Sicherung, funktionierende Rückweg-Firmware und den
   bekannten Wiederherstellungsweg bereithalten. Nichts löschen.
4. manifest.json gegen die Paketdateien prüfen. Die Doom-Engine passt
   ausschließlich zum hier beigepackten Lader.

## Erst nach der Freigabe

1. SD-Karte und funktionierende Firmware separat sichern. Netzteil und
   die bekannte funktionierende SD-Karte verwenden.
2. Inhalt von SD/ auf die Karte kopieren. Danach liegen doom.bin und
   doom.wad unter KORG/blechtribe/Doom/. Vorhandene Dateien erhalten.
3. Vorhandene Update-Datei separat sichern. SYSTEM-blech-v21-doom.VSB
   als SYSTEM.VSB in den zuvor bestätigten Systemordner kopieren.
4. Den bereits bekannten Weg DATA UTILITY, SOFTWARE UPDATE von Hand
   ausführen. Bei unerwarteter Anzeige stoppen und den Befund klären.
5. Ohne Tastenkombination einschalten. Erwartet: normaler v21-Sampler.
   Startbild, Blechy, Patternwechsel, Presets, Note-Assistent und
   TAP-Motion mit den bisher bekannten Prüfschritten vergleichen.
6. Normal ausschalten. SHIFT + TAP halten und einschalten. Erwartet:
   Doom-Lader, danach Freedoom-Spielbild. Zeit bis zum Bild notieren.
   Bei DOOM ERROR den Code notieren und mit Ein/Aus ausschalten.
7. Nach der Übergangsanimation spielen: PART ab/auf vorwärts/rückwärts,
   EDIT links/rechts drehen, PLAY schießen, TAP benutzen, REC bestätigen,
   MENU oder EXIT öffnet das Menü. Bewegung und Munition beobachten.
8. Im Menü NEW GAME wählen, zweite Episode, Schwierigkeit bestätigen.
   Erwartet: E2M1. Danach QUIT DOOM wählen und mit REC bestätigen.
   Erwartet: DOOM STOP. Mit Ein/Aus ausschalten.
9. Ohne Kombination erneut einschalten. Erwartet: v21-Sampler. Erst nach
   bestandenem Rückweg weitere Fehlerfälle prüfen. Bei Hänger, falscher
   Anzeige oder verändertem Normalstart stoppen; keine neuen Varianten
   improvisieren. Die Karte nie während eines Zugriffs herausziehen.

Je Schritt ok, anders oder nicht ausgeführt notieren. Fehlercode,
Ladezeit und groben Eindruck der Bildrate festhalten. Der Ton bleibt aus.
Kein Rechnerbefehl in diesem Paket führt eine Geräteaktion aus.
