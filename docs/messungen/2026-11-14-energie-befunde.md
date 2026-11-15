# Energie und Last: Befunde vor der Umsetzung

Stand 2026-11-14. Nur gelesen und im Emulator gemessen, kein Patch, kein Gerät. Basis: develop `5e6227a5` mit PR #577.
Grundlage für den Bindungs-Cache der Pad-Farben ([2026-10-20-patch-performance.md](2026-10-20-patch-performance.md)), eine
Lastanzeige, Einstellungen Version 4 und Idle Power Save. "Nicht selbst nachgelesen" heißt: aus einer Codeauswertung
übernommen, Adressen nicht einzeln geprüft.

## 0.1 Lastmethode

**Das Wort `0xC06A2894` (Blau `0xC0573C50`) ist Leerlaufmarke und IRQ-Tiefe zugleich** (gelesen und per Schreib-Haken gemessen,
Hacktribe rot):
- 0 = eine Aufgabe läuft
- Leerlaufschleife setzt 1 (`0xC00017F0`, Blau `0xC0001610`), schläft mit WFI (`0xC0001808` / `0xC0001628`), setzt danach 0
  (`0xC0001820` / `0xC0001640`)
- IRQ-Eintritt zählt +1 (`0xC000159C`, Blau `0xC00013BC`), Austritt -1 (`0xC0001654`). Aus dem Leerlauf: 1 -> 2, verschachtelt 3,
  aus einer Aufgabe 0 -> 1.
- Folge: "Wort == 1" heißt Leerlauf ODER IRQ über einer Aufgabe. Die Lesart der alten Doku (2026-11-08) ist unvollständig.
- Der 2-kHz-Handler `0xC0025B60` wurde im Hacktribe-BLECH-Build in 50 ms nicht getroffen; als Abtastpunkt deshalb der IRQ-Eintritt.

**Messung** (eigenes Python-Skript mit Haken an den Stellen oben, nicht im Repository; 2 s je Szene, Last in %, Modell =
`arm_load.py` Befehle x 5 ns):

| Szene | Rot Modell | Rot A | Rot B | Blau Modell | Blau A | Blau B |
|---|---|---|---|---|---|---|
| idle | 4,14 | 2,17 | 0,0 | 5,15 | 7,11 | 0,2 |
| playing | 10,81 | 3,16 | 0,0 | 11,11 | 8,09 | 0,4 |
| playing-keyboard | 11,04 | 3,68 | 0,0 | 11,34 | 7,23 | 0,8 |
| playing-16-parts | 31,85 | 26,95 | 1,9 | 29,83 | 29,13 | 2,6 |
| 16-parts-keyboard | 31,87 | 26,99 | 2,1 | 29,84 | 29,12 | 2,6 |

A = Zeitstempel: Zeit von "Wort := 1" bis zum nächsten IRQ-Eintritt mit Vorwert 1 ist Schlaf, Rest ist Last.
B = Stichprobe des Worts beim IRQ-Eintritt an der 2-kHz-Kante (Vorwert 0 oder 1).

- **B taugt nicht** (gemessen): fast 0 % statt 4 bis 32 %. Die Arbeit hängt am Tick und ist vor dem nächsten Tick fertig, eine
  tick-synchrone Stichprobe sieht sie nie. Genau die vermutete Verzerrung, nur viel stärker.
- **A ist die Methode.** Abweichung zum Modell 1 bis 8 Punkte. Mit flachem Zeitmodell (`GELUMPE_PACE=flat`) bleibt sie
  (rot idle 2,08 statt 4,15). Exakter Befehlszähler (Code-Haken je Befehl) = Blockzähler = 4,13 %, also stimmt das Modell als
  Befehlszahl; die Lücke liegt in der Zeitbuchhaltung des Emulators (Zeit je Befehl ist nicht überall 5 ns). Am Gerät misst A
  echte Zeit über einen Hardwarezähler, das Emulatormodell ist dort ohnehin nur Näherung (hergeleitet).
