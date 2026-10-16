# Idee 36: Terminal-Reiter mit einer Electribe-Bibliothek

Stand: gebaut (Bibliothek `src/korg.mjs`, Seite Terminal). Am echten Gerät nicht erprobt. Zurück zu den [Ideen](../ideen.md).

Eine JS-Bibliothek im Tool, etwa `KORG.screen.set(bild)` oder `KORG.ram.read(adresse, n)`, und im UI ein Reiter „Terminal“, in dem man sie aufruft. Was man tippt, geht an den Emulator; mit der echten Electribe verbunden geht es erst nach einer bestandenen Probe im Emulator auch ans Gerät. Die Bibliothek baut auf Gerätekarte, `DeviceSession`, Display im RAM (`0xC031B310`), LED-Setter und Panel-Nachrichten auf.

## Stand

- Am Gerät nur über den Emulator: jedes Skript läuft zuerst dort, nur ein bestandenes geht als genau dieselben Nachrichten ans Gerät, ohne Schalter. Siehe [Architektur](../architektur.md#terminal-und-echtes-gerät-erst-der-emulator-dann-das-gerät).
- `KORG.exec` führt ARM-Code als geprobte Einheit aus (Vorbereitung für Idee 34).
- Geprüft nur mit Fakes und im Ersatz für den Emulator-Dienst.
- RAM erforschen: `KORG.ram.snapshot`, `diff`, `search` und `where` lesen unbekanntes RAM und blenden aus, was schon erklärt ist (Idee 11, [unten](#ram-erforschen-idee-11)). Nur gegen die Simulation geprüft, am Gerät nicht erprobt.
- Ein Objektzugriff wie `KORG.ram.MFX_Presets[0].name = …` (Idee 8) ist nicht gebaut; die Bibliothek liest bisher RAM-Bereiche und Effektnamen.

## RAM erforschen (Idee 11)

Für die Suche nach Zuständen und Zeigern, die niemand zugeordnet hat. Alles ist Lesen, durch denselben Weg wie `KORG.ram.read` und durch dieselbe Sperrliste: kein Flash, keine DSP-Ports, RAM nur im vermessenen Fenster (`0xC0000000` bis `0xC8000000`). Der Bereich wird einmal vor dem ersten Lesen geprüft, ein Verbot kommt also vor dem ersten Block und nicht mittendrin.

| Aufruf | Was sie tut |
|---|---|
| `KORG.ram.snapshot({ from, to })` | hält einen Bereich fest; `to` ist das Ende ohne das Byte selbst. Auch `snapshot(from, to)` und `{ from, length }` gehen |
| `KORG.ram.diff(a, b)` | vergleicht zwei Snapshots, liefert die geänderten Läufe mit alt und neu und mit dem nächsten bekannten Bereich; `.summary()` ist die Kurzfassung, das Terminal druckt sie von selbst |
| `KORG.ram.search(wert, { from, to })` | sucht eine Zahl (32 Bit, little endian, `width: 1` oder `2` für kürzere), Bytes oder Text; `{ snapshot }` sucht in einem Snapshot, ohne zu lesen |
| `KORG.ram.where(adr)` | sagt, was an einer Adresse bekannt ist und ob eine Suche es ausblendet |

Ein Beispiel: erst festhalten, dann am Emulator etwas tun (eine Taste, ein Menü), dann noch einmal festhalten und vergleichen.

```js
const a = await KORG.ram.snapshot({ from: 0xC0300000, to: 0xC0360000 });
await KORG.press("menu");
await new Promise(r => setTimeout(r, 500));   // die Firmware soll fertig gezeichnet haben
const b = await KORG.ram.snapshot({ from: 0xC0300000, to: 0xC0360000 });
KORG.ram.diff(a, b)
```

**Was ausgeblendet wird.** Drei Quellen, ohne dass eine Zahl doppelt steht ([data/known-ram.mjs](../../data/known-ram.mjs)): die Gerätekarte bis zum einzelnen Feld (ein Feld mit `source: "unknown"` bleibt sichtbar), die Sperrliste und die [Speicherkarte](../speicherbereiche.md), und die Pattern-Slots. Ausgeblendet wird nur, was *erklärt* ist, nicht schon, was bekannt liegt. Vier Gruppen, die `show` zurückholt (`{ show: ["image"] }`):

- `image`: Code und statische Daten der Firmware
- `system`: Task-Stacks, Kontrollblöcke, Interrupt- und Startstack
- `map`: die Felder der Gerätekarte (Effekt-Presets, Samples, Display, Zeiger)
- `patterns`: die 250 Pattern-Slots, Feld für Feld

Heap, Arbeitspuffer, Sample-Info-Cache und die Systemdaten zwischen den Stacks bleiben sichtbar: ihr Zweck ist bekannt, ihre Bytes nicht. Sie dienen nur dazu, einen Lauf zu benennen (`in Heap (+0x40)`, sonst `0x20 Byte hinter Sample, Metadaten 12, 0x10 Byte vor Heap`). `{ mask: false }` liest und zeigt alles.

**Wie gelesen wird.** In Blöcken zu 4096 Byte (`chunk`, höchstens 16384), einer nach dem anderen, jeder wartet auf seine Antwort; `pauseMs` legt Pausen dazwischen. Ein Block, der durchgehend erklärt ist, wird gar nicht gelesen. Schon ein einziges unerklärtes Byte darin liest ihn ganz. Mehr als 4 MiB auf einmal verlangt `limit`. Fortschritt druckt das Terminal beim Lauf: eine Zeile am Anfang, dann alle zehn Prozent (`progress: false` schaltet das ab, eine Funktion übernimmt es).

**Grenzen, offen:**

- Die obere Hälfte des Fensters wird nur benannt (`im vermuteten Spiegel: ...`), nicht ausgeblendet; dass sie ein Spiegel ist, ist nicht bewiesen.
- Heap-Objekte, auf die die Zeiger der Gerätekarte zeigen, sind nicht aufgelöst; ausgeblendet wird nur das Zeigerwort selbst.
- Dass ein Pattern-Slot im RAM die Belegung der Gerätekarte hat, ist hergeleitet (PTST und PTED, Init-Pattern), nicht Feld für Feld gelesen. Die Gruppe `patterns` ist deshalb einzeln zuschaltbar.
- Im Terminal läuft Lesen im Emulator (siehe oben). Die Werkzeuge selbst (`src/ramsearch.mjs`) nehmen jeden Leser; `test/ramsearch.test.mjs` lässt sie über eine Gerätesitzung und über das Terminal laufen und bekommt dieselben Bytes.

## Bekannte Grenzen

Ins Display-RAM geschrieben hält nur bis zum nächsten Neuzeichnen der Firmware. Der Emulator kennt den Zustand des Geräts nicht.
