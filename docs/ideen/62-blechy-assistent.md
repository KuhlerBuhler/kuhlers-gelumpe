# Idee 62: Blechy schreibt Plugins

Stand: geplant für 1.4, nicht gebaut. Zurück zu den [Ideen](../ideen.md).

Auf der Seite Plugins, im Editor, sitzt unten rechts Blechys Kopf. Ein Klick öffnet einen kleinen
Chat. Dort beschreibt man, was das Plugin tun soll, und Blechy schreibt den Code dazu. Fragen und
Änderungswünsche gehen im selben Chat weiter. Das Sprachmodell läuft auf dem eigenen Rechner, nichts
geht an einen Server. Damit soll man eigene Plugins bauen und proben können, ohne programmieren zu
können.

Nur im Editor der Seite Plugins, sonst nirgends.

## Entscheidung: llama.cpp als zweiter Dienst der App

Drei Wege standen zur Wahl. Gewählt ist `llama-server` aus llama.cpp, gestartet von der App wie
schon der Emulator-Dienst.

| Weg | Für | Gegen |
|---|---|---|
| **llama.cpp (`llama-server`)** | läuft auf macOS (Metal), Windows und Linux (Vulkan oder CPU), also auf allen drei Builds aus `build-apps.yml`; liest GGUF direkt; bringt Chat und Embeddings mit derselben Schnittstelle; die App startet schon einen Dienst auf `127.0.0.1` mit Token und erlaubtem Ursprung (`src-tauri/src/main.rs`), der zweite folgt demselben Muster | eine Binärdatei mehr je Plattform im Paket |
| MLX | auf Apple Silicon etwas schneller (geschätzt, nicht gemessen) | nur Mac, braucht Python oder eine eigene Swift-Brücke; zwei Wege für ein Ergebnis |
| WebLLM im Browser | kein Dienst nötig | braucht WebGPU in der Webview der App (WKWebView, WebView2, WebKitGTK verhalten sich verschieden, ungeprüft); das Modell liegt im Browser-Cache, den das System leeren kann; Gemma 4 als fertiges WebLLM-Modell nicht gesehen |

Hergeleitet: Die App gibt es nur als App, nie als Seite im fremden Browser
([Architektur](../architektur.md)). Damit fällt der wichtigste Vorteil von WebLLM weg. MLX kann später
dazukommen, wenn eine Messung am Mac einen deutlichen Abstand zeigt; die Seite spricht dann mit
derselben Schnittstelle.

## Modelle

Die Chat-Modelle sind der erste Entwurf. Ohne Denkphase reichen Gemma 4 E2B und E4B nicht, mit
Denkphase reichen sie für 6 und 7 von 11 Plugins (siehe die vierte Messung unten). Es bleibt bei E2B
und E4B, größere Modelle kommen nicht in Frage.

| Rolle | Modell | Wann |
|---|---|---|
| Chat, Standard | Gemma 4 E2B it, QAT, Q4 als GGUF | immer |
| Chat, groß | Gemma 4 E4B it, QAT, Q4 als GGUF | wenn der Rechner genug hat (siehe unten), wählbar |
| Embeddings | EmbeddingGemma 300M als GGUF | für die Suche in der Doku |

QAT, weil die Gewichte schon beim Training auf 4 Bit vorbereitet sind: kleiner als die volle Fassung
und näher an ihrer Qualität als ein nachträglich gerechnetes Q4. Kandidat für die Quelle ist
`unsloth/gemma-4-E2B-it-qat-GGUF` (Quant `UD-Q4_K_XL`), dazu dasselbe für E4B. Dateigrößen, Lizenz
und welche Datei genau sind offen und werden vor dem Bau auf der Modellseite nachgesehen.

**Wann E4B.** Die App liest beim Start den Arbeitsspeicher und ob eine GPU da ist (Metal am Mac,
Vulkan sonst). Vorschlag, geschätzt: ab 16 GB RAM mit GPU wird E4B angeboten, darunter nur E2B. Danach
misst die App die ersten Antworten (Token pro Sekunde) und schlägt E2B vor, wenn E4B zu langsam ist.
Die Grenzen werden an einem Mac mit 8 GB, einem mit 16 GB und einem Windows-Rechner ohne GPU gemessen,
bevor sie fest werden.

