# Idee 40: Haustier „Blechy“

Stand: Charakter und Verhalten festgelegt, ein 1-Bit-Prototyp liegt außerhalb des Repos (Figur, alle Zustände, Beat-Sync, Pads). In BLECH eingebaut (die letzte Seite des Menü-Rings, kein Plugin der Karte), im Emulator geprüft, am Gerät nichts. Das neue Gehen (siehe unten) ist im Browsermodell geprüft, sein Emulatorfall ist geschrieben, aber noch nicht durchgelaufen. Zurück zu den [Ideen](../ideen.md).

Ein Maskottchen auf dem Display, benannt nach dem Patcher „Blech“. Baut auf Idee 37 (Backlight-Strobo) und Idee 45 (Power-Ton und -Screen) auf.

## Charakter

Heruntergekommene Nasenfigur in 1-Bit, die Nase ist der Körper. Hohle Augen mit doppelten Tränensäcken und Pinnadel-Pupillen, laufende Nase, Stoppeln, Schweiß, Zuckbraue, Storchenbeine. Soll aussehen wie zehn Jahre durch.

## Zustände

- **Idle:** steht still, zuckt nur ab und zu.
- **Schranz/Terror:** Zombie-Geflail aus wenigen Einzel-Frames, die hin und her springen. Der Frame wechselt pro Trigger (Haken am Sequencer-Tick oder Note an den DSP), nicht nach Uhr.
- Hartes Strobo läuft über das RGB-Licht (Idee 37, schaltet sofort). Der Frame-Flip auf dem LCD ist nur bis zu 8teln knackig, 16tel schmieren: das LCD schaltet träge, grob 100 ms (geschätzt).

## Touchpad als Blechys Fläche

Steht er auf dem Display, wird das Touchpad seine interaktive Fläche, grob an seiner Bildposition. Die Finger werden über die schon vermessenen Touchpad-Koordinaten gelesen (Typ `05`). Normales Antippen: Maul auf, er wird wütend (`blechy-angry`). Drüberwischen oder Streicheln: glücklich (`blechy-happy`).

## Samples

Eigene Aufnahmen in `assets/blechy/` (Quelle `source-original.mp3`):

- `blechy-happy`: Streicheln
- `blechy-angry`: Antippen
- `blechy-sad`: beim Ausschalten (Idee 45)
- `blechy-key`: Ton, wenn ein Keyboard-Menü offen ist

Es gibt keinen zufälligen Grund-Schnüffler.

## Ablauf

- Er kommt zufällig vorbei, oder bei **Stop** läuft er herein und fragt („wat machst'n du da atze?“, er steht seitlich, die Sprechblase daneben).
- **Play:** er bleibt. Schranz startet erst nach etwa 10 bis 15 s, nicht sofort.
- Noch einmal **Stop:** er läuft wieder hinaus.
- **Stats** liegen nur im RAM und werden bei jedem Boot zurückgesetzt, nie im Flash (der nutzt sich ab). Er zählt Spielzeit, Lieblingstempo und Ähnliches und redet einen bei Stop damit an.
- Am Anfang kein eigener Menüpunkt (er kommt ohnehin zufällig), ein Menü später optional.
- **Pad-Drum-Easter-Egg:** die Pads spielen Blechys Töne als Finger-Tap-Mini.

## In BLECH eingebaut

Statt eines Überlagerns über den Hauptbildschirm hat Blechy die letzte Seite des EDIT Rings der Firmware (hinter Event, vor dem
Pattern Menü; [Plugins](../plugins.md), Abschnitt "Blechy, die letzte Seite des Rings"). Er war zuerst eine App unter GAMES und ist
kein Plugin der Karte mehr: er braucht keine Karte, steht in keiner Liste und fehlt mit EXIT beim Einschalten. Auf der Seite steht er
sofort da und winkt nach etwa einer Sekunde einmal je Landung. Nur auf der Seite ist er sichtbar, sonst zählt er im Hintergrund die Stats (RAM). Spielt ein Pattern, bleibt er stehen und wirft nach
etwa 12 s Schranz an, der Frame wechselt mit den Achteln. Bei STOP fragt er und nennt Spielzeit und Lieblingstempo.
Antippen nahe an ihm macht ihn wütend, Streicheln froh. Keine Töne, Plugins spielen keine Samples. Die Bilder sind
die Sprites in `assets/blechy/sprites/` (Idle, Terror 1 bis 4, dazu aus Idle abgeleitet: ruhig, wütend, froh; traurig für das Ausschalten, [Idee 45](45-blechy-ein-aus.md)), das Werkzeug
`tools/blechy-build.mjs` macht den Plugin-Quelltext daraus. Messung, Bilder und was die Schnittstelle dafür noch nicht kann: [Blechy in BLECH eingebaut](../messungen/2026-10-15-blechy.md).

## Gehen wie auf der Discord-Seite

Idee 68, gebaut und im Browsermodell geprüft, der Emulatorfall (`tools/emu/blechy_cases.py`, `blechy-gang-*`) ist noch nicht durchgelaufen. Beim Gehen wechseln das ruhige Bild (`calm`) und das Gehbild (`walk`) alle 240 ms,
wie auf der Discord-Seite der App (`site/app/discord.mjs`, `STEP_MS`). Geht er nach links, sind es dieselben beiden Bilder
gespiegelt (`back0`, `back1`), wie die App ihn mit `scaleX(-1)` spiegelt. Stehen, Zucken, Winken, Reaktionen, Reden und Tanz sind
unverändert. Die gespiegelten Bilder sind keine neue Kunst: `tools/blechy-build.mjs` dreht die Sprites aus `assets/blechy/sprites/`
beim Bauen links nach rechts, um die Mitte des Kastens um beide Gehbilder, damit die Grenzen des Gehens (`WALK_RIGHT`) gleich
bleiben (Tabelle in `data/script/blechy-art.mjs`). Das Gehbild sitzt eine Zeile tiefer als das ruhige Bild, das ist der Schritt
(vorher wechselte die Zeile alle zwei Pixel, jetzt mit dem Bild). Der Block wuchs um rund 700 Byte, Platz im Abbild ist genug
(Block höchstens 16384 Byte). Die Gehgeschwindigkeit blieb bei einem Pixel alle 120 ms; die App geht schneller, ihr Schritt ist 240 ms.
Messung: [Blechy in BLECH eingebaut](../messungen/2026-10-15-blechy.md).

## Offen

- Gehen und Spiegeln am Gerät ansehen: ob der Wechsel alle 240 ms auf dem trägen LCD gut lesbar ist.

- Ein ungenutzter RAM-Fleck für die Stats (hinter dem Image Richtung `0xD0000000`, noch nicht als frei vermessen).
- Stop-Haken und Zeichnen im Doppelpuffer `0xC031B310`.
- Haken am Sequencer-Trigger. Die Plugin-Ereignisse `step`, `beat` und `stop` gibt es ([Plugins](../plugins.md)); ob sie reichen, ist nicht geprüft.
- Haken für den Keyboard-Ton: wie er zu bauen ist, ist noch unklar.
