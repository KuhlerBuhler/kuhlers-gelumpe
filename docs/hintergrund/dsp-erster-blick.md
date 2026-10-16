# DSP, erster Blick: Werkzeug, Effektwechsel, Filter, erster Patch

Stand 2026-10-12, Korrektur zu den Filtern vom 2026-10-14.

Hintergrund zum DSP des Korg electribe sampler: wie sich sein Programm lesen und ausführen lässt, was beim
Effektwechsel passiert, wie die Filter aufgebaut sind und was ein erster DSP-Patch riskiert. Alle Adressen
gelten für Firmware 2.02 (Stock und mit Hacktribe).

Grundlage: alles offline, dazu der Emulator (`tools/emu`) für die ARM-Seite und der GNU-Blackfin-Simulator
für einzelne reine DSP-Funktionen. Kein Gerätezugriff. Die Arbeitsskripte (`dsp_extract.py`, `hs.py`,
`ftmap.py` und weitere) liegen nicht im Repository, im Repository sind nur `tools/emu` und
`tools/fx-tables.py`. Die Arbeitsnamen für DSP-Adressen stammen nicht von Korg.

Markierungen: **gemessen** (ausgeführt und beobachtet, Befehl genannt), **offline** (Code oder Daten
gelesen), **hergeleitet** (aus beidem geschlossen), **offen** (braucht das Gerät oder mehr Arbeit).

Verwandt: [patternwechsel.md](patternwechsel.md) (die Lücke beim Patternwechsel),
[../messungen/2026-10-14-fx-tabellen.md](../messungen/2026-10-14-fx-tabellen.md) (Effekt-Parameter aus dem
DSP-Strom), [../patcher.md](../patcher.md).

## Kurzfassung

1. **Werkzeug steht.** DSP-Strom aus der VSB extrahieren, Blackfin disassemblieren (binutils 2.42, lokal
   gebaut) und einzelne DSP-Funktionen ausführen (Simulator aus gdb 14.2). Der Simulator läuft nur für reine
   Rechenfunktionen, die Schreibwarteschlange des DSP lässt ihn hängen (1.4).
2. **Der DSP-Strom ist in allen 23 geprüften VSBs byte-gleich**, auch zwischen Korgs 2.02 und Hacktribe.
   Hacktribe hat den DSP nie angefasst, ein DSP-Patch wäre der erste überhaupt. Alle geprüften Hacktribe-
   Abbilder stammen aus eigenen Sicherungen, ein Stock-Abbild kam aus Korgs offiziellem Paket.
3. **Zwei getrennte Befehlsräume zum DSP.** "Befehl 0x30" heißt etwas anderes im A34-Postfach (Objekt
   setzen, Filter) und im Frame-Postfach (Effektplatz stumm schalten). Der Bericht zum Patternwechsel meint
   die Frame-Befehle.
4. **Effektwechsel** je Platz: Frame-Befehl 0x30 (Platz-Pegel auf 0), 10 ms Wartezeit auf der ARM-Seite,
   0x31 (Platz auf Durchreichen), Parameter und Typ, dann löscht der DSP-Lader 192 000 Byte Platzspeicher
   in 64-Byte-Schritten, ruft die Init-Funktion des neuen Effekts und setzt den Pegel wieder auf voll.
   Der alte Effekt kann nicht weiterlaufen, weil Lader und Effekt denselben Speicher benutzen und es
   keinen freien Platz gibt (16 Inserts plus Master, fest). Ein Überblenden braucht eine DSP-Änderung.
5. **Filter:** Typ -> Art -> DSP-Objekttyp -> eigener Kern, alles Tabellen. Die Koeffizienten rechnet der
   ARM, der DSP rechnet nur die Schleife. Alle Filtertabellen sind in Stock und Hacktribe identisch, aber
   die Oberfläche bietet nicht dieselben Typen an (siehe Korrektur am Ende). Ein neuer Typ ist ARM-seitig
   (Daten plus wenige Befehle) möglich, ohne den DSP zu ändern.