### Einmal laden, dann liegt es

- Das Modell lädt nur auf Klick, mit Größe und Quelle vorher im Dialog. Ohne diesen Klick geht nichts
  ins Netz; die App sendet weiterhin keine Nutzungsdaten.
- Ziel ist das Datenverzeichnis der App (`app_data_dir` von Tauri, unter `models/`), nicht der
  Browser-Cache. Ein Neustart, ein Update der App und ein geleerter Webview-Speicher lassen es liegen.
- Der Download läuft in Rust, mit Fortschritt, Fortsetzen nach Abbruch und Prüfung gegen eine
  SHA-256-Summe, die in der App steht. Erst eine geprüfte Datei bekommt ihren endgültigen Namen.
- In den Einstellungen: welches Modell da ist, wie groß, und Löschen.

## Ablauf im Chat

1. **Frage einbetten.** Die Nachricht des Nutzers, dazu bei Folgefragen der aktuelle Code, geht an den
   Embedding-Dienst.
2. **Doku suchen.** Die Doku ist zur Bauzeit in Stücke geteilt und eingebettet (siehe unten). Die Seite
   nimmt die besten Stücke, bis ein festes Budget voll ist (Vorschlag: rund 3000 Token). Immer dabei ist
   ein kurzer fester Teil: Aufbau eines Plugins, die Handler, die Grenzen.
3. **Antwort.** Das Modell bekommt Systemtext, die Doku-Stücke, den aktuellen Code, den Verlauf und
   die Frage. Code steht in der Antwort in einem Block.
4. **Übersetzen.** Die Seite übersetzt den Block mit `compile` aus `src/script/compiler.mjs`.
   Fehler (Zeile, Spalte, Text aus `formatError`) gehen ohne Zutun des Nutzers mit den passenden
   Doku-Stücken zurück ans Modell, höchstens zweimal. Danach zeigt Blechy den Fehler und fragt.
5. **Proben.** Übersetzt der Code, läuft die Probe wie beim Knopf Proben (`SimDevice` und `probe` aus
   `src/script/sim.mjs`). Was die Probe meldet, geht bei der nächsten Frage mit.
6. **Übernehmen.** Der Code landet nicht von selbst im Editor. Ein Knopf „In den Editor“ ersetzt den
   Inhalt, ein Rückgängig im Editor holt den alten zurück. Bei einem Plugin aus dem Katalog legt der
   Knopf ein eigenes Plugin an, wie „Als eigenes Plugin öffnen“.

Die Skriptsprache ist eine eigene ([Plugins](../plugins.md)). Ein kleines Modell kennt sie nicht aus
dem Training. Darum tragen die Doku-Stücke und die Schleife über den Übersetzer die Arbeit, nicht das
Modell allein. Ob E2B damit lauffähige Plugins schreibt, ist die erste offene Frage und wird mit den
Beispielen aus dem Katalog gemessen (Beschreibung rein, übersetzt und probt es?).

## Doku als Index

- **Quelle:** `docs/plugins.md` ab der Sprachreferenz bis zu den Beispiel-Plugins, dazu die Vorlagen aus
  `data/script/templates.mjs` und die Plugins aus `data/script/presets.mjs` als Beispielcode.
  Abschnitte über Karte, Menü am Gerät und Stand bleiben draußen.
- **Stücke:** nach Überschriften `###`, lange Abschnitte an Absätzen geteilt, jedes Stück mit seiner
  Überschrift davor.
- **Zur Bauzeit:** `tools/build-site.mjs` ruft einen Schritt, der die Stücke mit EmbeddingGemma einbettet
  und als Datei neben die Seite legt. Zur Laufzeit wird nur die Frage eingebettet.
- **Ohne Embedding-Modell:** fällt die Suche auf eine Wortsuche (BM25) über dieselben Stücke zurück.
  Ein Test hält fest, dass der Index zur aktuellen Doku passt, sonst schlägt er fehl.

## Dienst und Schnittstelle

