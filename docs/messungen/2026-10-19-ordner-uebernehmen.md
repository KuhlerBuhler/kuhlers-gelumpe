# Alten Kartenordner beim ersten Start übernehmen (19.10.)

Wunsch vom 19.10.: wer BLECH frisch installiert und auf der Karte einen Ordner `KORG/hacktribe` oder
`KORG/electribe sampler` hat, aber keinen `KORG/blechtribe`, soll vor dem Laden gefragt werden, ob der Ordner kopiert
werden soll, damit die Samples weiter da sind. Wählen zwischen beiden Ordnern, oder EXIT, dann startet es normal.

## Was die Firmware dafür hat (Hacktribe 2.02, Disassembly und Emulator)

- FatFs (ältere Reihe mit LFN): `f_opendir` `0xC009E660`, `f_readdir` `0xC009E740`, `f_closedir` `0xC009E728`, `f_open`
  `0xC009DB60` (Modus 1 lesen, `0x0A` neu anlegen und schreiben), `f_read`, `f_write`, `f_close`
  ([Virtuelle SD](../hintergrund/virtuelle-sd.md)).
- **`f_mkdir` ist `0xC009EB00`** (offline: die Funktion hinter `f_unlink`, legt die Einträge `.` und `..` an; gemessen:
  `SD:KORG`, `SD:KORG/blechtribe`, `SD:KORG/blechtribe/Sample` geben 0, die Ordner stehen danach im FAT-Abbild).
- Puffer vom Heap der Firmware: `0xC0028DCC` (new) und `0xC0028DD4` (delete).
- Alle benutzten Funktionen sind in Korgs Original 2.02 Byte für Byte gleich.

## Der Patch (`tools/patch/script_migrate.s`, Laufzeit des BLECH-Menüs)

- Im Haken vor dem Sample-Lader (`0xC0038D34`, gleich nach dem Lesen der Einstellungen): ist `SD:KORG/blechtribe` zu öffnen,
  passiert nichts. Sonst sieht BLECH nach `SD:KORG/hacktribe` und `SD:KORG/electribe sampler`; ist keiner da, auch nichts.
- Die Frage: der Rahmenhaken (UiTask, vor dem Senden) legt das Bild der Laufzeit mit der Frage über den Bildspeicher, der
  Eingangsfilter nimmt alle Tasten, Rad, Regler, Pads und Touchpad (Power-Taste und Netzteil nicht) und gibt EXIT, MENU und
  "anderer Ordner" (Rad, EDIT < >, PART < >) an die wartende Startfunktion. Mit beiden Ordnern stehen Pfeile neben dem Namen.
- MENU: 32 KiB Puffer vom Heap, `KORG/blechtribe` anlegen, dann jede Datei und jeden Ordner kopieren (bis 5 Ebenen, Namen mit
  Punkt am Anfang nicht, das sind `.`, `..` und die `._`-Dateien anderer Rechner). Das Display zeigt COPYING, den Dateinamen und
  die kopierten MB, am Ende 1,5 s DONE oder COPY FAILED. Danach lädt die Firmware die Samples aus dem neuen Ordner.
- Nicht mit EXIT beim Einschalten, nicht auf der blauen (`MG_WORK 0`). Arbeitsbereich 0xF00 Byte bei `0xC0190100` (hinter der Tabelle der Synth-Filter, FF in allen drei
  Abbildern).

## Platz prüfen (19.10., Vorschlag 2)

Vor dem Kopieren zählt ein Probelauf über denselben Baum die nötigen Cluster (jede Datei auf ganze Cluster aufgerundet, ein
Cluster je Ordner) und vergleicht mit den freien Clustern von `f_getfree` (`0xC009E85C`, offline: zählt die freien Einträge der
FAT, nimmt den Wert aus FSInfo, wenn er gültig ist; Clustergröße aus Byte 2 des Volumes). Reicht der Platz nicht, steht 1,5 s
CARD FULL, NOT COPIED da, es wird nichts geschrieben und der Start geht weiter. Beim nächsten Start kommt die Frage wieder.

## Emulator (`tools/emu/migrate_cases.py`, 8 von 8, Hacktribe mit BLECH)

| Fall | Ergebnis |
|---|---|
| `KORG/hacktribe` mit Samples, Import-Datei, Unterordner, `._junk`; MENU | Frage auf Bildschirm 0, nach 2 s alles kopiert außer `._junk`, DONE, dann Hauptbildschirm; der alte Ordner bleibt |
| dasselbe, EXIT | nichts geschrieben, Hauptbildschirm |
| beide Ordner, Rad eine Raste, MENU | electribe sampler kopiert, von hacktribe nichts |
| `KORG/blechtribe` schon da | keine Frage |
| EXIT beim Einschalten | keine Frage, nichts geschrieben |
| leere Karte | keine Frage |
| 64 KiB frei für 180 KB | CARD FULL, nichts geschrieben, Hauptbildschirm |
| 1 MiB frei | kopiert |

## Offen

- Am Gerät nicht geprüft, auch nicht die Dauer: eine volle `e2sSample.all` hat einige hundert MB, das Kopieren dauert am Gerät
  Minuten (geschätzt, nicht gemessen). Das Display zählt die MB mit.
- Bricht das Kopieren trotzdem ab (Lesefehler, Karte gezogen), bleibt ein halber `KORG/blechtribe` stehen und beim nächsten Start
  kommt keine Frage mehr. Dann den Ordner am Rechner löschen oder fertig kopieren.
