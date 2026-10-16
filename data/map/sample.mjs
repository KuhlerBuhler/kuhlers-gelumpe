/**
 * The RAM tables the sampler keeps per sample: name, playback values, metadata. A block is one entry
 * of such a table, `meta.table` says where the table sits (src/map/address.mjs turns an index into
 * an address). `i` is zero-based, the display shows i + 1. The notes in docs/messungen/ prove where
 * the bytes sit (byte comparison with the sample file's `esli`) and, for the name and the tune, what a
 * write does; only those two are editable.
 *
 * `count` is 998: the notes do not give the table size, and with an entry of 0x45C bytes the
 * metadata of the 999th sample would run 12 bytes into the name table (derived from the addresses).
 */
const FIRMWARE = "sampler-2.02-hacktribe";
const NAMES = "measure:2026-10-07/sample-name-ram";
const META = "measure:2026-10-07/sample-metadaten-ram";
const l = (de, en = de) => ({ de, en });

const COUNT = 998;

/** A field of one of the three tables; read only and measured unless the field says more. */
const f = (id, label, offset, type, rest = {}) => ({
  id, label, area: "samples", where: { offset }, type, transport: ["ram"],
  edit: "readonly", source: "measured", evidence: META, ...rest,
});

const unknown = (id, label, offset, type, note) => ({
  id, label, area: "samples", where: { offset }, type, transport: ["ram"], edit: "expert", source: "unknown", note,
});

export default [
  {
    block: "sampleName",
    size: 0x20,
    firmware: FIRMWARE,
    label: l("Sample, Namenstabelle", "Sample name table entry"),
    meta: { table: { ram: 0xc047b080, stride: 0x20, count: COUNT } },
    fields: [
      f("sample.header", l("Kopfdaten", "Header data"), 0, "bytes:12", { note: "feste Headerdaten, gleich esli[22:34] der Sample-Datei" }),
          f("sample.name", l("Name", "Name"), 12, "latin1:16", {
        edit: undefined, evidence: NAMES, note: "16 Byte, mit NUL aufgefüllt; am Display bestätigt (Sample 653)",
      }),
      f("sample.category", l("Kategorie", "Category"), 28, "u16le", { note: "gleich esli[18:20]" }),
      f("sample.importNumber", l("Import-Nummer", "Import number"), 30, "u16le", { note: "gleich esli[20:22]" }),
    ],
  },
  {
    block: "samplePlayback",
    size: 0x10,
    firmware: FIRMWARE,
    label: l("Sample, Wiedergabetabelle", "Sample playback table entry"),
    meta: { table: { ram: 0xc0362ee8, stride: 0x10, count: COUNT } },
    fields: [
      f("sample.start", l("Start", "Start"), 0, "u32le", { note: "Audio-Offset plus Startwert aus esli[40:44]; die Einheit ist nicht gemessen" }),
      f("sample.loop", l("Loop", "Loop"), 4, "u32le", { note: "Loop-Wert, gleich esli[44:48]; die Einheit ist nicht gemessen" }),
      f("sample.end", l("Ende", "End"), 8, "u32le", { note: "End-Wert, gleich esli[48:52]; die Einheit ist nicht gemessen" }),
      unknown("sample.playback.unknown12", l("Wiedergabe +12, unbekannt", "Playback +12, unknown"), 12, "u16le",
        "bei sechs frischen Einträgen null und nicht gleich der Playback Period aus esli[34:36]; nicht zugeordnet"),
      f("sample.oneShot", l("One-Shot", "One shot"), 14, "u8", { note: "gleich esli[52]; in der Bank 226 mal 1 und 13 mal 0" }),
      unknown("sample.playback.unknown15", l("Wiedergabe +15, unbekannt", "Playback +15, unknown"), 15, "u8",
        "gleich esli[53], Bedeutung unbekannt"),
    ],
  },
  {
    block: "sampleMeta",
    size: 0x45c,
    firmware: FIRMWARE,
    label: l("Sample, Metadaten", "Sample metadata entry"),
    meta: { table: { ram: 0xc036ad88, stride: 0x45c, count: COUNT } },
    fields: [
      unknown("sample.meta.audioOffset", l("Audio-Offset, vermutet", "Audio offset, presumed"), 0, "u32le",
        "vermuteter Audio-Offset; die Audio-Offsets sind keine bestätigten CPU-RAM-Adressen"),
      f("sample.pcmBytes", l("PCM-Länge", "PCM length"), 4, "u32le", { note: "in Byte, gleich esli[60:64]" }),
      f("sample.stereo", l("Stereo-Flag", "Stereo flag"), 9, "u8", { note: "gleich esli[65]" }),
      f("sample.playLevelFlag", l("Play-Level-Flag", "Play level flag"), 10, "u8", { note: "gleich esli[66]; ihre Wirkung ist nicht geprüft" }),
      f("sample.rate", l("Samplerate", "Sample rate"), 16, "u32le", { unit: "Hz", note: "gleich esli[72:76]" }),
      f("sample.tune", l("Tune", "Tune"), 21, "s8", {
        edit: undefined, convert: "signed8", range: [-128, 127],
        note: "Rohwert; die Skala ist nicht gemessen, -12 änderte die Tonhöhe hörbar, ohne dass die Größe gemessen wurde",
      }),
      f("sample.repeatIndex", l("Wiederholter Index", "Repeated index"), 22, "u16le", { note: "gleich esli[78:80]" }),
      f("sample.slice", l("Slice-Record", "Slice record"), 24, "bytes:16", {
        repeat: [{ count: 64, stride: 16, label: l("Slice") }],
        note: "64 Records zu 16 Byte, gleich esli[80:1104]; die Feldnamen stammen aus dem Dateiformat, ihre Wirkung im Gerät ist nicht bewiesen",
      }),
      f("sample.sliceSteps", l("Slice-Steps", "Slice steps"), 1048, "bytes:64", { note: "gleich esli[1104:1168]" }),
      f("sample.stepCount", l("Step-Anzahl", "Step count"), 1112, "u8", { note: "gleich esli[1168]" }),
      f("sample.beat", l("Beat", "Beat"), 1113, "u8", { note: "gleich esli[1169]" }),
      f("sample.activeSteps", l("Aktive Steps", "Active steps"), 1114, "u8", { note: "gleich esli[1170]" }),
    ],
  },
];