- Rust startet `llama-server` erst beim ersten Öffnen des Chats, nicht beim Start der App, auf einem
  freien Port mit eigenem Token, nur auf `127.0.0.1`, mit denselben erlaubten Ursprüngen wie der
  Emulator-Dienst. Der Emulator bekommt Port und Token beim Start über `#emu=port:token` in der
  Adresse; weil der Chat-Dienst erst später startet, fragt die Seite ihn über einen Tauri-Befehl an und
  bekommt Port und Token als Antwort.
- Zwei Prozesse: einer für Chat, einer mit `--embeddings` für EmbeddingGemma. Ob die Embeddings mit den
  Werten aus SentenceTransformers übereinstimmen, wird einmal geprüft.
- Die Seite spricht die OpenAI-artige Schnittstelle von `llama-server` (`/v1/chat/completions` mit
  Streaming, `/v1/embeddings`). Ein Modul `src/assist/` baut den Prompt, sucht in der Doku und zieht den
  Code aus der Antwort; es läuft ohne `node:`-Importe im Browser und ist ohne Modell testbar.
- Schließt der Chat für ein paar Minuten, beendet die App den Chat-Prozess und gibt den Speicher frei.

## Die Chat-Komponente

- **Knopf:** rund, unten rechts im Editor, Blechys Kopf aus den Bildern in `site/img/blechy/`
  (Pixelgrafik, `image-rendering: pixelated`). Gesicht nach Zustand: `idle` wartet, `happy` nach einem
  Code, der übersetzt und probt, `sad` nach einem Fehler, `loaded` während des Downloads.
- **Fenster:** klappt über dem Knopf auf, feste Breite, auf schmalen Bildschirmen über die ganze
  Breite. Kopfzeile mit Blechy, Modellname und Schließen. Darunter der Verlauf, unten ein Eingabefeld
  (Enter sendet, Shift+Enter neue Zeile) und Stopp während einer Antwort.
- **Nachrichten:** Text als Markdown über `site/app/markdown.mjs`, Code mit derselben Färbung wie der
  Editor, darunter „In den Editor“ und der Zustand (übersetzt, Fehler in Zeile n, geprobt).
- **Kein Modell:** statt des Verlaufs eine Karte mit E2B, Größe und Laden; E4B daneben, wenn der Rechner
  es hergibt. Fortschritt als Zeile in der Karte, Fehler als Toast.
- **Verlauf:** je Plugin im `localStorage`, wie die Plugins selbst. Ein Knopf leert ihn.
- **Klassen** mit `cee-assist-`, Farben und Abstände aus den Tokens ([DESIGN.md](../../DESIGN.md)).
  Tastatur: der Knopf ist erreichbar, Escape schließt, der Fokus geht zurück in den Editor.

## Erste Messung: E2B allein reicht nicht

Gemessen am 25.10. mit `llama-server` (llama.cpp 0.5.0, Metal) und
`gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` (2,62 GB) auf einem Mac mit 32 GB. Eingabe war die Beschreibung
und die Steuerung jedes der elf Katalog-Plugins, nie ihr Code. Als Beispiel gab es die Vorlage „App in
GAMES“. Die Ausgabe ging durch `compile` und `probe` mit festen Eingaben (Tasten, Pads, Touchpad,
Drehgeber). Bei einem Fehler gingen die Meldung und die Bitte um den ganzen korrigierten Code zurück,
höchstens zweimal. Je Plugin und Fassung ein Lauf, Temperatur 0,3. Die Zahlen streuen also.

| Fassung | Doku im Prompt | lauffähig | davon erst nach Reparatur |
|---|---|---|---|
| Suche | rund 3700 Token, Wortsuche über die Sprachreferenz | 2 von 11 | 0 |
| Ganze Referenz | rund 13200 Token | 2 von 11 | 1 |
| Suche und Regeln | wie Suche, dazu acht feste Regeln zu den Unterschieden zu JavaScript, bei einem Fehler die Zeile im Wortlaut | 3 von 11 | 0 |

Lauffähig waren nur Lauflicht, Pulsieren und in der dritten Fassung BLECH Clicker, also die kürzesten.
Spiele und Werkzeuge mit Feldern und Zustand scheiterten alle beim Übersetzen.

- **Die Fehler sind JavaScript-Gewohnheiten:** leere Felder `[]`, Objekte, Kommazahlen, ein Ausdruck
  nach `=>`, erfundene Namen wie `korg.key.ONE`, `korg.touch.get` oder `korg.display.textNumber` mit
  falschen Argumenten.
