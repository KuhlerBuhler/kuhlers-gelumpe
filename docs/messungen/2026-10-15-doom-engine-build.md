# Doom Engine: nativer ARM926 Build und Spiellauf

**Historischer Befund vor der Integration von `integ/overnight`.** Die hier
genannten BLECH-v8-Artefakte und alten Speicheradressen sind kein aktueller
Gerätekandidat. Neue Firmware muss separat gebaut und geprüft werden.

Stand: 15.10.2026. Ausschließlich lokale Prüfung mit eigenen Adaptern.
Keine Firmware geändert, kein echtes Gerät verwendet, nichts gepusht.

## Ergebnis

Gemessen: Die originale, unveränderte Doom-Engine aus `doomgeneric` lässt
sich für ARM926 bauen und führt unter Unicorn eine echte Karte aus.
Spielzustand, Renderer und Tasteneingabe funktionieren im isolierten Test.
Die bisherigen Standardläufe verwenden `-nomonsters` und `-nosound`,
also ohne Gegner und ohne Ton. Ein zusätzlicher Lauf aktiviert die Gegner,
bleibt aber stumm; dieser Beleg ist unten getrennt dokumentiert.
Dies belegt die grundsätzliche Eignung der Engine für den Prozessor.
Die Electribe-Anbindung und deren erreichbare Bildrate sind damit offen.

Hergeleitete Empfehlung: Originalengine beibehalten, ihre Plattformgrenze
an den getrennten Doom-Startmodus anschließen und mit einem zunächst
stummen Port beginnen. Ein kleiner eigener Raycaster ist nicht nötig.
Der wahrscheinlichste Engpass liegt jetzt beim konfliktfreien Treiberstart
und bei SD-, Display- und Eingabeanbindung, nicht beim ARM Befehlssatz.

## Quellen und Lizenzen

