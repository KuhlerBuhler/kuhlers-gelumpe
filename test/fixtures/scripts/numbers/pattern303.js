// 303Pattern: generator (14 scales, accent / slide / tie), step locks, in-app menu
// writes to the sequencer and lights the pads of the steps with a note
korg.app("303Pattern", "TOOLS");

const CLEAR_FIRST = 0;  // 1 = always clearPart() before writing
                        // 0 = only after the density changed
const VEL = 100;        // velocity of a normal step
const VEL_ACC = 127;    // velocity of an accented step
const KNOB_GATE = 8;    // index of the decay knob (by the docs' knob order)
const DEBUG_KNOB = 0;   // 1 = show the index of the knob you turn, set back to 0 when done
const BOXES = 4;        // boxes drawn per frame (1, 2, 4 or 8); lower it if FUEL comes back
const NIT = 9;          // items in the in-app menu

// 14 scales x 12 semitones (1 = in scale), relative to the root
// 0 chromatic, 1 major, 2 nat minor, 3 harm minor, 4 dorian, 5 phrygian,
// 6 lydian, 7 mixolydian, 8 locrian, 9 min pent, 10 maj pent, 11 blues,
// 12 goa (phrygian dominant), 13 whole tone
const mask = [1,1,1,1,1,1,1,1,1,1,1,1,
              1,0,1,0,1,1,0,1,0,1,0,1,
              1,0,1,1,0,1,0,1,1,0,1,0,
              1,0,1,1,0,1,0,1,1,0,0,1,
              1,0,1,1,0,1,0,1,0,1,1,0,
              1,1,0,1,0,1,0,1,1,0,1,0,
              1,0,1,0,1,0,1,1,0,1,0,1,
              1,0,1,0,1,1,0,1,0,1,1,0,
              1,1,0,1,0,1,1,0,1,0,1,0,
              1,0,0,1,0,1,0,1,0,0,1,0,
              1,0,1,0,1,0,0,1,0,1,0,0,
              1,0,0,1,0,1,1,1,0,0,1,0,
              1,1,0,0,1,1,0,1,1,0,1,0,
              1,0,1,0,1,0,1,0,1,0,1,0];
const wt = [100,100,100,100,100,100,100,100,100,100,100,100];

// the notes of the current scale, built once per generation
const deg = new Array(12);
let ndeg = 0;
let total = 0;

// the 16 steps: pitch row (0-11), octave window (1-3), flags
const row = new Array(16);
const win = new Array(16);
const gate = new Array(16);
const acc = new Array(16);
const sld = new Array(16);
const tie = new Array(16);
const lock = new Array(16);  // 1 = step is locked, generation leaves it alone
const lit = new Array(16);   // pad LED state last sent: 0 off, 1 red, 2 blue, 3 dim blue, 9 unknown

let sc = 12;
let root = 6;      // F#
let dens = 100;    // percent chance that a step has a note
let slidePc = 25;
let tiePc = 0;
let accPc = 2;
let gateOn = 48;   // gate time 1-96, default until the knob is moved
let autoWrite = 0; // 1 = every new pattern is written at once, 0 = key 3 writes
let needClear = 0; // 1 = density changed since the last write
let seed = 1;
let pos = 0;
let isOpen = 0;
let drawIdx = 20;  // 0-15 next box, 16 = bottom line, 20 = nothing to draw
let ledIdx = 16;   // 0 or 8 = next group of 8 pads to send, 16 = nothing to send
let written = 0;   // 1 = the sequencer holds the pattern shown
let menuOn = 0;    // 1 = the in-app menu is shown
let menuDirty = 0; // 1 = the menu needs redrawing
let msel = 0;      // selected menu item
let mtop = 0;      // first visible menu item

let mScale = korg.menu.add("SCALE 0-13", 0, 13, 12);
let mRoot = korg.menu.add("ROOT 0-11", 0, 11, 6);
let mDens = korg.menu.add("DENS 0-100", 0, 100, 100);
let mSlide = korg.menu.add("SLIDE 0-100", 0, 100, 25);
let mTie = korg.menu.add("TIE 0-100", 0, 100, 0);
let mAcc = korg.menu.add("ACCENT 0-100", 0, 100, 2);

function rnd(n) {
  seed = seed * 1103515245 + 12345;
  // multiply-and-shift instead of % n: same range 0..n-1, no division
  return (((seed >> 16) & 0x7FFF) * n) >> 15;
}