- **Die Reparatur trägt nicht:** von 53 Reparaturen machte eine das Plugin lauffähig. Meist schrieb
  das Modell denselben Fehler in dieselbe Zeile.
- **Mehr Doku hilft nicht:** die ganze Referenz war nicht besser als die Suche, nur langsamer.
- **Tempo:** rund 60 Token je Sekunde, eine erste Antwort in 6 bis 30 Sekunden.

### Zweite Messung: E4B und feste Korrekturen

Gleicher Aufbau, dazu ein Schritt, der vor jeder Rückfrage ans Modell die häufigsten Fehler selbst
richtet: Kommazahl runden, leeres Feld auf 256 Plätze, Feld leeren statt neu zuweisen, Block nach
`=>`, `Math.floor` weglassen, unbekannte Tastennamen (`korg.key.ONE` wird `korg.key.BAR_1`, sonst der
erste Vorschlag des Übersetzers). Gemessen am 25.10. mit `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` (4,22 GB).

| Modell | Fassung | lauffähig | Tempo |
|---|---|---|---|
| E2B | Suche, Regeln, feste Korrekturen | 3 von 11 | rund 58 Token je Sekunde |
| E4B | Suche, Regeln, feste Korrekturen | 5 von 11 (Set-Timer, Tetris, Mandelbrot, Lauflicht, Pulsieren) | rund 33 Token je Sekunde, 15 bis 125 Sekunden je Plugin |

Die festen Korrekturen allein machten aus den 86 Ausgaben der ersten Messung 14 statt 10, die
übersetzen. Bei E4B wurden zwei Plugins erst durch eine Reparatur lauffähig. „Lauffähig“ heißt nur:
übersetzt und besteht die Probe. Ob das Plugin tut, was beschrieben war, ist nicht geprüft.

Hergeleitet: Gemma 4 E2B und E4B reichen für das Ziel nicht. Die restlichen Fehler sind erfundene
Namen und JavaScript-Muster (Objekte, `push`, Text verbinden), die keine feste Regel auffängt.

### Dritte Messung: anderer Input, MoE-Modelle

Frage war, ob es am Input liegt statt am Modell. Die zweite Fassung des Inputs ersetzt die Wortsuche
durch ein vollständiges Verzeichnis, erzeugt aus `data/script/contract.mjs`, `describe.mjs`,
`names.mjs` und `properties.mjs`: jeder `korg.*`-Aufruf mit Argumenten und Wertebereich, die
Eigenschaften, die Ereignisse mit ihren Werten, alle Tasten- und LED-Namen. Dazu kommen der Abschnitt
Sprache und zwei Katalog-Plugins mit ähnlicher Beschreibung als Beispiel, nie das geprüfte selbst
(rund 6400 bis 8400 Token). Regeln und feste Korrekturen wie in der zweiten Messung. Gemessen am 25.10.,
je Plugin ein Lauf.

| Modell | Datei | alter Input (Suche) | neuer Input (Verzeichnis, Beispiele) | Tempo |
|---|---|---|---|---|
| Gemma 4 E2B QAT | 2,6 GB | 3 von 11 | 2 von 11 | rund 60 Token je Sekunde |
| Gemma 4 E4B QAT | 4,2 GB | 5 von 11 | 3 von 11 | rund 37 |
| Mellum2.1 12B-A2.5B Thinking, ohne Denkphase | 8,1 GB | 3 von 11 | 3 von 11 | rund 60 mit kurzem, 30 mit langem Prompt |
| LFM2.5-8B-A1B, mit Denkphase | 5,2 GB | 6 von 11 | 1 von 11 | rund 95, aber 6000 bis 33000 Zeichen Denktext je Antwort, 20 bis 170 Sekunden je Plugin |

- **Der neue Input half keinem Modell.** Auch mit der Signatur im Verzeichnis ruft E2B
  `korg.display.textNumber` mit drei Argumenten auf, Mellum erfindet `korg.key.PAD1`. Die übrigen
  Fehler sind Regeln der Sprache, die im Prompt stehen und trotzdem gebrochen werden: ein zweiter
  Handler für dasselbe Ereignis, ein Feld innerhalb einer Funktion, `++` in einem Ausdruck,
  Textvorlagen mit Backtick.
