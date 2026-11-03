// Filter Toggle, an app under TOOLS: SHIFT + LPF, HPF or BPF turns the filter of the selected part off, and the same
// combination turns it on again with the type that key had last, kept per part and key until power off. SHIFT and another
// filter key goes straight to that key's last type. The plain filter keys stay with the firmware and its cycling.
// While the app is open the firmware never sees SHIFT and a filter key (korg.passKeys, every other key passes); while it is
// closed the firmware turns the type first and the plugin sets the right one in the next frame.
// Types: 0 OFF, 1 to 6 the LPF family, 7 to 11 HPF, 12 to 16 BPF.
korg.app("Filter Toggle", "TOOLS");
const FIRST = [1, 7, 12];
const last = new Array(48);
let shift = 0;
let before = 0;
let isOpen = 0;
let shownPart = -1;
let shownType = -1;

function family(type) {
  if (type >= 12) return 2;
  if (type >= 7) return 1;
  if (type >= 1) return 0;
  return -1;
}

function keyFamily(key) {
  if (key == 18) return 0;
  if (key == 20) return 1;
  if (key == 22) return 2;
  return -1;
}

function remember(part, type) {
  let f = family(type);
  if (f >= 0) last[part * 3 + f] = type;
}

function holdFilters(hold) {
  korg.passKeys(18, 1 - hold);
  korg.passKeys(20, 1 - hold);
  korg.passKeys(22, 1 - hold);
}

function toggle(part, f) {
  let type = 0;
  if (family(before) != f) type = last[part * 3 + f];
  if (family(before) != f && type == 0) type = FIRST[f];
  korg.parts[part].filterType = type;
  before = type;
}

// The model names as the firmware lists them; HPF and BPF have no MG.
function typeName(type, y) {
  let f = family(type);
  if (f < 0) { korg.display.text("OFF", 4, y); return; }
  if (f == 0) korg.display.text("LPF", 4, y);
  if (f == 1) korg.display.text("HPF", 4, y);
  if (f == 2) korg.display.text("BPF", 4, y);
  let model = type - FIRST[f];
  if (f > 0 && model >= 2) model += 1;
  if (model == 0) korg.display.text("electribe", 28, y);
  if (model == 1) korg.display.text("MS20", 28, y);
  if (model == 2) korg.display.text("MG", 28, y);
  if (model == 3) korg.display.text("P5", 28, y);
  if (model == 4) korg.display.text("OB", 28, y);
  if (model == 5) korg.display.text("Acid", 28, y);
}

function draw(part, type) {
  korg.display.clear();
  korg.display.text("Filter Toggle", 4, 2);
  if (part < 16) korg.display.textNumber("Part ", part + 1, 4, 20);
  else korg.display.text("all parts", 4, 20);
  if (part < 16) typeName(type, 32);
  korg.display.text("SHIFT+LPF/HPF/BPF", 4, 55);
}

korg.onEvent("open", () => {
  isOpen = 1;
  for (let key = 0; key < 34; key++) korg.passKeys(key, 1);
  holdFilters(shift);
  shownPart = -1;
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("frame", () => {
  let part = korg.selectedPart;
  let type = 0;
  if (part < 16) type = korg.parts[part].filterType;
  if (part < 16) remember(part, type);
  if (part != shownPart || type != shownType) draw(part, type);
  shownPart = part;
  shownType = type;
});

korg.onEvent("partChange", (part) => {
  if (shift && part < 16) before = korg.parts[part].filterType;
});

korg.onEvent("buttonPress", (key) => {
  let part = korg.selectedPart;
  if (key == 10) {
    shift = 1;
    if (isOpen) holdFilters(1);
    if (part < 16) before = korg.parts[part].filterType;
    if (part < 16) remember(part, before);
    return;
  }
  let f = keyFamily(key);
  if (shift && f >= 0 && part < 16) toggle(part, f);
});

korg.onEvent("buttonRelease", (key) => {
  let part = korg.selectedPart;
  if (key == 10) {
    shift = 0;
    if (isOpen) holdFilters(0);
    return;
  }
  if (!shift && keyFamily(key) >= 0 && part < 16) remember(part, korg.parts[part].filterType);
});
