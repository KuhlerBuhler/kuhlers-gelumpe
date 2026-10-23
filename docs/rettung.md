# Rettung

Stand: 22. Oktober 2026. Die Seite "Rettung" im Editor führt durch den Weg zurück, wenn das
Gerät nach einem Update oder Patch nicht mehr richtig startet. Blechy fragt in Sprechblasen, was das
Gerät zeigt, die Antworten sind Knöpfe; jeder Fall läuft Schritt für Schritt, das Stoppschild steht
bei dem Fall, der es braucht. Sie sagt nur, was die Messungen und
die Dokumentation belegen. Jeder Schritt trägt einen Marker: **gemessen** (am Gerät gesehen),
**offline** (Code oder Emulator gelesen), **hergeleitet**, **offen** (nicht geprüft). Der Inhalt steht
in `data/rescue.mjs`, die Seite in `site/app/rescue.mjs`, der Test in `test/e2e/rescue.e2e.mjs`.

## Stoppschild

Der Bootloader (Flash `[0, 0x20000)`) wird nie angefasst: der Editor sperrt ihn
([Sperrliste](speicherbereiche.md#die-sperrliste-als-maschinenregel)) und kennt keinen Befehl, der
Flash beschreibt. Hängt das Gerät, bevor eine Update-Abfrage kommt, beschreibt Hacktribe nur
JTAG/OpenOCD als Weg, ein defekter Secondary Bootloader braucht eine eigene Wiederherstellung
([Quellenprüfung](messungen/2026-10-08-firmware-rueckweg.md)). Dann wird nichts weiter ausprobiert.

## Welche Datei in welchen Ordner

Die Datei heißt immer `SYSTEM.VSB`.

| Läuft gerade | Pfad auf der Karte | Stand |
|---|---|---|
| Hacktribe | `KORG/hacktribe/System/SYSTEM.VSB` | gemessen, am 10.10. hin und zurück geübt ([Rückweg geübt](messungen/2026-10-10-rueckweg-geuebt.md)) |
| BLECH | `KORG/blechtribe/System/SYSTEM.VSB` | gemessen: am 15.10. nahm eine laufende BLECH am Gerät ihr Update aus dieser Datei ([Gerätetest](geraetetests/blech-datei.md)) |
| Korgs Original (Sampler) | `KORG/electribe sampler/System/SYSTEM.VSB` | Pfad laut Hacktribe-Doku, am Gerät nicht geübt |
| Korgs Original (Electribe 2) | `KORG/electribe/System/SYSTEM.VSB` | Pfad laut Hacktribe-Doku, am Gerät nicht geübt |

## Doom

SHIFT + TAP beim Einschalten startet Doom von der Karte (Patch `doom-loader`, nur mit BLECH aus dem Patcher
und mit `doom.bin` unter `KORG/blechtribe/Doom/`). Der Rückweg ist kurz und liegt in der Firmware:

- **Ohne SHIFT + TAP** startet der normale Sampler. Das ist im Emulator geprüft, am Gerät nicht.
- **EXIT beim Einschalten** hält alle Patches heraus, auch den Lader: der Lader springt nur bei genau
  SHIFT + TAP an. Im Emulator geprüft ([Doom auf BLECH v21](messungen/2026-10-15-doom-v21.md)), am Gerät nicht.
- **`DOOM ERROR` mit Code** (fehlende Datei, falsche Länge oder Prüfsumme, Karte nicht lesbar): mit Ein/Aus
  ausschalten, wieder einschalten ohne SHIFT + TAP. Die Karte nicht während des Zugriffs ziehen.
- **`DOOM STOP`** nach QUIT DOOM: ebenso mit Ein/Aus aus.
- Der Bootloader und die Update-Wege bleiben unberührt. Das Update der Firmware geht wie sonst über den
  Ordner oben, auch mit dem Lader darin.

## Die vier Fälle

1. **Das Gerät startet, aber etwas stimmt nicht.** EXIT, notfalls aus und mit gehaltenem EXIT wieder
   an (Notschalter, am Gerät nur für den MFX-2-Patch bestätigt). Dann die gesicherte Original-Datei in
   den Ordner oben legen, Prüfsumme auf der Karte nachlesen, DATA UTILITY, SOFTWARE UPDATE (FACTORY
   RESET direkt davor nicht bestätigen), Abschluss abwarten. Das ist am 10.10. am Gerät geübt.
2. **SOFTWARE UPDATE, press ENTER beim Einschalten.** Korgs Original-Firmware für den Sampler unter
   `KORG/electribe sampler/System/SYSTEM.VSB` auf die Karte, einschalten, ENTER, Update durchlaufen lassen,
   aus und wieder an. Am Gerät bestätigt (23.10.). Im Emulator suchte die Abfrage die Datei an der
   Kartenwurzel und meldete "Error, Invalid File" (Grund offen, [Hintergrund](hintergrund/virtuelle-sd.md)).
3. **Anzeige 00.** Offline gelesen: so zeigt die Firmware das Panel-Update, wenn der Panel-Controller
   nicht mit Version `0x96` antwortet ([Boot](messungen/2026-10-08-emulator-boot.md)). Am Gerät bestätigt
   (23.10.): mit Korgs Original-Firmware unter `KORG/electribe sampler/System/SYSTEM.VSB` fragt das Gerät
   nach dem Update, und nach dem Update startet es wieder.
4. **Nichts, keine Abfrage.** Stoppschild, nur JTAG.

Alle Rettungswege liegen in der Firmware selbst. Eine Firmware, die vor ihnen hängt, ist ohne JTAG
nicht zu retten ([Patcher](patcher.md), "Startablauf und warum er tabu ist"). Offen bleibt die
Rettung am Gerät ([Offene Messungen](ideen/offene-messungen.md)).
