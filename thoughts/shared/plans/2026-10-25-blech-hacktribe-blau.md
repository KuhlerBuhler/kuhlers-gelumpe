---
planId: 2026-10-25-blech-hacktribe-blau
revision: 1
spec: docs/ideen/65-blech-hacktribe-blau.md
teamSync: false
---

# BLECH mit Hacktribe für die blaue Electribe: Umsetzungsplan

**Ziel:** Der Patcher macht aus Korgs roter 2.02 plus `hacktribe-2.patch` (Hacktribe `7cb4825c`) die BLECH-Hacktribe-Datei und setzt für die
blaue den richtigen Kopf (Route 4). Die Spezifikation und alle Belege stehen in [Idee 65](../../../docs/ideen/65-blech-hacktribe-blau.md).

**Architektur in einem Satz:** Route 4 ist Route 2 (`data/patches/blech.json` auf Hacktribe) plus ein Schreibschritt für zwei Bytes im
Kopf (`0x12`, `0x2E`), der von der Frage "Was läuft gerade auf deiner blauen?" abhängt; im Emulator bekommt Hacktribe ein blaues Profil
(Kennung `KORGelec2USR` im Flash).

**Regeln für die ganze Arbeit:** keine Korg-Daten im Repository (Tests bauen eigene Abbilder, echte Dateien nur über `E2_HACKTRIBE_VSB` und
`E2_BLUE_VSB`); nichts an ein Gerät schicken ohne das Okay des Besitzers; keine Firmware im Repository; Hacktribes Patch-Datei wird nie
kopiert oder mitgeliefert; keine Gedankenstriche in Texten.

## Was schon feststeht (aus Idee 65, nicht noch einmal prüfen)

- Hacktribe unterscheidet sich von Korgs Sampler in der Kennungsprüfung um ein Wort: die blaue Kennung gilt als Typ `0x124`. BLECH
  rührt das nicht an.
- Der Updater nimmt den Typ aus Bytes `0x2C` bis `0x2E`: von Korgs blauer Firmware aus Kopf Synth, von Hacktribe oder BLECH aus Kopf
  Sampler. Eine falsche Wahl wird vor dem ersten Flash-Befehl abgelehnt.
- Der Emulator bootet Hacktribe mit blauem Flash, der Rückweg zu Korgs Blauer (Kopf Sampler, Ordner `hacktribe`) läuft durch.
- `buildOf` (`src/firmware.mjs:35`) hält Hacktribe mit Synth-Kopf für Korgs Blaue.

## Phase 1: Nur Emulator (kein Gerät)

Ziel: alles beweisen, was ohne blaue Electribe beweisbar ist, und die Messung wiederholbar machen. Ausgang der Phase ist ein Ja oder Nein für
Phase 2, kein Patcher-Code.

- [ ] **1.1 Blaues Profil im Emulator.** Schalter "Hardware: rot oder blau" in `tools/emu/machine.py`, `runner.py`, `check.py` und
  `server.py`: die Kennung im Flash richtet sich nach der Hardware, nicht nach dem Build (`firmware.py:162`, `machine.py:80`, `:219`,
  `server.py:42`). `blank_flash` für blau ohne Werksbank des Samplers. Hacktribe und BLECH laufen damit auf `KORGelec2USR`.
  - Test: neuer Python-Test in `tools/emu/` mit selbstgebautem Sampler-Abbild (kein Korg), Kennung im Flash gleich der Wahl.
  - Fertig, wenn: Hacktribe (mit `E2_HACKTRIBE_VSB`) bootet auf beiden Hardware-Werten bis Bildschirm 1, ohne Assertion.
- [ ] **1.2 `tools/emu/hacktribe_blue_probe.py`.** Macht aus den Wegwerf-Skripten der Messung ein Werkzeug mit der Matrix aus Idee 65, Abschnitt 2:
  laufende Firmware (Korg blau, Hacktribe) mal Datei (Kopf Sampler, Synth, nur `0x12`, nur `0x2E`) mal Ordner (`electribe`, `hacktribe`, `blechtribe`),
  dazu Hin und Zurück Korg blau, Hacktribe, Korg blau mit Vergleich des ganzen 16-MiB-Flashs. Läuft nur mit den eigenen Dateien, schreibt nur
  außerhalb des Repositorys (wie `synth_update_probe.py`).
  - Test: die Matrix aus Idee 65 kommt wieder heraus (angenommen oder abgelehnt je Zeile).
  - Ergebnis in `docs/messungen/2026-10-xx-hacktribe-blau.md` mit Belegtabelle (Marker gemessen, Befehl genannt).
