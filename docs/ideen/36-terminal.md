# Idee 36: Terminal-Reiter mit einer Electribe-Bibliothek

Status: gebaut (Bibliothek `src/korg.mjs`, Seite `site/app/terminal.mjs`), am echten Gerät nicht erprobt. Offen ist ein
Objektzugriff. Zurück zu den [Ideen](../ideen.md).

Eine JS-Bibliothek im Tool, etwa `KORG.screen.set(bild)` oder `KORG.ram.read(adresse, n)`, und im UI ein Reiter "Terminal",
in dem man sie aufruft. Was man tippt, geht an den Emulator; mit der echten Electribe verbunden geht es erst nach einer
bestandenen Probe im Emulator auch ans Gerät, mit genau denselben Nachrichten und ohne Schalter. Aufbau und Regel:
[Architektur](../architektur.md#terminal-und-echtes-gerät-erst-der-emulator-dann-das-gerät). `KORG.exec` führt ARM-Code als
geprobte Einheit aus.

**Offen:** ein Objektzugriff wie `KORG.ram.MFX_Presets[0].parameter.level = 64`, aus dem der passende Gerätezugriff
entsteht. Die Bibliothek liest bisher RAM-Bereiche und Effektnamen. (`flash` bezeichnet nie einen Live-RAM-Zugriff.)

## RAM erforschen (Idee 11)

Für die Suche nach Zuständen und Zeigern, die niemand zugeordnet hat. Alles ist Lesen, über denselben Weg wie
`KORG.ram.read` und dieselbe Sperrliste ([Speicherbereiche](../speicherbereiche.md)): kein Flash, keine DSP-Ports, RAM nur im
vermessenen Fenster (`0xC0000000` bis `0xC8000000`). Nur gegen die Simulation geprüft.

| Aufruf | Was sie tut |
|---|---|
| `KORG.ram.snapshot({ from, to })` | hält einen Bereich fest; `to` ist das Ende ohne das Byte selbst. Auch `snapshot(from, to)` und `{ from, length }` gehen |
| `KORG.ram.diff(a, b)` | vergleicht zwei Snapshots, liefert die geänderten Läufe mit alt und neu und mit dem nächsten bekannten Bereich; `.summary()` ist die Kurzfassung, das Terminal druckt sie von selbst |
| `KORG.ram.search(wert, { from, to })` | sucht eine Zahl (32 Bit, little endian, `width: 1` oder `2` für kürzere), Bytes oder Text; `{ snapshot }` sucht in einem Snapshot, ohne zu lesen |
| `KORG.ram.where(adr)` | sagt, was an einer Adresse bekannt ist und ob eine Suche es ausblendet |

Beispiel: erst festhalten, am Emulator etwas tun (eine Taste, ein Menü), noch einmal festhalten und vergleichen.

```js
const a = await KORG.ram.snapshot({ from: 0xC0300000, to: 0xC0360000 });
await KORG.press("menu");
await new Promise(r => setTimeout(r, 500));   // die Firmware soll fertig gezeichnet haben
const b = await KORG.ram.snapshot({ from: 0xC0300000, to: 0xC0360000 });
KORG.ram.diff(a, b)
```

**Was ausgeblendet wird.** Nur was *erklärt* ist, aus drei Quellen ([data/known-ram.mjs](../../data/known-ram.mjs)): die
Gerätekarte bis zum einzelnen Feld (ein Feld mit `source: "unknown"` bleibt sichtbar), die Sperrliste und die
Speicherkarte, und die Pattern-Slots. Vier Gruppen, die `show` zurückholt (`{ show: ["image"] }`): `image` (Code und
statische Daten der Firmware), `system` (Task-Stacks, Kontrollblöcke, Interrupt- und Startstack), `map` (die Felder der
Gerätekarte) und `patterns` (die 250 Pattern-Slots, Feld für Feld). Heap, Arbeitspuffer, Sample-Info-Cache und die
Systemdaten zwischen den Stacks bleiben sichtbar und dienen nur dazu, einen Lauf zu benennen. `{ mask: false }` liest und
zeigt alles.

**Wie gelesen wird.** In Blöcken zu 4096 Byte (`chunk`, höchstens 16384), einer nach dem anderen, jeder wartet auf seine
Antwort; `pauseMs` legt Pausen dazwischen. Ein durchgehend erklärter Block wird gar nicht gelesen, ein einziges unerklärtes
Byte darin liest ihn ganz. Mehr als 4 MiB auf einmal verlangt `limit`.

**Grenzen, offen:**

- Die obere Hälfte des Fensters wird nur benannt (`im vermuteten Spiegel: ...`), nicht ausgeblendet; dass sie ein Spiegel
  ist, ist nicht bewiesen.
- Heap-Objekte, auf die die Zeiger der Gerätekarte zeigen, sind nicht aufgelöst; ausgeblendet wird nur das Zeigerwort.
- Dass ein Pattern-Slot im RAM die Belegung der Gerätekarte hat, ist hergeleitet (PTST und PTED, Init-Pattern), nicht Feld
  für Feld gelesen. Die Gruppe `patterns` ist deshalb einzeln zuschaltbar.

Die Werkzeuge selbst (`src/ramsearch.mjs`) nehmen jeden Leser; `test/ramsearch.test.mjs` lässt sie über eine Gerätesitzung
und über das Terminal laufen und bekommt dieselben Bytes. Ins Display-RAM Geschriebenes hält nur bis zum nächsten
Neuzeichnen der Firmware.