- **Die Denkphase hilft:** LFM2.5 mit Denkphase ist mit 6 von 11 das beste Ergebnis bisher, obwohl
  es kein Code-Modell ist. Mellum lief ohne Denkphase, weil der Prompt sie abschaltet; mit Denkphase
  ist es nicht gemessen.
- Ein Fehler der ersten Fassung des Prüfschritts zählte eine leere Antwort als lauffähig. Er traf nur
  einen ersten LFM-Lauf, der verworfen und wiederholt wurde; die übrigen Zahlen sind davon nicht
  betroffen.

Hergeleitet: Mehr oder genaueres Nachschlagewissen im Prompt bringt bei diesen Größen nichts. Was
noch offen ist, setzt an der Form an, nicht am Wissen:

- Mellum2.1 mit Denkphase (gemessen, siehe vierte Messung);
- das Modell schreibt nicht das ganze Plugin, sondern füllt ein festes Gerüst (Variablen oben, je
  Ereignis ein Handler), das die Seite zusammensetzt und so die häufigsten Regelbrüche gar nicht
  zulässt;
- die Seite gibt die Meldung des Übersetzers nicht als Text zurück, sondern lässt das Modell nur die
  eine fehlerhafte Zeile neu schreiben.

### Vierte Messung: alle mit Denkphase

In den Messungen davor schaltete der Prompt die Denkphase ab (`enable_thinking: false`). Nur LFM2.5
dachte trotzdem, weil seine Vorlage den Schalter nicht kennt. Hier denken alle, mit altem Input
(Suche, Regeln, feste Korrekturen) und höchstens 8000 Token je Antwort. Gemessen am 25.10., je Plugin
ein Lauf. Parallel lief ein anderes Modell in Ollama, die Zeiten sind darum zu langsam, die Zahl der
lauffähigen Plugins gilt.

| Modell | ohne Denkphase | mit Denkphase | Denktext je Antwort | Zeit je Plugin |
|---|---|---|---|---|
| Gemma 4 E2B QAT | 3 von 11 | 6 von 11 | 2000 bis 4000 Zeichen | 1 bis 9 Minuten |
| Gemma 4 E4B QAT | 5 von 11 | 7 von 11 | 3000 bis 9500 Zeichen | 1 bis 8 Minuten |
| LFM2.5-8B-A1B | nicht gemessen | 6 von 11 | 6000 bis 33000 Zeichen | 20 Sekunden bis 3 Minuten |
| Mellum2.1 12B-A2.5B | 3 von 11 | 7 von 11 | 9000 bis 29000 Zeichen | 1 bis 9 Minuten |

- **Die Denkphase ist der größte Hebel bisher:** jedes Modell gewinnt zwei bis vier Plugins.
- **E4B** schafft BLECH Clicker, Set-Timer, Game of Life, Simon, GIF Player, Lauflicht und Pulsieren.
  Snake, Tetris und Pong übersetzen, scheitern aber in der Probe an Werten außerhalb des erlaubten
  Bereichs (meist Koordinaten am Display).
- **Mellum** schafft BLECH Clicker, Tetris, Game of Life, Pong, Simon, Lauflicht und Pulsieren. In 9 von
  33 Antworten war das Limit von 8000 Token schon im Denken aufgebraucht, es kam kein Code. Mit mehr
  Token ist mehr drin, aber auch längere Wartezeit.
- Die erste Antwort braucht mit Denkphase meist eine bis mehrere Minuten. Für einen Chat ist das
  lang; ohne das zweite Modell im Hintergrund wären es geschätzt etwa halb so viele.

Entschieden: Es bleiben Gemma 4 E2B und E4B. Rund 8 GB wie bei Mellum sind für den Zweck zu viel,
E4B schafft mit 4,2 GB gleich viel. Offen ist, wie viel ein festes Gerüst und ein höheres Token-Limit noch bringen.

### Fünfte Messung: tun sie, was beschrieben war?

Die 7 lauffähigen Plugins von E4B im Simulator bedient, wie die Beschreibung es sagt (Pads, Tasten, Touchpad),
und LEDs und Display nachgesehen. Gemessen am 26.10.

