# Gerätetest: Gerätemenüs auf Deutsch

Stand 2026-11-23. Anleitung für Tester. Gebaut und im Emulator geprüft (Hacktribe, Korgs rote 2.02, blaue
Electribe), am Gerät noch nicht. Siehe auch die [Übersicht](README.md) und [Firmware-Sprache](../firmware-sprache.md).

## 1. Worum es geht

Der optionale Patch `lang-de` stellt das BLECH-Menü und Korgs Menüs auf Deutsch: Seiten, Dialoge, Meldungen,
Fehlertexte, Skalen und Namen der Effektparameter. Begriffe, die auf dem Gerät aufgedruckt sind (PATTERN, PART,
IFX, MFX, ...), bleiben Englisch, damit die Bedienungsanleitung passt.

Die Sprache wählst du beim Patchen: in der App, Seite **Patcher**, **Schritt 2**, unter der BLECH-Datei das Häkchen
**"Gerätemenüs auf Deutsch"** (neben "Electribe 3" als Gerätename). Es ist aus per Voreinstellung. Eine Seite im
Gerät zum Umschalten gibt es nicht: für Englisch baust du neu ohne das Häkchen.

Am Ende ist belegt: die deutsche Datei startet, jede Seite zeigt Deutsch ohne abgeschnittene oder überlappende
Texte, die Umlaute sehen richtig aus, die Texte, die der Emulator nicht auf den Bildschirm bringt (Dialoge,
Meldungen, Fehler), passen auch, und ein Update behält die Sprache.

| Was | Stand |
|---|---|
| BLECH-Menü, Korgs Bildschirme 0 bis 44 mit Reglern und EDIT | im Emulator gemessen (nichts über dem Rand, keine Überlappung) |
| Umlaute Ä Ö Ü ä ö ü ß in Schrift 0, 1, 3 | im Emulator gemessen |
| Dialoge, Meldungen, Fehlertexte (Abschnitt 6) | nur hergeleitet: Breite gerechnet, nie gezeichnet |
| Update behält Englisch oder Deutsch | gemessen an echten Dateien (`test/lang.test.mjs`) |
| alles am Gerät | offen |

## 2. Warnung

**Das Gerät wird verändert.** SOFTWARE UPDATE schreibt eine neue Firmware in den Flash. Du machst das auf eigenes
Risiko, ohne Gewähr. Der Weg zurück: die vorher gesicherte `SYSTEM.VSB` wieder aufspielen. Mehr in [blech-datei.md](blech-datei.md) Abschnitt 2.

In diesem Test nichts bestätigen, was Daten löscht: FACTORY RESET, FORMAT und Löschdialoge nur öffnen, lesen und
mit EXIT abbrechen.

## 3. Voraussetzungen

- Electribe 2 Sampler (rot), Netzteil, SD-Karte.
- Die App mit dem Häkchen. **1.4.8 hat es noch nicht**, es kommt mit 1.5. Bis dahin die App aus `develop` starten
  (`npm start`, Seite Patcher) oder einen App-Build von `develop` aus der CI nehmen.
- Ausgangsdatei: die unveränderte `ORIGINAL.BIN` von der Karte (Hacktribe), nicht eine schon gepatchte Datei.
  `lang-de` passt nur auf BLECHs eigene Dateien; auf einer fremden Datei sagt die App das in der Planzeile.
- Blaue Electribe nur über einen Tester.

## 4. Vorher sichern

- SD-Karte komplett kopieren.
- Die jetzige `SYSTEM.VSB` von der Karte mit Prüfsumme aufheben (`shasum -a 256`).

## 5. Installieren

| # | Schritt | Erwartet |
|---|---|---|
| 1 | App, Patcher, Schritt 1: `ORIGINAL.BIN` wählen | Hacktribe erkannt |
| 2 | Schritt 2: BLECHTRIBE, Häkchen "Gerätemenüs auf Deutsch" an | Planzeile nennt "Gerätemenüs auf Deutsch" |
| 3 | Prüfung laufen lassen, speichern auf die Karte | Prüfung grün, Datei in `KORG/hacktribe/System/` |
| 4 | DATA UTILITY, SOFTWARE UPDATE | Update läuft durch |
| 5 | Neustart | Ladeanimation wie gewohnt, Hauptbildschirm |

Schritt 4 läuft noch mit der alten Firmware und zeigt deren Texte. Die deutschen Update-Texte kommen erst beim
nächsten Update (Schritt 25).

## 6. Durchgang am Gerät

Je Seite schauen: Text Deutsch, nichts abgeschnitten, nichts überlappt, keine stehengebliebene Grundlinie unter
einem Dialogtext, Umlaute erkennbar. Bei jeder Auffälligkeit ein Foto vom Display.

### 6.1 Seiten (im Emulator schon gemessen, hier zur Bestätigung)