6. **Erster DSP-Patch:** machbar, aber der Emulator-Check sieht ihn nicht (gemessen), und der ARM wartet
   beim Hochladen ohne Zeitgrenze auf den DSP-Bootloader. Ein DSP-Patch braucht eigene Prüfungen, bevor er
   geflasht wird. Eine Laufzeit-Variante über den Host-Port (ohne Flash) ist denkbar, aber ungeprüft.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| DSP-Strom bei `0xC00F9E10`, `0x422A0` Byte, 157 Blöcke, Prüfsummen stimmen | gemessen | `dsp_extract.py VSB out/x` (bricht bei falschem Kopf-XOR ab); 268 496 Datenbyte + 157 * 16 Kopf = 271 008 |
| Strom in 23 VSBs identisch (md5 `5c3923ba...`) | gemessen | md5 über Datei-Offset `0xF9F10 + 0x422A0` aller geprüften `*.VSB` (eigene Dateien und Korgs Paket) |
| Korgs 2.02 hat denselben DSP wie Hacktribe | gemessen | `dsp_extract.py` auf beide, md5 der fünf Regionsdateien gleich |
| Stock und Hacktribe unterscheiden sich in 65 397 Byte, alle im ARM-Teil | gemessen | `cmp -l`, `vsbdiff.py STOCK HACK 16` (944 Bereiche) |
| Filtertabellen, Rechner, Vorlagen, Namenslisten gleich in Stock und Hacktribe | gemessen | `vsb.py`-Vergleich der Bereiche `0xC0093400-0xC0097800`, `0xC00E5A00-0xC00E6B00`, `0xC00E8F88`, Namenscode `0xC00785C0` |
| Alle Startwege laden den DSP genau einmal, bei 68,66 ms, vor Tastenabfrage und Update-Prüfung | gemessen | `bootmap.py` mit Flash-Dump, `dsp_uploads_ms` in allen 16 Läufen |
| Start-Phase-Bereiche (`bootmap.json`) überlappen den DSP-Strom nicht | gemessen | Schnitt der Bereiche mit `0xC00F9E10-0xC013C0B0`: leer |
| Erster Host-Port-Zugriff erst bei 93,1 ms (nur normaler Start); Update-Abfrage und Taste-Start 8 ("Data Util") greifen in 1,5 s nie auf den Host-Port zu | gemessen (Emulator) | `first_dsp_access.py` |
| Hochladen wartet pro Byte und am Ende ohne Zeitgrenze auf "DSP bereit" | offline | Schleifen bei `0xC0011B78` und `0xC0011C30`, nur der Anfang `0xC0011AE4` hat 1000 Versuche |
| Frame-Befehle 0x30, 0x31, 0x32: Wirkung auf Platzwörter | offline | Handler `0x17FF8` (SDRAM), Zeilen `0x18152` ff.; im Simulator nicht nachgespielt (hängt) |
| Lader: 7 Zustände, 64-Byte-Schritte, entstummt am Ende | offline | `0x1859C`, Sprungtabelle `0x1F02B68` |
| 10 ms Wartezeit ist ARM-Konstante, kein DSP-Wert | offline | Konstante 10 bei `0xC003E244`, Zeitprüfung im Zeitplaner `0xC003E65C` |
| Frames brauchen auf dem Gerät je einen Takt des DSP, Lücke ca. 10 ms + n * Frame | hergeleitet | Rechnung in 2.6, Frame-Zahl aus [patternwechsel.md](patternwechsel.md) |
| Pegelwort 37 (+0x94) sperrt den ganzen Platz oder nur den Effekt | offen | Leser des Worts nur an 5 Stellen gefunden |
| 4 von 21 Filter-Vorlagen sind von keinem Filtertyp erreichbar | gemessen | `ftmap.py` |
| Stock bietet am Gerät nur electribe LPF, HPF, BPF und OFF, Hacktribe alle sechs LPF-Familien | gemessen (Emulator) | Korrektur am Ende |

---

## 1. Werkzeug