- [ ] **1.3 BLECH auf Hacktribe im blauen Profil.** BLECH-Hacktribe-Datei lokal bauen (außerhalb des Repositorys, nicht einchecken), dann:
  - `check.py` Kurzprüfung und Voll auf blauem Flash, Rettungswege (normaler Start, Update-Abfrage ohne Kennung, Panel-Update, Startmodi, EXIT).
  - Ordner übernehmen (`migrate_cases.py`) im blauen Profil: Frage kommt, wenn `KORG/hacktribe/Sample/e2sSample.all` da ist; keine Frage, wenn nur
    `KORG/electribe` da ist oder keine Datei. Das Ergebnis in die Messung schreiben.
  - Update über BLECH SysEx `0x65`/`0x66`: Datei mit Kopf Sampler schreiben, SOFTWARE UPDATE im Ordner `KORG/blechtribe/System/` läuft; mit Kopf
    Synth wird abgelehnt.
  - Rückweg im blauen Profil: Korgs Blaue mit Kopf Sampler in `KORG/blechtribe/System/` (misst das Hergeleitete aus Idee 65, Abschnitt 4 und 5).
  - Fertig, wenn: alle Läufe grün, jeder Fehlschlag mit Ursache in der Messung.
- [ ] **1.4 Entscheidung.** Idee 65 und `docs/ideen.md` bekommen den Stand "Phase 1 geprüft: Ja/Nein". Bei Nein endet der Plan hier.

**Rückfall Phase 1:** nur Werkzeuge und Docs, nichts davon ändert Firmware oder Patcher; `git revert` genügt.

## Phase 2: Patcher (nach Ja aus Phase 1)

- [ ] **2.1 `buildOf` zuerst nach Code, dann nach Kopf** (`src/firmware.mjs:35`): Hacktribe-Lauf entscheidet vor dem Synth-Kopf; `firmwareName` bleibt.
  Der Kopf wird als eigene Eigenschaft gelesen (`headerType`: Sampler oder Synth, aus Bytes `0x2C` bis `0x2E`).
  - Test zuerst (rot): `test/` mit selbstgebautem Abbild, Hacktribe-Lauf gefüllt, Kopf Synth, erwartet `hacktribe`.
- [ ] **2.2 Kopf schreiben:** eine Funktion `setHeader(bytes, "synth" | "sampler")` in `src/` (läuft im Browser, kein `node:`), setzt `0x12` und
  `0x2E` wie Hacktribes `e2-header.py`, gibt eine Kopie zurück. Tests mit selbstgebautem Kopf in beide Richtungen und für eine Datei, die keine VSB ist.
- [ ] **2.3 Eingaben:** Hacktribe-Datei mit Synth-Kopf (`2b2e1c2f…`, Hacktribes `-e`-Ausgabe) wird erkannt und vor dem Patchen auf Sampler-Kopf
  gesetzt; die Prüfsumme für `7cb4825c` bleibt die einzige Quelle der Wahrheit.
- [ ] **2.4 Fluss und Seite** (`src/patcher.mjs`, `site/app/patcher.mjs`): Gerät wählen (rot, blau), "mit Hacktribe", bei blau und Hacktribe die Frage
  "Was läuft gerade auf deiner blauen?" (Korgs Original: Kopf Synth, Ordner `KORG/electribe/System/`; Hacktribe oder BLECH: Kopf Sampler,
  Ordner `KORG/hacktribe/System/` oder `KORG/blechtribe/System/`). `cardFolder` (`src/patcher.mjs:96`) bekommt die Wahl statt nur den Typ. Der
  Hinweis zu Hacktribes eigenem Patcher (`site/app/patcher.mjs:106`) wird ersetzt. Ausgabe nennt den Ordner, dass dort nur `SYSTEM.VSB` liegen
  darf, und was beim Ordner `KORG/blechtribe` beim ersten Start passiert (Abschnitt 5 der Idee).
- [ ] **2.5 Teile für Route 4:** Auswahl der Teile (Doom, Hintergrundlicht-Plugins) aus dem Ergebnis von Phase 1 und der offenen Risiken; Vorgabe: Teile mit
  ungeprüften Pin-Annahmen aus, bis Phase 3 sie bestätigt hat. Pro Teil ein Satz, warum.
- [ ] **2.6 Prüfung im Patcher:** Kurzprüfung läuft für Route 4 im blauen Profil (Phase 1.1); Liste geprüfter Kopien (`data/patches/verified.json`,
  `tools/verify-patches.mjs`) bekommt die Paare für beide Köpfe.
