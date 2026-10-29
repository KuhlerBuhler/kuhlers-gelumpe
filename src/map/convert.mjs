/**
 * Named conversions between a field's raw value and plain words.
 *
 * The raw value is what the field's type reads: an unsigned or signed
 * integer. A converter turns it into a value in a real unit and back. Several
 * raw values may share one plain value (sixteen speeds for 128 bytes), so
 * the guarantee is that a round trip is stable, not that it returns the same
 * byte: fromRaw(toRaw(fromRaw(r))) === fromRaw(r), for every raw value the
 * converter can write.
 *
 * Two kinds of raw value it cannot write, and says so instead of guessing: a
 * value a list does not name (an unknown control source) makes toRaw throw,
 * and a gate between 97 and 126 is outside what Korg documents and lands on
 * 96. Both still read and display. Untouched fields are never rewritten
 * through a converter, so such a byte survives as the device wrote it.
 *
 * Every number here is measured; docs/messungen names where.
 */
import FX from "../../data/map/fx.mjs";
import FX_RANGES from "../../data/map/fx-ranges.mjs";
import { number as localNumber } from "../text.mjs";

const round = (v, digits = 0) => Number(v.toFixed(digits));

/** Pick the raw value whose plain value lies closest to the target. */
function nearest(domain, fromRaw, target) {
  let best = domain[0];
  let bestErr = Infinity;
  for (let r = domain[0]; r <= domain[1]; r++) {
    const err = Math.abs(fromRaw(r) - target);
    if (err < bestErr) { bestErr = err; best = r; }
  }
  return best;
}

/** Piecewise interpolation between measured points, on a log or linear axis. */
function interpolate(points, raw, log) {
  const xs = points.map(p => p[0]);
  if (raw <= xs[0]) return points[0][1];
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i];
    if (raw > x1) continue;
    const [x0, y0] = points[i - 1];
    const t = (raw - x0) / (x1 - x0);
    return log ? y0 * (y1 / y0) ** t : y0 + (y1 - y0) * t;
  }
  return points[points.length - 1][1];
}

const number = value => {
  const n = typeof value === "number" ? value : Number(String(value).replace(",", "."));
  if (!Number.isFinite(n)) throw new RangeError(`${JSON.stringify(value)} is not a number`);
  return n;
};

function numeric({ name, unit, domain, fromRaw, format }) {
  return {
    name, unit, domain,
    fromRaw,
    toRaw: value => nearest(domain, fromRaw, number(value)),
    format: raw => format(raw, fromRaw(raw)),
  };
}

/** A number whose every stored value has its own label, such as "33.3%": the slider shows the label, the value is the number in it. */
function fxLabelled(name, list) {
  return numeric({
    name, unit: null, domain: [0, list.length - 1],
    fromRaw: r => parseFloat(list[r]), format: r => list[r],
  });
}

/** A list of choices. Raw values outside the list read as unknown and are kept. */
export function choices(name, labels, { first = 0, domain = null } = {}) {
  const list = labels.map((label, i) => ({ raw: first + i, label }));
  const known = new Map(list.map(c => [c.raw, c.label]));
  return {
    name, unit: null,
    domain: domain || [first, first + labels.length - 1],
    choices: list,
    fromRaw: raw => raw,
    toRaw: value => {
      const v = Number(value);
      if (!known.has(v)) throw new RangeError(`${value} is not a choice of ${name}`);
      return v;
    },
    format: raw => known.get(raw) ?? `unbekannt (${raw})`,
  };
}

const NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
/** Note 60 is C4: the factory default note, 61 in a step slot, is C4. */
export const noteLabel = n => `${NOTE[n % 12]}${Math.floor(n / 12) - 1}`;

/** measure:2026-09-17/osc-pitch */
const PITCH_STEPS = [[5, 1], [10, 5], [11, 10], [15, 20], [17, 40], [22, 60], [24, 50], [48, 25], [63, 80]];
const PITCH_CENTS = (() => {
  const t = [0];
  let prev = 0;
  for (const [upTo, step] of PITCH_STEPS) {
    for (let b = prev + 1; b <= upTo; b++) t[b] = t[b - 1] + step;
    prev = upTo;
  }
  return t;
})();

