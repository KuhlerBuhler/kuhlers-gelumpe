/**
 * Fields and tables of the firmware image, SYSTEM.VSB.
 *
 * Every address here holds for Sampler 2.02 with the Hacktribe build these
 * were measured on, and for nothing else. Offsets are file offsets; the RAM
 * address is file - 0x100 + 0xC0000000.
 */
const FIRMWARE = "sampler-2.02-hacktribe";
const FIRMWARE_STOCK = "sampler-2.02";
const RAM_WRITE = "measure:2026-09-14/fx-ram-write";
const MODS = "measure:2026-09-14/modulation-table";
const MOD_DEFAULTS = "measure:2026-10-14/offene-fragen";
const MOD_STAGE2 = "measure:2026-10-15/modulation-stufe2";
const PRESETS = "measure:2026-10-15/preset-tabellen";
const GROOVE ="derived:hacktribe-editor/extra/e2_groove_template.py";
const LAYOUT = "derived:hacktribe/firmware layout, as listed in the modding notes v3";
const l = (de, en = de) => ({ de, en });

const IFX_COUNT = [0x3f0dc, 0x98250, 0x98294, 0x981ec, 0x9819c, 0x9821c, 0x98238];
const IFX_LAST = [0x49080, 0x49ff0, 0x4a2f8, 0x9824c, 0x98288, 0x981e8];

