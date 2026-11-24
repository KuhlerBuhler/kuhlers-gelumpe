Entwurf, Teil der Notizen zu 1.6.0 (Plugin-API zur nativen Aufnahme).

**Neu für Entwickler**
- Plugin-API 41:
  - `korg.audio.capture(25)` nimmt den Master ab, den Mix, den die Firmware an den Ausgang gibt. Läuft die native Aufnahme, nutzt der Master ihren Abgriff mit; jede andere Quelle gibt dann 2 (belegt). Nur Sampler (Hacktribe und rot), auf blau 6.
  - Neue Werte, nur lesen: `korg.record.running`, `korg.record.seconds`, `korg.record.gaps`.
- Apps, die Audio abgreifen (wie Spettro), schließen während der Aufnahme weiterhin; den Master teilen nur Plugins im Hintergrund.

## English

Draft, part of the 1.6.0 notes (plugin API for the native recording).

**New for developers**
- Plugin API 41:
  - `korg.audio.capture(25)` takes the Master, the mix the firmware sends to the output. While the native recording runs, the Master shares its capture; every other source then returns 2 (busy). Sampler only (Hacktribe and red), 6 on the blue.
  - New read-only values: `korg.record.running`, `korg.record.seconds`, `korg.record.gaps`.
- Apps that capture audio (such as Spettro) still close during a recording; only background plugins share the Master.
