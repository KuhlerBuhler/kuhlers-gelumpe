# Effekte und Klangfunktionen: Hintergrund

Wissensseite zu den Effekt-Funktionen und Klangfunktionen von BLECH, nach Themen geordnet: Effektdatei vom Gerät lesen, Effekte beim Start
neu anwenden, Pegel und Röhrenkurve, TAP Motion einmal, Glide und CUTOFF auf allen Parts, Filter-Schnellschalter, Touch Scale Umfang 0,
Spettro und der Start-Haken der blauen Electribe. Die Katalog-Effekte selbst stehen im [Effekt-Katalog](../effekt-katalog.md).
Die rohen Messnotizen stehen in der Git-Historie (`git show 03c7827adc7b:docs/messungen/<Datei>`), die Quelle steht unter jedem Abschnitt.

Markierungen: **gemessen** (Emulator oder Gerät, steht dabei), **offline** (Code gelesen), **hergeleitet**, **offen**. Wo nichts anderes
steht, ist am Gerät nichts geprüft.

## Effektdatei `e2sFx.all` über SysEx lesen

Die App liest die Effekt-Sammeldatei `KORG/blechtribe/Presets/e2sFx.all` von der Karte ohne Kartenleser
([Effekte vom Gerät](../messungen/2026-11-14-effekte-vom-geraet.md), Dateitabelle in [Sample-Datei](sample-datei.md)).

- **offline:** die Bits 30 und 29 im Offset von FILE READ wählen `SD:KORG/blechtribe/Presets/e2sFx.all`, den Pfad, den der Lader beim
  Start liest (`tools/patch/fx_card.s`). Grenze 256 MiB wie bei der Sample-Datei. `BLECH.FILE_FX` in `src/protocol.mjs`, `FILE_FX` in
  `tools/patch/blech_sysex.py`.
- **offline:** nur lesen. FILE BEGIN mit denselben Bits sagt Status 3 und schreibt nichts. Mit Bit 31 dazu nennen die Bits keine Datei,
  READ und BEGIN sagen Status 3. Eine ältere Firmware sagt bei READ ebenfalls Status 3, daran erkennt die App sie (kein INFO-Bit dafür).
  Fehlt die Datei: Status 6.
- **gemessen (Emulator, Hacktribe und Korg Original, `fx_read_cases` in `tools/emu/sysex_cases.py`):** `fx_read` (66313 Byte, Größe stimmt,
  in 3 Blöcken gleich zurückgelesen), `fx_read_tail` (READ über das Ende gibt die letzten 100 Byte), `fx_write_refused` (Status 3, Datei
  unverändert), `fx_missing` (Status 6). `doom_refusals` liest mit den Bits 31, 30 und 29, weiter Status 3.
- **Code-Bereiche:** der zweite Code-Bereich (Sample-Befehle ab `0xC017B950`) ist auf der blauen bis `0xC017C000` voll, dort beginnen die
  Preset-Tabellen. `doom_path`, die Doom-Namen und der neue Pfad liegen im Hauptbereich: der endet bei `0xC0172F0C` (`0xe0c` von `0xf00`
  Byte), der zweite bei `0xC017BF6C`, auf der blauen bei `0xC017BF90`.
- **Offen:** am Gerät lesen, sobald eine Firmware mit dem Patch auf der Karte ist. Blau: gleicher Code, nicht ausgeführt. Die App hat
  noch keinen Knopf dafür.

Quelle: Messung 2026-11-14/fx-datei-lesen

## Effekte beim Start neu anwenden (`fx_reapply`)

Lädt der Start `e2sFx.all`, stehen die neuen Presets im RAM, der DSP spielt aber noch die Effekte, die das Pattern beim Laden geschickt
hat. Nach dem Laden setzt `fx_reapply` (`tools/patch/fx_card.s`) darum den MFX des Patterns und den IFX jedes der 16 Parts einmal auf
Typ + 1 und zurück, beide Male mit Meldung an den DSP. MFX geht über den Setter des Pattern-Menüs, IFX über die Part-Bearbeitung, Feld 26.
Mit gleichem Wert und ohne Meldung schickt die Firmware nichts.

- **Beleg (gemessen, Emulator, beide Firmwares):** ein Datensatz IFX bzw. MFX Nummer 5 in der Datei, der als Folge von drei
  DSP-Übertragungen genau so beim Wählen dieses Typs ohne Datei entsteht, steht unter den Übertragungen des Starts mit Datei
  (`boot_ifx_sent`, `boot_mfx_sent`).
- **Offen:** ob das Umschalten das Pattern als geändert markiert.

Quelle: Messung 2026-11-05/effekte-start-splash-liste (Fälle `splash_menu_cases` in `tools/emu/menu_cases.py`)

