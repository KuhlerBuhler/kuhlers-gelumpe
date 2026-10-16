# Design System

Verbindliche Referenz für das visuelle Design. Diese Datei **dokumentiert** die Tokens,
die **Quelle der Wahrheit ist der CSS-Code**:

- `colors.min.css` -- semantische Farb-Tokens (`--color-*`)
- `root.min.css` -- Aliase, Maße, Typo, Standard-Komponenten
- `COMPONENTS.md` -- Komponenten-Nutzung (Buttons, Cards, Forms, …)

Regel: neue Werte (Farbe, Radius, Spacing, Font) müssen auf ein hier/dort definiertes
Token zurückgehen. Kein Inline-Literal wie `#cbd5e1` oder `14px`, wenn ein Token existiert.
Fehlt ein Token, erst in `colors.min.css`/`root.min.css` anlegen, dann referenzieren.

## Ein Farbschema, keine Themes

Es gibt **ein** Schema für die ganze App. Die Theme-Auswahl (Obsidian, Titanium, Emerald,
Crimson, Nord, Gold/Onyx, Solarized, Synthwave; `theme.js`, `:root[data-theme=…]`) entfällt.
Das Schema vereint drei der alten Themes:

| Herkunft | Was übernommen wird |
|----------|---------------------|
| Gold/Onyx | Hintergrund (fast reines Schwarz) |
| Titanium | Erfolgs-/Fehlerfarben, hellere Flächen und Rahmen |
| Nord | Kontrast: kühles Eisblau als Akzent, höhere Textkontraste, Fokusring |

Gold ist bewusst **nur Detail** (Favoriten-Stern), sonst wirkt das Schema zu gelb.

## Farb-Tokens (`colors.min.css`)

### Hintergründe
| Token | Wert |
|-------|------|
| `--color-bg-page` | `#0a0a0b` (Seiten-Hintergrund) |
| `--color-bg-page-alt` | `#0e0e10` (Navbar) |
| `--color-bg-page-deep` | `#050505` |
| `--color-bg-popover` | `#121212f1` |

### Flächen / Surfaces
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-surface-panel` | `rgba(255,255,255,.06)` | Kacheln, Karten, Suche |
| `--color-surface-panel-alt` | `rgba(255,255,255,.04)` | kleine Kacheln, Listen-Container |
| `--color-surface-item` | `rgba(255,255,255,.14)` | |
| `--color-surface-item-muted` | `rgba(255,255,255,.08)` | Avatar, Icon-Hintergrund |
| `--color-surface-item-strong` | `rgba(255,255,255,.17)` | |
| `--color-surface-item-bright` | `rgba(255,255,255,.20)` | |

### Rahmen
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-border-strong` | `rgba(255,255,255,.16)` | Standard-Border von Kacheln und Karten |
| `--color-border-muted` | `rgba(255,255,255,.10)` | Navbar-Linie, Achsen, Trenner |
| `--color-border-faint` | `rgba(255,255,255,.08)` | Listen-Trenner mobil |
| `--color-border-dashed` | `rgba(255,255,255,.22)` | freie Favoriten-Plätze (gestrichelt) |

### Text
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-text-primary` | `#f4f4f5` | Primärtext |
| `--color-text-secondary` | `rgba(255,255,255,.72)` | Fließtext, Beschreibungen |
| `--color-text-muted` | `rgba(255,255,255,.55)` | Meta, Achsen, Ränge (bleibt über 4.5:1) |

### Akzent (Eis-Platin)
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-accent-primary` | `#9ec3d1` | Logo, App-Icons, Balken, aktiver Filter, Play-Button |
| `--color-accent-primary-soft` | `#cfe1e8` | Link-Hover |
| `--color-accent-primary-contrast` | `#0b1417` | Text auf Akzent-Fläche (aktiver Filter-Chip) |
| `--color-accent-secondary` | `#c4c8cf` | Titan-Silber: zweite Diagramm-Serie |
| `--color-focus-ring` | `#88c0d0` | Fokusring, 2px, 2px Abstand |

### Favorit
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-favorite` | `#c9b27e` | **Nur** gefüllter Favoriten-Stern |

### Status
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-status-ok` | `#22c55e` | Statuspunkt "läuft", gültiges Zertifikat |
| `--color-status-ok-text` | `#4ade80` | Text "Gestartet", "Bewegung" |
| `--color-status-error` | `#ef4444` | Statuspunkt "offline" |
| `--color-status-error-text` | `#fca5a5` | Text "offline" |

Status nie nur über die Farbe zeigen: immer Punkt **und** Wort ("läuft", "offline").

### Daten

