# Barrierefreiheit

Ziel ist WCAG 2.2 Stufe AA. Dieses Dokument sagt, was automatisch geprüft wird, was dabei als erledigt gilt und was offen ist.
Marker: **gemessen** (ein Test belegt es), **hergeleitet** (aus dem Code gelesen), **offen** (nicht erfüllt oder nicht geprüft).

## Was geprüft wird

Die Tests liegen in `test/e2e/support/a11y-suite.mjs` (Läufe `test/e2e/a11y-1.e2e.mjs` und `a11y-2.e2e.mjs`, Start mit `npm run test:e2e`).

- **axe-core** über `@axe-core/playwright` mit den Regeln `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` und `wcag22aa`
  (`test/e2e/support/axe.mjs`). Ein Fund der Stufe **serious** oder **critical** lässt den Test scheitern. Gescannt werden:
  Start, Über-Seite, Emulator (aus, mit offenen Optionen, laufend), Startseite mit Firmware, Echtes Gerät, Patcher, Presets,
  Plugins mit laufendem Plugin und Editor, Modulationen und die versteckte Samples-Seite (`?labs`). **gemessen**
- **Gezielte Tests** für das, was axe nicht sieht (Namen siehe `a11y-suite.mjs`): die Tabliste der Seitenleiste enthält nur Tabs,
  die Statuszeile baut ihren Text nicht neu, wenn sich nichts ändert, das Display der Zeichnung hat einen Text für Screenreader,
  das Touchpad im Plugin-Laufbereich geht per Tastatur, die Schublade bei schmalem Fenster nimmt und gibt den Fokus,
  ein Dateiknopf mit verstecktem Eingabefeld zeigt den Fokus am Knopf, leuchtende Tasten halten den Kontrast
  (4,5:1 für die Beschriftung, 3:1 für das PLAY-Symbol) und ein fokussiertes Element liegt nie hinter der festen Navbar. **gemessen**
- **Nicht abgedeckt:** echte Screenreader (VoiceOver, NVDA), Canvas-Inhalte und Nicht-Text-Kontrast (axe prüft das nicht).

## Was gilt

- Fokus: alle Bereiche sind per Tastatur bedienbar, Dialoge sind natives `<dialog>` mit Fokus hinein und zurück. **gemessen** (Tests oben)
- Die Electribe-Zeichnung im Emulator: Regler sind `slider`, Drehgeber `spinbutton`, Schalter `switch`, Tasten tragen ihren
  LED-Zustand im Namen (zum Beispiel "Pad 1, leuchtet blau"); Pads setzen `aria-pressed` (`site/app/panel.mjs`). **hergeleitet**
- Der Plugin-Editor ist eine `textbox` mit `aria-multiline`, die Vervollständigung eine Liste mit `aria-activedescendant`, Fehler stehen
  zusätzlich als Liste unter dem Editor. **hergeleitet**
- Der Hintergrund (`site/design/bg.js`) zeichnet bei `prefers-reduced-motion: reduce` nur ein stehendes Bild. **hergeleitet**
- Seitentitel `lang="de"`, Landmarken `main`, `nav`, `aside`. **hergeleitet**

## Offen

