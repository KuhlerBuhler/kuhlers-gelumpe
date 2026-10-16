# Offline-ARM-Emulator

Eigenständiges Python-Programm des Editors. Es führt die Firmware der
Electribe (eine eigene `SYSTEM.VSB`) mit Unicorn aus, zeigt das Display live
und nimmt Panel und MIDI an. Benötigt Python 3.10+ und die offizielle
Python-Bindung `unicorn==2.1.4`. Keine Node-Laufzeit-Abhängigkeit, keine
Hardwareverbindung, keine eingebauten Firmwaredaten.

Hier liegen der Dienst (`server.py`), die Maschine (`machine.py`), die
Modelle für Display, SD-Karte und Flash, die Prüfungen (`check.py`,
`runner.py`) und ihre Python-Tests.

Vom Repository-Verzeichnis aus:

```sh
npm run setup:emu   # einmalig: tools/emu/.venv mit unicorn==2.1.4
npm start           # Seite und Emulator zusammen; Strg+C beendet beides
```

Den Dienst allein startet `npm run emu`. Die Tests mit Firmware:

```sh
E2_VSB=/pfad/SYSTEM.VSB npm run test:emu
```

Alles Weitere steht in [docs/emulator.md](../../docs/emulator.md):
Installation auch für Windows, Start, Karte und Flash, Display, Gerätezeit,
Boot, Prüfungen und Lizenz.

Dieses Python-Werkzeug steht unter GPL-2.0-only, siehe [LICENSE](LICENSE)
und [NOTICE](../../NOTICE).