### 1.1 Was verwendet wurde

| Teil | Quelle | Zweck |
|---|---|---|
| binutils 2.42 (Quelltext, 27 567 160 Byte) | GNU | Blackfin-Disassembler (`bfin-objdump`, `bfin-nm`, Ziel `bfin-elf`) |
| gdb 14.2 (Quelltext, 24 111 936 Byte, sha256 `2d4dd806...e7772`) | GNU | Blackfin-Simulator (`sim/bfin/run`, Modell bf527, Umgebung user) |
| Python `capstone` | PyPI | ARM-Disassembler für die VSB |

Gebaut mit `configure --target=bfin-elf --disable-gas --disable-ld ...` (binutils) und
`--enable-sim --disable-sim-igen` (gdb), beide fertig (configure und make ohne Fehler). Die Quelltexte sind
nur Werkzeugquellen, sie enthalten keine Korg-Daten. Entpackt und gebaut belegt das rund 1 GB (Quellen
605 MB, Extraktionen 935 MB). Offen: die Download-URL ist nicht protokolliert (GNU-Spiegel angenommen), die
mitgelieferte Signatur von binutils wurde nicht gegen einen Schlüssel geprüft.

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
Prozess-Funktion (`+0x18`), zweite Funktion (`+0x1C`), Init-Funktion (`+0x20`). Master-Typen tragen `0x10000`
in `+8`. Code liegt an drei Orten: L1-Instruktionen (`0xFFA0xxxx`), SDRAM unten (`0x0000xxxx`) und SDRAM
`0x01C7xxxx`. Es gibt keinen parametrisierten Einheitseffekt, jeder Typ hat eigenen Code.

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
Master-Einheiten). Die ursprüngliche Schlussfolgerung aus diesem Befund war falsch, siehe die Korrektur am
Ende des Dokuments.

### 3.2 Auswahlkette (gemessen, `ftmap.py`)

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

### 3.4 Neuer Typ, und der Wunsch "fest 18 Hz Low Cut, 20 kHz High Cut"

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

## 4. Erster DSP-Patch und sein Risiko

### 4.1 Wie er aussähe

- In-place, größenneutral, nur Nutzlastbytes eines bestehenden Blocks ändern, **keine** Kopfänderung (Kopf-XOR
  und Block-Struktur bleiben), Stufe 1 (Blöcke 0 bis 4) nie anfassen.
- Datei-Offset: `dsp_extract.vsb_offset(vsb, dspadresse)`. Beispiel (nichts angewendet): die Lader-
  Schrittgröße 64 Byte bei DSP `0x18792` ist VSB-Datei `0x1127F6` (RAM `0xC01126F6`), die 128 bei `0x189D0`
  ist Datei `0x112A34`. Ob größere Schritte die Lücke verkürzen, ist offen (hängt an der Aufrufrate in 2.3).
- Für die Wartezeit-Änderung und einen neuen Filtertyp braucht der erste Schritt keinen DSP-Patch: die
  ARM-Wartezeit (`0xC003E244`) und ein Typ 17 sind reine ARM-Änderungen.

### 4.2 Was der Emulator-Check abdeckt (gemessen: nichts am DSP-Strom)

Der Emulator ersetzt `0xC0011AB8` (DSP-Upload) durch einen Stummel (`machine.py`, `_dsp_upload`): R0 = 1,
zurück. Damit liest der Emulator die Strombytes nie, und `bootmap.json` hat keinen Bereich im Strom
(`0xC00F9E10` bis `0xC013C0B0`). Folge: ein geändertes DSP-Byte besteht die Start-Phase-Prüfung (`check.py`)
ohne Befund, obwohl der Upload auf jedem Startweg läuft, vor der Tastenabfrage (68,66 ms gegen 69,5 ms).
Geprüft wird nur `dsp_boot_once` (der Upload zählt einmal). Die Regeln in [../patcher.md](../patcher.md)
("gesperrte Bereiche = was bootmap misst") sperren den Strom damit nicht. Wer DSP-Patches erlaubt, muss ihn
dort ausdrücklich behandeln.

