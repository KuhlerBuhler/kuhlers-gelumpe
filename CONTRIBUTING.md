# Contributing

Thanks for wanting to help. Pull requests go to `develop`; `main` only takes merges from `develop`.

## Start

```bash
npm ci
npm run setup:emu
npm start
```

`npm test` runs the unit tests, `npm run test:e2e` the browser tests. Details: [docs/development.md](docs/development.md).

## Hard rules

- **No Korg data, ever.** No firmware (`SYSTEM.VSB`) or slice of one, no factory pattern, no sample, not even as a
  test fixture. Tests build their own data (`test/helpers.mjs`). A check (`tools/korg-guard.mjs`) closes a pull request
  that carries such data. Names and labels from the device are fine.
- **Every address is measured.** A new field, hook or address needs evidence: a file in `docs/messungen/`, a factory
  check or a derivation, see `CLAUDE.md` and `test/map.test.mjs`.
- **Firmware patches pass the emulator.** `tools/emu/check.py` with your own `SYSTEM.VSB` and flash dump must be green
  for every build the patch names. Say in the pull request what you tested on a real device and what not.
- **The bootloader is never touched.** No patch, tool or plugin writes to it.
- Own CSS classes carry the prefix `cee-`, colours and sizes come from the design tokens.

## Pull requests

Small and focused. Commit messages and pull request text in English. Fill in the checklist of the template.