| # | Wo | Erwartet |
|---|---|---|
| 6 | Hauptbildschirm, Pattern blättern | Deutsch, BPM und Namen an ihrem Platz |
| 7 | MENU: alle Seiten der Pattern- und Part-Menüs, je Seite einmal am Regler drehen und EDIT durchblättern | Deutsch, Werte nicht über den Rand |
| 8 | GLOBAL PARAMETER, alle Seiten | Deutsch; MIDI-Clock-Werte zeigen "Extern USB", "Extern MIDI", "Extern Sync" |
| 9 | DATA UTILITY, alle Seiten (nur ansehen) | Deutsch |
| 10 | BLECH-Menü, alle Gruppen und Unterseiten | Deutsch; Umlaute in Schrift 0, 1, 3 |
| 11 | IFX EDIT und MFX: einige Effekte, je Parameterseite | Namen der Parameter Deutsch und gleich lang wie vorher |

### 6.2 Texte, die nur am Gerät erscheinen

Diese Texte hat der Emulator nie gezeichnet. Hier entscheidet nur das Display.

| # | Auslösen | Erwartete Texte |
|---|---|---|
| 12 | Touch Scale / KEYBOARD: Skala durchschalten | "Dur-Blues", "Moll-Blues", "Vermindert", "Dur-Penta", "Moll-Penta", "Ganzton", "Mollterz", "Durterz", "Quarten", "Quinten", "Oktave" |
| 13 | WRITE drücken, dann EXIT | "Speichert" oder der WRITE-Dialog, sauber |
| 14 | Pattern-Funktionen mit Auswahl (z. B. Part kopieren), mit EXIT abbrechen | "Pattern wählen", "Quell-Part wählen", "Ziel wählen" |
| 15 | Sample-Export in DATA UTILITY öffnen, abbrechen | "SAMPLE-EXPORT", "VON WÄHLEN", "BIS WÄHLEN", "TYP WÄHLEN" |
| 16 | Sampling starten, abbrechen | "Rec bereit!", "Rec abbrechen? [Enter]", "Aufnahme...", "Fertig", "Enter: Wiedergabe" |
| 17 | Sample-Import mit einer Nicht-WAV-Datei | "Nur WAV-Datei" |
| 18 | Karte ziehen, dann Import oder Export versuchen | "Keine Karte." |
| 19 | Karte mit Schreibschutzschieber, Export versuchen | "Schreibschutz an" |
| 20 | Funktion, die laufenden Sequencer stoppt, bei PLAY aufrufen | "Sequencer stoppen?" |
| 21 | Sampling mit MIDI-Clock extern | "Clock nicht intern" |
| 22 | FACTORY RESET und FORMAT nur öffnen, mit EXIT raus | "Ganz sicher?", "GANZ SICHER?" sauber, nichts bestätigen |
| 23 | Touchpad-Kalibrierung, falls erreichbar, nur bis zur ersten Anzeige | "Ecke oben links", "Ecke unten rechts" |
| 24 | Batterie fast leer (nur wenn es sich ergibt) | "Batterie schwach" |

Was nicht nebenbei auslösbar ist (Fehler bei MIDI, Zeitüberschreitung, Karte voll, Karte: Formatfehler, Events
voll, Speicher voll, Updatefehler, ...), bleibt offen. Wenn es sich ergibt: Foto.

## 7. Update und Rückweg

| # | Schritt | Erwartet |
|---|---|---|
| 25 | In der App eine Update-Datei aus der deutschen `SYSTEM.VSB` bauen, aufspielen | Häkchen ist gesetzt und gesperrt ("Schon in der Datei ..."); die Update-Seite zeigt "Akt. Version:", "Neue Version :", "Update..."; danach weiter Deutsch |
| 26 | Dieselbe Datei ohne Deutsch bauen wollen | nicht möglich; für Englisch neu von `ORIGINAL.BIN` |
| 27 | Mit gehaltenem EXIT starten | BLECH aus. Korgs Menüs bleiben vermutlich Deutsch, weil `lang-de` feste Zeigeränderungen sind (hergeleitet, offen) |
| 28 | Gesicherte `SYSTEM.VSB` zurückspielen | Englisch wie vorher |

## 8. Rückmeldung zu den Begriffen

Wer die Menüs ohne Englisch bedient: welche Wörter versteht er nicht, welche sind ungewohnt, wo würde er anders
kürzen. Die Liste geht ins Glossar (`data/lang/de-glossar.json`) und die Abkürzungen (`data/lang/de-abk.json`).

## 9. Ergebnis

| # | Ergebnis | Notiz |
|---|---|---|
| 1-5 | offen | |
| 6-11 | offen | |
| 12-24 | offen | |
| 25-28 | offen | |
| Begriffe | offen | |