## Pegel: Gain-Staging im Baukasten

Der Linter und die Pegel-Ansicht (Regeln in [Linter](../linter.md)) beruhen auf diesen Entscheidungen:

- Die Insert-Pegel werden **angezeigt, nicht skaliert**. Ein Preset kann mehrere Parts und Patterns bedienen, es zu ändern ist Sache des
  Effekt-Editors. Das Master-Preset ist nicht dabei.
- Der Zugang ist der Puffer des Geräts, kein Dateieditor: Patterns haben im Editor keine Dateiseite.
- **Hergeleitet, nicht geprüft:** der Menüplatz eines Parts ist der gespeicherte Typ plus 1 (Insert-Menü 38 Einträge, beobachtet Typen 0
  bis 37, mit Hacktribe mehr). Die Zuordnung Part zu Preset in der Ansicht steht darauf.
- "Verzerrer-Preset" ist als Baustein `0x0f` (Distortion) gelesen. Bei einem anderen Baustein gilt nur die allgemeine Grenze von 90.
- Erreichen die Werks-Presets desselben Bausteins den Wert selbst, bleibt der Linter still: der Decimator liefert `output_level` 127 ab
  Werk. Die Prüfung `factory-check:gain-staging` hält die beiden gehörten Fälle gegen die Werkspresets (keines kommt an die gehörten
  Werte heran, der Pegelmodulator liegt bei 32 bis 36).
- **Offen:** am Gerät hören, ob die Skalierung im Satz so klingt wie die Vorschau. Die Standard-Ausgangsverstärkung per Patch neu
  abstimmen ist nicht angefangen. Die Obergrenze zwischen 60 und dem gehörten Fehlerfall ist unbekannt (dort steht die Warnung
  "ungetestet").

Quelle: Idee 31

## Röhrenkurve: Korgs Clipper ersetzen

Gebaut ist der Patch in [Röhrenkurve](../messungen/2026-11-20-roehrenkurve.md) (Adressen `0xFFA0135C` und `0xFFA01348`, Aufrufstelle, Kurve).
Facts aus dem DSP-Programm der roten Firmware (gleich Hacktribe, **offline gelesen**):

- Nach Master-Effekt und Dry/Wet läuft fest ein Soft-Clipper `0xFFA0135C` (rund 190 Byte bis `0xFFA01418`), für L und R gleich, in place auf
  `[P4 + 0x10]` und `[P4 + 0x14]`. Er hat keine Parameter. Schwelle `0x361962E9` (etwa 0,42) und Nachverstärkung (etwa 1,24) stehen als
  Konstanten im Code, über der Schwelle wird symmetrisch kubisch abgerundet.
- Gerufen wird er über eine fest geladene Adresse (`0xFFA01742`/`0xFFA01746`, `CALL (P0)`), nicht über die Effektliste.
- Die Kurve wirkt vor dem Aufnahme-Abgriff `0xFF802888` und landet mit auf einer nativen Aufnahme
  ([Natives Aufnehmen](../messungen/2026-11-17-native-aufnahme.md)).

Warum ersetzen statt hinzufügen (hergeleitet): der Clipper rechnet ohnehin jedes Sample, ein Ersatz mit ähnlich vielen Befehlen kostet kaum
mehr DSP-Zeit, und der DSP hat nach bisherigem Stand wenig Luft (Auslastung nicht gemessen).

Nicht gewählt: ein zweiter Effekt vor dem Clipper (Rechenzeit); Limiter oder Kompressor mit Hüllkurve (mehr Zustand und Rechenzeit);
Tape-Sättigung mit Hysterese oder harte Kurven mit Oversampling (zu teuer); Katalog-Effekte an dieser Stelle (sie laufen in Korgs
Effekt-Engine mit Einheit und Steuerzeilen). AUDIO IN und VOLUME scheiden als Regler aus: sie sind analog vor dem Wandler und schicken
keine Panel-Nachricht.

**Offen:** DSP-Auslastung (am Gerät oder in Zyklen im QEMU-Kern), Klangziel und Grenzen der Regler, Name und Platz des Menüpunkts.

Quelle: Idee 113

## TAP Motion: einmal abspielen (ONCE)

Baut auf [TAP Motion](../messungen/2026-10-15-tap-motion-patch.md) auf. Gemessen im Emulator (`tools/emu/tap_motion_cases.py`, Gruppe
`case_once`) mit BLECH auf Hacktribe und Korgs Original der blauen Electribe 2.

