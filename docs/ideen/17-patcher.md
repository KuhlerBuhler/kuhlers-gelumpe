# Idee 17: Eigener Patcher statt Hacktribe

Stand: gebaut (Patch-Format, Haken-Register, Seite Patcher, Export mit Prüfung im Emulator). Zurück zu den [Ideen](../ideen.md).

Ein Werkzeug, das Änderungen, Daten und eigenen Code, als Patch auf eine VSB-Kopie anwendet, im Emulator bootet und prüft und als neue Firmware exportiert. Damit sollen LED-Steuerung, neue Menüpunkte und ersetzte Firmwareteile möglich werden, verteilt als Patch wie Hacktribe, nie als Korg-Firmware. Das Projektziel: das Werkzeug, mit dem auch die Allgemeinheit das selbst tun kann.

Aufbau und Regeln stehen in [Patcher](../patcher.md).

## Was gebaut ist

- Patch-Format und Anwenden: `src/patch.mjs`; Haken-Register: `src/hooks.mjs`; Seite Patcher: `site/app/patcher.mjs`.
- Der Patch-Satz BLECH (`data/patches/blech.json`) besteht aus Startbild-Editor (Idee 35), MFX 2 (Idee 44), Plugin-Laufzeit (Idee 50), Kartenordner `blechtribe` und dem Blech-Startbild (Idee 41).
- Am Gerät belegt: ein Datenpatch am Startbild ([Rückweg geübt](../messungen/2026-10-10-rueckweg-geuebt.md)) und der Code-Patch MFX 2 ([MFX 2 am Gerät](../messungen/2026-10-13-mfx-umschalter-geraet.md)). Startbild-Editor, Plugin-Laufzeit und das Menü BLECH sind nur im Emulator geprüft.