- Umsetzung A (hergeleitet): zwei Haken. (1) Leerlauf setzt 1: Zählerstand merken. (2) IRQ-Eintritt mit Vorwert 1:
  Differenz auf Schlafsumme. Haken 2 liegt im heißesten Pfad (jeder IRQ), daher wenige Befehle. Zähler: TIM12 von Timer2
  (`0x01F0C000`, läuft für den 2-kHz-Tick) plus Tickzahl, oder ein frei laufender Timer, falls einer da ist; Wahl bei der
  Umsetzung.
- Emulatorprüfung der Anzeige: A gegen einen Python-Nachbau dieser Messung, Toleranz 1 Punkt, nicht gegen `arm_load.py`.

## 0.4 Einstellungen Version 4

(Kernpunkte selbst nachgelesen: `tools/patch/script_menu.s:684-695`, `:762-786`, `:855-861`, Stand develop 14.11.)
- Satz: magic, +4 Version, +5 Flagbyte (voll), +6/+7 Trust-Anzahl u16, +8 Generation u32, +12 Flagwort (voll), +16 Lookwort
  (voll), +20 n x Trust-CRC, CRC-32. Länge exakt 24+4n.
- `menu_flash_check` (`:688`) verlangt genau `SETTINGS_VERSION`; `menu_record_body` (`:767`) nimmt 1 bis `SETTINGS_VERSION`,
  64er-Trust-Grenze nur bei der aktuellen Version (`:773`). Nur hochzählen würde kartenlose Geräte auf Standard werfen und
  Karten mit mehr als 16 Plugins ablehnen.
- **Vorschlag:** Byte 7 wird zweites Flagbyte, Anzahl nur noch Byte 6 (max 64). In jedem gültigen v1-v3-Satz ist Byte 7 = 0, also
  ohne Weiche lesbar. Bits: 7.0 LOAD METER, 7.1 IDLE POWER SAVE aus (gesetzt = aus, damit der Standard "an" Version 3 schreibt), 7.2 DSP SLEEP, Rest frei. 0 = Standard.
- Änderungen: Version 4; `:688` nimmt 3 und 4; Anzahl nur Byte 6; Trust-Grenze ab Version 3; Maske für Byte 7; `:859` schreibt
  Flags2; Laden wertet Byte 7 aus.
- Migration ohne neuen Flash-Schreibpfad: v3 laden, im RAM als v4 führen, geschrieben wird erst beim nächsten normalen Speichern.
- Downgrade auf 1.4.5: lehnt v4 ab, nimmt die andere A/B-Kopie. Option: v3 schreiben, solange Byte 7 = 0.
- **Konflikt PR #574:** gleiche Stellen in `script_menu.s`; danach wird Flash nur beim Verlassen des Menüs (AUTO SAVE) oder per
  WRITE geschrieben. v4 baut auf #574 auf. Von außen gesetzte Werte (Plugin) würden erst beim nächsten Verlassen gespeichert.
- **Umgesetzt (Phase 4):** wie vorgeschlagen, ohne DSP SLEEP (gestrichen). Im RAM steht Byte 7 in `MX_FLAGS2` (`MENU_STATE-0x15`,
  vorher frei, `menu_arm` nullt es); unbekannte Bits fallen beim Laden weg. Geschrieben wird Version 4 nur mit einem Bit in Byte 7,
  sonst Version 3, also liest 1.4.6 alles, was diese Firmware ohne die neuen Schalter schreibt. Ein v3-Satz mit Byte 7 ungleich 0
  bleibt abgelehnt (Anzahl über 64). Belege: `tools/emu/menu_cases.py:settings_v4_cases` (Karte v3, v4 mit Byte 7 = 0xFF und 40
  Prüfsummen, gelöschte Bits, falsche CRC, v3 mit Byte 7 = 1, v4 mit 65 Prüfsummen, Flash-Kopie v3 und v4, WRITE ohne Karte
  als v4 in den Flash und zurück), HT, rot, blau, gemessen.

## 0.6 Testmodus