function clamp(v, lo, hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

function buildScale() {
  ndeg = 0;
  total = 0;
  let k = 0;
  while (k < 12) {
    if (mask[sc * 12 + k] == 1) {
      deg[ndeg] = k;
      ndeg += 1;
      total += wt[k];
    }
    k += 1;
  }
}

// weighted pick of a pitch row from the scale, then the octave:
// 70% window 2, 15% window 1, 15% window 3
function pickPitch(i) {
  let r = rnd(total);
  let k = 0;
  while (k < ndeg - 1) {
    let w = wt[deg[k]];
    if (r < w) break;
    r -= w;
    k += 1;
  }
  row[i] = deg[k];
  let o = rnd(100);
  win[i] = 2;
  if (o >= 70) win[i] = 1;
  if (o >= 85) win[i] = 3;
}

// a tie needs a gate on the step before and takes over its pitch
// (locked steps are never touched)
function fixTies() {
  let i = 0;
  while (i < 16) {
    if (tie[i] == 1 && lock[i] == 0) {
      if (i == 0) tie[i] = 0;
      else if (gate[i - 1] == 0) tie[i] = 0;
      else { row[i] = row[i - 1]; win[i] = win[i - 1]; }
    }
    i += 1;
  }
}

// new rhythm, new notes, new flags (one pass over the unlocked steps)
function generate() {
  seed = korg.millis() + 1;
  buildScale();
  let i = 0;
  while (i < 16) {
    if (lock[i] == 0) {
      gate[i] = 0;
      acc[i] = 0;
      sld[i] = 0;
      tie[i] = 0;
      row[i] = 0;
      win[i] = 2;
      if (rnd(100) < dens) {
        gate[i] = 1;
        pickPitch(i);
        if (rnd(100) < accPc) acc[i] = 1;
        if (i < 15) {
          if (rnd(100) < slidePc) sld[i] = 1;
        }
        if (i > 0 && tiePc > 0) {
          if (gate[i - 1] == 1) {
            if (rnd(100) < tiePc) tie[i] = 1;
          }
        }
      }
    }
    i += 1;
  }
  fixTies();
  written = 0;
  drawIdx = 0;
  ledIdx = 0;
}

// new notes, same rhythm (locked steps keep theirs)
function randomizeNotes() {
  seed = korg.millis() + 1;
  buildScale();
  let has = 0;
  let i = 0;
  while (i < 16) {
    if (gate[i] == 1) has = 1;
    i += 1;
  }
  if (has == 0) {
    i = 0;
    while (i < 16) {
      if (lock[i] == 0) {
        if (rnd(100) < dens) gate[i] = 1;
      }
      i += 1;
    }
  }
  i = 0;
  while (i < 16) {
    if (gate[i] == 1 && tie[i] == 0 && lock[i] == 0) pickPitch(i);
    i += 1;
  }
  fixTies();
  written = 0;
  drawIdx = 0;
  ledIdx = 0;
}

// moves the root and keeps the absolute pitch of the locked notes
function setRoot(r) {
  let d = root - r;
  let i = 0;
  while (i < 16) {
    if (lock[i] == 1) {
      let q = row[i] + d;
      let w = win[i];
      if (q < 0) { q += 12; w -= 1; }
      if (q > 11) { q -= 12; w += 1; }
      row[i] = q;
      win[i] = w;
    }
    i += 1;
  }
  root = r;
}

function unlockAll() {
  let i = 0;
  while (i < 16) {
    lock[i] = 0;
    i += 1;
  }
  drawIdx = 0;
  ledIdx = 0;
}

// gate time of step i: the knob value, or a full gate when the next step is tied
function gateFor(i) {
  let g = gateOn;
  if (i < 15) {
    if (tie[i + 1] == 1) g = 96;
  }
  return g;
}

// writes the 16 generated steps into the selected part;
// the part is cleared first when the density changed since the last write
function writeAll() {
  let part = korg.read.part();
  if (part > 15) part = 0;    // "all parts" (16) is not a part
  if (CLEAR_FIRST == 1 || needClear == 1) korg.seq.clearPart(part);
  needClear = 0;
  let i = 0;
  while (i < 16) {
    if (gate[i] == 1) {
      let note = 12 * (win[i] + 1) + root + row[i];
      let vel = VEL;
      if (acc[i] == 1) vel = VEL_ACC;
      korg.seq.setStep(part, i, note, vel);
      korg.seq.setGate(part, i, gateFor(i));
    } else {
      korg.seq.setGate(part, i, 0);
    }
    i += 1;
  }
  written = 1;
}

// only the gate times, for the knob: notes and velocities stay as they are
function writeGates() {
  let part = korg.read.part();
  if (part > 15) part = 0;
  let i = 0;
  while (i < 16) {
    if (gate[i] == 1) korg.seq.setGate(part, i, gateFor(i));
    i += 1;
  }
}

function regen() {
  generate();
  if (autoWrite == 1) writeAll();
}

function regenNotes() {
  randomizeNotes();
  if (autoWrite == 1) writeAll();
}

function scaleName(x, y) {
  if (sc == 0) korg.display.text("CHROMATIC", x, y);
  else if (sc == 1) korg.display.text("MAJOR", x, y);
  else if (sc == 2) korg.display.text("NAT MINOR", x, y);
  else if (sc == 3) korg.display.text("HARM MINOR", x, y);
  else if (sc == 4) korg.display.text("DORIAN", x, y);
  else if (sc == 5) korg.display.text("PHRYGIAN", x, y);
  else if (sc == 6) korg.display.text("LYDIAN", x, y);
  else if (sc == 7) korg.display.text("MIXOLYDIAN", x, y);
  else if (sc == 8) korg.display.text("LOCRIAN", x, y);
  else if (sc == 9) korg.display.text("MIN PENT", x, y);
  else if (sc == 10) korg.display.text("MAJ PENT", x, y);
  else if (sc == 11) korg.display.text("BLUES", x, y);
  else if (sc == 12) korg.display.text("GOA", x, y);
  else korg.display.text("WHOLE TONE", x, y);
}

function rootName(x, y) {
  if (root == 0) korg.display.text("C", x, y);
  else if (root == 1) korg.display.text("C#", x, y);
  else if (root == 2) korg.display.text("D", x, y);
  else if (root == 3) korg.display.text("D#", x, y);
  else if (root == 4) korg.display.text("E", x, y);
  else if (root == 5) korg.display.text("F", x, y);
  else if (root == 6) korg.display.text("F#", x, y);
  else if (root == 7) korg.display.text("G", x, y);
  else if (root == 8) korg.display.text("G#", x, y);
  else if (root == 9) korg.display.text("A", x, y);
  else if (root == 10) korg.display.text("A#", x, y);
  else korg.display.text("B", x, y);
}

// note name without octave, centred in a 15 px box
function pcName(p, bx, y) {
  if (p == 0) korg.display.text("C", bx + 5, y);
  else if (p == 1) korg.display.text("C#", bx + 2, y);
  else if (p == 2) korg.display.text("D", bx + 5, y);
  else if (p == 3) korg.display.text("D#", bx + 2, y);
  else if (p == 4) korg.display.text("E", bx + 5, y);
  else if (p == 5) korg.display.text("F", bx + 5, y);
  else if (p == 6) korg.display.text("F#", bx + 2, y);
  else if (p == 7) korg.display.text("G", bx + 5, y);
  else if (p == 8) korg.display.text("G#", bx + 2, y);
  else if (p == 9) korg.display.text("A", bx + 5, y);
  else if (p == 10) korg.display.text("A#", bx + 2, y);
  else korg.display.text("B", bx + 5, y);
}

// pad LEDs of 8 steps, only the ones that changed (max 16 packets):
// unlocked note = red, locked note = blue, locked rest = dim blue
function ledPads(a) {
  let i = a;
  while (i < a + 8) {
    let want = gate[i];
    if (lock[i] == 1) {
      if (gate[i] == 1) want = 2;
      else want = 3;
    }
    if (lit[i] != want) {
      lit[i] = want;
      let r = 0;
      if (want == 1) r = 255;
      let b = 0;
      if (want == 2) b = 255;
      if (want == 3) b = 40;
      korg.led(44 + 2 * i, r);
      korg.led(45 + 2 * i, b);
    }
    i += 1;
  }
}

// one step as a 15 x 20 box: note name on top, octave number below.
// locked = bold top and bottom edge, accent = block left of the octave,
// slide = block right of it, tie = mark in the gap to the left
function drawBox(i) {
  let bx = (i % 8) * 16;
  let by = 10;
  if (i >= 8) by = 32;
  if (gate[i] == 1 || lock[i] == 1) {
    korg.display.rect(bx, by, 15, 20);
    korg.display.clearRect(bx + 1, by + 1, 13, 18);
    if (lock[i] == 1) {
      korg.display.rect(bx, by, 15, 2);
      korg.display.rect(bx, by + 18, 15, 2);
    }
  }
  if (gate[i] == 1) {
    let n = 12 * (win[i] + 1) + root + row[i];
    pcName(n % 12, bx, by + 3);
    korg.display.number(n / 12 - 1, bx + 5, by + 11);
    if (acc[i] == 1) korg.display.rect(bx + 1, by + 13, 3, 4);
    if (sld[i] == 1) korg.display.rect(bx + 11, by + 15, 3, 2);
    if (tie[i] == 1 && i % 8 > 0) korg.display.rect(bx - 1, by + 9, 1, 2);
  } else {
    korg.display.rect(bx + 5, by + 9, 5, 2);
  }
}

// one box on its own, after a lock change
function redrawBox(i) {
  let bx = (i % 8) * 16;
  let by = 10;
  if (i >= 8) by = 32;
  korg.display.clearRect(bx, by, 15, 20);
  drawBox(i);
}

// the moving part: just the playhead bar (3 display calls)
function drawHead() {
  korg.display.clearRect(0, 30, 128, 2);
  korg.display.clearRect(0, 52, 128, 2);
  let bx = (pos % 8) * 16;
  if (pos < 8) korg.display.rect(bx, 30, 15, 2);
  else korg.display.rect(bx, 52, 15, 2);
}

function drawTop() {
  korg.display.clear();
  scaleName(4, 1);
  korg.display.text("ROOT", 70, 1);
  rootName(100, 1);
}

function drawBottom() {
  korg.display.textNumber("DENS ", dens, 4, 55);
  korg.display.text("TAP", 105, 55);
  drawHead();
}

// ---- in-app menu ----

function menuLabel(it, y) {
  if (it == 0) korg.display.text("SCALE", 12, y);
  else if (it == 1) korg.display.text("ROOT", 12, y);
  else if (it == 2) korg.display.text("DENS", 12, y);
  else if (it == 3) korg.display.text("SLIDE", 12, y);
  else if (it == 4) korg.display.text("TIE", 12, y);
  else if (it == 5) korg.display.text("ACCENT", 12, y);
  else if (it == 6) korg.display.text("GATE", 12, y);
  else if (it == 7) korg.display.text("AUTO", 12, y);
  else korg.display.text("UNLOCK", 12, y);
}

function menuValue(it, y) {
  if (it == 0) scaleName(54, y);
  else if (it == 1) rootName(54, y);
  else if (it == 2) korg.display.number(dens, 54, y);
  else if (it == 3) korg.display.number(slidePc, 54, y);
  else if (it == 4) korg.display.number(tiePc, 54, y);
  else if (it == 5) korg.display.number(accPc, 54, y);
  else if (it == 6) korg.display.number(gateOn, 54, y);
  else if (it == 7) {
    if (autoWrite == 1) korg.display.text("ON", 54, y);
    else korg.display.text("OFF", 54, y);
  } else korg.display.text("TAP", 54, y);
}

function drawMenu() {
  menuDirty = 0;
  korg.display.clear();
  korg.display.text("303 MENU", 4, 1);
  korg.display.text("MENU=BACK", 66, 1);
  let r = 0;
  while (r < 5) {
    let it = mtop + r;
    let y = 12 + 9 * r;
    if (it < NIT) {
      if (it == msel) korg.display.text(">", 4, y);
      menuLabel(it, y);
      menuValue(it, y);
    }
    r += 1;
  }
  // scrollbar (sized for 9 items, 5 visible)
  korg.display.rect(127, 12, 1, 43);
  korg.display.rect(125, 12 + 5 * mtop, 3, 23);
}

// d = -1 or +1
function menuAdjust(d) {
  if (msel == 0) { sc = (sc + 14 + d) % 14; regen(); }
  else if (msel == 1) { setRoot((root + 12 + d) % 12); regen(); }
  else if (msel == 2) { dens = clamp(dens + 5 * d, 0, 100); needClear = 1; regen(); }
  else if (msel == 3) { slidePc = clamp(slidePc + 5 * d, 0, 100); regen(); }
  else if (msel == 4) { tiePc = clamp(tiePc + 5 * d, 0, 100); regen(); }
  else if (msel == 5) { accPc = clamp(accPc + d, 0, 100); regen(); }
  else if (msel == 6) {
    gateOn = clamp(gateOn + 4 * d, 1, 96);
    if (written == 1) writeGates();
  }
  else if (msel == 7) autoWrite = 1 - autoWrite;
}

// ---- events ----

// all steps start unlocked
korg.onEvent("ready", () => {
  let i = 0;
  while (i < 16) {
    lock[i] = 0;
    i += 1;
  }
});

// the BLECH menu pages only preview, they never write
korg.onEvent("menu", (id, value) => {
  if (id == mScale) sc = value;
  if (id == mRoot) setRoot(value);
  if (id == mDens) { dens = value; needClear = 1; }
  if (id == mSlide) slidePc = value;
  if (id == mTie) tiePc = value;
  if (id == mAcc) accPc = value;
  generate();
});

// while the app is open it owns the panel LEDs
korg.onEvent("open", () => {
  isOpen = 1;
  menuOn = 0;
  menuDirty = 0;
  msel = 0;
  mtop = 0;
  korg.ledHold(1);
  let i = 0;
  while (i < 16) {
    lit[i] = 9;      // unknown, so all 16 pads are sent once
    i += 1;
  }
  generate();
});

korg.onEvent("close", () => {
  isOpen = 0;
  menuOn = 0;
  korg.ledHold(0);
});

// pressing a pad locks or unlocks that step
korg.onEvent("pad", (index, down) => {
  if (isOpen == 1 && menuOn == 0 && down == 1 && index < 16) {
    lock[index] = 1 - lock[index];
    redrawBox(index);
    ledIdx = 0;
  }
});

// the menu, or the screen built over several frames (top, BOXES boxes per
// frame, bottom), then the pad LEDs, 8 pads per frame
korg.onEvent("frame", () => {
  if (isOpen == 1) {
    if (menuOn == 1) {
      if (menuDirty == 1) {
        drawMenu();
      } else if (ledIdx < 16) {
        ledPads(ledIdx);
        ledIdx += 8;
      }
    } else if (drawIdx < 20) {
      if (drawIdx == 0) drawTop();
      if (drawIdx < 16) {
        let n = 0;
        while (n < BOXES) {
          drawBox(drawIdx + n);
          n += 1;
        }
        drawIdx += BOXES;
      } else {
        drawBottom();
        drawIdx = 20;
      }
    } else if (ledIdx < 16) {
      ledPads(ledIdx);
      ledIdx += 8;
    }
  }
});

// the knob sets the gate length, 0-1023 mapped to 1-96;
// it only goes to the sequencer after the shown pattern has been written
korg.onEvent("knob", (index, value) => {
  if (DEBUG_KNOB == 1 && isOpen == 1 && menuOn == 0) {
    korg.display.clearRect(58, 55, 42, 7);
    korg.display.textNumber("KNOB ", index, 58, 55);
  }
  if (index == KNOB_GATE) {
    gateOn = 1 + value * 95 / 1023;
    if (menuOn == 1) menuDirty = 1;
    if (isOpen == 1 && written == 1) writeGates();
  }
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen == 1) {
    if (key == 9) {
      menuOn = 1 - menuOn;
      menuDirty = 1;
      if (menuOn == 0) drawIdx = 0;    // rebuild the main screen
    } else if (menuOn == 1) {
      if (key == 11) msel = (msel + NIT - 1) % NIT;
      if (key == 15) msel = (msel + 1) % NIT;
      if (key == 8) menuAdjust(-1);
      if (key == 12) menuAdjust(1);
      if (key == 3 && msel == 8) unlockAll();
      if (msel < mtop) mtop = msel;
      if (msel > mtop + 4) mtop = msel - 4;
      menuDirty = 1;
    } else {
      if (key == 3) regen();
      if (key == 31) regenNotes();
      if (key == 30) writeAll();
      if (key == 15) { sc = (sc + 1) % 14; regen(); }
      if (key == 11) { sc = (sc + 13) % 14; regen(); }
      if (key == 12) { setRoot((root + 1) % 12); regen(); }
      if (key == 8) { setRoot((root + 11) % 12); regen(); }
      if (key == 29) { dens += 10; if (dens > 100) dens = 100; needClear = 1; regen(); }
      if (key == 28) { dens -= 10; if (dens < 0) dens = 0; needClear = 1; regen(); }
    }
  }
});

korg.onEvent("step", (s) => {
  pos = s % 16;
  if (isOpen == 1 && menuOn == 0 && drawIdx == 20) drawHead();
});

