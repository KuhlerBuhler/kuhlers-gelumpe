# Plugin-Laufzeit: Ereignisse, Ausführungsmodell, Speicher, Hardware-API, Menüs

Stand 2026-10-12. Hintergrund zur Plugin-Laufzeit der Electribe, siehe [../plugins.md](../plugins.md). Die Recherche klärt, wo eine Laufzeit in die Firmware eingreifen kann, wie sicher Plugin-Code ausgeführt wird, wo er im Speicher liegt und welche Firmware-Funktionen er nutzen kann (Idee 50 in [../ideen.md](../ideen.md)).

Alle Adressen gelten für Firmware 2.02 mit Hacktribe. Grundlage sind die Firmware `SYSTEM.VSB` (2.02 mit Hacktribe), ein Flash-Dump vom 9.10. und ein RAM-Dump vom Gerät (7./8.10.). Alle Läufe fanden im Emulator oder an diesen Dumps statt, am Gerät selbst wurde für diese Recherche nichts ausgeführt. Die Prototypen (VM, Haken, Menü) patchen nur eine Kopie des Abbilds im Speicher und liegen nicht im Repo, ebenso wenig Korg-Daten.

Markierungen: **gemessen** (im Emulator ausgeführt und gesehen, oder am Gerät-Dump gelesen, dann steht "Gerät"), **offline** (Disassembly gelesen), **hergeleitet**, **offen**.

## Methode und eine Warnung

- Emulator: `tools/emu/machine.py` (Unicorn 2.1.4, ARM926, 5 ns je Befehl angenommen). Der DSP ist eine Attrappe. Die Leerlaufschleife der Firmware (Warten auf Interrupt, `0xC0001808`) wird vom Emulator gedreht, Befehlszahlen zeigen also nicht die Last.
- **Der Emulator lief mit dem Standardwert `machine.SLICE = 20000` mit falschem Takt.** Der 1-kHz-Timer-Interrupt (INT 21) kam nur 791-mal je Sekunde (13 bis 21 % verloren), mit `SLICE = 2000` 1000-mal. Ursache und Behebung: [../messungen/2026-10-12-emulator-takt.md](../messungen/2026-10-12-emulator-takt.md).
  Der Sequencer-Takt wird in genau diesem Interrupt erzeugt. Deshalb zeigten frühere Messungen 46 ms Bildschirm-Takt (19,75 Hz) und 8,25 Schritte je Sekunde. Richtig sind **40 ms (25 Hz) und 10,67 Schritte je Sekunde bei 160 BPM**. Alle Zeiten und Raten in diesem Dokument sind auf `SLICE = 2000` umgerechnet oder damit gemessen, Befehlszahlen sind davon unabhängig.
  **Jeder Plugin-Test im Emulator muss `machine.SLICE = 2000` setzen.** Das gilt auch für ältere Messberichte in `docs/messungen/`: die 22 Hz und 46 ms dort sind dieses Artefakt.
- Zeiten in Emulator-Millisekunden vor 102 ms (Start) sind von dem Fund kaum berührt, der 1-kHz-Takt startet erst bei rund 102 ms.

## Kurzfassung

**Empfehlung: Bytecode-VM (Option b), nicht nativer Code.** Gründe, alle belegt: die Firmware läuft ohne MMU (kein Speicherschutz, ein wilder Schreibzugriff in RAM bricht nichts ab), ohne Watchdog (eine Endlosschleife friert die Task ein), und alle Abbruch-Vektoren zeigen in eine Endlosschleife ohne Anzeige.
Die VM prüft Felder in zwei Befehlen, begrenzt die Laufzeit mit einem Zähler und gibt einen Fehlercode zurück, statt abzustürzen. Sie kostet 972 B und 9,6 Befehle je Operation (10- bis 23-mal mehr Befehle als nativ), aber ein Takt ohne Ereignis kostet 209 Befehle und ein Snake-Schritt bei Länge 31 23136 Befehle.
Ein Prototyp (VM, Eingangsfilter, Rahmen-Haken, API-Glue, Start-Haken, Compiler-Rückgrat) läuft im gebooteten Abbild im Emulator: Snake spielt, Fehlerskripte werden abgeschaltet und das Gerät bleibt danach wie Stock bedienbar.

**Aufbau, den die Messungen tragen** (5 Eingriffe, keiner kollidiert mit MFX 2; Start-Haken und Global-vtable-Literal kollidieren mit dem Startbild-Editor, siehe [startbild-editor.md](startbild-editor.md), die Runtime muss sie besitzen):

1. **Eingangsfilter** am ersten Wort von `0xC002837C` (CsTask): 31 Befehle, schreibt Taste, Drehgeber, Regler, Pad, Touchpad in einen Ring und verschluckt auf Wunsch. Mit Maske 0 gleich Stock.
2. **Rahmen-Haken** bei `0xC00836FC` (UiTask, 25 Hz): leert den Ring in Plugin-Handler, ruft "frame", zeichnet in den Display-Puffer. Die Firmware flusht selbst, nichts anderes überschreibt das Bild bis zum nächsten Takt.
3. **Start-Haken** am Aufruf `0xC002ADAC` (nach den Rettungswegen): nur Variablen, Registrierung, Startbild. LEDs und Display setzt erst "ready" (erster Rahmen), weil die Firmware sie bei 99 bzw. 400 ms überschreibt.
4. **Speicher-Haken** am Eintritt von `0xC004C1B4` (WRITE auf Global und Ausschalten, CommandTask): Variablen in einen eigenen Flash-Sektor (`0x7F1000`), CRC zuletzt.
5. **Menü:** ein eigener Top-Level-Bildschirm 0x2D "Script" zwischen Global und Data Util (Tabelle umziehen, zwei Nachbar-Stubs), Plugin-Seiten als Daten. Ohne Seiten verhält sich die Firmware wie Stock.

**Ereignisse mit Haken:** start, ready, tick/frame (25 Hz), Taste, Drehgeber, Regler, Pad, Touchpad, Seitenwechsel, WRITE, Ausschalten, und über den Ring aus der SeqTask Schritt (10,67 Hz bei 160 BPM, Jitter ±1 ms), Beat, Takt, Note an/aus, Play/Stop/REC, Pattern-Wahl und -Laden, Tempo, Part-Wahl, Mute. Einen schnelleren Takt als 25 Hz, der für Plugins sicher ist, gibt es nicht.

**Größte Risiken:** (1) Code im FF-Bereich des Abbilds war zur Zeit der Recherche am Gerät nicht bestätigt (der Block ist im Gerät-RAM-Dump `0xFF`, also DDR), siehe Abschnitt 6; (2) die VM-Geschwindigkeit am Gerät ist wegen ausgeschaltetem D-Cache nur geschätzt, der Kraftstoff muss zeitbasiert sein;
(3) Handler in der UiTask halten die VoiceTask an (ab rund 5 ms gehen 2-kHz-Durchläufe verloren), Handler in der SeqTask verschieben Schritte; (4) alles ist an Firmware 2.02 mit Hacktribe gebunden; (5) Zustand im FF-Bereich liest sich `0xFFFFFFFF`, jeder Haken muss "armed" prüfen.