(Nicht selbst nachgelesen.)
- Testmodus kennt nur aus/an: LCD aus (`0xAE` über `lcd_invert_hook`), Licht-GPIO auf 0, `bl_set_*` erzwingen 0, `bl_pwm_hook`
  kehrt sofort zurück, Firmware-LEDs über Hold-Byte `0xC0345A1C+0xB98` (jeden Frame neu gesetzt), Plugin-LEDs Level 0, Sollwerte
  bleiben. Wiederherstellen: Hold zurück, `HW_LED_REFRESH 0xC00875F4` für alle LEDs, `menu_look_apply` fürs Licht.
- **Für Stufen ist der Power-Save-Pfad die Basis, nicht der Testmodus:** Licht-PWM mit 16 Stufen (`script_menu.s:2087-2146`)
  kann auch Weiß dimmen; LEDs dimmt pad-colors schon skaliert über das Flag `0xC00F9310`. Vom Testmodus wird nur das Muster
  Hold + Refresh fürs Wecken übernommen.
- Rangfolge: Testmodus > Idle > Firmware-Dimmen > normal. Nach Testmodus-Ende muss `menu_look_apply` den Idle-Zustand übernehmen.
- Offen: Doppelung von Firmware-Power-Save (Batterie) und Idle klären.

## 0.2 Statusleiste (Emulator-Dump `m.fb`, nur Rot)

- Kartensymbol: Spalten 109-114, Seite 0, Zeilen 1-7. Batterie (am Netzteil: Stecker gleicher Größe): Spalten 117-126, Seite 0.
- Seite 0 belegt sonst nur BPM (Spalten 50/52-74). Frei in allen geprüften Zuständen: Seite 0, Spalten 75-108.
- **Vorschlag Lastanzeige: Spalten 100-107, Zeilen 1-7, Seite 0**, 1 px Abstand zur Karte, unabhängig davon, ob eine Karte
  steckt. Pro Bild ändert sich nur Seite 0.
- Blau, REC, Step Jump und das WRITE-Fenster: siehe "Lastanzeige" unten.

## 0.3 Panel-MCU (Panelabbild aus eigener VSB, Cortex-M3, nicht selbst nachgelesen)

- `02 b` (Handler `0x5464`) schaltet nur einen GPIO-Pin (P0B), sonst nichts. Die ARM-Firmware schickt `02` beim Power Save
  (`0xC002856C`) und im Werkstatt-Bildschirm "Battery Check".
- **Kein anforderbarer Sparzustand im Panel** (hergeleitet): kein WFI/WFE im Code, Takt nur bei Init, Abtastrate und LED-Scan
  fest. Was P0B an der Hardware schaltet, ist offen (kein Schaltplan). Einziger Hebel bleibt die LED-PWM über `00 nn wert`.
- LED-Zustand lebt nur im Panel-SRAM; nach einem Panel-Reset müsste der Host alles neu senden. Die ARM-Firmware sendet nur bei
  Änderung (3 s Leerlauf: untere Leiste 25 Hz und TAP, gemessen).

## 0.5 Leerlauf-Erkennung (Verteiler `0xC002814C`, nicht selbst nachgelesen)

| Nachricht | Bedeutung | weckt / setzt Idle zurück |
|---|---|---|
| `00 nn 1/0` | Taste drücken/loslassen (0x22 = Touchpad berührt) | ja (nur Drücken) |
| `01 nn 00 dd` | Drehgeber relativ | ja |
| `02 nn hi lo` | Regler absolut 0..255, nur bei Änderung; nn >= 0x11 Hilfs-ADC | ja ab 2/255 Abweichung; Hilfs-ADC nein |
| `04 nn ...` | Pad drücken (Wert) / loslassen (Nullen) | ja (nur Drücken) |
| `05 ...` | Touchpad-Position, solange 0x22 gehalten | ja |
| `06`, `07`, `80`, `9x`, `Ax` | Power-Taste, Netzteil, Antworten | nein |

- Panel schickt nichts periodisch. Totband im Panel: etwa 1 Schritt von 0..255.
- APO-Zähler steht bei Disabled auf -1 und zählt nicht; er wird auch von `07`, Antworten und MIDI (außer F8/FE) zurückgesetzt.
- **Entscheidung: eigener Idle-Zähler im Eingabehaken `0xC002837C`**, Zurücksetzen nach der Tabelle. MIDI Noten/CC und PLAY
  halten wach (Entscheidung 14.11., eigener Weg, nicht über APO).
