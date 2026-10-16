# Design-System

Standard-Komponenten und Schriften (`--font-*`, selbst gehostet) leben in [`root.min.css`](./root.min.css). Farb- und Schatten-Tokens in [`colors.min.css`](./colors.min.css), dokumentiert in [`DESIGN.md`](./DESIGN.md).

Jede App lädt im `<head>`:

```html
<link rel="stylesheet" href="/css/Main/colors" />
<link rel="stylesheet" href="/css/Main/root" />
<link rel="stylesheet" href="/css/Main/navbar" />
<link rel="stylesheet" href="/css/{App}/{name}" />  <!-- App-Spezifika -->
```

App-CSS-Dateien dürfen **keine Standard-Klassen re-definieren**. Wenn eine App eine echte App-spezifische Variante braucht, mit Prefix wie `.tasks-board`, `.casino-card`, `.dh-*`.

Neue geteilte Komponenten tragen das Prefix `ui-` (z. B. `ui-page`), damit sie nicht mit
älteren App-Klassen wie `.page-header` oder `.section` kollidieren.

## Tokens für Maße

In `root.min.css`. Keine rohen px-Werte für diese Eigenschaften in App-CSS.

| Gruppe | Tokens |
|---|---|
| Abstände | `--space-1` (4) bis `--space-16` (64): 1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16 |
| Radien | `--radius-xs` 8, `-sm` 12, `-md` 14, `-lg` 16, `-xl` 20, `-2xl` 24, `-pill` |
| Schrift | `--text-2xs` 12, `-xs` 13, `-sm` 14, `-md` 15, `-base` 16, `-lg` 18, `-xl` 20, `-2xl` 26, `-3xl` 32, `-4xl` 44, `-display` 68 |
| Zeilenhöhe | `--leading-tight` 1.1, `-snug` 1.25, `-normal` 1.5 |
| Bewegung | `--dur-fast` 150ms, `-base` 180ms, `-slow` 280ms, `--ease-out` |
| Glas | `--glass-blur` 10px, `--glass-blur-hover` 18px |
| Seite | `--page-max` 1280px, `--page-gutter` (32, mobil 16) |

Semantische Farben in `colors.min.css`: `--color-text-success/-warning/-danger`,
`--color-status-ok/-warn/-error/-info` (jeweils mit `-text`), `--color-border-danger`.

## Seitengerüst (`ui-*`)

Jede App-Seite hat dieselbe Grundform: Navbar, darunter `main.ui-page`, darunter Abschnitte.
Ein Seitenkopf ist optional.

```html
${PARAM0}
<main class="ui-page">
  <header class="ui-page-header">                        <!-- optional, siehe unten -->
    <p class="ui-page-lead">Dateien werden nach 24 Stunden gelöscht.</p>   <!-- optional, siehe unten -->
    <div class="ui-page-actions">…Buttons…</div>          <!-- optional, rechts, mobil darunter -->
  </header>

  <section class="ui-section">
    <div class="ui-section-head">
      <h2 class="ui-section-title">Verlauf</h2>
      <span class="ui-section-meta">12 Dateien</span>        <!-- optional -->
      <div class="ui-section-actions">…</div>               <!-- optional, rechts -->
    </div>
    …
  </section>
</main>
```

Kein `h1.ui-page-title`, der nur den App-Namen wiederholt: die Navbar zeigt ihn schon, auch als
Übersetzung oder generischer Seitenname ("Aufgaben" unter Navbar "Tasks" zählt auch als
Wiederholung). Ein Titel kommt nur für echten Seiteninhalt dazu, den die Navbar nicht kennt: ein
Datensatzname (Event, Routine) oder eine Aktion wie "Routine bearbeiten":

```html
<header class="ui-page-header">
  <h1 class="ui-page-title">Routine bearbeiten</h1>
</header>
```

Bleibt vom Seitenkopf nach Abzug des Titels nur `.ui-page-actions` übrig, bleibt er stehen
(rechtsbündig, keine leere Titelspalte); ist er ganz leer, entfällt `header.ui-page-header`
komplett und `main.ui-page` trägt den oberen Abstand selbst (siehe `root.min.css`).

Abschnitte haben keinen Kasten: kein `panel` um eine `ui-section`, auch nicht um ein Formular.
Überschrift und Abstand trennen die Bereiche, Eingabefelder, Dropzone und Buttons stehen frei.
Eine Fläche gibt es nur für wiederholte Objekte (Karten in Raster oder Liste), Dialoge und einen
Medien- oder Player-Rahmen, wenn er wirklich einen braucht.

Kein Eyebrow über dem Titel. `ui-page-lead` nur für Information, die die Seite nicht selbst
zeigt (Löschfrist, Limit, Voraussetzung). Keine Beschreibung dessen, was man ohnehin sieht
("Such eine App ..."), keine Werbesätze: dann weglassen.

Seitenleiste + Inhalt (braucht `/js/Main/ui.js`):

```html
<div class="ui-split">
  <button type="button" class="btn ui-split-toggle" aria-expanded="false" aria-controls="side">Inhalt</button>
  <aside class="ui-split-side" id="side">…</aside>          <!-- 280px, klebt beim Scrollen -->
  <div class="ui-split-main">…</div>
</div>
```

Mobil (bis 720px) ist die Leiste eingeklappt, der Toggle-Button klappt sie über dem Inhalt auf.

## Verhalten: `ui.js`