## Belegtabelle

| Aussage | Status |
|---|---|
| Zehn Tasks, Namen aus den Assertion-Quelldateien, Prioritäten aus den Deskriptoren (kleiner = wichtiger, Einreihcode `0xC00018F0` unterbricht nur bei kleinerer Zahl) | offline |
| Leerlauf: 99,6 % der Stichproben in der Leerlaufschleife `0xC0001800` (Warten auf Interrupt, der Emulator dreht sie), 80169 Stichproben | gemessen (Emulator) |
| Bei laufendem Play 94,2 % im Leerlauf, 5,8 % in VoiceTask (4,1 %) und SeqTask (1,6 %) mit dem Platzhalter-DSP | gemessen (Emulator, DSP-Attrappe) |
| Eingang: CsTask ruft `0xC002837C(msg)`, danach der Handler je Typ; die UiTask bekommt Tasten über `0xC0083FE8` und `0xC00700D8` | gemessen + offline |
| Der Regler wird schon in der CsTask angewendet (`0xC00423A0`); ein Haken auf `0xC0083B2C` verschluckt den Parameter nicht, ein Haken auf `0xC002837C` schon | gemessen |
| Eingangsfilter-Stub (124 B, 31 Befehle) ist mit Maske 0 gleich Stock und mit Maske ungleich 0 gleich "Ereignis nie dagewesen" (Display, Pattern-Nummer, Hash des Pattern-Blocks) | gemessen |
| Takt `0xC006F178` alle 46,4 ms in der UiTask (Wert mit dem falschen `SLICE`, richtig 40 ms); Anzeige-Flush `0xC0015DD0(.., 3)` 44 ms später in der PeriodicTask, Zeichnen 2 ms vor dem nächsten Flush | gemessen |
| Rahmen-Haken bei `0xC00836FC`: ein gezeichnetes Muster bleibt (12 von 12 Proben), alle anderen Seiten gleich Stock, 470 Befehle je Takt | gemessen |
| PeriodicTask wacht mit 434,5 Hz auf (Wert mit dem falschen `SLICE`, richtig 500 Hz) und treibt fünf Softwaretimer (Nachladewerte 20, 20, 20, 20, 50); SeqTask wartet im selben Takt | gemessen |
| UND, SWI, PABT, DABT, FIQ führen in die Endlosschleife `0xC000007C`; nur der IRQ-Vektor wird gesetzt (`0xC00001D0`, Zeit 52,1 ms); `0xC0000200(index, handler)` setzt Vektoren und hat keinen Aufrufer (Suche über alle `b`/`bl`) | gemessen + offline |
| Die Endlosschleife `0xC000007C` wird in Boot und rund 20 s Bedienung nie erreicht | gemessen |
| MMU und D-Cache werden von keinem ausgeführten Code eingeschaltet; die Hilfsfunktionen `0xC00016C8`, `0xC00016D8`, `0xC00016EC` haben keine Aufrufer; der zweite Lader schaltet nur den I-Cache ein | offline (Suche über `bl`/`b`/Zeiger, Abschnitt des zweiten Laders) |
| Kein Watchdog: kein Schreibzugriff auf `WDTCR` in Boot und Bedienung; der zweite Lader nennt `0x01C21000` nie | gemessen (Firmware), offline (Lader) |
| Fehler in nativem Code lassen sich mit UND/PABT/DABT-Handlern plus setjmp abfangen (Ausnahmeeintritt nachgebaut) | gemessen (Modell) |
| VM: 972 B, 29 Operationen, 9,6 Befehle je Operation (Dispatch 5), gleich der Referenz-VM; Fehlercodes Kraftstoff, Grenzen, Opcode, Division gemessen | gemessen |
| Nativ: Summe-Schleife 16 Befehle (Variablen im Speicher), 7 (Register) gegen 163 in der VM | gemessen |
| VM im gebooteten Abbild: Tasten-Haken, Start-Haken, Ende-zu-Ende mit Eingangsfilter und Rahmen-Haken; Fehler schalten ab, Firmware bleibt bedienbar | gemessen (Emulator) |
| Start-Haken läuft bei 74,8 ms in der StartupTask im SVC-Modus; LED aus dem Start wird bei 99 ms überschrieben, Pixel hält bis rund 400 ms | gemessen |
| Bytecode-Abdeckung aus dem Emulator über einen Haken am Dispatch-Label: 59 von 59 Operationen nach drei Ereignissen | gemessen |
| Snake als Plugin (465 B Bytecode, 244 Operationen) läuft: Schritte, Drehen, Fressen, 20 s ohne Fehler; ein Schritt-Rahmen bei Länge 31 = 1763 VM-Operationen, 23136 Befehle | gemessen (Emulator) |
| FF-Block `0xC01A2100` bis `0xC01FFFF0` (375 KiB) ist im RAM-Dump vom Gerät vollständig `0xFF` | gemessen (Gerät, Dump) |
| Stack-Hochwasser am Gerät: UiTask 864 von 9216 B, CsTask 768, SeqTask 840, VoiceTask 604, CommandTask 3776 | gemessen (Gerät, Dump) |
| `0xC274F000` bis `0xC4000000`: 6318 von 6321 Seiten nicht null, also nicht geleert; Eigentümer unbekannt | gemessen (Gerät, Dump), offen (Nutzung) |
| RAM-Dump: 64-MiB-Spiegelung (31 von 15872 Seiten verschieden) | gemessen (Gerät, Dump, zeitlich zusammengesetzt) |
| Der Zustand im FF-Bereich liest sich `0xFFFFFFFF`; ein nicht gesetzter Schalter verschluckte im Prototyp alle Eingaben | gemessen |
| Der Emulator verliert mit `SLICE = 20000` 13 bis 21 % der 1-kHz-Interrupts; Tick 19,75 Hz, Schritt 8,25 Hz gegen 25 Hz und 10,75 Hz mit `SLICE = 2000` | gemessen |
| Sequencer-Takt: Timer-Interrupt 1 kHz erzeugt ihn (`0xC0025798` > `0xC002BC80`), SeqTask wird alle 2,00 ms geweckt, Schritt 93,75 ms bei 160 BPM, 576 Takt-Einheiten je 16tel | gemessen |
| Haken für Schritt, Beat, Note an/aus, Play, Stop, REC, Pattern, Tempo, Part, Mute mit Argumenten und Jitter (±1 ms) | gemessen |
| Transport-Zustand, Tempo, Schritt, Part, Mute, Part-Parameter im RAM (Tabelle in 4.4) | gemessen |
| UiTask- und CsTask-Code verzögert Schritte nicht (auch 52 ms nicht); VoiceTask verliert ab rund 5 ms 2-kHz-Läufe; SeqTask-Code verschiebt Schritte 1:1; IRQ-aus-Zeit geht 1:1 als Musikzeit verloren | gemessen |
| Stop aus der SeqTask hängt (Deadlock) | gemessen |
| LED-Setter `0xC0028600`: Queue 1024 B = 204 Nachrichten, bei vollem Puffer wartet der Aufrufer (43 ms für 300), bei gesperrten IRQs Assertion `CircularBuffer.cpp:185` | gemessen |
| LED-Sperre `LM+0xB98 = 1` stoppt alle Firmware-LED-Nachrichten; Pad-Rot kommt im SEQUENCER bei Play alle 118 ms neu; RGB-LEDs jeden Takt | gemessen |
| Textfunktion `0xC003F7D0(str, x, y, fett, abstand)` mit vier Schriften, Pixel, Linie, Rechteck, Bild; Überlauf wickelt um | gemessen |
| Die Firmware flusht selbst: Zeichnen im Takt, Flush 38 ms später in der PeriodicTask | gemessen |
| Power Save ist kein Bildschirmzustand, keine Leerlaufschleife gefunden; Dimm-IRQ `0xC00289F4`; Auto Power Off Zähler 7,2 Mio mal 2 ms | gemessen + offline |
| Backlight `0xC0016BB4` aus jedem Kontext sicher; Flag `0xC00F9310 = 0` allein reicht nicht, zusätzlich `0xC0028AB4` auf `bx lr` | gemessen |
| Bildschirm-Fabriktabelle 45 Einträge bei `0xC00F9CD8`; neuer Bildschirm 0x2D im Edit-Ring läuft; Zähler, MENU, WRITE nachgeführt | gemessen |
| Plugin-Seiten (Titel, Wert, Enum, Callback) mit den Firmware-Textfunktionen, höchstens 70 Seiten, Strings höchstens 31 Zeichen | gemessen |
| Globals-Haken `0xC004C1B4` läuft bei WRITE und Ausschalten; Flash-Schreiben auf `0x7F1000` dort funktioniert, Ausschalten kommt zu Ende | gemessen (Emulator) |
| 612 von 3552 Flash-Sektoren ab `0x220000` leer, Risikoeinstufung | gemessen (Dump) |

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
Für das Display-Haustier Blechy (Idee 40 in [../ideen.md](../ideen.md), "Frame pro Trigger") reicht das, weil das LCD ohnehin träge ist.

