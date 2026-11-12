# Pegel-LEDs unten: Spitzenpegel des Ausgangs, nicht Velocity

Stand 12. November 2026. Hacktribe 2.02 (CPU-Code und DSP-Programm aus der Firmware gelesen, DSP-Programm ab
`0xC00F9E10` entpackt mit `tools/dsp/dsp_extract.py`, disassembliert mit einem selbst gebauten `bfin-objdump`), dazu
Emulatorläufe. **Am Gerät nicht gemessen.** Der DSP-Code ist nur auf Hacktribe gelesen; die Kette CPU -> Meter-Objekt -> LEDs
ist im Emulator auf Hacktribe, rot und blau gemessen.

Anschluss an [Audio-Pegel für korg.audio.level](2026-11-11-plugin-api31-audio-level.md): Die LED-Funktion `0xC0088284`
(blau `0xC0078468`) liest alle 40 ms aus dem Objekt `[0xC033E4F4]` das Byte `+0x13` und das oberste Byte von `+0x14`.

## Ergebnis

Die zwei Werte sind die **Spitzenpegel des fertigen Stereo-Ausgangs** (L und R), gemessen im DSP Sample für Sample und
alle 40 ms abgeholt. Mit der Velocity einer Note haben sie nichts zu tun; ein Note-on schreibt sie nicht.

| Befund | Marker |
|---|---|
| Einziger Schreiber von `+0x10..+0x17`: `0xC00248BC` (Wort `+0x10`) und `0xC00248C4` (Wort `+0x14`), Aufrufer `0xC0013798`. Im Emulator 12 Aufrufe in 0,5 s Leerlauf, 23 in 0,5 s mit Noten, also etwa alle 40 ms, immer derselbe Weg | gemessen (Emulator, Schreib-Hook auf das Objekt) |
| Die Werte kommen aus `0xC0014080`: Lesen (`0xA9`) von zwei 32-Bit-Wörtern ab DSP-Adresse `0xFF9030F4`, danach Postfach-Kommando `0x31` mit Parameter `0x4C3D` und Nullen, das die beiden Wörter (und `0xFF9030FC`) auf 0 setzt | offline, Schreiben gemessen (Emulator: `0x31` an `0x4C3D..0x4C3F` im Takt der Leseaufrufe) |
| Parameter `0x4C3D` liegt bei `0xFF8F0000 + 4 * 0x4C3D = 0xFF9030F4` (Adressregel des DSP-Postfachs, `0xFFA071CC`) | offline |
| `0xFF9030F4`/`F8` sind die Felder `+0x50`/`+0x54` des Ausgangsblocks `0xFF9030A4` (eingerichtet in `0x1F0C55C`) | offline |
| DSP `0xFFA01946..0xFFA01966`: je Sample `peak_L = max(peak_L, abs(L))`, `peak_R = max(peak_R, abs(R))` auf dem 32-Bit-Summensignal (1.31) | offline |
| Das Summensignal ist die Mischung aller Parts samt Effekten, nach einer geglätteten Verstärkung (Zielwerte im Block `+0xBC..+0xC8`, Parameter `0x4C58..0x4C5B`), direkt vor der Ausgabe an den Codec (`[P4 + 0x10]`/`[P4 + 0x14]`, invertiert) | offline, hergeleitet |
| Die CPU schickt `0x4C58..0x4C5B` beim Start und beim Spielen nicht; die Verstärkung steht also auf ihrem Startwert. Ob der MASTER-Regler sie stellt oder analog hinter dem Codec sitzt, ist nicht geprüft | gemessen (Emulator), offen |
| Nach dem Messpunkt folgen nur noch ein optionaler Baustein (`[P5 + 0x170]`) und eine Verstärkung bei `+0x19C/+0x1A0` (Startwert `0x7FFFFFFF` = 1,0) | offline |
| Spitzenwert = Maximum über das 40-ms-Fenster seit dem letzten Abholen (Spitzenwert-Halten, kein RMS) | hergeleitet aus Lesen + Nullsetzen |
| Die LEDs nutzen nur das oberste Byte, also eine lineare Amplitudenskala mit 127 Stufen | offline (siehe 2026-11-11) |
| Welche Hälfte L und welche R ist: `+0x10` (erstes Wort, `+0x50`) treibt LEDs 7 bis 12 | offline, Zuordnung zu L/R hergeleitet |

Im Emulator beantwortet das DSP-Modell (`tools/emu/dsp_model.py`) die Lesezugriffe auf `0xFF9030F4..0xFF9030FB`: Es liefert
den größeren Wert aus dem, was die CPU dort zuletzt geschrieben hat (das Nullsetzen), und dem Pegel, den ein Fall mit
`DspModel.output(links, rechts)` setzt. Ohne gesetzten Pegel bleibt die Anzeige bei 0, das Modell hat keinen eigenen Ton.
**gemessen** (Emulator, Hacktribe): Pegel 0.5/0.25 ergibt im Objekt `+0x10 = 0x40000000`, `+0x14 = 0x20000000`, 1.0 ergibt
`0x7FFFFFFF`. Mit Netzteil und Standard-Anzeige färben sich die vier LEDs mit dem Pegel: 0 weiß (120), 0.25 grün, 0.5 türkis,
1.0 rot (244). Prüffall `shortcut:dsp_output_peak_drives_the_meter_leds` (`case_meter_dsp` in `tools/emu/shortcut_cases.py`):
still, voll, wieder still; grün auf Hacktribe, rot und blau (12.11.).

## Echte Übersteuerung

Die Mischung rechnet mit Sättigung (`(S)`-Addition, Akkumulator auf 32 Bit begrenzt), ein zu lautes Signal bleibt bei
`±0x7FFFFFFF` stehen; der Betrag (`R | 1`, dann `ABS`) macht daraus `0x7FFFFFFF` (offline). Die CPU bekommt das volle
32-Bit-Wort. Hergeleitet: Ein Clip-Anzeiger kann `Spitzenwert == 0x7FFFFFFF` (oder knapp darunter) prüfen und sieht damit
eine echte Begrenzung am Ausgang, nicht eine Schätzung aus der Velocity. Grenzen: Sättigung innerhalb eines Parts oder
Effekts vor der Summe sieht dieser Wert nicht; eine Verstärkung danach (`+0x19C`, MASTER-Regler falls analog) auch nicht.

## Offen

- Gerätemessung: Velocity fest, Part-Level drehen, LEDs müssen folgen; Level fest, Velocity drehen, LEDs nur über die
  Lautstärke der Note.
- `0xFF9030EC` (`+0x48`, Kommando 1 im selben Takt) und `0xFF9030FC` (`+0x58`): Bedeutung nicht gelesen.
- Rot und blau: DSP-Seite nicht gelesen, CPU-Seite im Emulator gleich.