Wird von `replyToReq` auf jeder App-Seite eingebunden (nicht auf der Login-Seite). Abschalten
ohne Deploy: `UI_GLOBAL_JS=0` in der `.env`. Immer über `window.ui` ansprechen, weil einige
Apps ein eigenes `ui` haben. Das Skript ist `defer`: aus Inline-Skripten während des Ladens
steht `window.ui` noch nicht bereit.

## Formularfeld (`ui-field`, `ui-input`)

```html
<div class="ui-field">
  <label class="ui-field-label" for="name">Name <span class="ui-field-required" aria-hidden="true">*</span></label>
  <input class="input" id="name" required>
  <p class="ui-field-help" id="name-help">Nur wenn der Hinweis wirklich hilft.</p>
</div>

<div class="ui-input">                                   <!-- Eingabe mit Icon und/oder Suffix -->
  <i data-lucide="at-sign"></i><input id="mail"><span class="ui-input-suffix">@example.org</span>
</div>
```

Fehler: `window.ui.setFieldError(feldOderId, 'Text')` setzt Rand, Text, `aria-invalid` und
`aria-describedby`; `window.ui.setFieldError(feld, null)` entfernt alles wieder.

## Dialog (`ui-dialog`)

Natives `<dialog>`: Tab bleibt im Dialog, der Rest der Seite ist gesperrt, Escape und Klick
daneben schließen, der Fokus springt zum Auslöser zurück. Mobil (bis 720px) als Sheet von unten.

```html
<button class="btn" data-ui-dialog-open="edit">Bearbeiten</button>
<dialog class="ui-dialog" id="edit" aria-labelledby="editTitle">   <!-- ui-dialog-narrow / ui-dialog-wide -->
  <form method="dialog" class="ui-dialog-box">
    <header class="ui-dialog-head">
      <h2 class="ui-dialog-title" id="editTitle">Aufgabe bearbeiten</h2>
      <button type="button" class="btn icon ui-dialog-close" data-ui-dialog-close aria-label="Schließen">…</button>
    </header>
    <div class="ui-dialog-body">…</div>
    <footer class="ui-dialog-foot">
      <button class="btn" value="cancel">Abbrechen</button>
      <button class="btn primary" value="ok">Speichern</button>
    </footer>
  </form>
</dialog>
```

Per JS: `window.ui.openDialog(elOderId)`, `window.ui.closeDialog(el, wert)`; das Ergebnis steht
danach in `dialog.returnValue`. `data-ui-static` am `<dialog>` verhindert das Schließen per Klick daneben.

Statt `confirm()` und `prompt()`:

```js
if (!(await window.ui.confirm({ title: 'Aufgabe löschen?', text: 'Das lässt sich nicht rückgängig machen.', danger: true }))) return;
const name = await window.ui.prompt({ title: 'Neuer Name', label: 'Name', value: alt });   // null bei Abbrechen
```

`confirm` liefert `true` nur bei Bestätigen, sonst `false` (Abbrechen, Escape, Klick daneben).
Bei `danger` hat Abbrechen den ersten Fokus. Wichtig beim Umbau: alles, was nach dem `await`
gelesen wird (IDs, Zustand), vorher festhalten, weil sich die Seite in der Zwischenzeit ändern kann.
Toasts (`showToast`) liegen in der obersten Ebene und bleiben auch über einem offenen Dialog sichtbar.
Eigene Dialoge mit Textfeld: Enter löst den ersten Submit-Knopf im Formular aus, also den Speichern-Knopf zuerst ins Markup setzen oder Enter abfangen.

Verhaltenstest: `node tools/ui-browser-check.mjs`.

## Leer, Laden, Fehler (`ui-state`)

Jede Liste und Fläche, die Daten lädt, zeigt einen dieser Zustände, nie eine leere Stelle.

```js
window.ui.state(el, { kind: 'loading', rows: 3 });                                   // Skeleton, role=status
window.ui.state(el, { kind: 'empty', text: 'Noch keine Aufgaben.', icon: 'inbox',
                      action: { label: 'Aufgabe anlegen', onClick: neu } });
window.ui.state(el, { kind: 'error', text: 'Konnte nicht geladen werden.', retry: laden });  // role=alert
```

Markup direkt: `<div class="ui-state" data-kind="empty|loading|error">` mit `ui-state-icon`,
`ui-state-text`, `ui-state-actions`; Laden enthält `ui-skeleton`-Zeilen.

## Liste (`ui-list`, `ui-row`)

```html
<ul class="ui-list">                                     <!-- ui-list-plain: ohne Rahmen, Linien zwischen den Zeilen -->
  <li><a class="ui-row" href="…">                        <!-- ganze Zeile klickbar -->
    <span class="ui-row-icon"><i data-lucide="music"></i></span>
    <span class="ui-row-text"><span class="ui-row-title">Titel</span><span class="ui-row-meta">vor 4 Std.</span></span>
    <span class="ui-row-end">3:42</span>
  </a></li>
  <li class="ui-row">                                    <!-- Link plus eigene Aktionen -->
    <a class="ui-row-link" href="…">…</a>
    <div class="ui-row-actions"><button class="btn icon" aria-label="Löschen">…</button></div>
  </li>
</ul>
```

### Lange Listen