### 1.3 Aufbau der Haken: ein Eingangsfilter, ein Rahmen-Haken, Platz für mehrere Handler

Ziel: möglichst wenige Eingriffe in die Firmware, jeder mit Notschalter (EXIT beim Einschalten, Maske `0x2000` in `*(*0xC033E6F8)+0x18`) und jeder gesperrt, solange "armed" nicht 1 ist (RAM im FF-Bereich liest sich `0xFFFFFFFF`).

| Haken | Stelle | Task | Kosten | Wofür |
|---|---|---|---|---|
| **Eingangsfilter** | erstes Wort von `0xC002837C` wird `b stub` | CsTask (3) | 31 Befehle je Ereignis (124 B Stub) | schreibt jede Taste, jeden Drehgeber, Regler, Pad und Touchpad-Wert (Typ, 4 Byte) in einen Ring (16 Einträge zu 8 B, nur der Stub schreibt `head`, nur die UiTask `tail`) und verschluckt auf Wunsch (Maske je Typ) |
| **Rahmen-Haken** | Anweisung `ldr r0,[pc,#0xc]` bei `0xC00836FC` wird `bl rahmen` (setzt `r0 = 0xC031BB2C`) | UiTask (4) | 209 Befehle ohne Ereignis | läuft alle 40 ms nach dem Zeichnen der Widgets, leert den Ring in Plugin-Handler, ruft den "frame"-Handler, zeichnet; die Firmware flusht selbst |
| Start | Aufruf `0xC002ADAC` (`bl 0xC002A248`) | StartupTask (1) | | "start", siehe 2.3; der Startbild-Editor belegt diese Stelle schon |
| Speichern | erstes Wort von `0xC004C1B4` | CommandTask (5) | | Plugin-Variablen sichern (WRITE und Ausschalten) |
| Menü | Tabelle und Nachbarn, siehe 5.2 | UiTask | | eigene Einträge |

**Gemessen:** mit Maske 0 ist das Gerät bit-gleich Stock (Display, Pattern-Nummer und Hash des ganzen aktuellen Pattern-Blocks nach Taste, Drehgeber, Regler, Pad und Touchpad); mit Maske 0x37 (alle fünf Typen verschluckt) ist der Zustand gleich der Firmware ohne diese Ereignisse (Pattern bleibt 0, Parameterblock unverändert);
Maske nur Regler und Maske "alle außer Regler" ebenso. Der Ring bekam die Werte: Taste `(0, 11, 0, 0)`, Drehgeber `(1, 0, 0, 1)`, Regler `(2, 3, 1, 244)` (Wert 500), Pad `(4, 5, 0, 100, 1)`, Touchpad `(5, 1, 144, 1, 144)` (x = y = 400); Typ 6 und 7 (Ausschalt-Taste, Netzteil) lässt der Stub immer durch.
Rahmen-Haken: ein gezeichnetes Muster blieb in 12 von 12 Proben über 0,6 s, ohne dass der Haken flusht; Menü, Drehgeber, Play und WRITE ändern daran nichts.

**Ende-zu-Ende:** Eingangsfilter, Rahmen-Haken und VM im gebooteten Abbild: ein Plugin mit Handlern für Taste, Regler und Rahmen zählt drei TAP-Drücke, liest den Reglerwert 800 und zeichnet beides als Balken (12 und 100 Spalten, wie erwartet); die Firmware-Tasten funktionieren weiter (Part< wählt Part 16 wie in Stock);
ein Plugin mit Endlosschleife im Rahmen-Handler wird nach 20000 Operationen abgeschaltet, danach verhält sich das Gerät wie Stock.

**Eigenschaften dieses Aufbaus (hergeleitet aus den Messungen):**
- **Latenz:** Ereignisse kommen mit Verzögerung von höchstens 40 ms im Plugin an (Ring, Leeren im nächsten Rahmen). Schneller geht es nicht ohne Plugin-Code in der CsTask. Die Verzögerung ist für Spiele und Zähler unkritisch (das LCD schaltet geschätzt 100 ms träge).
- **Verschlucken** muss deshalb vorher erklärt werden: das Plugin meldet über die API eine Maske (je Typ, später je Taste/Regler), die der Eingangsfilter ohne Plugin-Lauf auswertet (fünf Befehle). Eine Entscheidung "diese Taste verschlucken, falls ..." im Handler selbst ist nicht möglich, ohne die CsTask zu blockieren.
- **Ring-Überlauf:** 16 Einträge werden bei einem schnell gedrehten Regler zu wenig. Der Eingangsfilter sollte gleiche (Typ, Index) zusammenfassen (der letzte Wert zählt) oder der Ring 64 Einträge haben (nicht gebaut).
- **Mehrere Handler, ein Haken:** jeder Haken ruft eine Tabelle von Handlern (Kennung des Plugins, Einstieg im Bytecode, Kraftstoff), nacheinander. Ein Fehler schaltet nur dieses Plugin ab, nicht die Runtime. Die Tabelle steht im Abbild und wird beim Export erzeugt.
- **Besetzte Stellen der vorhandenen Patches** (aus `data/patches/*.json`):

