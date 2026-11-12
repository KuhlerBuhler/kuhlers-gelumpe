# Eigene Samples auf der blauen Electribe 2: wo im DSP-Speicher Platz ist

Stand 12. November 2026. Korgs blaue Firmware 2.02 (Synth), zum Vergleich Korgs rote 2.02. Frage für 1.5: wohin mit
eigenem PCM auf der blauen, die kein IMPORT SAMPLE hat, und wie viel Platz ist dort. Baut auf
[Samples auf der blauen Electribe 2](2026-10-15-synth-samples.md) (Oszillator-Tabelle, Lader, Entwurf) und
[Die PCM-Bank der blauen aus WAV-Dateien](2026-10-15-synth-pcm-flash.md) auf. Markierungen: **gemessen**, **gelesen**
(Code oder Bytes), **hergeleitet**, **Urteil**, **offen**.

## Kurzfassung

1. Das DSP-Programm der blauen reserviert für PCM **genau 16 MiB**: `0x365AE0` bis `0x1365AE0`. Direkt dahinter legt der
   DSP seine Effektpuffer an. Die rote reserviert an derselben Stelle 25 MiB (`0x365EC0` bis `0x1C65EC0`).
2. Die Werkswellen der blauen füllen davon rund 11 MB. **Frei im Fenster bleiben rund 5,4 MiB** (etwa 56 s mono bei
   48 kHz), nicht 9 MB.
3. Hinter allem, was der DSP lädt oder adressiert, liegen noch rund 11,5 MiB SDRAM ohne bekannten Nutzer
   (`0x1381354` bis `0x1F00000`). Ob eine Stimme von dort spielt, sagt der Code nicht eindeutig; das klärt nur das Gerät.
