# Nativer Doom-SD-Lader

**Historischer Befund vor der Integration von `integ/overnight`.** Die hier
genannten BLECH-v8-Artefakte und alten Speicheradressen sind kein aktueller
Gerätekandidat. Neue Firmware muss separat gebaut und geprüft werden.

Stand 15.10.2026. Schritt 1 im Worktree `feature/doom-runtime`.
Alle Ausführungen dieses Berichts fanden im Firmwareemulator statt.
Kein echtes Gerät wurde beschrieben, geflasht oder gestartet.

## Aufbau und Grenzen

Der Haken bei `0xC002ADB0` ruft zuerst die originale Initialisierung auf.
Nur exakt SHIFT + TAP, Maske `0x408`, ohne hohe Tastenbits, ohne anderen
Startmodus und ohne Panelupdate führt in den eigenen Lader. Der vorhandene
Startbildhaken davor bleibt bestehen. Normalpfad und Bootloader bleiben
in ihrer Zuständigkeit.

| Bereich | Zweck |
|---|---|
| `0xC0173000..0xC017B000` | eigener ROM-Lader |
| `0xC017B000..0xC0180000` | eigene FatFs-Strukturen und Laderzustand |
| `0xC0180000..0xC0181000` | gemeinsame Diagnose |
| `0xC1000000..0xC17F0000` | geladene Engine, BSS und Heap |
| `0xC17F0000..0xC1800000` | eigener 64-KiB-Taskstack |

Der Builder akzeptiert nur zwei bereits vermessene Firmware-SHA256,
prüft den Originalaufruf und verlangt ausschließlich `FF` im gesamten
reservierten ROM-/Zustandsbereich. Linkergrenzen verhindern Überlauf.
Ausgaben im Repo oder in anderen Git-Checkouts werden vor jedem
Schreibzugriff abgelehnt, einschließlich symbolischer Links.

Der Doom-Zweig startet den 1-kHz-Systemtick ohne Sampler-Callbacks,
aktiviert nur die SD-Task und die Eingabe und mountet die Karte. Der Lader
liest `SD:/KORG/blechtribe/Doom/doom.bin` über die nativen FatFs-Funktionen
in 4096-Byte-Stücken. Größe, gelesene Länge, Rückgabewerte und SHA256 müssen
zum beim Build eingebauten Programm passen. Der FIL wird vor dem Sprung
geschlossen. Fehler führen zu `DOOM ERROR`, Code und bedienbarem Ein/Aus.
Nach teilweise erfolgter Treiberinitialisierung startet kein Sampler als
verdeckter Ersatz.

