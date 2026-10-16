/**
 * What the device shows right now: the screen manager and the current
 * screen. Both live on the heap and are reached through a pointer, so a
 * block here has no file offset, only `meta.pointer`: read the word at `at`,
 * then for each offset in `then` add it and read the word there.
 */
const FIRMWARE = "sampler-2.02-hacktribe";
const MEASURE = "measure:2026-10-09/menuezustand";
const l = (de, en = de) => ({ de, en });
const AT = 0xc03404c0;

const f = (id, label, offset, rest = {}) => ({
  id, label, area: "screen", where: { offset }, type: "u32le", transport: ["ram"],
  edit: "readonly", source: "measured", evidence: MEASURE, ...rest,
});

/** Screen numbers at manager + 0x2C; `pages` names the values of screen + 0x2C. */
const MODES = {
  1: { de: "Hauptbildschirm", en: "Main screen" },
  3: { de: "Menü Pattern", en: "Pattern menu", pages: ["BPM", "SWING", "BEAT", "LENGTH", "PATTERN LEVEL", "MFX TYPE", "CLEAR MFX MOTION", "KEY", "SCALE", "CHORD SET", "GATE ARP", "ALTERNATE 13-14", "ALTERNATE 15-16", "CHAIN TO", "CHAIN REPEAT"] },
  7: { de: "Menü Part", en: "Part menu", pages: ["LAST STEP", "GROOVE TYPE", "GROOVE DEPTH", "VOICE ASSIGN", "PART PRIORITY", "MOTION SEQ", "TRG. PAD VELOCITY", "SCALE MODE"] },
  8: { de: "Menü Global", en: "Global menu" },
  10: { de: "Menü Event", en: "Event menu" },
  14: { de: "Menü Data Util", en: "Data utility menu" },
  18: { de: "Name eingeben", en: "Enter name" },
  19: { de: "Menü Step", en: "Step menu" },
  21: { de: "Menü Part Util", en: "Part utility menu" },
  37: { de: "Menü Sample", en: "Sample menu" },
};

/** Window kinds at manager + 0x30 while manager + 0x24 is set. */
const OVERLAYS = { 23: { de: "IFX TYPE", en: "IFX TYPE" } };

/** Screens that show an effect: the pattern's master effect, or the selected part's insert. */
const EFFECTS = [
  { mode: 3, page: 5, kind: "mfx", field: "pattern.mfx.type" },
  { overlay: 23, kind: "ifx", field: "part.ifxType" },
];

export default [
  {
    block: "screenManager",
    size: 0x34,
    firmware: FIRMWARE,
    label: l("Bildschirm-Verwalter", "Screen manager"),
    meta: { pointer: { at: AT, then: [] }, modes: MODES, overlays: OVERLAYS, effects: EFFECTS },
    fields: [
      f("screen.current", l("Aktueller Bildschirm", "Current screen"), 0x20, { note: "Zeiger" }),
      f("screen.overlay", l("Eingeblendetes Fenster", "Overlay window"), 0x24, { note: "Zeiger, 0 ohne Fenster" }),
      f("screen.mode", l("Bildschirm", "Screen"), 0x2c),
      f("screen.overlayKind", l("Art des Fensters", "Window kind"), 0x30),
    ],
  },
  {
    block: "display",
    size: 1024,
    firmware: FIRMWARE,
    label: l("Displaybild", "Display image"),
    meta: { ram: 0xc031b310 },
    fields: [
      f("display.image", l("Bild", "Image"), 0, { type: "bytes:1024", note: "8 Seiten zu 128 Spalten, Bit 0 oben; am Gerät ungeprüft" }),
    ],
  },
  {
    block: "editState",
    size: 0x18,
    firmware: FIRMWARE,
    label: l("Bearbeitungsstand", "Edit state"),
    meta: { pointer: { at: 0xc0348880, then: [] } },
    fields: [
      f("edit.part", l("Gewählter Part", "Selected part"), 0x14, { note: "0 bis 15" }),
    ],
  },
  {
    block: "ledState",
    size: 0x4b * 8 + 3,
    firmware: FIRMWARE,
    label: l("LED-Zustand", "LED state"),
    // The four RGB lights (0x4c and up) are left out: the front drawing has none.
    meta: { pointer: { at: 0xc0345a1c, then: [] }, offset: 0x88c, stride: 8, count: 0x4c, brightness: 2 },
    fields: [
      f("led.sent", l("Zuletzt gesendete LEDs", "LEDs as last sent"), 0, { type: "bytes:603", evidence: "measure:2026-10-14/led-zustand-ram", note: "je LED 8 Byte, Byte 0 Nummer, Byte 2 Helligkeit" }),
    ],
  },
  {
    block: "screen",
    size: 0x30,
    firmware: FIRMWARE,
    label: l("Aktueller Bildschirm", "Current screen"),
    meta: { pointer: { at: AT, then: [0x20] } },
    fields: [
      f("screen.class", l("Klasse", "Class"), 0x00, { note: "vtable-Zeiger" }),
      f("screen.page", l("Menüseite", "Menu page"), 0x2c, { note: "zählt nur in den Menüs Pattern und Part" }),
    ],
  },
];
