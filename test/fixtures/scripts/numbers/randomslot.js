korg.app("RANDOM SLOT", "TOOLS");

// RANDOM SLOT V0.5 by handst0n3, from the BLECH Discord
// BLECHTRIBE API 14+
// Single part randomizer
// No automatic mode

const soundFields = [
  1, 2, 3, 4, 5,
  6, 7, 8, 9, 10,
  11, 14, 15, 16, 18
];

const soundLow = [
  0, 0, 0, -63, 0,
  0, 0, 0, 0, 0,
  -63, 0, -63, 0, 0
];

const soundHigh = [
  16, 127, 127, 63, 71,
  127, 127, 127, 127, 127,
  63, 127, 63, 127, 127
];

const variationFields = [
  2, 3, 4, 6, 7, 8,
  9, 10, 11, 14, 15, 16, 18
];

const variationLow = [
  0, 0, -63, 0, 0, 0,
  0, 0, -63, 0, -63, 0, 0
];

const variationHigh = [
  127, 127, 63, 127, 127, 127,
  127, 127, 63, 127, 63, 127, 127
];

const savedMutes = new Array(16);

let opened = 0;
let selectedPart = 0;
let targetPart = 0;
let soloActive = 0;

let selectedMode = 1;
let activeMode = 0;

let spinFrame = 0;
let workIndex = 0;
let finished = 0;

let reelA = 0;
let reelB = 1;
let reelC = 2;

let sourcePattern = -1;
let seed = 1234567;
let frameCounter = 0;

// RANDOM ENGINE

function rnd(maximum) {
  seed = (
    seed * 1664525 + 1013904223
  ) & 2147483647;

  if (maximum <= 1) return 0;
  return seed % maximum;
}

function between(a, b) {
  return a + rnd(b - a + 1);
}

function clamp(value, a, b) {
  if (value < a) return a;
  if (value > b) return b;
  return value;
}

// DISPLAY

function outline(x, y, w, h) {
  korg.display.rect(x, y, w, 1);
  korg.display.rect(x, y + h - 1, w, 1);
  korg.display.rect(x, y, 1, h);
  korg.display.rect(x + w - 1, y, 1, h);
}

function drawStar(x, y) {
  korg.display.rect(x + 9, y, 2, 4);
  korg.display.rect(x + 8, y + 4, 4, 2);
  korg.display.rect(x + 3, y + 6, 14, 2);
  korg.display.rect(x + 5, y + 8, 10, 2);
  korg.display.rect(x + 6, y + 10, 8, 2);
  korg.display.rect(x + 4, y + 12, 4, 2);
  korg.display.rect(x + 12, y + 12, 4, 2);
  korg.display.rect(x + 3, y + 14, 3, 2);
  korg.display.rect(x + 14, y + 14, 3, 2);
}

function drawCherry(x, y) {
  korg.display.rect(x + 9, y, 2, 5);
  korg.display.rect(x + 5, y + 4, 5, 2);
  korg.display.rect(x + 10, y + 4, 5, 2);
  korg.display.rect(x + 3, y + 8, 6, 6);
  korg.display.rect(x + 11, y + 8, 6, 6);
  korg.display.rect(x + 4, y + 7, 4, 1);
  korg.display.rect(x + 12, y + 7, 4, 1);
}

function drawBell(x, y) {
  korg.display.rect(x + 8, y + 1, 4, 2);
  korg.display.rect(x + 5, y + 3, 10, 2);
  korg.display.rect(x + 4, y + 5, 12, 6);
  korg.display.rect(x + 2, y + 11, 16, 2);
  korg.display.rect(x + 7, y + 13, 6, 2);
  korg.display.rect(x + 8, y + 15, 4, 1);
}

function drawMoney(x, y) {
  outline(x + 1, y + 3, 19, 12);
  outline(x + 4, y + 5, 13, 8);
  korg.display.rect(x + 7, y + 8, 6, 3);
  korg.display.pixel(x + 3, y + 6, 1);
  korg.display.pixel(x + 17, y + 12, 1);
}

function drawJackpot(x, y) {
  korg.display.text("777", x + 1, y + 4);
  korg.display.rect(x + 1, y + 14, 19, 1);
}

function drawSymbol(kind, x, y) {
  if (kind == 0) drawStar(x, y);
  else if (kind == 1) drawCherry(x, y);
  else if (kind == 2) drawBell(x, y);
  else if (kind == 3) drawMoney(x, y);
  else drawJackpot(x, y);
}

function spinReels() {
  reelA = rnd(5);
  reelB = rnd(5);
  reelC = rnd(5);
}

function drawScreen() {
  if (opened == 0) return;

  korg.display.clear();
  korg.display.text("RANDOM SLOT", 30, 2);

  outline(4, 13, 38, 23);
  outline(45, 13, 38, 23);
  outline(86, 13, 38, 23);

  drawSymbol(reelA, 13, 16);
  drawSymbol(reelB, 54, 16);
  drawSymbol(reelC, 95, 16);

  if (selectedMode == 1) {
    korg.display.text("SOUND", 4, 39);
  } else if (selectedMode == 2) {
    korg.display.text("MELODY", 4, 39);
  } else if (selectedMode == 3) {
    korg.display.text("S-VAR", 4, 39);
  } else {
    korg.display.text("P-VAR", 4, 39);
  }

  korg.display.text("P:", 52, 39);
  korg.display.number(selectedPart + 1, 66, 39);

  if (soloActive == 1) {
    korg.display.text("SOLO", 96, 39);
  }

  if (activeMode != 0) {
    korg.display.text("SPINNING", 4, 54);
  } else if (finished == 1) {
    korg.display.text("DONE - READY", 4, 54);
  } else {
    korg.display.text("BAR 1-4 TO SPIN", 4, 54);
  }
}