Fehlende Prüfungen (billig, der Parser steht in `dsp_extract.parse`): Kopf-XOR und `0xAD` je Block, Länge
`0x422A0`, FINAL-Block vorhanden, Stufe-1-Blöcke gleich dem Original, geänderte Spannen disassemblieren und
zeigen, nur erlaubte Adressbereiche.

### 4.3 Risiko

- **Hochladen ohne Zeitgrenze (offline).** Beim Hochladen wartet der ARM zuerst bis zu 1000 mal auf "bereit"
  (`0xC0011AE4`), dann pro Byte (`0xC0011B78`) und nach dem letzten Byte (`0xC0011C30`) ohne Zeitgrenze, den
  Eingang liest `0xC00171A8` (GPIO, Bit 12). Ein Block, den der Boot-Rom des DSP ablehnt (Kopf-XOR falsch,
  Stufe 1 kaputt), kann den ARM in einer dieser Schleifen festhalten, **vor** Panel-Austausch, Tastenabfrage
  und Update-Abfrage. Dann hilft EXIT nicht, der Rückweg wäre JTAG
  ([../messungen/2026-10-08-firmware-rueckweg.md](../messungen/2026-10-08-firmware-rueckweg.md)). Ein DSP,
  der erst nach dem Laden stirbt (Anwendungscode falsch), hängt den Upload nicht, ist aber schwerer zu
  beurteilen: der Emulator-DSP antwortet immer sofort.
- **Mailbox-Hänger (offline):** wartet der DSP-Frame-Task nicht mehr, blockiert der ARM beim nächsten Frame
  (Bit 31 wird nie gelöscht). Im Emulator greifen Update-Abfrage und Start-Taste 8 ("Data Util") in den
  ersten 1,5 s nicht auf den Host-Port zu (gemessen), der normale Start erst bei 93,1 ms nach den
  Rettungsentscheidungen. Das stützt, dass die SD-Update-Wege einen toten DSP überleben könnten, ist aber
  nur im Emulator gesehen (**offen** am Gerät).
- **Rückweg:** alte VSB zurückflashen (Menüweg, setzt eine lebende Anwendung voraus), sonst JTAG. Der Menüweg
  ist am Gerät geübt ([../messungen/2026-10-10-rueckweg-geuebt.md](../messungen/2026-10-10-rueckweg-geuebt.md)),
  der JTAG-Weg ist dort nicht beschrieben als geübt.
- **Kein Vorlauf:** kein Emulator-DSP, keine Zeitmessung, Simulator nur für reine Funktionen. Es gibt keine
  Erfahrung Dritter (Hacktribe hat den DSP nie geändert, gemessen).
- **Idee zur Entschärfung (offen):** der ARM spricht beliebige DSP-Adressen über den Host-Port an (Lese- und
  Schreibkommandos `0xA9`/`0xAB` mit 32-Bit-Adresse, Wrapper `0xC0014284`, `0xC00141F8`). Ein DSP-Patch im
  SDRAM oder in L1-Daten ließe sich damit zur Laufzeit aus einem RAM-Stub einspielen, ein Neustart stellt den
  alten Stand her. Offen: ob SDRAM-Code im L1-Instruktionscache steht (veraltete Zeilen), ob
  L1-Instruktionen erreichbar sind, und ob das Gerät den Stub-Weg zulässt (Hook `0xC0170540`).

---

## Offen

- Wer liest Wort 37 (`+0x94`) im Audiopfad, und was zeigt ein Gerätetest mit nur einem geänderten Insert-Typ
  (schweigt der Part ganz, bleibt Dry)?
- Aufrufrate des Laders und Blockzeit des DSP (bestimmt die 100 ms).
- Wo ist SDRAM frei (für einen zweiten Effektplatz)?
- A34-Befehle 0x34 bis 0x3B und der Standardhandler `FFA04F50` nicht dekodiert.
- Frame- und Lader-Verhalten im Simulator (Schreibwarteschlange initialisieren, dann nachspielen).
- Aufrufkonvention der Filterkerne und Impulsantwort der e-Familie (für ein Band von 18 Hz bis 20 kHz).
- Was tun die unerreichbaren Arten 0, 8, 14, 19?
- Welche Anweisungen im ARM-Code den Filtertyp setzen (siehe Korrektur).