const firmware = {
  block: "firmware",
  // A RAM image of 2 MB behind a 0x100 header, measured on every SYSTEM.VSB at hand.
  size: 0x200100,
  firmware: FIRMWARE,
  label: l("Firmware"),
  fields: [
    {
      id: "menu.ifxCount", label: l("Einträge im Insert-Menü", "Insert menu entries"), area: "menus",
      sites: [
        ...IFX_COUNT.map(file => ({ file, value: "count" })),
        ...IFX_LAST.map(file => ({ file, value: "count - 1" })),
      ],
      type: "u8", transport: ["ram", "firmware"], firmware: FIRMWARE, convert: "plain", range: [1, 100],
      source: "measured", evidence: RAM_WRITE,
    },
    {
      id: "menu.mfxCount", label: l("Einträge im Master-Menü", "Master menu entries"), area: "menus",
      instruction: { expected: 0xe3a00032, mask: 0xffffff00, range: [1, 100], evidence: "measure:2026-10-08/geraeteprotokoll" },
      where: { offset: 0x3f0e4 }, type: "u8", transport: ["ram", "firmware"], firmware: FIRMWARE,
      convert: "plain", range: [1, 100], source: "measured", evidence: RAM_WRITE,
    },
    {
      id: "splash", label: l("Startbild", "Splash screen"), area: "splash",
      where: { offset: 0xf9954 }, type: "bitmap:128x64", transport: ["firmware"], firmware: FIRMWARE,
      edit: "expert", source: "measured", evidence: "measure:2026-10-10/startphase",
      note: "8 Seiten zu 128 Spalten, Bit 7 oben; gezeichnet vor allen Rettungswegen",
    },
    {
      id: "crc16", label: l("CRC16-Tabelle", "CRC16 table"), area: "firmware",
      where: { offset: 0xa7850 }, type: "bytes:512", transport: [], firmware: FIRMWARE,
      edit: "readonly", source: "derived", evidence: LAYOUT,
    },
  ],
  // How the firmware finds an FX preset, in every build: a getter reads a pointer from an array and clamps the index
  // (`clamp`, the `movhs r0, #n` behind the compare). `literal` holds the array's address. The records are not in one run
  // in Korg's own build, so no `tables` entry describes them; the array does. `reserve` is the room the BLECH patch
  // preset-tables leaves for records beyond the firmware's 100 (tools/patch/preset_tables.py).
  pointerTables: [
    {
      id: "presets.ifx", label: l("Insert-Presets über Zeiger", "Insert presets by pointer"), block: "fxRecord", kind: "ifx",
      getter: { literal: 0xc003e74c, clamp: 0xc003e740 },
      arrays: [
        // `records`: where Korg's build keeps the records of both kinds, 200 of them, in three runs of 0x20c bytes each
        // (the two arrays and the code between them interrupt the run); the editor writes live only into these.
        { build: "stock", ram: 0xc00adf94, count: 100, firmware: FIRMWARE_STOCK,
          records: [{ ram: 0xc00a7f60, count: 47 }, { ram: 0xc00ae124, count: 9 }, { ram: 0xc00af520, count: 144 }] },
        { build: "hacktribe", ram: 0xc00a7f60, count: 100, firmware: FIRMWARE },
        { build: "blech", ram: 0xc017c000, count: 128, firmware: "sampler-2.02 + BLECH preset-tables" },
      ],
      reserve: { ram: 0xc0174000, slots: 28, first: 101 },
      transport: ["firmware"], source: "measured", evidence: PRESETS,
    },
    {
      id: "presets.mfx", label: l("Master-Presets über Zeiger", "Master presets by pointer"), block: "fxRecord", kind: "mfx",
      getter: { literal: 0xc003e764, clamp: 0xc003e758 },
      arrays: [
        { build: "stock", ram: 0xc00af390, count: 100, firmware: FIRMWARE_STOCK },
        { build: "hacktribe", ram: 0xc00b4da0, count: 100, firmware: FIRMWARE },
        { build: "blech", ram: 0xc017c200, count: 128, firmware: "sampler-2.02 + BLECH preset-tables" },
      ],
      reserve: { ram: 0xc0178000, slots: 28, first: 101 },
      transport: ["firmware"], source: "measured", evidence: PRESETS,
    },
  ],
  tables: [
    { id: "table.mfx", label: l("Master-Effekte", "Master effects"), block: "fxRecord", file: 0xb5030, count: 100, stride: 0x20c, kind: "mfx",
      transport: ["ram", "firmware"], firmware: FIRMWARE, source: "measured", evidence: RAM_WRITE },
    { id: "table.ifx", label: l("Insert-Effekte", "Insert effects"), block: "fxRecord", file: 0xa81f0, count: 100, stride: 0x20c, kind: "ifx",
      transport: ["ram", "firmware"], firmware: FIRMWARE, source: "measured", evidence: RAM_WRITE },
    { id: "table.groove", label: l("Groove-Templates"), block: "groove", file: 0x143c00, count: 96, stride: 0x140,
      transport: ["ram", "firmware"], firmware: FIRMWARE, source: "derived", evidence: GROOVE,
      note: "hacktribe-editor lässt 96 Plätze zu, ältere Notizen nennen 128; bis das am Gerät geklärt ist, gilt 96" },
    // Hacktribe's firmware reads this copy (the table readers load 0xc01a0000, the start of its names, from two literals in the
    // code); the copy at 0xd82ec below is what Korg's stock firmware reads and stays as dead data in the Hacktribe build.
    // `locate` says how to tell which copy a given image reads: the aligned code words that point at the names of an entry 0.
    { id: "table.modType", label: l("Modulationsarten", "Modulation types"), block: "modType", file: 0x1a00fc, count: 72, stride: 0x58,
      transport: ["firmware"], firmware: FIRMWARE, source: "measured", evidence: "factory-check:mod-table-read-copy",
      locate: { pointsAt: 4, codeEnd: 0xf9f10, flags: [0x1d, 0x1e, 0x24], others: ["table.modTypeStock"] },
      note: "die Kopie, die Hacktribes Firmware liest (Lesehaken, 2026-10-14/offene-fragen); die Firmware von Korg liest die Kopie ab 0xd82ec, siehe table.modTypeStock; welche ein Abbild liest, sagt src/modtable.mjs aus dem Zeiger im Code. Vorgabe-Speed und -Tiefe dieser Tabelle füllen beim Einschalten den Speicher je Part und Art" },
    { id: "table.modTypeStock", label: l("Modulationsarten, Korgs Kopie", "Modulation types, Korg's copy"), block: "modType", file: 0xd82ec, count: 72, stride: 0x58,
      transport: ["firmware"], firmware: FIRMWARE_STOCK, source: "measured", evidence: MODS,
      note: "dieselben Einträge, bis auf die ersten vier Bytes des ersten (Zeiger gegen 0xff); bei Korgs Firmware die gelesene, im Hacktribe-Abbild wird sie nie gelesen" },
    { id: "table.initPattern", label: l("Init-Pattern"), block: "pattern", file: 0xd0058, count: 1, stride: 0x3c00, length: 0x3c00,
      transport: ["firmware"], firmware: FIRMWARE, source: "derived", evidence: LAYOUT },
  ],
};

