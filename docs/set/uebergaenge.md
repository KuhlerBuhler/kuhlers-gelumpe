# Übergangs-Patterns für ein Set erzeugen

Zwei Werkzeuge in `tools/set/` arbeiten auf Pattern-Sicherungen (`.e2sallpat`)
und einzelnen Patterns (`.e2spat`):

- `transition.mjs` erzeugt Übergangs-Patterns zwischen zwei Patterns A und B.
- `stil.mjs` wertet die verketteten Patterns eines Sets aus und schreibt die
  wiederkehrenden Züge als Markdown auf die Standardausgabe.

Beide lesen nur. Ausgaben gehen außerhalb des Repositories, die Sicherung wird nie
verändert, und es stehen nur Werte in den Auswertungen, keine Pattern-Bytes.
Stand: im Emulator durchgespielt (`tools/set/emu-check.mjs`), am Gerät nicht
geprüft. Der Generator liegt in `src/transition.mjs` und läuft auch im Editor, auf der Seite
[Pattern-Werkzeuge](pattern-werkzeuge.md); `tools/set/transition.mjs` ist die Befehlszeile dafür. Wie ein erzeugtes Pattern auf die Karte und ins Gerät kommt, steht in
[pattern-aufspielen.md](pattern-aufspielen.md).

Jeder Übergang ist eine Bearbeitung einer Kopie von Pattern A. Records werden
bearbeitet, nie gebaut ([Gerätekarte](../geraetekarte.md), "Zwei Fallen"). Die Parts von B
kommen als Kopien von B's eigenen Part-Blöcken herein.

## Die Auswertung

`stil.mjs` verbindet jedes Pattern mit gesetztem Chain To (Byte `0x3B00`, siehe
[Messung](../messungen/2026-10-10-pattern-kette-import.md)) mit seinem Ziel und
beginnt jede Kette bei einem Pattern, auf das keines verweist. Je Kette gibt es eine
Tabelle (BPM, Länge in Takten, Master-Effekt-Typ und Hold, Steps, hörbare Parts,
Motion) und danach die wiederkehrenden Züge mit den Ketten, die sie zeigen.

```bash
node tools/set/stil.mjs SET.e2sallpat > stil.md
```

## Die Regeln

Die Regeln sind aus der Auswertung eines eigenen Sets hergeleitet, mit einem
handgebauten Übergang als Gegenprobe. Sie sind der Schluss aus dem, was in den
Patterns steht, keine Aussage über die Absicht dahinter.

1. Das Ziel ist ruhig: im letzten Pattern einer Kette hört die Bewegung des
   Master-Effekts auf. Die Bewegung steht davor.
2. Der Master-Effekt wird über X und Y bewegt (Motion Sequence), in den Patterns vor
   dem Ziel. Die Pad-Bewegung läuft in die Ecke X 127 / Y 0 bis 1 und bleibt dort.
3. MFX Hold ist am Anfang der Kette an und wird später ausgeschaltet. Das Pad steht
   dabei bei Y 102 bis 112.
4. Mitten in der Kette wechselt der Master-Effekt gelegentlich, das Ziel setzt
   wieder seinen eigenen. Jeder Effektwechsel kostet eine Lücke beim Patternwechsel
   (`data/findings.mjs`, `effectsAlwaysRun`), darum hält der Generator die Effekttypen
   möglichst gleich.
5. Die Patterns werden zum Ziel hin voller, ohne dass mehr Parts klingen: es klingen
   weniger Parts, aber dichter. Der Rest steht gemutet im Pattern, bereit zum Einschalten.
6. Das Tempo bleibt in einer Kette meist gleich, geändert wird in einzelnen Sprüngen
   im dünnen Teil, nicht als Linie.
7. Der Filter wird über Motion Sequence geöffnet oder geschlossen, über das ganze
   Pattern. Die Kurve ist eine aufgenommene Handbewegung, kein gerader Strich.
8. Tonart und Swing bleiben, die Länge fast immer.
9. Parts von A gehen in Gruppen, nicht einzeln.
10. Parts von B, die den Puls tragen, kommen früh und mit dem Sound von B. Die
    Gegenschläge kommen erst mit B.
11. Im letzten Brücken-Pattern hört ein Part, der in A und B klingt, früh auf (bei
    60 bis 70 Prozent). Auf dem Part, der in B weiterläuft, steht dort eine Bewegung
    und ein kurzer Decay.
12. Ein gemuteter Part aus A, der in A und B schweigt, kommt zweimal als Akzent.
13. Byte 60 im Pattern-Kopf folgt Hold.
14. Das Tal der Brücke hat drei hörbare Parts.
15. Alle Ketten sind lückenlos durchverkettet, Chain Repeat 0.

Offen: Motion-Werte 0 in Lücken. Ob das einen aufgenommenen Wert oder "nichts
aufgenommen" meint, ist am Gerät nicht geprüft; der Generator schreibt durchgehende Werte.

## Der Generator

```bash
node tools/set/transition.mjs SET.e2sallpat --from 190 --to 192 [--count 2] [--out DIR]
node tools/set/transition.mjs --a-file A.e2spat --b-file B.e2spat --slots 214,215 --slot-b 219
```