| Patch | Stellen |
|---|---|
| Startbild-Editor | `0xC002ADAC` (Aufruf, Start), `0xC002AC38` (Aufruf wird `nop`), Literal `0xC0064D3C` (Global-vtable), `0xC0064980` und `0xC0064D04` ("/21"), Code `0xC01A2100` bis `0xC01A4A00`, Flash `0x7F0000` |
| MFX 2 | `0xC00700D8` (erstes Wort, Tasten), `0xC00836F8` (Aufruf, Takt), `0xC0048A64` (erstes Wort, Typ-Setter), `0xC004C2BC` (Aufruf, Pattern schreiben), Code `0xC01A5000` bis `0xC01A5E20`, Flash `0x7E8000` |
| Blech-Startbild | Daten `0xC00F9854` (Bild 13) |

  Der Eingangsfilter (`0xC002837C`), der Rahmen-Haken (`0xC00836FC`), der Speicher-Haken (`0xC004C1B4`) und das Menü (`0xC006E664`, Fabrik, Nachbar-Stubs) kollidieren mit **keinem** davon. Der Start-Haken `0xC002ADAC` und das vtable-Literal `0xC0064D3C` schon: **die Runtime muss den Start-Haken besitzen
  (der Startbild-Editor wird zu einem Eintrag in ihrer Start-Liste) und für die Menüs den eigenen Bildschirm statt der Global-Technik nehmen.** Der Patch-Prüfer lehnt zwei Änderungen an derselben Stelle ab. Die Runtime braucht also eigene "Haken-Besitzer", und die alten Patches werden zu Handlern ihrer Listen (oder bleiben, wenn sie andere Stellen nutzen).
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

## 2. Ausführungsmodell: nativer ARM-Code oder Bytecode-VM

### 2.1 Was die CPU an Fehlerbehandlung bietet (Vektoren, Abbrüche)

- **Vektortabelle (offline + gemessen):** Das Abbild beginnt bei `0xC0000000` mit acht `ldr pc, [pc, #..]` und den Zielen ab `0xC0000020`.
  Reset geht auf `0xC0000070`. UND, SWI, PABT, DABT und FIQ zeigen alle auf `0xC000007C`, und dort steht `bl 0xC000007C`, eine
  Endlosschleife ohne Anzeige. Nur der IRQ-Vektor wird zur Laufzeit gesetzt: der Code bei `0xC00001D0` schreibt `0xC0001560` an Adresse
  `0x34` (Emulator-Haken auf Schreibzugriffe bei 0 bis 0x3F, Zeit 52,1 ms). Die Slot-Tabelle `0xC06A283C` hält die Literaladressen
  `0x20, 0x24, 0x28, 0x2C, 0x30, 0x20, 0x34, 0x38`. `0xC0000200(index, handler)` schreibt einen Handler in ein solches Literal und wird
  von keinem Aufrufer benutzt (Suche über alle `bl`/`b`). Der RTOS braucht also keinen Abbruch-Handler.
- **In 4 s Start plus rund 20 s Bedienung (Menüs, Pattern, Play, WRITE, Touchpad) wird `0xC000007C` nie erreicht** (gemessen im Emulator).
- **Hergeleitet, nicht am Gerät gemessen:** Dass Adresse `0x34` auf dem Gerät beschreibbar ist, folgt daraus, dass die Firmware dorthin schreibt
  und IRQs laufen. Wie die Hardware Adresse 0 abbildet, ist offen: der zweite Lader (AIS, Flash `0x1C`) legt seine eigene Vektortabelle nach
  `0x80000000` (gleiche Form wie die Tabelle im Abbild). Über `0xC0000200` lässt sich der Handler unabhängig davon setzen, wie die Hardware das abbildet.
- **MMU und Caches (offline):** Kein ausgeführter Code der Firmware schaltet die MMU ein. Die Hilfsfunktionen `0xC00016C8` (I-Cache an), `0xC00016D8`
  (D-Cache an) und `0xC00016EC` (TTB, Domänen, MMU an) haben keine Aufrufer und wurden im Start nie ausgeführt. Der zweite Lader schaltet nur den I-Cache
  an (`mcr p15 c1`, Bit 12 bei `0x80000078`). Folge: **ohne MMU gibt es keinen Speicherschutz**, ein wilder Schreibzugriff in RAM löst keinen Abbruch aus. Abbrüche
  kommen nur durch Fehlbefehle (UND) und Busfehler außerhalb des Speichers. Ohne MMU ist der D-Cache praktisch aus (hergeleitet), jeder Datenzugriff geht ans DDR.
- **Watchdog:** In rund 24 s Emulatorzeit (Boot plus Bedienung) schreibt die Firmware nie auf `WDTCR` (`0x01C21028`, `0x01C20028`, `0x01F0C028`, `0x01F0D028`);
  der zweite Lader nennt nur den Zeitgeberblock `0x01F0D000`, nie `0x01C21000`. Es gibt also (hergeleitet, am Gerät nicht gemessen) **keinen Watchdog**: ein Plugin mit Endlosschleife friert die Task ein, bis jemand ausschaltet.
- **Prototyp: Fehler in nativem Code abfangen (Modell).** Der Dispatcher `run_native` sichert r4 bis r11, lr und sp wie ein setjmp und setzt ein Flag. Die Handler in den
  Vektoren UND, PABT, DABT (je rund 12 Befehle plus gemeinsamer Teil) lesen das Flag: gesetzt, dann zurück in den SVC-Modus, sp
  und Register des Dispatchers wiederherstellen, `r0 = 7` zurückgeben; nicht gesetzt, dann `ldr pc, =0xC000007C` (Verhalten wie Stock). Im Emulator (der Ausnahmeeintritt wurde mit Haken nachgebaut,
  denn Unicorn vektoriert nicht von selbst) kehren Fehlbefehl, Datenabbruch lesend und schreibend und Befehlsabbruch alle sauber zurück, r4 und r11 unverändert, sp wie vorher,
  Fehleradresse im Kontext. **Grenze:** das ist ein Modell. Was die echte Hardware ohne MMU überhaupt abbricht, ist unbelegt, und ein wilder RAM-Schreibzugriff bleibt ein stiller Schaden.

### 2.2 Vergleich