4. Der Weg für eigene Samples ist derselbe wie für die Werkswellen: der ARM schreibt PCM beim Start über den Host-Port in
   den DSP, eine Stimme bekommt nur Startadresse, Schleife und Tonhöhe. Das ist im Emulator schon gezeigt
   ([Entwurf](2026-10-15-synth-samples.md#entwurf-blech-samples-vom-kartenordner-als-oszillatoren)).

## Die Zahl 9 MB

Die Angabe "rund 9 MB frei im DSP-Speicher der blauen" stammt aus einem anderen Projekt (Omnitribe, eine Erweiterung auf
Hacktribe-Basis). Dessen Quelltext ist nicht mehr erreichbar (Repository und Konto liefern 404, 12.11., kein Archiv), also
ließ sich nicht nachlesen, wie die Zahl entstand. **offen**

Hergeleitet: Omnitribe baut laut seiner Beschreibung auf Hacktribe, also auf dem roten Programm, das auf der blauen läuft.
Dort gilt das 25-MiB-Fenster der roten und es gibt keine blauen Werkswellen im DSP. Für Korgs blaue Firmware gilt die Zahl
nicht unverändert.

Unsere eigene frühere Schätzung von 9,15 MiB ([2026-10-15](2026-10-15-synth-samples.md#4-platz-und-karte)) nahm die
Obergrenze der roten (`0x1C65EC0`). Die blaue hat eine eigene, tiefere Grenze (unten). Die Schätzung ist damit überholt.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| DSP-SDRAM ist 32 MiB: Stufe 1 schreibt `0x13` nach `EBIU_SDBCTL` (`0xFFC00A14`), EBSZ = 32 MB | gelesen | `0xFFA00042` im Bootstrom der blauen, `tools/dsp/dsp_extract.py` |
| Bootstrom der blauen (`0xC00DFB80`, `0x41C74` Byte): Nullfüllung `0x19ED8` bis `0x13769C0` (Block 50), danach Daten bis `0x1381354`, Code ab `0x1F00000` bis `0x1F11888`. Rot: Nullfüllung `0x1A2B8` bis `0x1C76DA0`, Daten bis `0x1C816EC` | gelesen | Blockliste beider Ströme |
| Die Werkswellen der blauen beginnen bei `0x365AE0` | gemessen | [2026-10-15](2026-10-15-synth-samples.md), Strom der PCM-Ladung |
| Der DSP legt ab `0x1365AE0` seine Puffer an: die Routine bei `0x184EA` schreibt die Adresse und Folgeadressen in eine Tabelle bei `0xFF802ECC` (Schritt 12 Byte). Rot macht dasselbe mit `0x1C65EC0` (`0x186C2`) | gelesen | Disassembly beider Ströme |
| Weitere feste Puffer dahinter: blau `0x1365EC0`, `0x1369EC0`, `0x1371EC0` (Puffer von Kommando `0x37`), rot dieselben Abstände ab `0x1C662A0`. Der Abstand vom Fensterende zum Ende der Nullfüllung ist auf beiden `0x10EE0` | gelesen | alle 32-Bit-Konstanten (Paare `.H`/`.L`) zwischen `0x300000` und `0x1F00000` |
| Also: PCM-Fenster der blauen `0x365AE0` bis `0x1365AE0`, genau `0x1000000` Byte. Rot `0x365EC0` bis `0x1C65EC0`, genau `0x1900000` | hergeleitet | aus den drei Zeilen davor |
| Ein Puffer unter dem Fenster: `0x307EE0` (blau) und `0x3082C0` (rot), je `0x5DC00` Byte (384 000, der Master-Effekt) | gelesen, hergeleitet | `0x1F0C402` (blau) |
| Die ARM-Firmware der blauen kennt keine Obergrenze für den DSP-Speicher; ein Lader von BLECH muss `0x1365AE0` selbst einhalten | gelesen | [2026-10-15](2026-10-15-synth-samples.md#4-platz-und-karte) |
| Werkswellen der blauen im DSP: mit der aus den WAVs nachgebauten Bank enden sie bei `0xE03E60` (11 133 824 Byte). Die echte Bank ist etwas größer (der Nachbau kürzt rund 51 000 Werte, etwa 100 KB) | gemessen (Nachbau), geschätzt (Werksbank) | [PCM-Bank aus WAVs](2026-10-15-synth-pcm-flash.md) |
| Frei im Fenster: `0x1365AE0` minus `0xE03E60` = 5 643 392 Byte (5,4 MiB) mit dem Nachbau; mit der Werksbank rund 5,5 MB. Am Gerät rechnet der Lader es aus den `SMPR`-Tabellen | hergeleitet | |
| Zwischen `0x1381354` und `0x1F00000` (12 053 676 Byte) steht keine Konstante im DSP-Code und kein Block im Bootstrom | gelesen | Konstantensuche wie oben. Berechnete Zeiger findet die Suche nicht |
| Ob der Generator einer Stimme (`0xFFA02E4E`) eine Startadresse über `0x1365AE0` annimmt: der Code hat die Konstante `0x1000000` dort nur als Flag-Maske, keine Adressgrenze. Wie er die Wellen liest, ist im Simulator nicht gefunden (Messung "DSP im Simulator", mit dem DSP-Modell) | offen | Gerätetest |
| Stimme bekommt Start (Byteadresse), Schleifenanfang, Schleifenlänge, Tonhöhe; eine Welle an anderer Adresse ändert nur den Start | gemessen (Emulator) | [2026-10-15](2026-10-15-synth-samples.md#3-was-der-dsp-für-eine-pcm-welle-braucht) |
| Die blaue schreibt nach dem Start nie mehr in den DSP-Speicher unter `0xFF000000`; eigenes PCM überschreibt also nichts, was die Firmware später erwartet | gemessen (Emulator) | ebenda |

## Was daraus folgt

- **Sicherer Platz:** im PCM-Fenster hinter den Werkswellen, rund 5,4 MiB. Dort liegen auch die Werkswellen, der DSP spielt
  von dort. **Urteil**
- **Möglicher Zusatzplatz:** `0x1381354` bis `0x1F00000`, rund 11,5 MiB. Nur nach einem Gerätetest, der eine Welle von
  dort hörbar macht und die Effekte (Delay, Reverb, Looper) dabei unverändert lässt. **Urteil**
- Zusammen wären das knapp 17 MiB, etwa 2:50 min mono bei 48 kHz. **hergeleitet**
- Der DSP-Speicher ist flüchtig. Eigene Samples müssen bei jedem Start von der Karte neu geladen werden. **hergeleitet**

## Umsetzung: Samples von der Karte als Oszillatoren

Patch `data/patches/user-samples-synth.json` (Code `tools/patch/user_samples.py`, Fälle `tools/emu/user_samples_cases.py`), im Satz
der blauen. Er nutzt nur das belegte Fenster bis `0x1365AE0`; der Zusatzbereich bleibt bis zum Gerätetest zu.

- Haken am Ende der PCM-Ladung (`0xC00473D0`): der Lader liest `Sample/e2sSample.all` aus dem Ordner der Firmware in Blöcken von
  16 KiB und schreibt die Werte über den Host-Port des DSP hinter die letzte Werkswelle (größtes `SMPR`-Ende, auf 32 Byte), 64 Byte
  Nullen dahinter. Jedes WAV wird ein Eintrag in `SMPR`, `MSRL`, `MSPR` und `MSVS` und ein Oszillator in der Gruppe `[User]`. **gemessen (Emulator)**
- Oszillator-Liste: Tabelle (409 auf 473 Einträge) und Part-Array (A, B, Flag je Oszillator) ziehen in freien Platz um, die Grenze
  `0x198` gilt an 11 Prüfstellen bis `0x1D8`, an den 3 Stellen des Rads bis zum letzten geladenen Sample. Freie Einträge spielen SAW. **gelesen, gemessen (Emulator)**
- Tonhöhe: `256 * (60 + 12 * log2(48000 / Rate))`, Wurzeltaste C4. Im Emulator weicht das Wort höchstens um 1 vom genauen Wert ab. **gemessen (Emulator)**
- Fälle im Emulator (Korgs blaue 2.02 allein und im ganzen Satz): Werte im DSP bitgleich, Stereo gemittelt, Schleife aus `esli`,
  ohne `esli` One-Shot, Pad spielt die Startadresse des Samples, zu groß und 8 Bit werden übersprungen und gezählt, EXIT beim
  Einschalten und keine Datei lassen Tabellen und Liste wie bei Korg; die Startphase von `check.py --quick` ist grün. **gemessen (Emulator)**
- Am Gerät noch nicht geprüft: Klang, Ladezeit beim Start, Pattern mit `[User]`-Oszillator auf Korgs Original. **offen**

## Offen

- Wie Omnitribe auf 9 MB kam.
- Ob eine Stimme der blauen außerhalb des 16-MiB-Fensters spielt.
- Größe der echten Werksbank der blauen (Ende der Werkswellen am Gerät).
- Wie ein Pattern den Oszillator speichert, falls die Oszillator-Liste verlängert wird
  ([2026-10-15](2026-10-15-synth-samples.md#2-die-oszillator-tabelle)).
