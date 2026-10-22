---
name: Kuhler's GELUMPE
description: Editor für den Electribe 2 Sampler. Tokens und Abstände kommen aus dem Interface (site/design/), die cee-Bausteine sind eigene.
source:
  codebase: site/design/root.min.css, site/design/colors.min.css, site/app.css, site/app/*.css
colors:
  primary: "#9ec3d1"
  on-primary: "#0b1417"
  primary-soft: "#cfe1e8"
  secondary: "#c4c8cf"
  background: "#0a0a0b"
  on-background: "#f4f4f5"
  surface: "#0a0a0b"
  on-surface: "#f4f4f5"
  surface-navbar: "#0e0e10"
  surface-popover: "#121212f1"
  surface-panel: "#ffffff0f"
  surface-panel-alt: "#ffffff0a"
  surface-item-muted: "#ffffff14"
  surface-item-strong: "#ffffff2b"
  text-secondary: "#ffffffb8"
  text-muted: "#ffffff8c"
  text-accent: "#e5edf2"
  border-strong: "#ffffff29"
  border-muted: "#ffffff1a"
  border-accent: "#9ec3d159"
  focus-ring: "#88c0d0"
  status-ok: "#22c55e"
  status-ok-text: "#4ade80"
  status-error: "#ef4444"
  status-error-text: "#fca5a5"
  status-warn: "#f59e0b"
  status-warn-text: "#fcd34d"
  favorite: "#c9b27e"
typography:
  display:
    fontFamily: Sora
    fontSize: 68px
    fontWeight: 700
    lineHeight: 1.1
  page-title:
    fontFamily: Sora
    fontSize: 44px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: -1px
  page-title-mobile:
    fontFamily: Sora
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.1
  section-title:
    fontFamily: Sora
    fontSize: 26px
    fontWeight: 700
    lineHeight: 1.25
  section-title-mobile:
    fontFamily: Sora
    fontSize: 20px
    fontWeight: 700
    lineHeight: 1.25
  title-sm:
    fontFamily: IBM Plex Sans
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.2
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.45
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  label-sm:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
  code:
    fontFamily: IBM Plex Mono
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
rounded:
  xs: 8px
  sm: 12px
  md: 14px
  lg: 16px
  xl: 20px
  2xl: 24px
  full: 999px
spacing:
  unit: 4px
  "1": 4px
  "2": 8px
  "3": 12px
  "4": 16px
  "5": 20px
  "6": 24px
  "8": 32px
  "10": 40px
  "12": 48px
  "14": 56px
  "16": 64px
  page: 56px
  page-mobile: 32px
  section: 20px
  section-mobile: 12px
  block: 8px
  block-wide: 12px
  row: 8px
  card-grid: 12px
  card-padding: 16px
  gutter: 32px
  gutter-mobile: 16px
components:
  section-title:
    typography: "{typography.section-title}"
    textColor: "{colors.on-surface}"
  card:
    backgroundColor: "{colors.surface-panel-alt}"
    rounded: "{rounded.lg}"
    padding: "{spacing.card-padding}"
  entry-card:
    rounded: "{rounded.lg}"
    padding: "{spacing.card-padding}"
  note:
    backgroundColor: "{colors.surface-item-muted}"
    rounded: "{rounded.md}"
    padding: 12px 16px
---

# Design: Kuhler's GELUMPE

## Overview

Ein Werkzeug für ein Gerät, kein Shop und kein Dashboard. Die Seiten sind ruhig und dunkel, Text
und Bedienelemente tragen die Seite, Flächen gibt es nur für wiederholte Objekte. Quelle ist das
Interface: die Tokens in `site/design/root.min.css` und `colors.min.css`, die Regeln aus
`Interface/docs/design-system/migration-recipe.md`. Farben, Schrift und Radien beschreibt
`site/design/DESIGN.md`, die Bausteine `site/design/COMPONENTS.md`. Diese Datei legt fest, was
der Editor darüber hinaus festlegt: die Abstände und die `cee-*`-Bausteine.

## Colors

Ein Farbschema, aus dem Interface übernommen. Hintergrund fast schwarz (`{colors.background}`),
Text `{colors.on-background}`, Eisblau `{colors.primary}` als einziger Akzent. Flächen sind weiß
mit wenig Deckkraft (`{colors.surface-panel}`), Rahmen ebenso. Statusfarben nur für Status.
Im Code immer `var(--color-…)`, nie der Wert.

## Typography

Überschriften in Sora (`{typography.page-title}`, `{typography.section-title}`), Text in IBM Plex
Sans (`{typography.body-md}`), Code und Werte des Geräts in IBM Plex Mono. Schriftgrößen nur über
`--text-*`.

## Layout

Nur diese Abstände, als `var(--space-N)`. Kein px für Abstände, außer 1px-Rahmen und 2px zwischen
Zeile und Unterzeile.

| Token | px | | Token | px |
|---|---|---|---|---|
| `--space-1` | 4 | | `--space-6` | 24 |
| `--space-2` | 8 | | `--space-8` | 32 |
| `--space-3` | 12 | | `--space-10` | 40 |
| `--space-4` | 16 | | `--space-12` | 48 |
| `--space-5` | 20 | | `--space-14` | 56 |
| | | | `--space-16` | 64 |

### Vier Ebenen

Jeder Abstand gehört zu genau einer Ebene.

| Ebene | Wo | Desktop | Mobil (≤ 720px) | Gesetzt von |
|---|---|---|---|---|
| Seite | zwischen Abschnitten einer Seite | `--space-14` (56) | `--space-8` (32) | `.ui-page` gap |
| Abschnitt | zwischen Blöcken in einem Abschnitt: Kopf, Absatz, Feld, Liste, Knopfleiste | `--space-5` (20) | `--space-3` (12) | `.ui-section` gap |
| Block | innerhalb eines Blocks: Label und Feld, Titel und Text einer Karte, Zeilen einer Liste | `--space-2` (8) bis `--space-3` (12) | gleich | `.ui-field`, `.ui-row`, `.ui-list` |
| Reihe | Knöpfe nebeneinander, Chips, Icon und Text | `--space-2` (8) | gleich | `.ui-page-actions`, `.ui-chipgroup` |

Innenabstand von Flächen: Karte `--space-4` (16), Dropzone `--space-6` / `--space-5`,
Dialog `--space-6` seitlich, `--space-4` bis `--space-5` oben und unten, Aufklapper `--space-4`.
Seitenkopf: `padding-top` `--space-12` (mobil `--space-6`), Seite unten `--space-16`.
Seitenrand: `--page-gutter` (32, mobil 16).

### Regeln

1. **Abstand macht der Elternteil, mit `gap`.** Kinder haben `margin: 0`. Kein `margin-top` auf
   einem Absatz, keine `<br>`, kein leeres Element als Abstandhalter. Absätze, Überschriften und
   Listen im Fluss setzen ihren Standard-Margin auf 0, sonst addiert er sich zum `gap`.
2. **Ein Abschnitt ist `section.ui-section`** mit `.ui-section-head` und `h2.ui-section-title`.
   Eine eigene Klasse für einen Abschnitt (`cee-sec`, `cee-patch-panel`) übernimmt dieselben Werte:
   `display: flex; flex-direction: column; gap: var(--space-5)`, mobil `--space-3`.
3. **Abschnitte bekommen keinen Kasten.** Überschrift und Abstand trennen sie. Eine Fläche nur für
   wiederholte Objekte (Karten im Raster), Dialoge und einen Medienrahmen.
4. **Karten im Raster:** `gap` `--space-3`, Innenabstand `--space-4`, Titel und Text darin
   `--space-1` bis `--space-2`.
5. **Knopfleiste am Ende eines Ablaufs:** eigene Reihe, oben durch den Abschnitts-Abstand getrennt,
   Zurück links, Weiter rechts.
6. **Nichts überlappt.** Kein negatives Margin, kein `position: absolute` für Inhalt im Fluss. Ein
   absolut gesetztes Icon in einer Karte bekommt seinen Platz als `padding` reserviert.

## Elevation & Depth

Tiefe kommt aus Flächen und Rahmen, nicht aus Schatten. `--shadow` nur für Dialoge und Popover,
die über der Seite liegen. Keine Verläufe, außer dem Leuchten der Pads auf der Zeichnung des
Geräts.

## Shapes

Radien nur über `--radius-*`: Karten `{rounded.lg}`, Hinweise `{rounded.md}`, kleine Flächen wie
Listenzeilen `{rounded.xs}`, Pillen `{rounded.full}`.

## Components

Die Standard-Bausteine sind die `ui-*`-Klassen aus `site/design/` und werden nicht umdefiniert.
Eigene Klassen tragen `cee-`. Welcher Selektor zu welchem Baustein und welcher Ebene gehört, steht
in `test/e2e/support/design-map.mjs`; `test/e2e/design.e2e.mjs` misst damit jede Seite.

- **Seite** (`.cee-main.ui-page`, Startseite `.cee-home`): Abschnitte im Abstand der Seiten-Ebene.
- **Abschnitt** (`.ui-section`, `.cee-sec`, `.cee-patch-panel`): Blöcke im Abstand der Abschnitts-Ebene.
- **Karte** (`.cee-card`, `.cee-entry-step`): Fläche mit Rahmen, nur im Raster `.cee-cards`.
- **Hinweis** (`.cee-note`): ein Satz, der nicht übersehen werden darf. Kein Abschnitt im Kasten.
- **Ablauf-Leiste** (`.cee-patch-nav`): Zurück links, Weiter rechts.

Eine neue `cee-*`-Klasse ist erst fertig, wenn feststeht, welche Ebene sie hat und welchen Token.

## Do's and Don'ts

- Do Abstände am Elternteil mit `gap` setzen und den Token der Ebene nehmen.
- Do im Browser bei 1280, 860 und 390px Breite prüfen und mit `getBoundingClientRect` messen.
- Do einen Wert, der kein Design ist (ein Pixel des Geräte-Displays), mit `raw-ok: <warum>` markieren.
- Don't rohe Farben, px-Radien, Schriftgrößen oder Abstände schreiben; `node tools/raw-values.mjs` findet sie.
- Don't Abschnitte in Kästen setzen oder Inhalt mit negativem Margin verschieben.
- Don't `site/design/` hier ändern; das ist die Kopie des Interface.
