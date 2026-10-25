# 65. BLECH mit Hacktribe für die blaue Electribe

Wunsch (25.10.): Nutzer fragen nach Hacktribe auf der blauen. Hacktribe läuft dort mit Hacktribes eigenem Werkzeug. Die Frage
hier: kann unser Patcher daraus **BLECH + Hacktribe für die blaue** machen (rote Sampler-2.02 + `hacktribe-2.patch` gibt das
Hacktribe-Abbild `7cb4825c…`, darauf der BLECH-Hacktribe-Satz `data/patches/blech.json`, am Ende der Kopf für den Synth)?

Stand 2026-10-25. Alles hier kommt aus dem Emulator, aus gelesenem Code oder aus Hacktribes öffentlichem Wiki und Skripten.
**Am Gerät nichts.** Es wurde keine Firmware gebaut und nichts an ein Gerät geschickt. Hacktribes Patch-Datei wurde weder
geladen noch kopiert; verglichen wurden nur die drei Originale auf diesem Rechner (Korg rot `1d0f0689`, Hacktribe `7cb4825c`,
Korg blau `41fc5f1c`). Keine Firmware-Bytes im Repository.

Marker: **gemessen** (ausgeführt, Befehl genannt), **hergeleitet** (aus gelesenem Code oder Wiki geschlossen, nicht laufen
gesehen), **ungeprüft** (nicht angesehen oder nur am Gerät zu klären).

## Kurzfassung

1. **Hacktribe erkennt die Hardware nicht. Es macht die blaue zur roten.** Zwischen Korgs Sampler und Hacktribe
   unterscheidet sich in der Prüfung der Nutzerdaten-Kennung (`0xC0029D78` samt Wertetabelle) genau ein Wort: die blaue Kennung
   `elec2USR` meldet bei Hacktribe den Gerätetyp `0x124` (Sampler) statt `0x123` (Synth). Der Start akzeptiert nur `0x124`.
   Damit ist die blaue für den Sampler-Code ein Sampler. BLECH fasst diese Stelle nicht an. (gemessen)
2. **Der Updater der blauen prüft den Typ im Kopf (Bytes `0x2C` bis `0x2E`), mehr nicht, was den Kopf angeht.** Korgs blaue
   Firmware nimmt Typ `0x123`, Hacktribe auf der blauen nimmt Typ `0x124`. Byte `0x12` prüft er nicht. (gemessen)
3. **Der Emulator bootet Hacktribe auf blauer Hardware**, wenn man ihm einen Flash mit der blauen Kennung gibt, auch mit der
   blauen PCM-Bank. Ein eigenes blaues Profil fehlt (siehe Abschnitt 3). (gemessen)
