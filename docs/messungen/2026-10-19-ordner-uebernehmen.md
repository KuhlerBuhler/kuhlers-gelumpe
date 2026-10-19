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
- Nicht mit EXIT beim Einschalten, nicht auf der blauen (`MG_WORK 0`). Arbeitsbereich 4 KiB bei `0xC0190000` (FF in allen drei
  Abbildern).

## Emulator (`tools/emu/migrate_cases.py`, 6 von 6, Hacktribe mit BLECH)

| Fall | Ergebnis |
|---|---|
| `KORG/hacktribe` mit Samples, Import-Datei, Unterordner, `._junk`; MENU | Frage auf Bildschirm 0, nach 2 s alles kopiert außer `._junk`, DONE, dann Hauptbildschirm; der alte Ordner bleibt |
| dasselbe, EXIT | nichts geschrieben, Hauptbildschirm |
| beide Ordner, Rad eine Raste, MENU | electribe sampler kopiert, von hacktribe nichts |
| `KORG/blechtribe` schon da | keine Frage |
| EXIT beim Einschalten | keine Frage, nichts geschrieben |
| leere Karte | keine Frage |

## Offen

- Am Gerät nicht geprüft, auch nicht die Dauer: eine volle `e2sSample.all` hat einige hundert MB, das Kopieren dauert am Gerät
  Minuten (geschätzt, nicht gemessen). Das Display zählt die MB mit.
- Bricht das Kopieren ab (Karte voll, Fehler), bleibt ein halber `KORG/blechtribe` stehen und beim nächsten Start kommt keine
  Frage mehr. Dann den Ordner am Rechner löschen oder fertig kopieren.
