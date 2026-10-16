# FX-Einheiten am Display: kein Befund

Stand 2026-10-14. Emulator mit der eigenen `SYSTEM.VSB` (Sampler 2.02, Hacktribe)
und dem eigenen Flash, kein Gerät. Markierungen: **gemessen**, **hergeleitet**,
**offen**.

Die Tabellen (Spannen und Wahlnamen aus dem DSP-Strom) stehen in
[2026-10-14-fx-tabellen.md](2026-10-14-fx-tabellen.md), die diese erste Messung fortführt.
Dort steht auch, warum die CPU-Seite die Namenstabellen nie liest.

Frage: Zeigt die Firmware beim Bearbeiten von Insert- und Master-FX-Parametern
Werte in Einheiten (ms, Hz, %, dB, Notenwerte, Namen), die sich am Display
ablesen und in die Karte übernehmen lassen? Antwort: im Emulator nein. Es gibt
deshalb keine Tabelle und keinen Konverter, und die Karte bleibt unverändert.

## Ablauf

Gebootet wie in `2026-10-08-emulator-boot.md`, Flash-Dump vom 9.10.,
sechs Sekunden Gerätezeit bis zum Hauptbildschirm (Pattern 001, Part 1). Alles
über die Panel-Nachrichten aus `data/panel.mjs`, das Display aus dem
Framebuffer (`Machine.fb`) als Bild gelesen.

1. IFX TYPE um eins gedreht: das Fenster zeigt Nummer und Namen, hier
   "18 Delay 1/4".
2. IFX EDIT auf 100 und auf 200 (Knopfwert 0 bis 255) gestellt: das Fenster
   zeigt "IFX EDIT 50" und "IFX EDIT 100".
3. MASTER FX gedrückt, Touchpad auf drei Positionen berührt: der
   Hauptbildschirm bleibt unverändert.
4. Pattern-Menü bis MFX TYPE durchgeschaltet: nur der Typname.

Dazu ein Lesehaken (Unicorn `UC_HOOK_MEM_READ`) auf `0xC011F000` bis
`0xC0124000`. Dort liegen in der VSB die Namenstabellen der Effektparameter
(lange und kurze Namen wie "Dry:Wet" und "DRY:WET", Wahlnamen wie "Simple",
"Absolute", "KHZ"). Während eines breiten Durchlaufs: alle Tasten `0x00` bis
`0x21` (außer SHIFT und WRITE) mit Drehgeber, die ersten 20 IFX-Typen mit allen
elf Knöpfen auf zwei Werte, alle fünf Drehgeber je zehn Schritte. Zur Kontrolle,
dass der Haken arbeitet: derselbe Haken auf `0xC00A0000` bis `0xC00B0000`
(Namenslisten der Firmware, etwa der IFX-Typnamen) liefert beim Drehen von
IFX TYPE und den Menüseiten Treffer.

## Ergebnis

- **Gemessen:** IFX EDIT zeigt eine ganze Zahl im Maß 0 bis 127 (Knopfwert
  geteilt durch zwei), ohne Einheit und ohne Parameternamen, mit dem
  Delay-Typ ebenso wie sonst. Das sind dieselben Zahlen wie heute auf der
  Presets-Seite.
- **Gemessen:** Kein Bildschirm des Durchlaufs zeigt einen Effektparameter in
  einer Einheit. Beim Touchpad im Master-Modus bleibt der Hauptbildschirm unverändert (drei Positionen).
- **Gemessen:** Null Lesezugriffe auf die Namenstabellen der Effektparameter in
  allen Läufen. Die CPU-Seite der Firmware benutzt sie in der Oberfläche nicht.
- **Hergeleitet:** Wer die Einheiten kennt, ist der DSP. Seine Parameterwandler
  ([dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md), Abschnitt 2.2:
  Deskriptor je Effekttyp, Parametertabelle bei `+0x14`, Wandler) rechnen Rohwerte
  in Koeffizienten um; die CPU schickt den Rohwert (`2026-10-09-mfx-dsp.md`:
  Wert `Parameter << 8`). Der Emulator hat dafür nur ein Stand-in.
- **Offen:** Ob die Namenstabellen etwas für ein anderes Werkzeug (Korgs
  Editor) enthalten, das Einheiten nennt. Sie sind nur Text; ein Zahlenbezug
  fehlt dort.

## Wege, die bleiben

- **Aus Korgs Parameter Guide** (`korg-spec:<Abschnitt>`), sofern er die
  Wertebereiche der Effekte nennt. Nicht geprüft, ob er sie nennt; die
  Beleg-Form gibt es schon (Tonleitern, Motion-Ziele).
- **Aus den Wandlern im DSP-Abbild**, offline gelesen (`derived:`). Aufwändig,
  aber ohne Gerät; jede Tabelle müsste einzeln gegen den Code belegt werden.
- **Am Gerät mit Gehör oder Messung** (`measure:`), wie bei Cutoff, Hüllkurve
  und Glide. Das ist die einzige Art, die dem Namen "gemessen" gerecht wird.

Bis dahin zeigt die Presets-Seite Zahlen von 0 bis 127 und für Wahlfelder eine
Zahl, wie `data/map/fx-labels.mjs` es beschreibt.