- Offen am Gerät: Regler-Rauschen in Ruhe, ob gehaltene Pads weiter senden.

## 0.7 DSP (Blackfin-Disassembly aus der Hacktribe-VSB, rot; Blau an diesen Stellen nicht geprüft; nicht selbst nachgelesen)

- **Der DSP schläft nie** (hergeleitet): Audio-Task wartet je Block auf den SPORT0-DMA, die Stimmenschleife und alle Effekte
  laufen auch in Stille jeden Block. Zwischen den Blöcken kreist eine Idle-Schleife (`0xFFA0AB38`) ohne `IDLE`.
- "Nichts klingt mehr" kann der ARM billig sehen: Spitzenpegel der Stereo-Summe nach allen Effekten (`0xFF9030F4/F8`, liest die
  CPU schon alle 40 ms), dazu die Stimmen-Gates aus dem eigenen Verkehr.
- **Variante A, DSP im Reset (GP6[10]) und neu booten:** möglich, aber auf Rot praktisch nicht machbar.
  - Der Boot nullt den SDRAM mit den Samples, die müssten wie beim Start neu geladen werden ("Loading nnn%", Sekunden).
  - Boot über SPI1 mit 271 008 Byte: geschätzt 1 s oder mehr bis zum ersten Ton.
  - Während des Resets muss jeder Host-Port-Zugriff gesperrt sein (Pegel 40 ms, Regler, MIDI, ~2000 Abfragen/s). Mehrere
    Warteschleifen ohne Zeitgrenze, Hängerisiko für den ARM.
  - Keine Routine "alles neu an den DSP senden" gefunden.
- **Variante B, `IDLE` in die DSP-Idle-Schleife (Recherche C3):** kleiner DSP-Patch, kein Zustandsverlust, keine Verzögerung,
  der SPORT-Interrupt weckt jeden Block. Spart nur zwischen den Blöcken. Nutzen unbekannt, weil die DSP-Auslastung unbekannt ist.
  Kein freies Byte an der Stelle, Code müsste verschoben werden. Fehler im DSP-Patch: Rückweg im schlimmsten Fall JTAG.
- Audio IN ohne DSP erkennen: nein, der Eingang geht über SPORT0 direkt in den DSP, den Pegel rechnet der DSP.
- Der AM1808 kann den DSP-Takt nicht stoppen (eigener Chip, eigene PLL).
- **Urteil: den DSP nach STOP schlafen zu legen entfällt auf Rot** (entschieden 14.11., Variante B wird ebenfalls nicht
  verfolgt). Nutzen wäre nur mit Gerätemessung zu klären: Strom im Stand gegen DSP im Reset und DSP-Auslastung über einen
  Test-Stream mit Zähler in der Idle-Schleife.

## Umgesetzt: Pegel-LEDs nur bei Änderung (14.11.)

Die Sendefunktion des LED-Managers `0xC00875F4` (Blau `0xC00776B0`) soll ohne Zwang (r2 = 0) nur senden, wenn sich etwas
geändert hat. Ihr Vergleich nimmt aber das Modusbyte des Sollwerts (`0x4D+8L`) für die gesendete Helligkeit (`0x88E+8L`)
(gelesen). Für die zwölf Pegel-LEDs (`0x4C` bis `0x57`, Modus 1) sendet sie deshalb fast immer, nur nach Helligkeit 1 nie
wieder; daher kommt die Regel "nie 1" im Look der Lastanzeige. Die Pegelfunktion `0xC0088284` ruft sie alle 40 ms für jede
LED, also rund 300 Panelnachrichten je Sekunde im Leerlauf, auch wenn die Leiste still steht.

