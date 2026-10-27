# Barrierefreiheit

Prüfung der Seite gegen WCAG 2.2 Stufe AA, Stand 2026-10-14, Commit-Stand `a11y/audit`. Geprüft
wurden alle Bereiche: Start, Emulator mit der Electribe-Zeichnung und den Optionen in der
Seitenleiste, Echtes Gerät (nicht verbunden), Patcher, Presets, Plugins mit Editor, Laufbereich
und Konsole. Marker: **gemessen** (Befehl oder Test belegt es), **hergeleitet** (aus Code oder
Token-Werten gerechnet), **offen** (nicht geprüft).

## Wie geprüft wurde

- **axe-core** über `@axe-core/playwright` (neue Dev-Abhängigkeit, nur für die Tests), Regeln
  `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`. `test/e2e/support/a11y-suite.mjs` scannt jeden Bereich
  und schlägt bei **serious** und **critical** fehl, Hilfsfunktion `test/e2e/support/axe.mjs`.
- **Per Hand mit Playwright** gegen den Dienst-Ersatz: Tab-Durchlauf je Bereich (Fokusreihenfolge,
  Fokusanzeige per Pixelvergleich fokussiert gegen unfokussiert), ARIA-Snapshot je Bereich, Überlauf
  bei 1280, 640, 400 und 320 px Breite, Zielgrößen, Textabstände (WCAG 1.4.12), `prefers-reduced-motion`,
  Dialoge, Live-Regionen mit `MutationObserver`.
- **Nicht geprüft (offen):** echte Screenreader (VoiceOver, NVDA), der Zustand "Gerät verbunden"
  mit axe, die Modulationsseite und der Hintergrund-Canvas (andere Branches, siehe unten).
  axe prüft keine Canvas-Inhalte und keinen Nicht-Text-Kontrast, das steht darum als Handprüfung drin.

## Gefunden und behoben

Je Fund ein Test in `test/e2e/support/a11y-suite.mjs` (oder `nav.e2e.mjs`).

| # | WCAG | Schwere | Wo | Beleg | Fix |
|---|---|---|---|---|---|
| 1 | 1.3.1, 4.1.2 | critical | Seitenleiste: die Optionen standen im `role=tablist` | axe `aria-required-children`, gemessen | Optionen als Geschwister der Tabliste, Reihenfolge per `order` (`site/app/subnav.mjs`, `site/app.css`) |
| 2 | 1.4.3, 1.4.11 | high | leuchtende Tasten: Beschriftung weiß auf Rot 3,85:1, PLAY-Symbol auf Blau 2,29:1 | axe `color-contrast`, gerechnet aus den Tokens | Füllanteil der LED-Farbe bei voller Helligkeit 90 auf 75 Prozent (Rot) und 60 Prozent (Blau) |
| 3 | 4.1.3 | high | Statuszeile des Emulators und Bildschirmzeile in der Seitenleiste bauten ihren Text jede Sekunde neu | der Dienst sendet jede Sekunde ein Status-Ereignis (`tools/emu/server.py`, `set_status`); `MutationObserver`-Test, gemessen | Text wird nur geschrieben, wenn er sich ändert (`emulator.mjs`, `sidebar.mjs`) |
| 4 | 2.1.1 | high | Touchpad im Laufbereich der Plugins reagierte nur auf Zeiger | Code (`sim-panel.mjs`), Test | Leertaste oder Enter hält, Pfeiltasten bewegen, wie auf der Zeichnung des Emulators |
| 5 | 2.4.7 | high | "Datei öffnen" (Plugins) und "Andere Datei" nehmen den Fokus in ein verstecktes Eingabefeld, der Knopf zeigt nichts | Pixelvergleich, `getComputedStyle`, gemessen | Fokusrahmen am Knopf (`site/app.css`) |
| 6 | 2.4.11 | high | der fixe Kopf verdeckt fokussierte Elemente: Fokus scrollt unter die Navbar, die Beispiel-Plugin-Liste klebt bei 1 rem darunter | Test mit `elementFromPoint`, gemessen | `scroll-padding-top` und eigener `top` für die beiden Seitenspalten |
| 7 | 2.4.3 | high | schmale Fenster und Zoom 200 Prozent (unter 60 rem): die Seitenleiste ist eine Schublade vor dem Inhalt, Tab lief nach "Menü" an ihr vorbei | Test, gemessen | Fokus geht beim Öffnen in die Schublade, Escape gibt ihn zurück |
| 8 | 1.1.1 | high | Display der Electribe hatte nur den festen Namen "Display der emulierten Electribe" | Code, ARIA-Snapshot | `aria-describedby` zeigt auf die Bildschirmzeile der Seitenleiste ("Was das Gerät gerade zeigt"). Das ist ein Teilersatz: Bildschirmname, Seite, Fenster, Part, nicht der Text im Display (siehe offene Punkte) |
| 9 | 3.1.2 | low | Titel "Patch your Firmware" ist Englisch, die Seite Deutsch | ARIA-Snapshot | `lang="en"` am Titel |
| 26 | 2.1.1, 1.4.3 | high | Plugin-Editor (CodeMirror): der Textbereich scrollt, hat aber keinen Tab-Stopp (axe `scrollable-region-focusable`), und die gewählte Zeile der Vervollständigung hatte 1,22:1 | axe, gemessen | `tabindex="0"` am Eingabebereich, Zeile der Liste mit `--color-surface-item-bright` (`site/app/script-editor.mjs`, `site/app.css`); der Test öffnet Liste, Hinweis und Fehlerunterstreichung |

