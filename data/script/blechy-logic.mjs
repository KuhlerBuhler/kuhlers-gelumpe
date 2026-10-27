/**
 * The behaviour of Blechy, as plugin source. The line `// @@FRAMES@@` is where tools/blechy-build.mjs puts the
 * frame constants and the drawing functions it makes from data/script/blechy-art.mjs; the build writes the
 * finished source to data/script/blechy-source.mjs. Everything here is plain plugin code, nothing is generated.
 */
export const BLECHY_LOGIC = `// Blechy, a run-down nose, built into BLECH: he is the last page of the Electribe's menu ring, open (and with the
// open event) whenever the firmware shows that page, closed (close event) when it shows another one.
// The firmware registers him as a hidden app before this body runs, so the line below only names him; the browser
// model needs it to let him draw.
// Open: he stands at the left edge, about a second after you land on his page he waves (once per landing), then he
// walks slowly to the right edge and back, again and again. Now and then, when he has reached an edge, he stops and
// says something in a speech bubble (a rotation of short lines, among them the favourite tempo and how long you have
// been at it). A tap on the touchpad near him makes him angry, stroking makes him happy.
// PLAY: he walks to the middle, says he will listen for a moment, listens, and then dances (schranz) as long as the
// pattern plays; the pose changes on step events, not on a clock. On stop he walks again.
// The stats live in RAM only. Closed, he draws nothing and only counts. His pictures are the frame tables
// in data/script/blechy-art.mjs, drawn as bitmaps at an offset (posX, posY); the drawing only runs when the picture changes.
korg.app("Blechy", "GAMES");
// @@FRAMES@@

const DX_MAX = 127 - WALK_RIGHT;
const DX_MID = 24;
const WALK_MS = 120;
const STEP_MS = 240;
const BRISK_MS = 70;
const LISTEN_MS = 2800;
const TALK_MS = 3500;
const TALK_FIRST = 8000;
const TALK_GAP = 8000;
const TALK_SPREAD = 8000;
const B_LISTEN = 9;
const ANGRY_MS = 1200;
const HAPPY_MS = 1600;
const STROKE = 120;
const POSE = [0, 2, 1, 3, 2, 0, 3, 1];
const WAVE_DELAY_MS = 1000;
const WAVE_STEP_MS = 220;
const WAVE_MS = 1760;

let isOpen = 0;
let openMs = 0;
let lastSig = -1;
let lastFrame = -1;
let lastBubble = 0;
let lastPos = -1;
let seed = 4711;
let twitchUntil = 0;
let nextTwitch = 0;
let reactKind = 0;
let reactUntil = 0;
let flail = 0;
let waved = 0;
let waveAt = 0;
let posX = 0;
let posY = 0;
let dir = 1;
let walkAt = 0;
let holdUntil = 0;
let mode = 0;
let listenAt = 0;
let nextTalk = 0;
let wantTalk = 0;
let talkKind = 0;
let talkNo = 0;
let talkSide = 0;
let playing = korg.read.transport() == 1 ? 1 : 0;
let playedOnce = 0;
let firstPlayAt = 0;
let bestBpm = 0;
let bestCount = 0;
let touching = 0;
let near = 0;
let moved = 0;
let lastX = 0;
let lastY = 0;
const beats = new Array(256);

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function abs(v) {
  return v < 0 ? -v : v;
}

function numLen(n) {
  let d = 1;
  while (n >= 10) {
    n = n / 10;
    d += 1;
  }
  return d;
}

function bubbleBox(l, r) {
  const w = r - l + 1;
  korg.display.rect(l, 8, w, 1);
  korg.display.rect(l, 41, w, 1);
  korg.display.rect(l, 8, 1, 34);
  korg.display.rect(r, 8, 1, 34);
}

// The tail points at him: to the left of a box on his right, to the right of a box on his left.
function tailLeft(l) {
  korg.display.pixel(l - 1, 22, 1);
  korg.display.rect(l - 2, 23, 2, 1);
  korg.display.rect(l - 3, 24, 3, 1);
  korg.display.rect(l - 2, 25, 2, 1);
  korg.display.pixel(l - 1, 26, 1);
}

function tailRight(r) {
  korg.display.pixel(r + 1, 22, 1);
  korg.display.rect(r + 1, 23, 2, 1);
  korg.display.rect(r + 1, 24, 3, 1);
  korg.display.rect(r + 1, 25, 2, 1);
  korg.display.pixel(r + 1, 26, 1);
}

function drawBubble(kind, side) {
  let l = 53;
  let r = 127;
  if (kind == B_LISTEN) l = 73;
  if (side) {
    l = 0;
    r = 74;
  }
  bubbleBox(l, r);
  if (side) tailRight(r);
  else tailLeft(l);
  const x = l + 3;
  if (kind == B_LISTEN) {
    korg.display.text("ich hoer", x, 11);
    korg.display.text("mir das", x, 22);
    korg.display.text("kurz an", x, 33);
  } else if (kind == 1) {
    korg.display.text("yo", x, 14);
    korg.display.text("na du?", x, 26);
  } else if (kind == 2) {
    if (bestCount > 0) {
      korg.display.text("Lieblings-", x, 12);
      korg.display.textNumber("tempo ", bestBpm, x, 26);
    } else {
      korg.display.text("mein Tempo", x, 12);
      korg.display.text("ist 150 bpm", x, 26);
    }
  } else if (kind == 3) {
    const t = korg.millis() - (playedOnce ? firstPlayAt : 0);
    korg.display.text(playedOnce ? "Spielt seit" : "Laeuft seit", x, 12);
    if (t >= 60000) {
      const m = t / 60000;
      korg.display.number(m, x, 26);
      korg.display.text("min", x + 6 + numLen(m) * 6, 26);
    } else {
      const s = t / 1000;
      korg.display.number(s, x, 26);
      korg.display.text("sek", x + 6 + numLen(s) * 6, 26);
    }
  } else if (kind == 4) {
    korg.display.text("Blech ist", x, 14);
    korg.display.text("mein Ding", x, 26);
  } else if (kind == 5) {
    korg.display.text("bisschen", x, 14);
    korg.display.text("mehr Bass?", x, 26);
  } else if (kind == 6) {
    korg.display.text("nicht so", x, 14);
    korg.display.text("doll tippen", x, 26);
  } else {
    korg.display.text("Schranz", x, 14);
    korg.display.text("ist Liebe", x, 26);
  }
}

function drawFrame(f, last, ox, oy) {
  // @@DISPATCH@@
}

function standing(now) {
  return now < twitchUntil ? F_TWITCH : F_IDLE;
}

// One step towards target every gap ms, px pixels at a time; 1 once he is there.
function move(now, target, gap, px) {
  if (posX == target) return 1;
  dir = target > posX ? 1 : -1;
  if (now - walkAt >= gap) {
    walkAt = now;
    if (abs(target - posX) <= px) posX = target;
    else posX += dir * px;
  }
  return posX == target ? 1 : 0;
}

function startTalk(now, side) {
  wantTalk = 0;
  talkSide = side;
  talkNo = talkNo % 7 + 1;
  talkKind = talkNo;
  holdUntil = now + TALK_MS;
  nextTalk = holdUntil + TALK_GAP + rnd() % TALK_SPREAD;
}

// The walk cycle: the calm and the walk picture in turn every STEP_MS (as on the Discord page), mirrored when he goes left.
// The walk picture sits one row lower, which makes the step.
function walking(now) {
  const pose = (now / STEP_MS) & 1;
  posY = pose;
  if (dir < 0) return F_BACK + pose;
  return pose ? F_WALK : F_IDLE;
}

// Which picture belongs to the moment, and where he is: a reaction first, then the play states (to the middle,
// listening, dancing), then the wave (once per landing, WAVE_DELAY_MS after it, the hand swings every WAVE_STEP_MS),
// then the walk (the pictures alternate, mirrored to the left) with its stops at the edges, the twitch, standing.
function pick(now) {
  if (!playing) mode = 0;
  else if (mode == 0) {
    mode = 1;
    waved = 1;
    talkKind = 0;
    wantTalk = 0;
    holdUntil = 0;
  }
  posY = 0;
  if (reactKind != 0 && now < reactUntil) {
    walkAt = now;
    return reactKind == 1 ? F_ANGRY : F_HAPPY;
  }
  if (mode == 1) {
    if (move(now, DX_MID, BRISK_MS, 2)) {
      mode = 2;
      listenAt = now;
      talkSide = 0;
      return standing(now);
    }
    return walking(now);
  }
  if (mode == 2 && now - listenAt >= LISTEN_MS) mode = 3;
  if (mode == 3) return F_FLAIL + flail;
  if (mode == 2) return F_IDLE;
  if (!waved && now - openMs >= WAVE_DELAY_MS) {
    waved = 1;
    waveAt = now;
  }
  if (waved && now - waveAt < WAVE_MS) return F_WAVE + (((now - waveAt) / WAVE_STEP_MS) & 1);
  if (!waved || now < holdUntil) return standing(now);
  if (now >= nextTalk) wantTalk = 1;
  if (move(now, dir > 0 ? DX_MAX : 0, WALK_MS, 1)) {
    talkKind = 0;
    if (wantTalk) startTalk(now, dir > 0 ? 1 : 0);
    else holdUntil = now + 1000;
    dir = 0 - dir;
    return standing(now);
  }
  return walking(now);
}

function bubbleAt(now) {
  if (mode == 2 && now - listenAt < LISTEN_MS) return B_LISTEN;
  if (mode == 0 && talkKind > 0 && now < holdUntil) return talkKind;
  return 0;
}

korg.onEvent("open", () => {
  isOpen = 1;
  openMs = korg.millis();
  nextTwitch = openMs + 1500;
  nextTalk = openMs + TALK_FIRST + rnd() % TALK_SPREAD;
  twitchUntil = 0;
  reactKind = 0;
  waved = playing;
  waveAt = 0;
  posX = 0;
  dir = 1;
  holdUntil = 0;
  talkKind = 0;
  wantTalk = 0;
  mode = 0;
  lastSig = -1;
  lastFrame = -1;
});

korg.onEvent("close", () => {
  isOpen = 0;
  touching = 0;
});

korg.onEvent("frame", () => {
  const now = korg.millis();
  if (now >= nextTwitch) {
    twitchUntil = now + 160;
    nextTwitch = now + 1500 + rnd() % 2500;
  }
  const f = pick(now);
  const b = bubbleAt(now);
  const pos = posX * 2 + posY;
  const sig = f + b * 16 + (b > 0 ? talkSide * 256 : 0) + pos * 512;
  if (sig != lastSig) {
    // a bubble that was there has to be wiped, so only a frame that stood alone, in the same place, is changed in place
    drawFrame(f, lastBubble == 0 && lastPos == pos ? lastFrame : -1, posX, posY);
    if (b > 0) drawBubble(b, talkSide);
    lastSig = sig;
    lastFrame = f;
    lastBubble = b;
    lastPos = pos;
  }
});

korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TOUCHPAD) {
    touching = 1;
    near = 0;
    moved = 0;
  }
});

korg.onEvent("touch", (x, y, first) => {
  if (!touching || !isOpen) return;
  if (first) {
    const px = x / 8;
    near = px >= FIG_LEFT + posX - 4 && px <= FIG_RIGHT + posX + 4 ? 1 : 0;
  } else {
    moved += abs(x - lastX) + abs(y - lastY);
  }
  lastX = x;
  lastY = y;
  if (near && moved >= STROKE) {
    reactKind = 2;
    reactUntil = korg.millis() + HAPPY_MS;
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.TOUCHPAD && touching) {
    touching = 0;
    if (isOpen && near && moved < STROKE) {
      reactKind = 1;
      reactUntil = korg.millis() + ANGRY_MS;
    }
  }
});

korg.onEvent("play", () => {
  if (!playing) {
    playing = 1;
    if (!playedOnce) {
      playedOnce = 1;
      firstPlayAt = korg.millis();
    }
  }
});

korg.onEvent("stop", () => {
  if (!playing) return;
  playing = 0;
  nextTalk = korg.millis() + TALK_GAP;
  lastSig = -1;
  lastFrame = -1;
});

korg.onEvent("step", (s) => {
  if ((s & 1) == 0) flail = POSE[(s >> 1) & 7];
});

korg.onEvent("beat", () => {
  const bpm = (korg.read.tempo() + 5) / 10;
  if (bpm < 256) {
    beats[bpm] += 1;
    if (beats[bpm] > bestCount) {
      bestCount = beats[bpm];
      bestBpm = bpm;
    }
  }
});
`;
