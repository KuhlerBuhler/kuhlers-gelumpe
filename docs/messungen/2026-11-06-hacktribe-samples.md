# Hacktribe und die Samples: was die Quellen sagen, was gemessen ist

Stand 2026-11-06. Anlass: Wer BLECHTRIBE installiert und im Patcher Hacktribe mit ankreuzt, meldet danach, die Samples seien
weg. Diese Seite trennt, was dazu **gemessen**, **hergeleitet** oder nur ein **Urteil** ist. Am Gerät wurde dafür nichts
ausgeführt; die Aussagen zu Hacktribe stammen aus dessen Doku, die zu BLECH aus dem Code und dem Emulator.

## Quellen

- Hacktribe, Wiki, Seite "How To" (am 2026-11-06 gelesen, `https://github.com/bangcorrupt/hacktribe/wiki/How-To`): Schritte
  "Install patched firmware", "Add factory samples from e2 sampler" und "Revert to factory firmware".
- Hacktribe, Wiki, Seite "FAQ": Importieren heißt, die `e2sSample.all` so zu bearbeiten, dass das erste Sample auf Platz 501
  liegt, abgelegt unter `KORG/hacktribe/Sample/e2sSample.all`.
- Eigene Messungen: [Sample-Fehler](2026-10-15-sample-fehler.md), [Sample-Speicher voll](2026-10-14-sample-speicher-voll.md),
  [Werks-Sample-Flash](2026-10-07-werks-sample-flash.md), [Ordner übernehmen](2026-10-19-ordner-uebernehmen.md),
  Format in [Sample-Datei](../hintergrund/sample-datei.md).

## Befunde

| Aussage | Stand | Beleg |
|---|---|---|
| Die Anleitung von Hacktribe verlangt beim Installieren: "Delete `e2sSample.all` from the `Sample` folder if it exists", danach `KORG/hacktribe/Sample` anlegen, alle Samples exportieren und vorhandene `e2sSample.all` so ändern, dass sie ab Platz 501 beginnen ("prevents memory errors") | Quelle gelesen, am Gerät nicht geprüft | Hacktribe, How To |
| Die Anleitung sagt außerdem, Oszillatoren und Samples liegen nach dem Patch auf anderen Plätzen als vorher | Quelle gelesen | Hacktribe, How To |
| Hacktribe überschreibt im Build die Namen der Werksplätze mit Oszillatornamen (Plätze 19 bis etwa 260 sind im Emulator belegt gesehen) | gemessen im Emulator | [Sample-Fehler](2026-10-15-sample-fehler.md), [Synth-Filter](2026-10-15-synth-filter.md) |
| Die Werks-Samples stehen nicht in `e2sSample.all`, sie liegen im Gerät: die Datei trägt nur die Plätze 501 bis 999 (nullbasiert 500 bis 998), Plätze 0 bis 499 sind Werksplätze | gemessen | [Sample-Datei](../hintergrund/sample-datei.md), [Werks-Sample-Flash](2026-10-07-werks-sample-flash.md) |
| Hacktribe schreibt "the original samples are still stored" im Gerät, sie kommen mit der Werks-Firmware zurück | Quelle gelesen, am Gerät nicht geprüft | Hacktribe, How To |
| Hacktribe liest und schreibt `KORG/hacktribe/`, Korgs Firmware `KORG/electribe sampler/` (blau `KORG/electribe/`), BLECHTRIBE `KORG/blechtribe/`. Wer von Korg auf Hacktribe wechselt, hat dort zuerst keine `Sample/e2sSample.all` | gemessen (Pfade der Firmware), hergeleitet (Folge für die Samples) | [Rettung](../rettung.md), [Patcher](../patcher.md) |
| BLECHTRIBE fragt beim ersten Start, ob der Ordner von Hacktribe oder Korgs `electribe sampler` nach `KORG/blechtribe` kopiert werden soll, wenn dort keine `Sample/e2sSample.all` liegt | gemessen im Emulator | [Ordner übernehmen](2026-10-19-ordner-uebernehmen.md) |
| Ein Update (SOFTWARE UPDATE) tauscht die Firmware und löscht keine Datei der Karte | hergeleitet: das Update liest nur `SYSTEM.VSB`, `f_unlink` gehört zu BLECHs eigenem Befehl FILE DELETE, den nur der Rechner schickt | [Sample-Datei](../hintergrund/sample-datei.md) |

## Was nicht belegt ist

- **Offen:** Ob Hacktribes Firmware die `e2sSample.all` beim ersten Start selbst löscht. In der Doku steht nur, dass der
  Nutzer sie löschen soll, in unserem Code und in den Emulator-Läufen löscht keiner der Builds eine Sample-Datei.
- **Offen:** Ob die Meldung "Plätze 0 bis 500 sind weg" (Aussage von Anwendern) die Werksplätze meint, die Hacktribe mit
  Oszillatoren belegt, oder Samples von der Karte. Die Werksplätze reichen nach unseren Messungen bis 499, die Nutzerplätze
  beginnen bei 501.
- **Offen:** Das Verhalten am Gerät, mit und ohne vorherige Sicherung.

## Urteil

- Die Warnung nennt beides: die Plätze 1 bis 500 gehören danach Hacktribe, und die `e2sSample.all` der Karte ist danach
  nicht mehr dort, wo das Gerät sie liest. Die Zahl 500 ist die Grenze der Werksplätze, nicht eine gemessene Löschung.
- Retten lässt sich nur, was als Datei vorliegt: die `e2sSample.all` aus einem der drei Ordner oder eine Kopie auf dem
  Rechner. Die App kann Samples eines Geräts mit Hacktribe oder Korgs Firmware nicht über USB lesen, die FILE-Befehle
  (`0x65`, `0x66`, `0x71` bis `0x73`) gibt es erst mit BLECH ([Sample-Datei](../hintergrund/sample-datei.md)).

## Sicherung durch die App: nicht gebaut

Machbar wäre nur die Karte: Die App kann den Kartenordner wählen lassen (`site/app/card-access.mjs`). Das reicht nicht:

- In der App liest `card_read` höchstens 4 MiB (`LIMIT` in `src-tauri/src/card.rs`), eine volle `e2sSample.all` hat 26,8 MB.
  Kopieren geht dort gar nicht, es gibt nur Lesen, Prüfen und Umbenennen.
- Im Browser ohne Schreibzugriff (Firefox, Safari) sieht die Seite nur `.VSB`-Dateien (`filesCard`).
- Ein Kopierbefehl in Rust wäre neue native Fläche (Pfade, Größen, Fehler) und am Gerät nicht prüfbar.

Darum steht vor dem Patchen eine klare Anweisung, welchen Ordner man selbst sichert, und der Patcher geht nicht weiter, bis der
Haken gesetzt ist.
