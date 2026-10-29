# Rettung

Stand: 28. Oktober 2026. Die Seite "Rettung" im Editor führt durch den Weg zurück, wenn das
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
| BLECH auf der blauen (Synth-Satz oder mit Hacktribe) | `KORG/blechtribe/System/SYSTEM.VSB` | im Emulator gemessen ([Messung](messungen/2026-10-26-blech-hacktribe-blau.md)), am Gerät offen |

**Hacktribe oder BLECH mit Hacktribe auf der blauen, zurück zu Korgs Original:** Korgs blaue 2.02 nehmen und im Kopf zwei
Bytes ändern: Byte `0x12` auf `0x53`, Byte `0x2E` auf `0x24` (das macht Hacktribes `e2-header.py DATEI sampler`). Die Datei
als `SYSTEM.VSB` in den Ordner der laufenden Firmware legen (`KORG/hacktribe/System/` oder `KORG/blechtribe/System/`), dort
nur diese Datei, dann SOFTWARE UPDATE. Unverändert sagt das Gerät "Error / Invalid File" und schreibt nichts. Im Emulator
gemessen ([Messung](messungen/2026-10-26-blech-hacktribe-blau.md)), am Gerät offen. Korgs BLECH-Synth-Satz (ohne Hacktribe)
nimmt die unveränderte blaue Datei in `KORG/blechtribe/System/`.

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
- **`DOOM ERROR` mit Code** (fehlende Datei, falsche Länge oder Prüfsumme, Karte nicht lesbar), **`DOOM STOP`** nach
  QUIT DOOM und das laufende Spiel: Ein/Aus schaltet in Doom am Gerät bisher nicht aus (25.10.: 30 s gehalten, sie blieb
  an). Netzteil ziehen oder Batterien raus, wieder einschalten ohne SHIFT + TAP. Die Karte nicht während des Zugriffs ziehen.
- Der Bootloader und die Update-Wege bleiben unberührt. Das Update der Firmware geht wie sonst über den
  Ordner oben, auch mit dem Lader darin.

## Die vier Fälle

1. **Das Gerät startet, aber etwas stimmt nicht.** EXIT, notfalls aus und mit gehaltenem EXIT wieder
   an (Notschalter, am Gerät nur für den MFX-2-Patch bestätigt). Hilft EXIT, gilt das nur für diesen einen
   Start. Die Seite fragt dann weiter: einmal ohne Karte normal einschalten (ohne Karte lädt der Plugin-Lader nichts
   und die Einstellungen stehen auf den Vorgaben, siehe [Plugins](plugins.md)). Läuft sie so, `Plugin/e2sPlugin.all`
   und `settings.a.bin`/`settings.b.bin` unter `KORG/blechtribe` umbenennen; das hält auch bei normalem Start.
   Spinnt sie auch ohne Karte, oder hilft EXIT nicht: die gesicherte Original-Datei in
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

## Meldungen beim Update und Ärger mit der App

Neben den vier Fällen fragt die Seite nach "Error, Invalid File", "Error, No File" und nach Ärger mit der App. Die
Fälle kommen aus dem Discord (25. bis 28.10.); dort ist auch der erste Gerätefall zu "Invalid File" beschrieben.

**Error, Invalid File.** Die Firmware hat eine Datei gefunden, die nicht passt, und schreibt nichts (offline, Emulator,
siehe oben). Die Seite fragt, wann die Meldung kommt:

- **Beim Einschalten, nach press ENTER:** Farbe, bei der blauen dann "War jemals Hacktribe drauf?". Nein oder weiß
  nicht: Korgs blaue Datei unter `KORG/electribe/System/SYSTEM.VSB`. Ja: Korgs Datei für die rote (Sampler) unter
  `KORG/electribe sampler/System/SYSTEM.VSB`. Grund (hergeleitet): Die Startabfrage folgt der Kennung im Flash, und
  eine blaue, auf der Hacktribe lief, kann die Sampler-Kennung tragen; dann gilt Zeile 1 der zweiten Tabelle oben.
  Am Gerät: eine blaue, vorher Hacktribe, zurück auf Korgs Synth-Firmware, dann BLECH, hing in der Schleife
  "SOFTWARE UPDATE / press ENTER", ENTER, "Error / Invalid File" mit Korgs blauer Datei unter `KORG/electribe/`
  (gemessen, Videos im Discord, 28.10.). Mit einer Sampler-Datei bzw. einem anderen Ordner ging es weiter; welcher der
  beiden Wege es war, ist offen. Dass Korgs Sampler-Firmware danach auf der blauen normal läuft, ist hergeleitet.
- **Im Menü bei SOFTWARE UPDATE:** Datei aus dem Patcher: meist für die andere Electribe gepatcht (Discord, 27.10.,
  rote mit Korgs Original, im Patcher die blaue gewählt); neu patchen mit der richtigen Farbe, der Patcher nennt die
  Farbe selbst, wenn die Electribe angesteckt ist (`patcher.device.cable.*`, offline, Code). Korgs Datei: rot und blau
  ohne Hacktribe gehen den Weg über den Ordner der laufenden Firmware; blau mit Hacktribe braucht die zwei Kopf-Bytes
  aus dem Absatz oben. Das macht die App nicht, die Seite führt dann zum Kontakt.

