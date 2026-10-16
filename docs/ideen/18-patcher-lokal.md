# Idee 18: Patcher lokal statt GitHub Actions

Stand: gebaut, Teil von Idee 17. Zurück zu den [Ideen](../ideen.md).

Eine VSB rein, Patch anwenden, VSB raus; der entschlüsselte Stand verlässt nie den Rechner (wie Hacktribe). Wer das Werkzeug benutzt, bringt eigene Firmware und Patch mit, spielt lokal ein und testet die gepatchte Firmware direkt im Emulator.

- Die Seite Patcher wendet die Patches im Browser an, die Prüfung läuft im lokalen Emulator-Dienst; der Weg von der originalen Korg 2.02 zu Hacktribe läuft über Hacktribes bsdiff-Patch, den man dort holt ([Patcher](../patcher.md), Abschnitt „Original Korg 2.02 zu Hacktribe“).
- Die Hacktribe-VSB ist bereits Klartext (disassemblierbar). Die Entschlüsselung einer Stock-VSB war als Zusatzstück gedacht; der gebaute Weg braucht sie nicht. Ob Korgs Original-Datei verschlüsselt ist, ist nicht geprüft.
- Rechtlich ein Graubereich, wie bei Hacktribe.
