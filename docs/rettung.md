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

Diese Tabelle gilt für DATA UTILITY, SOFTWARE UPDATE in einer laufenden Firmware. Die Abfrage beim
Einschalten (Fall 2) sucht woanders: sie richtet sich nach der Kennung des Geräts im Flash
(`0x220000`), nicht nach der Firmware, die läuft.

| Gerät (Kennung im Flash) | Es läuft | Abfrage beim Start sucht | Angenommen | Stand |
|---|---|---|---|---|
| rot, Sampler (`ele2sUSR`) | Korgs Synth-Firmware | `KORG/electribe sampler/System/SYSTEM.VSB` | jede Sampler-VSB: Korg, Hacktribe, BLECH | offline (Emulator), Korg am Gerät bestätigt (23.10.) |
| blau, Synth (`elec2USR`) | Korgs Sampler-Firmware | `KORG/electribe/System/SYSTEM.VSB` | Synth-VSB von Korg | offline (Emulator) |
| Kennung fehlt oder kaputt | beliebig | `System/SYSTEM.VSB` an der Kartenwurzel | nichts: immer "Error, Invalid File" | offline (Emulator) |

- **offline (Emulator):** In der Startabfrage findet die Firmware unter `KORG/hacktribe/System` und
  `KORG/blechtribe/System` nichts ("Error, No File"). Dieselbe Hacktribe- oder BLECH-VSB unter
  `KORG/electribe sampler/System` nimmt sie an und schreibt sie.
- **offline (Emulator):** Hacktribe und BLECH nehmen beide Kennungen an und starten normal, auch auf
  einem blauen Gerät. Bei ihnen kommt die Startabfrage also nur, wenn die Kennung fehlt, und dann
  hilft keine Datei (Zeile 3).
- **offline (Code):** Warum "Invalid File" an der Wurzel: ohne Kennung ist der Gerätetyp 0, der Ordner
  dafür ist leer (`0xC0035720`), und der Typ im Kopf jeder VSB (`0x124` Sampler, `0x123` Synth, Byte
  `0x2C` bis `0x2E`) passt nie zu 0 (Vergleich `0xC003AD80`).

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
   aus und wieder an. Am Gerät bestätigt (23.10.). Welcher Ordner, steht in der zweiten Tabelle oben.
   Im Emulator (offline) Schritt für Schritt: Startbild, "SOFTWARE UPDATE / press ENTER", einmal ENTER
   (am Panel die Taste MENU, Nachricht `0x09`), "Working...", dann "SOFTWARE UPDATE / OK. Please Reboot.",
   aus und wieder an. Ohne Netzteil kommt nach ENTER "Warning / Battery Low" und nichts wird geschrieben.
   Die Kartenwurzel aus der alten Emulator-Messung ist der Fall "Kennung fehlt": dort passt keine Datei.
3. **Anzeige 00.** Das ist das Panel-Update: die Firmware fragt den Panel-Controller nach seiner Version,
   erwartet `0x96` und schreibt sonst die Panel-Firmware aus der laufenden VSB neu; die Zahl ist der
   Schritt (00 bis 12). Hintergrund: [Panel-Controller](hintergrund/panel-controller.md).
   - **offline (Emulator):** Falsche Version: Startbild, leer, "Working...", nach rund 3,6 s "00" in einem
     Rahmen. Keine Antwort: dasselbe, "00" nach rund 8,8 s. Antwortet das Panel im Update, läuft es bis
     "Please Reboot"; antwortet es nicht, bleibt "00" stehen (60 s geprüft).
   - **offline (Emulator):** Während "00" liest die Firmware die Karte nicht (0 Sektoren). Eine Datei auf
     der Karte ändert an "00" nichts. Das Panel-Update kommt vor der Startabfrage aus Fall 2: mit falscher
     Panel-Version und falscher Kennung zeigt das Gerät zuerst "00".
   - **offline (Emulator, Bootloader):** Der Secondary Bootloader zeichnet nichts und sucht keine Datei.
     Er liest 2 MiB ab Flash `0x20000` ohne Prüfung und springt hinein; mit gelöschtem oder genulltem
     Abbild bleibt das Display leer, ohne "00". "00" kommt also immer aus der Firmware, nie aus dem
     Bootloader.
   - **Was tun (hergeleitet):** warten. Kommt "Please Reboot", aus und wieder an. Bleibt "00" stehen,
     redet das Panel nicht mit der CPU; das Debrick-Wiki von Hacktribe nennt dafür das Flachbandkabel
     zwischen Hauptplatine und Panel, nicht die Karte.
   - **gemessen am Gerät (23.10.):** Nach einem Update auf Hacktribe blieb "00" stehen, sonst passierte
     nichts, an "Please Reboot" erinnert sich der Nutzer nicht. Mit Korgs Sampler-Firmware unter
     `KORG/electribe sampler/System/SYSTEM.VSB` kam beim nächsten Einschalten die Update-Abfrage, danach
     startete es wieder.
   - **offen:** Warum die Abfrage kam. Laut Emulator liest die Firmware während "00" die Karte nicht, und
     Hacktribe nimmt beide Kennungen an. Ein Panel-Update, das hängen bleibt, und danach eine fehlende
     oder kaputte Kennung würden passen; nicht geprüft.
4. **Nichts, keine Abfrage.** Erst Netzteil und Batterien prüfen. Kommt dann weiter keine Abfrage, hilft
   nach der Debrick-Anleitung von Hacktribe nur JTAG.

Bei 2 und 3 fragt die Seite nach der Farbe: für die blaue Electribe liegt Korgs Datei unter
`KORG/electribe/System/SYSTEM.VSB` (zweite Tabelle oben). Bei 00 lässt sie erst warten und geht den Weg über die
Karte nur, wenn "00" stehen bleibt, so wie am Gerät am 23.10.; endet er nicht, nennt sie das Kabel. Ohne gesicherte
Original-Datei nimmt Fall 1 ebenfalls Korgs Datei von Korgs Download-Seite.

Die Seite spricht mit Leuten, die das Gerät kaum kennen und gerade Angst um es haben: Blechy erklärt
in Alltagssprache, nur die Antworten. Belege stehen hier in der Doku, auf der Seite steht nur eine offizielle Quelle, wo es eine gibt (Debrick-Anleitung von Hacktribe). Was nur zu lesen ist,
folgt nach einer Sekunde von selbst; Knöpfe gibt es nur, wo man etwas tun oder beantworten muss.

Alle Rettungswege liegen in der Firmware selbst. Eine Firmware, die vor ihnen hängt, ist ohne JTAG
nicht zu retten ([Patcher](patcher.md), "Startablauf und warum er tabu ist"). Offen bleibt die
Rettung am Gerät ([Offene Messungen](ideen/offene-messungen.md)).
