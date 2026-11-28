# Plugin-Laufzeit: Firmware-Tasks, Haken, Speicher, Hardware-API, Menüs

Hintergrund zur [Plugin-Laufzeit](../plugins.md) der Electribe: wo die Laufzeit in die Firmware eingreift, wie
Plugin-Code sicher ausgeführt wird, wo er im Speicher liegt und welche Firmware-Funktionen er nutzt. Alle Adressen
gelten für Firmware 2.02 (Korgs Original und [Hacktribe](../glossary.md#hacktribe), gleiche Adressen). Grundlage sind
die [`SYSTEM.VSB`](../glossary.md#vsb), ein Flash-Dump und ein RAM-Dump vom Gerät sowie Läufe im Emulator.

Markierungen: **gemessen** (im Emulator ausgeführt oder im Gerät-Dump gelesen, dann steht "Gerät"), **offline**
(Disassembly gelesen), **hergeleitet**, **offen**.

## Überblick

Die Laufzeit führt Plugins als Bytecode in einer [VM](../glossary.md#vm) aus, nicht als nativen Code: die Firmware hat keinen
belegten Speicherschutz zwischen Plugins und Firmware, und kein Watchdog fängt eine Endlosschleife ab (Abschnitt 2).
Die VM prüft Felder bei jedem Zugriff, begrenzt die Laufzeit mit einem Kraftstoff-Zähler und meldet einen Fehlercode,
statt abzustürzen. Sie greift an fünf Stellen ([Haken](../glossary.md#haken)) in die Firmware ein, jede mit [Notschalter](../glossary.md#notschalter) (EXIT beim Einschalten):

1. **Eingangsfilter** am ersten Wort von `0xC002837C` (CsTask): schreibt Taste, Drehgeber, Regler, Pad und Touchpad in
   einen Ring und verschluckt auf Wunsch. Mit Maske 0 gleich der Firmware ohne Patch.
2. **Rahmen-Haken** bei `0xC00836FC` (UiTask, 25 Hz): leert den Ring in Plugin-Handler, ruft "frame" und zeichnet in
   den Display-Puffer. Die Firmware flusht selbst.
3. **Start-Haken** am Aufruf `0xC002ADAC` (nach den Rettungswegen): nur Variablen, Registrierung, Startbild. LEDs und
   Display setzt erst "ready" (erster Rahmen), weil die Firmware sie bei 99 bzw. 400 ms überschreibt.
4. **Speicher-Haken** am Eintritt von `0xC004C1B4` (WRITE auf Global und Ausschalten, CommandTask): Plugin-Variablen in
   den Flash, CRC zuletzt.
5. **Menü:** ein eigener Top-Level-Bildschirm `0x2D` zwischen Global und Data Util, Plugin-Seiten als Daten. Ohne Seiten
   verhält sich die Firmware wie ohne Patch.

Einen schnelleren Takt als 25 Hz, der für Plugins sicher ist, gibt es nicht. Ereignisse aus Sequencer-Tasks erreichen
Plugins nur über den Ring im 40-ms-Raster.


## 1. Ereigniskatalog

### 1.1 Wie die Firmware aufgebaut ist (RTOS mit zehn Tasks)

Zehn Tasks, Namen aus den Quelldateien in den Assertion-Texten (offline), Prioritäten aus den Deskriptoren bei `0xC00A37A8` (Feld `+12`). **Kleinere Zahl heißt wichtiger**: der Einreihcode `0xC00018F0` unterbricht nur, wenn die neue Priorität kleiner ist als die laufende (offline).
Hochwassermarken aus dem RAM-Dump vom Gerät.

| Nr | Name | Prio | Stack | Einstieg | Rolle (gemessen) | Stack-Hochwasser am Gerät |
|---|---|---:|---:|---|---|---:|
| 1 | StartupTask | 8 | 9128 B | `0xC002AB7C` | Initialisierung bis `0xC002ADAC` (Start-Hook-Stelle), danach beendet | 576 B |
| 2 | PeriodicTask | 1 | 9216 B | `0xC002AA34` | wacht mit 500 Hz auf (2 ms), fünf Softwaretimer (viermal 40 ms, einmal 100 ms), sendet den Display-Frame, zählt Auto Power Off (2,0 ms) | 336 B |
| 3 | CentralServiceTask | 3 | 18432 B | `0xC002A3C0` | Panel-Eingänge: `0xC002837C`, wendet Regler direkt an | 768 B |
| 4 | UiTask | 4 | 9216 B | `0xC002B144` | Tasten-Verteiler `0xC00700D8`, Bildschirme, Takt `0xC006F178` (alle 40 ms) | 864 B |
| 5 | CommandTask | 6 | 1 MiB | `0xC002A598` | SysEx, Pattern laden (`0xC004A8E4`), Globals speichern (`0xC004C1B4`), Ausschalten | 3776 B |
| 6 | (unbekannt) | 0 | 9216 B | `0xC00245F0` | | 328 B |
| 7 | usbmidi | 0 | 9216 B | `0xC002C980` | | 184 B |
| 8 | SDCardDriverTask | 5 | 9216 B | `0xC001DA9C` | | 528 B |
| 9 | VoiceTask | 7 | 9216 B | `0xC002B220` | 2-kHz-Schleife, DSP-Briefkasten | 604 B |
| 10 | SeqTask | 2 | 9216 B | `0xC002AACC` | Sequencer | 840 B |

Folgen für Plugins (hergeleitet aus der Tabelle): **jeder Handler in der UiTask hält die VoiceTask (Prio 7) und die CommandTask (6) an**, solange er läuft; jeder Handler in CsTask oder SeqTask hält zusätzlich die UiTask an.
Plugin-Code läuft deshalb nur in der UiTask, und die höher priorisierten Tasks reichen nur Daten weiter (Ring, siehe 1.3).

**Eingabeweg (gemessen):** der UART-Interrupt füllt eine Queue, die CsTask (3) holt die 5-Byte-Nachricht und ruft die Verteilerfunktion **`0xC002837C(msg)`** (Typ in `msg+0xC`, Daten `msg+0xD` bis `+0x10`). Diese ruft je Typ den Handler der Firmware
(Taste `0xC0042BB8(key, down)`, Drehgeber `0xC00419B4(idx, delta)`, Regler `0xC0040A50(idx, wert16)`, Pad `0xC0044874(idx, an, wert16, 1)`, Touchpad (Typ 5, Zweig bei `0xC00284B4`), Ausschalt-Taste Typ 6, Netzteil Typ 7 über `0xC0083AAC`). **Der Regler-Handler `0xC00423A0` setzt den Parameter schon in der CsTask**
und meldet nur danach über `0xC0083B2C` an die UI. Ein Haken auf den Posting-Funktionen `0xC00839F0` bis `0xC0083C9C` verschluckt deshalb den Parameter nicht (gemessen: Parameterblock änderte sich trotz Haken). Der Haken auf `0xC002837C` verschluckt alles.
Die UiTask bekommt Tasten über `0xC0083FE8` (Queue) und ruft dann `0xC00700D8(this, key, down)` und die vtable-Slots des aktuellen Bildschirms.

### 1.2 Die Ereignisse

Raten gelten für das Gerät bei 160 BPM (aus Läufen mit `machine.SLICE = 2000`, siehe "Methode": mit dem Standardwert verliert der Emulator 13 bis 21 % der 1-kHz-Interrupts und alle Takte laufen zu langsam).
"Haken" ist die Stelle, an der der Patcher eingreift. Funktionseingänge beginnen mit `push` oder einem registerrelativen `ldr` und lassen sich ersetzen (der erste Befehl läuft dann im Stub), Ausnahme `0xC005E914` (pc-relativ, dort bei `0xC005E918` einhaken).
Im Stub sind r0 bis r3 und r12 frei (AAPCS), r4 bis r11 und lr muss er erhalten.

**Eingaben** (alle durch den einen Eingangsfilter `0xC002837C`, CsTask, siehe 1.3; Plugins sehen sie im nächsten 40-ms-Rahmen):

| Ereignis | Ring-Eintrag (Typ, b1, b2, b3, b4) | Firmware-Handler dahinter | Verschlucken |
|---|---|---|---|
| buttonPress / buttonRelease | `(0, Taste, down)` | `0xC0042BB8(Taste, down)`, später UiTask `0xC00700D8` | ja (Maske Typ 0) |
| encoder (Drehgeber, Hauptrad ist Index 0) | `(1, idx, 0, delta)` | `0xC00419B4(idx, delta)` | ja |
| knob (Regler 0..19, Wert 0..1023) | `(2, idx, hi, lo)` | `0xC0040A50(idx, wert)`, wendet den Parameter an | ja |
| padPress / padRelease | `(4, idx, 0, velocity, an)` | `0xC0044874(idx, an, wert, 1)` | ja |
| touchpad (Berührung `(5, xh, xl, yh, yl)`, Loslassen ist Taste `0x22`) | `(5, 1, 144, 1, 144)` für x = y = 400 | Zweig bei `0xC00284B4` | ja |
| Ausschalt-Taste (Typ 6), Netzteil (Typ 7) | | `0xC0083AD8`, `0xC0083AAC` | nein, der Stub lässt sie immer durch |

**Lebenszyklus, Takt, Bildschirm, Speichern:**

| Ereignis | Haken | Task | Rate | Hinweis |
|---|---|---|---|---|
| start | Aufruf `0xC002ADAC` (nach den Rettungswegen) | StartupTask (1), SVC, IRQ an, Zeit 74,8 ms (Emulator) | einmal | vor dem RTOS-Takt; LED und Display aus dem Start werden bei 99 bzw. rund 400 ms überschrieben; nur für Variablen, Registrierung, Startbild |
| ready | erster Rahmen-Haken mit Bildschirm 1 aktiv | UiTask | einmal | dort bleibende LED- und Display-Zustände setzen |
| tick / frame | `0xC00836FC` (nach `0xC006F178`) | UiTask | 25 Hz (40 ms) | das Plugin zeichnet hier; die Firmware flusht 38 ms später |
| menuOpen / pageChange | `0xC006E8BC` (r1 = n), Global-Seite `0xC0064948`, Pattern-Menü per Takt-Abfrage | UiTask | pro Wechsel | siehe 5.4; `0xC0067270` ist kein sauberer Haken |
| write (WRITE) | `0xC006F094` (Bildschirmnummer in `[r0+0x1c]`); Globals speichern `0xC004C1B4` | UiTask / CommandTask | pro Druck | |
| powerOff | Beginn `0xC0038A54`, kurz vor dem Stromabschalten Aufruf `0xC0038B4C` | CommandTask (5) | einmal | rund 1 s Zeit (Emulator), Stromhaltung fällt erst nach dem Schreibaufruf der Runtime |
| powerSave / Netzteil | Setzen des Dimm-Flags `0xC0028AB4(dim)`, Entscheidung `0xC0051140` | UiTask | bei Netzteil- und Einstellungsänderung | Power Save selbst ist kein Zustand (4.3) |

**Sequencer und Transport** (Messung 12 s Play mit `SLICE = 2000`; Abstände min / mittel / max in ms):

| Ereignis | Haken | Task | Rate | Abstand | Argumente |
|---|---|---|---|---|---|
| sequencer step (16tel, 0..63 pro Part) | `0xC00589EC` | SeqTask (10) | 10,67 Hz | 92,0 / 93,75 / 94,0 | keine; Schrittzähler `0xC06904B0 + 0x48*part` zeigt den gespielten Schritt |
| beat (Viertel) | `0xC005BD7C` | SeqTask | 2,67 Hz | 374 / 375 / 376 | r0 = 0 |
| bar (Takt) | wie beat mit `[0xC0690DCC] == 1` | SeqTask | 0,67 Hz | 1500 | |
| pattern loop | kein Eingang; Schrittzähler von Part 0 liest 0 | SeqTask | je Muster (1 bis 4 Takte) | | |
| tick (Takt-Einheit) | `0xC005E914` (bei `0xC005E918`), Poll `0xC005F2E8` | SeqTask | 500 Hz | 1,97 / 2,00 / 2,04 | r0 = 12 oder 13 Einheiten (6144 Einheiten/s bei 160 BPM, 576 je Schritt) |
| noteOn / noteOff | `0xC005AD44(part, quelle, note, vel)` / `0xC005A20C(part, quelle, note, 0)` | SeqTask (Quelle `0x10`) oder CsTask (Pad, `0x40`) | je Note | | schickt zugleich MIDI auf DIN und USB |
| play / stop / rec | `0xC0083000(T, 2, 1)` (Play-Zustandsmaschine), Start `0xC005E5E0(0, 1, 0)`, Stop `0xC0082D40(T)` und `0xC005C8F0(1)` in der SeqTask, REC `0xC0082944(T)` | UiTask (SeqTask beim Stop) | je Druck | | `T = 0xC06BC010`, Zustand `[T+0x308]` |
| patternChange (Wahl) | `0xC0081F50(MODEL, index, 1)` | UiTask | je Wahl | | Index wechselt sofort |
| patternLoad | `0xC004A8E4(0xC06B2798, index, 0xC06B6A06)` | CommandTask (5) | je Wechsel | Laden bis ca. 40 ms vor Loop-Ende, wenn gespielt wird | |
| partSelect | `0xC0081BB4(MODEL, part)` | UiTask / CsTask (Pad) | je Wahl | | |
| tempoChange | `0xC004A80C(0xC06B2798, zehntelBPM, 1)` | CsTask (TAP) / UiTask (Menü) | je Änderung | | |
| mute | `0xC0060C74(0xC06CA760, part, 1/0)` | UiTask | je Pad | | |
| mfxType | `0xC0048A64(*0xC0691334+0x4004, typ, 1)` | CommandTask / UiTask | je Wechsel | | von MFX 2 genutzt |

Wichtig für den Aufbau: **alle Sequencer-Haken laufen in der SeqTask (Prio 2)**. Ein Handler dort verschiebt Schritte um seine volle Laufzeit (siehe 1.4). Plugins bekommen diese Ereignisse deshalb nur über den Ring: der Stub in der SeqTask schreibt ein Wort und kehrt zurück,
der Handler läuft im nächsten Rahmen. Samplegenaues Timing (zum Beispiel "bei jedem 16tel eine LED") ist damit auf das 40-ms-Raster begrenzt, der Rahmen darf mehrere Schritte nachholen, der Ring trägt den Schrittzähler mit.
Für das Display-Haustier Blechy reicht das, weil das LCD ohnehin träge ist.

### 1.3 Aufbau der Haken: ein Eingangsfilter, ein Rahmen-Haken, Platz für mehrere Handler

Ziel: möglichst wenige Eingriffe in die Firmware, jeder mit Notschalter (EXIT beim Einschalten, Maske `0x2000` in `*(*0xC033E6F8)+0x18`) und jeder gesperrt, solange "armed" nicht 1 ist (RAM im FF-Bereich liest sich `0xFFFFFFFF`).

| Haken | Stelle | Task | Kosten | Wofür |
|---|---|---|---|---|
| **Eingangsfilter** | erstes Wort von `0xC002837C` wird `b stub` | CsTask (3) | 31 Befehle je Ereignis (124 B Stub) | schreibt jede Taste, jeden Drehgeber, Regler, Pad und Touchpad-Wert (Typ, 4 Byte) in einen Ring (16 Einträge zu 8 B, nur der Stub schreibt `head`, nur die UiTask `tail`) und verschluckt auf Wunsch (Maske je Typ) |
| **Rahmen-Haken** | Anweisung `ldr r0,[pc,#0xc]` bei `0xC00836FC` wird `bl rahmen` (setzt `r0 = 0xC031BB2C`) | UiTask (4) | 209 Befehle ohne Ereignis | läuft alle 40 ms nach dem Zeichnen der Widgets, leert den Ring in Plugin-Handler, ruft den "frame"-Handler, zeichnet; die Firmware flusht selbst |
| Start | Aufruf `0xC002ADAC` (`bl 0xC002A248`) | StartupTask (1) | | "start", siehe 2.3; der Startbild-Editor belegt diese Stelle schon |
| Speichern | erstes Wort von `0xC004C1B4` | CommandTask (5) | | Plugin-Variablen sichern (WRITE und Ausschalten) |
| Menü | Tabelle und Nachbarn, siehe 5.2 | UiTask | | eigene Einträge |

**Eigenschaften dieses Aufbaus (hergeleitet aus den Messungen):**
- **Latenz:** Ereignisse kommen mit Verzögerung von höchstens 40 ms im Plugin an (Ring, Leeren im nächsten Rahmen). Schneller geht es nicht ohne Plugin-Code in der CsTask. Die Verzögerung ist für Spiele und Zähler unkritisch (das LCD schaltet geschätzt 100 ms träge).
- **Verschlucken** muss deshalb vorher erklärt werden: das Plugin meldet über die API eine Maske (je Typ, später je Taste/Regler), die der Eingangsfilter ohne Plugin-Lauf auswertet (fünf Befehle). Eine Entscheidung "diese Taste verschlucken, falls ..." im Handler selbst ist nicht möglich, ohne die CsTask zu blockieren.
- **Ring-Überlauf:** 16 Einträge werden bei einem schnell gedrehten Regler zu wenig. Der Eingangsfilter sollte gleiche (Typ, Index) zusammenfassen (der letzte Wert zählt) oder der Ring 64 Einträge haben (nicht gebaut).
- **Mehrere Handler, ein Haken:** jeder Haken ruft eine Tabelle von Handlern (Kennung des Plugins, Einstieg im Bytecode, Kraftstoff), nacheinander. Ein Fehler schaltet nur dieses Plugin ab, nicht die Runtime. Die Tabelle steht im Abbild und wird beim Export erzeugt.
- **Ein schnellerer Takt als 25 Hz:** gemessen gibt es keinen, der für Plugins sicher ist. Die PeriodicTask (Prio 1) läuft mit 500 Hz und ruft fünf Softwaretimer (Zähler und Nachladewert `20, 20, 20, 20, 50` Takte = 40 ms und 100 ms), aber das ist Prio 1 und Ziel für winzige Rückrufe, nicht für Plugins. Der Timer-IRQ `0xC0025B20` (2 kHz, Dimm-Routine) und die VoiceTask-Schleife (2 kHz) sind keine Plugin-Kontexte.
  Zeit misst das Plugin selbst mit dem 24-MHz-Zähler (Abschnitt 4.1), unabhängig vom Takt.

### 1.4 Rechenlast und wie lange ein Handler laufen darf

- **Last der Firmware (gemessen, Emulator, Platzhalter-DSP):** im Leerlauf am Hauptbildschirm 99,6 % der Stichproben in der Leerlaufschleife (80169 Stichproben, zufällige Abstände); bei laufendem Play 94,2 %, die restlichen 5,8 % in VoiceTask (4,1 %) und SeqTask (1,6 %).
  Die echte Last beim Spielen ist höher, weil die VoiceTask auf den echten DSP wartet. Der Emulator dreht die Leerlaufschleife, Befehlszahlen zeigen die Last nicht.
- **Blockier-Versuch (gemessen, 5 ns je Befehl):**

| Wo | Spinzeit | Schritte spät | VoiceTask-Schleife spät / verlorene Läufe | Anmerkung |
|---|---|---|---|---|
| UiTask oder CsTask, IRQ an | 0,05 bis 0,5 ms | 0,29 ms (Referenz) | 3,8 ms (Referenz) / 0 | folgenlos |
| UiTask | 5,2 ms | 0,29 | 4,8 / 9 | nur die 2-kHz-Schleife leidet |
| UiTask | 52 ms | 0,30 | 51,8 / 103 | nichts wird nachgeholt |
| SeqTask | 0,51 ms | 0,77 | 3,8 / 0 | |
| SeqTask | 5,1 ms | 5,36 | 4,95 / 9 | Schritt verschiebt sich um die Laufzeit, danach holt die SeqTask auf, kein Schritt geht verloren |
| UiTask, **IRQ aus** | 5 ms | 2,26 | 4,6 / 9 | 4 Timer-Aufrufe verloren, **Sequencer-Zeit dauerhaft -3,9 ms** |
| UiTask, **IRQ aus** | 15 ms | 12,26 | 14,6 / 29 | -14 ms Musikzeit |

- **Folgerungen:** Handler in der UiTask dürfen bis rund 0,5 ms ohne messbare Wirkung laufen und bis rund 5 ms, wenn man den Verlust von 2-kHz-Durchläufen der VoiceTask hinnimmt (hörbar oder nicht ist nicht gemessen). Schritte, Takt und Noten bleiben unberührt, weil SeqTask (2) und Interrupts höher stehen.
  Code in der SeqTask unter 0,5 ms halten, Interrupts nie abschalten (Flash-Schreiben im Handler hält die Sperre `0xC0000D80(2)`, das ist Aufgabe der CommandTask).
- **Daraus für den Kraftstoff:** 0,5 ms sind im Emulator-Modell 100 000 Befehle, bei der VM (9,6 je Operation) rund 10 000 Operationen; auf dem Gerät mit ungepuffertem Speicher vielleicht ein Zehntel davon. Deshalb zeitbasiert begrenzen (24-MHz-Zähler, alle 256 Operationen lesen) und nicht nach Operationen.
  Ein Snake-Schritt bei Länge 31 braucht 1763 Operationen und 23136 Befehle (gemessen), weit unter dem Budget.
- **Grundrauschen:** die VoiceTask-Schleife hat auch ohne Zutun Lücken bis 3,8 ms (gemessen, über 5 s eine Lücke von 4,3 ms).

## 2. Ausführungsmodell: Bytecode-VM statt nativer Code

### 2.1 Was die CPU an Fehlerbehandlung bietet

- **Vektortabelle (offline + gemessen):** Das Abbild beginnt bei `0xC0000000` mit acht `ldr pc, [pc, #..]`. UND, SWI,
  PABT, DABT und FIQ zeigen alle auf `0xC000007C`, eine Endlosschleife ohne Anzeige. Nur der IRQ-Vektor wird zur
  Laufzeit gesetzt (`0xC00001D0`). Die Endlosschleife wird in Boot und rund 20 s Bedienung nie erreicht.
- **MMU und Caches:** Der Bootloader richtet die Seitentabelle ein, am Gerät sind MMU und D-Cache eingeschaltet
  (`TTBR = 0x8001C000`, `DACR = 0x00000003` gelesen). Die Bootloader-Tabelle legt den DDR-Bereich in Domäne 0 mit
  Managerrechten ab. Eine getrennte Schutzdomäne für Plugins ist nicht belegt. Details in der
  [MMU-Messung](../messungen/2026-11-06-sample-ram-mmu.md).
- **Watchdog:** In rund 24 s Emulatorzeit schreibt die Firmware nie auf `WDTCR`, der zweite Lader nennt nur den
  Zeitgeberblock `0x01F0D000`. Es gibt also (hergeleitet, am Gerät nicht gemessen) **keinen Watchdog**: ein Plugin mit
  Endlosschleife friert die Task ein, bis jemand ausschaltet.

### 2.2 Warum eine VM

Nativer Code bräuchte Compiler-Masken auf jedem Zugriff, einen Prüfer für den erzeugten Maschinencode und einen
Zähler an jeder Rücksprungkante, und schützt trotzdem nur mit Aufwand vor stillen RAM-Schäden. Die VM bietet dagegen:

- **Speicher:** `LOAD`/`STORE` haben geprüfte Konstanten als Index, Felder prüft die VM mit zwei Befehlen. Ein Plugin
  kann nichts außerhalb seines Variablenfelds ansprechen.
- **Firmware-Aufrufe** nur über eine Tabelle (ID zu Glue-Funktion, feste Argumentzahl), Plugins kennen keine Adressen.
- **Endlosschleife:** Kraftstoff in jedem Befehl, die VM stoppt das Plugin mit einem Fehlercode, das Gerät läuft weiter.
- **Firmware-Version:** Plugins bleiben gleich, nur die API-Tabelle hängt am Build.
- **Browser und Emulator:** derselbe Bytecode läuft in einer JS-VM (Vorschau) und in der ARM-VM, ein Haken am
  Dispatch-Label liefert die Zeilen-Abdeckung.

Der Preis ist die Geschwindigkeit (Abschnitt 2.3). Wo ein Plugin viel rechnen muss, bekommt die API native
Zwischenstücke (Füllen, Bitmap, Text, Linie).

### 2.3 Kosten der VM

- Eine Stapelmaschine mit 32-Bit-Ganzzahlen, Variablen, Konstanten, Sprüngen, Feldern mit Grenzprüfung und
  API-Aufrufen. Die Operationen sind in `data/script/contract.mjs` und `tools/patch/script_vm.s` definiert.
- Kosten je Operation im Emulator, Befehle inklusive Dispatch (**gemessen**): `PUSHB` 8, `PUSHK`/`LOAD`/`STORE` 9,
  `ADD`/`MUL`/`XOR` 10, `LT` 12, `JMP` 13, `JZ` 10, Mittelwert 9,6. Der Dispatch allein sind 5 Befehle (`ldrb`, `subs`,
  `beq`, `and`, `ldr pc`). Nativ kostet dieselbe Summenschleife 16 bzw. 7 Befehle, die VM 163: rund 10- bis 23-mal mehr.
- Die Last bleibt klein: ein Rahmen ohne Ereignis kostet im Rahmen-Haken wenige hundert Befehle, ein Ereignis 100 bis
  700 Befehle, ein Snake-Schritt bei Länge 31 rund 23 000 Befehle (**gemessen**, Emulator, 5 ns je Befehl).
- Am Gerät ist die VM langsamer, als der Emulator rechnet, weil jede Operation mehrere ungepufferte DDR-Zugriffe macht
  (geschätzt 0,5 bis 1 µs je Operation, **hergeleitet**). Deshalb begrenzt der Kraftstoff nach Zeit: alle 256
  Operationen wird der 24-MHz-Zähler `0x01C21010` gelesen.
- Messskript und Werte zum VM-Tempo: [Messung](../messungen/2026-10-12-vm-tempo.md).

## 3. Speicher

### 3.1 RAM für VM, Bytecode und Variablen

| Ort | Größe | Wer sonst | Eignung |
|---|---|---|---|
| FF-Block im Abbild `0xC01A2100` bis `0xC01FFFF0` | 375 KiB | Code der BLECH-Patches (Startbild-Editor, Power-Off-Bild, MFX 2 und weitere), Belegung je Patch in `data/patches/*.json` und [Speicherbereiche](../speicherbereiche.md) | Hier liegen VM, Glue, Bytecode, Variablen und Ring der Laufzeit (der Pool steht in [Plugins](../plugins.md)). Am Gerät gemessen: der Block ist im RAM-Abbild vom Gerät vollständig `0xFF` (Dump von 2026-10-07, 0 Byte abweichend), liegt also im DDR. |
| weitere FF-Läufe im Abbild | `0xC01720B0` bis `0xC01A0000` 183 KiB, `0xC015027C` bis `0xC0170000` 127 KiB, `0xC0148880` bis `0xC0150000` 29 KiB, fünf kleine (2 bis 14 KiB) | Hacktribe-Code liegt direkt davor (`0xC0150000`, `0xC0170000`) | möglich, aber der große Block reicht |
| Heap `0xC06A2940` bis `0xC08A2940` (2 MiB) | | Allokator der Firmware | nein |
| Arbeitspuffer `0xC0D3A940` bis `0xC273AA40` (27 MB) | | Import und Export, Hacktribe nutzt darin `0xC1000000` (SysEx-Upload) und `0xC2000000` (Flash-Lesen) | nein: Nutzung zeitlich nicht getrennt belegt |
| `0xC274F000` bis `0xC4000000` (24 MB) | | niemand bekannt | im RAM-Dump vom Gerät 6318 von 6321 Seiten (4 KiB) nicht null, also nicht geleert (Boot löscht nur `0xC0200000` bis `0xC08A2940`). **Gemessen am Gerät:** ein Muster darin bleibt im Leerlauf, bei USB-Lesen, Import, Aufnahme und SAMPLE EDIT unverändert (0 abweichende Seiten); ein Besitzer ist damit nicht bewiesen und eine Freigabe als Cache nicht erteilt ([Sample-Speicher](sample-speicher.md)) |

- **Physischer RAM:** im RAM-Dump vom Gerät unterscheiden sich `0xC0200000` bis `0xC4000000` und dieselben Adressen 64 MiB höher nur in 31 von 15872 Seiten (4 KiB): Spiegelung bei 64 MiB, also hergeleitet 64 MiB physisch
  (am Gerät gemessen, aber zeitlich zusammengesetzter Dump). Der zweite Lader programmiert den DDR-Controller (Register `0xB0000008` = `(alt und 0xF0000000) oder 0x0813CA22`, `0xB0000010`, `0xB0000014`); der Wert ist nicht dekodiert.
- **Zustand im FF-Bereich startet mit `0xFFFFFFFF`.** Jedes RAM-Wort der Runtime braucht einen Startwert aus dem Start-Haken, und jeder Haken beginnt mit "armed == 1": ein nicht gesetzter Schalter
  (`MASK` = FF) würde alle Eingaben verschlucken. Das ist dieselbe Regel wie bei MFX 2 ("FF heißt aus").
- **Stack-Reserve (am Gerät gemessen):** Hochwassermarken im RAM-Dump vom Gerät, UiTask 864 von 9216 B (9 %), CentralService 768 von 18432, SeqTask 840 von 9216, VoiceTask 604 von 9216, CommandTask 3776 von 1 MiB, StartupTask 576 von 9128. Der Emulator nach Boot und Bedienung: UiTask 856 B. Die VM braucht am ARM-Stack rund 100 B (Frame von `vm_run` 36 B plus Haken 32 B plus Glue); ihren Operandenstapel hat sie im eigenen Feld.

### 3.3 Dauerhafte Variablen (Flash)

Plugin-Variablen im RAM überstehen kein Ausschalten. Für einen "Korg Klicker"-Zähler reicht ein eigener 4-KiB-Datensatz im Muster von Startbild-Editor und MFX 2 (Kennung, Version, Länge, Daten, CRC-32 zuletzt).

- **Wann schreiben:** nicht bei jedem Ereignis (Flash nutzt sich ab, Löschen eines Sektors hält die Sperre `0xC0000D80(2)`). Ein Haken am Eintritt von `0xC004C1B4` (Globals speichern, CommandTask) läuft bei WRITE auf Global **und** beim Ausschalten
  (gemessen im Emulator: Sektor `0x7F1000` wird bei beidem geschrieben, die Firmware speichert danach ihre Globals, das Ausschalten kommt zu Ende bei 1179,6 ms ohne Assertion). Die Stromhaltung fällt erst nach dem Schreibaufruf, das Schreiben der Runtime verzögert den Abschaltvorgang.
  Nur schreiben, wenn sich eine als dauerhaft markierte Variable geändert hat.
- **Wohin (aus dem Flash-Dump, 612 von 3552 Sektoren ab `0x220000` leer):**

| Bereich | Größe | Risiko |
|---|---|---|
| `0x7F1000` bis `0x7FCFFF` | 48 KiB | niedrig, Empfehlung (`0x7F0000` hat der Startbild-Editor, `0x7FD000` und `0x7FE000` die BLECH-Einstellungen ohne Karte, [Messung](../messungen/2026-11-13-einstellungen-flash.md), `0x7FF000` ist die XY-Kalibrierung) |
| `0x7E0000` bis `0x7EEFFF` | 60 KiB | niedrig (`0x7E8000` hat MFX 2, `0x7EF000` die Panel-Kennung) |
| `0xE60000` bis `0xFFFFFF` | 1,6 MiB | mittel (Update-Weg `0x80`) |
| `0x221000` bis `0x22FFFF`, `0x231000` bis `0x23FFFF` | je 60 KiB | mittel (Update-Bereich `0x22` = `0x220000` bis `0x6B0000`) |
| `0x7BC000` bis `0x7DFFFF` | 136 KiB | mittel bis hoch (Update-Bereich `0x75`) |
| `0x628000` bis `0x62FFFF`, `0x631000` bis `0x63FFFF`, `0x661000` bis `0x6AFFFF` | 32 + 60 + 316 KiB | mittel bis hoch |

- **Nicht empfohlen:** der freie Rest des Globals-Sektors (`0x230100` bis `0x230FFF`, im Dump leer, die Firmware lässt ihn beim Speichern stehen, Marker bei `0x230200` überlebte WRITE im Emulator): koppelt Plugin und Globals, und der Update-Weg `0x22` kann den Sektor neu schreiben.
- **Offen:** Löschzeit und Lebensdauer am Gerät, ob das Update von Korg `0x7E` oder `0x7F` anfasst (Länge der Update-Dateien).

## 4. Hardware-API für Plugins

Befehlszahlen sind Unicorn-Befehle, Zeit rechnet mit 5 ns je Befehl (Annahme des Emulators). "Sicher" heißt: im Emulator aus dieser Task ohne Assertion und ohne Verklemmung gelaufen.

### 4.1 Schnittstellentabelle

| Fähigkeit | Funktion und Register | Sicher aus | Kosten | Fallen |
|---|---|---|---|---|
| Tasten- und Ring-LEDs, Pad-Rot/Blau, TAP | `0xC0028600(panel = *0xC033E6FC, index, wert)`; sendet `00 index wert 00 00`, Wert als Byte (0..255), Index 0 bis 0x57 ungeprüft | UiTask, CsTask, SeqTask (mit IRQs an) | 293 Befehle | Queue 1024 B = 204 Nachrichten (`0xC033E648`); ist sie voll, blockiert der Aufrufer bis der UART-IRQ Platz macht (300 Stück am Stück: 43 ms); **bei gesperrten IRQs Assertion `CircularBuffer.cpp:185` und Hänger**. Leitung: 434 µs je Nachricht, rund 2300 pro Sekunde; die Firmware selbst belegt 265/s im Leerlauf, 392/s im SEQUENCER bei Play. |
| LED mit Firmware-Zustand | `0xC0087710(LM = *0xC0345A1C, index, modus, ticks)`: 0 aus, 1 an, 2 Blinken, 3 Blitz, ticks mal 40 ms | UiTask | 404 Befehle | |
| Pad violett | rot `0x2c + 2n` und blau `0x2d + 2n` beide auf 255 | wie Setter | | kein Grün bei Pads (siehe [LED-Execute-Messung](../messungen/2026-10-08-led-execute.md)) |
| Firmware-Neuschreiben stoppen | Byte `LM + 0xB98 = 1`: `0xC00875F4`, `0xC0088284` und alle Firmware-LED-Wege senden nichts mehr (392/s auf 0); der Setter geht weiter. Lösen: Byte 0, dann `0xC00875F4(LM, i, 1)` für i = 0 bis 0x57 | jeder Kontext (ein Byte) | 88 Nachrichten, rund 40 ms Leitung | ohne die Sperre überschreibt die Firmware: Pad-Rot im SEQUENCER bei Play alle 118 ms (136/s), TAP im Beat-Takt, **die 12 RGB-LEDs `0x4c` bis `0x57` jeden Tick (21,7/s) in `0xC0088284`**; Tasten-LEDs und Ringe nur bei eigenem Zustandswechsel |
| Untere RGB-LEDs | Index `0x4c` bis `0x57` über den Setter, mit gesetzter Sperre | wie Setter | | mit Power Save "Auto" auf Batterie schreibt die Firmware 0, mit Netzteil 120 (`0x78`) |
| Display-Puffer | `0xC031B310`, 1024 B, 8 Seiten zu 128, Byte `(y/8)*128 + x`, Bit `y%8` | UiTask im Rahmen-Haken | Kopie 1 KiB: einige hundert Befehle | schreiben ohne Flush reicht (siehe 4.2) |
| Seite füllen | `0xC0015988(seite, spalte, anzahl, an)` | UiTask | 8 Spalten rund 200 Befehle | ohne Dirty-Rechteck nötig |
| Löschen | `0xC0015804()` nur Puffer (547 Befehle), `0xC003F0D4()` mit Zeichenzustand (558) | UiTask | | |
| Pixel, Linie, Rechteck, Füllung, Bild | `0xC003F12C(&x,&y)` (416), `0xC003F2B4(&x0,&y0,&x1,&y1)` (56315 für die Diagonale), `0xC003F4D8(&x,&y,&b,&h)`, `0xC003F55C(x,y,b,h)` (12851 für 128x64), `0xC003F650(&nr,&x,&y)` (2,5 Mio für Bild 13); Farbe `0xC003F10C(&0 oder &255)` | UiTask | | **Überlauf wickelt um, schneidet nicht ab** (Text bei y=40 mit 16 px erscheint oben wieder); die VM muss Koordinaten klemmen |
| Text | Schrift `0xC003F730(&index)` (Tabelle `0xC00C2818`: 0 klein 8 px, 1 fett 16 px, 2 fest 12 px, 3 dünn 16 px); `0xC003F7D0(str, x, y, fett, abstand)` mit `abstand` als fünftem Argument **auf dem Stack**; Breite `0xC003F89C(str)`; zentrieren `0xC003F904(str, &y, &x)` | UiTask | 15 Zeichen: 88k (Schrift 0), 267k (Schrift 1), 102k (Schrift 2) | der Assert-Handler ruft `0xC003F7D0` genauso, also ist die Signatur belegt |
| Kontrast | `0xC0015DD0(0xC031BB2C, 4, &byte)`, Bereich 0x12 bis 0x2A | UiTask | | wirkt beim nächsten Flush |
| Display-Licht | `0xC0016BB4(0x01E26000, an, 3, maske)`, Maske `0x08` rot, `0x10` grün, `0x20` blau; 40 Befehle, nur Set/Clear-Register | beliebig (läuft auch im Timer-IRQ) | 40 | auf Batterie überschreibt der Dimm-IRQ (siehe 4.3) |
| Uhr | 24-MHz-Zähler `0x01C21010` (Firmware nutzt ihn in `0xC001673C(0xC031BB20, µs)`) | beliebig | 1 Lesezugriff | Auflösung 1/24 µs; Plugin-Ereignisse selbst kommen höchstens alle 40 ms |
| Gehaltene Tasten | **kein** laufender Bitplan (`*(*0xC033E6F8)+0x18` ist nur der Schnappschuss vom Start); das Plugin führt ihn aus den Tasten-Ereignissen selbst | | | |
| Regler-Werte | Panel-Wert 0..1023 im Emulator; laut Code des Panels schickt das echte Panel höchstens 255 ([Panel-Controller](panel-controller.md)); die Firmware speichert `wert >> 1` als u16 ab `+0xF4` im Objekt `*(*0xC0691240 + 8)` (Heap-Adresse); gemessen für Regler 0, 3, 5 bis 10; Regler 1, 2, 4 anders abgebildet | | | Rohwert zuverlässig aus dem Ereignis (CS-Ring, siehe 1.3) |
| Nicht vorhanden | Buzzer, 7-Segment-Anzeige: keine Strings, kein Host-Befehl | | | |

### 4.2 Den Bildschirm besitzen

- **Die Firmware flusht selbst (gemessen):** alle 40 ms sendet die Periodic-Task (Task 2, Prio 1) den Frame (`0xC0015DD0(DISP, 3, ..)`, vergleicht jede Seite mit der zuletzt gesendeten Kopie); 2 ms später zeichnet die UiTask die Widgets in den Puffer (`0xC006F178`)
  und ruft `0xC0015DD0(DISP, 2, 0)`. Was im Tick im Puffer steht, ist nach 38 bis 40 ms im Display.
- **Haken (gemessen):** die Anweisung `ldr r0, [pc, #0xc]` bei `0xC00836FC` (direkt nach dem Aufruf von `0xC006F178`) wird zu `bl stub`; der Stub setzt `r0 = 0xC031BB2C` und kehrt zurück. Ein hineingeschriebenes Muster hielt in 12 von 12 Proben über 0,6 s,
  ohne dass der Stub flusht; Menü, Drehgeber, Play und WRITE änderten nichts daran; alle anderen Seiten waren gleich der Firmware ohne Patch; 470 Befehle je Takt für 128 Byte Füllung.
  Die vorhandenen Patches nutzen `0xC00836F8` (MFX 2): kein Konflikt.
- **Bildschirm ganz übernehmen:** den Puffer im Haken zuerst löschen (`0xC0015804`), dann zeichnen. Wer in einem Tasten-Handler außerhalb des Takts zeichnet, wird überschrieben, sobald die Firmware das Widget neu malt (ein ganzes Bild blieb ohne Neuzeichnen 2 s stehen, nur das Batteriesymbol malt sich neu).
- **Sonderfälle:** Fortschrittsbalken (`0xC006038C`), Power-Off (`0xC0038A54`), Assert und Kontrast zeichnen und flushen außerhalb des Takts selbst.
- **Frame-Rate:** 25 Bilder pro Sekunde (40 ms); das LCD selbst schaltet träge (geschätzt 100 ms), 4 bis 8 Bilder pro Sekunde wirken scharf. Mehr braucht das Display-Licht (schaltet sofort).

### 4.3 Power-Save, Auto Power Off und Display-Licht

- **Eine "Power-Save-Schleife" gibt es nicht** (offline + gemessen). Power Save (Global-Seite 16, Byte `*0xC0691324 + 0x29`, Werte 0 bis 2, im Dump vom Gerät 1 = "Auto") ist **kein Bildschirmzustand**. Anzeige, Takt und Flush laufen unverändert weiter,
  der Tick-Haken zeichnet also auch dort. Gesucht wurde in den Strings (`Power`, `Energy`, `Save`, `Auto`, `Sleep`, `Idle`, `Inactiv`), den Globalseiten-Titeln und allen Lesern des Getters `0xC0047340`: keine Leerlauf-Schleife, die nach Inaktivität das Display ändert.
  Was eine frühere Notiz "Energiesparanzeige beim Start" nennt, ist hergeleitet das gedimmte Licht (Flag `0xC00F9310`, bei 101 ms und 328 ms gesetzt).
- **Wirkung von Power Save:** (a) Software-PWM des Display-Lichts, (b) die vier unteren RGB-LEDs, (c) Panel-Nachricht `02 flag 00 00 00` (Wirkung offen). Die Schleife, die einer "Power-Save-Schleife" am nächsten kommt, ist die Dimm-Routine `0xC00289F4` im 2-kHz-Timer-IRQ (`0xC0025B20`):
  Zähler 0 bis 17, Rot und Grün je 2 von 18 Takten, Blau nie (rechnerisch 3,7 %, gemessen 3,5 und 3,8 %). Wert 0 dimmt nie, 1 nur ohne Netzteil, 2 immer.
- **Auto Power Off (Global-Seite 15):** Zähler `*0xC033E6B4 + 0x18` startet bei 7 200 000 (4 Stunden) und fällt alle 2,0 ms (Periodic-Task); jedes Panel-Byte setzt ihn zurück. Bei 0: Ereignis `0xC002D5D8(0x18)`, 3 ms später in der CommandTask `0xC0038A54`: Fenster "Power Off", 1 s Warten, Stromhaltung loslassen.
  Das ist derselbe Ablauf wie bei der Ein/Aus-Taste.
- **Display-Licht besitzen (gemessen):** `0xC0016BB4` ist von jedem Kontext sicher. Auf Batterie mit "Auto" überschreibt der Dimm-IRQ jede Farbe alle 0,5 ms. Flag `0xC00F9310 = 0` allein reicht nicht: Netzteil stecken oder ziehen (`0xC0028AB4`, UiTask) setzt es neu.
  Robust: Flag 0, Farbe setzen, erstes Wort von `0xC0028AB4` auf `bx lr` (`0xE12FFF1E`), I-Cache leeren (`0xC00016A4`); danach blieb Blau nach Stecken und Ziehen stehen. Zurück: Originalwort `0xE59F3044`, Flag aus der Einstellung neu setzen (`0xC0051140`).
  Eigenes Dimmen braucht eine eigene PWM im 2-kHz-Takt (Haken bei `0xC0025B60`, nicht gemessen); aus dem 22-Hz-Takt flimmert es. Messungen zur LCD-Helligkeit: [../messungen/2026-10-12-lcd-helligkeit.md](../messungen/2026-10-12-lcd-helligkeit.md).

### 4.4 Zustand lesen und Aktionen auslösen (Transport, Pattern, Parameter)

Die Aufrufe liefen im Emulator aus dem UI-Takt ohne Assertion (der Hilfsaufruf `Dev.call` ist dafür ungeeignet, er schaltet Interrupts ab und schiebt keine Zeit).

**Lesen (RAM, Wörter little endian):**

| Was | Adresse | Einheit |
|---|---|---|
| Transport-Zustand (0 Stop, 1 Play, 2 Pause, 3 REC bereit, 4 Aufnahme) | `0xC06BC318` (T `0xC06BC010` + 0x308) | Wort |
| Sequencer verteilt Takt | `0xC068FC6C` | Byte |
| Tempo | `0xC0691518`; Kopie im Pattern `0xC06B27BE` | Zehntel BPM (1600 = 160,0), 100 bis 3000 |
| Schritt des Parts p | `0xC06904B0 + 0x48*p` | Wort 0..63 |
| Schritt im Takt, Beats bis Taktende | `0xC0690DC0` (Byte, -1 keiner), `0xC0690DCC` (4..1) | |
| Pattern-Index (0-basiert) | `0xC06B2420` (MODEL `0xC06B2108` + 0x318) | 0..249 |
| Gewählter Part | `0xC06B2428` (MODEL + 0x320) | 0..15 (16 = alle) |
| Touchpad-Modus | MODEL + 0x334 | 1 Touch Scale, 2 Master FX |
| Mute des Parts p | `0xC06B2F9D + 0x330*p` | Byte, 1 = gemutet; Roh-Schreiben wirkt nicht |
| Part-Parameter | `0xC06B2F9C + 0x330*p + Offset`: `+0x0B` SAMPLE/OSC EDIT, `+0x0D` CUTOFF, `+0x0E` RESONANCE, `+0x0F` EG INT (vorzeichenbehaftet), `+0x10` MOD TYPE, `+0x11` MOD SPEED, `+0x12` MOD DEPTH, `+0x14` ATTACK, `+0x15` DECAY/RELEASE, `+0x18` LEVEL 0..127, `+0x19` PAN (vorzeichenbehaftet), `+0x21` IFX TYPE, `+0x22` IFX EDIT, `+0x24` OSC PITCH | Byte, Rohwerte |
| MFX-Typ des Patterns | `[*0xC033E6A4] + 65` | Byte |
| Nicht gefunden | Shift gehalten, Haltezustand der 16 Pads: das Plugin führt sie aus den Ereignissen selbst | |

**Auslösen** (Task = aus der gemessen sicher; Dauer im Aufrufer):

| Aktion | Aufruf | Task | Dauer | Warnung |
|---|---|---|---|---|
| Play | `0xC0083000(T, 2, 1)` oder Panel-Weg `0xC0042BB8(2, 1)` dann `(2, 0)` | UiTask | 0,31 ms | |
| Stop | `0xC0082D40(T)` (1,3 bis 2,2 ms) oder `0xC0042BB8(1, 1)`, `(1, 0)` | UiTask, CsTask | | **aus der SeqTask hängt es (Deadlock)** |
| REC bereit | `0xC0082944(T)` | UiTask | 0,25 ms | |
| Pattern wählen | `0xC0081F50(MODEL, index, 1)` | UiTask, SeqTask | 0,05 ms | steht der Transport, lädt die CommandTask sofort; bei Play am Loop-Ende |
| Tempo | `0xC004A80C(0xC06B2798, zehntelBPM, 1)` | UiTask, SeqTask, CsTask | 0,04 ms | `0xC00975A8` allein setzt nur die halbe Welt, nicht verwenden |
| Part wählen | `0xC0081BB4(MODEL, part)` | UiTask, SeqTask, CsTask | 0,15 ms | Einstieg liegt einen Befehl vor dem `push`: nie in den Rumpf springen |
| Mute | `0xC0060C74(0xC06CA760, part, 1 mute / 0 spielt)` | UiTask, SeqTask | 0,01 ms | |
| Parameter | Regler `0xC0040A50(idx 0..10, Rohwert 0..255)`, Drehgeber `0xC00419B4(idx, delta)` | UiTask (läuft sonst in der CsTask) | 0,01 ms | |
| MFX-Typ | `0xC0048A64(*0xC0691334 + 0x4004, typ, 1)` | UiTask | 0,03 ms | |
| Note an / aus | `0xC005AD44(part, 0x10, note, vel)` / `0xC005A20C(part, 0x10, note, 0)` | UiTask, SeqTask, CsTask | 0,01 ms | sendet zugleich MIDI auf DIN und USB |
| Nur Anzeige | `0xC0083B2C`, `0xC0083A18`, `0xC0083A68`, `0xC00839F0` | UiTask | | ändern die Daten nicht |

Sperren (Nummern von `0xC0000D80(n)`): Play und Stop 5 und 6, Tempo 6, Mute 5, Note 5, 3, 4 (die MIDI-Ausgabe). Aufrufe aus der UiTask greifen ohne gegenseitigen Ausschluss auf Sequencer-Daten zu, so wie die Firmware es selbst tut (TAP läuft in der CsTask, Part-Pad in der CsTask, Tasten in der UiTask).

## 5. Menüs: eigene Einträge, die das "start"-Plugin anlegt

Alles im Emulator gemessen, Koexistenz mit dem Startbild-Editor ebenfalls (beide im selben Abbild, keine Assertion).

### 5.1 Wie die Firmware Bildschirme anlegt

- Alle Bildschirme und Fenster kommen aus **einer Fabriktabelle mit 45 Einträgen (Nr. 0 bis 0x2C) bei `0xC00F9CD8`**; `0xC006E664(n, arg)` ruft `tabelle[n](arg)` und liefert 0 für n > 0x2C. Einziger Leser: das Literal bei `0xC006E68C`. Dahinter steht anderes Rodata,
  die Tabelle muss zum Erweitern umziehen (offline).
- `0xC0083D28(n, arg)` postet nur ein Ereignis (Typ 8); der Wechsel läuft in der UiTask in `0xC006E8BC(this = 0xC06C2220, n, arg)` (gemessen). Fenster (Working 0x19, Power Off 0x1C, Pattern schreiben 0x12) kommen über dieselbe Tabelle in `0xC006E9A0`.
- **Der Edit-rechts-Ring (gemessen):** Pattern (3, 15 Seiten) > Part (7, 8) > Step (0x13) > Part Util (0x15) > Sample (0x25) > Global (8) > Data Util (0xE) > Event (0xA) > Pattern. Der Seitenzähler "n/29" ist 15 + 8 + 6.
  Die Ziele stehen als Stubs `mov r0,#N; mov r1,#0; b 0xC0083D28` in den vtable-Slots 4 (links) und 5 (rechts), keiner hat einen anderen Benutzer.

### 5.2 Ein neuer Top-Level-Eintrag (gemessen)

Für einen Eintrag zwischen Global und Data Util (Bildschirm 0x2D) sind nötig:

1. Die 45 Tabellenwörter in den FF-Bereich kopieren, Wort 46 = eigene Fabrik, Literal `0xC006E68C` auf die neue Tabelle.
2. Grenze `cmp r0,#0x2c` bei `0xC006E664` auf `#0x2d`.
3. Nachbarn: Global Edit-rechts (`0xC0064D84`, `mov r0,#0xe`) und Data Util Edit-links (`0xC0061880`, `mov r0,#8`) springen auf einen Stub, der 0x2D wählt, wenn Seiten angelegt sind, sonst das alte Ziel. **Ohne Plugin-Seiten (N = 0) verhält sich die Firmware wie ohne Patch** (gemessen: Edit-rechts von Global geht auf 14, Zähler 28/29).
4. Eigene Klasse: vtable-Kopie von `0xC00E3440` (18 Wörter) mit eigenen Slots 3, 4, 5, 6, 10, eigener Konstruktor nach dem Muster von Bildschirm 9 (Kopf-Widget `0xC0085464`, Seiten-Widget `0xC00856C0`, Reiter `0xC0085218`, Seitenzähler `0xC008A83C`), Objekt 0x34 Byte.

Dazu gehören: Seitenzähler "n/29" nachführen (zehn Immediates oder Haken auf `0xC008A83C`/`0xC008A8A8`: wenn r2 = 29 dann r2 += N, wenn r1 >= 27 dann r1 += N; Ring danach lückenlos 1 bis 29 + N, gemessen), MENU auf dem Hauptbildschirm (Sprung bei `0xC006E8D8`, damit 0x2D als Top-Level zählt;
gemessen: EXIT, MENU kehrt zurück), WRITE (Erstbefehl-Haken auf `0xC006F094`: ohne ihn öffnet WRITE auf dem neuen Bildschirm das Pattern-Schreiben-Fenster 0x12).

### 5.3 Plugin-Seiten: Global-Seiten gegen eigener Bildschirm

- **Global-Technik (Startbild-Editor):** 20 Seiten fest an fünf Stellen (`0xC0064980`, `0xC006498C`, `0xC0064BF0`, `0xC0064BF8`, `0xC0064D04`), drei 20-Einträge-Tabellen am Parameter-Objekt (Index 20 liest hinter die Tabelle), die vtable hängt an **einem** Literal `0xC0064D3C`, das der Startbild-Editor schon belegt;
  zwei Patches können es nicht gemeinsam ersetzen.
- **Der eigene Bildschirm 0x2D.** Eigene vtable, keine 20er-Tabellen, kein geteiltes Literal, kein Konflikt mit dem Startbild-Editor.
- **Seiten als Daten:** je Seite ein 32-Byte-Deskriptor (Titel, min, max, Wert, Enum-Namen, Flags, Callback). Die Runtime zeichnet sie mit drei Firmware-Textfunktionen am Seiten-Widget (Objekt aus `0xC00856C0`, 0xCC Byte): Titel `0xC00857E4(w, char*)`, Wertzeile `0xC0085828(w, char*)`,
  dritte Zeile `0xC0085888(w, char*)` (rund 20 Zeichen, geeignet für Fehlertext). Das Dirty-Byte stößt das Zeichnen im nächsten Tick an.
- **Eingaben (gemessen):** VALUE kommt in vtable-Slot 10 (this, delta ±1), Edit links/rechts in 4/5, MENU in 6, EXIT in 2, rohe Tasten in 3. WRITE kommt zuerst als Slot 3 (this, 0x0E, 1), danach in `0xC006F094`.
- **Grenzen (gemessen):** höchstens 70 Seiten (der Zähler ist zweistellig, ab Summe 100 zeigt er "06/10"); Titel rund 13 breite oder 19 gemischte Zeichen, Wert rund 11 breite; jeder String höchstens 31 Zeichen, weil der Kopierer `0xC000AA64` ungebunden ist und der Puffer 32 Byte hat (die Runtime muss kürzen).
- **Offen:** Reihenfolge und Gruppen bei mehreren Plugins (ein Bildschirm, mehrere Gruppen?), eine nach Bildschirmnummer indizierte Tabelle in einem nicht ausgelösten Pfad ist nicht ausgeschlossen (alle Tasten 0 bis 0x2F am neuen Bildschirm liefen ohne Assertion), VALUE-Sprünge größer als ±1 wurden nicht ausgelöst.
- **Volle Pixelkontrolle (Snake, Klicker mit eigener Grafik):** der Rahmen-Haken (Abschnitt 4.2) oder ein eigenes Widget im Vektor des Bildschirms (Slot 2 zeichnet, wie der Cursor des Startbild-Editors).

### 5.4 Ereignisse rund um Menüs und Speichern

| Ereignis | Haken | Task | Anmerkung |
|---|---|---|---|
| Bildschirmwechsel, Ausführung | erstes Wort von `0xC006E8BC`, r1 = n | UiTask | Objekt noch nicht gebaut; Rückkehr nach `0xC006E664` (bl bei `0xC006E980`): Objekt steht in `[0xC06C2220 + 0x10]`. Hauptbildschirm aktiv = n = 1. |
| Fenster öffnen | `0xC006E9A0` (r1 = Fensternummer) | UiTask | auch aus Task 5 gepostet |
| Global-Seitenwechsel | Eintritt `0xC0064948`, Seite in `[r0 + 0x2C]` | UiTask | Konstruktor ruft ebenfalls |
| Pattern-Menü-Seite | Takt-Abfrage von `[Bildschirm + 0x2C]` bei Nummer 3, oder vtable-Slots 4/5 (`0xC00677A8`, `0xC00677B0`) | UiTask | `0xC0067270` feuert auch beim Loslassen und bei VALUE: kein sauberer Haken |
| WRITE zentral | erstes Wort von `0xC006F094`, `[r0 + 0x1c]` = Bildschirmnummer | UiTask | sieht WRITE auf jedem Bildschirm; 8 und 9 speichern die Globals (`0xC002D5D8(0xB,0,0)`) |
| Globals speichern (WRITE auf Global und Ausschalten) | Eintritt `0xC004C1B4`, r0 = Objekt, r1 = Quelle (0x100 B) | CommandTask (5) | fünf Aufrufer; WRITE-Weg und Ausschalt-Weg gemessen, drei weitere (`0xC002E5F8`, `0xC0031204`, `0xC00317C4`) nicht ausgelöst |
| Ausschalten Beginn | `0xC0038A54` (Handler der Meldung 0x18) | CommandTask | Fenster "Power Off" bei 3,1 ms; Meldung 0x18 kommt aus `0xC0028C2C` (Taste gehalten), `0xC00728F4`, `0xC0074928` |
| Ausschalten, kurz vor Stromabschaltung | Aufruf `0xC0038B4C` (bl `0xC004C1B4`), danach `0xC001734C(0x01E26000, 1)` bei `0xC0038B64` | CommandTask | rund 1175 ms nach dem Fenster (Emulator); die Stromhaltung fällt erst nach dem Schreibaufruf der Runtime |

## 6. Offene Fragen

- Flash-Löschzeit und Lebensdauer am Gerät; ob das Update von Korg `0x7E` oder `0x7F` anfasst.
- Genaue Panel-Helligkeitsstufen, Wirkung der Panel-Nachricht `02 flag` und der Befehle `83`/`84`; Regler 1, 2, 4 (PAN,
  OSC PITCH, EG INT) werden anders abgebildet.
- Chain To / Chain Repeat: die Stelle, die beim Loop-Ende die Kette ausführt, ist nicht gefunden. Shift gehalten und der
  Haltezustand der Pads haben keine RAM-Stelle.
- Weitere Quellen für Note an (Keyboard, Chord, Gate Arp, Touchpad).
- Auto Power Off: 4 Stunden folgen aus 2,0 ms im Emulator; drei weitere Absender der Ausschaltmeldung `0x18` und drei
  weitere Aufrufer von `0xC004C1B4` wurden nicht ausgelöst.
- Ob `0xC274F000` bis `0xC4000000` (24 MB) einen Besitzer hat, den das Muster nicht gesehen hat (Leerlauf, USB-Lesen, Import, Aufnahme und
  SAMPLE EDIT änderten es am Gerät nicht, [Sample-Speicher](sample-speicher.md)); das DDR-Register `0xB0000008` (Wert `0x0813CA22`) ist nicht dekodiert.