Mehr als 10 Zeilen (Verläufe: 5) werden nicht auf einmal gezeigt: die ersten N, darunter
`<button class="btn sm">Weitere laden (n)</button>`, der die nächsten N anhängt und bei 0
verschwindet. Zweitrangige Einträge (z. B. Bezahlmodelle neben lokalen) blendet ein Schalter
(`ui-switch`) ein, Standard ist aus. Regel 8 in [`DESIGN.md`](../../../DESIGN.md#regeln).

## Status-Pille (`ui-pill`)

`<span class="ui-pill" data-tone="ok|warn|error|info|running|neutral">Wort</span>`. Immer mit
Wort, der Punkt ist nur Zusatz. `running` pulsiert (nicht bei reduzierter Bewegung).

## Chips und Filterleiste (`ui-chip`, `ui-chipgroup`, `ui-filterbar`)

```html
<div class="ui-filterbar">
  <div class="ui-input"><i data-lucide="search"></i><input type="search" aria-label="Suchen"></div>
  <div class="ui-chipgroup" role="group" aria-label="Status" data-ui-single data-ui-required>
    <button type="button" class="ui-chip" aria-pressed="true">Alle <span class="ui-chip-count">24</span></button>
    <button type="button" class="ui-chip" aria-pressed="false">Offen</button>
  </div>
</div>
<span class="ui-chip ui-chip-sm">Tag <button type="button" class="ui-chip-remove" aria-label="Tag entfernen">…</button></span>
```

Chips mit `aria-pressed` schalten per `ui.js` um und feuern `ui:toggle` (bubbelt, `detail.pressed`),
auch für Chips, die eine Einzelauswahl abschaltet. `data-ui-single`: höchstens einer aktiv;
zusätzlich `data-ui-required`: genau einer (der aktive lässt sich nicht abwählen).
`aria-disabled="true"` oder `disabled` sperrt einen Chip.

## Tabs (`ui-tabs`, `ui-tab`, `ui-tabpanel`)

```html
<div class="ui-tabs" role="tablist" aria-label="Clips, Quellen oder Sample Packs">
  <button id="tabClips" class="ui-tab" type="button" role="tab" data-tab="clips" aria-selected="true" aria-controls="panelClips">Clips <span class="ui-tab-count">24</span></button>
  <button id="tabSources" class="ui-tab" type="button" role="tab" data-tab="quellen" aria-selected="false" aria-controls="panelSources" tabindex="-1">Quellen <span class="ui-tab-count"></span></button>
</div>
<div id="panelClips" class="ui-tabpanel" role="tabpanel" aria-labelledby="tabClips" tabindex="0">…</div>
<div id="panelSources" class="ui-tabpanel" role="tabpanel" aria-labelledby="tabSources" tabindex="0" hidden>…</div>
```

```js
const tabs = window.ui.tabs(tablistEl, {
  persist: 'app.tab',              // optional: localStorage-Schlüssel, der aktive Tab steht auch im URL-Hash
  onChange: (id) => { /* Daten des Tabs laden */ },
});
tabs.select('quellen');            // { focus: true } setzt den Fokus, { persist: false } lässt Speicher und Hash aus
```

Ein Tab ist ein `<button>` und sieht aus wie ein `.btn` (Radius, Rand, Schrift), mindestens so hoch
wie das Touch-Ziel (`--control-target-min`, 44 px); der gewählte Tab trägt Akzentrand,
Akzentfläche und Akzenttext. Jedes Panel bekommt `tabindex="0"` (APG-Muster), damit Tastaturnutzer
in Panels ohne fokussierbaren Inhalt hineinkommen. Tabs ersetzen keine Filter: für „mehrere
Bedingungen, eine Liste“ sind Chips da, Tabs wechseln zwischen Bereichen mit eigenem Inhalt.

- **Verhalten:** Pfeiltasten (rechts, links, mit Umbruch), `Home` und `End` bewegen die Auswahl,
  `tabindex` wandert mit dem aktiven Tab, nur dessen Panel ist sichtbar (`hidden`).
- **Start:** URL-Hash vor gespeichertem Wert vor dem ersten Tab. `persist` schaltet Speicher und Hash
  ein, `hash: false` nur den Hash aus. Ohne `persist` bleibt alles im Speicher der Seite.
- **Ein Hash pro Seite:** nur eine Instanz je Seite darf den Hash nutzen, weitere bekommen
  `hash: false`. `select(id, { persist: false })` schreibt weder Speicher noch Hash: steht im Hash
  ein anderer Tab, landet ein Neuladen auf diesem.
- **`onChange`** feuert nur bei einem echten Wechsel, auch beim ersten Setzen. Das Panel ist da
  schon sichtbar: erst dann lassen sich Raster messen oder Sichtbarkeits-Beobachter starten.
- **Zähler:** `ui-tab-count` bleibt leer, solange es keine Zahl gibt (dann ist er ausgeblendet). Der
  Zähler nennt, was der Tab gerade zeigt, nicht den Gesamtbestand: mit Filter die gefilterte Zahl.
- Mobil (bis 640px) teilen sich die Tabs die Zeile, bei zu wenig Platz umbrechen sie.

## Segmented Control (`ui-segmented`)

Auswahl aus zwei bis fünf Werten, die sofort gilt (Format, Ansicht, Zeitraum). Für Bereiche mit
eigenem Inhalt sind Tabs da, für mehrere Bedingungen gleichzeitig Chips.

```html
<div class="ui-segmented" role="radiogroup" aria-label="Format">            <!-- data-fill: volle Breite -->
  <label class="ui-segmented-option"><input type="radio" name="fmt" value="mp3" checked><span>MP3</span></label>
  <label class="ui-segmented-option"><input type="radio" name="fmt" value="wav"><span>WAV</span></label>
</div>
```

Native Radios: Pfeiltasten wechseln, das Formular schickt den Wert, `change` kommt am Input. Ein
Icon steht als `<i data-lucide>` mit im `<span>`. `disabled` am Input sperrt eine Option.

## Schalter (`ui-switch`)

An oder aus, und es gilt sofort. Muss ein Speichern-Knopf bestätigen, bleibt es eine Checkbox.

```html
<label class="ui-switch"><input type="checkbox" role="switch" checked><span class="ui-switch-track" aria-hidden="true"></span>Benachrichtigungen</label>

<label class="ui-switch" data-end>                                            <!-- Schalter rechts in einer Einstellungszeile -->
  <input type="checkbox" role="switch"><span class="ui-switch-track" aria-hidden="true"></span>
  <span class="ui-switch-text">Nachts leiser<span class="ui-switch-hint">00:00 bis 06:00 nur stille Hinweise</span></span>
</label>
```

Leertaste schaltet, `change` kommt wie bei jeder Checkbox, `input.checked` liest den Zustand.
Die ganze Zeile ist mindestens 44 px hoch und klickbar.

## Kennzahl (`ui-kpis`, `ui-kpi`)

```html
<div class="ui-kpis">
  <div class="ui-kpi">
    <span class="ui-kpi-label">Temperatur</span>
    <span class="ui-kpi-value">21,4<span class="ui-kpi-unit">°C</span></span>
    <span class="ui-kpi-trend">+0,8 seit gestern</span>     <!-- data-tone nur, wenn die Richtung eindeutig gut/schlecht ist -->
  </div>
</div>
```

## Diagramm (`ui-chart`)

Karte für Chart.js oder ein eigenes Canvas. Die Fläche hat eine feste Höhe (`--chart-height`, 320px, mobil 260px; `ui-chart-lg` 420px), Chart.js braucht dafür `maintainAspectRatio: false`.

```html
<section class="ui-chart ui-chart-lg" id="tempChart">
  <header class="ui-chart-head">
    <h2 class="ui-chart-title">Temperatur (24 h)</h2>
    <div class="ui-chart-actions"><button type="button" class="btn icon" aria-label="Erklärung">…</button></div>
  </header>
  <div class="ui-chart-body"><canvas id="c"></canvas></div>
  <div class="ui-chart-foot">optionaler Text unter dem Diagramm</div>
</section>
```

Leer, Laden, Fehler über der Fläche (gleiche Optionen wie `ui.state`), `null` blendet aus. Der aktuelle Zustand steht in `.ui-chart-body[data-state]`:

```js
window.ui.chartState(tempChart, { kind: 'loading' });
window.ui.chartState(tempChart, { kind: 'empty', icon: 'thermometer', text: 'Für diesen Tag gibt es keine Messwerte.' });
window.ui.chartState(tempChart, { kind: 'error', text: 'Konnte nicht geladen werden.', retry: load });
window.ui.chartState(tempChart, null);
```

Trifft ein Fehler viele Diagramme gleichzeitig, einmal ansagen (Toast) und die Karten mit `silent: true` füllen, sonst liest ein Screenreader ihn für jede Karte vor. Liegt der Fokus auf einem Knopf im Zustand, springt er beim Wechsel auf den Diagrammtitel.

Farben: Serien über `chartSeries(n)` aus `chartTheme.js` (`--chart-1..4`), Achsen `--chart-tick`/`--chart-grid`. Für Heatmaps und andere Werte-Skalen `--data-seq-1..5` (kalt nach warm) und `--data-empty` für fehlende Werte. Im JS `const scale = chartScale('--data-seq', 5)` einmal pro Zeichnung holen, dann `scale(t)` mit `t` von 0 bis 1; nie Farben ins JS schreiben.

Mit beschrifteten Feldern (`ui-field`) in einer `ui-filterbar` stehen Chips und Knöpfe auf der Höhe der Eingabe.

## Fortschritt und Jobs (`ui-progress`, `ui-job`)

```html
<div class="ui-job">
  <div class="ui-job-head">
    <span class="ui-job-name">Sommer-Mix.wav → MP3</span>
    <div class="ui-job-actions"><button type="button" class="btn icon" aria-label="Sommer-Mix.wav: abbrechen" title="Sommer-Mix.wav: abbrechen"><i data-lucide="x"></i></button></div>
  </div>
  <div class="ui-progress" id="p" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="Sommer-Mix.wav">
    <span class="ui-progress-bar"></span>
  </div>                                                   <!-- data-tone="error|ok" -->
  <span class="ui-job-meta">62 % · noch etwa 20 s</span>
</div>
```

Aktionen in `ui-job-actions` sind immer Icon-Knöpfe aus `ui.jobAction(kind, { name, onClick })`:
`cancel` (x), `retry` (Pfeil zurück), `delete` (Mülleimer, rot), `dismiss` (x, Meldung schließen)
und `discard` (x, angefangenen Upload verwerfen).
`name` landet im `aria-label` ("Sommer-Mix.wav: abbrechen"). Eine Status-Pille daneben entfällt,
der Zustand steht in `ui-job-meta`.

`window.ui.setProgress(el, 62, 'Sommer-Mix.wav')` setzt Breite und `aria-valuenow`;
`window.ui.setProgress(el, null)` schaltet auf unbestimmt. Ein vierter Parameter
`{ valueText: 'Fehlgeschlagen' }` setzt `aria-valuetext`; ohne ihn entfällt das Attribut.

Regel: Fortschritt einer Aufgabe (Upload, Konvertierung, Generierung, Import) zeigt immer
`ui-progress`, nie ein eigener Balken. Drei Fälle:

| Zustand | Aufruf | Bewegung |
|---|---|---|
| Wert bekannt (gemeldet oder Schätzung, dann höchstens 95 %) | `setProgress(el, 62)` | Füllstand |
| Läuft, Wert unbekannt (startet, 0 % gemeldet, Schätzung aufgebraucht) | `setProgress(el, null)` | Animation |
| Wartet auf etwas Äußeres (Warteschlange, Worker) oder Stand unbekannt | `setProgress(el, 0, label, { valueText: 'Wartet' })` mit Text daneben | keine |

Fertig und Fehler stehen mit `100` und `data-tone="ok|error"`, ein Fehler zusätzlich mit
`valueText: 'Fehlgeschlagen'`. Gestoppt oder beendet steht mit dem letzten Wert, nie unbestimmt.
Ein Balken im Zustand "läuft" wird beim Update nicht neu gebaut, sonst startet die Animation
neu. Größe und Platz gibt die App über eine eigene Layout-Klasse
(`.cm-bar { flex: 0 0 6rem }`), die nichts zeichnet. Unbestimmter Fortschritt zeigt einen
vollständig gefüllten Balken mit laufenden diagonalen Streifen. Bei `prefers-reduced-motion`
stehen die Streifen still; `data-tone` färbt den Balken.

Fortschritt oder Füllstand: **Fortschritt einer Aufgabe** (läuft, wird fertig, kann scheitern)
ist `ui-progress` mit `setProgress`, `null` heißt unbekannt. **Füllstand oder Auslastung** (CPU,
Speicher, Kontext, Rang; ein Wert, der steigt und fällt und nie „fertig“ wird) ist `ui-meter`
mit `setMeter`.

## Füllstand (`ui-meter`, `ui-meter-ring`)

```html
<div class="ui-meter" id="cpu" aria-label="CPU, Raspberry Pi 4"></div>   <!-- data-size="sm|lg" -->
<div class="ui-meter-ring" id="ctx"></div>                                <!-- data-shape="arc": Halbkreis -->
```

```js
window.ui.setMeter(el, 62, { label: 'CPU', warnAt: 70, errorAt: 90, valueText: '54,0 °C' });
window.ui.setMeter(el, null);   // kein Messwert: Balken leer, aria-valuetext „keine Daten“
```

`setMeter` legt `role="meter"`, `aria-valuemin/max/now`, `aria-label` und bei Bedarf
`aria-valuetext` an und baut die Füllung (Balken: `<span class="ui-meter-fill">`, Ring: SVG) beim
ersten Aufruf selbst. `valueText` steht für Werte, die keine Prozent sind (`54,0 °C`,
`12 Aufrufe`). Der Wert ist immer 0 bis 100; eine Größe wie Temperatur rechnet die App vorher um.

Ton: ohne Angabe Akzentfarbe. `tone: 'ok' | 'warn' | 'error'` setzt ihn fest, `warnAt` und
`errorAt` legen Schwellen fest (ab dem Wert), damit keine App die Farblogik selbst baut. Die
Farben sind die Status-Token (`--color-status-ok/warn/error`), die Breite läuft mit kurzer
Transition und steht bei `prefers-reduced-motion` still.

Größe: `data-size="sm"` (4 px), Standard (6 px), `data-size="lg"` (8 px). Breite und Platz gibt
die App über eine Layout-Klasse (`.home-pop-meter { display: none }` auf dem Handy), die nichts
zeichnet.

**Ring statt eigener Tacho:** `ui-meter-ring` ist ein Vollring (Kontext-Anzeige am Senden-Knopf
in MulmAI), `data-shape="arc"` ein Halbkreis (Auslastung pro Gerät in VPN). Beide zeichnet
`setMeter` mit dem Pfad `pathLength="100"`, deshalb gilt derselbe Wert 0 bis 100. Die Zahl im
Ring ist ein `<span class="ui-meter-ring-value">` im Ring, das die App selbst beschriftet. Größe
über `width` einer Layout-Klasse (Standard 32 px). Sitzt der Ring an einem Knopf, steht er als
Geschwister daneben, nicht darin: Kinder eines Knopfes lesen Screenreader nicht einzeln vor.
Ein Ring mit `hidden` fehlt im Accessibility-Baum, solange kein Wert da ist.

## Upload (`ui-dropzone`)

```html
<label class="ui-dropzone">
  <input type="file" class="ui-dropzone-input" multiple accept="audio/*">
  <i data-lucide="upload" class="ui-dropzone-icon"></i>
  <span class="ui-dropzone-title"><span class="ui-dropzone-drag">Dateien hierher ziehen oder </span>auswählen</span>
  <span class="ui-dropzone-hint">MP3, WAV oder FLAC, bis 200 MB</span>
  <span class="ui-dropzone-files"></span>                  <!-- ui.js schreibt die gewählten Namen hinein -->
</label>
```

Abgelegte Dateien landen im Input und lösen `input` und `change` aus; die App hört nur auf das
Input. `accept` gilt auch beim Ablegen: passt keine Datei, bekommt das Label `data-invalid`
(roter Rand), der Grund steht in `.ui-dropzone-files`, es gibt einen Toast und kein `change`.
Eigene Prüfungen der App (Größe, Format) im `change`-Handler mit
`window.ui.rejectFile(input, 'datei.mov: zu groß, bis 500 MB.')` ablehnen: gleiches Bild, Feld wird geleert. Der Server muss Typ und Größe trotzdem selbst prüfen.
Nach einer Auswahl trägt das Label `data-filled` (Haken für eigene Styles). `disabled` am Input
sperrt; auch dann fängt das Feld abgelegte Dateien ab, statt sie den Browser öffnen zu lassen.

### Gewählte Datei bleibt stehen (`ui.dropzoneFiles`)

Soll die Auswahl über einen Lauf hinaus stehen bleiben (etwa ein Upload, den der Server behält),
zeigt `window.ui.dropzoneFiles(input, items, { onRemove })` sie als `ui-list` direkt unter der
Dropzone, je Datei mit X-Knopf (`aria-label` "<Name> entfernen"):

```js
ui.dropzoneFiles(input, [{ name: 'Sommer-Mix.wav', size: 48_000_000, keptUntil: Date.now() + 864e5 }], {
  onRemove: (item, index) => { /* aus der eigenen Auswahl nehmen, dann erneut aufrufen */ },
});
ui.dropzoneFiles(input, []);   // Liste weg
```

- `items`: `{ name, size?, keptUntil?, meta? }`. Die Meta-Zeile setzt sich aus Größe, "bereit bis 14:30"
  (aus `keptUntil`; "morgen 14:30", später mit Datum) und `meta` zusammen. Name und Meta brechen um.
- Die App hält die Auswahl selbst und ruft die Funktion nach jeder Änderung neu auf; `onRemove` ändert
  nur die eigene Auswahl. Danach springt der Fokus auf die nächste Datei oder zurück aufs Feld.
- Die Liste steht neben dem `<label>`, nicht darin: Knöpfe in einem Label wären ungültig.
- Solange eine Liste steht, trägt die Dropzone `data-selected` und `data-filled`; `.ui-dropzone-files`
  bleibt leer. Eine neue Auswahl im Feld ersetzt die Liste nicht von selbst, das entscheidet die App.
- `ui.formatReadyUntil(ms)` liefert den Text "bereit bis 14:30" allein.

**Einfügen (Cmd/Strg+V)** funktioniert ohne eigenen Code: eine Datei aus der Zwischenablage
landet im sichtbaren Upload-Feld, das ihren Typ annimmt (Fokus in einem Feld gewinnt), mit
denselben `input`- und `change`-Events wie beim Ablegen, dazu `ui:paste`. Ein eigenes Datei-Feld
außerhalb einer Dropzone (z. B. versteckt hinter einem Knopf) macht mit `data-paste` mit; als
sichtbar zählt dann sein Elternelement oder ein umschließendes `[data-paste-area]`. Hat die App
das Einfügen selbst behandelt (`preventDefault`, etwa ein Editor), passiert nichts.

## Aufklapper (`ui-details`) und Slider (`ui-range`)

```html
<details class="ui-details"><summary>Erweitert</summary><div class="ui-details-body">…</div></details>

<div class="ui-field">
  <label class="ui-field-label" for="vol">Lautstärke <output class="ui-range-value" for="vol" data-unit=" %"></output></label>
  <input type="range" class="ui-range" id="vol" min="0" max="100" value="70">
</div>
```

`ui.js` hält Füllung und Wertanzeige bei Eingaben aktuell. Wer `.value` per Code setzt (etwa
gespeicherte Einstellungen) oder Slider nachträglich einfügt, ruft danach
`window.ui.syncRange(input)`, weil dabei kein `input`-Ereignis entsteht.

## Audio-Player (`ui-player`)

Einen Player gibt es nur einmal, und er wird per Code gebaut:

```js
const player = window.ui.player({
  src: "/pfad/sound.wav",
  label: "Kick",          // steht im aria-label von Knopf und Wellenform
  duration: 4.2,          // optional, zeigt die Länge schon vor dem Laden
  size: "sm",             // "sm" für Listenzeilen, "lg" für die Hauptansicht
  time: false,            // Zeitanzeige aus, wenn die Länge schon daneben steht
  title: "kick.wav",      // optional: Name oben links, Zeit oben rechts
  meta: "0:04 · Drums",   // optional: Zeile unter dem Namen
  titleFull: langerText,  // optional: Tooltip, wenn title gekuerzt ist
  actions: [removeBtn],   // optional: Knöpfe rechts neben der Wellenform
  topActions: [dlLink],   // optional: oben rechts neben der Zeit, etwa Download
});
host.append(player.el);
```

- **Listenzeile mit Namen:** mit `title` steht der Name oben links und die Zeit oben
  rechts, darunter Knopf, Wellenform und `actions` in einer Zeile. Download gehört
  als `topActions` oben rechts neben die Zeit, Löschen als `actions` neben die
  Wellenform. Den Namen nicht zusätzlich daneben setzen.
- **Es klingt immer nur eine Quelle.** Startet ein Player, setzt sich der vorige zurück:
  Ton aus, Strich weg. Eigene Engines (Web Audio, Mehrspur, Schnitt-Editoren) melden sich
  mit `window.ui.claimAudio(stopFn)` an und mit `window.ui.releaseAudio(stopFn)` ab.
  `window.ui.claimAudio(null)` stoppt alles, etwa beim Schließen eines Dialogs.
- **Wellenform** kommt aus der Datei selbst: sichtbar gewordene Player dekodieren im
  Browser, zwei gleichzeitig. Für lange Aufnahmen `wave: false`, dann bleibt eine flache
  Spur. Serverseitig berechnete Spitzen gehen als `peaks` hinein.
- **Bedienung:** Klick oder Ziehen auf der Wellenform springt, Pfeiltasten eine Sekunde
  (mit Umschalt fünf), Leertaste spielt oder pausiert. Pause behält die Stelle.
- **Methoden:** `play(ab)`, `pause()`, `seek(sek)`, `reset()`, `playRange(von, bis)`,
  `setSrc(src, opts)`; `player.audio` ist das `<audio>` für eigene Ereignisse wie
  `timeupdate`. Jeder Zustandswechsel feuert `ui:player` mit `detail.state`
  (`idle`, `loading`, `playing`, `paused`, `error`).
- **Server:** Die Media-Route muss Range-Anfragen mit 206 beantworten (`res.sendFile`
  kann das), sonst kann der Browser nicht springen.
- `window.ui.drawWave(canvas, peaks, { progress, gain })` und
  `window.ui.peaksFromBuffer(buffer)` zeichnen dieselben Balken für eigene Ansichten.

## Buttons

Alle Buttons: Glass-Style (transparenter Hintergrund), Border zeigt die Semantik.

```html
<button class="btn">Neutral / sekundär</button>
<button class="btn primary">Save / Confirm</button>       <!-- grüne Border -->
<button class="btn danger">Cancel / Delete</button>       <!-- rote Border -->
<button class="btn ghost">Tertiär (dashed)</button>
<button class="btn outline">Standard, explizit</button>
<button class="btn icon" aria-label="…">…</button>        <!-- 36×36 square -->
<button class="btn sm">Klein</button>
<button class="btn lg">Groß</button>
```

Kombinationen: `class="btn sm danger"`, `class="btn lg primary"`, `class="btn icon danger"`.

### Runder Icon-Button (`.avatar`)

Aus [`navbar.min.css`](./navbar.min.css). 40×40 Kreis, neutraler Glass-Hintergrund, Button-Reset eingebaut → rendert identisch auf `<button>` und `<div>`. In der Navbar für Back, App-Install und Profil. `hidden` blendet ihn aus (`.avatar[hidden]`).

```html
<button class="avatar" title="…"><svg>…</svg></button>
```

## Cards / Container

```html
<section class="panel">…</section>     <!-- großer Glass-Container (border-radius 20, padding 20), nicht um Seitenabschnitte -->
<div class="card">…</div>              <!-- mittel-große Card -->
<a class="tile">…</a>                  <!-- klein, klickbar, mit Lift-Hover -->
```

Modifier: `.card-muted`, `.card-strong` (verschiedene Surface-Helligkeiten).

## Typography

```html
<h1>Page-Titel</h1>
<h2>Section</h2>
<h3>Sub-Section</h3>
<div class="title">Page-Titel (semantisches Div statt h1)</div>
<div class="subtitle">Untertitel</div>
<p class="description">Längerer Beschreibungstext</p>
<p class="muted">Sekundärer / gedimmter Text</p>
<span class="label">UPPERCASE LABEL</span>
```

## Forms

```html
<input class="input" type="text" />
<select class="select">…</select>
<textarea class="textarea"></textarea>

<div class="searchbox">
  <svg>…</svg>
  <input type="text" placeholder="Suche…" />
</div>
```

`input`, `select`, `textarea` werden **auch ohne Klasse** automatisch gestyled, die Klassen-Form ist nur zur Klarheit.

## Layout

```html
<div class="actions">                  <!-- flexrow, linksbündig, gap 10px, flex-wrap -->
  <button class="btn">A</button>
  <button class="btn">B</button>
</div>

<div class="actions">                  <!-- Text links, Buttons rechts -->
  <h2>Titel</h2>
  <div class="actions-buttons">        <!-- margin-left: auto pusht rechts -->
    <button class="btn">Action</button>
  </div>
</div>

<div class="grid">…</div>              <!-- responsiver Grid mit Breakpoints (2→3→4→5 cols) -->
<div class="stack">…</div>             <!-- vertikales flex mit gap -->
<div class="row">…</div>               <!-- horizontales flex mit gap -->
<div class="toolbar">…</div>           <!-- horizontales flex, wrap, gap -->
```

### Lange Texte (`ui-truncate`, `ui-break`)

Lange Wörter (URLs, Pfade, Dateinamen) brechen seitenweit um (`overflow-wrap: break-word` am
`body`). In einer Flex- oder Grid-Zeile reicht das nicht: das Textelement darf erst schrumpfen,
wenn es `min-width: 0` hat. Dafür zwei Klassen:

```html
<span class="ui-truncate" title="voller Text">https://www.instagram.com/p/…</span>  <!-- eine Zeile mit "…" -->
<span class="ui-break">/Users/runner/work/…/SingleStreamDecoder.cpp</span>     <!-- bricht überall um -->
```

- **Titel und Namen** aus Nutzerdaten (Datei, URL, Betreff) in einer Zeile: `ui-truncate`, und
  wo JS den Text setzt, denselben Text als `title` setzen, damit er erreichbar bleibt.
- **Fehlermeldungen, Pfade, Fließtext** neben anderen Elementen: `ui-break`.
- **Knöpfe** neben solchem Text behalten ihre Breite (`flex-shrink: 0`); im Dialogkopf passiert
  das schon, dort gibt nur `.ui-dialog-title` nach.
- In App-CSS dasselbe mit eigener Klasse: `min-width: 0` plus Ellipsis oder `overflow-wrap: anywhere`.

## Feedback

```html
<div id="app-toasts" role="status">…</div>  <!-- Toast-Container (fixed bottom-right), legt loading.js beim Laden selbst an -->
<div class="app-toast visible ok">…</div>  <!-- success-Toast -->
<div class="app-toast visible err">…</div> <!-- error-Toast -->

<div class="app-loader">                <!-- Vollflächiger Overlay-Loader -->
  <span class="app-loader__spinner"></span>
  <span class="app-loader__label">Lädt…</span>
</div>

<span class="badge">Tag</span>
<span class="status-dot online"></span>
<span class="status-dot offline"></span>

<div class="hidden">…</div>      <!-- display:none !important, global Utility -->
```

## Bewegung (Micro-Animationen)

Kommt aus `root.min.css` und `ui.js` und gilt auf jeder Seite ohne eigenen Code. Alles steht in
`@media (prefers-reduced-motion: no-preference)`; bei reduzierter Bewegung bleibt die Seite ruhig. Bewegt werden nur `scale`, `translate`, `rotate` und `opacity`,
nie `transform`: ein App-eigenes `transform` (Zentrieren, gedrehter Regler) bleibt so unberührt.

| Was | Wo | Wie |
|---|---|---|
| Druck | Buttons, Chips, `.avatar` | `scale: var(--press-scale)` (.97) beim Drücken |
| Druck, breit | `.tile`, klickbare `ui-row` | `--press-scale-wide` (.99) |
| Hover | `.btn` | hebt sich 1 px an, setzt beim Drücken wieder auf |
| Aufklapper | `ui-details` | Inhalt steigt beim Öffnen auf, der Pfeil dreht mit |
| Icon zeigt die Aktion | lucide-Icons in Links und Buttons bei Hover/Fokus | Pfeile und Chevrons 2 px in ihre Richtung, Download nach unten, Plus/X drehen 90°, Refresh 180°, Zahnrad 60°, Play/Suche/Stern wachsen |
| Regler | `ui-range` | Daumen wächst beim Ziehen |
| Laden | `ui-skeleton` | mehrere Zeilen pulsieren versetzt |
| Seite öffnet | direkte Kinder von `main.ui-page` | steigen gestaffelt auf (`--dur-enter`, `--stagger`) |
| Scrollen | Blöcke in `ui-page`, `ui-section`, `ui-list`, `.grid` | was beim Hinzufügen unterhalb des Sichtbereichs liegt, blendet beim Hineinscrollen ein |
| Knopf arbeitet | `window.ui.busy(knopf, true)` | `aria-busy`, gesperrt, Kreis statt Icon; `ui.busy(knopf, false)` hebt es auf |

Einblenden beim Scrollen: was beim Laden oder Neurendern schon sichtbar ist, wird nie versteckt,
Polling-Listen flackern also nicht. Ein Bereich, der nicht einblenden soll (etwa ein Editor mit
eigener Bewegung), bekommt `data-no-reveal`; Dialoge sind ausgenommen. Eine App, die selbst
`animation` auf ein direktes Kind von `ui-page` setzt, gewinnt (die Regel hat Spezifität null).

## Hover-Patterns (konsistent über alle Apps)

- **Buttons**: leichter Background-Tint (Glass wird etwas heller)
- **Tiles/Karten**: Lift `translateY(-2px)` + heller Background
- **Primary/Danger-Buttons**: Tint in der jeweiligen Farbe + dunklere Border

## Kompakte Medienkarten und Details

```js
const card = window.ui.mediaCard({
  src: '/api/audio/file', title: 'Aufnahme', meta: 'WAV · Heute',
  href: '/aufnahme?id=123', duration: 12,
  download: { href: '/api/audio/download', filename: 'aufnahme.wav' },
});
host.append(card.el);
```

Der native Titel-Link öffnet die Unterseite unabhängig von Play/Seek und Download.
Titel erhalten maximal zwei Zeilen, Metadaten eine Zeile mit Ellipse. In Listen
steht nur der Download im Kopf. Bei einem endgültigen Audiofehler wird er verborgen.
`setSrc()` wechselt die Abspielquelle; Titel, Detail-Link und der separate Download
bleiben am Datensatz. Für einen anderen Datensatz die Karte neu erstellen und die alte
mit `destroy()` freigeben.
`mediaCard` gibt die Player-API einschließlich `audio`, `setSrc` und `destroy` zurück.
`ui.player({layout:'stacked'})` verwendet auf Unterseiten die gleiche Anordnung:
Play und Wellenform nebeneinander, Zeit darunter. Ohne `layout` bleibt die bisherige
Player-Anordnung erhalten.

```html
<dl class="ui-media-facts">
  <div><dt>Dauer</dt><dd>0:12</dd></div>
  <div><dt>Format</dt><dd>WAV</dd></div>
</dl>
<div class="ui-media-actions" role="group" aria-label="Aufnahmeaktionen">
  <button type="button" class="btn sm">Bearbeiten</button>
  <button type="button" class="btn sm danger">Löschen</button>
</div>
```

Kennzahlen stehen kompakt nebeneinander und umbrechen bei Platzmangel. Detailaktionen
verwenden bestehende Buttons mit mindestens 44px Höhe und umbrechen als Gruppe.