/** measure:2026-09-17/envelope-time, milliseconds */
const ENV_POINTS = [[8, 30], [16, 48], [24, 85], [32, 130], [48, 275], [64, 490], [80, 700], [96, 1100], [112, 2900], [127, 5300]];
/** measure:2026-09-17/glide-time, milliseconds */
const GLIDE_POINTS = [[4, 10], [12, 20], [16, 30], [24, 60], [32, 90], [48, 180], [64, 321], [88, 790], [96, 1302], [104, 2011], [112, 3359], [120, 5630], [126, 5630 * 1.5]];
/** measure:2026-09-17/cutoff-resonance-peak, dB at the corner */
const RESO_POINTS = [[0, 0], [8, 1.9], [64, 12.5], [112, 24.1], [126, 27.0]];
/** measure:2026-09-17/mod-speed-depth, one note value per eight bytes from 32 */
const MOD_SPEEDS = ["1/2", "3/8", "1/3", "1/4", "3/16", "1/6", "1/8", "1/12", "1/16", "1/24", "1/32", "1/64"];

const ms = v => v >= 1000 ? `${localNumber(round(v / 1000, 1))} s` : `${Math.round(v)} ms`;

/** korg-spec: Parameter Guide, Scale List. 35 names, numbered from 0. */
const SCALES = [
  "Chromatic", "Ionian", "Dorian", "Phrygian", "Lydian", "Mixolydian", "Aeolian", "Locrian",
  "Harm minor", "Melo minor", "Major Blues", "minor Blues", "Diminished", "Com.Dim",
  "Major Penta", "minor Penta", "Raga 1", "Raga 2", "Raga 3", "Arabic", "Spanish", "Gypsy",
  "Egyptian", "Hawaiian", "Pelog", "Japanese", "Ryuku", "Chinese", "Bass Line", "Whole Tone",
  "minor 3rd", "Major 3rd", "4th Interval", "5th Interval", "Octave",
];

/** korg-spec: MIDI Implementation, Table 5, Destination List. */
const MOTION_DESTINATIONS = [
  "Aus", "reserviert", "Osc Pitch", "Osc Glide", "Osc Edit", "Cutoff", "Resonanz", "Filter EG Int",
  "Mod Depth", "Mod Speed", "Amp Level", "Pan", "Attack", "Decay/Release", "IFX Edit",
  "Master FX X", "Master FX Y", "IFX An/Aus", "MFX Send", "MFX Pad An/Aus",
];

/** derived:vsb-table/0xC00FED74. Effect parameters whose DSP table starts below zero: the byte is the shown value plus this much. */
const FX_SHIFTS = [...new Set(Object.values(FX_RANGES.units).flat().map(([min]) => -min).filter(n => n > 0))].sort((a, b) => a - b);

const FX_SOURCES = FX.meta.sources.map(s => [s.raw, s.label]);
const FX_CHAINS = FX.meta.chains.map(c => [c.raw, c.label]);

const MOD_SOURCES = ["EG+", "EG+ BPM", "EG-", "EG- BPM", "LFOTri", "LFOTriB", "SawUpB", "SawDwnB", "SquUpB", "SquDwnB", "S&HBPM", "Random"];
const MOD_TARGETS = ["Filter", "Pitch", "OSC", "Level", "Pan", "IFX"];

