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