## Offen, braucht eine Entscheidung

Alles ab hier ist nicht angefasst, weil es das Aussehen oder das Bedienkonzept ändert oder im
Design-System (`site/design/`, eine feste Kopie) liegt.

| # | WCAG | Schwere | Wo | Beleg | Vorschlag |
|---|---|---|---|---|---|
| 10 | 1.4.4, 1.4.10 | high | Beschriftungen der Zeichnung sind 6,1 px (62 Stück) und 5,5 px (4 Stück) groß und wachsen mit Browser-Zoom nicht: die Schrift hängt an der Breite der Zeichnung (`cqw`), und die schrumpft beim Zoomen mit | `getComputedStyle` bei 1280 px, Zeichnung 768 px breit, gemessen | `min-width` an `.cee-e2-body` (etwa 45 rem), die Zeichnung scrollt dann waagerecht in `.cee-e2-viewport`, das ist für ein Diagramm erlaubt (1.4.10). Auf dem Handy wird die Zeichnung dadurch größer statt immer kleiner. Das Aussehen auf kleinen Schirmen ändert sich |
| 11 | 2.5.7 | high | die Drehgeber VALUE/PATTERN, SAMPLE/OSC, MOD. TYPE, IFX TYPE und CUTOFF gehen nur per Ziehen, Mausrad oder Pfeiltasten. Die Regler öffnen beim Klick ein Eingabefeld, die Drehgeber nicht | Code (`panel.mjs`, `encoder`, `cutoff`) | Klick auf einen Drehgeber öffnet ein kleines Feld mit "-" und "+", oder obere und untere Hälfte klicken. Das ist ein Bedienkonzept |
| 12 | 1.4.11 | high | Rahmen von Eingaben, Auswahlfeldern und Knöpfen sind `rgba(255,255,255,.16)` auf dem Seitengrund, das sind 1,52:1, die Füllung 1,19:1 (Soll 3:1) | gerechnet aus `colors.min.css`, gemessen an `#cee-script-name` | gehört ins Design-System (Rahmen heller, Token `--color-border-strong`), hier nicht änderbar |
| 13 | 2.5.8 | medium | 30 Tasten der Zeichnung sind bei 1280 px kleiner als 24 mal 24 px (zum Beispiel 36 mal 18, die Bar-Tasten 20 mal 29). Ausnahme "wesentlich" greift, weil die Tasten die Lage am Gerät nachbilden, ist aber angreifbar | gemessen (`getBoundingClientRect`) | ein größerer Mindestmaßstab (siehe 10) behebt es zum Teil. Alternativ eine Liste der Bedienelemente als zweite Bedienung |
| 14 | 2.4.3, 2.4.1 | medium | die Zeichnung hat rund 68 Tab-Stopps in DOM-Reihenfolge, nicht in der Reihenfolge des Gerätes (Encoder, Regler, Tasten rechts, dann Transport links), und keinen Sprung am Block vorbei | Tab-Durchlauf, gemessen | je Gruppe (Sample, Filter, Modulation, Insert FX, Transport, Pads) ein Tab-Stopp mit Pfeiltasten innen (Toolbar-Muster), und ein Link "Zu: Was das Gerät zeigt" |
| 15 | 1.1.1 | medium | im Plugin-Laufbereich ist der Inhalt des Displays (zum Beispiel der Spielstand bei Snake) für Screenreader nicht lesbar | Code | die Plugin-Laufzeit hat Text-Aufrufe (`korg.display.text`), die sich zusätzlich als Text in eine Live-Region schreiben ließen. Entscheidung, wie viel gesagt werden soll |
| 16 | 1.3.1, 2.4.6 | medium | außer Start und Patcher hat kein Bereich eine `h1`; Presets beginnt bei `h3`, die Entscheidungsbox des Geräts hat `h3` ohne `h2` | axe `page-has-heading-one` (moderate), Überschriftenliste | die Navbar-Überschrift als `h1` für alle Bereiche, auf der Startseite die vorhandene behalten (die Navbar-Zeile zeigt dort "Start") |
| 17 | 3.1.2 | low | Meldungen des Linters sind Englisch ("the preset has no name ...") und stehen ohne `lang` in der Seite | ARIA-Snapshot Presets | `lang="en"` an der Meldung oder die Texte übersetzen. Texte kommen aus `src/`, dort gilt Englisch für Code |
| 18 | 2.2.2 | low | der Sternenhimmel im Hintergrund bewegt sich ohne Pausenknopf. Er hält bei `prefers-reduced-motion` an (`site/design/bg.js`), das gilt üblicherweise als Mechanismus | Code | nur gemeldet, gehört zu `feat/blech-background` |
| 19 | 1.4.3 | low | einzelne Sterne hinter Text senken den Kontrast punktuell. Pixelmessung: kleinster Wert 1,8 bis 2,4:1 unter einem Stern, sonst über 5:1 | Pixelprobe, nur Näherung | nur gemeldet, gehört zu `feat/blech-background`: Sterne unter Textflächen weglassen oder dämpfen |
| 20 | 4.1.2 | low | Regler der Zeichnung setzen `aria-valuenow`, aber keinen `aria-valuetext`; die Drehgeber haben `aria-valuetext="endlos, Pfeiltasten drehen"` ohne Zahl | ARIA-Snapshot | Wert mit Einheit sagen, wenn die Seite ihn kennt |
| 21 | 4.1.2 | low | Pads zeigen "gedrückt" nur, wenn sie rot leuchten, kein `aria-pressed` | Code (`paintPad`) | `aria-pressed` setzen |
| 22 | 2.4.2 | low | der Seitentitel bleibt auf allen Bereichen "Kuhler's GELUMPE" | Code | beim Wechsel `Bereich | Kuhler's GELUMPE` setzen |
| 23 | 2.3.3 (AAA) | low | unter `prefers-reduced-motion: reduce` laufen Übergänge von 0,15 bis 0,22 s weiter, auch das Drehen des Pfeils am Moduswahl-Knopf | `getComputedStyle` mit emuliertem Medium, gemessen | Übergang in `@media (prefers-reduced-motion: no-preference)` stellen |
| 24 | 2.4.4 | low | Links mit `target="_blank"` (Patcher: hacktribe-2.patch) sagen nicht, dass sie ein neues Fenster öffnen | Code | Hinweis im Linktext |
| 25 | 2.4.3 | low | die Entscheidungsbox des Geräts (`role=alert` mit "Sicherung zurückspielen") nimmt den Fokus nicht an | Code (`device.mjs`) | beim Erscheinen den ersten Knopf fokussieren |