| Kriterium | (a) Plugin zu nativem ARM übersetzen | (b) Bytecode-VM im Abbild |
|---|---|---|
| Speicher-Sandbox | Kein Hardware-Schutz (MMU aus). Nur mit Compiler-Masken auf jedem Zugriff und einem Prüfer für den erzeugten Maschinencode (SFI). Ohne Prüfer reicht ein Compilerfehler für stille RAM-Schäden. | `LOAD`/`STORE` haben geprüfte Konstanten als Index, Felder prüft die VM (`cmp`, `bhs`: 2 Befehle). Ein Plugin kann nichts außerhalb seines Variablenfelds ansprechen. |
| Firmware-Aufrufe | Zielliste im Compiler; Aufruf mit falschen Argumenten oder Zeigern läuft ungeprüft in die Firmware | Nur über eine Tabelle (ID zu Glue-Funktion, feste Argumentzahl). Die Plugins kennen keine Adressen. |
| Endlosschleife | Ohne Watchdog friert die Task ein. Möglich: Zähler an jeder Rücksprungkante (`subs; beq`, 2 Befehle), also kein Geschwindigkeitsvorteil mehr bei engen Schleifen. | Kraftstoff in jedem Befehl (1 `subs`, 1 `beq`), gemessen: ein Schleifen-Plugin wird nach 20000 Operationen gestoppt, Plugin aus, Gerät läuft weiter. |
| Fehlerbehandlung | UND/PABT/DABT-Handler plus setjmp (Prototyp ok), erfasst aber nur Abbrüche, nicht stille RAM-Schäden | Fehlercode von `vm_run`, Handler nicht nötig. Die Vektor-Handler bleiben als zweite Linie möglich. |
| Zeit je Operation | gemessen: Summe-Schleife 16 Befehle je Durchlauf (Variablen im Speicher), 7 (Register) | gemessen: 163 Befehle je Durchlauf (17 Operationen, 9,6 Befehle je Operation inkl. Dispatch 5), also rund 10-fach bzw. 23-fach langsamer |
| Code-Größe | rund 4 B je Befehl, 3 bis 8 Befehle je Operation | VM 972 B (844 Code, 128 Tabelle), Glue 96 B, Bytecode rund 1,6 B je Operation (Demo: 70 B für 43 Operationen) |
| Firmware-Version | Adressen im Maschinencode, jede Firmware braucht einen neuen Compilerlauf | Plugins bleiben gleich, nur die API-Tabelle (ID zu Adresse) hängt am Build |
| Emulator-Abdeckung | PC-Spur auf Block-Ebene, zugeordnet über eine Adresstabelle des Compilers | gemessen: ein einziger Haken am Dispatch-Label (`vm_run: loop`) liest bei jeder Operation r4 (Bytecode-Offset) und ergibt Zeilen-Abdeckung, unabhängig vom ARM-Code |
| Vorschau im Browser | braucht den Emulator | derselbe Bytecode läuft in einer JS-VM, Differenztest gegen die ARM-VM bestanden (Summe-Programm: gleiche Variablen, gleiche Operationszahl) |
| Wartbarkeit | Code-Erzeuger (ARM) plus Prüfer plus Handler | VM (rund 1 KiB) einmal bauen, Rest ist Daten |

### 2.3 VM-Prototyp, Messungen

- 29 Operationen (Stapelmaschine, 32-Bit-Ganzzahlen, Variablen, Konstanten, Sprünge, Felder mit Grenzprüfung, API-Aufrufe mit 0 bis 3 Argumenten, Division), gebaut mit dem Assembler `tools/patch/arm.py`,
  972 Byte inklusive Sprungtabelle. Eine Python-Referenz-VM rechnet dasselbe: die Summe-Schleife ergibt in beiden `i=1000, s=1346792`.
- Kosten je Operation (Befehle inklusive Dispatch, gemessen): `PUSHB` 8, `PUSHK`/`LOAD`/`STORE` 9, `ADD`/`MUL`/`XOR` 10, `LT` 12, `JMP` 13, `JZ` 10. Mittelwert 9,6.
  Dispatch allein: `ldrb`, `subs`, `beq`, `and`, `ldr pc` = 5 Befehle.
- Fehler (gemessen): eine Endlosschleife stoppt mit Code 1 nach 10000 Operationen (130010 Befehle, 13 je Operation); Feldindex 50 bei Länge 10 gibt Code 3; ungültiger Opcode 2; Division durch 0 gibt Code 4.
- **Im gebooteten Abbild (Emulator):** Haken am ersten Befehl des Tasten-Verteilers `0xC00700D8`, Plugin "Korg Klicker" (TAP zählt, Pad-LEDs binär, Pixel, Flush): Zähler 5 nach 5 Drücken,
  Pad-LEDs `0x2c`/`0x30` an, keine Assertion. Fehlervarianten: Endlosschleife und Feldfehler schalten das Plugin ab (Zustand 2, Code 1 bzw. 3), alle Pad-LEDs rot, und `Part<` wirkt danach wie in Stock.
  Kosten eines Handler-Aufrufs für eine fremde Taste: 121 Befehle; TAP gedrückt mit vier LED-Aufrufen, Pixel und Flush: 704 Befehle.
- **Start-Ereignis:** Haken am Aufruf `0xC002ADAC` (nach den Rettungswegen). Der Haken läuft bei 74,8 ms in der StartupTask (Task 1), SVC-Modus, IRQ an. Mit EXIT beim Einschalten läuft nichts (Variablen bleiben `0xFFFFFFFF`).
  Ein LED-Setzen im Start geht bei 75,5 ms hinaus und wird von der Firmware bei 99 ms mit 0 überschrieben, ein Pixel im Display hält bis rund 400 ms: **"start" eignet sich für Variablen, Registrierung und Startbild, nicht für bleibende LED- oder Display-Zustände. Dafür braucht es "ready" (erster Takt auf dem Hauptbildschirm).**
- **Ende-zu-Ende:** CS-Stub (siehe 1.3), Rahmen-Haken und VM zusammen. Ein Plugin mit Handlern für Taste, Regler und Rahmen: Zähler 3, Reglerwert 800, Balken auf Display-Seite 7 (12 Spalten, erwartet 3*4) und Seite 6 (100 Spalten, erwartet 800 geteilt durch 8),
  keine Assertion. `Part<` wirkt wie in Stock (blaue Pad-LED `0x4b`). Fehlervariante (Endlosschleife im Rahmen-Handler): Zustand 2, Code 1, danach Display und LEDs nach `Part<` gleich Stock.
  Kosten pro Takt ohne Ereignisse: 209 Befehle (Rahmen-Haken, VM, Glue). Größen: VM 972 B, Glue 96 B, Rahmen-Haken 284 B, CS-Stub 124 B.
- **Zeit auf dem Gerät (hergeleitet, nicht gemessen):** der Emulator rechnet 5 ns je Befehl. Ohne MMU ist der D-Cache aus, jede Operation macht rund 4 bis 6 Datenzugriffe auf DDR (Opcode, Operandenstapel, Variable).
  Bei geschätzt 100 bis 200 ns je Zugriff wären das 0,5 bis 1 µs je Operation, also 1 bis 2 Millionen Operationen pro Sekunde. Das reicht: **Snake als Plugin (465 B Bytecode, 244 Operationen) lief im Emulator** (Schritte, Drehen mit Part< und Part>, Fressen, 20 s ohne Fehler). Ein Schritt-Rahmen kostet bei Länge 3 291 Operationen und 4429 Befehle, bei Länge 20 1158 und 15240, bei Länge 31 1763 und 23136 (alles inklusive der Firmware-Füllaufrufe), also 0,12 ms im Emulator-Modell und geschätzt 1 bis 2 ms auf dem Gerät. **Konsequenz: der Kraftstoff muss nach Zeit begrenzen, nicht nach Operationen** (zum Beispiel alle 256 Operationen den 24-MHz-Zähler `0x01C21010` lesen). 20000 Operationen sind im Emulator-Modell 1,3 ms, auf dem Gerät eher 10 bis 20 ms.
  Verbesserung bei Bedarf: oberster Stapelwert in einem Register.