- Engine: [ozkl/doomgeneric](https://github.com/ozkl/doomgeneric/tree/e257a09527062bfb986b6e5e0780839b6cbd5b71),
  Commit `e257a09527062bfb986b6e5e0780839b6cbd5b71`.
  Quelldateien nennen GPL Version 2 oder neuer. Alle 80 übernommenen
  Engine-Übersetzungseinheiten bleiben im Test unverändert außerhalb Repo.
- Compiler: [Arm GNU Toolchain 14.2.Rel1 für Darwin ARM64](https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi.tar.xz),
  GCC 14.2.1, Newlib und libgcc. Portable Entpackung unter `/tmp`,
  keine Systeminstallation.
- Testdaten: [Freedoom 0.13.0](https://github.com/freedoom/freedoom/releases/tag/v0.13.0),
  Phase 1. Dessen `COPYING` nennt eine BSD Lizenz mit drei Klauseln.
  Das WAD liegt nur unter `/tmp`; keine Doom-Spieldaten oder Korg-Daten
  wurden ins Repo übernommen.
- Emulator: Unicorn 2.1.4 mit explizitem CPU Modell `UC_CPU_ARM_926`.

Die Engine ist Doom; die Inhalte im gemessenen Lauf stammen von Freedoom.
Ein eigenes rechtmäßig bereitgestelltes Doom IWAD bleibt ein separater
späterer Kompatibilitätstest.

## Buildbeleg

Gemessen: 81 Objektdateien einschließlich eines eigenen Testadapters.
Compileroptionen: `-mcpu=arm926ej-s -marm -mfloat-abi=soft -Os`,
Linken mit Newlib und libgcc, ohne Betriebssystem und ohne Startbibliothek.
`nm -u` liefert keine undefinierten Symbole.
`readelf -h -A` meldet ELF32 Little Endian, ARMv5TEJ, EABI Version 5 und
Softfloat. Die eingebundene Laufzeit enthält auch ARM926-kompatiblen Thumb-1
Code. Keine FPU und keine ARMv7 Erweiterung werden vorausgesetzt.

| Abschnitt | Byte |
| --- | ---: |
| Text einschließlich Konstanten | 387100 |
| Initialisierte Daten | 61340 |
| BSS | 241180 |
| Summe | 689620 |
| ELF Datei einschließlich Tabellen | 569800 |

Der Linker warnt vor einem lesbaren, schreibbaren und ausführbaren
LOAD Segment. Die Probe bildet absichtlich ein einfaches RAM Programm ab;
Speicherschutz und endgültiges Ladeformat sind hier nicht implementiert.
Die künstliche Ladeadresse `0x01000000` ist keine Gerätefreigabe.

## Spiellauf und Eingabe

Gemessen, Standardlauf ohne Gegner und ohne Ton mit explizitem
16 MiB Zonenbudget:

- 120 Ausgaben bis Spieltick 46, 24 verschiedene RGB Bilder.
- Erstes sichtbares Spielbild mit weitergelaufenem Spiel: Ausgabe 38,
  Spieltick 5. Vorherige schwarze Bilder gehören zum Startübergang.
- Letzte Ausgabe: 1224 gesetzte Pixel im 128 mal 64 Bild.
- 13619 Datei-Leseaufrufe, 13945028 gelesene Byte.
- Keine gemeldeten ungültigen Speicherzugriffe und kein Engineabbruch.
- Angeforderter Heap: 17132064 Byte, darin die gewählte 16 MiB Spielzone.

Gemessen, gepaarter Eingabelauf mit sonst gleicher Konfiguration:
Rechte Richtungstaste bei Spieltick 5 gedrückt und bei Spieltick 12
losgelassen. Letzter Spieltick bleibt 46. Die Blickrichtung wechselt
von `0` auf `4106223616`; das letzte RGB Bild und das monochrome Bild
unterscheiden sich vom Standardlauf. Das belegt Verarbeitung der Taste
durch die echte Spielsimulation ohne Gegner und ohne Ton, nicht bloß
das Registrieren eines Events.

Gemessen, zusätzlicher Lauf mit dem ursprünglichen 6 MiB Zonenbudget:
Ebenfalls 120 Ausgaben bis Spieltick 46 und identisches letztes Bild.
Ein zusätzlicher abschließender Lauf mit 6 MiB und aktiviertem Eingabetest
besteht ebenfalls den verschärften Selbstcheck mit geänderter Blickrichtung.
Der insgesamt von Newlib angeforderte Heap sinkt auf 6646304 Byte.
Die kleineren Caches verursachen 15195 Leseaufrufe und 15558852 gelesene Byte.

Hergeleitete RAM Untergrenze für diese getestete Karte:
689620 Byte Code/Daten/BSS plus 6646304 Byte angeforderter Heap ergeben
7335924 Byte, rund 7,0 MiB. Stack, Treiber und Sicherheitsreserve kommen
dazu. Das ist weder der schlechteste Fall aller Karten noch ein Nachweis,
dass dieser Bereich auf der Electribe frei bleibt. Die Probe reserviert
32 MiB für Heap und nutzt eine künstliche 96 MiB RAM Abbildung.

## Stackmessung und erstes RAM Ziel

Gemessen, zusätzlicher 6 MiB Eingabelauf mit `UC_HOOK_MEM_WRITE`,
beschränkt auf das 1 MiB Stackfenster unter dem Startwert
`SP=0x06FFF000`: 8863450 Schreibereignisse. Niedrigste beschriebene Adresse
und niedrigster bei einem solchen Schreibzugriff beobachteter SP sind
beide `0x06FFEB18`. Das beobachtete Stack-Hochwasser beträgt damit
1256 Byte. Der Lauf erreicht erneut Spieltick 46 und dasselbe letzte
Eingabebild ohne Fehler. Das ist ein Messwert für Initialisierung und
die getestete Kartenfolge, keine statische Obergrenze aller Enginepfade.

Hergeleiteter Vorschlag für die nächste Integrationsprobe: 64 KiB eigener
Engine-Stack. Das liegt mehr als Faktor 50 über dem gemessenen Bedarf.
Interruptkontexte, tiefere Karten und Fehlerpfade wurden dabei nicht
abgedeckt und müssen im integrierten Port erneut gemessen werden.

Hergeleitete erste Zielreserve: 8 MiB für Engine, deren Heap und Stack
bei festem 6 MiB Doom-Zonenbudget. Die gemessenen Code/Daten/BSS und der
angeforderte Heap ergeben mit 64 KiB Stack zusammen 7401460 Byte. Der zusätzlich geprüfte Gegnerlauf liegt wegen leicht
anderer statischer Daten und Heap-Ausrichtung acht Byte darüber, bei
7401468 Byte; in 8 MiB verbleiben dann rechnerisch 987140 Byte Reserve. Treiber und
Firmwaretasks gehören außerhalb dieses Enginebudgets. Eine freie,
konfliktfreie 8 MiB Geräteadresse ist damit ausdrücklich nicht bewiesen.
Bei anderem Zonenbudget ist diese Rechnung neu anzusetzen.

Der Stackbeleg liegt unter `run-stack/result.json` und `run-stack.log`.
SHA256 des Ergebnisdokuments:
`d13e83f1763eb98debd86437ba635449d75b00bfdb2eac67871c99c4f94ac122`.

## Zusatzlauf mit Gegnern

Der Builder bietet zusätzlich `--monsters`. Der Standard bleibt unverändert
bei `-nomonsters`; nur mit diesem Schalter fehlt das Argument im eigenen
Startadapter. Die Argumentanzahl wird aus dem tatsächlich erzeugten Array
berechnet. `build.json` dokumentiert den Schalter und stets deaktivierten Ton.
Aus dem unveränderten Enginecode abgeleitet: Ohne `-nomonsters` wird die
normale Gegnererzeugung ausgeführt. Es ist kein eigener Gegnerersatz vorhanden.

Gemessen: Genau ein zusätzlicher Build und Lauf mit 6 MiB Zone,
`--monsters` und injizierter Richtungstaste. Exitcode 0, 120 Ausgaben,
Spieltick 46, Blickrichtung `4106223616`, 1162 helle Bildpixel am Ende,
keine Fehler. Der angeforderte Heap beträgt 6646320 Byte; das beobachtete
Stack-Hochwasser bleibt 1256 Byte. Text/Daten/BSS ergeben 689612 Byte.
Das letzte Bild unterscheidet sich vom gegnerfreien Lauf. Eine vollständige
Kampfsituation, längeres Überleben, Ton oder weitere Karten sind damit
nicht geprüft.

Belege: `build-monsters/build.json`, `build-monsters/size.txt`,
`build-monsters.log`, `run-monsters/result.json`, `run-monsters/console.log`
und `run-monsters.log` unter dem genannten externen Probeverzeichnis.
ELF SHA256: `45ca0b33009e954e688ef8fbd8b3b1634a8915ca8772ba07597a26b1533c1dbd`.
Ergebnis SHA256: `2cc5ade658478e8f855c46739e1d6ea3d95694eddb7f47c6a0325f48aee48e66`.

## Bildumsetzung und Systemgrenze

Aus Code gelesen und im Spiellauf verwendet: Die Engine zeichnet intern
320 mal 200 Pixel. `DOOMGENERIC_RESX=128` allein funktioniert nicht, weil
die vorhandene Bildausgabe nur ganzzahlig vergrößert. Der eigene
`DG_DrawFrame` Adapter wählt Pixel für 128 mal 64 aus und wandelt deren
Helligkeit mit einem geordneten 4 mal 4 Raster in ein Bit pro Pixel um.
Das Ergebnis hat 1024 Byte und dieselbe Seitenanordnung wie der spätere
Displayadapter. Eine physische Displayübertragung wurde nicht ausgeführt.

Alle sechs `DG_*` Plattformfunktionen sind eigene Adapter. Die C Laufzeit
ruft für Dateizugriff einen eigenen Testsystemaufruf auf. Python stellt das
nur lesbare WAD und Ausschnittzugriffe bereit. Das WAD belegt keinen eigenen
vollständigen ARM RAM Bereich. Konfigurations- und Speicherdateien sind im
Test nicht beschreibbar. Zeit läuft synthetisch; Tastendrücke sind injiziert.
Die Erstprüfung endete zu früh im schwarzen Übergang und wurde deshalb
korrekt als fehlgeschlagen geführt. Erst der längere Lauf belegt das Spiel.

Ungeprüft: FatFs und SD Durchsatz im Doom-Zweig, konkrete Geräteadressen,
CPU Zyklen pro Bild, Hardwarebildrate, Ton, echte Paneltasten,
Startkombination, Rettungswege und weitere Karten. Hostlaufzeiten von
Unicorn werden nicht in Gerätebilder pro Sekunde umgerechnet.

## Reproduktion und vollständige Belege

Eigener Code und Befehle: [Buildanleitung](../../tools/doom/README.md), `build_probe.py`,
`run_probe.py`, `probe.c`, `probe.ld`.
Alle fremden Quellen, Toolchain, Spieldaten und erzeugten Dateien liegen in:
`$doom_feasibility/engine/`.

Finale Builds und Läufe:

- `build-final/`: 16 MiB Zone; `build-final.log`.
- `build-6m/`: 6 MiB Zone; `build-6m.log`.
- `run-final/result.json`, `run-final/console.log`, `run-final.log`.
- `run-input/result.json`, `run-input/console.log`, `run-input.log`.
- `run-6m/result.json`, `run-6m/console.log`, `run-6m.log`.
- `verification-final/result.json`, `verification-final/console.log`,
  `verification-final.log`: abschließender 6 MiB Lauf mit Eingabe.
- PBM Bilder jeweils `frame-001.pbm` und `frame-120.pbm`.
- `build.log` dokumentiert den ersten Linkfehler wegen fehlendem
  `mkdir` und `_link`; der Adapter implementiert danach bewusst nur lesbare
  Daten und verweigert diese Schreibfunktionen. Kein Laufzeitersatz im Produkt.

| Beleg | SHA256 |
| --- | --- |
| Arm Toolchain Archiv | `c7c78ffab9bebfce91d99d3c24da6bf4b81c01e16cf551eb2ff9f25b9e0a3818` |
| Freedoom Archiv | `3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59` |
| Freedoom1 IWAD | `7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d` |
| ELF, 16 MiB Zone | `10d5a68eb9d6158cfd9558c9e3335e133b4d3bc8291b1728520b4bc5c43f54fb` |
| ELF, 6 MiB Zone | `1759d9b8ff25e178450c40cff08237924bf0d676bd660aed521ce3f7eb7ec19b` |
| Standardlauf Ergebnis | `f0f455e14903baf864326338eea9976176fe7ff8ee8280a733964715f6d0bd4e` |
| Eingabelauf Ergebnis | `e88f72d092e83abff742b5ecc6170a0d8c47dc505e5a49e241855e5deea4b694` |
| 6 MiB Lauf Ergebnis | `306159786e0360fc9ff533dc3b89bded8095dc1ced7fc4bc0c3148ae7fc47b57` |

Abschließender 6 MiB Eingabebeleg SHA256: `ada9bf3197aba4281b4061d3ceec806aae3119dec0c97f1dc97e1edcf269710b`.
