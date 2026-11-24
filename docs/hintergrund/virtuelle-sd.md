# Virtuelle SD-Karte im Emulator und die Datei-Funktionen der Firmware

Wie die Firmware mit der SD-Karte umgeht, wie der Emulator eine Karte aus einer Abbilddatei nachbildet und wie sich die
Datei-Funktionen der Firmware über das USB-Kabel aufrufen lassen. Der Emulator selbst steht in
[emulator.md](../emulator.md), Messungen zur Karte am Gerät unter [messungen/](../messungen/).

Alle Adressen gelten für Firmware 2.02 mit [Hacktribe](../glossary.md#hacktribe) (die eigene
[`SYSTEM.VSB`](../glossary.md#vsb)) und den eigenen Flash-Dump. Alles wurde im Emulator beobachtet
(`tools/emu/machine.py`, Unicorn), nicht mit einer echten Karte. Dieses Dokument enthält keine Firmwarebytes, nur
Adressen, Größen und Verhalten.

Markierungen: **gemessen** = im Emulator ausgeführt und beobachtet, **offline gelesen** = Disassembly gelesen,
**hergeleitet** = Schluss aus beidem, **geschätzt** = Annahme mit genannten Voraussetzungen, **offen** = nicht geprüft.

## Überblick

- Eine virtuelle Karte aus einer Abbilddatei reicht aus. Die Firmware erkennt sie, mountet sie, liest und schreibt
  Dateien und Verzeichnisse und ist danach dateisystemkonsistent (`fsck_msdos` ohne Fehler). **gemessen**
- Das Dateisystem der Firmware ist [FatFs](../glossary.md#fatfs). Alles läuft über einen kleinen Controller-Block (MMC0, Polling-FIFO, ein Interrupt), ohne EDMA. **gemessen**
- DATA UTILITY (das Dateimenü der Firmware) funktioniert mit der Karte durchgehend: SOFTWARE UPDATE findet die VSB und schreibt sie in den Flash,
  IMPORT SAMPLE liest eine WAV, EXPORT SAMPLE und EXPORT ALL SAMPLE schreiben auf die Karte, der Neustart lädt
  [`e2sSample.all`](../glossary.md#e2ssampleall) zurück in die Slots. **gemessen**
- Über das Kabel lässt sich die Datei-API der Firmware aus einem Execute-Stub aufrufen (Abschnitt 6).
- Die Firmware importiert beim Start keine einzelnen WAVs, nur `e2sSample.all` (Abschnitt 10).
- Nicht belegt, weil der DSP im Emulator ein Platzhalter ist: dass die PCM-Daten eines importierten Samples beim Export
  wieder herauskommen. Am Gerät **offen**.

## 1. Der SD-Pfad in der Firmware

### Kartenerkennung

- **gemessen:** GPIO 4.1 ist aktiv low. Das Modell hatte den Eingang schon als
  1 (keine Karte) gesetzt; mit 0 startet die Firmware den Kartentreiber. Ohne
  Karte kommt im ganzen Boot kein einziger MMC-Befehl.
- **offline gelesen:** Gelesen wird die Bank 4/5 per Polling an `0xC001C9F0`
  (gemessen rund 8,7 Lesungen je ms Gerätezeit). Es gibt keinen
  Flankeninterrupt für die Erkennung.
- **gemessen:** Mit Karte erscheint ein Kartensymbol neben dem Batteriesymbol.
  Ein Einstecken während des Laufs ist nicht geprüft (Eingang beim Start
  gesetzt). **offen**

### Controller und Treiber

Quelldateien laut Assertion-Texten: `AM180xMMSDCardController.cpp`,
`SDCommand.cpp`, `SDCardDriver.cpp`, `SDCardDriverTask.cpp`.
Registerbelegung wie TI AM1808 MMCSD (Basis `0x01C40000`).

| Funktion | Adresse | Verhalten |
|---|---|---|
| Controller-Init | `0xC00175B0` ff. | MMCCTL Reset, MMCCLK `0x35D` (Teiler 0x5D, langsam), dann `0x105`; MMCTOR `0x1FFFF`, MMCTOD `0xFFFF`; MMCIM `0x600` (DXRDY und DRRDY) |
| Befehl senden | `0xC00178A0` | wartet auf MMCST1 BUSY=0, löscht RSP01..RSP67, schreibt MMCARGHL, dann MMCCMD |
| Befehlswort | `0xC0017C30` | Sprungtabelle über Index 0 bis 0x37; gültig nur 0, 2, 3, 6, 7, 8, 9, 10, 12, 16, 17, 18, 24, 25, 41, 55, alles andere ist eine Assertion (Zeile 0x13B) |
| Antwort abwarten | `0xC00179B0` | MMCST0: Bit 2 RSPDNE ok, Bit 4 TOUTRS = 1, Bit 7 CRCRS = 2 |
| Antwortwort lesen | `0xC0017B28` | liest RSP67, RSP45, RSP23, RSP01 als 16-Bit-Hälften; R1, R3, R6, R7 stehen in RSP67, R2 über alle vier |
| FIFO vorbereiten | `0xC0017E00` (Schreiben), `0xC0017E68` (Lesen) | MMCFIFOCTL Reset, BLEN `0x200`, NBLK |
| Daten schreiben | `0xC0017F18` | wartet auf DXRDY (`0x200`), schreibt MMCDXR 32 Bit |
| Daten lesen | `0xC00180F0` | wartet auf DRRDY (`0x400`), liest MMCDRR 32 Bit, 64 Byte je Aufruf |
| Interrupt | IRQ 16, Handler `0xC0025BD0` | löscht das AINTC-Bit und läuft über `0xC001CFAC` bis `0xC001DB60`: liest MMCST0 (offline gelesen, 2026-10-30), hebt es mit DRRDY oder DXRDY für die Task auf und setzt ihr Ereignis 5 |
| Kartentask | `0xC001D1B0` (Schleife), `0xC001D888` (Zustandsautomat), `0xC001D2B8` (Mount), `0xC001D76C` (Auftragsarten 0 bis 9) | der FS-Code ruft nicht direkt, sondern über diesen Task |

**gemessen:** Der Interrupt muss aus dem Modell kommen, sonst bleibt die
Firmware nach dem ersten Lesebefehl stehen: MMCST0 mit DRRDY und MMCIM `0x600`
genügt, sie liest dann je Interrupt 64 Byte.

### Befehlsfolge (gemessen)

| ms | Befehl | Argument | MMCCMD | Antwort des Modells |
|---:|---|---|---|---|
| 75,6 | CMD0 | 0 | `0x8000` | keine |
| 75,65 | CMD8 | `0x1AA` | `0x208` | R7, Echo `0x1AA` |
| 86,06 | CMD55, ACMD41 | 0, dann `0x40000000` | `0x237`, `0x629` | R1, R3 mit Busy; zweiter ACMD41 mit `0x40FF8000` |
| 86,24 | CMD2, CMD3 | 0 | `0x402`, `0x283` | R2 CID, R6 mit RCA |
| 86,37 | CMD9, CMD10 | RCA | `0x409`, `0x40A` | R2 CSD (v2.0), R2 CID |
| 86,42 | CMD7 | RCA | `0x207` | R1 |
| 86,53 | CMD16 | `0x200` | `0x210` | R1 |
| 86,56 | CMD55, ACMD6 | 2 (4-Bit-Bus) | `0x237`, `0x286` | R1 |
| 87,0 | CMD18 + CMD12 | LBA 0 | `0x12212`, `0x30C` | R1 + 512 Byte, dann R1b |
| beim Schreiben | CMD25 + CMD12 | LBA | `0x12A19`, `0x30C` | R1, einzelne Blöcke |

- **gemessen:** Blockgröße immer 512. Gelesen wird mit CMD18 (Mehrfachblock),
  geschrieben mit CMD25, beides mit CMD12 abgeschlossen, auch bei einem Block.
  CMD17 und CMD24 stehen in der Tabelle, kamen in keinem Lauf vor.
- **gemessen:** Die Firmware schickt CMD8 und ACMD41 mit HCS. Das Modell
  antwortete als SDHC (OCR Bit 30), und die Firmware übergab dann den
  Blockindex als Argument (zum Beispiel `0x27E2` für LBA 10210).
  SDSC (Byte-Adressierung, keine CMD8-Antwort) ist seither nachgebildet und
  mountet (siehe Fehlerfälle der Karte im Emulator-Dokument). **gemessen**
- **gemessen:** Das DMATRIG-Bit steht im Befehlswort für Lesen und Schreiben
  (`0x10000`), im Modell ohne Wirkung. Es wurde kein EDMA programmiert.

### Dateisystem

- **offline gelesen + gemessen:** FatFs von ChaN, ältere Reihe (FIL-Objekt mit
  eigenem 512-Byte-Puffer), mit LFN. Adressen:
  `0xC009C038` check_fs, `0xC009C0F0` chk_mounted (ruft die Kartentask),
  `0xC009DB60` f_open, `0xC009DD74` f_read, `0xC009DFB8` f_write,
  `0xC009E404` f_lseek, `0xC009E3DC` f_close, `0xC009E9B8` f_unlink.
- **gemessen:** FAT16 und FAT32 werden über die Clusterzahl unterschieden
  (ein FAT32-Abbild mit weniger als 65525 Clustern mountet nicht). MBR und
  Superfloppy mounten beide. Mit MBR liest die Firmware LBA 0, dann die
  Partition (LBA 8192 im Test), BPB und FSInfo, dann das Wurzelverzeichnis.
- **gemessen:** Laufwerkspräfix `SD:`. Pfade in der Firmware sind
  `SD:KORG/hacktribe/...` (Maschinentyp 0x124, Sampler) beziehungsweise
  `SD:KORG/electribe/...` (Typ 0x123). Die Pfadbausteine: `0xC0035720`
  (Ordner je Typ), `0xC003568C` (`SD:`), `0xC003576C` (`System`),
  `0xC0035A80` (Pfad der `e2sSample.all`: `SD:KORG/hacktribe/Sample/e2sSample.all`).
- **gemessen:** Der Pfad `KORG/electribe/sampler/e2sSample.all` kommt in dieser
  Firmware nicht vor. Mit Hacktribe-Typ 0x124 ist der Weg `KORG/hacktribe/Sample/`.
  Eine Datei unter `KORG/electribe/sampler/` wurde in keinem Lauf gelesen.
- **gemessen:** Beim Anlegen schreibt FatFs nur dann einen LFN-Eintrag, wenn
  der Name nicht 8.3 in Großbuchstaben ist: `T.WAV` entsteht ohne LFN,
  `501_tst_root.wav` mit.
- **offline gelesen:** Korgs FatFs ist ohne `_FS_LOCK` gebaut: f_open prüft
  keine Sperre, f_close schreibt nur zurück und löscht das Objekt. Offene
  Dateien können also nicht ausgehen. Es ist auch nicht wiedereintrittsfest
  (find_volume sperrt nicht), Korgs Hüllen (`0xC0035440`) rufen es direkt.
  BLECH ruft es aus der SysEx-Task und aus der UI-Task; zwei Dateizugriffe
  gleichzeitig sind ungeschützt (im Emulator nie überlappend gesehen).
- **gelesen:** Status 6 von FILE READ und WRITE (`STATUS_FILE` in
  `tools/patch/blech_sysex.py`) steht für jedes Ergebnis ungleich 0 von
  f_open, f_lseek, f_read oder f_close. Den FatFs-Code selbst verwirft
  `frb_error`; 6 sagt also nur, dass die Karte nein gesagt hat, nicht warum.
- **Byte-Vergleich + gemessen (14.11.):** Kein BLECH-Patch ändert ein Byte an
  Korgs SD-Treiber und Kartentask (`0xC00175B0` bis `0xC001DC00`), diskio
  (`0xC003F000` bis `0xC0041000`) oder FatFs (`0xC009B000` bis `0xC009F200`),
  geprüft auf develop und release/1.4.6 gegen Hacktribe 2.02. Im Emulator ist
  der Verkehr am Kartencontroller beim Start ohne Karte und bei der ersten
  Initialisierung nach spätem Stecken gleich mit BLECH, mit EXIT beim
  Einschalten und mit Hacktribe pur. Grenze: die Emulator-Karte ist ideal
  (kein ACMD41-Busy); ob Hacktribe pur nach einem Start ohne Karte am Gerät
  genauso hängt (#518), ist ungeprüft.

## 2. Wann die Firmware die Karte anfasst

| Zeitpunkt | Was | Beleg |
|---|---|---|
| ab 75 ms nach Reset | Controller-Init, Kartenfolge, Mount | gemessen |
| rund 87 bis 93 ms | MBR, BPB, FSInfo, Wurzel, `KORG`, `KORG/hacktribe`, `KORG/hacktribe/Sample` | gemessen, 9 Sektoren |
| rund 346 bis 390 ms | dieselbe Verzeichniskette noch zweimal, dann die Kopfsektoren der `e2sSample.all` und bei vorhandener Datei ihr Inhalt | gemessen; mit der aus "EXPORT ALL SAMPLE" entstandenen Datei (14928 Byte) ist der Slot nach dem Boot identisch zu vor dem Neustart, Aktiv-Byte 1 |
| im Betrieb | keine Zugriffe, solange DATA UTILITY, EVENT REC/PLAY oder Pattern-Import nicht laufen | gemessen (Kartenlog über 8 s Leerlauf nach dem Boot) |
| DATA UTILITY, Seite 14/14 SOFTWARE UPDATE | ENTER zeigt "Now Version / Next Version", dazu liest sie den Kopf der VSB aus `KORG/hacktribe/System/SYSTEM.VSB` | gemessen |
| zweites und drittes ENTER | "Are You Sure ?", dann Update | gemessen |
| Start mit fehlender Kennung bei Flash `0x220000` (Startmodus 10) | nach ENTER Mount, dann nur `System/SYSTEM.VSB` an der Kartenwurzel (ohne `KORG`) | gemessen, siehe Abschnitt 5 |

**gemessen:** Mit Karte sieht das Display im Standardfall (160.0, 001 Init
Pattern, Part:01) so aus wie ohne, nur das Kartensymbol kommt dazu.

## 3. Das Kartenmodell im Emulator

Umsetzung als Unterklasse von `Machine`, die `_rd`, `_wr`, `lines` und die
Flash-Klasse (nur zum Zählen von Erase und Program) überschreibt. Das Modell
steht in `tools/emu/sdcard.py`, der FAT-Schreiber und -Leser in
`tools/emu/fat32.py`, die Abbildverwaltung in `tools/emu/cardstore.py`.
Es besteht aus:

- **Kartenzustand:** CMD0 setzt zurück, CMD8 antwortet R7 mit Echo, CMD55
  setzt ein App-Flag, ACMD41 liefert OCR `0x00FF8000` mit HCS und nach dem
  zweiten Aufruf Bit 31, CMD2 CID, CMD3 RCA `0x1234` (R6), CMD9 CSD v2.0 mit
  C_SIZE aus der Abbildgröße, CMD7, CMD16, ACMD6 (nur quittiert), CMD12,
  CMD17/18 und CMD24/25 mit Blockindex als Argument. CRC wird nicht geprüft
  und nicht erzeugt (Antworten ohne CRC, wie es der Controller ohnehin
  abschneidet).
- **Register:** MMCCMD löst aus. MMCST0 ist sofort gesetzt: RSPDNE (`0x4`) für
  jede Antwort, TOUTRS (`0x10`) für unbekannte Befehle, DATDNE (`0x1`) am
  Blockende; die Pegelbits DRRDY (`0x400`) und DXRDY (`0x200`) kommen aus dem
  Zustand der Puffer. Alle anderen Register bleiben im vorhandenen
  Registerspeicher. Antwort in RSP01..RSP67 wie in Abschnitt 1.
- **Daten:** MMCDRR liefert 4 Byte je Lesezugriff aus einem 512-Byte-Puffer,
  MMCDXR nimmt 4 Byte je Schreibzugriff, bei 512 Byte geht der Block ins
  Abbild. NBLK zählt Blöcke bei CMD18/25.
- **Interrupt:** in `lines()` (zwischen den Scheiben): ist
  `MMCST0-Pegel & MMCIM` nicht null, wird AINTC-Leitung 16 gesetzt. Das
  entspricht dem Pegelverhalten und kostet pro 64-Byte-Block einen Interrupt.
- **Karte vorhanden:** GPIO 4.1 auf 0.
- **Abbild:** `bytearray` im Speicher aus einer Datei, schreibend oder mit
  `ro=True` (Schreibzugriffe werden verworfen und gezählt).
- **Abbildbau und Gegenprobe:** ein eigener FAT32-Schreiber mit LFN, MBR oder
  Superfloppy, und ein Leser, der Firmware-Schreibzugriffe auf dem Abbild
  zurückliest. Unabhängige Gegenprobe: `fsck_msdos -n` auf dem Abbild, ohne
  Befund vor und nach den Firmware-Schreibzugriffen.

Der Dienst bedient die Karte über Routen unter `/sd` (`tools/emu/server.py`),
die Seite dazu ist `site/app/sdcard.mjs`. Die Abbilddatei ist der Kern, nicht
ein synthetisiertes Dateisystem: Der Controller arbeitet auf einem Blockgerät
(`read(lba)`, `write(lba, data)`), eine Datei ist das einfachste Blockgerät, und
`fsck` sowie jedes Hostwerkzeug sind eine Gegenprobe. Firmware-Fehler (halb
geschriebene Verzeichnisse) zeigen sich so wie am Gerät.

### Wie weit die Firmware kommt (alle Läufe gemessen)

| Stufe | Ergebnis |
|---|---|
| Karte erkannt | ja, Symbol in der Statuszeile |
| Mount | ja, MBR und Superfloppy |
| Verzeichnisse lesen | ja, inklusive LFN-Namen mit Leerzeichen und 9+ Zeichen |
| Datei lesen | ja (e2sSample.all-Kopf beim Boot, WAV beim Import, VSB beim Update) |
| Datei schreiben, anlegen, löschen, Ordner anlegen | ja (Export, Datei-API, `KORG/hacktribe/Sample` wird bei Bedarf angelegt) |
| Kartendateisystem danach konsistent | ja (`fsck_msdos`) |

### Tests

Kartenmodell (Befehle, Antworten, Blockzugriff) und der FAT-Schreiber und
-Leser sind reine Python-Tests (`tools/emu/test_sdcard.py`, `test_fat32.py`,
`test_cardstore.py`). Die Läufe mit Firmware (Boot, Import, Export, Update, auch
über die Routen des Dienstes und das Bedienfeld) stehen in
`test/emulator-card.test.mjs` (`npm run test:emu`, mit `E2_VSB` und `E2_FLASH`)
und arbeiten mit selbst erzeugten Karten.

## 4. Tempo und Risiken des Kartenmodells

- **Tempo, gemessen:** Das Modell liefert 64 Byte je Interrupt, rund 0,8 ms je
  Sektor Gerätezeit (rund 640 KB/s). Für eine große `e2sSample.all` (25 MB)
  wären das über 40 s im Boot. **hergeleitet:** Abhilfe wie beim Flash-Lesen in
  `machine.py` (`_flash_read`): die PIO-Lesefunktion `0xC00180F0` und
  Schreibfunktion `0xC0017F18` abfangen und den Block auf einmal kopieren. Das
  verlässt den Registerpfad und wäre nur für Tempo gedacht, mit Umschalter,
  damit die Registerlinie geprüft werden kann.
- **Schreiben:** Die Firmware schreibt Verzeichnisse und FAT jeweils sofort
  (CMD25 je Block, keine Zusammenfassung). Wird der Emulator mitten in einem
  Export gestoppt, ist das Abbild halb geschrieben wie bei einem Stromausfall.
  Der Dienst darf das Abbild nur beim sauberen Anhalten herausgeben oder muss
  "Karte in Benutzung" melden.
- **Netzteil:** Ohne Netzteil-Schalter scheitert jedes Update scheinbar
  ("Battery Low"), siehe Abschnitt 5. Der Dienst braucht dafür einen
  eigenen Schalter.
- **Nachbildung:** CRC, Schreibschutz (GPIO 4.0), Timeouts, Lese- und
  Schreibfehler sind im Emulator nachgebildet; was die Firmware daraus macht
  ("Card Error", "Card Write Protected"), steht unter Fehlerfälle der Karte in
  [../emulator.md](../emulator.md). "Card Removal" ist weiter ungeprüft.
- **Typen:** Karten über 1 GiB und exFAT sind ungeprüft. FatFs
  unterscheidet FAT12/16/32 nur nach der Clusterzahl; ein falsch gebautes Abbild
  mountet ohne Fehlermeldung nicht.
- **Urheberrecht:** Echte Karten enthalten Korg-Daten. Abbilder mit
  Korg-Dateien dürfen nie ins Repo, Tests brauchen selbst erzeugte.

## 5. DATA UTILITY und SOFTWARE UPDATE mit der virtuellen Karte

Bedienung in der Firmware (Panel-Nachrichten wie in `data/panel.mjs`): MENU
(0x09) öffnet das Pattern-Menü, Edit◄ (0x08) zweimal geht auf Seite 28/29
"DATA UTILITY", MENU ist ENTER und öffnet die 14 Funktionen, Edit► blättert:
1 EXPORT PATTERN, 2 EXPORT ALL PATTERN, 3 IMPORT PATTERN, 4 IMPORT ALL
PATTERN, 5 INITIALIZE PATTERN, 6 EXPORT AUDIO, 7 EXPORT P.SET AUDIO,
8 EXPORT CHAIN AUDIO, 9 IMPORT SAMPLE, 10 EXPORT SAMPLE, 11 EXPORT ALL SAMPLE,
12 CARD FORMAT, 13 FACTORY RESET, 14 SOFTWARE UPDATE. Ohne Sample steht bei 10
"No Sample". **gemessen** Bildschirm- und Menüzustände:
[2026-10-09-menuezustand.md](../messungen/2026-10-09-menuezustand.md).

### SOFTWARE UPDATE

- **gemessen:** Eine Kopie der eigenen `SYSTEM.VSB` unter
  `KORG/hacktribe/System/SYSTEM.VSB` (nur im Abbild der Messung) wird gefunden.
  Das Display zeigt "Now Version: 2.02, Next Version: 2.02".
- **gemessen:** Ohne Netzteilmeldung (Panel-Nachricht 7 auf 0, Standard von
  `Machine`) zeigt der dritte ENTER "Warning, Battery Low" und tut nichts. Mit
  `m.adapter = True` läuft das Update. Der Dienst startet das Gerät darum am
  Netzteil.
- **gemessen:** Am Netzteil ignoriert die Firmware den Netzschalter, das Gerät
  läuft 4 s nach dem Halten weiter. Der Dienst meldet deshalb vor dem Halten
  Batterie, dann schaltet die Firmware ab wie ohne Netzteil.
- **gemessen:** Ablauf mit Netzteil: 4118 Sektoren gelesen (2 MiB VSB plus
  Verzeichnisse), 512 Erase-Befehle `0x20` zu 4 KiB und 8192 Seiten zu
  256 Byte, geschrieben in `[0x20000, 0x220000)`; Anzeige "Working..." und
  danach "OK. Please Reboot.". Gerätezeit rund 3 bis 4 s; im Emulator Erase und
  Program ohne Zeitbedarf.
- **gemessen:** Mit einer anderen VSB (711 Byte Unterschied zur laufenden) ist
  der Flash danach in diesem Bereich gleich der neuen Nutzlast (0 Byte
  Unterschied), neun 4-KiB-Sektoren verändert, **außerhalb des Bereichs
  nichts**. Der Emulator startet danach aus der neuen Nutzlast
  (`flash[0x20000:0x220000]` als Abbild) bis zum Hauptbildschirm ohne
  Assertion. Das ist ein Emulator-Neustart, kein Bootloader-Test.
- **offline gelesen:** Der Bootloader (Flash `0..0x20000`) enthält keine SD-,
  FAT- oder Dateinamen-Strings. Die Update-Abfrage beim Start ist Code der VSB,
  nicht des Bootloaders. Der Bootloader selbst fasst keine Karte an.
- **gemessen:** Das Update schreibt nichts auf die Karte (Prüfung mit
  schreibgeschütztem Abbild: 0 Schreibzugriffe).
- **offen:** Wie die Firmware ein fehlerhaftes oder abgebrochenes Update
  behandelt (Prüfsumme der VSB, Verify Error); im Emulator nur der Gutfall.

### Update beim Start (Startmodus 10)

- **gemessen:** Mit gelöschter Kennung bei Flash `0x220000` zeigt die Firmware
  "SOFTWARE UPDATE, press ENTER" (Karte erkannt). Erst ENTER startet den
  Kartentreiber (vorher kein MMC-Befehl).
- **gemessen:** In diesem Zustand sucht sie `System/SYSTEM.VSB` an der
  **Kartenwurzel**, ohne `KORG/...`. Der Maschinentyp ist dort noch nicht aus der
  Kennung gesetzt, und die Pfadfunktion `0xC0035720` liefert für unbekannte
  Typen einen leeren Ordner. Der Pfad `KORG/electribe sampler/System/SYSTEM.VSB`
  wurde nicht gesehen, und dieser Text kommt in der VSB nicht vor.
  **hergeleitet:** Er stammt aus einem anderen Pfad (die Bootmaschine des Werks
  oder die Anleitung), nicht aus dem Hacktribe-Code der VSB.
- **gemessen:** Mit `System/SYSTEM.VSB` an der Wurzel liest sie die Datei an und
  meldet "Error, Invalid File", mit beiden getesteten VSBs. Warum, ist
  **offen**. Die Namensliste `BOOT`, `SYSTEM`, `USER`, `PCM`, `SLICE`
  (`0xC0030B40`) deutet auf einen Satz mehrerer VSBs hin; der Test hatte nur
  eine Datei. Ohne `System`-Ordner an der Wurzel kommt "Error, No File".

## 6. Datei-Funktionen der Firmware übers Kabel

Die Funktionen lassen sich aus einem Execute-Stub aufrufen (Hacktribes [SysEx](../glossary.md#sysex)-Befehle `0x53`/`0x54`/`0x52`/`0x57`); die
BLECH-eigenen Dateibefehle in `tools/patch/blech_sysex.py` benutzen dieselben Funktionen.

### Die Datei-API der Firmware, aufgerufen aus einem Execute-Stub

Alle Funktionen wurden **gemessen** aus einem Stub aufgerufen (Adressen aus dem
Build 2.02 mit Hacktribe).

| Zweck | Adresse | Argumente (ARM, r0 bis r3) | Rückgabe |
|---|---|---|---|
| Öffnen | `0xC009DB60` | r0 FIL* (Objekt, hergeleitet rund `0x224` Byte, im Test `0x240` reserviert), r1 Pfad `SD:/...` (C-String), r2 Modus: 1 lesen, `0xA` schreiben und neu anlegen | 0 = ok |
| Schreiben | `0xC009DFB8` | r0 FIL*, r1 Quelle, r2 Länge, r3 `uint32*` für geschriebene Bytes | 0 = ok |
| Lesen | `0xC009DD74` | r0 FIL*, r1 Ziel, r2 Länge, r3 `uint32*` für gelesene Bytes | 0 = ok |
| Positionieren | `0xC009E404` | r0 FIL*, r1 absoluter Offset | 0 = ok |
| Schließen (schreibt Verzeichniseintrag und FAT mit) | `0xC009E3DC` | r0 FIL* | 0 = ok |
| Löschen | `0xC009E9B8` | r0 Pfad | 0 = ok |
| Ordner anlegen | unter `KORG/hacktribe/Sample` macht es die Firmware selbst beim Export (`0xC0035504`) | | |

- **gemessen:** Ein Stub öffnet mit `0xA`, schreibt, schließt: 9644 Byte WAV,
  alle Rückgaben 0; das Abbild enthält danach die Datei, auf dem Host Byte für
  Byte gleich; `fsck_msdos` ohne Befund. Lesen derselben Datei mit Modus 1 in
  einen RAM-Puffer, dann `0x52` zum Holen: gleich dem Hostlesen (10832 Byte).
  Löschen mit `0xC009E9B8`: Datei danach weg.
- **gemessen:** Ein Pfad ohne `/` (zum Beispiel `SD:t.wav`) schreibt und liest
  korrekt, aber der Importer leitet den Samplenamen aus dem Teil nach dem
  letzten `/` ab (`0xC0035A20`, bis zum Punkt, höchstens 16 Zeichen, Abbruch bei
  Zeichen ab `0x80`): ohne `/` bleibt der Name leer. Immer `SD:/name.wav` oder
  einen Pfad mit Ordner übergeben.
- **offline gelesen:** Kein eigener Flush der FAT außer dem Schließen: `f_close`
  ruft das Sync. Ein getrenntes `f_sync` ist nicht gefunden (nicht gesucht).
  Schließen vergessen heißt: Verzeichniseintrag und Größe fehlen.

### Läuft das aus einem Execute-Stub?

- **gemessen:** Ja. Der Stub kommt durch Hacktribes 0x57 (`0xC017074C`: ruft die
  Adresse aus `*0xC06BD84C`, danach geht es über `0xC0026554` weiter). Der Stub
  läuft im **Task-Kontext** (CPSR `0x...53`, Supervisor-Modus, IRQ an, eigener
  Stack bei `0xC0208F60`), nicht in einem Interrupt. Ein blockierender
  Dateiaufruf blockiert diese Task. Der Kartentreiber ist eine eigene Task
  (Stack `0xC0311F80`), die über Auftrag und Semaphore antwortet. Das Ganze lief
  im Emulator ohne Assertion.
- **gemessen:** Execute antwortet erst, **wenn der Stub zurückkehrt, und nur, wenn
  r0 bei der Rückkehr 1 ist**. Mit r0 = 2 kam gar keine Antwort (`0x21` bleibt
  aus). Stubs also mit `mov r0, #1` beenden. Der Importer-Aufruf (unten) braucht
  im Emulator rund 1 s Gerätezeit, der Execute-Befehl antwortet erst danach; der
  Host muss entsprechend lang warten (im Test bis 60 s).
- **gemessen, wichtig:** `0xC1000000` ist der **Eingangspuffer jeder
  `0x54`-Nachricht**: wer an eine andere Adresse schreibt, überschreibt trotzdem
  die ersten Bytes bei `0xC1000000` mit seinen Daten. Wenn der Stub dort liegt,
  muss er als **letztes** hochgeladen werden, nach allen anderen Daten (Pfade,
  Befehlsblock, Nutzdaten). Das fällt erst mit mehreren Uploads auf
  (Muster der Execute-Stubs: [2026-10-08-led-execute.md](../messungen/2026-10-08-led-execute.md)).
  Der Nutzdatenbereich im Test: `0xC1001000` (Befehle), `0xC1001100`
  (Ergebnis), `0xC1002000` (FIL-Objekt), `0xC1003000` (Daten), `0xC1010000`
  (Lesepuffer), alle im Hook-Upload-Bereich des Shared Buffer.
- **offen:** Ob das am echten Gerät genauso gilt (Stackgröße der Task, ob
  SD-Zugriffe die Echtzeitaufgaben dieser Task stören).
- **Sperren, offline gelesen:** Im Prolog von `f_open` und `chk_mounted` ist
  kein Betriebssystem-Mutex zu sehen (nicht erschöpfend gesucht). FatFs ist ohne
  Wiedereintritt gebaut. **hergeleitet**, nicht ausgelöst: Ein Stub-Dateizugriff
  **gleichzeitig** mit einer Datei-Aktion der Oberfläche (DATA UTILITY, Start-Laden
  von `e2sSample.all`, EVENT REC) kann das Dateisystem durcheinander bringen. Die
  Oberfläche (UI-Task) und die Execute-Task sind verschiedene Tasks. Folge: nur
  ausführen, wenn das Gerät im Hauptbildschirm steht und keine Karten-Aktion
  läuft (Prüfung über den Bildschirm-/Menüzustand, siehe
  [2026-10-09-menuezustand.md](../messungen/2026-10-09-menuezustand.md)).
- **offline gelesen:** Die UI-Aktionen von DATA UTILITY laufen in der UI-Task
  (Import-Handler `0xC0038D80`, Export-Handler `0xC003A108`, Methoden eines
  Befehlsobjekts, das die UI-Task anlegt).

### Importweg und Weg zu `e2sSample.all`

**WAV auf die Karte und IMPORT SAMPLE**

- **gemessen:** DATA UTILITY, Seite 9 IMPORT SAMPLE, ENTER: ein
  **Dateibrowser ab der Kartenwurzel**, zeigt Ordner (`KORG`, `Sample`) und
  `.wav`-Dateien ohne Endung. Die Datei darf **überall** auf der Karte liegen.
  Mit dem Drehgeber VALUE (Panel-Nachricht `01 00 00 delta`) wählen, ENTER (MENU)
  öffnet Ordner oder die Datei.
- **gemessen:** Danach "Select Destination, 501" (Vorschlag: erster freier
  Slot der Nutzerbank), ENTER, dann "IMPORT SAMPLE, OK" nach rund 1 bis 6 s
  Gerätezeit. Gelesen werden die Sektoren der Datei (19 für eine WAV von
  9644 Byte).
- **gemessen:** WAV mono 16 bit 48 kHz wird akzeptiert; die Firmware schreibt
  Slotdaten (Name, Rate 48000, Aktiv-Byte 1) in die RAM-Tabelle bei
  `0xC036AD88 + Slot * 1116`. Der Import legt **nichts auf der Karte** an und
  ändert `e2sSample.all` **nicht**.
- **offline gelesen:** Der Importer erkennt `RIFF`, `WAVE`, `fmt `, `data` und
  optional `korg` und `esli` (Loopdaten); 44.100 und 48.000 Hz, mono und stereo
  laufen laut früherer Messung
  ([2026-10-08-usb-sample-import-offline.md](../messungen/2026-10-08-usb-sample-import-offline.md)).

**Direkt über das Kabel ohne Knopfdruck**

- **gemessen:** Der Importer ist aus einem Stub aufrufbar:
  `0xC003644C(Pfad, Slot-1)` liefert 0 und füllt den Slot; danach
  `0xC009A0A8(Slot-1)` (dieselbe Folge wie der UI-Handler `0xC0038D80`, ebenfalls
  0). Der Slot ist danach im DATA-UTILITY-Menü "EXPORT SAMPLE, SELECT SAMPLE 501"
  sichtbar; der Name kommt aus dem Dateinamen (bei Pfaden mit `/` gemessen am
  Namen der Exportdatei, ohne `/` leer). Argumente: r0 Pfad (C-String,
  `SD:/...`), r1 Slotnummer ab 0; bei negativem r1 sucht die Funktion selbst
  einen freien Slot (`0xC004EF94`, **offline gelesen**).
- **gemessen:** Mit einem nicht belegten Slot ging es; ein belegter Slot wurde
  nicht geprüft. **offen** (Überschreiben, Platz im DSP-Speicher: "Memory Full"
  und "Card Full"-Texte existieren).
- **hergeleitet:** Der RAM-Weg (Importer mit einer WAV im RAM statt auf der
  Karte, wie in [2026-10-08-usb-sample-import-offline.md](../messungen/2026-10-08-usb-sample-import-offline.md))
  wird nicht gebraucht, wenn man die Karte nutzt: WAV auf die Karte, dann der
  Importer. Das braucht keinen Dateiobjekt-Ersatz.

**Von RAM zu `e2sSample.all`**

- **gemessen:** Das Gerät schreibt `e2sSample.all` ausschließlich über
  **DATA UTILITY, 11 EXPORT ALL SAMPLE** (`0xC0039E68`): Kopf 4096 Byte, je
  Sample 1232 Byte Metadaten plus PCM (Beispiel: ein Sample von 4800 Frames gibt
  14928 Byte). Ziel: `KORG/hacktribe/Sample/e2sSample.all`.
- **gemessen:** Der Boot liest genau diese Datei zurück (Verzeichnisse
  `KORG/hacktribe/Sample`, dann die Datei; 350 bis 390 ms) und stellt den Slot
  wieder her, byteweise gleich dem Stand vor dem Neustart (Slot 501, Aktiv-Byte 1).
- **gemessen:** Der Aufruf von `0xC0039E68` mit einem leeren Ersatzobjekt stürzt
  ab (Lesezugriff auf nicht abgebildeten Speicher): die Funktion braucht ein
  echtes Befehlsobjekt der UI. **Daher nur über die Oberfläche.** Das ist die
  offene Frage für "ohne Knopfdruck".
- Der Weg "WAV via Kabel, DATA UTILITY importieren, EXPORT ALL SAMPLE, Neustart"
  ist durchgängig im Emulator belegt. Ein Weg "Sample im RAM-Puffer, dann in
  `e2sSample.all`" hat keinen Direktaufruf; er müsste über Importer und die
  UI-Aktion gehen oder die Datei selbst im Hostformat bauen (Layout nur aus einem
  Beispiel bekannt, nicht nachgeprüft). **offen**

## 7. Kartengrößen: die R2-Antwort war im Modell verdreht

- **gemessen:** Das erste Modell legte die Antwort auf CMD9 (CSD) so in die
  Register, dass das untere Ende des CSD in RSP7 lag und das obere in RSP0. Die
  Firmware baut sich daraus einen 16-Byte-Puffer und liest die Kartengröße aus
  Byte 7 bis 9 (`0xC001B85C` bis `0xC001B8A4`, `C_SIZE`); bei mehr als `0xFFFE`,
  also ab 32 GiB, setzt sie einen Merker (`+0x15B`, hergeleitet: "zu groß"), und
  danach kommt kein Lesebefehl mehr. Der Puffer der Firmware war das CSD
  rückwärts nach 16-Bit-Hälften. Bei 128 MiB ging das nur gut, weil `C_SIZE` dort
  in einem Byte steht und die Rechnung zufällig unter der Grenze blieb.
- **gemessen:** Mit RSP7 als oberen 16 Bit (Bit 127) und RSP0 als unteren
  (Bit 0) ist der Puffer der Firmware gleich dem gesendeten CSD, Byte für Byte
  (Haken auf `0xC001B85C`, Puffer gelesen). Der Test in
  `tools/emu/test_sdcard.py` hält das fest.
- **gemessen:** Vorher nahm die Firmware Karten über 128 MiB nicht an: nach
  CMD16 und ACMD6 kam kein Lesebefehl mehr (192, 256, 384, 512, 1024 MiB).
  Nachher mountet sie 64, 128, 192, 256, 512 und 1024 MiB (CMD18 kommt, MBR und
  Verzeichnisse werden gelesen). IMPORT SAMPLE, EXPORT SAMPLE und ein
  anschließendes `fsck` liefen bei 64, 128 und 512 MiB; 192, 256 und 1024 MiB nur
  bis zum Mount. Der Dienst bietet 128, 256 und 512 an. FAT-Cluster wachsen mit
  (512 Byte bei 64 MiB, 1 KiB bei 128, 4 KiB bei 512).
- **offen:** SDSC-Adressierung, Karten über 1 GiB, Schreibschutz.

## 8. Dateien, die die Firmware schreibt

- **gemessen, Karte frisch formatiert vom Dienst, nur eine WAV im
  Wurzelordner:**
  - IMPORT SAMPLE zeigt die WAV im Dateibrowser, Slot 501, "OK".
  - EXPORT SAMPLE: `KORG/hacktribe/Sample/501_<Name>.wav`, 10832 Byte. Die
    Firmware legt `KORG`, `hacktribe` und `Sample` selbst an. Der Eintrag steht
    schon mit Größe 0 im Verzeichnis, solange sie schreibt; die Größe kommt erst
    mit dem Schließen. Wer von außen liest, muss auf die Größe warten, nicht nur
    auf den Namen.
  - EXPORT ALL SAMPLE: `KORG/hacktribe/Sample/e2sSample.all`, 4096 + je Sample
    (1232 + PCM) Byte; bei drei Samples zu 4800 Frames 36592 Byte.
  - EXPORT ALL PATTERN: **`KORG/hacktribe/electribe_sampler_allpattern.e2sallpat`**,
    4161792 Byte. Das Pattern-Backup liegt also eine Ebene höher als die Samples,
    direkt in `KORG/hacktribe/`, nicht in einem `Pattern`-Ordner.
  - `fsck_msdos -n` auf dem Abbild nach allen diesen Schreibzugriffen: ohne
    Befund (zwei unabhängige Prüfer: `fat32.py check` und `fsck_msdos`).
- **gemessen, Ordner als Karte:** Ein Ordner `my samples/drums/snare hit.wav`,
  einmal in die Karte kopiert: die Firmware zeigt den Ordner `drums`, dazu "Upper
  Folder" und die Datei, importiert sie (Slot 501 "snare hit") und exportiert sie
  als `501_snare hit.wav`. Der Browser steht beim Öffnen eines Ordners auf "Upper
  Folder"; die Datei braucht einen Dreh am VALUE-Regler.
- **gemessen, CARD FORMAT (DATA UTILITY 12):** Auf Karten mit 128, 256 und 512 MiB
  fragt die Firmware "Are You Sure ?" und lehnt dann ab: "Error, Not Supported
  Size" (bei 128 MiB im Display gesehen), kein einziger Schreibzugriff. Auf einer
  Karte mit 1 GiB formatiert sie (908 Sektoren geschrieben) und legt **FAT16** an
  (MBR-Typ `0x06`, 65508 Cluster); `fsck_msdos` ist damit zufrieden. Der Dienst
  liest nur FAT32 und sagt das dann in der Seite, das Abbild lässt sich weiter
  laden. **offen:** ob eine echte Karte ab 4 GiB (SDHC) FAT32 bekommt, hier nicht
  nachgebildet.

## 9. `KORG/hacktribe` in `blechtribe` umbenennen

Fragen: alle Pfadstrings, Längen, Platz dahinter, passt ein Datenpatch am selben
Ort, was muss sonst ändern, was wird aus einer echten Karte.

### Die Zeichenketten (offline gelesen, Adressen aus dem Abbild)

Im ganzen ARM-Abbild kommt `hacktribe` genau zweimal vor, beide in einer Tabelle
von Pfadbausteinen bei `0xC00A5639`:

| Zeichenkette | RAM | VSB-Offset | Länge | Platz bis zum nächsten String | Zeiger darauf |
|---|---|---|---:|---:|---|
| `hacktribe` | `0xC00A5656` | `0xA5756` | 9 | 18 Byte (bis `0xC00A5667`) | `0xC0035714`, gelesen von `0xC00356D4` (Maschinentyp 0x124) |
| `KORG/hacktribe/` | `0xC00A5678` | `0xA5778` | 15 | 24 Byte (bis `0xC00A568F`, dann `System`) | `0xC0035760`, gelesen von `0xC0035720` (Typ 0x124) |

Die Geschwister für den Typ 0x123 (`electribe`, `KORG/electribe/`) liegen davor;
für andere Typen liefert `0xC0035720` einen leeren String (`0xC00A65D1`). Gleich
bleibt, was kein Ordnername ist: `electribe_sampler_allpattern.` (`0xC00A47C8`,
Dateiname), `e2sSample.all`, `Sample/`, `System`, `PatternSet`, `e2spat`,
`e2sallpat`, `e2sev`.

- **Wer die Zeichenketten braucht:** `0xC0035720` hat 24 Aufrufstellen (alle Pfade
  der Form `SD:` + Ordner + ...), `0xC003576C` (`System`) hat 8, der Name allein
  (`0xC00356D4`) genau eine, in `0xC0035458`, das `SD:KORG` und
  `SD:KORG/hacktribe` anlegt. Mehr Stellen mit dem Ordnernamen gibt es nicht
  (Zeigerwörter und Aufrufer vollständig durchsucht, auch UTF-16 und
  `tribe`/`hack` einzeln).
- **Keine Längenkonstanten:** Beide Funktionen bauen einen `std::string` aus dem
  Literal (`0xC00A324C`, `strlen` zur Laufzeit). Es gibt keine Zeiger-, Längen-
  oder Pufferkonstanten, die mit ändern müssten. Auch kein geteiltes Ende mit
  anderen Strings: die Zeigerwörter in die Tabelle zeigen auf `/` am Ende von
  `KORG/electribe/` (`0xC00A5676`), nie in die zwei Strings hier.

### Passt ein Datenpatch an derselben Stelle?

- **Ja, gemessen.** `KORG/blechtribe/` hat 16 Zeichen plus NUL, 17 Byte in 24;
  `blechtribe` hat 10 plus NUL, 11 in 18. Geändert werden 21 Byte, sie stehen als
  zwei Läufe in der Datei: `0xA5756` (10 Byte) und `0xA577D` (11 Byte; `KORG/`
  bleibt, das NUL steht schon). Die Dateigröße bleibt `0x200100`.
- **gemessen mit dieser Änderung im Emulator:** Beide Zeichenketten ersetzt,
  sonst nichts.
  - EXPORT SAMPLE, EXPORT ALL SAMPLE und EXPORT ALL PATTERN schreiben nach
    `KORG/blechtribe/Sample/...` und
    `KORG/blechtribe/electribe_sampler_allpattern.e2sallpat`; die Firmware legt
    `blechtribe` selbst an.
  - Neustart auf dieser Karte: `e2sSample.all` aus `KORG/blechtribe/Sample` wird
    gelesen, der Slot ist wieder da (gleich dem Stand vor dem Neustart).
  - SOFTWARE UPDATE (DATA UTILITY 14) sucht `KORG/blechtribe/System/SYSTEM.VSB`:
    dort liegend "Now Version 2.02 / Next Version 2.02", unter dem alten Pfad
    "Error, No File".
  - Der Rettungsweg beim Start (Update-Abfrage bei fehlender Kennung) sucht an der
    Kartenwurzel `System/SYSTEM.VSB`, ohne Typordner: unberührt.
- **gemessen, `tools/emu/check.py`:** `check.py --base ... --patched ... --allow
  0xa5778:17` besteht alle 17 Startwege. Ohne `--allow` meldet `start_phase` die
  11 Byte bei `0xA577D`: die Firmware liest das Literal `KORG/hacktribe/` schon im
  Start (auch ohne Karte), den Namen allein (`0xA5756`) nicht. Der Patch ist also
  eine Datenänderung mit erlaubter Spanne, keine neue Art von Patch. Im Format von
  [../patcher.md](../patcher.md): zwei rohe Änderungen mit Prüfsumme der ersetzten
  Bytes.

### Folge für eine echte Karte mit `KORG/hacktribe/Sample/e2sSample.all`

- **gemessen:** Die umbenannte Firmware findet sie nicht. Beim Start sieht der
  Slot 501 leer aus (im Emulator die Signatur eines leeren Slots, 7 gesetzte
  Byte, gegenüber 13 mit Probe). Sie liest den alten Ordner nicht, schreibt keinen
  Sektor (0 Schreibzugriffe) und verändert die Karte nicht (Hash vor und nach dem
  Start gleich). Es geht also nichts verloren, die Samples sind nur "weg", bis
  der Ordner umbenannt ist.
- **gemessen:** Ein EXPORT ALL SAMPLE danach schreibt eine neue, kleinere
  `e2sSample.all` nach `KORG/blechtribe/Sample` und lässt die alte stehen. Wer
  ohne Umbenennen exportiert, hat zwei verschiedene Stände.
- **gemessen:** Die Original-Firmware liest dieselbe Karte wie bisher aus
  `KORG/hacktribe`. **hergeleitet, Rückweg:** Wer die Original-Firmware zurück
  flasht, nachdem die umbenannte auf der Karte geschrieben hat, hat in
  `hacktribe` einen älteren und in `blechtribe` einen neueren Stand.
- **hergeleitet:** Dateien, die die Firmware nur über den Browser öffnet (IMPORT
  SAMPLE, IMPORT PATTERN), bleiben unberührt: der Browser beginnt an der
  Kartenwurzel. Nur das, was die Firmware selbst an festem Ort sucht, wandert:
  `e2sSample.all` beim Start, das Update-Image, die Ziele der Exporte.

## 10. Importiert die Firmware beim Start einzelne WAVs?

### Nein, nur `e2sSample.all` (gemessen)

- Karte nur mit WAV-Dateien: im Wurzelordner, als `KORG/hacktribe/Sample/501_kick.wav`
  (Name wie vom Export), `502_snare.wav`, `loose.wav`, in `KORG/hacktribe/Import`
  und in `Sample`: nach 8 s Gerätezeit sind 11 Sektoren gelesen (7 verschiedene,
  alles Verzeichnisse und die Kopfsektoren) und **von keiner der sechs WAVs ein
  einziger Datensektor** (0 von je 20). Die Slots 501 bis 503 bleiben leer.
- Dieselbe Karte mit `e2sSample.all` daneben: die Datei wird ganz gelesen (30 von
  30 Sektoren), ihre WAV-Nachbarn (`501_my kick.wav`) nicht; Slot 501 ist gefüllt.
- **gemessen, wer was wann liest** (Haken auf `f_stat` und `f_open`): Bei 75,6 ms
  fragt der Start, ob `SD:KORG/hacktribe/Sample/e2sSample.all` existiert (`f_stat`
  über `0xC0035440`, hergeleitet aus dem Aufruf bei `0xC002AE60`; nur im normalen
  Start, die Modi 1 bis 10 kommen nie dorthin, offline gelesen). Bei 347 ms fragt
  es noch einmal, und bei 351 ms springt der Lader `0xC00364F0` an (gemessen,
  Rücksprung `0xC0038D64` in die Methode `0xC0038D34`, ein Befehlsobjekt;
  hergeleitet, dass die zweite Abfrage von dort kommt). Er öffnet die Datei, liest
  4096 Byte Kopf und geht 999 Einträge durch (offline gelesen). Es gibt keinen
  Pfad im Start, der eine WAV öffnet.
- **offen:** Ob ein anderer Anlass (Kartenwechsel im Betrieb, Menü) WAVs liest;
  IMPORT SAMPLE ist der Weg dafür.

## Offen

- Einstecken und Ziehen im Betrieb (Eingang 4.1 umschalten), "Card Inserted Error", Reaktion auf ein Ziehen während
  eines Schreibens.
- Fehlerfälle beim Update (kaputte VSB, Abbruch). Warum "Invalid File" beim Update beim Start mit einer einzelnen VSB
  kommt und ob `USER`, `PCM`, `SLICE` nötig sind.
- Karten über 1 GiB.
- Ob PCM beim Export am echten Gerät wieder herauskommt.