Messskript und Emulatorwerte zum VM-Tempo (Geräteläufe offen): [../messungen/2026-10-12-vm-tempo.md](../messungen/2026-10-12-vm-tempo.md).

### 2.4 Empfehlung: (b) Bytecode-VM

Ausschlaggebend (alles gemessen oder offline belegt, siehe oben): kein Speicherschutz und kein Watchdog machen nativen Code nur mit Compiler-Masken, Zähler und einem Prüfer für den Maschinencode sicher. Das ist mehr Aufwand
als die VM und garantiert weniger. Die VM kostet 10- bis 23-mal mehr Befehle je Schleifendurchlauf, aber die Last ist winzig (Takt ohne Ereignis 209 Befehle, Ereignis 100 bis 700 Befehle). Dazu: feste API-Tabelle statt Adressen im Plugin,
Abdeckung über einen einzigen Haken, derselbe Bytecode in Browser, Emulator und Gerät. Wo ein Plugin viel rechnen muss, bekommt die API native Zwischenstücke (Füllen, Bitmap, Text, Linie), die die Firmware oder eigene Glue-Funktionen schnell ausführen.

## 3. Speicher

### 3.1 RAM für VM, Bytecode und Variablen

| Ort | Größe | Wer sonst | Eignung |
|---|---|---|---|
| FF-Block im Abbild `0xC01A2100` bis `0xC01FFFF0` | 375 KiB | Startbild-Editor `0xC01A2100` bis `0xC01A3C48` (Zustand und Puffer seit 15.10. bei `0xC0182000`), Power-Off-Bild `0xC01A4A00` bis `0xC01A5000`, MFX 2 `0xC01A5000` bis `0xC01A5E20`; ab `0xC01A6000` bleiben rund 360 KiB | **Empfohlen für VM, Glue, Bytecode, Variablen, Ring.** Am Gerät gemessen: der Block ist im RAM-Abbild vom Gerät vollständig `0xFF` (Dump von 2026-10-07, 0 Byte abweichend), liegt also im DDR. |
| weitere FF-Läufe im Abbild | `0xC01720B0` bis `0xC01A0000` 183 KiB, `0xC015027C` bis `0xC0170000` 127 KiB, `0xC0148880` bis `0xC0150000` 29 KiB, fünf kleine (2 bis 14 KiB) | Hacktribe-Code liegt direkt davor (`0xC0150000`, `0xC0170000`) | möglich, aber der große Block reicht |
| Heap `0xC06A2940` bis `0xC08A2940` (2 MiB) | | Allokator der Firmware | nein |
| Arbeitspuffer `0xC0D3A940` bis `0xC273AA40` (27 MB) | | Import und Export, Hacktribe nutzt darin `0xC1000000` (SysEx-Upload) und `0xC2000000` (Flash-Lesen) | nein: Nutzung zeitlich nicht getrennt belegt |
| `0xC274F000` bis `0xC4000000` (24 MB) | | niemand bekannt | **offen:** im RAM-Dump vom Gerät 6318 von 6321 Seiten (4 KiB) nicht null, also nicht geleert (Boot löscht nur `0xC0200000` bis `0xC08A2940`); ob die Firmware dort liest oder schreibt, ist nicht belegt |

- **Physischer RAM:** im RAM-Dump vom Gerät unterscheiden sich `0xC0200000` bis `0xC4000000` und dieselben Adressen 64 MiB höher nur in 31 von 15872 Seiten (4 KiB): Spiegelung bei 64 MiB, also hergeleitet 64 MiB physisch
  (am Gerät gemessen, aber zeitlich zusammengesetzter Dump). Der zweite Lader programmiert den DDR-Controller (Register `0xB0000008` = `(alt und 0xF0000000) oder 0x0813CA22`, `0xB0000010`, `0xB0000014`); der Wert ist nicht dekodiert.
- **Zustand im FF-Bereich startet mit `0xFFFFFFFF`.** Jedes RAM-Wort der Runtime braucht einen Startwert aus dem Start-Haken, und jeder Haken beginnt mit "armed == 1": im Prototyp hat ein nicht gesetzter Schalter
  (`MASK` = FF) alle Eingaben verschluckt, bis er explizit auf 0 gesetzt wurde. Das ist dieselbe Regel wie bei MFX 2 ("FF heißt aus").
- **Stack-Reserve (am Gerät gemessen):** Hochwassermarken im RAM-Dump vom Gerät, UiTask 864 von 9216 B (9 %), CentralService 768 von 18432, SeqTask 840 von 9216, VoiceTask 604 von 9216, CommandTask 3776 von 1 MiB, StartupTask 576 von 9128. Der Emulator nach Boot und Bedienung: UiTask 856 B. Die VM braucht am ARM-Stack rund 100 B (Frame von `vm_run` 36 B plus Haken 32 B plus Glue); ihren Operandenstapel hat sie im eigenen Feld.

### 3.2 Platz im Firmware-Abbild für Code

- Die Datei bleibt `0x200100` B groß; Code und Bytecode gehören in die FF-Läufe (3.1). Bytecode wächst um rund 1,6 B je Operation, die Runtime selbst um rund 1,5 KiB (VM 972 B, Glue, Rahmen-Haken, CS-Stub). Ein Plugin wie Snake belegt geschätzt unter 1 KiB.
- Die vorhandenen Patches setzen ihre Adressen fest (`CODE_AT`, `STATE`). Mit einer Runtime teilt der Patcher Plätze zu (Abschnitt "Später: Code als Quelltext, dem der Patcher einen Platz zuteilt" in [../patcher.md](../patcher.md)).

### 3.3 Dauerhafte Variablen (Flash)

Plugin-Variablen im RAM überstehen kein Ausschalten. Für einen "Korg Klicker"-Zähler reicht ein eigener 4-KiB-Datensatz im Muster von Startbild-Editor und MFX 2 (Kennung, Version, Länge, Daten, CRC-32 zuletzt).

- **Wann schreiben:** nicht bei jedem Ereignis (Flash nutzt sich ab, Löschen eines Sektors hält die Sperre `0xC0000D80(2)`). Ein Haken am Eintritt von `0xC004C1B4` (Globals speichern, CommandTask) läuft bei WRITE auf Global **und** beim Ausschalten
  (gemessen im Emulator: Sektor `0x7F1000` wird bei beidem geschrieben, die Firmware speichert danach ihre Globals, das Ausschalten kommt zu Ende bei 1179,6 ms ohne Assertion). Die Stromhaltung fällt erst nach dem Schreibaufruf, das Schreiben der Runtime verzögert den Abschaltvorgang.
  Nur schreiben, wenn sich eine als dauerhaft markierte Variable geändert hat.
