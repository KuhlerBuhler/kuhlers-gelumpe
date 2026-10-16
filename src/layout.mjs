/**
 * Where things live, and what is known about the units.
 *
 * A view on the device map (data/map/) and the findings (data/findings.mjs),
 * shaped the way the linter, the image reader and the simulation have always
 * read it. New knowledge goes into the map or the findings, not here.
 *
 * Measured on a Korg Electribe 2 Sampler, firmware 2.02, with Hacktribe
 * installed. A different build moves all of it.
 */
import { field, TABLES as MAP_TABLES, BLOCKS, typeOf } from "./map/index.mjs";
import FINDINGS from "../data/findings.mjs";

const finding = id => {
  const f = FINDINGS.find(x => x.id === id);
  if (!f) throw new Error(`no finding ${id}`);
  return f;
};
const findings = kind => FINDINGS.filter(x => x.kind === kind);
const FX_META = BLOCKS.get("fxRecord").meta;

/** A RAM address as the device sees it, to an offset in a SYSTEM.VSB. */
export const ramToFile = a => a - 0xc0000000 + 0x100;
export const fileToRam = f => f - 0x100 + 0xc0000000;

export const RAM_BASE = 0xc0000000;

/** One effect preset record, master and insert alike. */
export const RECORD_SIZE = MAP_TABLES.get("table.mfx").stride;

const table = id => {
  const t = MAP_TABLES.get(id);
  return { file: t.file, ram: fileToRam(t.file), stride: t.stride, count: t.count };
};

export const TABLE = {
  mfx: { ram: table("table.mfx").ram, slots: table("table.mfx").count },
  ifx: { ram: table("table.ifx").ram, slots: table("table.ifx").count },
};

/** Other tables in the same image, kept here so they are not re-hunted. */
export const TABLES = {
  // 128 per our notes, but hacktribe-editor only allows indices 0 to 95.
  // Until that is settled on hardware, 96 is the safe number.
  grooveTemplates: table("table.groove"),
  modulationTypes: table("table.modType"),
  crc16: { file: field("crc16").where.offset, ram: fileToRam(field("crc16").where.offset), stride: 2, count: typeOf(field("crc16")).width / 2 },
  splashBitmap: { file: field("splash").where.offset, bytes: typeOf(field("splash")).width, note: "1 bit per pixel, 128 by 64" },
  initPattern: { file: MAP_TABLES.get("table.initPattern").file, bytes: MAP_TABLES.get("table.initPattern").length },
};

/** Flash offsets for the flash command. Not image offsets. */
export const FLASH = {
  firmware: 0x000000,
  codeEnd: 0x1d0000,
  userDataStart: 0x220000,
  userGlobals: 0x230000,
  userPatterns: { at: 0x240000, blocks: 250, blockSize: 0x4000 },
  factoryGlobals: 0x630000,
  factoryBankSqez: 0x640000,
  pcm: 0x6b0000,
};

/** How many entries the menu on the device offers. */
export const MFX_COUNT_RAM = fileToRam(field("menu.mfxCount").where.offset);

/**
 * The insert menu length is stored in thirteen places at once, six holding
 * the last index and seven the count. Miss one and the menu and the lookup
 * disagree, which shows up as a preset that selects but plays the wrong unit.
 */
const ifxSites = field("menu.ifxCount").sites;
export const IFX_LAST_INDEX_FILE = ifxSites.filter(s => s.value === "count - 1").map(s => s.file);
export const IFX_COUNT_FILE = ifxSites.filter(s => s.value === "count").map(s => s.file);

const stageDevice = field("fx.stage.device");
const stageAt = i => stageDevice.where.offset + i * stageDevice.repeat[0].stride;
const PARAMS_FROM_DEVICE = FX_META.paramsFromDevice;
const mapRow = field("fx.map.source");

/** Offsets inside a record. */
export const REC = {
  name: field("fx.name").where.offset,
  nameWidth: typeOf(field("fx.name")).width,
  map: mapRow.where.offset,
  mapEntries: mapRow.repeat[0].count,
  mapEntrySize: mapRow.repeat[0].stride,
  stage: Object.fromEntries(stageDevice.repeat[0].names.map((name, i) =>
    [name, { device: stageAt(i), params: stageAt(i) + PARAMS_FROM_DEVICE }])),
};

/** A stage block runs from its device byte to the next one. */
export const STAGE_BLOCK_SIZE = REC.stage.ifx2.device - REC.stage.ifx1.device;

/**
 * A control map entry is 28 bytes. Five are understood. The rest is copied
 * from whatever record the preset was built on and must not be zeroed: a
 * record assembled from scratch selects on the device but stays silent.
 */
export const MAP = Object.fromEntries(["source", "chain", "param", "low", "high"]
  .map(k => [k, field(`fx.map.${k}`).where.offset - mapRow.where.offset]));

export const SOURCES = Object.fromEntries(FX_META.sources.map(x => [x.raw, { name: x.name, ifx: x.ifx, mfx: x.mfx }]));

export const CHAINS = Object.fromEntries(FX_META.chains.map(x => [x.raw, { name: x.name, stage: x.stage }]));