| Token | Wert | Zweck |
|---|---|---|
| `--chart-1..4` | Eis, Titan, Grün, Gold | Serienfarben (`chartSeries`) |
| `--data-seq-1..5` | `#2f5d7c` bis `#d9694f` | sequentielle Skala kalt nach warm (Heatmap) |
| `--data-empty` | `rgba(255,255,255,.05)` | Zelle ohne Wert |

### Buttons (Glass)
Buttons bleiben transparent, die Border zeigt die Semantik: `btn primary` = grün,
`btn danger` = rot, default = neutral. Ausnahme Schnellbefehl-Play: Border und Icon in
`--color-accent-primary`.

## Typografie

| Rolle | Schrift | Einsatz |
|-------|---------|---------|
| Display | **Sora** 700 | Überschriften h1/h2, Logo-Schriftzug, Avatar-Initiale |
| Text | **IBM Plex Sans** 400/500/600 | alles andere |
| Zahlen | **IBM Plex Mono** 500 | Uhrzeit, Zeitangaben, Achsen, Ränge, Messwerte |

Selbst gehostet unter `fonts/` (woff2, `latin` + `latin-ext`, SIL Open Font License). Kein Google-Fonts-Request, damit keine Besucher-IP an Dritte geht. Inter entfällt.

| Element | Desktop | Mobil |
|---------|---------|-------|
| h1 (Begrüßung) | 68px / 700, `letter-spacing: -1.5px` | 40px |
| h2 (Sektion) | 26px / 700 | 20px |
| h3 (Karte) | 18px / 600 | 16px |
| Body | 16px | 15px |
| klein / Meta | 14px, 13px, 12px | 13px, 12px |

## Hintergrund

Fest, ohne Auswahl im Profilmenü:
- **Alle Seiten:** BLECH-Look wie das README-Banner (`bg.js`): ruhiges Sternenfeld auf einem festen 1-Bit-Zellraster (quadratische Pixel, kein Anti-Aliasing, Zellgröße und Deckkraft über die `--cee-bg-*`-Tokens in `app.css`), Dither-Bänder an den Seiten und schwach gedithertes Treiben dazwischen, leichte Parallaxe zur Maus.
- **Easter Egg:** selten blinzeln die Blech-Augen aus dem Dither hoch (nur ab 640px Breite). Aus mit `data-eyes="off"` am Canvas oder `?bg-eyes=off`, sofort zum Testen mit `?bg-eyes=now`.
- **Variante:** `?bg=bands` lässt das Treiben weg, `?bg=off` blendet den Hintergrund aus.
- **Bewegung:** 12 Bilder pro Sekunde, Pause bei verstecktem Tab, bei `prefers-reduced-motion` ein statisches Bild ohne Augen.

## Komponenten der Startseite

Das Prinzip ist **Selbstähnlichkeit**: dieselbe App-Kachel kommt in drei Größen vor.

| Komponente | Maße | Radius | Aufbau |
|------------|------|--------|--------|
| Sektionskopf | | | nur `h2`, **kein** Hinweistext rechts |
| App-Kachel L ("Zuletzt genutzt") | 164px hoch, 4 Spalten | 20px | Icon in 52px-Feld, Name 20px, Zeit in Mono, Stern oben rechts |
| App-Kachel M ("Favoriten") | 124px hoch, 4 Spalten, 8 Plätze | 20px | Icon, Name, gefüllter Stern; freie Plätze gestrichelt |
| App-Kachel S ("Alle Apps") | 64px hoch, 5 Spalten | 16px | Icon + Name in einer Zeile, Stern rechts |
| Beliebt-Liste | 60px pro Zeile | 20px (Container) | Rang in Mono, Icon, Name, Balken in Akzent, Stern |
| Stern-Toggle | 44 x 44px | 12px | `aria-pressed`, leer = Umriss, aktiv = `--color-favorite` |
| Filter-Chip | 44px hoch | 999px | aktiv = Akzent-Fläche + Kontrast-Text |
| Dienst-Kachel | 76px hoch, 4 Spalten | 18px | Icon, Name, Statuspunkt + Wort, ↗ (öffnet neuen Tab), **keine** Adresse |
| Widget-Karte | 380px hoch, 3 Spalten | 20px | h3 + Chevron-Link, Diagramm 150px, Kennzahlen als 3er-`dl` |
| Zertifikat-Kachel | 84px hoch, 7 Spalten | 16px | Statuspunkt, Domain, Resttage + Datum in Mono |
| Befehl-Kachel | mind. 150px, wächst mit, 4 Spalten | 18px | Name, Beschreibung, Zahnrad-Link, Play-Button 44px; nach Klick "Gestartet" |