`meter_dedupe_hook` (`tools/patch/script_menu.s`) sitzt hinter der Sperrprüfung auf `cmp r2, #0` (`0xC0087608`, Blau
`0xC00776C4`) und merkt sich je Pegel-LED Helligkeit und Modus der letzten Nachricht in `METER_SENT` (48 Byte hinter
`DATA_FILE`, FF beim Einschalten passt zu nichts). Gleicher Wert ohne Zwang: zurück ohne Nachricht. Anderer Wert oder Zwang
(Sperre frei, Testmodus, `korg.led`-Auffrischung): Wort neu, dann der Sendepfad selbst, also auch Helligkeit 1. Die
Abdunklung durch Korgs Power Save (`[Manager+0xB78]`) zählt als Helligkeit 0. Andere LEDs, das unscharfe Menü (EXIT beim
Einschalten) und der Ladebildschirm (Bildschirm 0) gehen unverändert weiter.
Was der Ladebildschirm oder ein Plugin mit `korg.led` an eine Pegel-LED schickt, vergisst das gemerkte Wort (FF), damit
die nächste Nachricht der Firmware wieder rausgeht und die Leiste nicht auf dem fremden Wert stehen bleibt.

Warum der Ladebildschirm ausgenommen ist (gemessen im Emulator, Hacktribe und Rot): mit Entprellen auch dort brauchte der
Sample-Lader beim Start 51 ms länger (368 bis 1563 ms statt bis 1511 ms), der Hauptbildschirm kam 53 ms später
(`menu:early_look_main_screen_not_later` rot). Der Lader fragt die Karte in einer Schleife ab und kommt früher wieder an die
Reihe, solange die UART-Interrupts der Panelnachrichten kommen. Ohne Entprellen auf dem Ladebildschirm: 1540,6 ms
(Hacktribe) und 1541,0 ms (Rot) wie in Phase 2. Am Gerät nicht gemessen; ob Kartenarbeit auf anderen Bildschirmen
(Pattern schreiben, Sample-Tausch) ohne die Leerlauf-Nachrichten ebenso etwas länger dauert, ist offen. Die Tastenlatenz
(PLAY bis zur ersten LED-Nachricht) wurde dabei 1 ms kürzer.

Gemessen mit `tools/emu/arm_load.py` (Stand Phase 2 gegen Phase 3, `blech.json` bzw. `blech-synth.json`, je 2 s):

| Szene | Panelnachrichten/s (Hacktribe, Rot, Blau) | Last in Punkten |
|---|---|---|
| idle | 298,5 / 304,0 / 304,5 -> 0 / 0 / 0 | -0,18 / -0,18 / -0,18 |
| playing | 341 / 341,5 / 339,8 -> 41,3 je Build | -0,18 / -0,18 / -0,19 |
| playing-keyboard | 401,5 / 401,5 / 401 -> 101 / 101 / 100,5 | -0,18 / -0,18 / -0,20 |
| sequencer-four-note-long-ties | 485,5 / 485 / 485,5 -> 185,5 / 185 / 185,5 | -0,18 / -0,18 / -0,20 |

Die Pegel-LEDs senden beim Spielen weiter (41 Nachrichten je Sekunde), nur ein gleicher Wert entfällt. Firmware-Assertions 0.
`test_meter_dedupe_sends_only_a_change` in `tools/patch/test_script_hooks.py` prüft Gleich, Änderung, Modus, Zwang,
Helligkeit 1, Power Save, Nachbar-LEDs und das unscharfe Menü. `tools/emu/meter_led_cases.py` prüft dasselbe am
gebooteten Gerät im Emulator (Leerlauf ohne Pegelnachricht, Änderung einmal, Zwang, Helligkeit 1, EXIT beim Einschalten wie
vorher). Am Gerät nicht geprüft.

## Lastanzeige (Phase 5, umgesetzt)

(Selbst nachgelesen und im Emulator gemessen, HT, rot, blau; Gerät nicht.)
- **Freie Spalten (5.0):** Seite 0, Spalten 95-108 sind auf allen drei Builds leer: Hauptbildschirm, beim Spielen, in REC, in
  Step Jump und im WRITE-Fenster. Kartensymbol Spalten 109-114, auf Blau gleich. Auf Rot und HT ist VRAM das nächste Bild und
  weicht vom Controllerpuffer ab, auf Blau sind beide gleich.