/**
 * What hardware tests showed about the second insert stage.
 *
 * Most of it comes from an automated sweep with the filter 0x0a fixed in
 * stage one, run twice with the same result. The failure modes differ and
 * that matters when hunting a fault: a crash is obvious, a silent preset
 * looks like a mistake by the person playing it.
 *
 * Nine of nineteen units are measured. Anything missing here is untested,
 * which is not the same as forbidden and not the same as safe.
 */
export const STAGE2 = Object.fromEntries(findings("stage2").map(f => [f.unit, { verdict: f.verdict, note: f.note }]));

/** Chains Korg itself builds, so they are safe beyond any doubt. */
export const FACTORY_CHAINS = finding("factoryChains").chains;

/** The mute unit an insert record carries in its unused master field. */
export const MFX_MUTE = finding("mfxMute").unit;

/**
 * Enumerations. Their meanings are written down nowhere, so the values a
 * preset may use are learned from the factory presets rather than listed
 * here. Nothing is hard-coded, because the one value that was hard-coded
 * turned out to be wrong.
 *
 * The story is worth keeping. A preset of ours went silent device-wide until
 * a restart and the blame landed on `level_mod_source = 4`, a value we
 * thought Korg never used. Korg's own "Pumper" on IFX 36 carries 4 and works.
 * The conclusion was drawn from four presets and one bad evening, and it was
 * wrong. See LFO_RESET_HELD for the suspect that replaced it.
 */
export const ENUM_PARAMS = {
  level_mod_source: {},
  mod_src: {},
  mask_type: {},
  lfo_wave: {},
};

/**
 * Refuted on hardware, 2026-09-21, kept so it is not proposed again.
 *
 * The theory was that holding `lfo_reset` at 1, with a reset phase of 0 and
 * nothing driving it from the play button, pinned the level modulator at a
 * phase with no level. Four presets were put in RAM covering both variables
 * independently: held or fired from play, phase 0 or Korg's value.
 *
 * All four pump. Neither the holding nor the phase silences anything, so
 * whatever took that preset's sound away is still unaccounted for. What is
 * left between it and the factory preset is `output_gain` at 95 and
 * `saturation` at 0, and neither of those looks like a cause either.
 *
 * Second thing that came out of the same test, and worth chasing: three of
 * the four lose their beat when a parameter changes and only recover on stop
 * and play, which is the re-synchronisation problem the notes already
 * describe. The one that held the reset may not. Not measured carefully.
 */
export const REFUTED = {
  lfoResetHeldSilences: finding("refuted.lfoResetHeldSilences").note,
  levelModSourceFour: finding("refuted.levelModSourceFour").note,
  lfoResetHeldSyncs: finding("refuted.lfoResetHeldSyncs").note,
};

/**
 * What the play row actually does, heard 2026-09-21.
 *
 * Two presets, alike but for the play row. The one with it starts at the same
 * point every time. The one without it, holding lfo_reset at 1, comes in
 * somewhere different after every stop and play.
 *
 * So `lfo_reset` is not a state that pins the modulator. It is what the play
 * row fires, and the value in the parameter is what gets fired. Without the
 * row the modulator free-runs, and nothing makes it line up with the bar.
 * That is why every factory preset using this unit carries the row.
 */
export const PLAY_ROW_RESYNCS = { units: finding("playRow.15").units, note: finding("playRow.15").note };

/**
 * Parameters that make a unit inaudible, and the value at which they do it.
 *
 * `level_mod_int` is the reason this is a table rather than a list. It is
 * bipolar: 0 pumps on the beat, 127 pumps off the beat, and the middle does
 * not pump at all. Korg's own Pumper maps the knob from 63 upwards, which
 * said so all along. Treating 0 as off produces a check that is exactly wrong
 * about the one unit it was written for. Confirmed by ear, 2026-09-21.
 *
 * Careful with what "off" means here. At 63 the modulation stops but the
 * signal is quieter than it is with the modulation running, so the unit is
 * still doing something to the level. It is the quiet point, not a bypass.
 * Whether it matches the level with the effect switched off has not been
 * compared.
 *
 * A null means nobody has worked out where the off position is, and the
 * check stays quiet rather than guessing.
 */
export const OFF_AT = Object.fromEntries(findings("offAt").map(f => [f.param, f.value]));

/** Levels the hearing tests settled on, as opposed to what the bytes allow. */
const loud = finding("loudness");
export const LOUDNESS = {
  outputCeiling: loud.outputCeiling,
  outputTypical: loud.outputTypical,
  feedbackCeiling: loud.feedbackCeiling,
  note: loud.note,
};

/** The output levels heard as playable, and the single values heard as unplayable. */
export const GAIN_STAGING = {
  usable: finding("usableLevel").range,
  unplayable: findings("unplayableLevel").map(f => ({ unit: f.unit, param: f.param, value: f.value, note: f.note })),
};

/** Stage 1 units that took the device down as soon as a second stage existed. */
export const STAGE1_NEEDS_SOLO = Object.fromEntries(findings("stage1NeedsSolo")
  .map(f => [f.unit, f.verdict ? { note: f.note, verdict: f.verdict } : { note: f.note }]));

/** Master units. One of these inside an insert chain hangs the device. */
export const MFX_DEVICE_RANGE = finding("mfxDeviceRange").range;
