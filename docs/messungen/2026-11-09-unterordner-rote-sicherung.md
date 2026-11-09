# Fehlende Unterordner in KORG/blechtribe, rote fragt auch nach der Pattern-Sicherung (9.11.)

Stand 2026-11-09. Alles im Emulator mit Korgs roter 2.02 (`1d0f0689`), Hacktribe (`7cb4825c`) und Korgs blauer 2.02
(`41fc5f1c`), die Dateien außerhalb des Repositorys. **Am Gerät nichts.** Vorher:
[Ordner beim ersten Start, Sicherung der blauen](2026-11-09-blechtribe-ordner.md).

Marker: **gemessen** (ausgeführt), **hergeleitet** (aus Code oder Doku geschlossen).

Zwei Wünsche vom Gerät: viele legen `KORG/blechtribe` schon vor der Firmware an, von Hand, weil sie denken, er wird
gebraucht. Dann fehlten bisher alle Unterordner, denn ein vorhandener Ordner blieb, wie er war. Und die rote soll wie die
blaue auch fragen, wenn im alten Ordner nur eine Pattern-Sicherung liegt, und die mitkopieren.

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Rot und Hacktribe schreiben EXPORT ALL PATTERN als `electribe_sampler_allpattern.e2sallpat` direkt in den Kartenordner (`KORG/hacktribe/`, unter BLECH `KORG/blechtribe/`) | gemessen (Hacktribe), hergeleitet (Korg rot: gleicher Dateiname im Abbild, Ordner `KORG/electribe sampler/`) | [virtuelle SD-Karte](../hintergrund/virtuelle-sd.md), Abschnitte 8 und 9 |
| Vor dem Sample-Lader ist für die Sicherung keine Zeit: mit `f_open` auf die Sicherung in `KORG/blechtribe` dort kam der Lader 3 ms (Sicherung da) bis 6.4 ms (nicht da, dann noch die zwei alten Ordner) später als mit develop; mit dem Lesen aller Einträge von `KORG/blechtribe` dort 7 ms später | gemessen | `early_run` aus `menu_cases.py` mit und ohne Haken, Karte mit den sechs Unterordnern, je Variante gebaut |
| Ein `f_mkdir` vor dem Sample-Lader kostet etwa 16 ms | gemessen | Testkarte von `early_look_cases` (nur `Sample`), fünf fehlende Ordner vor dem Lader angelegt: Lader 431 statt 351 ms (Hacktribe) |
| Mit allen sechs Unterordnern auf der Karte kommt der Sample-Lader schon mit dem Stand von develop 14 ms später (statt 12 ms mit der Testkarte, die nur `Sample` hat) | gemessen | `early_run`, develop (`2a314844`) gegen die Kopie ohne Haken: 364.8 statt 350.8 ms |

## Der Patch

- **Unterordner:** `mg_folders` öffnet `KORG/blechtribe` einmal und liest jeden Eintrag. Fehlt der Ordner, legt es `KORG`,
  `KORG/blechtribe` und alle Ordner der Liste an. Ist er da, legt es nur die Ordner der Liste an, die fehlen; der Vergleich
  ist Groß und klein egal (`gif` zählt als `Gif`), was im Ordner liegt, bleibt. Mit EXIT beim Einschalten nichts.
- **Wann:** auf der blauen wie bisher in `migrate_start` im Kartenhaken. Auf rot und Hacktribe im ersten Rahmen auf dem
  Hauptbildschirm (`mg_frame_later`, UI-Task, wie das Schreiben der Einstellungsdatei): vor dem Lader ist für das Lesen
  aller Einträge und für die `f_mkdir` keine Zeit. `migrate_start` setzt dafür `MG_LATER`, der Kartenhaken schaltet es
  scharf, der Rahmenhaken wartet auf den Hauptbildschirm (`SCREEN_MANAGER` + `0x2c` = 1, wie `sc_held`).
