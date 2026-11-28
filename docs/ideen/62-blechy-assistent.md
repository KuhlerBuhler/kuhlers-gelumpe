# Idee 62: Blechy schreibt Plugins

Status: geplant, keiner Version zugeordnet, nicht gebaut. Zurück zu den [Ideen](../ideen.md).

Auf der Seite Plugins sitzt im Editor unten rechts der Kopf von [Blechy](../glossary.md#blechy). Ein Klick öffnet einen
kleinen Chat: man beschreibt, was das [Plugin](../glossary.md#plugin) tun soll, und Blechy schreibt den Code. Fragen und
Änderungswünsche gehen im selben Chat weiter. Das Sprachmodell läuft auf dem eigenen Rechner, nichts geht an einen
Server. Gedacht für Leute, die ohne Programmieren eigene Plugins bauen wollen. Nur im Editor der Seite Plugins.

## Entscheidung: llama.cpp als zweiter Dienst der App

Gewählt ist `llama-server` aus llama.cpp, von der App gestartet wie der Emulator-Dienst: läuft auf macOS (Metal), Windows
und Linux (Vulkan oder CPU), liest GGUF direkt, bringt Chat und Embeddings über dieselbe Schnittstelle. Verworfen: MLX
(nur Mac) und WebLLM im Browser (braucht WebGPU in der Webview, ungeprüft; die App gibt es nur als App, damit fällt der
Vorteil weg).

## Modelle

| Rolle | Modell | Wann |
|---|---|---|
| Chat, Standard | Gemma 4 E2B it, QAT, Q4 als GGUF | immer |
| Chat, groß | Gemma 4 E4B it, QAT, Q4 als GGUF | wenn der Rechner genug hat, wählbar |
| Embeddings | EmbeddingGemma 300M als GGUF | für die Suche in der Doku |

Das Modell lädt nur auf Klick, mit Größe und Quelle vorher im Dialog, ins Datenverzeichnis der App (nicht in den
Browser-Cache), mit Fortschritt, Fortsetzen nach Abbruch und Prüfsumme. Danach bleibt es liegen. Ohne diesen Klick geht
nichts ins Netz. Ab welchem RAM E4B angeboten wird (Vorschlag: 16 GB mit GPU), wird erst gemessen.

## Ablauf im Chat

1. Die Frage (bei Folgefragen mit dem aktuellen Code) wird eingebettet und sucht in der Doku: `docs/plugins.md` ab der
   Sprachreferenz, dazu die Vorlagen und Katalog-Plugins als Beispielcode. Nach Überschriften geteilt, zur Bauzeit
   eingebettet; ohne Embedding-Modell fällt die Suche auf eine Wortsuche (BM25) zurück.
2. Das Modell bekommt Systemtext, Doku-Stücke (Budget rund 3000 Token), Code, Verlauf und Frage.
3. Die Seite übersetzt den Code mit `compile` aus `src/script/compiler.mjs`. Fehler gehen mit den passenden Doku-Stücken
   höchstens zweimal zurück ans Modell, dann zeigt Blechy den Fehler und fragt.
4. Übersetzt der Code, läuft die Probe wie beim Knopf Proben (`SimDevice` und `probe` aus `src/script/sim.mjs`).
5. Der Code landet nicht von selbst im Editor: ein Knopf "In den Editor" ersetzt den Inhalt, ein Rückgängig holt den alten
   zurück.

Die Skriptsprache ist eine eigene, ein kleines Modell kennt sie nicht aus dem Training. Darum tragen die Doku-Stücke und
die Schleife über den Übersetzer die Arbeit.

## Messungen mit den elf Katalog-Plugins

Eingabe war Beschreibung und Steuerung jedes Katalog-Plugins, nie ihr Code; die Ausgabe ging durch `compile` und `probe`.
Ein Lauf je Plugin und Fassung, die Zahlen streuen. Lauffähig heißt nur: übersetzt und besteht die Probe. Alles **gemessen**
mit llama.cpp (Metal) auf einem Mac mit 32 GB.

| Modell | ohne Denkphase | mit Denkphase |
|---|---|---|
| Gemma 4 E2B QAT (2,6 GB) | 3 von 11 | 6 von 11 |
| Gemma 4 E4B QAT (4,2 GB) | 5 von 11 | 7 von 11 |
| LFM2.5-8B-A1B (5,2 GB) | nicht gemessen | 6 von 11 |
| Mellum2.1 12B-A2.5B (8,1 GB) | 3 von 11 | 7 von 11 |

- Die Fehler sind JavaScript-Gewohnheiten (Objekte, leere Felder, Kommazahlen) und erfundene Namen wie `korg.key.ONE`.
  Mehr Doku im Prompt oder ein vollständiges Verzeichnis aller `korg.*`-Aufrufe half keinem Modell. Eine Reparatur über
  die Fehlermeldung trug kaum (von 53 Reparaturen machte eine das Plugin lauffähig).
- Die Denkphase ist der größte Hebel: jedes Modell gewinnt zwei bis vier Plugins, die erste Antwort braucht dann aber
  eine bis mehrere Minuten.
- Ob die lauffähigen Plugins tun, was beschrieben war, prüfte eine Bedienprobe im Simulator mit den 7 lauffähigen von
  E4B: ganz wie beschrieben war keins, ungefähr richtig 4. Fast alle Fehler sind rohe Zahlen statt Namen für Tasten und
  LEDs, das falsche Ereignis für Pads und der Wertebereich des Touchpads. Eine Prüfung nach dem Übersetzen, die das als
  Fehler meldet, verschob die Fehler, ohne sie zu beheben (E4B: 1 von 11 ganz richtig).
- Entschieden: Es bleiben E2B und E4B, ein Modell von rund 8 GB ist für den Zweck zu viel.

## Reihenfolge

1. Messung vorab: für E2B und E4B gemacht, für andere Kandidaten offen. Ohne brauchbare Quote kein Bau.
2. `src/assist/`: Stücke, Suche, Prompt, Code aus der Antwort ziehen, Fehlerschleife; testbar ohne Modell.
3. Chat-Komponente mit einem Dienst, den der Nutzer selbst startet.
4. Rust: Download mit Prüfsumme, Start und Ende von `llama-server`, Erkennung von RAM und GPU.
5. Embeddings: Index zur Bauzeit, Abfrage zur Laufzeit, BM25 als Rückfall.
6. `llama-server` für die drei Plattformen ins App-Paket.

## Offen

- Welches Modell schafft deutlich mehr als 7 von 11 und tut, was beschrieben war? Weitere Wege: das Modell füllt ein
  festes Gerüst (Variablen oben, je Ereignis ein Handler), die Seite schickt nur die fehlerhafte Zeile zurück, Beispielcode
  aus dem Katalog zur Frage, ein auf die Skriptsprache nachtrainiertes Modell.
- Dateinamen, Größen, Prüfsummen und Lizenz der Modelle als GGUF.
- Grenzen für E4B (RAM, GPU, Token pro Sekunde).
- Größe des App-Pakets mit `llama-server` je Plattform.
