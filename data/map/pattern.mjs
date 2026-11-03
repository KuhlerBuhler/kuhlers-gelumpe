/**
 * The pattern block, 0x4000 bytes. The same block travels in a pattern
 * backup (.e2sallpat), a single pattern file (.e2spat), the pattern SysEx
 * dump and the flash; where it sits in each is the address module's job.
 *
 * Offsets are relative to the start of the block.
 */
const PATTERN_DIFF = "measure:2026-09-16/pattern-diff";
const CC = "measure:2026-09-16/cc-map";
const CHAIN = "measure:2026-10-10/pattern-kette-import";
const SPEC = "korg-spec:MIDI Implementation, Table 1";
const PART_SPEC = "korg-spec:MIDI Implementation, Table 6";
const MOTION_SPEC = "korg-spec:MIDI Implementation, Table 5";
const LIVE = "measure:2026-11-03/live-schreibwege";

const TRANSPORT = ["pattern-sysex", "e2sallpat", "e2spat"];
const PART = [{ count: 16, stride: 0x330, label: { de: "Part", en: "Part" } }];
const STEP = [...PART, { count: 64, stride: 12, label: { de: "Step", en: "Step" } }];
const PART_BASE = 0x800;
const STEP_BASE = PART_BASE + 0x30;

const l = (de, en = de) => ({ de, en });

/**
 * How the running firmware writes the value: its setter on each build, the arguments, whether a plain byte write
 * into the pattern in RAM does the same, and what else the setter refreshes (docs/geraetekarte.md, Schreibweg).
 */
const live = (hacktribe, blue, args, plainWrite, refresh, status = "gemessen", red = hacktribe) => ({
  setter: { hacktribe, red, blue }, args, plainWrite, refresh, status, evidence: LIVE,
});
const PAT = "(Pattern-Objekt, Wert, 1)";
const MFX = "(Pattern-Objekt + 0x4004, Wert, 1)";
const PRT = "(Pattern-Objekt + 0x400C, Part, Wert, 1)";
const KNOB = n => `(r0 aus 0xC034886C, beim Blue 0xC0348570, 0x10, 0, Parameter ${n}), Wert und 0 auf dem Stack`;
const COPY = "Kopie für die Klangerzeugung hinter dem Block";
const NOTIFY = "nur die Meldung an die Beobachter, sonst nichts";
const SCALE = "Tonart- und Skalen-Cache ab 0xC068C280 (Blue 0xC0566588)";

const f = (id, label, offset, rest) => ({
  id, label, where: { offset }, type: "u8", transport: TRANSPORT, ...rest,
});

const part = (id, label, k, rest) =>
  f(`part.${id}`, label, PART_BASE + k, { area: "parts", repeat: PART, ...rest });

const step = (id, label, k, rest) =>
  f(`step.${id}`, label, STEP_BASE + k, { area: "steps", repeat: STEP, ...rest });