- **Umsetzung:** `tools/patch/script_load_meter.s`, Methode A aus 0.1. Haken an der Leerlaufschleife (`0xC00017F0`, Blau
  `0xC0001610`, `str r3, [r6]` vor wfi) merkt sich Timer3; Haken am IRQ-Eingang (`0xC000159C`, Blau `0xC00013BC`) addiert beim
  ersten IRQ, der das Leerlaufwort auf 1 findet, die Schlafzeit. Der Rahmen summiert seine Timer3-Abstände und rechnet nach
  einer Sekunde 100 minus Schlafanteil, gerundet, höchstens 99. Gezeichnet werden zwei Ziffern 3x7 mit Abstand in Spalten 100-107, nur auf
  dem Hauptbildschirm ohne Fenster, ohne offene App, ohne eigene Frage und ohne Ordnerübernahme, und nur Bytes, die sich
  unterscheiden (danach `MG_MARK`). Schalter: Byte 7 Bit 0 (`MX_FLAGS2`), also Version 4 beim Speichern.
- **Nachbesserungen nach dem Review:** ein dritter Haken an der Stelle nach dem Aufwachen (`0xC0001820`, Blau `0xC0001640`,
  `str r3, [r6]` mit r3 = 0) löscht die gemerkte Marke, damit ein IRQ, der das Leerlaufwort nicht mehr auf 1 findet, keine
  alte Zeit zählt. Gemessen wird erst, wenn `menu_arm` gelaufen ist (`LM_ARMED`); mit EXIT beim Einschalten bleibt die
  Summe unberührt, und der IRQ-Pfad bleibt gleich lang, weil ohne Marke nie etwas gültig ist. Liegen zwischen zwei Rahmen mehr
  als 1000 OS-Ticks (1 ms), beginnt die Messung neu, statt ein langes Fenster zu verrechnen. Im Disassembly geprüft: die
  Leerlaufschleife lädt r0 bis r2 am Anfang (`0xC00017CC`) neu, der IRQ-Eingang schreibt r0 bis r2 vor dem Lesen, die
  Haken dürfen sie also benutzen.
- **Zahl statt Balken (5.4):** zwei Ziffern lesen sich neben Tempo und Karte ohne Legende, ein Balken in 8 Spalten hätte nur
  8 Stufen gehabt. Bilder im Emulator (Scratch, nicht im Repo): Leerlauf zeigt "2" (Blau "3" bis "4"), 16 Parts spielend "27".
- **Genauigkeit:** `tools/emu/load_meter_cases.py` rechnet Methode A aus denselben zwei Stellen in Python nach (Zeit vom Store
  bis zum IRQ-Eingang mit r3 = 1) und vergleicht jedes Fenster zwischen zwei gespeicherten Werten: Leerlauf HT 2/2, rot 2/2,
  blau 3/3 und 4/4; 16 Parts spielend auf allen dreien 27/27. Abweichung 0 Punkte (erlaubt 1).
- **Kosten:** Befehle im eigenen Code mal 5 ns (Modell aus 0.1) über 2 s Leerlauf: aus 0,036 Punkte (Blau 0,035), an 0,038
  Punkte, auf allen drei Builds (Grenze SC-5.1: 0,1). Aus kostet nur die zwei Haken und den frühen Rücksprung im Rahmen.
- **Schalter und Speichern:** Seite DISPLAY 6/6 "LOAD METER", OFF Vorgabe, das Rad schaltet sofort; im Menü keine Ziffern;
  WRITE schreibt Version 4 mit Byte 7 = 1, der nächste Start liest es und zeigt die Ziffern. Im WRITE-Fenster der Firmware
  sind die Spalten leer, danach kommen die Ziffern wieder; OFF nimmt sie sofort weg. ORIG-Plakette über `orig_masks` (Byte 7).
- **Downgrade:** ein BLECHTRIBE bis 1.4.6 lehnt den Satz der Version 4 ab und nimmt die andere Kopie oder die Standardwerte.
- Offen: am Gerät nicht geprüft. Im Emulator folgt die Zeit dem 5-ns-Modell, am Gerät misst Timer3 die echte Zeit, die Zahl kann dort anders ausfallen.

## Idle Power Save (Phase 6, umgesetzt)