export const CONVERTERS = {
  plain: numeric({
    name: "plain", unit: null, domain: [0, 127],
    fromRaw: r => r, format: r => String(r),
  }),

  plain255: numeric({
    name: "plain255", unit: null, domain: [0, 255],
    fromRaw: r => r, format: r => String(r),
  }),

  signed63: numeric({
    name: "signed63", unit: null, domain: [-63, 63],
    fromRaw: r => r, format: r => (r > 0 ? `+${r}` : String(r)),
  }),

  signed8: numeric({
    name: "signed8", unit: null, domain: [-128, 127],
    fromRaw: r => r, format: r => (r > 0 ? `+${r}` : String(r)),
  }),

  pan: numeric({
    name: "pan", unit: null, domain: [-63, 63],
    fromRaw: r => r, format: r => (r === 0 ? "Mitte" : r < 0 ? `L${-r}` : `R${r}`),
  }),

  bipolar63: numeric({
    name: "bipolar63", unit: null, domain: [0, 127],
    fromRaw: r => r - 63, format: (r, v) => (v === 0 ? "Mitte (Ruhepunkt)" : v > 0 ? `+${v}` : String(v)),
  }),

  ...Object.fromEntries(FX_SHIFTS.map(n => [`fxShift${n}`, numeric({
    name: `fxShift${n}`, unit: null, domain: [0, 127],
    fromRaw: r => r - n, format: (r, v) => (v > 0 ? `+${v}` : String(v)),
  })])),

  // Effect value labels as the DSP's text functions show them (address in the field's choiceEvidence and in fx-ranges.mjs).
  timeRatio: fxLabelled("timeRatio", FX_RANGES.labels.timeRatio.list),
  looperStep: fxLabelled("looperStep", FX_RANGES.labels.looperStep.list),
  filterOutput: choices("filterOutput", ["LPF4", "LPF3", "LPF2", "BPF", "HPF"]),
  envelopeSelect: choices("envelopeSelect", ["LR Mix", "LR Indv"]),
  maskType: choices("maskType", ["Simple", "Absolute"]),
  phaserType: choices("phaserType", ["2stage", "4stage"]),
  phasePolarity: choices("phasePolarity", ["+", "-"]),
  lfoWaveTriSin: choices("lfoWaveTriSin", ["LFO Tri+", "LFO Sin+"]),
  feedbackType: choices("feedbackType", ["Stereo", "Cross"]),
  loopType: choices("loopType", ["Looper", "RevLooper", "TriggerLooper"]),
  levelModType: choices("levelModType", ["mpy", "add"]),
  modShape: choices("modShape", [
    "SAW", "TRI", "SIN", "SQU", "EXP", "LOG", "LOGH", "---",
    "SAWPLUS", "TRIPLUS", "SINPLUS", "SQUPLUS", "EXPPLUS", "LOGPLUS", "LOGHPLUS", "-------",
  ]),

  cutoffHz: numeric({
    name: "cutoffHz", unit: "Hz", domain: [0, 127],
    fromRaw: r => round(654 * 2 ** ((r - 64) / 12.09), 1),
    format: (r, v) => (v >= 1000 ? `${localNumber(round(v / 1000, 2))} kHz` : `${Math.round(v)} Hz`),
  }),

  resonanceDb: numeric({
    name: "resonanceDb", unit: "dB", domain: [0, 127],
    fromRaw: r => (r === 127 ? 33.6 : round(interpolate(RESO_POINTS, r, false), 1)),
    format: (r, v) => (r === 127 ? "Selbstoszillation" : `+${localNumber(v)} dB`),
  }),

  oscPitchCents: numeric({
    name: "oscPitchCents", unit: "Cent", domain: [-63, 63],
    fromRaw: r => Math.sign(r) * (PITCH_CENTS[Math.abs(r)] ?? PITCH_CENTS[63]),
    format: (r, v) => {
      if (Math.abs(r) > 63) return `unbekannt (${r})`;
      if (v === 0) return "0 Cent";
      const s = v > 0 ? "+" : "-";
      const a = Math.abs(v);
      if (a % 1200 === 0) return `${s}${a / 1200} Okt.`;
      if (a % 100 === 0) return `${s}${a / 100} Halbt.`;
      return `${s}${a} Cent`;
    },
  }),

  envTime: numeric({
    name: "envTime", unit: "ms", domain: [0, 127],
    fromRaw: r => Math.round(r <= 8 ? 30 : interpolate(ENV_POINTS, r, true)),
    format: (r, v) => (r <= 8 ? "unter 30 ms" : ms(v)),
  }),

  glideMs: numeric({
    name: "glideMs", unit: "ms", domain: [0, 127],
    fromRaw: r => (r === 0 ? 0 : r === 127 ? 40000 : Math.round(interpolate(GLIDE_POINTS, r, true))),
    format: (r, v) => (r === 0 ? "aus" : r === 127 ? "etwa 40 s" : ms(v)),
  }),

  modSpeed: {
    name: "modSpeed", unit: null, domain: [0, 127],
    choices: [
      { raw: 0, label: "langsamer als 1/2 (nicht gemessen)" },
      ...MOD_SPEEDS.map((label, i) => ({ raw: 32 + i * 8, label })),
    ],
    fromRaw: r => (r < 32 ? -1 : Math.floor((r - 32) / 8)),
    toRaw: v => (Number(v) < 0 ? 0 : 32 + Math.min(11, Math.round(Number(v))) * 8),
    format: r => (r < 32 ? "langsamer als 1/2 (nicht gemessen)" : MOD_SPEEDS[Math.floor((r - 32) / 8)]),
  },

  modType: choices("modType", MOD_SOURCES.flatMap(s => MOD_TARGETS.map(t => `${s} ${t}`))),

  filterType: {
    ...choices("filterType", ["OFF"], { domain: [0, 16] }),
    choices: [
      { raw: 0, label: "OFF" }, { raw: 1, label: "electribe LPF" },
      { raw: 7, label: "electribe HPF" }, { raw: 12, label: "electribe BPF" },
    ],
    toRaw: v => {
      const n = Number(v);
      if (!Number.isInteger(n) || n < 0 || n > 16) throw new RangeError(`${v} is not a filter type`);
      return n;
    },
    format: r => ({ 0: "OFF", 1: "electribe LPF", 7: "electribe HPF", 12: "electribe BPF" })[r]
      ?? `Hacktribe-Filter ${r}`,
  },

  noteName: numeric({
    name: "noteName", unit: null, domain: [0, 127],
    fromRaw: r => r, format: r => noteLabel(r),
  }),

  /** A step's note slot: 0 is empty, otherwise the note number plus one. */
  stepNote: {
    name: "stepNote", unit: null, domain: [0, 128],
    fromRaw: r => (r === 0 ? null : r - 1),
    toRaw: v => (v === null || v === "" ? 0 : Math.max(0, Math.min(127, Math.round(Number(v)))) + 1),
    format: r => (r === 0 ? "leer" : noteLabel(r - 1)),
  },

  tempoBpm: numeric({
    name: "tempoBpm", unit: "BPM", domain: [200, 3000],
    fromRaw: r => r / 10, format: (r, v) => `${localNumber(v)} BPM`,
  }),

  /** Korg's spec: 0 to 96, 127 is a tie. 255 is common and unexplained. */
  gateTime: {
    name: "gateTime", unit: null, domain: [0, 127],
    valid: r => r <= 96 || r === 127,
    fromRaw: r => r,
    toRaw: v => {
      const n = Math.round(Number(v));
      if (n === 127) return 127;
      return Math.max(0, Math.min(96, n));
    },
    format: r => (r <= 96 ? `${r}/96` : r === 127 ? "Tie (laut Korg)" : `unbekannt (${r})`),
  },

  /** Stored upside down: 127 means level 0. */
  playLevel: numeric({
    name: "playLevel", unit: null, domain: [0, 127],
    fromRaw: r => 127 - r, format: (r, v) => String(v),
  }),

  onOff: choices("onOff", ["Aus", "An"]),

  /** A part's sample. A part that never had one holds 0xFFFF. */
  sampleSlot: numeric({
    name: "sampleSlot", unit: null, domain: [0, 999],
    fromRaw: r => r, format: r => (r === 0xffff ? "kein Sample" : String(r)),
  }),

  /** Shown counting from one, stored from zero: channels. */
  oneBased: numeric({
    name: "oneBased", unit: null, domain: [0, 127],
    fromRaw: r => r + 1, format: (r, v) => String(v),
  }),

  /** measure:2026-10-14/global-felder: the display shows 1 to 25 for the bytes 18 to 42. */
  contrast: numeric({
    name: "contrast", unit: null, domain: [18, 42],
    fromRaw: r => r - 17, format: (r, v) => String(v),
  }),

  patternLength: choices("patternLength", ["1 Takt", "2 Takte", "3 Takte", "4 Takte"]),
  beat: choices("beat", ["16tel", "32tel", "8tel-Triolen", "16tel-Triolen"]),
  key: choices("key", NOTE),
  scale: choices("scale", SCALES),
  voiceAssign: choices("voiceAssign", ["Mono 1", "Mono 2", "Poly 1", "Poly 2"]),
  motionMode: choices("motionMode", ["Aus", "Smooth", "Trigger Hold"]),
  priority: choices("priority", ["Normal", "Hoch"]),
  motionPart: choices("motionPart", ["Aus", ...Array.from({ length: 16 }, (_, i) => `Part ${i + 1}`), "Master FX"]),
  motionDestination: choices("motionDestination", MOTION_DESTINATIONS),

  metronome: choices("metronome", ["Aus", "Rec 0", "Rec 1", "Rec 2", "An"]),
  syncPolarity: choices("syncPolarity", ["steigend", "fallend"]),
  syncResolution: choices("syncResolution", ["1 Step", "2 Steps"]),
  velocityCurve: choices("velocityCurve", ["Heavy", "Normal", "Light", "Const 96"]),
  knobMode: choices("knobMode", ["Jump", "Catch", "Value Scale"]),
  triggerMode: choices("triggerMode", ["Normal", "Seq 1st", "Seq Play"]),
  batteryMode: choices("batteryMode", ["Ni-MH", "Alkali"]),
  autoPowerOff: choices("autoPowerOff", ["Aus", "nach 4 Stunden"]),
  powerSave: choices("powerSave", ["Aus", "Auto", "An"]),
  octaves: choices("octaves", ["1 Oktave", "2 Oktaven", "3 Oktaven", "4 Oktaven"], { first: 1 }),
  clockMode: choices("clockMode", ["Intern", "Auto", "Extern USB", "Extern MIDI", "Extern Sync"]),
  midiFilter: choices("midiFilter", ["Aus", "Short", "Short + Program"]),

  /** What drives a control map row. Insert presets have no Y. */
  fxSource: {
    ...choices("fxSource", [], { domain: [0, 255] }),
    choices: FX_SOURCES.map(([raw, label]) => ({ raw, label })),
    toRaw: v => {
      const n = Number(v);
      if (n !== 0 && !FX_SOURCES.some(([raw]) => raw === n)) throw new RangeError(`${v} is not a control source`);
      return n;
    },
    format: r => (r === 0 ? "aus" : FX_SOURCES.find(([raw]) => raw === r)?.[1] ?? `unbekannt (${r})`),
  },

  fxChain: {
    ...choices("fxChain", [], { domain: [0, 255] }),
    choices: FX_CHAINS.map(([raw, label]) => ({ raw, label })),
    toRaw: v => {
      const n = Number(v);
      if (!FX_CHAINS.some(([raw]) => raw === n)) throw new RangeError(`${v} is not a known target`);
      return n;
    },
    format: r => FX_CHAINS.find(([raw]) => raw === r)?.[1] ?? `unbekannt (${r})`,
  },

  /** A unit number; its name comes from the unit table, which the page loads. */
  fxDevice: numeric({
    name: "fxDevice", unit: null, domain: [0, 255],
    fromRaw: r => r, format: r => `0x${r.toString(16).padStart(2, "0")}`,
  }),

  /** The waveform of the LFO unit of a modulation type (measure:2026-10-15/modulation-stufe2, section 4). 7 acts as 4, 8 and up read past a table. */
  modCurve: choices("modCurve", ["Sägezahn fallend", "Rechteck", "Dreieck", "Sample and Hold", "Zufall", "Rechteck einpolig", "Sinus"], { domain: [0, 255] }),

  /** Source of a modulation slot. 2 is what the editor writes for off; 2, 3 and 255 all measured as off. */
  modSlotSource: choices("modSlotSource", ["Hüllkurve", "LFO", "Aus"]),

  /** Target code of a modulation slot. 4 to 7 act (no type uses them), what they do to the sound is open. */
  modSlotTarget: choices("modSlotTarget", ["Kein Ziel", "Pitch", "OSC", "Filter", "Code 4", "Code 5", "Code 6", "Code 7", "Level", "Pan", "IFX"]),

  modTarget: {
    ...choices("modTarget", ["Pan", "Pitch", "OSC", "Filter", "Level", "IFX"]),
  },
};

export function converter(name) {
  const c = CONVERTERS[name];
  if (!c) throw new Error(`no converter called ${name}`);
  return c;
}