- **Pattern-Sicherung auf der roten:** im Kartenhaken nach dem Sample-Lader, vor den Plugins (`migrate_folders`). Fragt
  der Start vor dem Lader schon (Samples), fragt er nicht ein zweites Mal. Gesucht wird der Name, den die Firmware der
  Sicherung gibt, ein `f_open` je Ordner: erst `KORG/hacktribe` und `KORG/electribe sampler`, `KORG/blechtribe` nur, wenn
  einer der beiden sie hat (ein fehlender Name kostet am meisten). Eine umbenannte Sicherung findet sie nicht. Die Frage und
  die Kopie sind dieselben wie für die Samples, die Kopie nimmt den ganzen alten Ordner, vorhandene Dateien bleiben.
- **Vor dem Lader** prüft die rote nur noch die Samples, wie bisher, aber ohne das `f_opendir` auf `KORG/blechtribe`.

## Emulator

`tools/emu/migrate_cases.py`:

| Firmware | Ergebnis |
|---|---|
| Korg rot + `blech.json` | 21 von 21, neu: `KORG/blechtribe` nur mit einer Datei bekommt alle sechs Ordner; mit `Plugin` und `gif` (klein) bekommt es die anderen vier, eigene Dateien bleiben; EXIT beim Einschalten: keiner; nur die Sicherung in `KORG/hacktribe`: Frage, MENU kopiert sie; Samples und Sicherung: beide kopiert; `KORG/blechtribe` mit Samples ohne Sicherung, `KORG/electribe sampler` mit beiden: Frage, die Sicherung kommt, die eigenen Samples bleiben; Sicherung schon in `KORG/blechtribe` (Name groß geschrieben): keine Frage; EXIT auf die Sample-Frage: keine zweite Frage; umbenannte `.e2sallpat`, Punktdatei, `.e2allpat`: keine Frage |
| Hacktribe + `blech.json` | 21 von 21, dieselben Fälle |
| Korg blau + `blech-synth.json` | 17 von 17, neu: Ordner nur mit einer Datei bekommt `Plugin`, `Gif`, `System`; mit `Plugin` und `gif` nur `System` dazu; EXIT beim Einschalten: keiner |

`menu_cases.early_look_cases` (Testkarte mit nur `Sample`), Zeit bis zum Sample-Lader und bis zum Hauptbildschirm, Kopie
mit Haken gegen Kopie ohne (Grenze je 15 ms):

| Firmware | Lader develop | Lader jetzt | Hauptbildschirm jetzt |
|---|---|---|---|
| Hacktribe | +12.1 ms | +10.2 ms | +9.5 ms |
| Korg rot | +12.1 ms | +10.2 ms | +8.4 ms |

Dieselbe Messung mit einer Karte nach dem ersten Start (alle sechs Unterordner, `probe`-Skript außerhalb des Repositorys):

| Karte | Lader develop | Lader jetzt | Hauptbildschirm develop | Hauptbildschirm jetzt |
|---|---|---|---|---|
| Unterordner, keine Sicherung | +14.0 ms | +12.1 ms | +3.4 bis +5.0 ms | +10.3 bis +11.2 ms |
| dazu Sicherung in `KORG/blechtribe` | +14.0 ms | +12.1 ms | wie oben | +6.0 bis +8.9 ms |
| dazu Sicherung auch im alten `KORG/hacktribe` | +14.0 ms | +12.1 ms | wie oben | +12.1 bis +12.9 ms |

Der Hauptbildschirm kommt bis 13 ms später als ohne Haken, das sind die `f_open` im Kartenhaken. Vorher versucht und
verworfen: alles vor dem Lader (Lader +23 ms statt +16 ms), dort mit festem Namen (+22 ms mit Sicherung im alten Ordner), im
Kartenhaken zuerst `KORG/blechtribe` fragen (Hauptbildschirm +16.3 ms ohne Sicherung, Hacktribe).

`check.py --quick` mit den drei Sätzen: siehe PR.

## Offen, für den Gerätetest

- Ob die Ordner am Gerät im ersten Rahmen nach dem Start angelegt werden (Karte mit leerem `KORG/blechtribe`).
- Ob die Frage nach der Sicherung am Gerät nach dem Laden der Samples kommt und die Kopie dort durchläuft.
