# DSP: Programm, Effektwechsel und Filter

Hintergrund zum DSP des Korg electribe sampler: wie sich sein Programm lesen und ausführen lässt, was beim Effektwechsel
passiert und wie die Filter aufgebaut sind. Alle Adressen gelten für Firmware 2.02 (Korgs Original und
[Hacktribe](../glossary.md#hacktribe)). Der DSP ist ein Blackfin-Chip, der neben dem ARM-Prozessor das Audio rechnet. Sein
Programm steckt als Strom in der [`SYSTEM.VSB`](../glossary.md#vsb).

Grundlage: alles offline, dazu der Emulator (`tools/emu`) für die ARM-Seite und der GNU-Blackfin-Simulator für einzelne reine
DSP-Funktionen. Kein Gerätezugriff. Im Repository liegen `tools/emu`, `tools/dsp` (Extraktion, Blackfin-Worker) und
`tools/fx-tables.py`. Die Arbeitsnamen für DSP-Adressen stammen nicht von Korg. Wie der DSP im Emulator ausgeführt wird,
steht in [emulator.md](../emulator.md) ("Blackfin-Worker: QEMU oder GNU").

Markierungen: **gemessen** (ausgeführt und beobachtet), **offline** (Code oder Daten gelesen), **hergeleitet** (aus beidem
geschlossen), **offen** (braucht das Gerät oder mehr Arbeit).

Verwandt: [patternwechsel.md](patternwechsel.md) (die Lücke beim Patternwechsel),
[2026-10-14-fx-tabellen.md](../messungen/2026-10-14-fx-tabellen.md) (Effekt-Parameter aus dem DSP-Strom),
[patcher.md](../patcher.md).

## Überblick

1. **Der DSP-Strom ist in allen 23 geprüften VSBs byte-gleich**, auch zwischen Korgs 2.02 und Hacktribe. Hacktribe hat den
   DSP nie angefasst.
2. **Zwei getrennte Befehlsräume zum DSP.** "Befehl 0x30" heißt etwas anderes im A34-Postfach (Objekt setzen, Filter) und im
   Frame-Postfach (Effektplatz stumm schalten). Der Bericht zum Patternwechsel meint die Frame-Befehle.
3. **Effektwechsel** je Platz: Frame-Befehl 0x30 (Platz-Pegel auf 0), 10 ms Wartezeit auf der ARM-Seite, 0x31 (Platz auf
   Durchreichen), Parameter und Typ, dann löscht der DSP-Lader 192 000 Byte Platzspeicher in 64-Byte-Schritten, ruft die
   Init-Funktion des neuen Effekts und setzt den Pegel wieder auf voll. Der alte Effekt kann nicht weiterlaufen, weil Lader
   und Effekt denselben Speicher benutzen und es keinen freien Platz gibt (16 Inserts plus Master, fest).
4. **Filter:** Typ, Art, DSP-Objekttyp und eigener Kern sind Tabellen. Die Koeffizienten rechnet der ARM, der DSP rechnet nur die
   Schleife. Alle Filtertabellen sind in Korgs Original und Hacktribe identisch, aber die Oberfläche bietet nicht dieselben
   Typen an (Abschnitt 4). Ein neuer Typ ist ARM-seitig (Daten plus wenige Befehle) möglich, ohne den DSP zu ändern.
5. **Hochladen ohne Zeitgrenze:** der ARM wartet beim Hochladen des DSP-Programms ohne Zeitgrenze auf den DSP-Bootloader
   (Schleifen bei `0xC0011B78` und `0xC0011C30`, nur der Anfang `0xC0011AE4` hat 1000 Versuche), vor Panel-Austausch,
   Tastenabfrage und Update-Abfrage. Ein DSP-Strom, den der Boot-ROM ablehnt, hängt den Start, dann hilft EXIT nicht und der
   Rückweg wäre JTAG ([Messung](../messungen/2026-10-08-firmware-rueckweg.md)). Der Emulator ersetzt den Upload
   (`0xC0011AB8`) durch einen Stummel, die Start-Prüfung in `check.py` sieht Änderungen im Strom also nicht.

## 1. Werkzeug

Der Strom wird mit `tools/dsp/dsp_extract.py` aus der VSB gelesen, Blackfin-Code mit `bfin-objdump` (GNU binutils,
Ziel `bfin-elf`) disassembliert, einzelne reine DSP-Funktionen führt der Simulator aus gdb aus (Modell bf527), die ARM-Seite
liest Python `capstone`. Die Werkzeugquellen enthalten keine Korg-Daten.

### 1.2 Extraktion des DSP-Abbilds (gemessen)

`dsp_extract.py SYSTEM.VSB OUTDIR` schreibt je Zielregion eine Datei, `blocks.txt` und `map.json`. Das Format
ist das Blackfin-Boot-Format: 16-Byte-Kopf (`flags|XOR|0xAD`, Ziel, Zähler, Argument, XOR aller 16 Byte gleich
0), Flags `0x0001` Daten, `0x0100` Füllblock (32-Bit-Muster, keine Nutzlast), `0x4000` erster, `0x8000`
letzter, `0x0800` INIT-Block.

Aufbau des Stroms (aus `blocks.txt`):

| Blöcke | Ziel | Inhalt |
|---|---|---|
| 0 bis 4 | `0xFFA00000` | Stufe 1: Init-Code (SDRAM, PLL), INIT-Block, zweiter Start |
| 5 bis 49, 51 bis 63 | SDRAM `0x4` bis `0x1A2B8`, `0x1C76DA0` bis `0x1C816EC` | Code und Daten (Lader, Frame-Handler, Effekte, Deskriptoren) |
| 50 | SDRAM `0x1A2B8` bis `0x1C76DA0` | Nullfüllung, 29 776 912 Byte, der Boot-Rom führt sie aus |
| 64 bis 117 | SDRAM `0x1F00000` bis `0x1F11B40` | Code und Tabellen (geschütztes Schreiben, Sprungtabellen, Init) |
| 118 bis 145 | L1 Daten A/B `0xFF800000`, `0xFF900000` | Anfangswerte der Arbeitsdaten |
| 146 bis 155 | L1 Instruktionen `0xFFA00000` bis `0xFFA0BFF8` | 49 144 Byte Kernel, Mischer, Filterkerne |
| 156 | `0xFFA00000`, Flag FINAL | Einsprung nach dem Laden |

In der VSB liegt der Strom bei Datei `0xF9F10` bis `0x13C1B0` (RAM `0xC00F9E10` bis `0xC013C0B0`).
`dsp_extract.vsb_offset(vsb, dspadresse)` liefert den Datei-Offset einer DSP-Adresse.

### 1.3 Disassembler (gemessen)

Qualität: das L1-Instruktions-Abbild (16 533 Zeilen) enthält 0 `ILLEGAL`, 134 `LINK`, 251 `UNLINK`, 257 `RTS`;
in den SDRAM-Regionen stehen `ILLEGAL` nur dort, wo Daten zwischen dem Code liegen. Eine Funktionsliste (854
Einträge) und Konstanten-Querverweise entstehen aus dem Disassembly. Die ARM-Seite wird mit capstone gelesen.

### 1.4 Simulator (gemessen, mit Einschränkung)

Der Simulator führt eine Folge von DSP-Funktionsaufrufen in einem Lauf aus und gibt Speicherbereiche zurück.
Dafür waren drei Korrekturen nötig: Syscalls nur mit 32-Bit-Befehlen für P- und R-Register (die 16-Bit-
Konstantenbefehle setzten das Register nicht), die L1-Regionen mit `--memory-region` anlegen, und der Aufrufer
legt SP an. Beleg, dass es geht: die Koeffizientenfunktion `0xFFA04568` liefert aus A=`0x232372`,
B=`0x40000000` die abgeleiteten Wörter `0x001A5A95` und `0xC008C8DD`.

Grenze: Funktionen, die das geschützte Schreiben `0x1F0E54C` benutzen (Frame-Handler, Lader), hängen im
Simulator, weil Warteschlange und Gate-Wörter nach dem Boot-Code anders stehen als im rohen Abbild. Die
Aussagen zu 0x30/0x31/0x32 sind deshalb **offline**, nicht gemessen. Peripherie (SPORT, DMA, HOSTDP) fehlt
ganz, es gibt keine Zeitmessung.

---

## 2. Mailbox, Befehle 0x30 und 0x31, Effektwechsel

### 2.1 Zwei Befehlsräume (offline)

| Raum | Ort im DSP | Format | Zweck |
|---|---|---|---|
| **A34-Postfach** | `0xFF900A34` | Kopf `0x106` (Bit 1 = neu, der DSP löscht es), Befehlsnummer, Wörter | Objekte und Werte setzen (Filter, Part-Werte) |
| **Frame-Postfach** | `0xFF900018` und `0xFF900098`, je 32 Wörter | `Bit31 gültig, 30..28 Folge, 27..22 Feld, 21..16 Befehl, 15..0 Wert` | Parameter und Typ der Effektplätze |

Verwechslungsgefahr: `0xFFA05308` ist der Handler für den A34-Befehl 0x30 (Objekt setzen) und `0xC003E244`
die Wartezeit zwischen Frame-Befehl 0x30 und 0x31. Das sind zwei verschiedene Befehle. Die 10 ms gehören zu
den **Frame**-Befehlen.

**A34-Dispatch:** `0xFFA04EC8` (aus der Audioschleife `0xFFA0010C` aufgerufen) liest HOSTDP_STATUS
(`0xFFC03404` Bit 4), prüft den Kopf, löscht Bit 1, nimmt `W[+2]` als Befehlsnummer und springt über die
60-Einträge-Tabelle `0x01F02B84` (Nummer unter `0x3C`). Alles Nicht-Zugewiesene geht an `0xFFA04F50` (legt
in einen Puffer ab, nicht dekodiert). Dekodiert (hergeleitet aus dem Code):

| Nr. | Handler | Wirkung |
|---|---|---|
| 0x00, 0x01, 0x02 | `FFA04FD8`, `FFA05000`, `FFA0502E` | Wörter an Handle-Adressen schreiben (16 oder 32 Bit, Block) |
| 0x09 | `FFA0505A` | 26 Wörter von Handle A nach B kopieren |
| 0x16 | `FFA05084` | Wortpaare setzen |
| 0x1F, 0x21 | `FFA050B0`, `FFA050EE` | Parameter über Wandler `FFA06670`, Tabellen füllen (16 oder 24 Einträge) |
| 0x2B, 0x2C | `FFA051C0`, `FFA05210` | Wert plus Delta mit Begrenzung 0 bis `0x7FFF`, dann Wandler `FFA06970` |
| 0x2D, 0x2E | `FFA05268`, `FFA05290` | Setzer nach Typ (Tabellen `1F02ED8`) |
| **0x2F** | `FFA052B8` | Objekt setzen: nur Typ-Setter, optional zweites Objekt bei Handle+`0x1B8` |
| **0x30** | `FFA05308` | Objekt setzen und übernehmen: Setter `FFA05CB2` (Tabelle `1F02E84`, 21 Einträge), dann Übernahme `FFA05BF0` (Tabelle `1F02E30`) |
| **0x31** | `FFA05382` | Block von Wörtern an Handle schreiben ("Vorlage"), das erste Wort ist der Objekttyp |
| 0x32, 0x33 | `FFA053B6`, `FFA053F6` | Schleifen über `FFA057B8`, `FFA059F8` |
| 0x34 bis 0x3B | | nicht dekodiert (**offen**) |

Handle zu Adresse: `h < 0x4000: 0xFF800000 + 4h`, sonst `0xFF8F0000 + 4h` (`FFA071CC`).

### 2.2 Frame-Handler: Befehle 0x30, 0x31, 0x32, 0x38, 0x39 (offline)

Task 0 bei SDRAM `0x17FF8` (Zustandsstruktur `0xFF803CE0`). Er nimmt einen Frame, prüft Gültigkeit und
Folgenummer und arbeitet Wort für Wort ab. Feld 0x00 bis 0x1F: Insert-Plätze (Feld/2 = Platz 0 bis 15),
0x20/0x21: Master, 0x28: Parameter-Staging, 0x38: Mischer-Werte, 0x3E: Frame-Ende. Platz k liegt bei
`0xFF800B08 + k * 0x1B4` (109 Wörter), Typ-Tabelle je Feld bei `0xFF9007CC`.

| Befehl | Insert-Platz k | Master (Feld >= 0x20) |
|---|---|---|
| **0x30** | Wort 37 (`+0x94`) := 0 (über geschütztes Schreiben). Hat der Platz einen verbundenen Nachbarn (Bit 7 der Typ-Tabelle), wird auch dessen Wort 37 geleert. | Mischer-Kontext `0xFF903114` := `0x7FFF0000`, `0xFF903118` := 0 |
| **0x31** | Wörter 43 (`+0xAC`) und 49 (`+0xC4`) := `Deskriptor[0].+0x18` (Durchreich-Funktion `0xFFA01348`), auch beim Nachbarn | `0xFF903128` := 0 |
| 0x32 | Wörter 43 und 49 := `Deskriptor[Typ].+0x18`, Wort 37 := `0x7FFFFFFF` | `0xFF903128` := `0x7FFF0000` |
| Befehl 0..0x19 im Feld 0x28 | Parameter ins Staging `0xFF900118 + Platz * 0x34`, dann Wandler | |
| Feld 0x28, Befehl 0x38 / 0x39 | Typ / Ziel-Feld in `0xFF900008/9`; 0x39 setzt zusätzlich das Go-Flag Byte `0xFF803CFA` und startet den Lader | |

Alle Platzschreibungen laufen über das geschützte Schreiben `0x1F0E54C`: liegt die Zieladresse in einem
Platz- oder Parameterbereich (`0xFF800B08 + 0x1B40`, `0xFF90186C + 0x1180`, `0xFF8029EC + 0x190`,
`0xFF802648 + 0x1E0`) und ist das Gate `W[0xFF900010]` leer, wird (Adresse, Wert) in eine 64-Eintrags-
Warteschlange bei `0xFF900834` gelegt. Die Audioschleife leert sie nach den 4 Mischerdurchläufen
(`0xFFA00238` ruft `0x1F0E48C`). Das Pegel- und Zeigerschreiben wird also auf eine Blockgrenze gelegt, nie
mitten im Block.

Deskriptor je Effekttyp (66 Zeiger bei SDRAM `0x4C30`, je `0x34` Byte): Name, Parameterzahl (Byte `+4`),
Speicherflags (Bytes `+5`, `+6`, nicht null: der Effekt braucht Platzspeicher), Parametertabelle (`+0x14`),
Codeanfang (`+0x18`), weiteres Codefeld (`+0x1C`), Init-Funktion (`+0x20`). Bei Flagbyte `+0x0A == 1` ist `+0x1C` die exklusive Code-Endadresse, kein zweiter Funktionsanfang. Master-Typen tragen `0x10000`
in `+8`. Code liegt an drei Orten: L1-Instruktionen (`0xFFA0xxxx`), SDRAM unten (`0x0000xxxx`) und SDRAM
`0x01C7xxxx`. Es gibt keinen parametrisierten Einheitseffekt, jeder Typ hat eigenen Code. Die [Nachprüfung vom 20. November](../messungen/2026-11-20-dsp-sdram-freiraum.md) verfolgt die Endadresse und die genaue Kopierlänge am Baustein `0x2E` in beiden Originalen.

### 2.3 Lader (Task 1, SDRAM `0x1859C`) (offline)

Zustand in `W[0xFF803D04]`, Sprungtabelle `0x1F02B68` (7 Zustände):

| Zustand | Adresse | Tut |
|---|---|---|
| 0 | `185E4` | Lader belegen, Typ übernehmen |
| 1 | `18600` | prüfen, ob der Platz schon die Prozess-Funktion des neuen Typs hat (dann überspringen) |
| 2 | `186AE` | Zeigertabellen für den Platz setzen |
| 3 | `18736` | Speicherbereich bestimmen: Insert `0x1A2C0 + k * 0x2EE00` (192 000 Byte), Master `0x3082C0` (`0x5DC00` = 384 000 Byte), nur wenn der Deskriptor Speicher verlangt |
| 4 | `1878A` | **64 Byte pro Aufruf** mit `memset` nullen (`0x1F1025C`), kehrt zurück, bis alles gelöscht ist: 3000 Aufrufe je Insert-Platz |
| 5 | `189C8` | kleiner Bereich (80 Byte), 128-Byte-Schritte |
| 6 | `18A84` | Staging-Parameter übernehmen, **Init-Funktion des neuen Effekts rufen** (installiert dessen Platzzeiger), Parameter über Wandler `17DC4`, Wort 37 := `0x7FFFFFFF` (Master: `0xFF903128` := `0x7FFF0000`), Lader frei |

Der Lader läuft als Task im Kernel (`0xFFA0B5A8`, Semaphoren, Zählung mit CYCLES): er bekommt nur Rechenzeit
neben der Audioschleife. Die tatsächliche Aufrufrate ist **offen**.

### 2.4 ARM-Seite: ein Zustandsautomat je Platz (offline)

`0xC003E65C` ist ein Zeitplaner über 18 Einträge zu je `0x18` Byte (Tabelle `0xC00F934C`, 16 Inserts,
Master, ein Reserveplatz). Jeder Eintrag ruft `0xC003E018` mit seinem Zustand: Zustand 2 sendet Frame-Befehl
0x30 und stellt Zustand "warten" mit `[+4] = 10` (Ticks, Konstante bei `0xC003E244`), Zustand 3 sendet 0x31,
Zustand 6 wartet, bis `0xC003DF2C` den DSP-Lader als frei meldet (liest `0xFF803CF8` über den Host-Port,
**ohne Zeitgrenze**), schickt Parameter (Feld 0x28), Typ (`0x0A38xxxx`) und Ziel (`0x0A39xxxx`), danach wartet
er wieder auf "Lader frei". Der ARM sendet 0x32 nie (kein Aufruf gefunden), die Aktivierung macht der Lader.
Die Plätze laufen nebeneinander durch denselben Automaten und teilen sich Mailbox und Lader.

### 2.5 Fragen und Antworten

**Was tut 0x30?** Frame-Befehl 0x30 setzt den Pegel (Wort 37) des Platzes auf 0, beim Master ändert er zwei
Mischer-Kontextwerte. A34-Befehl 0x30 setzt ein Filterobjekt (kein Bezug zum Effektwechsel).

**Warum wartet der ARM genau 10 ms?** Die 10 ms sind eine ARM-Konstante (10 Zeitplaner-Ticks) zwischen 0x30
und 0x31. Der DSP verschiebt das Schreiben auf die Blockgrenze (Warteschlange), 10 ms sind mehrere
Audioblöcke Sicherheitsabstand, bevor der Platz auf Durchreichen springt. Die Begründung ist **hergeleitet**,
ein Beleg im Code fehlt. Die Zeit ist kein DSP-Wert und lässt sich ARM-seitig ändern.

**Kann der alte Effekt weiterlaufen, bis der neue bereit ist?** Nein, im bestehenden Entwurf nicht (offline):
(a) Der Lader löscht denselben Platzspeicher, den der alte Effekt benutzt. (b) Es gibt 17 Plätze fest, je Part
einer plus Master, keinen freien. (c) Jeder Typ hat eigenen Code und eigene Init-Funktion, aber keinen
zweiten Satz Zustand. Zwei Effekte gleichzeitig brauchen einen zusätzlichen Platz mit eigenem Speicher
(192 KB Insert, 384 KB Master), Mischereintrag und Anpassung der festen Feldgrenzen (`0x21`, `0x1B40`). Wo
SDRAM frei ist, ist **offen** (die Füllung `0x1A2B8` bis `0x1C76DA0` ist beim Boot genullt, dort liegen
vermutlich Samples).

**Geht ein Wechsel ohne Stille (Überblenden, Dry weiterlaufen lassen)?**
- Überblenden: nur mit zweitem Effektplatz, also DSP-Änderung (groß).
- Dry weiterlaufen: ab 0x31 ist der Platz auf Durchreichen, `0xFFA01348` kopiert Eingang auf Ausgang und
  ignoriert Wort 37. Wenn das Pegelwort nur effektintern gelesen wird, läuft das Dry-Signal ab 0x31 hörbar
  durch und die Stille beschränkt sich auf die 10 ms plus den fehlenden Effekt. Wer Wort 37 außerhalb des
  Effekts liest, ist **offen** (nur fünf direkte Leser gefunden: `FFA012EA`, `FFA081CC`, `FFA082B2`,
  `FFA082D0` und Stellen in SDRAM `0x155AC`, `0x16AF0`). Billige ARM-Probe ohne DSP-Änderung: in Zustand 2
  den Befehl 0x30 durch 0x31 ersetzen und die Wartezeit `0xC003E244` auf 1 setzen; beides wirkt nur im
  RAM-Betrieb und ist zurücknehmbar. Das wäre ein Gerätetest, kein Beleg.

**Ist die Stille die ganze Ausgabe oder nur der Effektpfad?** Pro Platz, nie global (offline): jeder Befehl
adressiert genau einen Platz (Feld/2). Bei Inserts ist das der Pfad eines Parts. Ob der Part wirklich ganz
schweigt oder nur seinen Effektanteil verliert, hängt an der Frage nach Wort 37 (offen). Die Master-Stufe
fasst nur zwei Mischer-Kontextwerte an, nicht die Summe.

### 2.6 Wie die rund 100 ms entstehen können (hergeleitet)

[patternwechsel.md](patternwechsel.md) misst im Emulator 21 bis 66 Frames je Wechsel. Der DSP kann Frames nur
im Takt seines Tasks abnehmen, der Emulator quittiert sofort. Rechnung für den Fall Pattern 68 auf 211: 39
Frames. Bei einem Frame je Audioblock von 1,3 bis 2,7 ms (64 oder 128 Stereo-Samples bei 48 kHz, Blockgröße
nicht bestätigt) ergeben 39 Frames 52 bis 105 ms, plus 10 ms Wartezeit, plus Lader je Platz. Das passt zur
gehörten Lücke, ist aber eine Rechnung mit geschätzter Blockzeit, **kein Beleg**. Die DSP-Zeit je Frame
lässt sich nur am Gerät oder mit einem zeitgenauen DSP-Modell messen.

---

## 3. Filter

### 3.1 Daten in Stock und Hacktribe gleich (gemessen)

Korgs offizielles Paket `electribe_sampler_system_v202` (815 KB, mit Release Notes) enthält ein `SYSTEM.VSB`
(md5 `1589b5f2...`), das ebenfalls die Namensliste `electribe LPF`, `MS20 LPF`, `MG LPF`, `P5 LPF`, `OB LPF`,
`Acid LPF`, `electribe HPF` ... `Acid BPF` sowie OFF enthält. Verglichen mit Hacktribe: gleicher Namenscode,
gleiche 17-Byte-Typkarte, gleiche 21 Vorlagen, gleiche 7 Koeffizientenrechner, gleicher DSP. Hacktribe ändert
in der Nähe nur Zählgrenzen der Effektlisten (`0x26` -> `0x3B` Einträge bei `0xC0098084` ff., 38 auf 59
Master-Einheiten). Daraus folgt nicht, dass die Oberfläche dieselben Typen anbietet (Abschnitt 4).

### 3.2 Auswahlkette (gemessen)

Pattern-Part-Byte 12 (Typ 0 = OFF, 1 bis 16) -> `0xC0097744` (Karte `0xC00E8F88`, 17 Byte) -> "Art" (0 bis 20)
-> Vorlage (`0xC00E632C`, 21 Zeiger, erstes Wort = DSP-Objekttyp) -> DSP-Kern (Tabelle `0xFF803B84`, 21
Zeiger, zur Laufzeit in den Scratchpad `0xFFB000E0` kopiert) und ARM-Rechner (Sprungtabelle `0xC0094AA4`).

| Typ | Name | Art | DSP-Typ | Kern | ARM-Rechner |
|---|---|---|---|---|---|
| 1 | electribe LPF | 1 | 0x02 | `FFA0383C` | `C0093EB4` |
| 2 | MS20 LPF | 5 | 0x05 | `FFA03EAC` | `C009438C` |
| 3 | MG LPF | 2 | 0x06 | `FFA0411E` | `C00944F4` |
| 4 | P5 LPF | 3 | 0x07 | `FFA042DA` | `C00946B0` |
| 5 | OB LPF | 4 | 0x03 | `FFA03A1C` | `C0093F40` |
| 6 | Acid LPF | 6 | 0x04 | `FFA03C3C` | `C00940F8` |
| 7 | electribe HPF | 7 | 0x08 | `FFA0383C` | `C0093EB4` |
| 8 | MS20 HPF | 11 | 0x0B | `FFA03EAC` | `C009438C` |
| 9 | P5 HPF | 9 | 0x0D | `FFA042DA` | `C0094860` |
| 10 | OB HPF | 10 | 0x09 | `FFA03A1C` | `C0093F40` |
| 11 | Acid HPF | 12 | 0x0A | `FFA03C3C` | `C00940F8` |
| 12 | electribe BPF | 13 | 0x0E | `FFA0383C` | `C0093EB4` |
| 13 | MS20 BPF | 17 | 0x11 | `FFA03EAC` | `C009438C` |
| 14 | P5 BPF | 15 | 0x13 | `FFA042DA` | `C00946B0` |
| 15 | OB BPF | 16 | 0x0F | `FFA03A1C` | `C0093F40` |
| 16 | Acid BPF | 18 | 0x10 | `FFA03C3C` | `C00940F8` |
| 0 | OFF | 20 | (Vorlage 1 Byte) | | |

Das sind 6 Kerne für die 16 Typen (e, MS20, MG, P5, OB, Acid) plus ein kleiner Verstärkungskern `0xFFA03820`
(Typ 0), zusammen 7 Kerne. LPF, HPF und BPF derselben Familie teilen den Kern und unterscheiden sich durch
den DSP-Typ (Setter- und Übernahme-Tabellen) und die Vorlage.

**Unerreichbare Arten (gemessen):** 0, 8, 14 und 19. Sie haben Vorlage und Rechner, aber keinen Filtertyp
zeigt auf sie (Art 0 und 19: electribe-Kern, Art 8: DSP-Typ 0x0C, Art 14: DSP-Typ 0x12, beide Kern
`FFA042DA`). Was sie klanglich tun, ist offen.

**Zur Laufzeit** (offline): jede Änderung von Cutoff oder Resonanz ruft `0xC0094A6C`: der Rechner liefert
drei 32-Bit-Wörter, der ARM schickt sie mit Handle als A34-Befehl 0x30 (Rampe) oder 0x2F (sofort). Bei
Typwechsel geht vorher die Vorlage (A34-Befehl 0x31) an dasselbe Handle (`0xC0094A10`). Der DSP rechnet nur
die Sample-Schleife der Kerne.

### 3.3 Cutoff-Tabellen

Rechner `0xC0093EB4` (electribe-Familie): Eingang Cutoff als 16 Bit (Byte in der oberen Hälfte, untere Hälfte
Interpolation, `0x7F00` und mehr = Klemme), Ausgang: A aus der 128-Eintrags-Tabelle `0xC00E6840` (Q31), B aus
`0xC00E6640` (Resonanz), dritter Wert aus 16-Bit-Tabelle `0xC00E6396`. Liest man A als `pi * f / fs` mit
fs = 48 kHz (Annahme, mit den Messpunkten bei Byte 16, 48, 64 verträglich), ergibt sich: Byte 0 = 16,4 Hz,
Byte 2 = 18,4 Hz, 16 = 41,3 Hz, 48 = 262 Hz, 64 = 660 Hz, 96 = 4,14 kHz, 127 = 14,69 kHz. Die gemessene
Zeitreihe in [../messungen/2026-09-17-cutoff-resonance-peak.md](../messungen/2026-09-17-cutoff-resonance-peak.md)
(41, 263, 652 Hz) passt bis Byte 64, bei Byte 120 weicht sie ab (14 739 Hz gemessen gegen 12 683 Hz Tabelle),
das ist bei Resonanzgipfeln plausibel.

Die anderen Familien haben je eine monotone 128-Eintrags-Tabelle mit 16-Bit-Werten bis `32767`: OB und Acid
`0xC00E5D78`, MS20 `0xC00E5F28` und `0xC00E5C78`, MG `0xC00E6128` (plus Q31 `0xC00E6A40`), P5 `0xC00E64C8`,
P5 HPF `0xC00E622C`. Die Hz-Bedeutung dieser Werte ist **offen**.

### 3.4 Neuer Filtertyp

Ein neuer Typ braucht ARM-seitig: Namenseintrag, Typbereich im Part-Parameter (derzeit 0 bis 16), Kartenbyte,
Vorlage (Zeiger plus Länge), Rechner (bestehend oder neu). Der DSP bleibt unberührt, solange ein vorhandener
DSP-Typ und Kern wiederverwendet wird (21 Typen, alle Ids 1 bis 0x14 belegt, Id 0 unbenutzt). Wege, von klein
nach groß:

1. **Unerreichbare Arten 0, 8, 14, 19 freischalten:** nur Karte, Name, Bereich. Klang unbekannt, billig zu
   hören.
2. **Variante über Daten oder Rechner:** ein Typ 17 mit Vorlage und Rechner eines bestehenden Typs, Cutoff auf
   einen festen Wert gezwungen (ein Rechner-Aufruf mit festem Eingang) oder andere Tabellenwerte. Beispiel:
   electribe HPF mit Cutoff-Byte 2 ergibt laut Tabelle 18,4 Hz. **18 Hz Low Cut geht damit heute schon**,
   auch ohne neuen Typ, mit der vorhandenen Cutoff-Einstellung.
3. **20 kHz High Cut:** die electribe-Familie kommt nur bis 14,7 kHz (`A` wäre bei 20 kHz größer als 1,0 und
   nicht als Q31 darstellbar). OB, Acid, MS20, P5 haben 16-Bit-Tabellen bis zum Maximum, was das in Hz ist,
   ist offen.
4. **Beide Ecken in einem Typ** (Band 18 Hz bis 20 kHz, flach dazwischen): ein Objekt hat einen Cutoff, die
   BPF-Kerne haben die Breite über die Resonanz. Ob ein BPF-Kern zwei unabhängige Ecken hergibt, ist
   **offen** und lässt sich im Simulator messen: Rechner (ARM, per Port nach Python) -> Setter
   `FFA05D18`/`FFA04568` -> Kern `FFA0383C` mit Impulsantwort. Dafür fehlt noch die Aufrufkonvention (Zeiger
   auf Objekt und Zustand). Wenn ein Kern es nicht hergibt, bleibt nur ein neuer Kern, also ein DSP-Patch
   (mittel bis groß).

---

## 4. Filtertypen in Korgs Original und Hacktribe

Korgs Sampler-Firmware enthält die Daten aller 16 Filtertypen samt Namen (Abschnitt 3.1), die Oberfläche bietet aber nicht dieselben
Typen an. Ob sie einen Typ *anbietet*, hängt nicht an den Tabellen, sondern an der Tastenbehandlung im ARM-Code.
Hacktribe leitet dafür neun Aufrufe und Sprünge im Tastencode auf neuen Code um.

**Gemessen** (Emulator, `tools/emu/machine.py`, leerer Flash, Part 01 nach dem Start, nach 3 s Gerätezeit die
Filtertaste n-mal gedrückt und losgelassen, Display als Bild gelesen; Taste `0x12` LPF, `0x14` HPF, `0x16` BPF
aus `data/panel.mjs`):

| Firmware | Taste | Anzeige nach 1, 2, 3, ... Drücken |
|---|---|---|
| Stock 2.02 (Korgs Paket `electribe_sampler_system_v202`, md5 `1589b5f2...`) | LPF | OFF, electribe LPF, OFF, electribe LPF, OFF, electribe LPF, OFF (7 Läufe) |
| Stock 2.02 | HPF | electribe HPF, OFF, electribe HPF (3 Läufe) |
| Stock 2.02 | BPF | electribe BPF, OFF, electribe BPF (3 Läufe) |
| Hacktribe | LPF | MS20 LPF, MG LPF, P5 LPF, OB LPF, Acid LPF, OFF, electribe LPF (7 Läufe) |

Die Stock-Oberfläche kennt also nur electribe LPF, HPF und BPF mit OFF. Hacktribe läuft über alle sechs
LPF-Familien. Die Typnummern der Hacktribe-Reihenfolge (2 bis 6, dann 0, dann 1) passen zur Namensliste bei
`0xC00A6D4F`, die in beiden VSBs dieselben 16 Namen in derselben Reihenfolge hat. Die Projektseite von
Hacktribe bestätigt es: sie nennt Electribe, Moog, MS20, Oberheim, Prophet-5 und Acid als die aus der
Synth-Version übernommenen Filter, Stock hat nur LPF, HPF und BPF.

**Wo der Schalter sitzt** (hergeleitet, nicht bis zur letzten Anweisung verfolgt). Der Vergleich zwischen
Stock und Hacktribe (`vsbdiff`) zeigt im ARM-Code nur 86 Bereiche mit 145 624 Byte, davon rund 140 Byte echte
Code- und Literaländerungen unterhalb von `0xC0099000`. Neun Aufrufe oder Sprünge (`0xC0026450`,
`0xC00265B0`, `0xC0026B00`, `0xC002B098`, `0xC002B294`, `0xC005F144`, `0xC006EAD4`, `0xC00702C0`,
`0xC008374C`) zeigen in neuen Code bei `0xC0150000` und `0xC0170000` bis `0xC01721B0` (Datei `0x170100` bis
`0x1721B0`, in Stock leer). Welcher dieser Einsprünge die Filtertasten behandelt, ist **offen**: der Block bei
`0xC0170300` (ersetzt den Aufruf von `0xC00400B4`) führt einen Zustand bis `0x10` über Sprungtabellen,
behandelt aber nach dem Code Tastenwerte ab `0x13`, nicht `0x12`. Dass der Schalter im ARM-Code liegt und
nicht in den Tabellen, folgt aus dem gemessenen Unterschied und dem identischen Datenbestand; welche
Anweisungen den Filtertyp setzen, ist nicht gelesen. Die Datenbereiche, in denen sich beide unterscheiden
(`0xC00D9CF0` ff.: Hacktribe überschreibt die Werks-Samplenamen mit Oszillatornamen, DUAL-SAW, OCT-SAW,
CHIP-TRI ...; Effektzähler `0x26` auf `0x3B` bei `0xC0098084` ff.), haben mit den Filtern nichts zu tun.

**Wo der Schalter sitzt:** die Frage ist beantwortet ([Messung](../messungen/2026-10-15-synth-filter.md)): die Auswahl der Typen sitzt in der Tastenfunktion `0xC006FC80` (drei Sprungtabellen, die nur 0, 1, 7 und 12 kennen), und der Teilsetter `0xC00495B8` faltet die Typen 2 bis 6, 8 bis 11 und 13 bis 16 beim Schreiben auf 1, 7 und 12 zurück. Der Schalter ist der eine bedingte Sprung `0xC00495DC`, den Hacktribe unbedingt macht, dazu die Tastenfunktion. Ein Patch mit beiden Stellen gibt Korgs Build die Synth-Filter ([Patcher](../patcher.md)).

**Folgen.** Der DSP braucht für die Hacktribe-Filter keine Änderung (Kern und Tabellen sind schon da, siehe
3.2), die Freischaltung ist reiner ARM-Code. Die Messung
[../messungen/2026-09-17-filter-types.md](../messungen/2026-09-17-filter-types.md) ("Hacktribe hat weitere
Filter in die Lücken gelegt") stimmt in der Sache, auch wenn "in die Lücken" aus der Werksbank geraten war:
die Lücken sind die Typen 2 bis 6 und 8 bis 11, 13 bis 16 der 17er-Karte. Die Namen aller 16 Typen stehen in
der Firmware (siehe [../messungen/2026-10-14-fx-tabellen.md](../messungen/2026-10-14-fx-tabellen.md)).

## 5. Offen

- Wer liest Wort 37 (`+0x94`) im Audiopfad, und was zeigt ein Gerätetest mit nur einem geänderten Insert-Typ
  (schweigt der Part ganz, bleibt Dry)?
- Aufrufrate des Laders und Blockzeit des DSP (bestimmt die 100 ms).
- Wo ist SDRAM frei (für einen zweiten Effektplatz)?
- A34-Befehle 0x34 bis 0x3B und der Standardhandler `FFA04F50` nicht dekodiert.
- Frame- und Lader-Verhalten im Simulator (Schreibwarteschlange initialisieren, dann nachspielen).
- Aufrufkonvention der Filterkerne und Impulsantwort der e-Familie (für ein Band von 18 Hz bis 20 kHz).
- Was tun die unerreichbaren Arten 0, 8, 14, 19?
