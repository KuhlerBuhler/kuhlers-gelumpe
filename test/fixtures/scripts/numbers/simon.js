// Simon, an app under GAMES, on all 16 pads. The pads light up in a sequence, repeat it on the pads, and the sequence
// grows by one step every round. A wrong pad ends the game and shows the number of rounds you got through. While the app is
// open it holds the panel LEDs (korg.ledHold) so the firmware does not paint over the pads; the display shows the round, the
// step and what to do. TAP or any pad starts anew.
korg.app("Simon", "GAMES");
const seq = new Array(60);
let len = 0;
let pos = 0;
let state = 0;
let timer = 0;
let lit = -1;
let score = 0;
let flash = 0;
let seed = 1;
let isOpen = 0;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function setPad(i, on) {
  korg.led(44 + i * 2, on ? 255 : 0);
}

function light(i) {
  if (lit >= 0) setPad(lit, 0);
  lit = i;
  if (i >= 0) setPad(i, 1);
}

function setAll(on) {
  for (let i = 0; i < 16; i++) setPad(i, on);
}

function status(which) {
  korg.display.clearRect(0, 22, 128, 20);
  if (which == 0) korg.display.text("GET READY", 37, 28);
  else if (which == 1) korg.display.text("WATCH", 49, 28);
  else if (which == 2) korg.display.text("YOUR TURN", 37, 28);
  else if (which == 3) korg.display.text("WELL DONE", 37, 28);
  else korg.display.text("GAME OVER", 37, 28);
}

// the round (0) or the score (1), right-aligned 4 pixels from the edge
function header(which, n) {
  const x = n >= 10 ? 77 : 83;
  korg.display.clearRect(60, 0, 68, 10);
  if (which == 0) korg.display.textNumber("ROUND ", n, x, 2);
  else korg.display.textNumber("SCORE ", n, x, 2);
}

// the bottom line: nothing (0), the step to play (1, n), how to start anew (2)
function hint(which, n) {
  korg.display.clearRect(0, 53, 128, 11);
  if (which == 1) korg.display.textNumber("STEP ", n, 4, 55);
  else if (which == 2) korg.display.text("TAP OR PAD: NEW GAME", 4, 55);
}

function newGame() {
  len = 0;
  pos = 0;
  score = 0;
  lit = -1;
  state = 0;
  timer = 25;
  korg.display.clear();
  korg.display.text("SIMON", 4, 2);
  status(0);
  hint(0, 0);
}

function addStep() {
  seq[len] = rnd() & 15;
  len += 1;
  pos = 0;
  timer = 12;
  state = 1;
  header(0, len);
  status(1);
  hint(0, 0);
}

korg.onEvent("open", () => {
  isOpen = 1;
  seed = korg.millis() + 11;
  korg.ledHold(1);
  for (let i = 0; i < 32; i++) korg.led(44 + i, 0);
  newGame();
});

korg.onEvent("close", () => {
  isOpen = 0;
  for (let i = 0; i < 32; i++) korg.led(44 + i, 0);
  korg.ledHold(0);
});

korg.onEvent("pad", (index, down) => {
  if (!isOpen || index > 15) return;
  if (state == 5) {
    if (down) newGame();
    return;
  }
  if (!down) {
    if (lit == index && (state == 2 || state == 4)) light(-1);
    return;
  }
  if (state != 2) return;
  light(index);
  if (seq[pos] != index) {
    state = 3;
    flash = 0;
    timer = 8;
    return;
  }
  pos += 1;
  if (pos >= len) {
    score = len;
    state = 4;
    timer = 20;
    status(3);
  } else {
    hint(1, pos + 1);
  }
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen && state == 5 && key == 3) newGame();
});

// A step of the sequence lights for 18 frames (0.72 s), a little shorter every fourth round, never below 10 (0.4 s).
korg.onEvent("frame", () => {
  if (state == 0) {
    timer -= 1;
    if (timer <= 0) addStep();
  } else if (state == 1) {
    timer -= 1;
    if (timer > 0) return;
    if (lit >= 0) {
      light(-1);
      pos += 1;
      if (pos >= len) {
        pos = 0;
        state = 2;
        status(2);
        hint(1, 1);
      }
      timer = 6;
    } else {
      light(seq[pos]);
      timer = 18 - len / 4;
      if (timer < 10) timer = 10;
    }
  } else if (state == 4) {
    timer -= 1;
    if (timer <= 0) {
      light(-1);
      addStep();
    }
  } else if (state == 3) {
    timer -= 1;
    if (timer > 0) return;
    if (flash < 6) {
      lit = -1;
      setAll(flash & 1 ? 0 : 1);
      flash += 1;
      timer = 6;
    } else {
      setAll(0);
      state = 5;
      status(4);
      header(1, score);
      hint(2, 0);
    }
  }
});
