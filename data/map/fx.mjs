/**
 * One effect preset record, 0x20C bytes, the same for master and insert.
 * The record layout comes from hacktribe-editor; the tables it sits in were
 * measured by writing into them live.
 *
 * Offsets are relative to the start of the record. The unit parameters,
 * whose meaning depends on the unit in a stage, are generated into
 * fx-params.mjs from data/units.json.
 */
const FORMAT = "derived:hacktribe-editor/src/hacktribe_editor/utils/ht_fx_ram_format.py";
const l = (de, en = de) => ({ de, en });
const TRANSPORT = ["ram", "firmware"];
const ROW = [{ count: 10, stride: 28, label: l("Zeile", "Row") }];
const STAGE = [{ count: 3, stride: 0x4a, label: l("Stufe", "Stage"), names: ["ifx1", "ifx2", "mfx"] }];

const r = (id, label, offset, rest) => ({
  id, label, area: "fx", where: { offset }, type: "u8", transport: TRANSPORT,
  source: "derived", evidence: FORMAT, ...rest,
});

export default {
  block: "fxRecord",
  size: 0x20c,
  label: l("Effekt-Preset", "Effect preset"),
  meta: {
    // Unit parameters start this many bytes behind their stage's device byte, at stride 2.
    paramsFromDevice: 0x0b,
    paramStride: 2,
    // What drives a control map row; insert presets have no touchpad, so no Y.
    // `who` is the name for a sentence per effect kind: the insert effect has a knob where the master has the touchpad (a reading of Korg's "X / knob", not measured).
    sources: [
      { raw: 0x41, name: "FX on/off", label: "FX-Schalter", ifx: true, mfx: true, who: { ifx: "FX-Schalter", mfx: "FX-Schalter" } },
      { raw: 0x42, name: "X / knob", label: "X / Regler", ifx: true, mfx: true, who: { ifx: "Regler", mfx: "Touchpad X" } },
      { raw: 0x43, name: "Y", label: "Y", ifx: false, mfx: true, who: { mfx: "Touchpad Y" } },
      { raw: 0x44, name: "knob upper half / X upper half", label: "obere Hälfte", ifx: true, mfx: true, who: { ifx: "Regler, obere Hälfte", mfx: "Touchpad X, obere Hälfte" } },
      { raw: 0x45, name: "knob lower half / X lower half", label: "untere Hälfte", ifx: true, mfx: true, who: { ifx: "Regler, untere Hälfte", mfx: "Touchpad X, untere Hälfte" } },
      { raw: 0x46, name: "Y upper half", label: "Y obere Hälfte", ifx: false, mfx: true, who: { mfx: "Touchpad Y, obere Hälfte" } },
      { raw: 0x47, name: "Y lower half", label: "Y untere Hälfte", ifx: false, mfx: true, who: { mfx: "Touchpad Y, untere Hälfte" } },
      { raw: 0x4a, name: "play pressed", label: "Play", ifx: true, mfx: true, who: { ifx: "Play-Taste", mfx: "Play-Taste" } },
    ],
    // What a row drives.
    chains: [
      { raw: 0x00, name: "insert stage 1", label: "Insert Stufe 1", stage: "ifx1" },
      { raw: 0x01, name: "insert stage 2", label: "Insert Stufe 2", stage: "ifx2" },
      { raw: 0x02, name: "master", label: "Master", stage: "mfx" },
      { raw: 0x07, name: "input level", label: "Eingangspegel", stage: null },
      { raw: 0x0a, name: "output level", label: "Ausgangspegel", stage: null },
    ],
  },
  fields: [
    r("fx.name", l("Name"), 0x01, { type: "latin1:15" }),
    r("fx.map.source", l("Steuerung", "Control"), 0x12, { repeat: ROW, convert: "fxSource" }),
    r("fx.map.chain", l("Ziel", "Target"), 0x13, { repeat: ROW, convert: "fxChain" }),
    r("fx.map.param", l("Parameter"), 0x14, { repeat: ROW, convert: "plain", range: [0, 23] }),
    r("fx.map.low", l("Von", "From"), 0x16, { repeat: ROW, convert: "plain", range: [0, 127] }),
    r("fx.map.high", l("Bis", "To"), 0x18, { repeat: ROW, convert: "plain", range: [0, 127] }),
    r("fx.map.byte3", l("Zeile, Byte 3", "Row, byte 3"), 0x15, { repeat: ROW, edit: "expert", source: "unknown", evidence: undefined }),
    r("fx.map.byte5", l("Zeile, Byte 5", "Row, byte 5"), 0x17, { repeat: ROW, edit: "expert", source: "unknown", evidence: undefined }),
    r("fx.map.unknown", l("Zeile, unbekannte Bytes", "Row, unknown bytes"), 0x19, { repeat: ROW, type: "bytes:21", edit: "expert", source: "unknown", evidence: undefined,
      note: "21 der 28 Bytes einer Zeile sind nicht entschlüsselt. Ein Record aus Nullen wählt sich aus und bleibt stumm." }),
    r("fx.stage.device", l("Baustein", "Unit"), 0x12a, { repeat: STAGE, convert: "fxDevice", edit: "expert",
      note: "Ein Baustein wird nie einzeln getauscht, sondern mit seinem ganzen Stufenblock aus einem Preset übernommen, in dem er an derselben Stelle stand." }),
    r("fx.stage.unknown", l("Stufe, unbekannte Bytes", "Stage, unknown bytes"), 0x12b, { repeat: STAGE, type: "bytes:10", edit: "expert", source: "unknown", evidence: undefined }),
  ],
};