- [ ] **2.7 Rettung:** `docs/rettung.md` und `data/rescue.mjs` bekommen den Text und die Tabellenzeilen aus Idee 65, Abschnitt 4; die Seite fragt bei blau,
  ob Korgs Original, Hacktribe oder BLECH läuft; `test/e2e/rescue.e2e.mjs` deckt es ab. Der Knopf "Korgs Blaue für den Rückweg vorbereiten"
  (Kopf Sampler setzen) ist Teil der Seite.
- [ ] **2.8 Docs:** `docs/patcher.md` und `docs/patcher.en.md`, README (beide Sprachen), `docs/ideen.md` Zeile 65, `docs/messungen/README.md`.
- Tests: `npm test`, `npm run test:e2e`, `npm run test:emu` (mit `E2_HACKTRIBE_VSB`, `E2_BLUE_VSB`).
- Fertig, wenn: eine rote 2.02 plus `hacktribe-2.patch` ergibt im Patcher für blau beide Dateien, jede startet im Emulator im blauen Profil
  durch alle Rettungswege, und der Weg zurück zu Korgs Blauer läuft.

**Rückfall Phase 2:** Route 4 hinter einer Seitenoption (aus, solange Phase 3 nicht bestätigt ist); Route 1 bis 3 bleiben unberührt. Die Prüfsummen
von Route 1 bis 3 in `verified.json` ändern sich nicht (Test).

## Phase 3: Gerät (nur mit einer blauen Electribe und dem Okay des Besitzers)

Nichts davon läuft ohne ausdrückliche Zustimmung des Besitzers; jede Zeile wird einzeln freigegeben. Vor Beginn: Kartensicherung, Korgs blaue 2.02
mit Kopf Sampler fertig im Ordner, Netzteil dran.

- [ ] **3.1** Hacktribe mit Hacktribes eigenem Werkzeug (`-e`) aufspielen, wenn es nicht schon läuft. Das ist der bekannte Weg und der Ausgangspunkt.
- [ ] **3.2** Rückweg zuerst üben: Korgs Blaue (Kopf Sampler) in `KORG/hacktribe/System/`, SOFTWARE UPDATE, Neustart, zurück auf Hacktribe. Erst wenn das am Gerät
  geht, geht es weiter.
- [ ] **3.3** BLECH + Hacktribe (Kopf Sampler) in `KORG/hacktribe/System/` aufspielen, nur mit den Teilen aus 2.5. Prüfen: Start, Display, Tasten,
  Pad-LEDs, Hintergrundlicht, Power-Taste, Karte, Werks-Patterns, ein Pattern speichern, EXIT beim Einschalten.
- [ ] **3.4** Ordner übernehmen: mit und ohne `e2sSample.all` in `KORG/hacktribe/Sample/`.
- [ ] **3.5** Update über BLECH SysEx aus dem Editor (Kopf Sampler, `KORG/blechtribe/System/`), dann Rückweg zu Korgs Blauer und zurück.
- [ ] **3.6** Teile aus 2.5 einzeln zuschalten (Hintergrundlicht, Pad-Farben, Doom), jedes mit Rückweg bereit.
- Ergebnisse in `docs/geraetetests/` (eigene Seite), Idee 65 und Rettung bekommen den Marker "am Gerät bestätigt" oder den Befund.
- **Abbruch:** bleibt das Gerät bei "00" oder startet es nicht, gilt `docs/rettung.md` (Fall 2 und 3); ohne Antwort des Panels hilft nur das Kabel
  oder JTAG, wie dort beschrieben. Danach gilt Route 4 als nicht freigegeben.

## Phase 4: Freigabe

- [ ] Route 4 in der Seite einschalten, Release-Notiz, `verified.json` für das Release bauen.
- [ ] Idee 65 und `docs/ideen.md` auf "gebaut, am Gerät bestätigt" setzen; falls Phase 3 etwas widerlegt, steht das dort und Route 4 bleibt aus.

## Offene Fragen an den Besitzer

1. Gibt es eine blaue Electribe 2 mit Korgs 2.02 für Phase 3, und wer stellt sie bereit?
2. Soll Route 4 anfangs ohne Doom und ohne Hintergrundlicht-Plugins ausgeliefert werden (Vorschlag), oder alles auf einmal?
3. Soll der Patcher auch Hacktribe-Dateien mit Synth-Kopf annehmen (Vorschlag: ja, vor dem Patchen zurücksetzen)?
