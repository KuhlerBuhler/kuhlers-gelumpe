// LIVE RELOAD v0.2 by handst0n3, from the BLECH Discord: restores the sound values of all 16 parts to the saved pattern
// without stopping playback. SHIFT + BAR 1 hard, SHIFT + BAR 2 smooth.
korg.app("LIVE RELOAD", "TOOLS");

const fields = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 18];
const before = new Array(240);
const target = new Array(240);

let opened = 0;
let shiftHeld = 0;
let running = 0;
let stage = 0;
let position = 0;
let blendFrame = 0;
let sourcePattern = -1;
let result = 0;

function isSmooth(field) {
  return field == 2 || field == 3 || field == 4 ||
         field == 8 || field == 9 || field == 10 || field == 11;
}

function drawScreen() {
  if (opened == 0) return;
  korg.display.clear();
  korg.display.text("LIVE RELOAD V0.2", 4, 2);
  korg.display.text("SHIFT + BAR 1: HARD", 4, 17);
  korg.display.text("SHIFT + BAR 2: SOFT", 4, 30);

  if (running == 1) korg.display.text("RESTORING...", 4, 45);
  else if (running == 2) korg.display.text("MORPHING...", 4, 45);
  else if (result == 1) korg.display.text("DONE", 4, 45);
  else if (result == 2) korg.display.text("CANCELLED", 4, 45);
  else korg.display.text("READY", 4, 45);
}

function abortReload() {
  running = 0;
  result = 2;
  drawScreen();
}

function finishReload() {
  running = 0;
  result = 1;
  drawScreen();
}

function beginReload(which) {
  sourcePattern = korg.read.pattern();
  stage = 0;
  position = 0;
  blendFrame = 0;
  result = 0;
  running = which;
  drawScreen();
}

function hardFrame() {
  for (let n = 0; n < 2; n += 1) {
    if (position >= 16) break;

    for (let j = 0; j < 15; j += 1) {
      let field = fields[j];
      let savedValue = korg.read.patternValue(
        sourcePattern, position, field
      );
      let liveValue = korg.read.patternValue(
        -1, position, field
      );

      if (liveValue != savedValue) {
        korg.seq.setPartValue(position, field, savedValue);
      }
    }
    position += 1;
  }

  if (position >= 16) finishReload();
}

function softFrame() {
  if (stage == 0) {
    for (let n = 0; n < 4; n += 1) {
      if (position >= 16) break;

      for (let j = 0; j < 15; j += 1) {
        let idx = position * 15 + j;
        let field = fields[j];

        before[idx] = korg.read.patternValue(
          -1, position, field
        );
        target[idx] = korg.read.patternValue(
          sourcePattern, position, field
        );
      }
      position += 1;
    }

    if (position >= 16) {
      stage = 1;
      blendFrame = 0;
    }
    return;
  }

  let group = blendFrame % 4;
  let fraction = (blendFrame - group) / 4 + 1;
  let firstPart = group * 4;

  for (let part = firstPart; part < firstPart + 4; part += 1) {
    for (let j = 0; j < 15; j += 1) {
      let field = fields[j];
      let idx = part * 15 + j;
      let value = target[idx];

      if (isSmooth(field)) {
        value = before[idx] +
          (target[idx] - before[idx]) * fraction / 3;
      } else if (fraction != 3) {
        continue;
      }

      if (korg.read.patternValue(-1, part, field) != value) {
        korg.seq.setPartValue(part, field, value);
      }
    }
  }

  blendFrame += 1;
  if (blendFrame >= 12) finishReload();
}

korg.onEvent("open", () => {
  opened = 1;
  shiftHeld = 0;
  result = 0;
  drawScreen();
});

korg.onEvent("close", () => {
  opened = 0;
  shiftHeld = 0;
  running = 0;
});

korg.onEvent("patternChange", () => {
  if (running != 0) abortReload();
});

korg.onEvent("buttonPress", (key) => {
  if (opened == 0) return;

  if (key == 10) shiftHeld = 1;

  if (shiftHeld == 1 && key == 28) {
    beginReload(1);
  }

  if (shiftHeld == 1 && key == 29) {
    beginReload(2);
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 10) shiftHeld = 0;
});

korg.onEvent("frame", () => {
  if (running == 0) return;

  if (korg.read.pattern() != sourcePattern) {
    abortReload();
    return;
  }

  if (running == 1) hardFrame();
  else softFrame();
});