`--from` und `--to` sind Pattern-Nummern (A und B), `--count` die Zahl der
Übergangs-Patterns, `--slots` die Zielplätze. Die vollständige Optionsliste steht im
Kopf von `tools/set/transition.mjs`. Standard ist, was in möglichst vielen
ausgewerteten Ketten zu sehen war; wo sie auseinandergehen, gibt es eine Option.

- **Richtung** (`--direction auto|down|up|blend`): `auto` wählt `blend`, wenn A Parts
  hat, die in B nicht klingen, und B Parts, die in A nicht klingen. Parts von A gehen
  gleichmäßig verteilt bis zum vorletzten Übergang, höchstens `--leave-max 2` je
  Übergang, zuerst die Parts ohne Melodie mit vielen Steps. Parts von B kommen als
  Kopie des Part-Blocks, der dünnste zuerst, erst auf 50 Prozent der Steps, im letzten
  Übergang auf alle. Parts mit überwiegend Gegenschlägen warten auf B (`--arrive all`
  holt sie früher). Parts, die in A und B klingen, bleiben. `down` lässt nur A gehen,
  `up` nur B kommen. Ausdünnen vor dem Abgang ist aus, `--thin-before 0.6` schaltet es ein.
- **Tal** (`--valley auto|none|0.25`, `--valley-parts 3`): in der Mitte der Brücke
  höchstens drei hörbare Parts und etwa 30 Prozent der Steps, die zwischen A und B zu
  erwarten wären. Ab drei Übergängen voll, bei zweien halb, bei einem gar nicht. Der
  Part, der in B weiterläuft, wird nie gemutet.
- **Akzent** (`--accent auto|none|16`): ein gemuteter Part von A mit 2 bis 8 Steps, der
  in A und B schweigt, klingt in der Brücke bei 40 Prozent und im letzten Übergang.
- **Pad und Hold** (`--pad hold|release|corner|none`): `hold` (Standard) schaltet Hold nach
  dem ersten Übergang an (Pad X 48 / Y 110, dann X 28) und im letzten aus, in beide
  Hold-Bytes geschrieben. `release` lässt das Pad im letzten Viertel des letzten
  Übergangs in die Ecke laufen, `corner` fährt es als Motion Sequence über alle
  Übergänge in die Ecke.
- **Effekte:** Insert- und Master-Effekte stehen in allen Übergängen wie in A, auch bei
  hereinkommenden Parts von B. Der Generator führt nie einen neuen Insert-Typ ein. Alle
  Unterschiede zu B fallen in den Wechsel nach B und stehen am Ende der Übersicht. Bei
  vier oder mehr Parts mit schweren Insert-Typen (6, 18 bis 30) steht ein Hinweis, weil
  die Effekte immer rechnen und Polyphonie kosten. `--mfx N` setzt im letzten Übergang
  einen Master-Typ und kostet zwei Effektwechsel.
- **Tempo** (`--tempo ease|ramp|keep`): `ease` (Standard) macht bis 5 BPM Unterschied einen
  Sprung ab 60 Prozent der Übergänge, sonst bleibt das Tempo bis 30 Prozent stehen, ändert
  sich bis 90 Prozent und liegt im letzten Übergang auf dem Tempo von B (ganze BPM).
- **Brücke zu B** (`--sweep tail|run|none`, `--clip N|none`, `--insert-motion`): im letzten
  Übergang hören Parts, die in A und B klingen, nach 65 Prozent auf. Der Part, der in B
  weiterläuft, bekommt den Filterbogen (ein tiefer Cutoff läuft nach oben, ein hoher nach
  unten) und Decay 15. `--insert-motion` schaltet seinen Insert für Step 32 bis 48 per Motion an.
- **Unverändert:** Das Ziel B bleibt, wie es ist. Tonart, Swing und Länge bleiben die von A.
  Namen: `PRE` plus Name von B (oder `--label`) plus Zähler ab 0.
- **Chain To** (`--chain`): jedes Pattern zeigt auf das nächste, das letzte auf B,
  Chain Repeat 0. `--chain-a` setzt es auch an A (nur in der neuen Sicherung).
  `--all-out new.e2sallpat` schreibt eine Kopie der Sicherung mit den Übergängen in
  freien Plätzen.

Nicht übernommen: Decay-Kürzung auf einem Part, der geht; neue Steps auf dem
hereinkommenden Part über B's Muster hinaus (kein festes Muster erkennbar); Mute-Wechsel
nach festem Plan (das bleibt Handarbeit); Noten- und Tonartverschiebung; Level-Automation
und Halftime.

## Im Emulator ansehen

`tools/set/emu-check.mjs` zeigt, dass der emulierte Gerät ein Set mit Übergängen
annimmt: das Set kommt auf eine virtuelle SD-Karte, DATA UTILITY, IMPORT ALL PATTERN
liest es, und der Hauptbildschirm wird für jedes angegebene Pattern fotografiert.
Es braucht die eigene Firmware und den eigenen Flash.

```bash
E2_VSB=SYSTEM.VSB E2_FLASH=flash_full.bin node tools/set/emu-check.mjs NEW.e2sallpat --show 190,201,202,192 --out DIR
```
