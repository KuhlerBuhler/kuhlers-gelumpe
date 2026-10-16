# Blechy-Sprites

1-Bit-Posen des Maskottchens Blechy (Idee 40 in `docs/ideen.md`). Erzeugt von
`tools/art/make_blechy.py` aus dem Zeichencode der Prototypen.

- Format: PNG, 56×56, 1-Bit. **Schwarz = gesetzt/leuchtet** (das Display zeigt
  gesetzte Pixel dunkel). Figur mittig, Füße unten.
- Für das Gerät in das jeweilige Blit-Format wandeln; invertieren falls der
  Screen invertiert ist (wie das Splash).

| Datei | Pose |
|---|---|
| `blechy-idle.png` | steht still (Idle, nur Zucken) |
| `blechy-calm.png` | wie Idle, aber ohne Zucken (abgeleitet, nur das Gesicht) |
| `blechy-angry.png` | wie Idle, Brauen schräg nach unten (abgeleitet, für Antippen) |
| `blechy-happy.png` | wie Idle, Augen als zufriedene Bögen (abgeleitet, für Streicheln) |
| `blechy-sad.png` | wie Idle, schwere Lider, Pupillen unten, Brauen nach innen oben (abgeleitet, nur das Gesicht, kein Mund; für den Power-Off-Screen, Idee 45) |
| `blechy-wave-1.png`, `blechy-wave-2.png` | winkt: die ruhige Pose mit erhobenem rechten Arm, die Hand neigt sich links, dann rechts (abgeleitet, für den Gruß auf der Ringseite) |
| `blechy-walk.png` | läuft (Blechy geht damit über die Ringseite, in beide Richtungen mit demselben Bild) |
| `blechy-terror-1.png` … `terror-4.png` | Schranz/Terror, die vier Frames springen hin und her |

Posen (Arm-/Beinstellung, Neigung) stehen in `tools/art/make_blechy.py` unter
`POSES` und lassen sich dort ändern, dann neu rendern:

```bash
python3 tools/art/make_blechy.py assets/blechy/sprites /tmp/blechy-strip.png
```
