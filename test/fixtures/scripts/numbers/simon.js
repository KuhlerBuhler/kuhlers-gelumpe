// Simon, an app under GAMES, on the four middle pads (3, 4, 11 and 12 counted from 0). The pads light up in a
// sequence, repeat it on the pads, and the sequence grows by one step every round. A wrong pad ends the game and
// shows the number of rounds you got through. While the app is open it holds the panel LEDs (korg.ledHold) so the
// firmware does not paint over the pads; the four squares on the display follow the pads. TAP or any pad starts anew.
korg.app("Simon", "GAMES");
const PADI = [3, 4, 11, 12];
const SX = [38, 66, 38, 66];
const SY = [10, 10, 33, 33];
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

function square(i, on) {
  korg.display.rect(SX[i], SY[i], 24, 20);
  if (!on) korg.display.clearRect(SX[i] + 2, SY[i] + 2, 20, 16);
}

function setPad(i, on) {
  korg.led(44 + PADI[i] * 2, on ? 255 : 0);
  square(i, on);
}

function light(i) {
  if (lit >= 0) setPad(lit, 0);
  lit = i;
  if (i >= 0) setPad(i, 1);
}

function setAll(on) {
  for (let i = 0; i < 4; i++) setPad(i, on);
}

function status(which) {
  korg.display.clearRect(0, 56, 128, 8);
  if (which == 0) korg.display.text("GET READY", 0, 57);
  else if (which == 1) korg.display.text("WATCH", 0, 57);
  else if (which == 2) korg.display.text("YOUR TURN", 0, 57);
  else if (which == 3) korg.display.text("WELL DONE", 0, 57);
  else korg.display.text("GAME OVER, TAP OR PAD", 0, 57);
}

function header() {
  korg.display.clearRect(60, 0, 68, 8);
  korg.display.textNumber("ROUND ", len, 70, 0);
}

function newGame() {
  len = 0;
  pos = 0;
  score = 0;
  lit = -1;
  state = 0;
  timer = 25;
  korg.display.clear();
  korg.display.text("SIMON", 0, 0);
  for (let i = 0; i < 4; i++) square(i, 0);
  status(0);
}

function addStep() {
  seq[len] = rnd() & 3;
  len += 1;
  pos = 0;
  timer = 10;
  state = 1;
  header();
  status(1);
}

function padIndex(index) {
  for (let i = 0; i < 4; i++) {
    if (PADI[i] == index) return i;
  }
  return -1;
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
  if (!isOpen) return;
  if (state == 5) {
    if (down) newGame();
    return;
  }
  const i = padIndex(index);
  if (i < 0) return;
  if (!down) {
    if (lit == i && (state == 2 || state == 4)) light(-1);
    return;
  }
  if (state != 2) return;
  light(i);
  if (seq[pos] != i) {
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
  }
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen && state == 5 && key == 3) newGame();
});

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
      }
      timer = 5;
    } else {
      light(seq[pos]);
      timer = 12 - len / 4;
      if (timer < 5) timer = 5;
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
      korg.display.clearRect(60, 0, 68, 8);
      korg.display.textNumber("SCORE ", score, 70, 0);
    }
  }
});
