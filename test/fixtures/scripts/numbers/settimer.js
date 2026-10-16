// Set timer, an app under TOOLS: big mm:ss (h:mm:ss from one hour on) for how long the set has run.
// The first PLAY or key 1 starts it, then it only counts: PLAY and STOP change nothing, key 4 resets after a second press.
// The clock is korg.millis(), so it keeps counting with the app closed; closed, the app only reacts to `play` and keys.
korg.app("Set-Timer", "TOOLS");
// segments a b c d e f g as bits 0 to 6, one entry per digit
const SEG = [63, 6, 91, 79, 102, 109, 125, 7, 127, 111];
const DW = 16;
const DH = 32;
const DX = new Array(5);
const shown = new Array(5);
let started = 0;
let t0 = 0;
let confirmUntil = 0;
let isOpen = 0;
let longMode = 0;
let status = -1;

function drawDigit(slot, d) {
  const x = DX[slot];
  const m = SEG[d];
  korg.display.clearRect(x, 16, DW, DH);
  if (m & 1) korg.display.rect(x, 16, DW, 3);
  if (m & 2) korg.display.rect(x + DW - 3, 19, 3, 11);
  if (m & 4) korg.display.rect(x + DW - 3, 33, 3, 12);
  if (m & 8) korg.display.rect(x, 45, DW, 3);
  if (m & 16) korg.display.rect(x, 33, 3, 12);
  if (m & 32) korg.display.rect(x, 19, 3, 11);
  if (m & 64) korg.display.rect(x + 3, 30, DW - 6, 3);
}

function colon(x) {
  korg.display.rect(x, 24, 3, 3);
  korg.display.rect(x, 37, 3, 3);
}

function layout() {
  korg.display.clearRect(0, 16, 128, DH);
  if (longMode) {
    DX[0] = 11;
    DX[1] = 36;
    DX[2] = 56;
    DX[3] = 81;
    DX[4] = 101;
    colon(30);
    colon(75);
  } else {
    DX[1] = 22;
    DX[2] = 42;
    DX[3] = 70;
    DX[4] = 90;
    colon(62);
  }
  for (let i = 0; i < 5; i++) shown[i] = -1;
}

function elapsed() {
  if (!started) return 0;
  return (korg.millis() - t0) / 1000;
}

function showTime() {
  const secs = elapsed();
  const h = (secs / 3600) % 10;
  const m = (secs / 60) % 60;
  const s = secs % 60;
  const wantLong = secs >= 3600 ? 1 : 0;
  if (wantLong != longMode) {
    longMode = wantLong;
    layout();
  }
  const d0 = h;
  const d1 = m / 10;
  const d2 = m % 10;
  const d3 = s / 10;
  const d4 = s % 10;
  if (longMode && shown[0] != d0) { shown[0] = d0; drawDigit(0, d0); }
  if (shown[1] != d1) { shown[1] = d1; drawDigit(1, d1); }
  if (shown[2] != d2) { shown[2] = d2; drawDigit(2, d2); }
  if (shown[3] != d3) { shown[3] = d3; drawDigit(3, d3); }
  if (shown[4] != d4) { shown[4] = d4; drawDigit(4, d4); }
}

// 0 waiting for the start, 1 running, 2 reset asked
function wantStatus() {
  if (!started) return 0;
  if (confirmUntil > 0) return 2;
  return 1;
}

function showStatus() {
  const s = wantStatus();
  if (s == status) return;
  status = s;
  korg.display.clearRect(90, 0, 38, 8);
  korg.display.clearRect(0, 52, 128, 8);
  if (s == 0) {
    korg.display.text("WAIT", 98, 0);
    korg.display.text("PLAY OR KEY 1 STARTS", 0, 56);
  } else if (s == 1) {
    korg.display.text("RUN", 104, 0);
    korg.display.text("KEY 4 = RESET", 0, 56);
  } else {
    korg.display.text("RESET?", 92, 0);
    korg.display.text("KEY 4 AGAIN = RESET", 0, 56);
  }
}

function start() {
  if (started) return;
  started = 1;
  t0 = korg.millis();
}

korg.onEvent("open", () => {
  isOpen = 1;
  if (confirmUntil > 0 && korg.millis() > confirmUntil) confirmUntil = 0;
  korg.display.clear();
  korg.display.text("SET TIMER", 0, 0);
  status = -1;
  layout();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("play", () => start());

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == 28) start();
  if (key == 31) {
    if (confirmUntil > 0 && korg.millis() <= confirmUntil) {
      started = 0;
      confirmUntil = 0;
    } else {
      confirmUntil = korg.millis() + 3000;
    }
  }
});

korg.onEvent("frame", () => {
  if (confirmUntil > 0 && korg.millis() > confirmUntil) confirmUntil = 0;
  showStatus();
  showTime();
});
