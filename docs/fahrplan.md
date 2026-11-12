# Fahrplan

Welche Version was bekommen soll. Stand 2026-11-06. Was hier steht, ist geplant, nicht zugesagt; Einzelheiten stehen in den
verlinkten Ideen. Was eine Version wirklich gebracht hat, steht in ihren Notizen unter `release-notes/` und in der App unter
Changelogs.

## Erschienen

- **1.3.6:** kleine Fixes, Autoverbinden, MIDI-Bericht, Gerätename "Electribe 3", USB-Symbol, Blechy auf dem Gerät.
- **1.4.0:** Pattern-Vorschau beim Spielen, Patcher-Assistent, Update ohne Original, BEAT 8, Stereo-Sample auf einem Pad,
  eigene Ladeanimation, MANAGE PLUGINS mit bis zu 64 Plugins, Plugin-API 11 und 12, Fernsteuerung über USB.
- **1.4.1 und 1.4.2:** Fixes am vollen Test im Patcher.

## 1.4.5: Plugins und Rettung

In Vorbereitung, wird vor dem Release am Gerät getestet ([Notizen](../release-notes/1.4.5.md)).

- Plugin-API 12 auf 25 ([Idee 74](ideen/74-plugin-api-feedback.md)), dazu Tasten bei offener App durchlassen mit
  `korg.passKeys(...)` (Idee 66 in der [Ideenliste](ideen.md)).
- Neue Plugins im Katalog: Momentary Mute, Image Viewer, Gate Hold und Step Copy. Key Pads und Filter Toggle sind fest in der
  Firmware eingebaut (BLECH > FEATURES, standardmäßig an).
- Hacktribe-Warnung zu den Samples im Patcher, Rettungsfälle für versehentliches Hacktribe und den Weg zurück zu Korgs
  Original ([Anleitung](original-zurueck.md)).

## Danach

- Sample Swap, dazu ein gemeinsames Format wie bei der ESX, in dem alle Anpassungen in einer Datei stecken.

## 1.5: "The sample update"

- Samples nativ auf der blauen: eine WAV wird importiert, in PCM umgewandelt und über denselben Weg wie Sample Swap auf die
  blaue gebracht.
- Besseres und vor allem mehr Sample-Editing ([Idee 59](ideen/59-sample-editor.md)).
- Wellenform beim Schneiden auf der roten ([Idee 75](ideen/75-wellenform.md)).
- Was genau dazugehört, wird ab 1.5 geplant.
