# Doom als Patch des BLECH-Satzes

Stand 15.10.2026. Im Emulator und offline, kein Gerät. Marker: **gemessen** (ausgeführt, Befehl
genannt), **offline** (Bytes oder Code gelesen), **hergeleitet**, **offen**. Die Firmware-Dateien
liegen nicht im Repository, nur Hashes und Ergebnisse.

## Kurzfassung

1. Der SD-Lader aus [Doom auf BLECH v21](2026-10-15-doom-v21.md) ist jetzt der Patch `doom-loader` im
   Satz `data/patches/blech.json`. Der Patcher erzeugt damit BLECH mit Doom, auf Hacktribe und auf Korgs
   Original. Dieselben Bytes wie vorher: der Lader (2732 Byte) entsteht aus `tools/doom/bootstrap.*` und ist
   auf die `doom.bin` in `third_party/doom/` gepinnt.
2. Auf Hacktribe ist das Ergebnis bytegleich zu `SYSTEM-blech-v21-doom.VSB` aus dem lokalen Paket.
3. Auf Korgs Original passt derselbe Patch ohne Änderung. Der Haken und alle Firmware-Aufrufe des Laders
   haben dort dieselben Bytes.
4. `check.py` besteht auf beiden mit dem eigenen Flash.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Der Lader hat 2732 Byte und liegt bei `0xC017CC00`, Zustand bis `0xC017F000`, gemeinsame Daten bis `0xC0180000` | gemessen | `python3 tools/patch/doom_loader.py --vsb SYSTEM.VSB --toolchain ARM_GNU_14_2 --out data/patches/doom-loader.json`, Ausgabe "loader 2732 bytes for doom.bin 17025aae..." |
| Der Patch hakt an `0xC002ADB0` ein, dem `bl 0xC002A35C` der Startfunktion; der Haken ruft das Original zuerst | offline | `build_patch` prüft die vier Bytes gegen `branch(site, 0xC002A35C)`; `tools/doom/bootstrap.S` |
| Die Stelle `0xC002ADB0` und alle Firmware-Funktionen, die der Lader aufruft, sind in Hacktribe und Korgs Original in den ersten 64 Byte gleich | offline | Bytevergleich beider Dateien nach dem Patchen mit dem Satz ohne Lader: `0xC00005A0`, `0xC0025754`, `0xC0025A14`, `0xC002A35C`, `0xC003FD20`, `0xC009DAD8`, `0xC009DB60`, `0xC009DD74`, `0xC009E3DC`, `0xC002ADB0` |
| Die Doom-Reserve ist in beiden Builds FF | gemessen | `build_patch` bricht sonst ab; `test/patch-ram.test.mjs` mit `E2_VSB` |
| Hacktribe: `node tools/patch/apply.mjs --vsb SYSTEM.VSB --set data/patches/blech.json` ergibt SHA-256 `004d23cf2d67cfad5f90849534b82ce21f5fcefbc1d9e5219caba4858af9b262` | gemessen | `cmp` gegen `SYSTEM-blech-v21-doom.VSB` des Pakets: gleich |
| Korgs Original: gleicher Befehl ergibt `26b1c731717d10ea0c6903f9a8a314481bc6ba14b1eaf52509a11d712d11bb9f` | gemessen | gegen dieselbe Basis ohne Lader (`953082de...`) unterscheiden sich nur das Wort bei `0xC002ADB0` und die 2644 Byte des Laders |
| Hacktribe mit Lader besteht `tools/emu/check.py` mit dem eigenen Flash: 291 von 291 | gemessen | `check.py --base SYSTEM.VSB --patched ... --flash flash_full_2026-10-09.bin` mit den Spannen aus `apply.mjs` (darin `0x2aeb0:4` und `0x17cd00:2732` als Startphase) |
| Korgs Original mit Lader besteht `check.py` mit dem eigenen Flash: 316 von 316 | gemessen | ebenso |
| Die vom Patcher erzeugte Hacktribe-Datei spielt Doom im Emulator: Drehen, Bewegen, Schießen, Benutzen, E2M1, Quit, Ausschalten, kein SD-Schreiben, Randwächter heil | gemessen | `E2_DOOM_REQUIRED=1 node --test test/doom-native.test.mjs` mit `E2_DOOM_IMAGE=SYSTEM-blech-v23.VSB` (Patcher-Ausgabe), `doom.bin` aus dem Neubau (gleiche SHA-256 wie `third_party/doom/doom.bin`) und `doom.wad` aus `third_party/doom/`: 3 von 3 bestanden, darin der Bedientest mit 17 Prüfungen |
| Start- und Fehlerregression (Normalstart, EXIT, Kombinationen, fehlende oder beschädigte Dateien, Ausschalten) und TAP-/SysEx-Verträglichkeit mit der Patcher-Ausgabe | gemessen | `test/doom-native.test.mjs` (34 von 34) und `test/doom-compatibility.test.mjs` mit `E2_DOOM_REQUIRED=1`, Basis `SYSTEM-blech-v21.VSB`; dazu `test/doom-loader.test.mjs`, `test/doom-layout.test.mjs`, `test/doom-sources.test.mjs` |
| `doom.bin` entsteht aus dem mitgelieferten Quellarchiv bytegleich neu | gemessen | `python3 gelumpe/tools/doom/rebuild_runtime.py` aus dem frisch entpackten Archiv, `matches: true`, `network_used: false` |
| Die Doom-Reserve gehört jetzt dem Patch selbst (`ram`), nichts liegt mehr "außerhalb des Satzes" | gemessen | `RESERVED` in `data/patch-ram.mjs` ist leer; `test/patch-ram.test.mjs` hält jeden der drei Bereiche gegen Eindringlinge |
| Auf Korgs Original läuft Doom selbst | offen | nur die Startregression der Firmware ist geprüft, die Engine im Emulator auf Hacktribe |
| Am Gerät | offen | nicht versucht |

## Entscheidungen

- **Ein Patch für beide Builds** (`builds: ["hacktribe", "stock"]`), keine Stock-Variante, weil Haken und
  Aufrufziele dort gleich sind.
- **Der Hakenort** steht im Register als eigene Stufe `doom-select` der Kette `start`, nach
  `after-rescue-paths` und vor `card-mount`.
- **`ram` enthält nicht die Lader-Bytes selbst**, die schon als geschriebene Änderung zählen, sondern den
  Rest des 4-KiB-Codebereichs dahinter, den Zustand und die gemeinsamen Daten. So bleibt die ganze Reserve belegt.
- **`currentPatches` in `tools/doom/layout.mjs` lässt `doom-loader` weg**, damit `build_bootstrap.py` und die
  Prüfläufe ihre Basis weiter als "Satz ohne Lader" rekonstruieren.

## Prüfung

Befehle (eigene Dateien; Hacktribe `SYSTEM.VSB`, Korgs Original `electribe_sampler_system_v202/SYSTEM.VSB`):

```bash
node tools/patch/apply.mjs --vsb HACKTRIBE.VSB --set data/patches/blech.json --out SYSTEM-blech-v23.VSB
node tools/patch/apply.mjs --vsb KORG.VSB --set data/patches/blech.json --out SYSTEM-blech-v23-korg.VSB
tools/emu/.venv/bin/python tools/emu/check.py --base BASIS --patched DATEI [Spannen aus apply.mjs] --flash flash_full_2026-10-09.bin
```