Favoriten setzt man per Stern direkt an jeder Kachel. Kein separater Bearbeiten-Modus.

### Mobil (390px)
- Seitenrand 16px, keine horizontale Scrollbar der Seite.
- "Zuletzt genutzt" als wischbare Reihe (148 x 128px), Favoriten als 4er-Raster (84px).
- Beliebt, Alle Apps, Dienste, Zertifikate, Befehle als Listen mit 56-64px Zeilen.

## Radien (Komponenten)

| Komponente | Radius |
|------------|--------|
| `--radius` (global) | 24px |
| `.panel` | 20px |
| `.tile` | 20px |
| `.card` | 18px |
| `.btn` | 14px (sm 10px, lg 16px, icon 10px) |
| `.input` / `.select` / `.textarea` | 12px (Suchfeld Startseite 16px, mobil 14px) |
| `.chip` | 999px (Pille) |

## Regeln

1. **Tokens statt Literale.** Keine rohen Hex/rgba/px-Werte, wenn ein Token existiert.
2. **Standard-Klassen nicht re-definieren.** App-CSS darf `btn`, `card`, `panel`, `tile`,
   `title`, `input`, `toast`, `loader` etc. nicht überschreiben. App-spezifisch → Prefix
   `{app}-{thing}` (z.B. `.tasks-board`, `.motion-bar`).
3. **CSS-Serving:** App-Stylesheets müssen `{name}.min.css` heißen (CSS-Route).
4. **Keine Farbverläufe, keine Emoji als Icons.** Flächen, Pillen, Knöpfe und Panels sind
   einfarbig (Token), nie `linear-/radial-/conic-gradient`. Erlaubt sind nur eine einfarbige
   Ebene `linear-gradient(var(--x), var(--x))` zum Übereinanderlegen und `mask-image` zum
   Ausblenden (Fraktal-Rand der Startseite). Auch keine weichgezeichneten Farbflecken (`filter: blur` auf farbigen Flächen) als Ersatz. Icons sind Stroke-Icons (lucide).
5. **Tipp-Flächen mindestens 44px**, auch für reine Icon-Buttons (mit `aria-label`).
6. **Vorhandene Standard-Komponente vor Eigenbau.**
7. **Nicht alles auf einmal zeigen.** Eine Seite zeigt zuerst das, was man meistens braucht:
   - Lange Listen und Ranglisten zeigen die ersten 10 (Verläufe 5) und darunter einen Knopf
     `Weitere laden (n)`, der die nächsten nachlädt. Kein Scrollen durch Hunderte Zeilen.
   - Zweitrangige Daten (fremde Vergleichswerte, Premium-/Bezahlmodelle, Rohdaten) stehen hinter
     einem Schalter (`ui-switch`) und sind ausgeblendet, bis man ihn einschaltet. Für ein reines
     An/Aus nie einen Chip oder Knopf nehmen.
   - Tabellen haben wenige Hauptspalten; alle weiteren Messwerte liegen in einem `ui-details`
     darunter. Werte pro Einzelschritt (pro Frage, pro Datei) werden zu einer Zeile je Objekt
     zusammengefasst, die Einzelwerte sind aufklappbar.
   - Live-Ausgaben sind ein festes Fenster mit den letzten Zeilen, kein scrollender Verlauf.

## Bewegung

Micro-Animationen sind Teil des Systems und greifen überall automatisch: Druck-Feedback,
Icons, die bei Hover ihre Aktion andeuten, versetzt pulsierende Skeletons, gestaffeltes
Aufsteigen beim Öffnen einer Seite, Einblenden beim Scrollen, `ui.busy()` für arbeitende
Knöpfe. Nur `scale`/`translate`/`rotate`/`opacity`, Druck 150 ms, Einblenden 320 ms, alles
aus bei `prefers-reduced-motion: reduce`. Details und Tabelle: `COMPONENTS.md`, "Bewegung".

## Ergänzende Maße

In `root.min.css` definiert: `--space-1/2/3/4/5/6/8/12` = 4/8/12/16/20/24/32/48px,
`--control-target-min` = 44px, `--font-size-readout` = 1.5rem für numerische Anzeigen.
Neue App-Layouts referenzieren diese Maße.

`.btn.icon` und `input`/`select`/`textarea` wachsen unter `@media (pointer: coarse)` auf
44px bzw. 16px Schriftgröße: 36px trifft sich am Finger schlecht, und unter 16px zoomt
iOS Safari beim Fokussieren die Seite. Zeigergeräte behalten die kompakte Größe.
Offen: `.btn.sm` und die Navbar unterschreiten weiterhin 44px.
