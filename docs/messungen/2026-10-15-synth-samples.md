# Samples auf der blauen Electribe 2: PCM-Wellen und Oszillator-Tabelle

Im [Emulator](../glossary.md#emulator) und offline, kein Gerät. Eingabe: die [`SYSTEM.VSB`](../glossary.md#vsb) 2.02 der blauen Electribe 2
(Synth), zum Vergleich Korgs Sampler-Original 2.02, und der PCM-Bereich der eigenen Flash-Sicherung des Samplers (nur als
Eingabe für Messungen, die Firmware der blauen nimmt ihn an). Alles andere sind selbstgebaute Sinuswellen. Es liegt nichts davon
im Repository, nur Ergebnisse, Adressen und Aufbau. Markierungen: **gemessen** (ausgeführt, Befehl genannt),
**offline** (Code oder Bytes gelesen), **hergeleitet**, **geschätzt**, **offen**. Die Messungen laufen mit
`tools/emu/synth_probe.py` und sind in `tools/emu/test_synth_probe.py` festgehalten, siehe unten.

Frage: Wie bringt [BLECH](../glossary.md#blech) auf der Synth-Firmware eine WAV von der Karte als Oszillator zum Klingen, möglichst ohne
den Flash zu beschreiben? Die Synth-Firmware hat keinen Sample-Pfad wie der Sampler, aber das reicht: eine Tabelle von
PCM-Wellen im RAM, die sie beim Start selbst aufbaut, und eine Oszillator-Tabelle, die darauf zeigt. Umgesetzt ist das im
[Patch](../glossary.md#patch) `user-samples-synth` ([Eigene Samples auf der blauen](2026-11-12-blau-sample-import.md)).

## Kurzfassung

1. **PCM-Wellen.** Die Bank liegt im Flash bei `0x800000` (8 MiB, komprimiert in 12-Bit-Blöcken). Beim Start liest die
   Firmware sie in zehn Stücken in ihren Arbeitspuffer (`0xC0B6BD00`), entpackt sie auf dem ARM und schreibt sie als
   16-Bit-Wörter über den [Host-Port](../glossary.md#host-port) in den [DSP](../glossary.md#dsp)-Speicher ab Byteadresse `0x365AE0`, einmal, nur beim Start. Danach sieht
   der ARM den DSP-Speicher nie wieder an, der DSP spielt die Wellen von dort. Es ist derselbe Weg, den der Sampler für
   die Nutzersamples nimmt (Arbeitspuffer, Host-Port), mit eigenen Adressen.
2. **Oszillator-Tabelle.** 409 Einträge zu 32 Byte im Abbild, mit Name, Gruppe und Wellen-Nummer. Wellen-Nummern ab
   `0x32` sind PCM-Instrumente (Nummer minus `0x32` ist der Instrumentindex), darunter sind es Wellen, die der DSP selbst
   erzeugt. Jede PCM-Welle ist in RAM-Tabellen beschrieben (Instrument, Zone, Lage, Sample mit Start, Schleife, Ende), die
   bis 512 Instrumente und 1536 Samples fassen. Einträge lassen sich ohne Eingriff in den Code ersetzen und, mit
   Anhängen eines Instruments, auch neu anlegen. **Die Liste selbst zu verlängern** wäre ein größerer Eingriff (13
   Vergleiche mit der Grenze 408, zehn Zugriffe auf die Tabelle, drei Arrays je Part).
3. **Was der DSP braucht.** 16-Bit-Wörter, mono, ab einer 32-Byte-Grenze, dazu je Stimme vier Parameter über den
   Host-Port: Startadresse, Schleifenanfang, Schleifenlänge und ein Tonhöhenwort. Im Emulator sendet die Firmware für
   eine Welle, die wir an eine freie Adresse legen, **dieselben Parameter bis auf die Startadresse** (und den
   Stimmenplatz). Ob der echte DSP von dort spielt, lässt der Emulator offen (der DSP ist eine Attrappe).
4. **Platz.** ARM: 911 KB freier Block im Abbild (in keinem Lauf beschrieben), der 12-MiB-Arbeitspuffer der Firmware für
   Dateien. DSP: ab dem Ende der Werksdaten, bei der Sampler-Bank `0x133F5C0`. Wo der DSP-Speicher aufhört und was der
   DSP dort selbst nutzt, ist **offen**. Die Kartenfunktionen (FatFs: `f_open`, `f_read`, `f_write`, `f_close`,
   `f_lseek`, `f_opendir`, `f_readdir`, `f_closedir`) sind im Synth da und laufen im Emulator am Ende der PCM-Ladung,
   auch Lesen, Schreiben und Ordner auflisten.
5. **PCM Update.** `PCM.VSB` ist ein VSB mit Kopf (`0x100` Byte, Typ `PCM` bei `+0x20`, Nutzlänge `0x800000` bei `+0x3C`)
   und dem 8-MiB-Bild des Flash-Bereichs. Die Firmware schreibt es unverändert in den Flash. Aufbau der Bank, Prüfsumme
   und Block-Kodierung sind unten; eine selbstgebaute Bank aus Rohblöcken nimmt die Firmware im Emulator an und streamt
   sie bitgenau in den DSP.
6. **WAV.** Der Synth hat einen WAV-**Schreiber** (48 kHz, 16 Bit, Stereo, 44-Byte-Kopf) und **keinen Leser**; Öffnen, Lesen,
   Schreiben und Schließen der Datei geht mit den Funktionen der Firmware.

**Urteil: machbar ohne Flash-Schreiben**, mit zwei Dingen, die nur am Gerät zu klären sind (spielt der DSP von einer
Adresse hinter den Werksdaten, und die Tonhöhen-Konstante).

## Belegtabelle

### 1. Wo die PCM-Wellen liegen und wie sie in den DSP kommen

| Behauptung | Status | Beleg |
|---|---|---|
| Die Bank liegt im Flash bei `0x800000` bis `0xFFFFFF` (8 MiB). Beim Start liest die Firmware den ganzen Bereich in zehn Stücken (je `0xCCCCD` Byte, das letzte `0xCCCCB`) nach `0xC0B6BD00`, bei 93 bis 96 ms Gerätezeit | gemessen | `synth_probe.py boot VSB --bank ...`, Liste `flash_reads`; `0xC0B6BD00` gibt `0xC0032A04` zurück |
| Das ist der allgemeine Arbeitspuffer der Firmware: `0xC0B6BD00` mit `0xC00100` Byte (12 MiB und 256), jeder Benutzer holt ihn mit `0xC0032A04` und gibt ihn mit `0xC0032A1C` zurück (das ist ein Rücksprung ohne Wirkung) | offline | Konstanten bei `0xC0032A14` und `0xC0032A18`, 16 Aufrufer in Dateiroutinen |
| Der Lader ist `0xC0046E54`, aufgerufen von `0xC0028080` im Start (übersprungen, wenn `[Objekt + 0x22]` gesetzt ist). Er prüft die Summe, die Kennung und die Abschnitte, kopiert Tabellen in RAM, entpackt mit `0xC0046BD0` und schreibt über `0xC00108C4` (Fenster setzen), `0xC0010978` (ein Wort) und `0xC001061C` (Übertragung beginnen) | offline | Code gelesen; im Emulator laufen genau diese Stellen (Rückkehradressen im Aufrufbaum der Host-Port-Zugriffe) |
| Nach dem Entpacken gehen die Daten in 127 Übertragungen zu je 65520 Wörtern über den Host-Port (Steuerwörter `0xAB`, Adresse, Anzahl, Breite 2, 0, 0) in den DSP-Speicher, von `0x365AE0` bis `0x133F5C0` (16.620.256 Byte), zwischen 284,8 und 5697,7 ms | gemessen | `boot --bank ...`, `dsp_memory_writes`; zusammenhängend, eine Strecke |
| Danach gibt es bis 14,5 s Gerätezeit keinen Zugriff mehr auf den DSP-Speicher unterhalb `0xFF000000`, weder Schreiben noch Lesen, auch nicht beim Drehen am OSC-Geber und beim Drücken der Pads. Die Stimmennachrichten gehen an die Postfächer ab `0xFF900000` | gemessen | Lauf mit 60 Drehgeberschritten und Pads, alle 10881 Übertragungen ausgewertet |
| Der DSP liest die Wellen zur Laufzeit also selbst aus seinem Speicher; der ARM schickt nur Adressen | hergeleitet | aus der vorigen Zeile und aus den Parametern unten |
| Die Bank beginnt mit `KORG` und `elec2PCM` (die Firmware nimmt auch `X11100PC` an), Version `01 01`, danach ein 16-Bit-Wort, das die Summe aller 16-Bit-Wörter der 8 MiB auf 0 bringt (Offset `0x0E`). Die Summe ist 0, die Firmware prüft das beim Start (`0xC0046F04` bis `0xC0046F4C`) | gemessen und offline | `synth_probe.py bank FLASH`: `sum16 0`, die Summe ohne das Korrekturwort ist sein Zweierkomplement; ob die Firmware eine Bank mit falscher Summe wirklich ablehnt, ist im Emulator **offen** |
| Sieben Abschnitte, ihre Offsets stehen ab `+0x10` im Kopf: `DRMP` (`+0x10`), `DRUM` (`+0x14`), `MSPR` (`+0x18`), `MSRL` (`+0x1C`), `SMPR` (`+0x20`), `SMPL` (`+0x24`), `MSVS` (`+0x28`). Jeder Abschnitt hat einen Kopf von `0x20` Byte: Kennung, Größe mit Kopf (bei `DRUM` und `SMPL` `0xFFFFFFFF`), Anzahl (bei `DRUM` und `SMPL` die Zahl der Werte), ein Prüfwort | gemessen | `synth_probe.py bank` über die eigene Bank; die Lader-Kopien und ihre Grenzen (`DRMP` bis `0x200` Einträge, `MSPR` und `MSVS` bis `0x200`, `MSRL` und `SMPR` bis `0x600`) stehen im Code |
| `SMPL` und `DRUM` sind Ströme aus Blöcken: ein 16-Bit-Wort (oben 3 Bit Modus, unten 13 Bit Anzahl), bei den Modi 0 bis 4 danach die Länge des kodierten Teils, bei Modus 7 (roh) die Werte als 12-Bit-Zahlen, höchstes Bit zuerst. Das Prüfwort im Kopf ist die Summe der 16-Bit-Wörter, die der DSP bekommt (Wert mal 16) | gemessen | Strom der eigenen Bank an den Kopfwörtern abgelaufen: 4058 Blöcke, 8.310.104 Werte, Modi 0 bis 4 und 7 in der Verteilung, die [2026-10-07-werks-sample-flash.md](2026-10-07-werks-sample-flash.md) hat; für Modus 7 und die Summe: die selbstgebaute Bank wird angenommen |
| Die ersten 16 Werte (`DRUM`) stehen bei `0x365AE0`, die erste Welle fängt bei `0x365B00` an. Die Startadresse eines Samples im RAM ist sein Strom-Offset aus `SMPR` plus `0x365B00` | gemessen | Tabelle `smpr` im RAM gegen die Datei; selbstgebaute Bank: Start der Welle 1 ist `0x365B00` plus ihr Offset |
| Eine selbstgebaute Bank aus vier Sinuswellen (nur Rohblöcke) wird angenommen: Hauptbild bei 500 ms, vier Instrumente, und die Firmware schreibt **bitgenau** `Wert * 16` je Wort, 16-Wörter-Lead-in plus alle Wellen, aufgefüllt auf 32 Byte, ab `0x365AE0` | gemessen | `boot VSB --synthetic`: `equals_made_up_waves true`; Test `test_it_boots_and_streams_every_value_as_a_16_bit_word_from_the_dsp_base` |
| Ohne gültige Bank (leerer Flash) liest sie dieselben zehn Stücke, `r6` am Ende der Ladung ist 0, die Tabellen sind leer (Zähler 0), der Start geht trotzdem durch | gemessen | `boot VSB --seconds 3` auf leerem Flash |
| Mit der eigenen Bank (411 Instrumente) dauert der Start bis zum Hauptbild 5,9 s Gerätezeit, die Ladung endet bei 5,74 s; mit der selbstgebauten Bank 0,5 s | gemessen | `boot`, `booted_ms` und `at_the_end_of_the_pcm_load.ms` |

### 2. Die Oszillator-Tabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Die Tabelle liegt im Abbild ab `0xC00BEB48` (Name des ersten Eintrags), 409 Einträge zu `0x20` Byte, danach beginnt die Modulationstabelle. SAW ist Eintrag 325, `Audio In` der letzte (408) | gemessen und offline | `synth_probe.py osc VSB`; Grenze 408 (`0x198`) in 13 Vergleichen |
| Aufbau eines Eintrags (ab dem Namen): Name 16 Byte (ASCII, Nullbyte am Ende), Gruppe 1 Byte (`+0x10`), Wellen-Nummer 16 Bit (`+0x12`), Bereich der Regler A und B als zwei vorzeichenbehaftete Bytes (`+0x16`, `+0x17`), Vorgabe und Schalter für A (`+0x18`, `+0x19`) und für B (`+0x1C`, `+0x1D`) | offline | die Zugriffe in `0xC0086C50` (Eintrag in den Part übernehmen), `0xC0086BD0` (Wellen-Nummer) und `0xC003B93C` (Gruppe) |
| 14 Gruppen (0 bis 13) in einem Stück hintereinander, die Wellen-Nummern gehen von 1 bis 411, 398 verschiedene. 48 Einträge zeigen auf Wellen des DSP (Nummer unter `0x32`), 361 auf PCM-Instrumente | gemessen | `synth_probe.py osc` |
| Auf dem Bildschirm steht der Name aus dem RAM: Schreibt man in den Eintrag, zeigt die Seite OSC TYPE `[Gruppenname] Laufnummer Name` und der Hauptbildschirm `OSC: Name`. Die Laufnummer zählt über alle Einträge (1 bis 409) | gemessen | Bild der Anzeige nach dem Umschreiben von Eintrag 1 und 334 (`synth_probe.py demo`); `[Kick]` ist die Gruppe 0, `[Synth]` die Gruppe 11 |
| Ein Schritt am SAMPLE/OSC-Geber ändert den Eintrag um 1 (von SAW, 325, nach 385 in 60 Schritten) | gemessen | Lauf mit 60 Meldungen, Stimmen-Aufruf zeigt Eintrag 385 |
| Die Firmware übernimmt den Eintrag erst, wenn eine Stimme beginnt (`0xC0086C50` setzt Eintrag und Wellen-Nummer in das Timbre, `0xC0086E1C` schickt die Welle an den DSP) | gemessen | Haken auf beide Funktionen, Aufruf beim Pad-Druck |
| Wellen-Nummer zu Sample: Instrument = Nummer minus `0x32`; die Firmware nimmt `MSVS[Instrument]` (bis zu vier Tastenzonen, hier eine), daraus eine `MSPR`-Nummer, daraus die erste Lage in `MSRL` (Anschlagstärke-Grenze, Sample-Nummer, Tonhöhenwort), daraus den `SMPR`-Eintrag (Start, Schleife, Ende, Schalter). Das macht `0xC0086B18`; Taste und Anschlagstärke für die Auswahl kommen aus zwei Feldern des Timbres (`+0x17`, `+0x18`, hergeleitet: die Werte der Regler A und B) | gemessen | Kette im RAM gelesen (`Probe.chain`), Ergebnis gegen die Stimmennachricht |
| Eine Nummer größer als `Anzahl + 0x31` ist keine PCM-Welle mehr (`0xC0086C18`); die Anzahl ist die Zahl der `MSVS`-Einträge, steht bei `0xC0353E68` und hat nur diese Leser: die Prüfung, der Lader und die beiden Stimmenfunktionen | offline | alle Zugriffe auf die Zählvariablen und Tabellen gesucht (`literal_users`): außer dem Lader nur `0xC0086B18`, `0xC0086E1C`, `0xC0086F20` und der Getter `0xC0046B8C` |
| Die RAM-Tabellen sind feste Arrays: `MSVS` bei `0xC034DE68` (32 Byte je Instrument, Platz für 512), `MSPR` `0xC0351E68` (16 Byte, 512), `MSRL` `0xC0348664` (8 Byte, 1536), `SMPR` `0xC0353E74` (16 Byte, 1536), Zähler bei `0xC0353E68`, `0xC0353E6C`, `0xC0359E74` und `0xC034DE64` | gemessen | Inhalt nach dem Start gelesen; die Abstände der Arrays entsprechen den Grenzen des Laders |
| Ein **angehängtes Instrument** (Tabellen beschrieben, vier Zähler um eins erhöht, Eintrag auf die neue Nummer gebogen) wird gespielt: Nummer 54 in der Stimmennachricht, Start, Schleife und Tonhöhe sind die geschriebenen | gemessen | `synth_probe.py demo`, `test_an_appended_instrument_plays_from_the_address_it_was_written_to` |
| **Wellen-Eintrag ersetzen** (nur Start, Schleife, Ende, Tonhöhenwort und Name ändern) geht ebenso | gemessen | `synth_probe.py demo --replace 1` |
| 11 Einträge zeigen auf dieselbe DSP-Welle wie ein anderer Eintrag und unterscheiden sich nur in den Vorgaben für A und B: `OCT-SAW`, `OCT-SQU`, `OCT-TRI`, `OCT-SINE` (334 bis 337), `X-SAW 2`, `X-SQUARE 2`, `X-TRI 2`, `X-SINE 2` (355, 357, 359, 361), `VPM-SINE 2` bis `4` (366 bis 368). Sie lassen sich umwidmen, ohne dass ein Klang verloren geht (die Vorgaben bleiben über A und B erreichbar, das ist **hergeleitet**) | gemessen und hergeleitet | `synth_probe.py osc`, Gruppen mit gleicher Wellen-Nummer |
| Die Liste **verlängern** braucht: die 13 Vergleiche mit `0x198` ändern (`0xC003B93C`, `0xC003BB48`, `0xC0086BEC`, `0xC0086C68`, `0xC0086D24`, `0xC0087034`, `0xC0087218`, `0xC00872AC`, `0xC00872E0`, `0xC0087318`, `0xC008735C`, `0xC00873A4`, `0xC00873F0`), die zehn Zugriffe auf die Tabelle umlenken (`0xC003B8FC`, `0xC003B958`, `0xC003B9F0`, `0xC006B498`, `0xC0070DF0`, `0xC0086BF0`, `0xC0086C70`, `0xC0086D2C`, `0xC008703C`, `0xC008716C`), die Tabelle ins freie Stück legen und die Arrays je Part (16 mal 409 mal 3 Byte, Stride `0x4CB`) vergrößern. Nicht gebaut, nicht nötig für die ersten Samples | offline | `synth_probe.py osc`: `compare_with_bound`, `users_of_table` |
| Wie ein Pattern den Oszillator speichert (Index, vermutlich 16 Bit im Part), ist nicht gemessen; der Index im RAM der Part-Werte ändert sich bei jedem Geberschritt | offen | RAM-Vergleich vor und nach einem Schritt: der Wert steht in den Part-Werten, nicht in den Pattern-Plätzen |

### 3. Was der DSP für eine PCM-Welle braucht

| Behauptung | Status | Beleg |
|---|---|---|
| Bitbreite und Rate: **16-Bit-Wörter, mono**. Die Werksdaten sind 12-Bit-Werte mal 16, der DSP bekommt 16-Bit-Wörter. Eine Rate gibt es nicht in der Welle: Tonhöhe und Rate stecken im Tonhöhenwort | gemessen | Wörter wie `0x7FF0`, `0xFFE0` im Strom; selbstgebaute Bank bitgleich |
| Der ARM schickt je Stimme vier Parameter, jeder ein 32-Bit-Wert an einen Parameterindex: Start (roh, eine Byteadresse), Schleifenanfang mal 4096, Schleifenlänge mal 4096, Tonhöhenwort mal 65536. Index = `0x4300 + 0x1A * Stimme + {0xB4, 0xAF, 0xB0, 0xBE}` | gemessen | Haken auf `0xC00816C0` (Welle an den DSP: Stimme, Nummer, Start, Schleifenanfang, auf dem Stack Schleifenlänge und Tonhöhenwort) und `0xC000E924` (ein Parameter) |
| Ein Parameter geht als Nachricht an das Postfach `0xFF900A34`: ein 16-Wörter-Block `0x0106`, `1`, `0`, Index, Wert oben, Wert unten, danach Füllwörter | gemessen | Übertragung nach dem Parameter `0x43B4` ausgelesen |
| Schleife: **Anfang und Ende sind Byteabstände vom Start der Welle** (die Werksdaten haben bei einer Welle ohne Schleife Anfang gleich Ende; die Länge ist Ende plus 2). Der DSP bekommt Anfang und Länge (Ende minus Anfang); Länge 0 heißt eine Wiedergabe ohne Schleife. Bit 16 im Schalterwort eines `SMPR`-Eintrags ist bei den Werksdaten genau dann gesetzt, wenn Anfang gleich Ende | gemessen | selbstgebaute Welle mit Anfang gleich Ende und mit Schleife 200 bis 598 (`0xC8000`, `0x18E000`), Test `test_a_loop_is_sent_as_its_start_and_its_length_and_a_moved_wave_changes_only_the_start`; an der eigenen Bank Schleife 1000 bis 5000 (`0x3E8000`, `0xFA0000`); eigene Bank: 342 ohne Schleife, 69 mit |
| Die Lage (`MSRL`, 8 Byte) hat bei den Werksdaten: größte Anschlagstärke (127), 0, die Sample-Nummer (16 Bit), das Tonhöhenwort (16 Bit), ein Wort (meist `0xFFFF`). Der Zonen-Eintrag (`MSVS`, `+0x18`) hat ein Wort, das die Firmware doppelt nimmt und als Pegel mit der Stimme malnimmt (`0x8000` ist 1,0, nach oben begrenzt) | offline | `0xC0086B18`, `0xC0086E1C` (Pegel in `+0x32`), `0xC0086FC4` |
| **Tonhöhenwort**: 16 Bit, Einheit ein Zweihundertsechsundfünfzigstel Halbton. Die Firmware **addiert beim Laden 375** zum Wort jeder Lage (0x4800 in der Datei wird `0x4977` im RAM; 375 ist 1,4648 Halbtöne, der Abstand von 44,1 zu 48 kHz). Das Wort im RAM ist die Taste, bei der die Welle mit einem Wert je Ausgangswert spielt: bei den Werksdaten mit einer Schleife von einem Zyklus (neun Wellen) ist Wort geteilt durch 256 gleich der MIDI-Note der Schleife bei 48 kHz auf rund 0,15 Halbton | gemessen | Lage nach dem Laden mit der Datei verglichen; Schleifenlänge in Wert 48000 durch Länge in Note umgerechnet: Unterschied Wort minus Note zwischen minus 1,33 und minus 1,47 in der Datei, zwischen 0 und plus 0,13 im RAM |
| Daraus für eine Welle mit Rate R und Wurzeltaste K: Wort = `256 * (K + 12 * log2(48000 / R))`, dieselbe Zahl, die der DSP sieht (`pitch_word` in `synth_probe.py`) | hergeleitet | aus der Zeile davor; **offen**, ob der DSP die Taste wirklich so einsetzt und ob die Tastenzählung der Firmware der MIDI-Zählung entspricht (ein Messton am Gerät klärt es) |
| Stimmenplatz: die Stimmen gehen reihum (Stimme 0, 1, 2, ...), der Parameterindex springt um `0x1A` je Stimme | gemessen | drei Pad-Drücke nacheinander |
| **Eine Welle an anderer Adresse**: Lage-Start auf eine freie Adresse nach den Werksdaten gesetzt, die Stimme sendet dieselben vier Parameter, nur der Start (und der Stimmenplatz) ändert sich | gemessen | `boot --voice 1 --relocate` mit selbstgebauter Bank und mit der eigenen Bank (Start `0xB6AD92` wird `0x133F5C0`, `voice_params_changed` enthält nur `start`) |
| Der Emulator zeigt nicht, ob der DSP von dort tatsächlich spielt: er hat keinen DSP-Speicher und keinen Klang | offen | `docs/emulator.md` |
| Schreiben in den DSP-Speicher: die Firmware hat einen fertigen Schreiber `0xC00105A4(Anschluss, DSP-Adresse, Quelle, Anzahl Wörter)` (rundet die Anzahl auf ein Vielfaches von 16 auf; `0xC00104F0` schreibt eine nicht durch 16 teilbare Anzahl als zwei Übertragungen), den Anschluss gibt `0xC0011554()`. Ein Aufruf am Ende der Ladung legt die Daten wie die der Firmware ab | gemessen | `synth_probe.py demo`: `dsp_has_the_wave true`; Test `test_the_end_of_the_pcm_load_is_a_place_where_the_card_and_the_dsp_functions_work` |
| Lesen aus dem DSP-Speicher (für EXPORT SAMPLE) geht mit dem Gegenstück `0xC0010148` (Befehl `0xA9`, gleiche sieben Steuerwörter), das im Emulator nicht aufgerufen wurde, weil der DSP-Speicher dort fehlt | offline | Code gelesen; das Gegenstück im Sampler ist belegt ([DSP-Audiopfade](2026-10-08-dsp-audiopfade.md)) |

### 4. Platz und Karte

| Behauptung | Status | Beleg |
|---|---|---|
| Freier Block im Abbild: `0xC01217F4` bis `0xC01FFFF0` (911.356 Byte; beim Sampler beginnt der freie Block bei `0xC013C0B0`). In einem Lauf mit Start, 60 Drehgeberschritten und Pad wurde **kein Wort** darin geschrieben (Schreib-Haken auf Block und 64-MiB-Spiegel) | gemessen | `0xC01217F4` bis `0xC01FFFF0` ist FF in der Datei; Haken `UC_HOOK_MEM_WRITE` über den Lauf |
| RAM hinter dem Abbild: benutzt bis `0xC1780000` (Stacks), darüber in den Läufen nichts. Der Arbeitspuffer `0xC0B6BD00` bis `0xC176BE00` (12 MiB) trägt nach dem Start noch die Kopie der Bank; keine Tabelle zeigt in ihn hinein | gemessen | Seitenkarte `ram_runs` nach dem Start und nach dem Spielen; die Tabellen stehen in eigenen Arrays |
| DSP-Speicher: die Firmware kennt keine Obergrenze (keine Konstante im Code, alle Pool-Wörter durchsucht). Frei ist, was hinter den Werksdaten liegt, wenn der DSP dort nichts Eigenes hält. Der Sampler hält seine Nutzersamples im Bereich `0x365EC0` bis `0x1C65EC0` (siehe [2026-10-14-sample-speicher-voll.md](2026-10-14-sample-speicher-voll.md)); der Anfang der Werksdaten des Synths (`0x365AE0`) liegt `0x3E0` darunter, ein Hinweis, dass die untere Reserve des DSP bei beiden Programmen gleich ist | offen, hergeleitet | `synth_probe.py boot`; Ende der Werksdaten der eigenen Bank: `0x133F5B0`, aufgerundet `0x133F5C0` |
| FatFs ist da, mit denselben Funktionen und Signaturen wie im Sampler: `f_open` `0xC008A6B8`, `f_read` `0xC008A8CC`, `f_write` `0xC008AB10`, `f_close` `0xC008AF34`, `f_lseek` `0xC008AF5C`, `f_opendir` `0xC008B1B8`, `f_closedir` `0xC008B280`, `f_readdir` `0xC008B298`. `f_unlink` wurde mit der Signatur des Samplers nicht gefunden | gemessen | Maskensuche der Signaturen aus dem Sampler im Synth-Abbild (`firmware.sign`, `firmware.search`) |
| Diese Funktionen laufen im Emulator **am Ende der PCM-Ladung** (Stelle `0xC00473D0`, `mov r0, r6`): Datei öffnen, 2044 Byte lesen und vergleichen, Ordner auflisten (`TEST.WAV`), mit `0x0A` anlegen, schreiben, schließen, auf der Karte wiedergefunden. Die Firmware fasst die Karte erst 4 ms später an | gemessen | `synth_probe.py fatfs VSB --synthetic` |
| Lesegeschwindigkeit im Emulator während des Starts (am Ende der PCM-Ladung und bis zum Ende der Init-Funktion): Blöcke bis 16 KiB rund 550 KiB/s, ein einzelnes `f_read` über 32 KiB (64 Sektoren) nur 37 KiB/s (je Aufruf 0,8 s). Ursache offen, das Kartenmodell kann es sein; der Lader liest in Blöcken von 16 KiB. Später im Betrieb (Bildschirm-Takt läuft) schafft der Emulator 500 KiB/s auch mit 32 KiB | gemessen | `f_read` in Blöcken von 512, 4096, 8192, 16384, 32768 Byte; Kartenmodell: [virtuelle SD](../hintergrund/virtuelle-sd.md) |
| Kartenordner der Firmware: `SD:KORG/electribe/` (und `SD:KORG/electribe sampler/`), darunter `System`, `PatternSet`, `Project`, `Audio`. Ein eigener Ordner ist unabhängig davon (BLECH ruft `f_open` mit eigenem Pfad) | offline | Zeichenketten um `0xC00904B0`; der Ordner `electribe` ist nur hergeleitet geprüft ([blaue Electribe](2026-10-15-blaue-electribe.md)) |
| EXIT beim Einschalten ist an der Stelle sichtbar, an der BLECHs Lader nachsieht: `[[Bedienfeld] + 0x18] & 0x2000` (`0xC033E8F8` ist das Bedienfeld des Synths) | gemessen | `boot --held 0x2000`, Wert am Ende der Ladung `0x2000` gegen `0x0` |

### 5. PCM Update und `PCM.VSB`

| Behauptung | Status | Beleg |
|---|---|---|
| Der Lader der Datei ist `0xC0034538`: Pfad aus `SD:` und `/PCM.VSB`, öffnen, die ersten `0x100` Byte lesen, bei `+0x20` die Kennung `PCM` (3 Zeichen) prüfen, bei `+0x3C` die Nutzlänge (32 Bit) prüfen, sie muss genau `0x800000` sein, und in den Arbeitspuffer passen | offline | Code gelesen: `0xC0034644` bis `0xC0034674` |
| Danach liest er die Nutzlänge in den Arbeitspuffer und schreibt sie mit `0xC0027000(Flash, 0x80, Länge, Puffer)` in den Flash, ohne die Bank selbst zu prüfen. Die Prüfung macht der nächste Start (Summe, Kennung, Abschnitte); fällt sie durch, bleibt die Ladung ohne Klang (`r6` ist 0) und der Start geht trotzdem durch (gemessen mit leerem Flash) | offline und gemessen | Code gelesen; Lauf mit leerem Flash |
| Eine `PCM.VSB` ist also `0x800100` Byte: der Kopf eines VSB (Magic `KORG SYSTEM FILE`, Typ `E2`, Name `PCM`, Länge `0x800000` bei `+0x3C`) und die Bank | offline, hergeleitet (Name und Länge aus der Prüfung, der Rest aus dem Kopf der `SYSTEM.VSB`) | Kopf der `SYSTEM.VSB` gelesen, Prüfung der Firmware |
| Eine eigene Bank braucht: den Kopf mit den sieben Offsets, `DRMP` (ein Eintrag, 20 Byte), `DRUM` (16 Werte), `MSPR`, `MSRL`, `SMPR`, `SMPL`, `MSVS` in gleicher Zahl, das Format-Wort 1 im Kopf von `MSVS` (die Einträge werden dann unverändert kopiert), die Summe 0 mit dem Korrekturwort, die Prüfwörter der Ströme. Für Modi 0 bis 4 (die Werksdaten) braucht es den Kodierer, der öffentliche der Korg-Volca-Sample-Bibliothek passt ([Werks-Samplebank](2026-10-07-werks-sample-flash.md)). Mit Rohblöcken (Modus 7) genügt ein Packer, den hat `synth_probe.py` | gemessen | `build_bank` wird von der Firmware angenommen, bitgenau im DSP |
| Den echten `PCM.VSB` der blauen Electribe gibt es hier nicht; die Anzahl der Instrumente und die Größe der Werksdaten der blauen sind unbekannt (die Tabelle zeigt 361 PCM-Einträge, mit Nummern bis 411) | offen | Dateien liegen nicht vor |

### 6. WAV im Synth

| Behauptung | Status | Beleg |
|---|---|---|
| Es gibt einen WAV-Schreiber `0xC00328B8(Pfad, Daten, Anzahl Frames)`: Platz auf der Karte prüfen (Fehler 6), Kopf aufbauen (RIFF, `fmt ` mit PCM, 2 Kanäle, 48000 Hz, 192000 Byte/s, Ausrichtung 4, 16 Bit, `data`), Datei mit `0x0A` öffnen, Kopf und Daten schreiben, schließen. Es ist **immer 48 kHz, 16 Bit, Stereo** | offline | Code und Kopfvorlage bei `0xC00329EC` |
| Die Kennungen `RIFF`, `WAVE`, `fmt ` und `data` kommen im Synth nur in diesem Schreiber vor, es gibt keinen Leser, keinen `smpl`- und keinen `korg`-Abschnitt. Im Sampler sind die Kennungen in zwei Funktionen (Schreiber und Leser), dort steht auch `korg` | offline, hergeleitet | `refs` und `ldr`-Nutzer der Konstanten in beiden Abbildern |
| Wiederverwendbar sind `f_open`, `f_read`, `f_write`, `f_close` und der Weg zum Plattenplatz | hergeleitet | |

## Umsetzung

Der Lader von BLECH hängt am Ende der PCM-Ladung (`0xC00473D0`, `mov r0, r6`), weil dort Tabellen und DSP fertig sind, die Karte
geht und `r6` sagt, ob es eine Bank gibt. Er hängt neue Instrumente an die Tabellen an und lenkt Einträge der Oszillator-Tabelle darauf
um; die Liste selbst zu verlängern kostet 13 Vergleiche, zehn Zugriffe und drei Arrays je Part (Tabelle 2). Die Wellen gehen in
Blöcken zu 16 KiB (im Emulator ist ein 32-KiB-Lesen in diesem Zustand viel langsamer, Ursache offen) von der Karte in den DSP.
Der tatsächliche Aufbau steht in [Eigene Samples auf der blauen](2026-11-12-blau-sample-import.md).

## Das Werkzeug und die Prüfungen

`tools/emu/synth_probe.py` (GPL-2.0-only wie der Rest von `tools/emu/`):

```bash
tools/emu/.venv/bin/python tools/emu/synth_probe.py bank DATEI            # Aufbau einer Bank (Flash-Sicherung, PCM.VSB oder 8 MiB)
tools/emu/.venv/bin/python tools/emu/synth_probe.py osc SYSTEM.VSB        # Oszillator-Tabelle, Stellen mit der Grenze 408
tools/emu/.venv/bin/python tools/emu/synth_probe.py boot SYSTEM.VSB --synthetic --voice 1 --relocate
tools/emu/.venv/bin/python tools/emu/synth_probe.py boot SYSTEM.VSB --bank DATEI --held 0x2000
tools/emu/.venv/bin/python tools/emu/synth_probe.py fatfs SYSTEM.VSB --synthetic
tools/emu/.venv/bin/python tools/emu/synth_probe.py demo SYSTEM.VSB [--replace 1] [--png bild.png]
```

`boot` startet die Firmware auf einem Flash, der die Bank trägt (der Flash selbst ist leer, mit der Kennung des Synths) und
berichtet, was sie vom Flash liest und in den DSP schreibt, die Tabellen im RAM, die Seitenkarte; mit `--voice` die Stimme.
`demo` macht aus dem Emulator heraus, was der Lader tun würde. Die Tests in `tools/emu/test_synth_probe.py` laufen ohne Firmware
(Packer, Bank, Strom, Tonhöhe, Befehlssuche) in `npm test`; die gegen die Firmware (`E2_BLUE_VSB`, in
`npm run test:emu`) booten die selbstgebaute Bank, vergleichen die DSP-Bytes bitgenau, prüfen die Stimmennachricht, den
angehängten Instrument-Eintrag, den DSP-Schreiber, EXIT am Ende der Ladung.

## Offen

- Spielt der DSP von einer Adresse hinter den Werksdaten, und wo hört sein Speicher auf? Am Gerät.
- Die Tonhöhen-Konstante und die Tastenzählung. Am Gerät, ein Messton.
- Die Bank der blauen (Zahl der Instrumente, Größe): die eigene Datei fehlt.
- Wie ein Pattern den Oszillator speichert, und ob die Part-Arrays beim Ersetzen etwas speichern, das nicht stimmt.
- Warum ein 32-KiB-Lesen in der Ladephase im Emulator so langsam ist (Kartenmodell oder Treiber).
- Ob die Firmware eine Bank mit falscher Summe tatsächlich ablehnt (im Emulator nicht probiert).
- `f_unlink` im Synth: mit der Signatur des Samplers nicht gefunden.
- Stereo-Instrumente der Bank (zwei Samples je Instrument): nicht untersucht.
