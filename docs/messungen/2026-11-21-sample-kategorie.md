# Sample-Kategorie in SAMPLE EDIT

21.11.2026, Firmware 2.02 rot (Korg) und Hacktribe, jeweils mit dem BLECH-Satz, **gemessen im Emulator** und **offline** aus
dem Code gelesen. Am Gerät nicht gemessen, der Gerätetest steht in [blech-datei.md](../geraetetests/blech-datei.md) Schritt 24.
Code: `tools/patch/script_sample_edit.s`, Fälle: `tools/emu/sample_category_cases.py`.

Markierungen: **gemessen** (Emulator), **offline** (Disassembly gelesen), **hergeleitet**.

## Was gebaut ist

SAMPLE EDIT hat eine Seite mehr: CATEGORY als Seite 3 von 11, hinter RENAME. Das Rad stellt die Kategorie des Samples, das
SAMPLE EDIT gerade bearbeitet, auf eine der 18 Kategorien der Firmware, mit den Texten der Firmware. Gespeichert wird wie
RENAME erst mit DATA UTILITY > EXPORT ALL SAMPLE. Die Seite ist eine Ebene des BLECH-Menüs (Ebene 9), die sich wie eine
Seite von SAMPLE EDIT zeigt; Korgs Seiten bleiben, wie sie sind. Mit EXIT beim Einschalten hat SAMPLE EDIT Korgs 10 Seiten.
Die blaue Electribe hat kein SAMPLE EDIT und bekommt nichts.

## Belegtabelle

| Aussage | Status | Beleg |
|---|---|---|
| SAMPLE EDIT ist Bildschirm 37 (Auswahl) und 38 (Seiten). Die Seite steht in `0xC0691278` (0 SELECT SAMPLE, 1 RENAME, 2 START POINT bis 9), das Byte `0xC0691280` lässt Bildschirm 38 auf dieser Seite wieder aufgehen wie nach RENAME | offline + gemessen | Konstruktor von Bildschirm 38, `case_page` |
| EDIT links und rechts auf den Seiten sind die Funktionen `0xC0069BB8` und `0xC0069C88` (Fächer 4 und 5 der Seitentabelle), beide beginnen mit `push {r4, r5, r6, lr}`; dort sitzen die zwei Haken | offline | Klassentabelle von Bildschirm 38 |
| Der Zähler rechts oben kommt aus `0xC008A83C` / `0xC008A8A8` (r1 Index, r2 Anzahl); der Haken macht aus 10 Seiten 11 und zählt ab CATEGORY eins weiter | offline + gemessen | `case_page`: 1/11, 2/11, 3/11 CATEGORY, 4/11 START POINT bis 11/11, Umlauf auf 1/11 |
| Beim Zurückspringen aus CATEGORY setzt der Konstruktor den Zähler, solange der Manager noch Bildschirm 45 (BLECH-Menü) meldet; ohne Sonderfall stand dann "/10" | gemessen | `case_page` (Schritt zurück auf RENAME), Haken `menu_counter_se` |
| EXIT auf jeder Seite geht wie bei Korg auf Bildschirm 37, ein neuer Eintritt beginnt bei 1/11 | gemessen | `case_page` (`exit`, `again`) |
| Kategorie steht im Namenseintrag `0xC047B08C + Slot * 32 + 0x10` (0 bis 17), das Byte danach bleibt 0 | offline + gemessen | `case_wheel`: Rad läuft durch die Firmware-Texte, hält bei 0 und 17, Byte `+0x11` bleibt 0 |
| Die Texte der 18 Kategorien liegen auf rot und Hacktribe an denselben Adressen; 17 heißt rot "[User]", Hacktribe "[Wave]" | offline + gemessen | Texttabelle von `0xC007881C`, `case_wheel` |
| EXPORT ALL SAMPLE schreibt die Kategorie nach `esli[18:20]` der `e2sSample.all` | gemessen | `case_export`: auf 7 gestellt, 7 geschrieben |
| SAMPLE EDIT lässt nur Plätze mit Sample zu (Test der Firmware `0xC007DEAC`, Schleife bei `0xC007DFA8`); ohne ein einziges Sample geht SAMPLE EDIT nicht auf | offline + gemessen | `case_no_sample`: Bildschirm bleibt 37 |
| CATEGORY nimmt denselben Test, dazu die Sperre für Oszillator-Plätze (Wave-Nummer bis 49): dort zeigt die Seite "---" und das Rad ändert nichts | gemessen | `case_no_sample` (roher Platz 0 zeigt "---", Wert unverändert) |
| Ein Werks-Platz mit eigenem Sample von der Karte ist bearbeitbar (rot Platz 101); Hacktribe lehnt Platz 100 ab, dort ist ein Oszillator | gemessen | `case_factory_slot` |
| Ein Sample mit Slice-Schritten (mono, eigenes Sample, Schrittzahl ungleich 0) springt in der Firmware von RENAME gleich auf LOOP START (Seite 5); CATEGORY folgt dem: EDIT rechts von CATEGORY geht auf LOOP START, EDIT links von LOOP START auf CATEGORY | offline + gemessen | Test `0xC007DE74` → `0xC004FF44`, `case_sliced` |
| Im Emulator haben die Werks-Samples im Flash leere META-Einträge; die Fälle nehmen deshalb Samples von der Karte | gemessen | `sample_category_cases.py` (Karte aus `tools/emu/sampleset.py`) |
| Ohne BLECH-Satz (Schalter `mc.KILL`) hat SAMPLE EDIT 10 Seiten und keinen Haken | gemessen | `case_without` |
| Code liegt im Bereich der Laufzeit (MORE3), RAM braucht die Seite keinen neuen: Ebene 9 nutzt die Felder des BLECH-Menüs | offline | `tools/patch/script_hooks.py`, `script_menu.s` |

Alle Fälle grün auf beiden Builds: `PYTHONPATH=tools/patch tools/emu/.venv/bin/python tools/emu/sample_category_cases.py --vsb <BLECH-VSB>`.

## Offen

- Am Gerät nicht gemessen. Gerätetest: [blech-datei.md](../geraetetests/blech-datei.md) Schritt 24.
- Kategorie-Sprung am OSC-Rad (SHIFT + OSC) gruppiert nur zusammenhängende Folgen gleicher Kategorie: ein umgestelltes Sample
  bildet eine eigene Folge, es springt nicht zu den anderen Kicks. **hergeleitet** aus der Schleife bei `0xC0040E0C`.
- Ob die Kategorie ohne EXPORT ALL SAMPLE beim Ausschalten verloren geht: **hergeleitet** aus der
  [Import-Messung](2026-11-16-import-werks-slots.md) (der Namenseintrag ist RAM), im Emulator nicht mit Neustart geprüft.

## Davor

Die Frage, ob Hacktribe eine `e2sSample.all` ohne Sample der Kategorie 17 ("Wave") liest:
[2026-11-17-sample-kategorie-wave.md](2026-11-17-sample-kategorie-wave.md). Ergebnis: ja, darum gibt es keine Sperre für das
letzte Wave-Sample.