export default {
  block: "pattern",
  size: 0x4000,
  label: l("Pattern"),
  fields: [
    f("pattern.magic", l("Kennung"), 0, { area: "pattern", type: "bytes:4", edit: "readonly", source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.size", l("Größe", "Size"), 4, { area: "pattern", type: "u32le", edit: "readonly", source: "korg-spec", evidence: SPEC }),
    f("pattern.version", l("Pattern-Version", "Pattern version"), 12, { area: "pattern", type: "bytes:4", edit: "readonly", source: "korg-spec", evidence: SPEC }),
    f("pattern.name", l("Name"), 16, { area: "pattern", type: "latin1:16", source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.tempo", l("Tempo"), 34, { area: "pattern", type: "u16le", convert: "tempoBpm", unit: "BPM", range: [200, 3000], source: "measured", evidence: PATTERN_DIFF,
      live: live("0xC004A80C", "0xC00448EC", PAT, false, "Clock-Zähler und Hauptanzeige, beim Blue auch eine LED") }),
    f("pattern.swing", l("Swing"), 36, { area: "pattern", type: "s8", convert: "signed63", range: [-48, 48], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A594", "0xC0044674", PAT, true, NOTIFY) }),
    f("pattern.length", l("Länge", "Length"), 37, { area: "pattern", convert: "patternLength", range: [0, 3], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A560", "0xC0044640", PAT, false, "kopiert beim Verlängern die Steps des ersten Takts nach hinten") }),
    f("pattern.beat", l("Beat"), 38, { area: "pattern", convert: "beat", range: [0, 4], source: "measured", evidence: "measure:2026-10-29/beat-achtel", note: "4 (8tel) nur mit BLECH; Korgs Firmware kennt 0 bis 3 und spielt 4 mit einem Step alle 2 ms",
      live: live("0xC004A4F8", "0xC00445F8", PAT, null, "Meldung an die Beobachter; Hacktribe und Rot melden zusätzlich Parameter 0x3B an die Klangerzeugung, ohne Spur im RAM. Ob das Byte allein reicht, ist offen; der Setter ist der sichere Weg") }),
    f("pattern.key", l("Tonart", "Key"), 39, { area: "pattern", convert: "key", range: [0, 11], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A6FC", "0xC00447DC", PAT, false, SCALE) }),
    f("pattern.scale", l("Tonleiter", "Scale"), 40, { area: "pattern", convert: "scale", range: [0, 34], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A77C", "0xC004485C", PAT, false, SCALE) }),
    f("pattern.chordset", l("Chord Set"), 41, { area: "pattern", convert: "plain", range: [0, 4], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A534", "0xC0044614", PAT, false, "Chord-Cache ab 0xC068CFD0 (Blue 0xC05672D8)") }),
    f("pattern.playLevel", l("Lautstärke", "Play level"), 42, { area: "pattern", convert: "playLevel", range: [0, 127], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A698", "0xC0044778", PAT, false, "Kopie hinter dem Block bei 0x426E (Blue 0x424E)") }),
    f("pattern.gateArp", l("Gate Arp"), 49, { area: "pattern", convert: "plain", range: [0, 49], source: "measured", evidence: LIVE,
      note: "Seite GATE ARP im Pattern-Menü",
      live: live("0xC004A5F8", "0xC00446D8", PAT, true, NOTIFY) }),
    f("pattern.mfx.touch", l("Pad berührt", "Pad touched"), 60, { area: "master", convert: "onOff", range: [0, 1], source: "measured", evidence: LIVE,
      note: "1, solange das Pad im Master-FX-Modus berührt ist",
      live: live("0xC00488A0", "0xC0042AF8", MFX, false, `${COPY} und der Zustand des Master-Effekts`) }),
    f("pattern.mfx.type", l("Master-Effekt", "Master effect"), 61, { area: "master", convert: "plain", range: [0, 99], source: "measured", evidence: PATTERN_DIFF, note: "Platz im Master-Menü, mit Hacktribe über Korgs Bereich hinaus",
      live: live("0xC0048A64", "0xC0042CBC", MFX, false, `${COPY} (0x401D) und der Zustand des Master-Effekts`) }),
    f("pattern.mfx.padX", l("Pad X, zuletzt", "Pad X, last"), 62, { area: "master", convert: "plain", range: [0, 127], source: "measured", evidence: PATTERN_DIFF,
      live: live("0xC0048924", "0xC0042B7C", MFX, false, `${COPY} und der Zustand des Master-Effekts`) }),
    f("pattern.mfx.padY", l("Pad Y, zuletzt", "Pad Y, last"), 63, { area: "master", convert: "plain", range: [0, 127], source: "measured", evidence: PATTERN_DIFF,
      live: live("0xC0048984", "0xC0042BDC", MFX, false, `${COPY} und der Zustand des Master-Effekts`) }),
    f("pattern.mfx.hold", l("Pad halten", "Pad hold"), 65, { area: "master", convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF,
      live: live("0xC00489E4", "0xC0042C3C", MFX, false, `${COPY}; setzt auch Byte 60`) }),
    f("pattern.alternate1314", l("Alternate 13-14"), 68, { area: "pattern", convert: "onOff", range: [0, 1], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A614", "0xC00446F4", "(Pattern-Objekt, 0, Wert, 1)", false, `${COPY} (0x4024)`) }),
    f("pattern.alternate1516", l("Alternate 15-16"), 69, { area: "pattern", convert: "onOff", range: [0, 1], source: "korg-spec", evidence: SPEC,
      live: live("0xC004A614", "0xC00446F4", "(Pattern-Objekt, 1, Wert, 1)", false, `${COPY} (0x4025)`) }),
    f("pattern.touchScale", l("Touch Scale, unbekannt", "Touch scale, unknown"), 44, { area: "pattern", type: "bytes:5", edit: "expert", source: "unknown",
      note: "Korgs Tabelle legt Touch Scale und Master FX hierhin; Master FX liegt gemessen 8 Byte weiter, Gate Arp bei 49. Im Emulator schreibt und liest der Touch-Scale-Modus hier kein Byte, der Bereich bleibt unbekannt" }),
    f("pattern.unknown50", l("Bytes 50 bis 59, unbekannt", "Bytes 50 to 59, unknown"), 50, { area: "pattern", type: "bytes:10", edit: "expert", source: "unknown",
      note: "im Emulator schreibt und liest kein Menü und keine Taste hier ein Byte" }),

    f("pattern.chainTo", l("Chain To"), 15104, { area: "pattern", convert: "plain255", range: [0, 250], source: "measured", evidence: CHAIN,
      note: "Nummer des Ziel-Patterns, von 1 gezählt; 0 heißt keine Kette. Byte 15105 ist in allen 250 Patterns 0",
      live: live("0xC004A5B0", "0xC0044690", PAT, true, NOTIFY) }),
    f("pattern.chainRepeat", l("Chain Repeat"), 15106, { area: "pattern", convert: "plain", range: [0, 127], source: "measured", evidence: CHAIN,
      note: "Das Gerät zeigt 0 und 1 beide als 1; ein auf 3 gestellter Wert steht im Byte als 3",
      live: live("0xC004A5D4", "0xC00446B4", PAT, true, NOTIFY) }),

    f("motion.part", l("Motion: Part"), 256, { area: "motion", repeat: [{ count: 24, stride: 1, label: l("Slot") }], convert: "motionPart", range: [0, 17], edit: "expert", source: "korg-spec", evidence: MOTION_SPEC, note: "am Gerät nicht geprüft" }),
    f("motion.destination", l("Motion: Ziel", "Motion: destination"), 280, { area: "motion", repeat: [{ count: 24, stride: 1, label: l("Slot") }], convert: "motionDestination", range: [0, 19], edit: "expert", source: "korg-spec", evidence: MOTION_SPEC, note: "am Gerät nicht geprüft" }),
    f("motion.value", l("Motion: Wert", "Motion: value"), 304, { area: "motion", repeat: [{ count: 24, stride: 64, label: l("Slot") }, { count: 64, stride: 1, label: l("Schritt", "Step") }], convert: "plain", range: [0, 127], edit: "expert", source: "korg-spec", evidence: MOTION_SPEC,
      note: "am Gerät nicht geprüft. Korgs Text nennt 49 als Beginn, die Tabellengröße 1584 = 24 + 24 + 24 * 64 geht nur ab 48 auf." }),

    part("lastStep", l("Last Step"), 0, { convert: "plain", range: [0, 15], source: "measured", evidence: LIVE,
      note: "Seite LAST STEP im Part-Menü; das Display zeigt 0 als 16, 1 bis 15 wie sie sind. Werks-Parts haben 0",
      live: live("0xC0048CE8", "0xC0042EC4", PRT, true, "keine, der Setter ist nur der Store") }),
    part("mute", l("Stumm", "Mute"), 1, { convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF,
      live: live("0xC0049330", "0xC00434F0", PRT, false, `${COPY} und der Stimmenzustand`) }),
    part("voiceAssign", l("Voice Assign"), 2, { convert: "voiceAssign", range: [0, 3], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC00493A0", "0xC0043560", PRT, false, COPY) }),
    part("motionMode", l("Motion Sequence"), 3, { convert: "motionMode", range: [0, 2], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC0049410", "0xC00435D0", PRT, false, COPY) }),
    part("padVelocity", l("Pad-Velocity", "Pad velocity"), 4, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC0049478", "0xC0043638", PRT, false, COPY) }),
    part("scaleMode", l("Scale Mode"), 5, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC00492A0", "0xC0043460", PRT, false, SCALE) }),
    part("priority", l("Part-Priorität", "Part priority"), 6, { convert: "priority", range: [0, 1], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC00494E8", "0xC00436A8", PRT, false, COPY) }),
    part("sample", l("Sample"), 8, { type: "u16le", convert: "sampleSlot", range: [0, 999], source: "measured", evidence: PATTERN_DIFF, note: "Slot-Nummer des Samples",
      live: live("0xC0048460", "0xC0042700", KNOB(8), false, `${COPY}, Stimmen und Anzeige; schreibt auch Byte 11`) }),
    part("oscEdit", l("Osc Edit"), 11, { convert: "plain", range: [0, 127], source: "measured", evidence: CC }),
    part("filterType", l("Filtertyp", "Filter type"), 12, { convert: "filterType", range: [0, 16], source: "measured", evidence: "measure:2026-09-17/filter-types" }),
    part("cutoff", l("Cutoff"), 13, { convert: "cutoffHz", unit: "Hz", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/cutoff-resonance-peak" }),
    part("resonance", l("Resonanz", "Resonance"), 14, { convert: "resonanceDb", unit: "dB", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/cutoff-resonance-peak" }),
    part("egInt", l("Filter EG Int"), 15, { type: "s8", convert: "signed63", range: [-63, 63], source: "measured", evidence: PATTERN_DIFF }),
    part("modType", l("Modulation"), 16, { convert: "modType", range: [0, 71], source: "measured", evidence: "measure:2026-09-17/mod-speed-depth" }),
    part("modSpeed", l("Mod Speed"), 17, { convert: "modSpeed", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/mod-speed-depth" }),
    part("modDepth", l("Mod Depth"), 18, { convert: "plain", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/mod-speed-depth" }),
    part("attack", l("Attack"), 20, { convert: "envTime", unit: "ms", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/envelope-time" }),
    part("decay", l("Decay/Release"), 21, { convert: "envTime", unit: "ms", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/envelope-time" }),
    part("level", l("Amp Level"), 24, { convert: "plain", range: [0, 127], source: "measured", evidence: CC,
      live: live("0xC0048460", "0xC0042700", KNOB(19), false, `${COPY} und das Parameterfenster`) }),
    part("pan", l("Panorama", "Pan"), 25, { type: "s8", convert: "pan", range: [-63, 63], source: "measured", evidence: PATTERN_DIFF }),
    part("egOn", l("Hüllkurve an", "EG on"), 26, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC0049664", "0xC0043780", PRT, false, COPY) }),
    part("mfxSend", l("MFX Send"), 27, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC00496D4", "0xC00437F0", PRT, false, COPY) }),
    part("grooveType", l("Groove"), 28, { convert: "plain", range: [0, 24], source: "korg-spec", evidence: PART_SPEC,
      note: "der Setter klemmt bei Hacktribe erst über 61, bei Rot und Blau über 24 (aus dem Code gelesen); darüber setzt er 0",
      live: live("0xC0049DA4", "0xC0043EC0", PRT, true, NOTIFY) }),
    part("grooveDepth", l("Groove-Tiefe", "Groove depth"), 29, { convert: "plain", range: [0, 127], source: "korg-spec", evidence: PART_SPEC,
      live: live("0xC0049D7C", "0xC0043E98", PRT, true, NOTIFY) }),
    part("ifxOn", l("IFX an", "IFX on"), 32, { convert: "onOff", range: [0, 1], source: "measured", evidence: CC,
      live: live("0xC0049DEC", "0xC0043F08", PRT, false, COPY) }),
    part("ifxType", l("Insert-Effekt", "Insert effect"), 33, { convert: "plain", range: [0, 99], source: "measured", evidence: PATTERN_DIFF, note: "Platz im Insert-Menü, mit Hacktribe über Korgs Bereich hinaus",
      live: live("0xC0048460", "0xC0042700", KNOB(26), false, COPY) }),
    part("ifxEdit", l("IFX Edit"), 34, { convert: "plain", range: [0, 127], source: "measured", evidence: CC }),
    part("pitch", l("Osc Pitch"), 36, { type: "s8", convert: "oscPitchCents", unit: "Cent", range: [-63, 63], source: "measured", evidence: "measure:2026-09-17/osc-pitch" }),
    part("glide", l("Glide"), 37, { convert: "glideMs", unit: "ms", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/glide-time",
      transport: ["e2sallpat", "e2spat", "cc"], note: "Pattern senden verwirft dieses Byte; am Gerät geht es nur per CC 81" }),
    part("byte38", l("Byte 38, unbekannt", "Byte 38, unknown"), 38, { edit: "expert", source: "unknown", note: "belegt, Bedeutung unbekannt" }),

    step("on", l("An", "On"), 0, { convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF }),
    step("gate", l("Gate"), 1, { convert: "gateTime", range: [0, 127], source: "korg-spec", evidence: PART_SPEC, note: "255 kommt oft vor und ist ungeklärt" }),
    step("velocity", l("Velocity"), 2, { convert: "plain", range: [1, 127], source: "measured", evidence: PATTERN_DIFF }),
    step("trigger", l("Trigger"), 3, { convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF }),
    f("step.note", l("Note"), STEP_BASE + 4, { area: "steps", repeat: [...STEP, { count: 4, stride: 1, label: l("Note") }], convert: "stepNote", range: [0, 128], source: "measured", evidence: PATTERN_DIFF }),
  ],
};
