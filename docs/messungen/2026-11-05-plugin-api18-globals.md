# Plugin API 18: die Globals als Blätter von `korg.global`

Stand 5. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/global_cases.py` (läuft als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Plan Phase 6: kann ein Plugin jedes bekannte Global (die 19 Seiten von GLOBAL PARAMETERS) lesen und setzen, so dass der Wert ohne
Neustart wirkt, das Menü ihn zeigt, die Firmware ihn behält und ein ungültiger gespeicherter Wert beim Start repariert wird?

## Weg

Ein Blatt `korg.global.<name>` hat die Basis "global": das Global-Objekt steht hinter dem Zeiger bei `0xC0691324` (derselbe Wert wie
`[0xC033E6A0]`), sein Block ab +4; der Offset des Blatts ist der der [Gerätekarte](../geraetekarte.md) plus 4. Lesen liest das Byte. Setzen klemmt auf den Bereich der Karte (die Grenzen
des Menüs, [Messung vom 14. Oktober](2026-10-14-global-felder.md)), zählt eine Klemmung in `korg.system.repairs` und ruft dann die
Funktion der Firmware, die auch die Seite im Menü beim Drehen ruft: `(Global-Objekt, Wert, 1)`, die Adressen je Firmware aus den
[Live-Schreibwegen](2026-11-03-live-schreibwege.md) (`GLOBAL_SETTERS` in `tools/patch/script_hooks.py`, ein Test hält sie gleich
der Karte). Die Funktion schreibt das Byte und meldet es weiter, ein reines Schreiben des Bytes genügt bei fünf Globals, bei den
anderen nicht. Darum geht jedes Blatt durch die Funktion. Ist der Zeiger noch 0, lehnt der Aufruf ab.

## Ergebnisse

| Befund | Marker |
|---|---|
| Alle 19 Blätter nehmen ihr Maximum, ihr Minimum und einen Wert über dem Maximum (geklemmt, eine Klemmung gezählt): das Byte steht danach im Block, bei Hacktribe, rot und blau, keine Assertion | gemessen |
| Die gemeldeten Parameter der Klangerzeugung sind die der Messung vom 3. November: clockMode 0x31, midiChannel 0x32, powerSave 0x33, autoPowerOff 0x34, touchScaleRange 0x35, lcdContrast 0x36, tempoLock 0x37 (danach das Tempo neu), sendFilter 0x38, receiveFilter 0x39, syncResolution 0x3A, syncPolarity 0x2D, audioInThru 0x2E; die übrigen sieben melden nichts | gemessen |
| Zwillingsprobe je Blatt: die Seite im Menü um eins hochgedreht und derselbe Wert durch das Plugin gesetzt geben dieselben Meldungen an die Klangerzeugung und denselben Block (0x104 Byte); nach Verlassen und Wiederöffnen der Seite zeigt das Display dasselbe Bild (außer LCD CONTRAST, dessen Bild zweimal hintereinander nicht gleich ist) | gemessen |
| Das Menü zeichnet eine Seite erst beim Öffnen neu, nicht schon beim Setzen: mit dem Setzen allein ändert sich das Bild der offenen Seite nicht (nur LCD CONTRAST, weil sich das Display selbst ändert) | gemessen |
| TOUCH SCALE RANGE: das Touch-Scale-Objekt (`0xC06911E4`, +0x14) trägt nach dem Setzen den Wert, auf Hacktribe und rot; auf blau steht dort nichts (das Objekt liegt dort anders oder wird nicht kopiert, nicht weiter untersucht) | gemessen |
| Ein Plugin setzt und liest `korg.global.*` über den Übersetzer: Block und gelesene Werte stimmen, ein Wert aus einer Variablen über dem Bereich wird geklemmt und gezählt | gemessen |
| WRITE auf GLOBAL PARAMETERS mit allen Blättern auf Maximum, danach auf Minimum: der Block im Flash (`0x230000`) trägt die Werte, nach dem Neustart auf diesem Flash stehen sie im Block, das Menü zeigt dieselben Seiten wie vorher, keine Assertion, keine Reparatur | gemessen |
| Ausschalten (Batterie) ohne WRITE nach dem Setzen aller Blätter durch ein Plugin: der Block im Flash trägt danach die Werte aus dem RAM | gemessen |
| Beim Start ist das Global-Objekt schon geladen, wenn die Laufzeit die gespeicherten Werte prüft (`menu_arm_load`): ein Block mit ungültigen Bytes in jedem Feld wird auf die nächste Grenze geklemmt, jede Klemmung gezählt, die Seiten zeichnen, keine Assertion; ein folgendes Ausschalten speichert den reparierten Block | gemessen |
| Die Reparatur beim Start schreibt nur das Byte und ruft die Funktion der Firmware nicht: die Firmware hat den Wert da schon selbst gelesen | hergeleitet |
| TEMPO LOCK an im gespeicherten Block: der Emulator erreicht danach den Hauptbildschirm nicht, mit Korgs unverändertem Hacktribe-Abbild genauso. Die Restart- und Reparaturfälle lassen tempoLock deshalb aus; ob das am Emulator liegt, ist offen | gemessen (Emulator), Ursache offen |
| `clockMode` lehnt die Firmware ab, solange der Transport in Zustand 6 bis 9 ist; der Zustand wurde nicht herbeigeführt | offline gelesen, nicht gemessen |
| Der Setter von `triggerMode` legt das Trigger-Objekt neu an; im Emulator läuft er im Rahmen eines Plugins ohne Assertion und mit denselben Meldungen wie das Menü, ob der Pad-Weg danach unverändert ist, wurde nicht gesondert geprüft | gemessen (Aufruf), offen (Folge) |

## Grenzen

Die Grenzen sind die Menügrenzen der Karte. Die Slots 247 bis 249 des Blocks, die Patches von BLECH belegen, die Kennungen am
Anfang und Ende und die Bytes, die kein Menü ändert, stehen nicht im Baum. Alle 19 Blätter sind für Plugins schreibbar, weil
jedes im Emulator ohne Neustart wirkte. Am Gerät ist keines geprüft.

## Offen

- **Am Gerät**: keine Zeile.
- **Tempo Lock** im gespeicherten Block, siehe oben.
- **Nach dem Laden** durch Import einer Sicherung oder SysEx `0x51` prüft die Laufzeit die Globals nicht erneut, nur beim Start.
