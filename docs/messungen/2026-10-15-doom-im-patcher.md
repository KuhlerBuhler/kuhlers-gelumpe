# Doom als Patch des BLECH-Satzes

Im Emulator und offline, kein Gerät. Marker: **gemessen** (ausgeführt), **offline** (Bytes oder Code gelesen),
**hergeleitet**, **offen**. Die Firmware-Dateien liegen nicht im Repository.

## Kurzfassung

Der SD-Lader aus [Nativer Doom-SD-Lader](2026-10-15-doom-sd-lader.md) ist der [Patch](../glossary.md#patch) `doom-loader` im
Satz `data/patches/blech.json`. Der [Patcher](../patcher.md) erzeugt damit BLECH mit Doom, auf Hacktribe und auf Korgs
Original. Der Lader entsteht aus `tools/doom/bootstrap.*` und ist auf die `doom.bin` in `third_party/doom/` gepinnt.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Der Lader liegt bei `0xC017CC00`, sein Zustand reicht bis `0xC017F000`, die gemeinsamen Daten bis `0xC0180000` | offline | `tools/doom/layout.json`, `tools/patch/doom_loader.py` |
| Der Haken sitzt auf `0xC002AE64`, als Stufe `doom-select` der Kette `start` (nach `after-rescue-paths`, hinter `card-mount`) | offline | `data/hooks.mjs` |
| Die Doom-Reserve ist in beiden Builds `FF`, sonst bricht der Bau ab | gemessen | `build_patch` in `tools/patch/doom_loader.py`; `test/patch-ram.test.mjs` mit `E2_VSB` |
| Die Reserve gehört dem Patch selbst (`ram`), `RESERVED` in `data/patch-ram.mjs` ist leer | offline | `data/patch-ram.mjs`, `test/patch-ram.test.mjs` |
| Der Lader besteht Start- und Fehlerregression, TAP- und SysEx-Verträglichkeit im Emulator | gemessen | `test/doom-native.test.mjs`, `test/doom-compatibility.test.mjs`, `test/doom-loader.test.mjs`, `test/doom-layout.test.mjs`, `test/doom-sources.test.mjs` (mit `E2_DOOM_REQUIRED=1`) |
| `doom.bin` entsteht aus dem mitgelieferten Quellarchiv bytegleich neu | gemessen | `tools/doom/rebuild_runtime.py` |
| Auf Korgs Original läuft Doom selbst | offen | nur die Startregression ist geprüft |
| Am Gerät | offen | nicht versucht |

## Entscheidungen

- **Ein Patch für beide Builds** (`builds: ["hacktribe", "stock"]`), weil Haken und Aufrufziele dort gleich sind.
- **`ram` enthält nicht die Lader-Bytes selbst**, die schon als geschriebene Änderung zählen, sondern den Rest des
  4-KiB-Codebereichs dahinter, den Zustand und die gemeinsamen Daten. So bleibt die ganze Reserve belegt.
- **`currentPatches` in `tools/doom/layout.mjs` lässt `doom-loader` weg**, damit `build_bootstrap.py` und die Prüfläufe
  ihre Basis als "Satz ohne Lader" rekonstruieren.
