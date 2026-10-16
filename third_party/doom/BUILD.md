# doom.bin neu bauen

`doom.bin` entsteht bytegleich aus `doom-sources.tar.gz`. Ohne Netz, ohne Git. Gemessen am
15.10.2026: Neubau aus dem entpackten Archiv in einem neuen Verzeichnis ergibt
`17025aae03ef2eb05a9990774c0882f3298b6c0efc54a7173e7dbc6b30373078`, 450492 Byte.

## Was dazugehört

| Teil | Festlegung |
|---|---|
| Engine | doomgeneric, Revision `e257a09527062bfb986b6e5e0780839b6cbd5b71`, unverändert (im Archiv unter `doomgeneric/`) |
| Adapter, Linkerskript, Skripte | `tools/doom/` dieses Repositories, Kopie im Archiv unter `gelumpe/tools/doom/` |
| Compiler | Arm GNU Toolchain 14.2.Rel1, `arm-none-eabi-gcc` 14.2.1 20241119 (Build arm-14.52), mit newlib 4.4.0 |
| Optionen | `-mcpu=arm926ej-s -marm -mfloat-abi=soft -Os -ffunction-sections -fdata-sections`, Gegner an, Ton aus, 320 mal 200 Pixel, alle weiteren Flags in `build.json` im Archiv |
| Werkzeugkette laden | [Arm GNU 14.2.Rel1, Darwin ARM64](https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi.tar.xz), andere Hosts das Paket gleicher Version für ihren Host |

Die Werkzeugkette wird nicht von hier aus geladen oder installiert.

## Aus dem Archiv

```sh
mkdir rebuild-src && tar -xzf third_party/doom/doom-sources.tar.gz -C rebuild-src
python3 rebuild-src/gelumpe/tools/doom/rebuild_runtime.py \
  --toolchain "$doom_toolchain" --output "$doom_rebuild"
```

`$doom_rebuild` liegt außerhalb eines Git-Verzeichnisses. Das Skript prüft die archivierten Quellen,
den Compiler und das Toolchainmanifest gegen `build.json`, baut nur aus dem Archiv und bricht ab,
wenn der Hash vom archivierten abweicht. Das Ergebnis steht in `rebuild.json`.

## Aus dem Repository

```sh
git clone https://github.com/ozkl/doomgeneric "$doom_source"
git -C "$doom_source" checkout e257a09527062bfb986b6e5e0780839b6cbd5b71
python3 tools/doom/build_runtime.py \
  --source "$doom_source" --toolchain "$doom_toolchain" --output "$doom_output/runtime"
```

Der Builder lehnt andere Revisionen und lokal veränderte Quellen ab. Das Ergebnis muss wieder
`doom.bin` mit dem Hash oben sein, sonst ist eine der Angaben hier veraltet.

## Der Lader

`data/patches/doom-loader.json` trägt den SD-Lader, der genau diese `doom.bin` über Länge und
SHA-256 festlegt. Neu erzeugt wird er mit

```sh
python3 tools/patch/doom_loader.py --vsb SYSTEM.VSB --toolchain "$doom_toolchain" \
  --out data/patches/doom-loader.json
```

Wer `doom.bin` ändert, ändert damit den Hash im Lader und muss den Patch neu bauen.
