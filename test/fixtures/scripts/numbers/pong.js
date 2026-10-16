// Pong against a bot, an app under GAMES: first to 9 wins. Your paddle is on the left. Move it with a finger on the
// touchpad (the height of the finger is the height of the paddle), with Part left (up) and Part right (down), or
// with an encoder. The bot is slow on purpose: it only reacts to a ball that comes towards it, it misjudges the height
// a little after every return, and a steep return is faster than it can follow. The ball speeds up with every hit.
// Positions of the ball are in quarter pixels.
korg.app("Pong", "GAMES");
const NET = [0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33];
const PH = 14;
const PX = 4;
const BOTX = 121;
let bx = 0;
let by = 0;
let vx = 0;
let vy = 0;
let py = 25;
let boty = 25;
let botErr = 0;
let myScore = 0;
let botScore = 0;
let state = 0;
let wait = 0;
let serveDir = 1;
let up = 0;
let down = 0;
let seed = 1;
let isOpen = 0;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function serve() {
  bx = 62 * 4;
  by = 30 * 4;
  vx = 10 * serveDir;
  vy = (rnd() % 9 - 4) * 2;
  botErr = rnd() % 11 - 5;
  state = 1;
}

function newGame() {
  myScore = 0;
  botScore = 0;
  serveDir = 1;
  state = 0;
  wait = 25;
}

function clampPaddle(y) {
  if (y < 0) return 0;
  if (y > 64 - PH) return 64 - PH;
  return y;
}

function point(mine) {
  if (mine) {
    myScore += 1;
    serveDir = 1;
  } else {
    botScore += 1;
    serveDir = -1;
  }
  if (myScore >= 9 || botScore >= 9) {
    state = 2;
  } else {
    state = 0;
    wait = 25;
  }
}

function moveBot() {
  let target = 25;
  if (vx > 0 && (bx >> 2) > 40) target = (by >> 2) - 6 + botErr;
  target = clampPaddle(target);
  if (boty < target) boty += 2;
  else if (boty > target) boty -= 2;
  if (boty > target - 2 && boty < target + 2) boty = target;
}

function moveBall() {
  bx += vx;
  by += vy;
  if (by < 0) {
    by = 0 - by;
    vy = 0 - vy;
  }
  if (by > 60 * 4) {
    by = 120 * 4 - by;
    vy = 0 - vy;
  }
  const x = bx >> 2;
  const y = by >> 2;
  if (vx < 0 && x <= PX + 3 && x >= PX - 2 && y + 3 >= py && y <= py + PH) {
    bx = (PX + 4) * 4;
    vx = 0 - vx + 1;
    if (vx > 20) vx = 20;
    vy = (y + 1 - (py + 7)) * 2;
    botErr = rnd() % 11 - 5;
  } else if (vx > 0 && x + 3 >= BOTX && x <= BOTX + 3 && y + 3 >= boty && y <= boty + PH) {
    bx = (BOTX - 4) * 4;
    vx = 0 - vx - 1;
    if (vx < -20) vx = -20;
    vy = (y + 1 - (boty + 7)) * 2;
  } else if (x < 0) {
    point(0);
  } else if (x > 127) {
    point(1);
  }
}

function draw() {
  korg.display.clear();
  korg.display.bitmap(NET, 63, 0, 1);
  korg.display.rect(PX, py, 3, PH);
  korg.display.rect(BOTX, boty, 3, PH);
  korg.display.number(myScore, 52, 2);
  korg.display.number(botScore, 70, 2);
  if (state == 1) korg.display.rect(bx >> 2, by >> 2, 3, 3);
  if (state == 2) {
    if (myScore > botScore) korg.display.text("YOU WIN", 44, 30);
    else korg.display.text("BOT WINS", 40, 30);
  }
}

korg.onEvent("open", () => {
  isOpen = 1;
  seed = korg.millis() + 5;
  up = 0;
  down = 0;
  py = 25;
  boty = 25;
  newGame();
  draw();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("touch", (x, y) => {
  if (!isOpen) return;
  if (y > 1023) y = 1023;
  py = clampPaddle(((1023 - y) * (65 - PH)) >> 10);
});

korg.onEvent("encoder", (index, delta) => {
  if (isOpen) py = clampPaddle(py + delta * 3);
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == 11) up = 1;
  if (key == 15) down = 1;
  if (state == 2) newGame();
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 11) up = 0;
  if (key == 15) down = 0;
});

korg.onEvent("frame", () => {
  if (up) py = clampPaddle(py - 3);
  if (down) py = clampPaddle(py + 3);
  if (state == 0) {
    wait -= 1;
    if (wait <= 0) serve();
  } else if (state == 1) {
    moveBot();
    moveBall();
  }
  draw();
});