const groove = {
  block: "groove",
  size: 0x140,
  label: l("Groove-Template"),
  fields: [
    { id: "groove.magic", label: l("Kennung"), area: "grooves", where: { offset: 0 }, type: "bytes:4", transport: ["ram", "firmware"], edit: "readonly", source: "derived", evidence: GROOVE },
    { id: "groove.name", label: l("Name"), area: "grooves", where: { offset: 0x10 }, type: "latin1:15", transport: ["ram", "firmware"], source: "derived", evidence: GROOVE },
    { id: "groove.length", label: l("Länge in Steps", "Length in steps"), area: "grooves", where: { offset: 0x22 }, type: "u8", transport: ["ram", "firmware"], convert: "plain", range: [1, 64], edit: "expert", source: "derived", evidence: GROOVE },
    { id: "groove.offset", label: l("Versatz", "Offset"), area: "grooves", where: { offset: 0x30 }, repeat: [{ count: 64, stride: 4, label: l("Step") }], type: "u8", transport: ["ram", "firmware"], convert: "plain255", range: [0, 255], edit: "expert", source: "derived", evidence: GROOVE, note: "96 Einheiten je Step; ob vorzeichenbehaftet, ist offen" },
    { id: "groove.velocity", label: l("Velocity"), area: "grooves", where: { offset: 0x31 }, repeat: [{ count: 64, stride: 4, label: l("Step") }], type: "u8", transport: ["ram", "firmware"], convert: "plain255", range: [0, 255], edit: "expert", source: "derived", evidence: GROOVE, note: "neu angelegt 96; ob absolut oder relativ, ist offen" },
    { id: "groove.gate", label: l("Gate"), area: "grooves", where: { offset: 0x32 }, repeat: [{ count: 64, stride: 4, label: l("Step") }], type: "u8", transport: ["ram", "firmware"], convert: "plain255", range: [0, 255], edit: "expert", source: "derived", evidence: GROOVE, note: "96 heißt gebunden" },
    { id: "groove.endMagic", label: l("Endkennung", "End mark"), area: "grooves", where: { offset: 0x13c }, type: "bytes:4", transport: ["ram", "firmware"], edit: "readonly", source: "derived", evidence: GROOVE },
  ],
};