// SOLO MODE

function soloOn() {
  if (soloActive == 1) return;

  for (let i = 0; i < 16; i += 1) {
    savedMutes[i] = korg.read.mute(i);
  }

  soloActive = 1;

  for (let i = 0; i < 16; i += 1) {
    if (i == selectedPart) {
      korg.mute(i, 0);
    } else {
      korg.mute(i, 1);
    }
  }

  drawScreen();
}

function soloOff() {
  if (soloActive == 0) return;

  soloActive = 0;

  for (let i = 0; i < 16; i += 1) {
    korg.mute(i, savedMutes[i]);
  }

  drawScreen();
}

function toggleSolo() {
  if (soloActive == 0) soloOn();
  else soloOff();
}

function selectPart(part) {
  if (part < 0 || part > 15) return;

  selectedPart = part;

  if (soloActive == 1) {
    for (let i = 0; i < 16; i += 1) {
      if (i == selectedPart) {
        korg.mute(i, 0);
      } else {
        korg.mute(i, 1);
      }
    }
  }

  drawScreen();
}

// SOUND RANDOM

function randomSoundField(part, slot) {
  let value = between(
    soundLow[slot],
    soundHigh[slot]
  );

  korg.seq.setPartValue(
    part,
    soundFields[slot],
    value
  );
}

// SOUND VARIATION

function randomSoundVariation(part) {
  let slot = rnd(13);
  let field = variationFields[slot];

  let current = korg.read.patternValue(
    -1, part, field
  );

  let change = between(-7, 7);

  let value = clamp(
    current + change,
    variationLow[slot],
    variationHigh[slot]
  );

  if (value != current) {
    korg.seq.setPartValue(
      part, field, value
    );
  }
}

// MELODY RANDOM

function randomMelodyChunk(part, firstStep) {
  for (let i = 0; i < 8; i += 1) {
    let step = firstStep + i;

    if (rnd(100) < 60) {
      let note = between(36, 84);
      let velocity = between(55, 127);
      let gate = between(25, 95);

      korg.seq.setGate(part, step, gate);

      korg.seq.setStep(
        part, step, note, velocity
      );
    } else {
      korg.seq.setStep(part, step, -1, 0);
    }
  }
}

// PATTERN VARIATION

function randomPatternVariation(part) {
  let step = rnd(64);

  if (rnd(100) < 30) {
    korg.seq.setStep(
      part,
      step,
      between(48, 76),
      between(65, 110)
    );
  } else {
    korg.seq.setGate(
      part,
      step,
      between(35, 96)
    );
  }
}

// START RANDOMIZATION

function startSpin(mode) {
  if (opened == 0) return;
  if (activeMode != 0) return;

  selectedMode = mode;
  activeMode = mode;

  targetPart = selectedPart;
  sourcePattern = korg.read.pattern();

  spinFrame = 0;
  workIndex = 0;
  finished = 0;

  seed = (
    seed +
    frameCounter * 7919 +
    mode * 1237 +
    selectedPart * 311
  ) & 2147483647;

  if (seed == 0) seed = 1234567;

  spinReels();
  drawScreen();
}

// SPIN PROCESS

function performSpin() {
  if (activeMode == 0) return;

  if (korg.read.pattern() != sourcePattern) {
    activeMode = 0;
    finished = 0;
    drawScreen();
    return;
  }

  spinFrame += 1;

  if (spinFrame % 2 == 0) {
    spinReels();
    drawScreen();
  }

  if (spinFrame <= 8) return;

  // BAR 1 : SOUND RANDOM

  if (activeMode == 1) {
    for (let i = 0; i < 3; i += 1) {
      if (workIndex < 15) {
        randomSoundField(
          targetPart,
          workIndex
        );
        workIndex += 1;
      }
    }
  }

  // BAR 2 : MELODY RANDOM

  if (activeMode == 2) {
    if (workIndex < 64) {
      randomMelodyChunk(
        targetPart,
        workIndex
      );
      workIndex += 8;
    }
  }

  // BAR 3 : SOUND VARIATION

  if (activeMode == 3) {
    if (workIndex < 2) {
      randomSoundVariation(targetPart);
      workIndex += 1;
    }
  }

  // BAR 4 : PATTERN VARIATION

  if (activeMode == 4) {
    if (workIndex < 2) {
      randomPatternVariation(targetPart);
      workIndex += 1;
    }
  }

  if (spinFrame >= 24) {
    activeMode = 0;
    finished = 1;
    drawScreen();
  }
}

// EVENTS

korg.onEvent("open", () => {
  opened = 1;
  activeMode = 0;
  finished = 0;

  let part = korg.read.part();

  if (part >= 0 && part < 16) {
    selectedPart = part;
  } else {
    selectedPart = 0;
  }

  korg.padHold(1);
  drawScreen();
});

korg.onEvent("close", () => {
  soloOff();

  opened = 0;
  activeMode = 0;

  korg.padHold(0);
});

korg.onEvent("patternChange", () => {
  activeMode = 0;
  finished = 0;
  soloActive = 0;
  drawScreen();
});

korg.onEvent("buttonPress", (key) => {
  if (opened == 0) return;

  if (key == 16) {
    toggleSolo();
  }

  if (key == 28) {
    startSpin(1);
  }

  if (key == 29) {
    startSpin(2);
  }

  if (key == 30) {
    startSpin(3);
  }

  if (key == 31) {
    startSpin(4);
  }
});

korg.onEvent("pad", (index, down, velocity) => {
  if (opened == 0) return;
  if (down == 0) return;

  selectPart(index);
});

korg.onEvent("frame", () => {
  frameCounter += 1;

  if (activeMode != 0) {
    performSpin();
  }
});