- **Wohin (aus dem Flash-Dump, 612 von 3552 Sektoren ab `0x220000` leer):**

| Bereich | Größe | Risiko |
|---|---|---|
| `0x7F1000` bis `0x7FEFFF` | 56 KiB | niedrig, Empfehlung (`0x7F0000` hat der Startbild-Editor, `0x7FF000` ist die XY-Kalibrierung) |
| `0x7E0000` bis `0x7EEFFF` | 60 KiB | niedrig (`0x7E8000` hat MFX 2, `0x7EF000` die Panel-Kennung) |
| `0xE60000` bis `0xFFFFFF` | 1,6 MiB | mittel (Update-Weg `0x80`) |
| `0x221000` bis `0x22FFFF`, `0x231000` bis `0x23FFFF` | je 60 KiB | mittel (Update-Bereich `0x22` = `0x220000` bis `0x6B0000`) |
| `0x7BC000` bis `0x7DFFFF` | 136 KiB | mittel bis hoch (Update-Bereich `0x75`) |
| `0x628000` bis `0x62FFFF`, `0x631000` bis `0x63FFFF`, `0x661000` bis `0x6AFFFF` | 32 + 60 + 316 KiB | mittel bis hoch |

- **Nicht empfohlen:** der freie Rest des Globals-Sektors (`0x230100` bis `0x230FFF`, im Dump leer, die Firmware lässt ihn beim Speichern stehen, Marker bei `0x230200` überlebte WRITE im Emulator): koppelt Plugin und Globals, und der Update-Weg `0x22` kann den Sektor neu schreiben.
- **Offen:** Löschzeit und Lebensdauer am Gerät, ob das Update von Korg `0x7E` oder `0x7F` anfasst (Länge der Update-Dateien).
- **Alternative ohne Flash:** Variablen auf der SD-Karte über die Datei-Funktionen der Firmware; größerer Aufwand, nicht untersucht.

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
| Regler-Werte | Panel-Wert 0..1023; die Firmware speichert `wert >> 1` als u16 ab `+0xF4` im Objekt `*(*0xC0691240 + 8)` (Heap-Adresse); gemessen für Regler 0, 3, 5 bis 10; Regler 1, 2, 4 anders abgebildet | | | Rohwert zuverlässig aus dem Ereignis (CS-Ring, siehe 1.3) |
| Nicht vorhanden | Buzzer, 7-Segment-Anzeige: keine Strings, kein Host-Befehl | | | |

### 4.2 Den Bildschirm besitzen

- **Die Firmware flusht selbst (gemessen):** alle 40 ms sendet die Periodic-Task (Task 2, Prio 1) den Frame (`0xC0015DD0(DISP, 3, ..)`, vergleicht jede Seite mit der zuletzt gesendeten Kopie); 2 ms später zeichnet die UiTask die Widgets in den Puffer (`0xC006F178`)
  und ruft `0xC0015DD0(DISP, 2, 0)`. Was im Tick im Puffer steht, ist nach 38 bis 40 ms im Display.
- **Haken (gemessen):** die Anweisung `ldr r0, [pc, #0xc]` bei `0xC00836FC` (direkt nach dem Aufruf von `0xC006F178`) wird zu `bl stub`; der Stub setzt `r0 = 0xC031BB2C` und kehrt zurück. Ein hineingeschriebenes Muster hielt in 12 von 12 Proben über 0,6 s,
  ohne dass der Stub flusht; Menü, Drehgeber, Play und WRITE änderten nichts daran; alle anderen Seiten waren gleich Stock; 470 Befehle je Takt für 128 Byte Füllung. Ein zweiter Stub von 344 B mit Text `SCRIPT TICK`: 60 von 60 Takten, keine Assertion.
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

### 5.2 Ein neuer Top-Level-Eintrag (gemessen, Prototyp lief)

Für einen Eintrag "Script" zwischen Global und Data Util (Bildschirm 0x2D) sind nötig:

1. Die 45 Tabellenwörter in den FF-Bereich kopieren, Wort 46 = eigene Fabrik, Literal `0xC006E68C` auf die neue Tabelle.
2. Grenze `cmp r0,#0x2c` bei `0xC006E664` auf `#0x2d`.
3. Nachbarn: Global Edit-rechts (`0xC0064D84`, `mov r0,#0xe`) und Data Util Edit-links (`0xC0061880`, `mov r0,#8`) springen auf einen Stub, der 0x2D wählt, wenn Seiten angelegt sind, sonst das alte Ziel. **Ohne Plugin-Seiten (N = 0) verhält sich die Firmware wie Stock** (gemessen: Edit-rechts von Global geht auf 14, Zähler 28/29).
4. Eigene Klasse: vtable-Kopie von `0xC00E3440` (18 Wörter) mit eigenen Slots 3, 4, 5, 6, 10, eigener Konstruktor nach dem Muster von Bildschirm 9 (Kopf-Widget `0xC0085464`, Seiten-Widget `0xC00856C0`, Reiter `0xC0085218`, Seitenzähler `0xC008A83C`), Objekt 0x34 Byte.

Empfohlen: Seitenzähler "n/29" nachführen (zehn Immediates oder Haken auf `0xC008A83C`/`0xC008A8A8`: wenn r2 = 29 dann r2 += N, wenn r1 >= 27 dann r1 += N; Ring danach lückenlos 1 bis 29 + N, gemessen), MENU auf dem Hauptbildschirm (Sprung bei `0xC006E8D8`, damit 0x2D als Top-Level zählt;
gemessen: EXIT, MENU kehrt zurück), WRITE (Erstbefehl-Haken auf `0xC006F094`: ohne ihn öffnet WRITE auf dem neuen Bildschirm das Pattern-Schreiben-Fenster 0x12).

### 5.3 Plugin-Seiten: Global-Seiten gegen eigener Bildschirm

- **Global-Technik (Startbild-Editor):** 20 Seiten fest an fünf Stellen (`0xC0064980`, `0xC006498C`, `0xC0064BF0`, `0xC0064BF8`, `0xC0064D04`), drei 20-Einträge-Tabellen am Parameter-Objekt (Index 20 liest hinter die Tabelle), die vtable hängt an **einem** Literal `0xC0064D3C`, das der Startbild-Editor schon belegt;
  zwei Patches können es nicht gemeinsam ersetzen.
- **Empfehlung: der eigene Bildschirm 0x2D.** Eigene vtable, keine 20er-Tabellen, kein geteiltes Literal, kein Konflikt mit dem Startbild-Editor.
- **Seiten als Daten:** je Seite ein 32-Byte-Deskriptor (Titel, min, max, Wert, Enum-Namen, Flags, Callback). Die Runtime zeichnet sie mit drei Firmware-Textfunktionen am Seiten-Widget (Objekt aus `0xC00856C0`, 0xCC Byte): Titel `0xC00857E4(w, char*)`, Wertzeile `0xC0085828(w, char*)`,
  dritte Zeile `0xC0085888(w, char*)` (rund 20 Zeichen, geeignet für Fehlertext). Das Dirty-Byte stößt das Zeichnen im nächsten Tick an.