**Error, No File.** Dort, wo die Firmware sucht, liegt keine Datei mit genau diesem Namen. Beim Einschalten geht die
Seite den Weg über die Farbe wie bei "Invalid File". Im Menü nennt sie die Stellen, an denen es im Discord hing
(gemessen, Chat und Fotos, vier Fälle):

- Der Name ist genau `SYSTEM.VSB`. Der Patcher speichert über einen Download mit diesem Namen
  (`site/app/save-file.mjs`); liegt im Download-Ordner schon eine, nennt der Browser die neue `SYSTEM (1).VSB`
  (gemessen, Foto). Dass genau das "No File" auslöste, ist hergeleitet, im Fall fehlte auch der Ordner `System`.
- Die Datei liegt im Unterordner `System`, fehlt er, wird er angelegt.
- Kein Ordner wird umbenannt. `KORG/blechtribe/` nimmt die Firmware erst, wenn BLECH läuft; vor dem ersten Update gehört
  die Datei in den Ordner der laufenden Firmware (Tabelle oben). Ein Ordner, der vor dem ersten Flash in `blechtribe`
  umbenannt wurde, führte zu "No File" (gemessen, Discord).
- Im Patcher die richtige Electribe: für die rote und die blaue nennt er verschiedene Ordner (`folderOf`, offline, Code).

Danach fragt die Seite, welche Firmware läuft, und legt die Datei in deren Ordner.

**Die App findet die Electribe nicht.** Die Seite liest den MIDI-Bericht der App selbst (`midiVerdict` in
`site/app/midi-report.mjs`, ohne den Browser zu fragen) und den Modus oben in der App:

| Bericht | Die Seite sagt | Stand |
|---|---|---|
| Ports, die auf ` PAD/KNOB` oder ` SOUND` enden, unter Windows | Korgs USB-MIDI-Treiber entfernen, Windows' eigener reicht (Wortlaut wie `settings.midi.korgDriver`) | gemessen (Windows, 28.10.) |
| dieselben Ports auf einem anderen System | noch nicht geprüft, MIDI-Bericht ins Discord, keine Ursache genannt | offen (Mac) |
| eine Electribe erkannt, Modus Emulator | oben "Echtes Gerät" wählen; nur dort verbindet die App, auch automatisch | offline (Code), Fall im Discord gelöst |
| eine Electribe erkannt, Modus Echtes Gerät | "Mit Electribe verbinden", automatisches Verbinden in den Einstellungen | offline (Code) |
| ein Port mit "electribe", aber kein Paar | MIDI-Bericht ins Discord | offen |
| kein Port mit "electribe" | einschalten, Datenkabel, anderer USB-Anschluss | hergeleitet |
| Zugriff abgelehnt oder kein Web MIDI | Zugriff erlauben, bzw. die App oder ein Browser mit Web MIDI | offline (Code) |

Kann die Seite nichts lesen (Web MIDI noch nicht erlaubt), fragt sie nach dem Modus und nach den Namen im Bericht.

**Export oder Import zeigt alte Patterns.** Kein Fehler in BLECH ([Messung](messungen/2026-10-28-pattern-export.md)):
EXPORT PATTERN schreibt das gespeicherte Pattern, also erst WRITE; Exporte liegen in `KORG/blechtribe/`, der alte Ordner
bleibt nach der Übernahme mit den alten Kopien stehen, auf der blauen gibt es keine Übernahme und `KORG/electribe/`
bleibt; Gerätedateien tragen immer den 01.01.2014.

**Die volle Prüfung im Patcher wird rot.** Auf das Gerät kommt dann nichts. Vor App 1.3.7 scheitern die Fälle der Patches
an Patterns, die im Emulator gespeichert sind; ab 1.3.7 laufen sie auf einem leeren Flash (`tools/emu/check.py`,
`test/emulator-check-flash.test.mjs`). Die Seite liest die Version der App: darunter, oder im Browser ohne Version,
nennt sie `~/.gelumpe/flash/flash.bin` zum Umbenennen; sonst und danach bittet sie um `~/.gelumpe/emu.log`.

**Was die Seite aus der App liest.** Nur, was die App ohnehin hat, nichts wird am Gerät neu gelesen oder geraten:
die Farbe der angesteckten Electribe (`Session.hardware()`, wie im Patcher), ob dort BLECH läuft (BLECH INFO beim
Verbinden), den Ordner der letzten Datei aus dem Patcher (bis die App geschlossen wird), den MIDI-Bericht und die
Version der App. Bei Farbe und Ordner sagt Blechy, was die App weiß, und markiert die passende Antwort mit "Sagt die
App"; wählen muss die Person selbst. Die Farbe aus `hardware()` folgt der Kennung im Flash; ob eine blaue mit Hacktribe
sich dort als rote meldet, ist offen.

Die Seite spricht mit Leuten, die das Gerät kaum kennen und gerade Angst um es haben: Blechy erklärt
in Alltagssprache, nur die Antworten. Belege stehen hier in der Doku, auf der Seite steht nur eine offizielle Quelle, wo es eine gibt (Debrick-Anleitung von Hacktribe). Was nur zu lesen ist,
folgt nach einer Sekunde von selbst; Knöpfe gibt es nur, wo man etwas tun oder beantworten muss.

Alle Rettungswege liegen in der Firmware selbst. Eine Firmware, die vor ihnen hängt, ist ohne JTAG
nicht zu retten ([Patcher](patcher.md), "Startablauf und warum er tabu ist"). Offen bleibt die
Rettung am Gerät ([Offene Messungen](ideen/offene-messungen.md)).