| Wo | Was | Beleg |
|---|---|---|
| Seitentitel | `<title>` bleibt auf allen Bereichen "Kuhler's GELUMPE", beim Bereichswechsel wird er nicht gesetzt (WCAG 2.4.2) | **hergeleitet:** kein `document.title` in `site/app/`, `<title>` fest in `site/index.html` |
| Entscheidungsbox am Gerät | die Box mit `role="alert"` ("Sicherung zurückspielen", `site/app/device.mjs`) nimmt den Fokus nicht an (2.4.3) | **hergeleitet:** kein `focus()` dort |
| Plugin-Laufbereich | der Inhalt des Displays ist für Screenreader nicht lesbar, es gibt keine Live-Region für `korg.display.text` (1.1.1) | **hergeleitet:** keine `aria-live` in `site/app/sim-panel.mjs` |
| Zeichnung der Electribe | die Beschriftungen skalieren mit der Breite der Zeichnung (`cqw`, `site/app.css`) und wachsen daher nicht mit dem Browser-Zoom (1.4.4, 1.4.10) | **hergeleitet** aus dem CSS |
| Screenreader | nie mit VoiceOver oder NVDA getestet | **offen** |
| Drehgeber der Zeichnung | VALUE/PATTERN, SAMPLE/OSC, MOD TYPE, IFX TYPE und CUTOFF gehen nur per Ziehen, Mausrad oder Pfeiltasten, ein Klick tut nichts (2.5.7). Die Regler öffnen beim Klick ein Eingabefeld. Vorschlag: Klick öffnet ein Feld mit "-" und "+" (ein Bedienkonzept, braucht eine Entscheidung) | **hergeleitet:** `encoder` in `site/app/panel.mjs` hat kein `onClick`, `freeDial` schon |
| Rahmen von Eingaben und Knöpfen | `--color-border-strong` ist `rgba(255, 255, 255, .16)`, auf dem Seitengrund rund 1,52:1, die Füllung 1,19:1, Soll 3:1 (1.4.11). Gehört ins Design-System (`site/design/`) | **hergeleitet** aus `site/design/colors.min.css`; das Verhältnis gerechnet |
| Kleine Tasten der Zeichnung | 30 Tasten waren bei 1280 px kleiner als 24 x 24 px (zum Beispiel 36 x 18, die Bar-Tasten 20 x 29, 2.5.8). Die Ausnahme "wesentlich" greift, weil die Tasten die Lage am Gerät nachbilden, ist aber angreifbar | **gemessen** mit `getBoundingClientRect`, auf dem heutigen Stand nicht neu gemessen |
| Tab-Reihenfolge der Zeichnung | rund 68 Tab-Stopps in DOM-Reihenfolge, nicht in der Reihenfolge am Gerät, und kein Sprung am Block vorbei (2.4.3, 2.4.1). Vorschlag: ein Tab-Stopp je Gruppe mit Pfeiltasten innen, dazu ein Sprunglink | **gemessen** (Tab-Durchlauf), kein Sprunglink in `site/index.html` (**hergeleitet**) |
| Überschriften | eine `h1` haben nur Start, BLECHTRIBE-Übersicht, Doom, Über und Unterstützen, die anderen Bereiche nicht (1.3.1, 2.4.6; axe `page-has-heading-one`, Schwere moderate) | **hergeleitet** aus `site/index.html` |
| Meldungen des Linters | Englisch ("the preset has no name ...") ohne `lang="en"` (3.1.2) | **gemessen** (ARIA-Snapshot Presets), nicht neu geprüft |
| Sterne im Hintergrund | einzelne Sterne hinter Text senken den Kontrast punktuell auf 1,8 bis 2,4:1, sonst über 5:1 (1.4.3) | **gemessen** per Pixelprobe, nur Näherung |
| Werte der Regler | Regler der Zeichnung setzen `aria-valuenow`, aber kein `aria-valuetext`; Drehgeber sagen nur "endlos, Pfeiltasten drehen" ohne Zahl (4.1.2) | **hergeleitet** aus `site/app/panel.mjs` |
| Links in neues Fenster | Links mit `target="_blank"` (zum Beispiel Spenden, Issue, Lizenzen) sagen nicht, dass sie ein neues Fenster öffnen (2.4.4) | **hergeleitet** aus `site/index.html` |
| Osterei am Gerät | die Show auf der Seite VERSION blinkt mit 2,5 Blitzen je Sekunde, unter der Grenze von 3 (2.3.1); am Gerät nicht geprüft, Einzelheiten in [Firmware-Extras](hintergrund/firmware-extras.md#lichtgrenze) | **gemessen** im Emulator |

Die Funde der ersten Prüfung stehen in der Git-Historie: `git show origin/develop:docs/barrierefreiheit.md`.
