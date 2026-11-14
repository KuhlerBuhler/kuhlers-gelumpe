korg.app("Blechy Run", "GAMES");
// BLECHY RUN, an endless runner under GAMES. Blechy, the BLECH mascot, runs along the ground and blocks come in from the
// right. Any key (not PLAY, STOP or REC), a pad or a tap on the touchpad makes him jump. The run gets faster over time;
// touching a block ends it with GAME OVER and the score, the best score stays on the card (korg.store slot 0). The same
// keys start the next run, EXIT leaves. The pads keep playing the Electribe while the app is open.
// The pictures are the calm and the walk sprite of assets/blechy/sprites made small, 20 x 24 pixels, three strips of
// column bytes for korg.display.bitmap; HIT is the calm one with crosses for eyes. Positions and speeds count in 1/16 pixel.
const RUN1 = [0, 0, 240, 236, 30, 94, 31, 231, 7, 231, 22, 86, 20, 224, 8, 8, 8, 0, 0, 0, 64, 32, 28, 255, 252, 253, 253, 249, 248, 248, 248, 253, 253, 253, 254, 252, 252, 60, 0, 0, 0, 0, 0, 0, 3, 135, 143, 255, 31, 31, 31, 31, 255, 143, 135, 3, 0, 0, 0, 0];
const RUN2 = [0, 0, 240, 236, 30, 94, 31, 231, 7, 231, 22, 86, 20, 224, 8, 8, 8, 0, 0, 0, 64, 32, 28, 255, 252, 253, 253, 249, 248, 248, 248, 253, 253, 253, 254, 252, 252, 60, 0, 0, 0, 0, 0, 128, 131, 199, 47, 31, 31, 31, 31, 31, 31, 47, 199, 131, 128, 0, 0, 0];
const HIT = [0, 0, 240, 28, 174, 78, 175, 23, 7, 23, 166, 70, 164, 16, 8, 8, 8, 0, 0, 0, 64, 32, 28, 255, 252, 252, 252, 249, 248, 249, 248, 252, 252, 253, 254, 252, 252, 60, 0, 0, 0, 0, 0, 0, 3, 135, 143, 255, 31, 31, 31, 31, 255, 143, 135, 3, 0, 0, 0, 0];

const GROUND = 60;
const BX = 8;
const TOP = GROUND - 24;
const JUMP = 92;
const GRAVITY = 12;
const MAXSPEED = 112;
const N = 3;
const ox = new Array(N);
const ow = new Array(N);
const oh = new Array(N);

// 0 waits for the first jump, 1 runs, 2 game over; keys and pads reach the handlers while the app is closed too
let isOpen = 0;
let state = 0;
let height = 0;
let vy = 0;
let speed = 48;
let dist = 0;
let score = 0;
let best = korg.store.get(0, 0);
let newBest = 0;
let next = 0;
let frames = 0;
let wait = 0;
let dirty = 0;
let shown = 0;
let seed = 12345;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function reset() {
  for (let i = 0; i < N; i++) ow[i] = 0;
  height = 0;
  vy = 0;
  speed = 48;
  dist = 0;
  score = 0;
  newBest = 0;
  next = 64 * 16;
  frames = 0;
}

function spawn() {
  for (let i = 0; i < N; i++) {
    if (ow[i] == 0) {
      const kind = rnd() % 3;
      ox[i] = 128 * 16;
      if (kind == 0) { ow[i] = 4; oh[i] = 10; }
      else if (kind == 1) { ow[i] = 6; oh[i] = 14; }
      else { ow[i] = 12; oh[i] = 7; }
      // room to land before the next one: about 22 frames of running, plus up to 63 pixels
      next = speed * 22 + (rnd() % 64) * 16;
      return;
    }
  }
}

function jump() {
  if (state == 0) {
    seed += korg.millis();
    reset();
    state = 1;
    dirty = 1;
  } else if (state == 2) {
    if (wait > 0) return;
    reset();
    state = 1;
    dirty = 1;
    return;
  }
  if (height == 0) vy = JUMP;
}

function over() {
  state = 2;
  dirty = 1;
  wait = 15;
  if (score > best) {
    best = score;
    newBest = 1;
    korg.store.set(0, best);
    korg.store.save();
  }
}

function step() {
  frames += 1;
  if (vy != 0 || height > 0) {
    height += vy;
    vy -= GRAVITY;
    if (height <= 0) {
      height = 0;
      vy = 0;
    }
  }
  dist += speed;
  score = dist >> 7;
  if (frames % 50 == 0 && speed < MAXSPEED) speed += 2;
  next -= speed;
  if (next <= 0) spawn();
  for (let i = 0; i < N; i++) {
    if (ow[i] == 0) continue;
    ox[i] -= speed;
    const x = ox[i] >> 4;
    if (x + ow[i] <= 0) {
      ow[i] = 0;
      continue;
    }
    if (x < BX + 18 && x + ow[i] > BX + 4 && (height >> 4) < oh[i]) over();
  }
}

function digits(n) {
  let d = 1;
  while (n >= 10) {
    n = n / 10;
    d += 1;
  }
  return d;
}

// The field below the score line: ground, blocks and Blechy (at his highest his top is at y 11).
function field() {
  korg.display.clearRect(0, 10, 128, 54);
  korg.display.rect(0, GROUND, 128, 1);
  const off = (dist >> 4) & 31;
  for (let x = 31 - off; x < 128; x += 32) {
    korg.display.rect(x, GROUND + 2, 2, 1);
    if (x + 17 < 128) korg.display.pixel(x + 17, GROUND + 3, 1);
  }
  for (let i = 0; i < N; i++) {
    if (ow[i] == 0) continue;
    let x = ox[i] >> 4;
    let w = ow[i];
    if (x < 0) {
      w += x;
      x = 0;
    }
    if (x < 128) korg.display.rect(x, GROUND - oh[i], w, oh[i]);
  }
  const y = TOP - (height >> 4);
  if (state == 2) korg.display.bitmap(HIT, BX, y, 20);
  else if (height > 0 || state == 0 || (frames & 4) == 0) korg.display.bitmap(RUN1, BX, y, 20);
  else korg.display.bitmap(RUN2, BX, y, 20);
}

// The score top right, drawn again only when it changed.
function scoreText() {
  shown = score;
  korg.display.clearRect(64, 2, 64, 7);
  korg.display.number(score, 124 - 6 * digits(score), 2);
}

function draw() {
  korg.display.clear();
  korg.display.textNumber("HI ", best, 4, 2);
  scoreText();
  field();
  if (state == 0) korg.display.text("JUMP: KEY OR PAD", 16, 16);
  if (state == 2) {
    korg.display.text("GAME OVER", 37, 16);
    if (newBest) korg.display.text("NEW BEST", 40, 26);
  }
}

korg.onEvent("open", () => {
  isOpen = 1;
  state = 0;
  reset();
  draw();
});

korg.onEvent("close", () => {
  isOpen = 0;
  state = 0;
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key != 2 && key != 1 && key != 0) jump();
});

korg.onEvent("pad", (index, down) => {
  if (isOpen && down) jump();
});

// While it runs the field is drawn every frame and the score when it changed; GAME OVER and the start draw the whole
// display once.
korg.onEvent("frame", () => {
  if (state == 1) step();
  else if (wait > 0) wait -= 1;
  if (dirty) {
    dirty = 0;
    draw();
  } else if (state == 1) {
    field();
    if (score != shown) scoreText();
  }
});
