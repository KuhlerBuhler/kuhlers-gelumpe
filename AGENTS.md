# Agent instructions

Shared instructions for every agent working in this repository (Claude, Codex, others).
Kuhler's GELUMPE is the app for BLECHTRIBE, a firmware patch for the Korg Electribe 2 (red
Sampler and blue Synth, firmware 2.02, Korg's original or Hacktribe). It patches the user's own
`SYSTEM.VSB` (Firmware Patcher), runs it in an emulator, brings a device back (Rettung), edits effects
(Baukasten), writes plugins for the device and puts changes on the device only after a linter and the
emulator have checked them. What it does and why is in [README.md](README.md) and
[docs/README.md](docs/README.md). Read the page that matches your task before you start; do not
duplicate its content here.

Where the code lives:

| Part | Where |
|---|---|
| The page (the app's UI) | `site/index.html`, `site/app/*.mjs`, `site/app.css`, `site/app/*.css` |
| UI texts, eleven languages | `site/app/i18n-<lang>.mjs`, loaded by `site/app/i18n.mjs` |
| Firmware Patcher and rescue page | `site/app/patcher.mjs`, `site/app/rescue.mjs`, `src/patch.mjs`, `tools/patch/apply.mjs` |
| Browser logic (formats, linter, patcher, plugin compiler) | `src/`, `src/script/` |
| Plugin API contract (`API_VERSION`, calls, events) | `data/script/contract.mjs`, catalog in `data/script/presets.mjs` |
| Device knowledge | `data/map/` (fields), `data/findings.mjs` (behaviour), `data/patches/*.json` (built patches) |
| Firmware patches (ARM assembler and Python builders) | `tools/patch/` (`script_*.s` is the runtime: menu, VM, plugin API) |
| Emulator and its cases | `tools/emu/`, cases in `tools/emu/*_cases.py` |
| CI helpers | `tools/ci/`, `.github/workflows/` |
| Desktop app (Tauri) | `src-tauri/` |
| Release notes | `release-notes/X.Y.Z.md`, built into `data/release-notes.mjs` |

## Setup

Node 20 or newer, Python 3.10 or newer for the emulator. Details, environment variables and the
emulator setup are in [docs/development.md](docs/development.md) and [docs/emulator.md](docs/emulator.md).

```bash
npm ci               # Playwright and CodeMirror sources for the browser tests
npm run setup:emu    # tools/emu/.venv with Unicorn
```

A fresh git worktree has neither `node_modules` nor `tools/emu/.venv`. Run both commands there, or
symlink the venv of the main checkout (`ln -s <main>/tools/emu/.venv tools/emu/.venv`): the patch tools
and `tools/verify-patches.mjs` start `tools/emu/.venv/bin/python` and fail without it. Both are
gitignored; never commit them or a symlink to them.

In VS Code, F5 runs `npm start` and opens the editor at `http://127.0.0.1:8737` (`.vscode/launch.json`, `.vscode/tasks.json`).

## Build and test

```bash
npm test             # everything that runs without hardware and without Korg data
npm run test:e2e     # the page in Chrome against the simulated device
npm run test:all     # unit and browser tests side by side
npm run test:emu     # emulator tests, need E2_VSB (E2_STOCK_VSB, E2_BLUE_VSB for the other builds)
E2_VSB=/path/SYSTEM.VSB E2_PATTERNS=/path/backup.e2sallpat npm run test:local   # own files
node --test test/docs.test.mjs   # after a change to README*, AGENTS.md or docs/
```

Run `npm test` and `npm run test:e2e` before you call something done. Never mark a fix as
done without a failing test that now passes or a check in the browser or emulator. On a loaded
machine use `GELUMPE_JOBS=2 node --test --test-concurrency=1 "test/*.test.mjs"`.

Firmware patches are checked in the emulator with your own original `SYSTEM.VSB` (never in the repo):

```bash
node tools/patch/apply.mjs --vsb SYSTEM.VSB --set data/patches/blech.json --out BLECH.VSB   # prints the check.py command
tools/emu/.venv/bin/python tools/emu/check.py --base SYSTEM.VSB --patched BLECH.VSB --quick   # start scenarios only, minutes
tools/emu/.venv/bin/python tools/emu/check.py --base SYSTEM.VSB --patched BLECH.VSB --cases menu_cases   # start scenarios plus these case modules
```

The full `check.py` (all case modules) takes hours on a loaded machine. Locally run `--quick` and the
case modules your change touches; CI runs the rest (see below). The blue Electribe uses
`data/patches/blech-synth.json` and its own original. Stop a hanging run by its PID, never with
`pkill -f check.py`: other sessions may run their own.

## Hard rules

- **No Korg data in the repository, ever.** No firmware image, no slice of one, no factory
  pattern, no sample, not even as a test fixture. `*.VSB`, pattern backups and sample files are
  gitignored. Tests build their own data (`test/helpers.mjs`). The Korg data guard closes a pull
  request that carries any.
- `.e2/factory-profile.json` is derived from the user's firmware and gitignored for the same reason.
- `thoughts/` is local working state and gitignored: never add files from it.
- **Never send anything to a real device without the owner's consent.** The emulator is the
  place to try things first. The bootloader is never touched.
- Everything in `src/` except `node.mjs` must run in a browser. No `node:` imports outside
  `src/node.mjs`, `bin/`, `tools/` and `test/`.
- **The device map in `data/map/` describes every field once.** Evidence takes one of four
  forms, enforced by `test/map.test.mjs`: `measure:<date>/<name>` with a file in
  `docs/messungen/`, `factory-check:<name>` with a check in `test/factory-checks.mjs`,
  `korg-spec:<section>`, or `derived:<source>`. A pointer at a document is not evidence.
  Behaviour knowledge goes into `data/findings.mjs`. `src/layout.mjs` is only a view, add no
  numbers to it. `data/map/fx-params.mjs` is generated by `node tools/units-to-map.mjs`, never
  edit it by hand. See [docs/geraetekarte.md](docs/geraetekarte.md).
- **Records are edited, never built**, and the 7-bit packing needs care with lengths that leave
  a remainder of six. Both traps are explained in [docs/geraetekarte.md](docs/geraetekarte.md).
- Own CSS classes carry the prefix `cee-`. Standard `ui-*` classes are not redefined. Use
  tokens instead of raw colours or pixel values. Read [DESIGN.md](DESIGN.md) before UI work: it lists
  the tokens, the spacing levels and the components of the page.
- `site/design/` is a copy of the Interface design system. Do not edit it here, change it in the
  Interface. The one exception is `site/design/bg.js`, the page background.
- Infos, warnings and errors go to the toast (`site/app/toast.mjs`), never as a line in the page. A
  progress line of a running step may stay in the page.
- **Every UI text goes through `t()`.** A new key goes into `site/app/i18n-de.mjs` and into all ten
  other tables with the same `{placeholders}` and markup; German text in `site/index.html` sits next to
  its `data-i18n` key. `test/i18n.test.mjs` fails on hard-coded text and on a key missing in any language.
- Device menu paths are written as `Menü -> BLECH -> CUSTOMIZATION`, app paths by the sidebar group:
  `BLECHTRIBE -> Baukasten`.
- The firmware writes its settings to the SD card (`KORG/blechtribe/`), not to the flash. Do not add
  flash writes. The app sends no usage data anywhere. **The editor never gets a design system page**,
  no overview of all components. `test/design.test.mjs` holds that.
- A new linter rule has a severity and a message that says what was observed. Not seen on
  hardware yet means `warn`, not `error` ([docs/linter.md](docs/linter.md)).
- Every address was measured on hardware with firmware 2.02 and Hacktribe. Hold a claim against
  the factory presets of the same unit before it becomes a rule or a map entry.

## Docs

Where things live: [docs/README.md](docs/README.md) is the index. The knowledge itself stays in
`docs/`, do not copy it into this file.

The docs are written in the author's own voice, in German. README, `docs/plugins.en.md`,
`docs/patcher.en.md` and `docs/original-zurueck.en.md` have English twins; change both.
They name no person other than in the sentence that explains the project name, and they carry no
agent working vocabulary. No em or en dashes anywhere, no absolute personal paths, relative links only.
`test/docs.test.mjs` fails on dead links, absolute user paths, those names and dashes, and on a
`korg.*` call that `docs/plugins.md` names but `docs/plugins.en.md` does not.
Mark facts as measured, derived or open, and keep measurement files at their paths, because
`data/` and `test/` point at them. A new file in `docs/messungen/` gets a line in its README.
Docs state what holds now; before and after belong in commits and release notes.

## Firmware patches

- **Core features are built into the firmware**, with a switch under `Menü -> BLECH -> FEATURES`
  (Key Pads, Filter Toggle, LAST PATTERN, STEREO 1 PAD). A catalog plugin is for extras, not
  for playing features. Screens use the firmware's own look: its value window for a value, the file
  browser for a list, never a hand-drawn screen.
- A new patch is `tools/patch/<name>.py` (builder), `data/patches/<name>.json` (and `-synth.json` for
  the blue), an entry in the set `data/patches/blech.json` or `blech-synth.json`, cases in
  `tools/emu/<name>_cases.py`, a row in the table of [docs/patcher.md](docs/patcher.md) and a
  measurement in `docs/messungen/`. Add the case module to `tools/ci/verify-scope.mjs`;
  `test/verify-scope.test.mjs` fails otherwise.
- After a change to `tools/patch/script_*.s` or `data/script/contract.mjs`, rebuild the runtime patch
  for all three builds: `node tools/patch/script_runtime.mjs --build hacktribe`, `--build stock`,
  `--build synth`. Other patches have their builder next to them in `tools/patch/`.
- Runtime code lives in MORE3 (`tools/patch/script_hooks.py`). New RAM goes into an area declared in
  `ram_areas()` or the patch's `ram` list; `test/patch-ram.test.mjs` fails when two patches claim the
  same RAM. A word inside a block that is already in use collides silently, check the block first.
- An address on the blue Electribe goes through `tools/patch/synthaddr.py`; an emulator case that pokes
  firmware RAM has to translate its address the same way.
- `data/patches/verified.json` holds the checksums of patched copies that passed the full check. Do not
  edit it by hand: the workflow Verify patches writes it on the release pull request. Locally
  `node tools/verify-patches.mjs <stock> <synth> <hacktribe>` does the same with the original files.

## Plugin API

- `data/script/contract.mjs` is the one source. Ids are never reused or renumbered; a new call, event
  or error goes at the end of its list and raises `API_VERSION` (its `since`). `test/script-contract.test.mjs`
  pins the numbers.
- A plugin write acts like the hardware: the same MIDI CC the knob or key sends, the same window the
  firmware shows (a plugin may switch the window off). Prove a new write against the hardware path in
  the emulator, with a case in `tools/emu/plugin_api<N>_cases.py`.
- That includes the way to the sound engine. A part write (`script_seq_set_part_value_glue` in
  `tools/patch/script_seq.s`) does the part edit, then the parameter set (`HW_PARAM_SET` in
  `tools/patch/script_hooks.py`) for knob values and CUTOFF, the dispatcher refresh (flag 1, `PART_REFRESH`)
  for `sample`, `modType`, `ifxType` and `filterType`, and the part panel message for the filter LEDs, as the
  control does. A twin probe compares these calls, not only pattern RAM, screen, LEDs and MIDI
  ([docs/messungen/2026-11-09-plugin-part-dsp.md](docs/messungen/2026-11-09-plugin-part-dsp.md)).
- Document every new call in [docs/plugins.md](docs/plugins.md) and
  [docs/plugins.en.md](docs/plugins.en.md); their examples are compiled by `test/script-app.test.mjs`.

## Branches, pull requests and releases

- Feature pull requests go to `develop`. `main` only takes the release pull request `release/X.Y.Z`
  (or `develop`) -> `main`, which the workflow Release merge merges after an approval and green checks.
  A fix that a running release needs goes to `develop` first and then as its own pull request to
  `release/X.Y.Z`.
- English commit messages and PR descriptions, using the template in `.github/pull_request_template.md`.
  State what changed and why, and what was tested on a real device and what not. Do not add AI
  attribution lines.
- A pull request that may go in once CI is green gets the label `automerge` (`gh pr create ... --label automerge`):
  the workflow Automerge merges it when `unit`, `browser`, `guard` and `patches` pass. Do not poll CI or merge by hand.
  Leave the label off when the change waits for a device or listening test.
- On a pull request to `develop`, Verify patches runs `check.py --quick` plus the case modules that
  `tools/ci/verify-scope.mjs` maps to the changed files, on all four originals. The full check runs on
  the release pull request.
- A branch does not have to be current with develop to be merged; merge develop in only when you need its changes.
  Never rebase or force-push a shared branch. Leave a conflict that is only in `data/patches/script-runtime*.json`
  alone: the workflow Update pull requests rebuilds those.
- Firmware changes that touch the same patches (`data/patches/`, `tools/patch/`, `tools/emu/*_cases.py`) go one
  after the other or in one pull request, not in parallel. App changes may run in parallel.
- A release: `node tools/set-version.mjs X.Y.Z`, notes in `release-notes/X.Y.Z.md` (German, then
  `## English`), `node tools/release-notes.mjs build`. Details in
  [docs/development.md](docs/development.md), "Release".