const modType = {
  block: "modType",
  size: 0x58,
  label: l("Modulationsart", "Modulation type"),
  fields: [
    { id: "modType.name", label: l("Name"), area: "modulations", where: { offset: 4 }, type: "latin1:16", transport: ["firmware"], source: "measured", evidence: MODS },
    { id: "modType.target", label: l("Ziel", "Target"), area: "modulations", where: { offset: 25 }, type: "u8", transport: ["firmware"], convert: "modTarget", range: [0, 5], source: "measured", evidence: MODS,
      note: "nur ein Etikett: die Firmware liest dieses Byte nie, die Ziele stehen je Slot ab +0x2D (measure:2026-10-15/modulation-stufe2)" },
    { id: "modType.depth", label: l("Vorgabetiefe", "Default depth"), area: "modulations", where: { offset: 26 }, type: "u8", transport: ["firmware"], convert: "plain", range: [0, 127], source: "measured", evidence: MOD_DEFAULTS,
      note: "vorher auf +27 geführt; im Emulator setzt MOD. TYPE Tiefe aus +26 und Speed aus +27 (71 von 72 Arten)" },
    { id: "modType.speed", label: l("Vorgabe-Speed", "Default speed"), area: "modulations", where: { offset: 27 }, type: "u8", transport: ["firmware"], convert: "plain", range: [0, 127], source: "measured", evidence: MOD_DEFAULTS },
    { id: "modType.curve", label: l("Kurvenform", "Curve"), area: "modulations", where: { offset: 28 }, type: "u8", transport: ["firmware"], convert: "modCurve", range: [0, 255], source: "measured", evidence: MODS,
      note: "Wellenform der LFO-Einheit: 0 Sägezahn fallend, 1 Rechteck, 2 Dreieck, 3 Sample and Hold, 4 Zufall, 5 Rechteck einpolig, 6 Sinus, 7 wie 4; ab 8 ein Index hinter die Tabelle (measure:2026-10-15/modulation-stufe2)" },
    // From +0x14 on, measured in the emulator. The firmware's own record starts at the name, so +0x00 to +0x03 of this window are the
    // end of the structure in front. Nothing here is transported yet (empty transport), the editable ones are expert only.
    { id: "modType.reserved", label: l("Frei", "Unused"), area: "modulations", where: { offset: 0x14 }, type: "bytes:5", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2,
      note: "in allen 72 Arten 0 und nie gelesen; hinter einem Namen mit 16 Zeichen ist +0x14 der Abschluss" },
    { id: "modType.sync", label: l("Phase-Reset beim Anschlag", "Phase reset at note start"), area: "modulations", where: { offset: 0x1d }, type: "u8", transport: [], convert: "plain", range: [0, 1], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "1: die LFO-Phase springt bei manchen Anschlägen auf 0 (5 bis 7 von 7, je nach Zeitpunkt), 0: bei keinem; die Bedingung ist offen" },
    { id: "modType.tempoSync", label: l("LFO-Speed als Notenwert", "LFO speed as note value"), area: "modulations", where: { offset: 0x1e }, type: "u8", transport: [], convert: "plain", range: [0, 1], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "1: MOD. SPEED wählt einen Notenschritt (Ausgang 1, Bereich +0x20 bis +0x21 gleich 1 bis 16), 0: eine freie Rate (Ausgang 0, 0 bis 127). Gehört zum Bereich in +0x20 und +0x21" },
    { id: "modType.cacheLfo", label: l("Zwischenwert LFO-Speed", "Cached LFO speed output"), area: "modulations", where: { offset: 0x1f }, type: "u8", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2,
      note: "das Ergebnis des Bereichs bei der Vorgabe-Speed (bei allen 72 Arten nachgerechnet), nie gelesen" },
    { id: "modType.rateLo", label: l("LFO-Speed von", "LFO speed from"), area: "modulations", where: { offset: 0x20 }, type: "u8", transport: [], convert: "plain", range: [0, 127], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "Wert bei MOD. SPEED 0; bei freien LFOs ein Rate-Index (0 steht, 127 rund 100 Hz), bei tempo-synchronen ein Notenschritt von 1 (16 Schläge) bis 16 (1/64), größere laufen wie 16. Größer als der obere Wert dreht den Regler um" },
    { id: "modType.rateHi", label: l("LFO-Speed bis", "LFO speed to"), area: "modulations", where: { offset: 0x21 }, type: "u8", transport: [], convert: "plain", range: [0, 127], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "Wert bei MOD. SPEED 127, 255 Stufen dazwischen; bei Hüllkurven 0 und ohne Wirkung" },
    { id: "modType.spareA", label: l("Frei", "Unused"), area: "modulations", where: { offset: 0x22 }, type: "bytes:2", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2, note: "in allen 72 Arten 0, nie gelesen" },
    { id: "modType.egTempo", label: l("EG-Zeit als Notenwert", "EG time as note value"), area: "modulations", where: { offset: 0x24 }, type: "u8", transport: [], convert: "plain", range: [0, 1], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "1: der Ausgang 2 (EG-Zeit) ist ein Notenschritt des Tempos (1 bis 16, größere Werte werden auf 16 gekürzt), 0: ein Rate-Index. Gehört zum Bereich in +0x28 und +0x29" },
    { id: "modType.cacheEg", label: l("Zwischenwert EG-Zeit", "Cached EG time output"), area: "modulations", where: { offset: 0x25 }, type: "u8", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2,
      note: "das Ergebnis des Bereichs bei der Vorgabe-Speed (bei allen 72 Arten nachgerechnet), nie gelesen" },
    { id: "modType.spareB", label: l("Frei", "Unused"), area: "modulations", where: { offset: 0x26 }, type: "bytes:2", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2, note: "in allen 72 Arten 0, nie gelesen" },
    { id: "modType.egLo", label: l("EG-Zeit von", "EG time from"), area: "modulations", where: { offset: 0x28 }, type: "u8", transport: [], convert: "plain", range: [0, 127], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "Wert bei MOD. SPEED 0; Hüllkurven 0 (frei) oder 16 (Notenschritt), bei LFOs 0 und ohne Wirkung" },
    { id: "modType.egHi", label: l("EG-Zeit bis", "EG time to"), area: "modulations", where: { offset: 0x29 }, type: "u8", transport: [], convert: "plain", range: [0, 127], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "Wert bei MOD. SPEED 127; Hüllkurven 127 (frei) oder 1 (Notenschritt), bei LFOs 0 und ohne Wirkung" },
    { id: "modType.spareC", label: l("Frei", "Unused"), area: "modulations", where: { offset: 0x2a }, type: "bytes:2", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2, note: "in allen 72 Arten 0, nie gelesen" },
    // Six slots of eight bytes from +0x2C, each one modulation. The 72 types fill slot 0 (and slot 1 for four pitch types); the others
    // work when filled. The sixth slot runs into the next window, see modType.slot6.
    { id: "modType.slot.source", label: l("Quelle", "Source"), area: "modulations", where: { offset: 0x2c }, repeat: [{ count: 5, stride: 8, label: l("Slot") }], type: "u8", transport: [], convert: "modSlotSource", range: [0, 2], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "0: die Hüllkurve, 1: die LFO-Einheit; jeder andere Wert schaltet den Slot aus (2, 3 und 255 gemessen), der Editor schreibt 2" },
    { id: "modType.slot.target", label: l("Ziel", "Target"), area: "modulations", where: { offset: 0x2d }, repeat: [{ count: 5, stride: 8, label: l("Slot") }], type: "u8", transport: [], convert: "modSlotTarget", range: [0, 10], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "1 Pitch, 2 OSC, 3 Filter, 8 Level, 9 Pan, 10 IFX, 0 nichts. 4 bis 7 wirken ebenfalls (die Arten nutzen sie nicht), 11 und mehr tun nichts" },
    { id: "modType.slot.cache", label: l("Zwischenwert", "Cached value"), area: "modulations", where: { offset: 0x2e }, repeat: [{ count: 5, stride: 8, label: l("Slot") }], type: "u8", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2,
      note: "die Stärke bei der Vorgabetiefe (bei negativen Bereichen bei der gespiegelten Tiefe), nie gelesen" },
    { id: "modType.slot.lo", label: l("Stärke von", "Strength from"), area: "modulations", where: { offset: 0x2f }, repeat: [{ count: 5, stride: 8, label: l("Slot") }], type: "s8", transport: [], convert: "signed8", range: [-63, 63], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "Stärke bei MOD. DEPTH 0; ein Wert unter 0 bei einem oberen Wert über 0 macht den Bereich 0 bis 63, was auch immer beide Werte sind" },
    { id: "modType.slot.hi", label: l("Stärke bis", "Strength to"), area: "modulations", where: { offset: 0x30 }, repeat: [{ count: 5, stride: 8, label: l("Slot") }], type: "s8", transport: [], convert: "signed8", range: [-63, 63], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "Stärke bei MOD. DEPTH 127; 0 oder kleiner macht die Stärke negativ (von und bis spiegeln sich), über 63 wird auf 63 gekürzt" },
    { id: "modType.slot.follow", label: l("Tiefe folgt MOD. DEPTH", "Depth follows MOD. DEPTH"), area: "modulations", where: { offset: 0x31 }, repeat: [{ count: 5, stride: 8, label: l("Slot") }], type: "u8", transport: [], convert: "onOff", range: [0, 1], edit: "expert", source: "measured", evidence: MOD_STAGE2,
      note: "ungleich 0: die Stärke folgt MOD. DEPTH (bei allen 72 Arten der Fall); 0: sie bleibt auf der Vorgabetiefe der Art (+0x1A)" },
    { id: "modType.slot.spare", label: l("Frei", "Unused"), area: "modulations", where: { offset: 0x32 }, repeat: [{ count: 5, stride: 8, label: l("Slot") }], type: "bytes:2", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2, note: "in allen 72 Arten 0, nie gelesen" },
    { id: "modType.slot6", label: l("Sechster Slot, erste vier Byte", "Sixth slot, first four bytes"), area: "modulations", where: { offset: 0x54 }, type: "bytes:4", transport: [], edit: "readonly", source: "measured", evidence: MOD_STAGE2,
      note: "Quelle, Ziel, Zwischenwert und Stärke von; Stärke bis, Merker und die zwei freien Bytes liegen in den ersten vier Bytes des nächsten Fensters (Art + 1, bei Art 71 hinter der Tabelle). Keine Art nutzt den Slot, mit gesetzten Bytes wirkt er" },
  ],
};

export default [firmware, groove, modType];