## Nächste Schritte

1. Gegenprobe am Gerät ohne Code (billig): zwei Patterns, die sich nur in einem Insert-Typ unterscheiden,
   Aufnahme: schweigt der betroffene Part, laufen die anderen weiter? Das entscheidet Wort 37 (Abschnitt 2.5).
2. Ohne Gerät: den Emulator-Check um eine DSP-Strom-Prüfung erweitern (Parser aus `dsp_extract.py`) und den
   Strom in [../patcher.md](../patcher.md) als gesperrten Bereich aufnehmen, bevor irgendein DSP-Patch
   gebaut wird.
3. Typ-17-Prototyp (nur ARM) mit festem Cutoff bauen und im Emulator prüfen, parallel die Impulsantwort der
   e-Familie im Simulator messen.

---

## Korrektur 2026-10-14: Filtertypen in Stock und Hacktribe

Abschnitt 3.1 und Kurzfassung 5 sagten ursprünglich, Stock und Hacktribe seien in allen Filtertabellen
identisch und "Hacktribe hat Filtertypen hinzugefügt" sei durch die Dateien nicht gedeckt. Der erste Teil
stimmt, der Schluss daraus war falsch. Die offene Frage, ob Stock-Firmware und Hacktribe in der Oberfläche
dieselben Filtertypen anbieten, ist damit beantwortet: **nein**. Die Feature-Liste von Hacktribe (Filter)
stimmt.

**Was falsch war.** Verglichen wurden Daten: Namenscode, Typkarte, Vorlagen, Rechner und der DSP. Die gibt es
in Korgs Sampler-Firmware tatsächlich komplett, alle 16 Typen samt Namen. Ob die Oberfläche sie *anbietet*,
hängt aber nicht an diesen Tabellen, sondern an der Tastenbehandlung im ARM-Code, und die lag außerhalb der
verglichenen Bereiche. Eine Lücke in der Datenlage wurde als Beleg für "gleich" gelesen. Schon der Diff
(`diff16.txt`) zeigte den Unterschied: Hacktribe leitet neun Aufrufe und Sprünge im Tastencode auf neuen Code
um.

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

**Nachtrag 2026-10-15.** Die offene Frage ist beantwortet ([Messung](../messungen/2026-10-15-synth-filter.md)): die Auswahl der Typen sitzt in der Tastenfunktion `0xC006FC80` (drei Sprungtabellen, die nur 0, 1, 7 und 12 kennen), und der Teilsetter `0xC00495B8` faltet die Typen 2 bis 6, 8 bis 11 und 13 bis 16 beim Schreiben auf 1, 7 und 12 zurück. Der Schalter ist der eine bedingte Sprung `0xC00495DC`, den Hacktribe unbedingt macht, dazu die Tastenfunktion. Ein Patch mit beiden Stellen gibt Korgs Build die Synth-Filter ([Patcher](../patcher.md)).

**Folgen.** Der DSP braucht für die Hacktribe-Filter keine Änderung (Kern und Tabellen sind schon da, siehe
3.2), die Freischaltung ist reiner ARM-Code. Die Messung
[../messungen/2026-09-17-filter-types.md](../messungen/2026-09-17-filter-types.md) ("Hacktribe hat weitere
Filter in die Lücken gelegt") stimmt in der Sache, auch wenn "in die Lücken" aus der Werksbank geraten war:
die Lücken sind die Typen 2 bis 6 und 8 bis 11, 13 bis 16 der 17er-Karte. Die Namen aller 16 Typen stehen in
der Firmware (siehe [../messungen/2026-10-14-fx-tabellen.md](../messungen/2026-10-14-fx-tabellen.md)).