## Was in Ordnung ist

- **Sprache und Landmarken:** `lang="de"`, `main`, `nav`, `aside`, Kopfzeile (ARIA-Snapshot).
- **Plugin-Editor:** Eingabebereich mit Rolle `textbox`, Beschriftung „Plugin-Code“ und `aria-multiline`; Tab verlässt ihn (kein `indentWithTab`), die Vervollständigung ist eine Liste mit `aria-activedescendant`. Hover und Parameterhinweis sind Zugaben für die Maus, derselbe Text steht in der Vervollständigung, und die Fehler stehen zusätzlich als Liste unter dem Editor.
- **Tastatur:** Tabs, Moduswahl-Menü, Schublade, Dialoge (natives `<dialog>`, Fokus rein und zurück, gemessen), Pads, Tasten (Enter und Leertaste halten), Regler (Pfeile, Bild auf und ab, Pos1, Ende, Enter öffnet das Eingabefeld), Drehgeber (Pfeile), Touchpad der Zeichnung (Leertaste halten plus Pfeile). Keine Tastaturfalle gefunden.
- **Fokusanzeige:** auf allen 68 Elementen der Zeichnung und in allen anderen Bereichen sichtbar (Pixelvergleich), Rahmen `#88c0d0` auf dunkel.
- **Namen und Rollen:** Regler sind `slider` mit `aria-valuenow`, Drehgeber `spinbutton`, Schalter `switch`, Tabs `tab` mit `aria-selected`, Moduswahl `menuitemradio`. LED-Zustand steht im Namen ("Pad 1, leuchtet blau").
- **Formulare:** alle Felder haben ein Label (axe `label` ohne Fund), Dateiauswahlen sind Labels um das Eingabefeld, Fehler laufen über `role=status` oder `role=alert`.
- **Live-Regionen:** Statuszeile des Emulators, Navbar-Zustand, Konsole (`role=log`), Plugin-Meldungen.
- **Kontrast Text:** `--color-text-muted` ist 0,55 Weiß auf `#0a0a0b`, gerechnet etwa 6:1.
- **Reflow:** bei 1280, 640, 400 und 320 px kein Seiten-Scroll (gemessen, alle Bereiche); die Zeichnung scrollt in sich.
- **Textabstände (1.4.12):** mit erzwungenen Abständen kein abgeschnittener Text (gemessen).
- **Zeiger:** Pads lösen beim Drücken aus, das ist wesentlich für ein Instrument (2.5.2).