- **Mechanismus:** mit dem Einstellungswort `TM_SETTING` auf 2 spielt eine Bewegung, die TAP eingeschaltet hat, bis zum Ende des Patterns
  und geht dann von selbst aus. Gemerkt wird je Part der Schrittzähler (`0xC06904B0 + 0x48 * Part`) beim Einschalten. In jedem
  Bildschirm-Takt der UiTask vergleicht der Patch: ist der Zähler kleiner als beim letzten Blick, hat das Pattern neu angefangen, und der
  Part geht aus wie mit TAP (gemerkter Modus, Setter der Firmware). Steht der Sequencer, wird nicht verglichen.
- **Haken:** am Aufruf `0xC00836F0` der Bildschirm-Schleife (blau `0xC0073CF4`), also im selben Task wie TAP. Im Takt des LED-Managers
  hielt der Effekt am Gerät an (siehe unten).
- **gemessen:** `once_plays_to_the_end` (Regler in den Schritten 16 bis 31 aufgenommen, TAP aus bei Schritt 2, an bei Schritt 8: der erste
  Durchlauf spielt 16 von 16 Schritten, der zweite und dritte keinen, danach ist das Byte 0 samt Kopie), `once_comes_back_with_tap` (TAP
  danach schaltet mit dem gemerkten Modus wieder ein), `on_keeps_playing` (Einstellung 1: auch der zweite Durchlauf spielt). 36 Prüfungen
  auf beiden Builds bestanden.
- **Master FX:** hat keinen eigenen Zähler, der Patch nimmt den von Part 1 (hergeleitet). Hat Part 1 einen kürzeren LAST STEP als das
  Pattern, gehen die Master-FX-Spuren früher aus. Offen am Gerät.
- **Am Gerät (17.10.):** lief ONCE im Takt des LED-Managers, ging die Bewegung der Master-FX-Spuren am Patternende aus, der Effekt
  (Highpass, Looper) blieb aber an. Mit MASTER FX gehalten plus TAP geht er aus. Der Emulator zeigt das nicht. Darum läuft ONCE in der
  UiTask. Ob der Effekt am Gerät jetzt ausgeht, ist offen.
- **Offen:** ob beim Ausschalten am Patternanfang der Wert von Schritt 1 kurz anliegt (Vergleich im 40-ms-Takt, ein Schritt dauert bei
  160 BPM 94 ms).

Quelle: Messung 2026-10-17/tap-motion-einmal

## CUTOFF und Glide: Hauptbyte und Kopie auf allen Parts

CUTOFF (Encoder-Index 2) und Glide (SHIFT `0x0A` gehalten plus Regler OSC PITCH, Index 2, Eingabewert `200 + 2 * Part`, die Firmware setzt
Glide `100 + Part`) ändern auf jedem der 16 Parts genau zwei Bytes: das Hauptbyte und seinen Mirror in der Kopie der Klangerzeugung. Sonst
änderte sich nichts, keine Assertion. Quelle: PR #379, im Emulator mit Hacktribe 2.02 gemessen (Pattern-RAM vor und nach der Eingabe
verglichen), nicht nachgemessen. Das belegt die Kopien im RAM, nicht die Klangwirkung (der Emulator hat keinen DSP). Offsets relativ zum
Zeiger auf das Pattern-Objekt `[0xC033E6A4]`, der Block beginnt bei `+4`.

| | Hauptbyte | Mirror (Block `+0x4000`) |
|---|---|---|
| CUTOFF | `0x811 + 0x330 * p` | `0x403F + 0x24 * p` |
| Glide | `0x829 + 0x330 * p` | `0x4053 + 0x24 * p` |

Part 0: `0x811`/`0x403F` und `0x829`/`0x4053`. Part 15: `0x37E1`/`0x425B` und `0x37F9`/`0x426F`. Weitere Schreibwege:
[Live-Schreibwege](../messungen/2026-11-03-live-schreibwege.md).

Quelle: Messung 2026-11-06/glide-mirror

## Filter-Schnellschalter: offene Fragen

Gebaut ist er als Patch (Bit 5 von Byte 5, je Part und Familie gemerkt, Adressen je Build: [Filter-Toggle](../messungen/2026-11-08-filter-toggle-eingebaut.md)). Offen
am Gerät:

- Was "Filter aus" (Typ 0) am Klang bedeutet: Filter umgangen oder Cutoff voll offen. Hörprobe.
- Das Fenster beim Setzen und der Patternwechsel am Gerät.
- Ob auch ein Tastenwechsel ohne SHIFT den Speicher benutzen soll (LPF Acid, dann HPF gibt den letzten HPF-Typ). Heute bleibt die Taste
  allein bei der Firmware.

Quelle: Idee 81

## Touch Scale Umfang 0: Test am Gerät

Gebaut für rot und blau, im Emulator geprüft ([Messung](../messungen/2026-10-30-touch-scale-null.md)). Am Gerät offen, in dieser Reihenfolge:

1. Global > TOUCH SCALE RANGE bis 0 drehen, SHIFT + TOUCH SCALE gedrückt halten und X an mehreren Stellen berühren: immer C4.
2. KEYBOARD + 4 drücken: C5. KEYBOARD + 1: tiefer.
3. Tonart im Pattern auf D stellen: D4.
4. GATE ARP, ein Pad halten, Touchpad berühren: Arp mit Pad-Note und Grundton, Y ändert die Länge.
5. Aus- und einschalten: die 0 bleibt.

Quelle: Idee 84

## Spettro: Analyse

Der Dienst ist aus dem Gerät entfernt, die Anzeige in [Plugin API 31](../messungen/2026-11-12-plugin-api31-spektrum.md). Die Analyse (Code nur in
`tools/patch/spectrum/`):

- Der Leser lässt 256 Frames Sicherheitsabstand zum Schreiber. Er prüft Quelle, Zeiger und Zeit vor und nach dem Transfer, Lücken
  verwerfen das alte Fenster.
- 4096 Frames werden nach Mittelwertentfernung mit periodischem Hann gewichtet. Die FFT erhält sieben Nachkommabits und benutzt
  64-Bit-Produkte.
- Stereo kombiniert Leistungen, damit Gegenphase sich nicht auslöscht.
- Das Diagramm hat 128 logarithmische Spalten und etwa 72 dB Höhe. Schmale Spalten interpolieren Leistungen, das fügt keine reale
  Frequenzauflösung hinzu.
- Kosten des isolierten Q7-FFT-Kerns: 12 Zählerschritte, etwa 1 ms je Schritt (rund 12 ms), nicht die gesamte CPU-Last und nicht die Latenz.
- Rückmeldeliste am Gerät (9.11.), offen: Start bis Pattern und Menü, die Kurve folgt CUTOFF und RESONANCE (mono), BAR 1 bis 4 (Halten,
  Basslage, Gewinn), PART-Wahl und Pads im Trigger-Modus, PLAY/STOP bei offener App, fallende Kurve nach dem Ton, EXIT und wieder öffnen,
  Minuten mit einem Multi-Part-Pattern.

Quelle: Messung 2026-11-07/spettro

## Synth-Start-Haken (blaue Electribe)

Der Start-Haken von BLECH auf dem blauen Synth sitzt an derselben Stelle wie auf dem Sampler. Hintergrund in
[BLECH auf dem Synth](../messungen/2026-10-16-blech-synth.md). Adressen Sampler / Synth (Gleichheit der 16 Befehle je Stelle über
`FirmwareMap.same_code` geprüft):

| Stelle | Sampler (rot) | Synth (blau) |
|---|---|---|
| gemeinsamer Einstieg | `0xC002ADAC` | `0xC0027FE8` |
| Prüfung des Update-Flags | `0xC002AE40` | `0xC0028074` |
| Probe | `0xC002AEC0` | `0xC0028084` |
| Fortsetzung | `0xC002AEC4` | `0xC0028088` |
| Aufrufziel | `0xC0057884` | `0xC004E678` |
| Einstieg der vollen Laufzeit | `0xC002AFAC` | `0xC0028170` |
| Datei öffnen, lesen, schließen | `0xC009DB60`, `0xC009DD74`, `0xC009E3DC` | `0xC008A6B8`, `0xC008A8CC`, `0xC008AF34` |

Die Karte dieser Stellen kann auch in `data/synth-map` stehen.

**Sicherungsprüfungen des Wrappers, in dieser Reihenfolge:** Panel-Zeiger `0xC033E8F8` (nicht null, nicht `0xFFFFFFFF`), EXIT-Maske
`0x2000` bei Panel `+0x18`, Update-Flag bei Panel `+0x22`, Sonderstartmodus bei Panel `+0x20` muss 0 sein. Dann je einmal: Menü und
Einstellungen, Blechy, Kartenplugins, Seitenzahl. Der Wrapper stellt Register und Flags wieder her, führt den verschobenen Befehl
`ldrb r3,[r4,#4]` aus und setzt bei `0xC0028174` fort.

**Warum der Doom-Lader nicht auf blau läuft:** der native Aufruf bei der Sampler-Adresse `0xC00005A0` ist auf blau nicht bestätigt, und das
geladene Programm enthält Sampler-Adressen und den Ordner `blechtribe`. Die Ladebalken- und Sample-Fehler-Funktionen sind dort nicht nötig,
weil die blaue Firmware keinen Sample-Lader hat (sie hat einen eigenen PCM-Ladebalken); die Synth-Filter sind schon da.

Quelle: Messung 2026-10-16/synth-start-haken, Messung 2026-10-16/blech-synth