| Plugin | Ergebnis |
|---|---|
| BLECH Clicker | zählt und speichert, der Kristall bleibt leer (Feld ohne Inhalt) |
| Pulsieren | pulsiert, aber nur auf 8 der 16 Pads (`PAD_1_RED`, `PAD_3_RED`, ...) |
| Set-Timer | PLAY startet, [1] nicht, [4] zweimal setzt nicht zurück (`key == 1`, `key == 4`) |
| GIF Player | Encoder wählt die Datei, das Tempo liegt auf einem Regler statt auf PART |
| Lauflicht | läuft über SHIFT, WRITE, HPF und andere Tasten-LEDs statt über die Pads (`korg.led(9 + i)`) |
| Game of Life | Touchpad zeichnet nichts (Koordinaten 0 bis 1023 als Zellindex), Start auf MENU statt [1] |
| Simon | Pads kommen als `buttonPress` 0 bis 15 statt als `pad`, die Folge leuchtet auf falschen LEDs |

Ganz wie beschrieben ist damit keins, ungefähr richtig sind 4. E2B (6 lauffähige) sieht ähnlich aus: Lauflicht
und Pulsieren leuchten auf falschen LEDs, Set-Timer, Tetris und Pong reagieren auf die Eingaben, im Detail nicht geprüft.

Fast alle Fehler sind dieselbe Art: rohe Zahlen statt Namen für Tasten und LEDs, das falsche Ereignis für Pads, der
Wertebereich des Touchpads. Das fängt weder der Übersetzer noch die Probe. Zwei Wege, beide ohne größeres Modell:

- Eine Prüfung nach dem Übersetzen meldet `korg.led(<Zahl>)`, `key == <Zahl>` und Touch-Werte als Index als Fehler,
  mit dem passenden Namen als Vorschlag. Dann repariert das Modell es wie einen Übersetzerfehler.
- Die Doku-Ausschnitte bekommen je Ereignis ein kurzes Beispiel mit Namen (`korg.led.PAD_1_RED + pad * 2`,
  `korg.onEvent("pad", ...)`, Touch 0 bis 1023 auf das Display umrechnen).

### Sechste Messung: Prüfung auf rohe Zahlen

Nach dem Übersetzen meldet eine Prüfung drei Fehler wie einen Übersetzerfehler, mit den richtigen Namen im Text:
`korg.led(...)` mit einer Nummer, die nicht aus einem `korg.led`-Namen kommt, `key == <Zahl>` in `buttonPress`,
und Touch-Werte, die ohne Umrechnung als Index oder Display-Lage landen. Die 11 Katalog-Plugins bestehen sie ohne
Meldung, in den Läufen davor findet sie die Fehler von Set-Timer, Life, Simon und Lauflicht. Gemessen am 26.10.,
Denkphase an, 8000 Token, Regeln und feste Korrekturen wie in der vierten Messung.

| Modell | lauffähig | tut, was beschrieben war |
|---|---|---|
| Gemma 4 E4B QAT, ohne Prüfung | 7 von 11 | 0 ganz, 4 ungefähr |
| Gemma 4 E4B QAT, mit Prüfung | 6 von 11 | 1 ganz (BLECH Clicker), 2 teilweise (GIF Player, Pulsieren) |
| CrowQwen3.5 4B Agent Heretic, Q4_K_M, 2,7 GB | 0 von 11 | - |

E4B schreibt mit der Prüfung keine rohen Zahlen mehr, nimmt aber falsche Namen: Set-Timer startet und setzt mit TAP
statt mit [1] und [4] zurück, Lauflicht blinkt nur auf Pad 1, Pong startet nie. Die Prüfung verschiebt die Fehler,
sie behebt sie nicht.

CrowQwen (Qwen3.5-4B, auf Code und Agent-Aufgaben nachtrainiert) denkt mit Denkphase bis zum Limit und gibt keinen
Code aus, bei 11 bis 22 Token je Sekunde, langsamer als E4B. Ohne Denkphase wiederholt es dieselbe Kommentarzeile
bis zum Limit oder schreibt das Beispiel aus dem Prompt ab. Fällt raus.