4. **Route 4 sieht machbar aus**: die Datei ist die BLECH-Hacktribe-Datei plus zwei Bytes im Kopf, im Emulator beweisbar bis
   zum Hauptbild und durch alle Update-Wege. Offen bleibt nur, was ein Emulator ohne Klang und ohne die echte Blaue nicht
   zeigt (Abschnitt "Offene Risiken"). Jeder Test am Gerät braucht eine blaue Electribe und das Okay des Besitzers.

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Kopf Hacktribe = Kopf Korg rot, byteweise | gemessen | Vergleich der ersten `0x100` Byte beider Dateien: kein Unterschied |
| Kopf Korg blau gegen rot: nur Byte `0x12` (`0x00` statt `0x53`) und `0x2E` (`0x23` statt `0x24`) | gemessen | derselbe Vergleich; passt zu [Blaue im Emulator](../messungen/2026-10-15-blaue-electribe.md) |
| Hacktribe-Abbild mit `0x12 = 0x00`, `0x2E = 0x23` hat SHA-256 `2b2e1c2f…ddbe`, wie Hacktribes `hash/modified-hacked-SYSTEM.VSB.sha` | gemessen | SHA-256 über `hacktribe-original.VSB` mit den zwei Bytes geändert |
| Hacktribes `e2-header.py` schreibt Sampler `0x53`/`0x24`, Synth `0x00`/`0x23`; `-e` in `e2-firmware-patch.py` tut es für Synth und nimmt `KORG/electribe/System/SYSTEM.VSB` | hergeleitet | Hacktribe-Repo `scripts/`, Wiki [How-To](https://github.com/bangcorrupt/hacktribe/wiki/How-To) |
| Kennungsprüfung `0xC0029D78` ist in Korg rot, Hacktribe und Korg blau gleich gebaut; sie vergleicht 8 Byte mit `elec2USR` und danach `ele2sUSR` | gemessen | Disassembly der drei Dateien, `0xC0029D78` (rot, Hacktribe), `0xC00270BC` (blau) |
| Der Rückgabewert für `elec2USR` steht in einem Wort bei `0xC0029DE4`: Korg `0x123`, Hacktribe `0x124`; im Bereich `0xC0029000` bis `0xC002A000` ist das der einzige Unterschied | gemessen | Byte-Vergleich Korg rot gegen Hacktribe im Bereich |
| Der Start vergleicht das Ergebnis mit `0x124` und zeigt sonst die Update-Abfrage (`0xC00289D4` bis `0xC00289E4`) | gemessen | Disassembly Hacktribe |
| Korgs Sampler auf blau markiertem Flash zeigt beim Start SOFTWARE UPDATE; Hacktribe startet bis zum Hauptbild, auf rot und blau markiertem Flash mit gleichem Anzeige-Hash und 528258064 Befehlen in 12 s | gemessen | `machine.py` mit beiden Flash-Dateien, siehe "Wie gemessen" |
| Hacktribe auf blauem Flash antwortet auf Korgs Geräte-Suche (`F0 42 50 00 00 F7`) mit Modell `0x24` wie auf rot; Korgs blaue Firmware mit `0x23` | gemessen | `machine.py --midi f042500000f7@3.0` |
| Kein Patch in `blech.json` (23 Dateien) ändert Bytes im Bereich der Kennungsprüfung oder nennt `0xC0029DE4`, `0xC00289D4`, `0xC0029D78`; der Bereich liegt außerdem in der gesperrten Startphase | gemessen | Skript über alle `changes` und `site`-Einträge; [Patcher, Regel 2](../patcher.md) |
| Das Bedienfeld hat in Korg rot, Hacktribe und Korg blau dasselbe Abbild (SHA-256 `f3ba3b25…`), die ARM-Firmware erwartet überall Version `0x96` | gemessen (Abbild), hergeleitet (gleiche Platine) | [Panel-Controller](../hintergrund/panel-controller.md), Zeilen 16 bis 18 |
| Die Tastennummern der blauen sind die des Samplers | gemessen | [Blaue im Emulator](../messungen/2026-10-15-blaue-electribe.md), Tabelle "Tasten gehen" |
| Blau: Schriftfunktion, Bildfunktion und Bildgröße `128 mal 64` wie rot | gemessen offline | [BLECH auf der blauen](../messungen/2026-10-16-blech-synth.md), Abschnitt "Schriften und Bilder" |
| Updater der blauen (Hacktribe läuft): Datei mit Kopf Sampler wird angenommen, mit Kopf Synth "Error / Invalid File" | gemessen | Probelauf, Tabelle in Abschnitt 2 |
| Updater von Korgs blauer Firmware: Datei mit Kopf Synth wird geschrieben, mit Kopf Sampler abgelehnt, ohne einen Flash-Befehl | gemessen | Probelauf, Tabelle in Abschnitt 2 |
| Die Update-Abfrage nimmt den Ordner nach dem Gerätetyp, den die laufende Firmware fest übergibt (`0x124` Sampler, `0x123` Synth): `KORG/hacktribe/`, `KORG/blechtribe/`, `KORG/electribe/` | gemessen (Hacktribe), hergeleitet (BLECH) | `tools/patch/blech_sysex.py:139`, `:1216`, `tools/patch/blechtribe.py:27`; Emulator |
| Wie sich BLECH + Hacktribe auf einer echten blauen verhält | **ungeprüft** | braucht das Gerät |

## 1. Setzt der BLECH-Hacktribe-Satz rote Hardware voraus?

**Wie Hacktribe die Hardware "erkennt":** gar nicht. Sein Wiki und seine Skripte kennen keine Erkennung, der Typ kommt von Hand
über die Option `-e` und den Kopf ([How-To](https://github.com/bangcorrupt/hacktribe/wiki/How-To), FAQ: "Error, invalid file"
bedeutet falsche Geräte-ID im Kopf). Im Abbild selbst ist der Unterschied zu Korgs Sampler das eine Wort aus der Kurzfassung.
Der Sampler-Code auf der blauen weiß also nicht, dass er auf Blau läuft, und Hacktribes Nutzer berichten, dass es geht
(Angabe der Nutzer, nicht von uns geprüft).

Was wir sonst über rot und blau wissen, und was der BLECH-Satz davon braucht:

| Bereich | Stand | Folgerung |
|---|---|---|
| Panel-Version | gleiches Panel-Abbild, überall `0x96` (gemessen) | BLECH rührt Panel-Austausch und Version nicht an; nichts Rotes |
| Tasten | gleiche Nummern (gemessen) | die Tastenhaken von BLECH (TAP, EXIT, WRITE, Pads) sprechen die Funktionen der Firmware an, nicht die Hardware |
| Display | gleiche Treiberfunktionen, 128 mal 64 (gemessen offline); Hacktribe zeichnet auf blau markiertem Flash dasselbe Hauptbild (gemessen, Emulator) | Theme, Startbild, Menüs gehen über die Firmware |
| Pad-LEDs | BLECH setzt Sollwerte im LED-Manager der Firmware (`tools/patch/pad_colors.py`); die blaue hat dafür schon einen Satz (`pad-colors-synth.json`) | gleiche Zwei-LED-Pads (hergeleitet); Pink am Gerät nur auf rot gesehen, blau **ungeprüft** |
| Hintergrundlicht (Plugins, BLECH-Menü) | ruft `0xC0016BB4` mit den Pins `0x08`, `0x10`, `0x20` (`tools/patch/script_hw.s:345`); die Funktion gibt es in der blauen Firmware an `0xC0012470` (16 Wörter gleich, `data/synth-map/auto.json:298`) | dieselbe Firmwarefunktion (gemessen); ob die blaue Leiterplatte Rot, Grün, Blau an denselben Pins hat, **ungeprüft** |
| Karte und Power-Taste | GPIO 4.1 und 7.11/7.15 (`tools/patch/card_gate.py:8`, `load_bar.py:359`); die Firmware benutzt dieselben Pins | gleiche Annahme wie oben, **ungeprüft** auf blau |
| Doom-Lader | läuft hinter der Startfunktion, nutzt die Treiber der Firmware (`tools/patch/doom_loader.py`) | am meisten Annahmen auf einmal; für Route 4 erst nach den anderen Teilen entscheiden |
| Sample-Teile (Ladebalken, Sample-Fehler, Preset-Tabellen, Sammeldatei, Tasten vom Rechner) | Sampler-Code, der auf blau genauso läuft wie auf rot | prüfbar nur bis zum Emulator; Samples und Klang auf der blauen sind das Risiko von Hacktribe selbst, nicht von BLECH |

**Urteil (hergeleitet):** der Satz setzt rote Hardware nur an den Stellen voraus, an denen Hacktribe es auch tut: Sampler-Code
auf einem Gerät, dessen Panel, Display und SoC denselben Treibern gehorchen. Offene Annahmen sind Hintergrundlicht-Pins, Pad-Farben und Doom.

## 2. Was der Updater der blauen prüft, und welchen Kopf spätere Updates brauchen

Gemessen im Emulator (Hacktribe-Original `7cb4825c` läuft auf Flash mit blauer Kennung; Korgs blaue `41fc5f1c` läuft auf blau
markiertem Flash), Datei jeweils als `SYSTEM.VSB` im Ordner der laufenden Firmware, DATA UTILITY, SOFTWARE UPDATE, ENTER:

| Läuft | Datei | Ergebnis |
|---|---|---|
| Hacktribe auf blau | Hacktribe, Kopf Sampler (`0x12 = 0x53`, `0x2E = 0x24`) in `KORG/hacktribe/System` | angenommen ("Now 2.02, Next 2.02, press Enter") |
| Hacktribe auf blau | Hacktribe, Kopf Synth (`0x00`, `0x23`) | "Error / Invalid File" |
| Hacktribe auf blau | nur `0x12 = 0x00` geändert (`0x2E` bleibt `0x24`) | angenommen |
| Hacktribe auf blau | nur `0x2E = 0x23` geändert (`0x12` bleibt `0x53`) | abgelehnt |
| Hacktribe auf blau | gleiche Datei in `KORG/electribe/System` statt `hacktribe` | abgelehnt: "Error / No File" |
| Hacktribe auf rot | Kopf Sampler / Kopf Synth | angenommen / abgelehnt |
| Korg blau | Hacktribe mit Kopf Synth in `KORG/electribe/System` | geschrieben (512 Löschbefehle, 8192 Seiten), Neustart bis Hauptbild, Kennung `KORGelec2USR` bleibt (Flash ohne PCM-Bank) |
| Korg blau | Hacktribe mit Kopf Sampler | abgelehnt, null Flash-Befehle |
| Korg blau | Hacktribe mit nur `0x12` geändert | abgelehnt |
| Korg blau | Hacktribe mit nur `0x2E = 0x23` | geschrieben |
| Hacktribe auf blau (nach dem Hin) | Korgs blaue `41fc5f1c` mit Kopf Sampler in `KORG/hacktribe/System` | geschrieben (512/8192), Neustart bis Hauptbild, Kennung `KORGelec2USR` und Rest des Flashs unverändert |
| Hacktribe auf blau | Korgs blaue mit unverändertem Kopf Synth | "Error / Invalid File", null Flash-Befehle |

Weitere Prüfungen der Datei (gemessen auf Korgs blauer Firmware mit der Hacktribe-Datei): ein geänderter Wert bei Byte `0x3C` wird
abgelehnt; ein geändertes Byte im freien Lauf der Nutzlast wird angenommen (keine Prüfsumme darüber); 16 Byte mehr oder weniger
wurden ebenfalls angenommen, darauf sollte man sich nicht verlassen. Aus dem Code gelesen (`0xC003AD00` bis `0xC003AE5C`): 16 Byte
Kennung `KORG SYSTEM FILE`, ein 6-Byte-Vergleich ab `0x20`, die Versionsbytes `0x2A` und `0x2B` gegen eine Tabelle je Typ, die
Länge bei `0x3C` gegen die Flash-Größe; den Text des 6-Byte-Vergleichs haben wir nicht nachgesehen.

**Ergebnis für die Kopf-Wahl (gemessen für Hacktribe, hergeleitet für BLECH):**

- **Erstinstallation von Korgs blauer Firmware aus:** Kopf Synth (`0x12 = 0x00`, `0x2E = 0x23`), Ordner `KORG/electribe/System/`. Das
  ist Hacktribes `-e` und ergibt `2b2e1c2f…`. Sampler-Kopf wird sauber abgelehnt (vor dem Schreiben).
- **Spätere Updates, wenn schon Hacktribe oder BLECH auf der blauen läuft** (über SD-Karte oder über BLECH SysEx `0x65`/`0x66`):
  **Kopf Sampler**, wie für rot. Das ist auch das, was der Editor schon hat: die Datei `ORIGINAL.BIN`, die BLECH neben die Update-Datei
  legt, ist die Hacktribe-Datei mit Sampler-Kopf, und BLECH SysEx prüft den Kopf nicht selbst (`tools/patch/blech_sysex.py`: kein
  Kopfvergleich, der Ordner kommt aus der Firmwarefunktion mit `FOLDER_ID 0x124`). Ein Synth-Kopf wäre hier falsch und würde
  abgelehnt.
- Wer schon Hacktribe mit Synth-Kopf auf die blaue gebracht hat: die Datei auf der Karte hat Typ `0x123`, das Gerät läuft aber mit Typ
  `0x124`. Als Eingabe für den Patcher also zuerst auf Sampler-Kopf zurücksetzen.

## 3. Bootet unser Emulator Hacktribe auf blauer Hardware?

**Ja, mit einem eigenen Flash (gemessen).** Befehle unter "Wie gemessen". Ergebnis:

| Lauf (12 oder 20 s Gerätezeit) | Ergebnis |
|---|---|
| Hacktribe, Flash mit Kennung `KORGele2sUSR` (rot) | Hauptbild, keine Assertion |
| Hacktribe, Flash mit Kennung `KORGelec2USR` (blau) | dasselbe Bild, gleiche Befehlszahl, keine Assertion |
| Hacktribe, 16-MiB-Flash mit blauer PCM-Bank aus den eigenen WAVs (`synth_pcm_flash.py`) | Hauptbild, keine Assertion |
| Korgs Sampler (`1d0f0689`), blaue PCM-Bank-Flash | SOFTWARE UPDATE statt Hauptbild: Korgs Sampler lehnt die blaue Kennung ab |

**Was für ein richtiges "blaues Profil" fehlt:**

1. Die Kennung kommt aus dem Build, nicht aus der Hardware: `Profile.user_mark` nimmt `USER_MARKS["synth"]` nur für den Build `synth`
   (`tools/emu/firmware.py:76`, `:77`, `:162`). Ein Hacktribe- oder BLECH-Abbild bekommt immer die rote Kennung
   (`tools/emu/machine.py:219`). Heute geht es nur über `--flash` von Hand. Es braucht einen Schalter "Hardware: rot oder blau" in
   `machine.py`, `runner.py`, `check.py` und dem Dienst (`server.py:42` trennt `flash-synth.bin` nach Build, nicht nach Hardware).
2. `blank_flash` legt die Werksbank des Samplers nur bei der Sampler-Kennung an (`machine.py:80` bis `:89`); für blau und Sampler-Code
   gäbe es weder die noch eine PCM-Bank. Für den echten Fall braucht es die lokale Bank aus `synth_pcm_flash.py`, mit eigenen WAVs.
3. `check.py` nimmt einen Flash entgegen, aber die Fälle (Kurzprüfung, Voll, Update-Abfrage ohne Kennung) sind nur mit rotem Flash gelaufen.
   Sie müssen mit blauem Flash laufen und ihre Erwartungen (Ordner, Kopf des Updaters) pro Hardware kennen.
4. Grenze, die bleibt: kein Klang, kein DSP, keine Leiterplatte. Der Emulator zeigt "bootet, Haken laufen, Update-Wege gehen" und
   nichts über LED-Pins, Hintergrundlicht oder die Sample-Bank auf echter blauer Hardware.

Dazu ein Fehler im Browser-Teil (gemessen mit `node`): `buildOf` in `src/firmware.mjs:35` sagt für ein Hacktribe-Abbild mit Synth-Kopf
`"synth"`, weil es den Kopf zuerst prüft; `firmwareName` (`:73`) sagt richtig "Hacktribe Synth". Mit `buildOf` würde die Seite die Datei
für Korgs blaue Firmware halten und den falschen Satz laden. Für Route 4 muss die Reihenfolge so sein, dass der Hacktribe-Lauf
(`HACKTRIBE_CODE`) vor dem Kopf entscheidet.

## 4. Der Weg zurück zu Korgs blauer Firmware (Vorschlag für `docs/rettung.md`)

Hacktribes Wiki sagt: Korgs blaue 2.02 mit `e2-header.py DATEI sampler` bearbeiten und an den Ort legen, den Hacktribe liest. Im
Emulator (Abschnitt 2) stimmt das: ohne die Änderung "Invalid File", mit ihr wird geschrieben und die blaue startet. Vorschlag für
die Seite und `data/rescue.mjs`:

> **Läuft BLECH oder Hacktribe auf der blauen und du willst zurück zu Korgs Original.** Nimm Korgs blaue Firmware 2.02 (aus Korgs
> System Updater, unverändert). Im Kopf der Datei zwei Bytes ändern: Byte `0x12` auf `0x53`, Byte `0x2E` auf `0x24` (das macht
> Hacktribes `e2-header.py DATEI sampler`; unser Patcher bietet es als eigenen Knopf an). Die Datei als `SYSTEM.VSB` nach
> `KORG/blechtribe/System/` legen (bei Hacktribe `KORG/hacktribe/System/`), dort darf nur diese Datei liegen. DATA UTILITY,
> SOFTWARE UPDATE, durchlaufen lassen, aus und wieder an. Danach läuft Korgs Original, und weitere Updates gehen wieder mit der
> unveränderten Datei in `KORG/electribe/System/`. Ohne die Änderung zeigt das Gerät "Error / Invalid File" und schreibt nichts.
> Stand: im Emulator mit Hacktribe geübt (gemessen), mit BLECH hergeleitet, am Gerät offen.

Dazu in die Tabelle "Welche Datei in welchen Ordner":

| Läuft gerade | Pfad auf der Karte | Kopf der Datei |
|---|---|---|
| Hacktribe auf der blauen | `KORG/hacktribe/System/SYSTEM.VSB` | Sampler (`0x12 = 0x53`, `0x2E = 0x24`) |
| BLECH + Hacktribe auf der blauen | `KORG/blechtribe/System/SYSTEM.VSB` | Sampler |
| Korgs Original (blau) | `KORG/electribe/System/SYSTEM.VSB` | Synth, unverändert |

Die Rettungsfälle 2 bis 4 ändern sich nicht: die Start-Abfrage hängt an der Kennung im Flash, und der Sampler-Code mit Hacktribe
nimmt beide Kennungen an (`rettung.md:43`, hier noch einmal gemessen). Der Bootloader prüft den Kopf nicht, er liest 2 MiB ab
`0x20000` ohne Prüfung (`rettung.md`, Fall 3). Eine falsche Kopf-Wahl ist ungefährlich, weil der Updater sie vor dem ersten
Flash-Befehl ablehnt (gemessen, null Flash-Befehle). Wiki und FAQ nennen außerdem eine fertige `synth-revert-SYSTEM.VSB` aus dem
Hacktribe Tutorial; die haben wir nicht angesehen. Zu klären am Gerät: ob Muster und Einstellungen der blauen nach der Rückkehr
unverändert sind. Hacktribes Wiki sagt, ein Factory Reset stellt Werkspatterns und Globals wieder her.

## 5. Kartenordner auf der blauen: `electribe`, `hacktribe`, `blechtribe`

| Schritt | Ordner | Beleg |
|---|---|---|
| Erstinstallation aus Korgs blauer Firmware | `KORG/electribe/System/SYSTEM.VSB`, sonst keine `.VSB` im Ordner (die Firmware fragt auch `BOOT.VSB`, `USER.VSB`, `PCM.VSB`) | gemessen ([Update der blauen](../messungen/2026-10-16-blech-synth.md), "Prüfumgebung"; heute noch einmal mit der Hacktribe-Datei) |
| Erstinstallation, wenn schon Hacktribe auf der blauen läuft | `KORG/hacktribe/System/SYSTEM.VSB` (ältere Hacktribe-Versionen laut Wiki `KORG/electribe sampler/System`) | gemessen für unser Abbild; die Wiki-Angabe hergeleitet |
| Spätere Updates mit BLECH + Hacktribe | `KORG/blechtribe/System/SYSTEM.VSB` | hergeleitet: `blechtribe.py` ersetzt dieselben zwei Zeichenketten (`:27`), die den Ordner `hacktribe` wählen, und die Update-Funktion übergibt feste `0x124`; auf rot am Gerät bestätigt ([Gerätetest](../geraetetests/blech-datei.md)) |
| BLECH-Synth-Satz (Route 3), spätere Updates | bleibt `KORG/electribe/System/` | der Satz hat keinen Ordner blechtribe ([Synth-Messung](../messungen/2026-10-16-blech-synth.md), Tabelle) |

**Ordner übernehmen beim ersten Start** (`tools/patch/script_migrate.s`, [Messung](../messungen/2026-10-19-ordner-uebernehmen.md)):
der Code ist Sampler-Code und läuft auf der blauen, so wie er ist (hergeleitet; im blauen Profil noch nicht gemessen). Er fragt nur,
wenn `KORG/blechtribe/Sample/e2sSample.all` fehlt und `KORG/hacktribe/Sample/e2sSample.all` oder
`KORG/electribe sampler/Sample/e2sSample.all` da ist (`script_migrate.s:605` bis `:615`). Folgen für die blaue:

- Wer von Korgs blauer Firmware kommt, hat `KORG/electribe/`. Den Ordner schaut die Übernahme nicht an (gelesen). Seine Pattern-Sicherungen
  und Exporte kommen nicht mit; das ist auch gut so, die Dateiformate der Synth-Firmware sind nicht die des Samplers (hergeleitet,
  nicht geprüft).
- Wer von Hacktribe kommt und dort keine `e2sSample.all` hatte (auf der blauen gibt es keine Sample-Slots), bekommt keine Frage. Der
  Ordner `KORG/blechtribe` entsteht dann leer, Einstellungen und Plugins liegen neu darin.
- Das ist kein Fehler, sollte aber auf der Patcher-Seite stehen, damit niemand denkt, seine Dateien seien weg.

## Die vier Routen

| Route | Eingabe | Satz | Kopf des Ergebnisses | Erstinstallation | Spätere Updates | Stand |
|---|---|---|---|---|---|---|
| 1. rot, nur BLECH | Korgs rote 2.02 (`1d0f0689`) | `blech.json`, Teile für Korgs Original | Sampler | `KORG/electribe sampler/System/` | `KORG/blechtribe/System/` | gebaut, am Gerät bestätigt |
| 2. rot, BLECH + Hacktribe | `7cb4825c` (aus der roten 2.02 plus `hacktribe-2.patch`) | `blech.json`, Teile für Hacktribe | Sampler | `KORG/hacktribe/System/` | `KORG/blechtribe/System/` | gebaut |
| 3. blau, BLECH-Synth-Satz | Korgs blaue 2.02 (`41fc5f1c`) | `blech-synth.json` | Synth (unverändert) | `KORG/electribe/System/` | `KORG/electribe/System/` | gebaut, im Emulator geprüft, am Gerät offen |
| 4. blau, BLECH + Hacktribe (neu) | wie Route 2 (auch die Datei aus Hacktribes `-e`, nach Zurücksetzen auf Sampler-Kopf) | `blech.json`, Teile für Hacktribe, dazu Auswahl der Teile (Doom, Hintergrundlicht) | von Korgs Blau aus: Synth (`0x12 = 0x00`, `0x2E = 0x23`); von Hacktribe oder BLECH aus: Sampler | `KORG/electribe/System/` (von Korg blau) oder `KORG/hacktribe/System/` (von Hacktribe) | `KORG/blechtribe/System/`, Kopf Sampler | Idee; Emulator-Teilbeweis in diesem Dokument, Gerät offen |

Der Unterschied zwischen Route 3 und 4: Route 3 ist Korgs Synth-Firmware mit unserem Satz (eigene Adressen, kein Hacktribe). Route 4
ist Sampler-Code mit Hacktribe auf blauer Hardware; sie bekommt den Funktionsumfang von Hacktribe und den ganzen Satz von Route 2
und verliert, was nur Korgs Synth-Firmware hat. Ob die blaue unter Sampler-Code ihre Oszillatoren und Werks-Patterns behält, haben
wir nicht geprüft.

## Offene Risiken

| Risiko | Marker | Was klärt es |
|---|---|---|
| Hintergrundlicht-Pins, Pad-LED-Farben, Power-Taste und Kartenerkennung der blauen Platine sind dieselben wie rot | ungeprüft | blaues Gerät, mit Okay des Besitzers; sonst Teile abschalten, die die Pins selbst setzen |
| Der Sampler-Code und sein DSP-Programm laufen auf der blauen mit der Bank und den Nutzerdaten der Synth-Firmware | ungeprüft (Hacktribe-Nutzer berichten, dass es geht) | blaues Gerät; im Emulator nur bis "bootet" |
| Muster und Einstellungen im Flash der blauen unter Sampler-Code und nach der Rückkehr | ungeprüft | Wiki: Factory Reset stellt sie her; am Gerät prüfen |
| Doom-Lader: Treiber, Tasten beim Einschalten | ungeprüft | Teil für Route 4 erst nach den anderen freigeben |
| `buildOf` hält die Datei für die blaue (Abschnitt 3) | gemessen | Fix und Test in Phase 2 |
| Die zwei Köpfe verwechselt | gemessen: ungefährlich, der Updater lehnt ab | Patcher fragt "Was läuft gerade auf deiner blauen?" und nennt den Ordner |
| Die Liste geprüfter Kopien (`data/patches/verified.json`) und das Release brauchen neue Prüfsummen-Paare | hergeleitet | Phase 2 |
| Ältere Hacktribe-Versionen lesen `KORG/electribe sampler/System` | hergeleitet (Wiki) | der Patcher nennt für Route 4 beide Pfade, wie Hacktribe selbst |
| Kein Weg zurück ohne JTAG, wenn die Datei vor den Rettungswegen hängt | wie bei jedem Patch | die Regeln aus [Patcher](../patcher.md) bleiben, Phase 1 prüft die Rettungswege auf blauem Profil |

## Wie gemessen

Alle Läufe offline im Emulator, mit den eigenen Dateien des Besitzers (Korg rot, Hacktribe, Korg blau, dazu ein 16-MiB-Flash
mit blauer PCM-Bank aus `synth_pcm_flash.py`). Nichts davon liegt im Repository.

```
# Flash mit Kennung der blauen (und der roten) schreiben, außerhalb des Repositorys
tools/emu/.venv/bin/python -c "import sys; sys.path.insert(0,'tools/emu'); import machine, firmware; \
  open('blau.bin','wb').write(machine.blank_flash(firmware.USER_MARKS['synth']))"
tools/emu/.venv/bin/python tools/emu/machine.py --vsb hacktribe-original.VSB --flash blau.bin --seconds 12 --png out.png
tools/emu/.venv/bin/python tools/emu/machine.py --vsb hacktribe-original.VSB --flash blau.bin --seconds 6 --midi f042500000f7@3.0
```

Die Update-Läufe (Abschnitt 2) nutzen `Rig`, `run_update` und `reboot` aus `tools/emu/synth_update_probe.py` mit eigenen Kopf-Varianten
der Dateien; die Seite "SOFTWARE UPDATE" wird über den Titel-Hash der Hacktribe-Seiten gefunden (`highram_watch.py:55`). Die Skripte
waren Wegwerf-Code außerhalb des Repositorys. Phase 1 des Umsetzungsplans zu dieser Idee
macht daraus `tools/emu/hacktribe_blue_probe.py` mit Tests, die ohne Korg-Daten laufen (selbstgebaute Abbilder) und mit
`E2_HACKTRIBE_VSB` und `E2_BLUE_VSB` die echten.