Vor der Übergabe werden der Task-1-Descriptor und SP auf den eigenen Stack
gesetzt. Der Lader reinigt die DCache-Zeilen der Arena, leert den Schreibpuffer
und invalidiert ICache und Prefetchpuffer (Nachtrag 22.10.: den Prefetch-Befehl `c7, c5, 4` gibt es auf dem ARM926 nicht,
am Gerät hängt er; er ist raus, siehe [Doom am Gerät](2026-10-22-doom-am-geraet.md)). Die ARM926-Befehle sind aus dem
[ARM926EJ-S TRM](https://documentation-service.arm.com/static/5e8e3d1088295d1e18d3a9b2%3Ftoken%3D)
abgeleitet. Unicorn prüft ihre Ausführung, modelliert jedoch keine echten
Cacheinhalte. Hardwarewirkung bleibt ungeprüft.

Die Arena liegt im sonstigen Sampler-Arbeitspuffer. Ihre Verfügbarkeit ist
aus dem ausgelassenen Samplerstart und dem Tasktrace hergeleitet, keine
allgemeine Reservierung für beliebige Firmwarepfade. Randwächter belegen
keine vollständige Schreibisolation.

## Gemessener V2-Zwischenstand

Dieser Abschnitt bezieht sich ausdrücklich auf das V2-Abbild vor der
anschließenden Spielbild-Polaritätskorrektur in Runtime V3.

| Artefakt | SHA256 |
|---|---|
| BLECH v8 als Referenz | `584f5b7a057adf23c04f07da09c8669c5410a68c494bdd19a66245fc8cfab9cb` |
| Runtime V2, 450612 Byte | `7f7500bca523e12df75836e198c87327c5dd171e01b93342c6e981bfe56be7c7` |
| V2-Abbild, 2724 Byte eigener Lader | `b6e22dc9ad6bb22e67869a9714d6e76f636aa89549447bf777367074464f9287` |

- Produktmatrix: 34/34. 18 Normal-, EXIT-, Rettungs- und Updatekontexte
  mit identischen Tasks, Sampleraufrufen, Bildschirm, LCD und allen LEDs;
  sechs SD-/Dateifehler samt Schreibschutz sowie Uhr und zwei Powerwege.
- Power: echte Panel-UART-Nachricht Typ 6, Loslassen lässt eingeschaltet,
  Haltemeldung schaltet über den nativen letzten GPIO-Dienst aus. Weder
  vollständiger Sampler-Ausschaltpfad noch Samplerspeicherung werden aufgerufen.
- Uhr: 1000 Kernelticks zwischen 1,5000106 und 2,5 emulierten Sekunden.
- `check.py`: 67/67, einschließlich BLECH-Menü und Effektschaltung.
- `npm test`: 484 Tests, 419 bestanden, 65 wegen fehlender lokaler Daten
  oder nicht gesetztem Pflichtgate übersprungen, kein Fehler.
- SHA256 und Bereichsprüfungen haben eigene Tests mit Standardvektoren,
  Blockgrenzen, inkrementeller Verarbeitung und verbotenen Ausgabepfaden.

Die erste Matrix benutzte versehentlich `SYSTEM.VSB` als Referenz zu einem
auf BLECH v8 aufgebauten Kandidaten. Deren LED-Unterschied war kein
Normalpfadfehler. Der korrigierte Vergleich ist vollständig grün. Ein
vorgeschalteter bytegenauer Basisvergleich verhindert diesen Testfehler.
Die erste Uhrprüfung lag vor Timerstart und wurde durch die native Messung
nach Timerstart ersetzt. Diese älteren roten Ergebnisse werden nicht als
Produktfehler oder spätere Freigabe verwendet.

## Reproduktion und vollständige Logs

Lokales Belegverzeichnis außerhalb des Repos:
`$doom_artifacts/`.

| Beleg | Datei |
|---|---|
| Produktmatrix und Power | `regression-v2/regression.json` |
| Produktmatrix-Kurzfassung | `regression-v2-summary.json` |
| Firmwareprüfung | `check-v2.json`, `check-v2.log` |
| Vollständiger Testlauf | `npm-boot-step.log` |
| Native Unitprüfung | `runtime-v2-unit.log` |
| Compiler, Größen, Symbole | `runtime-v2/`, `runtime-v2-build.log` |
| Lader und lokales Abbild | `bootstrap-v2/manifest.json` |

Build- und Spielbefehle stehen in [Buildanleitung](../../tools/doom/README.md). Der genaue Aufruf
der Firmwareprüfung lautete:

```sh
tools/emu/.venv/bin/python tools/emu/check.py \
  --base "$doom_base" \
  --patched $doom_artifacts/bootstrap-v2/SYSTEM-doom-emulator.VSB \
  --flash "$doom_flash" \
  --allow-code 0x2aeb0:4 --allow-code 0x173100:2724
```

Der erste Span ist exakt der ersetzte Aufruf. Der zweite umfasst exakt den
eigenen, größenbegrenzten Lader und seine Literale. Keine Rettungsroutine,
kein DSP-Strom und kein pauschaler Startbereich ist freigestellt.

Offen nach diesem Schritt: endgültiger gemeinsamer Bedienlauf, Tonpfad,
weitere WADs und Level sowie sämtliche Gerätebelege.
