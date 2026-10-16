# Blaue Electribe 2 (Synth 2.02): Ladebalken, Kartenordner, Sample-Fehler

Frage: Lassen sich die BLECH-Patches `load-bar`, `blechtribe` und `sample-errors` auf die Synth-Firmware übertragen?
Antwort: keiner der drei, aus drei verschiedenen Gründen. Alles nur offline am Abbild und im Emulator gemessen, kein Gerät.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Das Synth-Abbild hat weder `e2sSample.all` noch `Loading 000%` noch eine Zeichenkette für Sample-Fehler (nur die allgemeinen "Unknown Error." und "Format Error") | gemessen | `re.finditer` über `SYSTEM.VSB` (blau) nach `e2sSample`, `Loading`, `Unknown Error`, `Format Error`; im Sampler stehen `e2sSample.all` bei `0xC00A56C4` und `Loading 000%` bei `0xC00A56F0` |
| Keine der Haken-Stellen von `load-bar` und `sample-errors` (Lader `0xC00364F0`, Stat `0xC0035440`, Text `0xC002D8EC`, Sample-Format `0xC0035FB4`, Slot `0xC004EE0C`) hat einen Treffer in der Adresstabelle | gemessen | `synthaddr.py show` für diese Adressen: "no entry" (nur der Flush `0xC008370C` und `0xC0015DD0` haben welche) |
| Der Synth hat keinen Weg, WAV-Dateien zu lesen: der einzige Benutzer der RIFF/WAVE/fmt/data-Wörter (`0xC00329EC` bis `0xC0032A00`) baut einen Kopf auf den Stapel und öffnet mit Modus `0xA` (schreiben). `WAV File Only` gehört zu EXPORT AUDIO, nicht zu einem Import | gemessen | Literal-Suche (`ldr` nach `0xC0032918/24/38/68`), Disassembly `0xC0032900` bis `0xC0032990`; Menüreihenfolge `EXPORT AUDIO`, `SELECT TYPE`, `WAV File Only`, `Ableton Live Set` |
| Der Synth lädt beim Start ein Ding mit echter Dauer: die PCM-Bank (Flash `0x800000`, 8 MiB) in 127 Übertragungen zum DSP, Ladung bis 5,74 s, Hauptbild 5,9 s mit der eigenen Bank | gemessen | [2026-10-15-synth-samples.md](2026-10-15-synth-samples.md) (`synth_probe.py boot`) |
| Dafür zeichnet die Firmware selbst einen Balken: Bildschirm 38 mit Logo, Schriftzug und einer Leiste unten, die mit der Zeit nach rechts wächst (Länge bei 0,3 s, 2,0 s und 5,0 s: 57, 83 und 106 Pixel), danach Hauptbild (Bildschirm 1) bei 5,95 s | gemessen | Emulator, blaues Abbild, eigene PCM-Bank, Anzeige alle 50 ms gelesen (Zeilen 59 und 60 des Bildspeichers); nur lokal, die Bilder sind Korg-Schirme und liegen nicht im Repo |
| Der Pfad `KORG/electribe/` (`0xC00904D4`) wird von EINER Funktion geliefert (`0xC003256C`, bei Modell `0x123` den Synth-Ordner) und von allen Kartenpfaden benutzt, auch vom Update: `SD:` + `KORG/electribe/` + `System` + `/BOOT.VSB` (gleich für `/USER.VSB`, `/PCM.VSB`, `/SYSTEM.VSB`) | gemessen | Disassembly `0xC002C490` bis `0xC002C4E8` (Aufrufe `0xC00324D8`, `0xC003256C`, `0xC00325B8`, Literal `0xC008F699`); 21 Aufrufer von `0xC003256C` per `bl`-Suche, sieben davon holen gleich danach `System` (`0xC00325B8`): `0xC002C4C8`, `0xC002D5D8`, `0xC002D634`, `0xC0034570`, `0xC0035324`, `0xC003570C`, `0xC0035D54` |
| Eine Umbenennung der Zeichenkette ändert deshalb den Update-Pfad mit; die Vorgabe "Update-Ordner nicht umbenennen" lässt sich so nicht einhalten | hergeleitet | aus der vorigen Zeile |
| Der Platz reicht nicht: `electribe` hat 10 Byte Fenster, `blechtribe` braucht 11; `KORG/electribe/` hat 16, `KORG/blechtribe/` braucht 17. Dahinter folgt sofort `KORG/electribe sampler/` (`0xC00904E4`) | gemessen | String-Tabelle ab `0xC00904AF` gelesen, Länge je String |
| Das Literal `0xC00904E2` zeigt in die Mitte von `KORG/electribe/` (auf das letzte `/`) und wird von zehn Stellen benutzt; ein Umbau der Zeichenkette würde sie ändern. Der Sampler hat das nicht (dort zeigt jedes Literal auf einen Stringanfang, siehe `blechtribe.py`) | gemessen | Literal-Suche über das Abbild (blau), `0xC0032344`, `0xC0032474`, `0xC00374A0`, `0xC0057C8C`, `0xC005A3B4`, `0xC005DDF0`, `0xC007A09C`, `0xC007A854`, `0xC007EA6C`, `0xC007EBF0` |

## Entscheidung je Patch

- **sample-errors: `notNeededOn: ["synth"]`.** Der Synth hat keinen Sample-Lader und keine Sample-Slots, es gibt nichts zu überspringen und keine Stelle für die drei Haken. Prüfung: Zeilen 1 bis 3 der Tabelle.
- **load-bar: nicht portiert, `notNeededOn: ["synth"]`.** Der Sampler-Balken sitzt auf dem Fenster "Loading nnn%" des Sample-Laders (`e2sSample.all`), beides fehlt im Synth (Zeilen 1 und 2). Es gibt zwar eine echte Ladephase (PCM-Bank, knapp 6 s), aber die Firmware zeigt dafür schon einen eigenen Balken (Zeile 5). Ein BLECH-Balken würde nur ein zweites Fenster über das vorhandene legen; das ist ein neues Feature, keine Übertragung, und sollte als eigenes Thema entschieden werden (Fortschritt hieße dort: Zähler der 127 DSP-Übertragungen, Haken bei `0xC001061C` bzw. dem Lader `0xC0046E54`).
- **blechtribe: nicht portiert.** Der Ordnername ist derselbe String wie im Update-Pfad (Zeilen 6 und 7), er passt nicht in sein Fenster (Zeile 8) und wird zum Teil als Teilstring benutzt (Zeile 9). Der Nutzer legt seine `SYSTEM.VSB` also weiter nach `KORG/electribe/System/`. Wer es trotzdem will, müsste die Aufrufer ohne `System` (Pattern, Export) einzeln auf einen neuen String im freien Bereich umbiegen und den Update-Pfad unberührt lassen; das wäre eine eigene Messung und ein eigener Patch.

## Offen

- Ob der Balken von Bildschirm 38 wirklich am PCM-Zähler hängt (er wächst mit der Zeit, passt zur Ladedauer; den Code habe ich nicht gelesen): hergeleitet.
- Ob `0xC003256C` mit einem anderen Modell als `0x123` für den Synth je aufgerufen wird: nicht gemessen, auf dem Synth ist `0x123` der gelesene Wert (Konstante `0xC002C4A8`).