- **Eingaben (gemessen):** VALUE kommt in vtable-Slot 10 (this, delta ±1), Edit links/rechts in 4/5, MENU in 6, EXIT in 2, rohe Tasten in 3. WRITE kommt zuerst als Slot 3 (this, 0x0E, 1), danach in `0xC006F094`.
- **Grenzen (gemessen):** höchstens 70 Seiten (der Zähler ist zweistellig, ab Summe 100 zeigt er "06/10"); Titel rund 13 breite oder 19 gemischte Zeichen, Wert rund 11 breite; jeder String höchstens 31 Zeichen, weil der Kopierer `0xC000AA64` ungebunden ist und der Puffer 32 Byte hat (die Runtime muss kürzen).
  Der ganze Prototyp (Fabrik, Konstruktor, Zeichnen, Dezimalausgabe, fünf Slots, sechs Haken) ist 1144 Byte.
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

## 6. Risiken

1. **Code im FF-Bereich war zur Zeit der Recherche am Gerät nicht bestätigt.** Der Block ist im Gerät-RAM-Dump vollständig `0xFF` (also DDR, beschreibbar ohne MMU), aber alle Code-Patches galten als am Gerät nicht geprüft. Der erste Gerätetest sollte der kleinste Haken sein: Eingangsfilter mit Maske 0 plus eine RAM-Variable, mit EXIT-Notschalter und Rückweg wie in [../messungen/2026-10-10-rueckweg-geuebt.md](../messungen/2026-10-10-rueckweg-geuebt.md). Der erste Code-Patch (MFX 2) am Gerät: [../messungen/2026-10-13-mfx-umschalter-geraet.md](../messungen/2026-10-13-mfx-umschalter-geraet.md).
2. **Der Eingangsfilter läuft in der CsTask (Prio 3) ab dem ersten Byte.** Ein Fehler dort stört die Bedienung, noch bevor die UiTask etwas tut. Er muss zuerst "armed == 1" und die EXIT-Maske prüfen (der Prototyp prüft EXIT dort noch nicht, nur der Rahmen-Haken tut es), und der Panel-Austausch beim Start darf nicht berührt werden (der Stub lässt Typen über 5 durch).
3. **VM-Geschwindigkeit am Gerät.** Ohne MMU ist der D-Cache praktisch aus; jede Operation macht 4 bis 6 Zugriffe auf DDR. Geschätzt 0,5 bis 1 µs je Operation. Kraftstoff nach Zeit (24-MHz-Zähler), nicht nach Operationen.
4. **Handler stehen vor der VoiceTask.** Länger als rund 5 ms in der UiTask kostet 2-kHz-Durchläufe der VoiceTask, Handler in der SeqTask verschieben Schritte. Plugins laufen deshalb nur in der UiTask, Ereignisse aus Cs- und SeqTask gehen über den Ring.
5. **Firmware-Bindung.** Alle Adressen gelten für 2.02 mit Hacktribe. Die API-Tabelle (ID zu Adresse) isoliert Plugins davon, die Haken der Runtime nicht.
6. **Gemeinsame Stellen.** Start-Haken `0xC002ADAC` und Global-vtable-Literal `0xC0064D3C` gehören dem Startbild-Editor. Der Patch-Prüfer lehnt zwei Änderungen an derselben Stelle ab; die Runtime muss Besitzer dieser Stellen werden und Startbild-Editor und MFX 2 als Handler aufnehmen oder ihre Haken umlegen.
7. **FF-Zustand.** RAM im FF-Bereich liest sich `0xFFFFFFFF` (im Prototyp hat ein ungesetzter Schalter alle Eingaben verschluckt): jeder Haken prüft "armed", der Start-Haken setzt alles.
8. **Flash.** Löschzeit, Lebensdauer, Verhalten bei Stromverlust und ob das Update von Korg `0x7E` oder `0x7F` anfasst sind am Gerät offen. Nur bei Änderung und nur in WRITE und Ausschalten schreiben.
9. **LED-Neuschreiben der Firmware** (Pad-Rot im SEQUENCER bei Play, TAP, RGB jeden Takt) überschreibt Plugin-Werte. Wer sie halten will, setzt die Sperre `LM+0xB98` und stellt sie danach wieder her.
10. **Fehleranzeige.** Die Runtime muss den Fehler selbst zeigen (dritte Zeile der Plugin-Seite oder Text im Rahmen-Haken); die Firmware zeigt bei Abbrüchen nichts (Endlosschleife) und bei einer Assertion "System Error" ohne Rückweg.
11. **Native Fehlerfänger sind ein Modell.** Was die echte Hardware ohne MMU abbricht, ist unbelegt (der Ausnahmeeintritt wurde im Emulator selbst nachgebaut).

## 7. Offene Fragen

- Läuft ein Haken am Gerät (Eingangsfilter, Rahmen-Haken)? Wie schnell ist die VM am Gerät (Operationen je Sekunde bei ausgeschaltetem D-Cache)?
- Flash-Löschzeit und Lebensdauer; gibt es einen Watchdog im Gerät außerhalb der Firmware (der zweite Lader berührt ihn nicht, `WDTCR` nie geschrieben)?
- Genaue Panel-Helligkeitsstufen, Wirkung der Panel-Nachricht `02 flag` und der Befehle `83`/`84`; Regler 1, 2, 4 (PAN, OSC PITCH, EG INT) werden anders abgebildet.
- Chain To / Chain Repeat: die Stelle, die beim Loop-Ende die Kette ausführt, ist nicht gefunden; Shift-gehalten und Pad-Haltezustand haben keine RAM-Stelle.
- Weitere Quellen für Note an (Keyboard, Chord, Gate Arp, Touchpad); MIDI-Start/Stop im Emulator ohne Wirkung.
- Auto Power Off: 4 Stunden folgen aus 2,0 ms im Emulator; die drei weiteren Absender der Ausschaltmeldung `0x18` und drei weitere Aufrufer von `0xC004C1B4` wurden nicht ausgelöst.
- Ob `0xC274F000` bis `0xC4000000` (24 MB, im Gerät-Dump nicht leer) von der Firmware gelesen oder beschrieben wird; DDR-Register `0xB0000008` (Wert `0x0813CA22`) nicht dekodiert.
- Wie mehrere Plugins sich Seiten und Haken-Listen teilen (Reihenfolge, Gruppen); Ring mit Zusammenfassen oder 64 Einträgen; Eingangsfilter mit Maske je Taste statt je Typ.
- Eine nach Bildschirmnummer indizierte Tabelle in einem nicht ausgelösten Pfad könnte den neuen Bildschirm 0x2D übergehen.
- Option MMU-Sandbox (nativer Code mit eigener Seitentabelle, die Firmware hat die Hilfsfunktion `0xC00016EC`, ruft sie aber nie): nicht untersucht, weil die VM das Problem ohne Hardware-Eingriff löst.