### Kandidaten für die nächste Messung

Stand 25.10., Größe der Q4-Datei laut Hugging Face, nicht gemessen.

| Modell | erschienen | Größe Q4 | Lizenz | Warum |
|---|---|---|---|---|
| Qwen3.5-4B | 02/2026 | 2,7 GB | Apache 2.0 | gleiche Klasse wie E4B, gilt als stark bei Code |
| Qwen3.5-9B | 02/2026 | 5,7 GB | Apache 2.0 | oft empfohlen für 8 GB Grafikspeicher |
| Granite 4.2 8B | 08/2026 | 5,4 GB | Apache 2.0 | GGUF vom Hersteller |
| LFM2.5-24B-A2B | 10/2026 | 13,6 GB | eigene | nur 2B aktiv, also schnell, braucht aber 16 GB RAM und mehr |
| Flint (40B, 2,5B aktiv) | 21.10.2026 | 23,4 GB | Apache 2.0 | neu, auf Code trainiert, braucht llama.cpp 0.7.0 und 32 GB RAM |

Kleine MoE-Modelle (viele Gewichte, wenige davon je Token aktiv: Speicher wie ein großes Modell,
Tempo wie ein kleines):

| Modell | erschienen | gesamt / aktiv | Größe Q4 | Lizenz | Warum |
|---|---|---|---|---|---|
| Mellum2.1 12B-A2.5B Thinking (JetBrains) | GGUF 10/2026 | 12B / 2,5B | 8,1 GB (MXFP4 7,0 GB) | Apache 2.0 | auf Code trainiert; laut Hersteller HumanEval+ 91,5, LiveCodeBench v6 82,0 (nicht nachgeprüft); denkt vor der Antwort, also mehr Token |
| Mellum2 12B-A2.5B Instruct (JetBrains) | 06/2026 | 12B / 2,5B | 8,1 GB | Apache 2.0 | dasselbe ohne Denkphase, kürzere Antworten |
| LFM2.5-8B-A1B (Liquid AI) | 05/2026 | 8,5B / 1B | 5,2 GB | eigene | allgemein, nicht auf Code; mit 1B aktiv sehr schnell |
| Ling-mini-2.0 (inclusionAI) | 09/2025 | 16B / 1,4B | offen | MIT | älter, allgemein |

Ob llama.cpp 0.5.0 die Bauart `mellum` schon lädt, ist nicht geprüft.

FrogNano 4B (Microsoft, 09/2026) ist ein Qwen3.5-4B, nachtrainiert für einen bestimmten Agenten-Rahmen
mit Python; für einen Chat ohne diesen Rahmen eher nicht.

Weiter offen als Weg: Beispielcode passend zur Frage aus dem Katalog statt nur Doku (beim Messen
ausgeschlossen, weil der Katalog die Prüfung war), und ein Modell, das auf die Skriptsprache
nachtrainiert ist.

## Reihenfolge

1. Messung vorab: für E2B und E4B gemacht (3 und 5 von 11), offen für die Kandidaten oben. Ohne
   brauchbare Quote kein Bau.
2. `src/assist/`: Stücke, Suche (erst BM25), Prompt, Code aus der Antwort ziehen, Fehlerschleife. Tests
   ohne Modell mit festen Antworten.
3. Chat-Komponente mit einem Dienst, den der Nutzer selbst startet (für die Entwicklung).
4. Rust: Download mit Prüfsumme, Start und Ende von `llama-server`, Erkennung von RAM und GPU.
5. Embeddings: Index zur Bauzeit, Abfrage zur Laufzeit, BM25 bleibt als Rückfall.
6. `llama-server` in `build-apps.yml` für die drei Plattformen ins Paket.

## Offen

- Welches Modell aus den Kandidaten schafft deutlich mehr als 5 von 11, und tun die lauffähigen
  Plugins auch, was beschrieben war?
- Dateinamen, Größen, Prüfsummen und Lizenz von Gemma 4 E2B, E4B und EmbeddingGemma als GGUF.
- Grenzen für E4B (RAM, GPU, Token pro Sekunde).
- WebGPU in den Webviews, falls WebLLM doch wieder gebraucht wird.
- Größe des App-Pakets mit `llama-server` je Plattform.