(Selbst nachgelesen und im Emulator gemessen, HT, rot, blau; Gerät nicht.)
- **Umsetzung:** `tools/patch/script_idle.s`. Zeit in `IS_LAST` (OS-Tick, 1 ms), `idle_frame` im Rahmenhaken rechnet die Stufe:
  ab 2:00 Stufe 1 (75 %), 3:00 Stufe 2 (50 %), 4:00 Stufe 3 (25 %), 5:00 Stufe 4 (dunkel). Nur bei einem Stufenwechsel
  laufen `menu_look_apply`, die LEDs der Firmware (erzwungenes `HW_LED_REFRESH` 0 bis 0x57, außer ein Plugin oder der
  Testmodus hält sie) und die LEDs der Plugins neu.
- **Licht:** `idle_scale` skaliert INTENSITY und SAVE LIGHT mit (i * (4 - Stufe) + 3) >> 2, Weiß 15 also 12, 8, 4, 0 von 16.
  Damit läuft im Dimmen der PWM-Weg auch für reines Weiß. Mit SAVE LIGHT 0 bleibt das Dimmen der Firmware in Stufe 1 bis 3
  stehen (es ist dunkler), in Stufe 4 schaltet `bl_pwm_save_none` alle Pins aus.
- **LEDs:** pad-colors liest den Prozentwert in `S_IDLE` (`PC_IDLE`) und nimmt das Minimum aus dem Viertel der Firmware und
  dem Idle-Wert; LEDs eines Plugins skaliert `script_led_try_send` in Stufe 1 bis 4 gleich (aufgerundet, eine leuchtende LED
  bleibt bis Stufe 4 an).
- **Wachhalten:** Taste (`00 nn 1`), Pad, Drehgeber, Touchpad (`00 22`, `05`), Regler nn < 0x11 erst ab 2/255 Abstand zum
  gemerkten Wert, PLAY (`HW_TRANSPORT`), MIDI-Note und CC im MIDI-Haken (Clock kommt dort nicht an), `korg.system.keepAwake()`.
  Testmodus hält wach und hat Vorrang. Mit EXIT beim Einschalten bleibt `IS_STAGE` 0xFF, nichts davon läuft.
- **Wecken:** `idle_input` im Eingabefilter: die erste Bedienung im gedimmten Zustand weckt und wird verschluckt, je Taste und
  Pad ein Bit bis zum Loslassen, Touchpad-Positionen bis Taste 34 losgelassen ist. Ein Regler: die weckende Bewegung wird
  verschluckt, der gemerkte Wert übernommen, die nächste Bewegung geht durch.
- **Fälle:** `tools/emu/idle_save_cases.py`, 18 Fälle, HT 18/18, rot 18/18, blau 18/18: jede Stufe (Licht 0,75/0,50/0,25/0,
  LEDs genau aufgerundet skaliert), Wecken mit Taste, Pad, Touchpad, Regler und Drehgeber verschluckt, MIDI-Note und CC wecken,
  Clock nicht, PLAY hält wach (Netzteil und Batterie), Testmodus vor Idle, Korg Power Save plus Idle nie heller, Plugin-Licht
  und -LED gehalten und zurück, keepAwake weckt, Schalter: Vorgabe ON schreibt Version 3, OFF Version 4 mit Byte 7 = 2, der
  nächste Start liest es, EXIT beim Einschalten ohne Wirkung.
- **Kosten des PWM:** Befehle mal 5 ns (Modell aus 0.1) über 1 s Leerlauf, wach (Weiß als Pin) gegen Stufe 1 (Weiß per PWM):
  HT 4,00 % gegen 4,02 %, rot gleich, blau 4,98 % gegen 5,00 %, also 0,02 Punkte.
- **Schalter:** Byte 7 Bit 1 gesetzt heißt OFF (`FLAGS2_IDLE_OFF`), damit die Vorgabe ON den Satz bei Version 3 lässt und ein
  BLECHTRIBE bis 1.4.6 ihn weiter liest.
- Offen: am Gerät nicht geprüft (Strom, Sichtbarkeit der Stufen, ob 25 % Weiß noch lesbar ist).
