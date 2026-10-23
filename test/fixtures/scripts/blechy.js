// Blechy, a run-down nose, built into BLECH: he is the last page of the Electribe's menu ring, open (and with the
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
// The frame numbers and the pictures below are made from data/script/blechy-art.mjs by tools/blechy-build.mjs.
const F_IDLE = 0;
const F_TWITCH = 1;
const F_ANGRY = 2;
const F_HAPPY = 3;
const F_FLAIL = 4;
const F_WAVE = 8;
const F_WALK = 10;
const FIG_LEFT = 5;
const FIG_RIGHT = 45;
const WALK_RIGHT = 48;

const P_STAND_BASE = [
  0, 0, 0, 0, 192, 0, 8, 4, 4, 2, 130, 130, 130, 130, 132, 196, 216, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 254, 1, 240, 252, 254, 68, 130, 24, 0, 24, 129, 65, 243, 255, 255, 255, 243, 1, 1, 1, 1, 1, 0, 0, 224, 128, 0, 0, 0, 0, 0,
  0, 0, 0, 224, 31, 1, 7, 15, 13, 23, 47, 47, 47, 119, 125, 127, 127, 127, 127, 127, 53, 22, 44, 12, 12, 6, 1, 0, 0, 1, 2, 4, 24, 224,
  16, 8, 0, 11, 48, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 48, 9,
  0, 0, 0, 0, 0, 0, 3, 12, 48, 64, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 64, 48, 12, 3, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 2, 2, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameStandBase(ox, oy) {
  korg.display.bitmap(P_STAND_BASE, ox + 7, oy + 6, 34);
}

const P_STAND_CORE = [
  0, 0, 0, 0, 128, 0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 128, 176, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 252, 3, 224, 248, 252, 136, 4, 49, 1, 49, 3, 131, 231, 255, 255, 254, 230, 2, 2, 2, 2, 2, 0, 0, 192, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 193, 62, 3, 15, 31, 26, 47, 94, 94, 94, 239, 250, 255, 255, 255, 255, 255, 106, 44, 88, 24, 24, 12, 2, 1, 1, 2, 4, 8, 48, 192,
  32, 16, 0, 23, 96, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 96, 19,
  0, 0, 0, 0, 0, 1, 6, 24, 96, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 96, 24, 6, 1, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 0, 4, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 6, 1, 0, 0, 0, 0, 0, 0, 0
];

function frameStandCore(ox, oy) {
  korg.display.bitmap(P_STAND_CORE, ox + 7, oy + 5, 34);
}

const P_IDLE = [
  0, 0, 0, 0, 0, 0, 0, 128, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 2, 132, 164, 132, 9, 17, 48, 0, 0, 2, 50, 18, 10, 226, 161, 225, 9, 25, 97, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33, 134, 12, 140, 76, 70, 41, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 128, 0, 0, 32, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 16, 32, 64, 64, 128,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 46, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 46, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameIdle(ox, oy) {
  korg.display.bitmap(P_IDLE, ox + 5, oy + 4, 41);
}

const P_TWITCH = [
  0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 8, 4, 8, 72, 8, 18, 34, 96, 0, 0, 7, 101, 181, 119, 55, 55, 55, 64, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 64, 135, 133, 7, 64, 32, 16, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 64, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 32, 64, 128, 128, 0,
  2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 240, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 96, 96, 96, 92, 99, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 96, 99, 92, 96, 96, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameTwitch(ox, oy) {
  korg.display.bitmap(P_TWITCH, ox + 5, oy + 3, 41);
}

const P_ANGRY = [
  0, 0, 0, 0, 0, 0, 0, 128, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 136, 144, 128, 17, 33, 0, 0, 0, 0, 0, 32, 16, 240, 168, 232, 10, 30, 99, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33, 134, 12, 140, 76, 70, 41, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 128, 0, 0, 32, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 16, 32, 64, 64, 128,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 46, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 46, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameAngry(ox, oy) {
  korg.display.bitmap(P_ANGRY, ox + 5, oy + 4, 41);
}

const P_HAPPY = [
  0, 0, 0, 0, 0, 0, 0, 128, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 194, 4, 100, 4, 200, 16, 48, 0, 0, 3, 51, 19, 203, 99, 99, 99, 207, 31, 96, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33, 134, 12, 140, 76, 70, 41, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 128, 0, 0, 32, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 16, 32, 64, 64, 128,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 46, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 46, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameHappy(ox, oy) {
  korg.display.bitmap(P_HAPPY, ox + 5, oy + 4, 41);
}

const P_WAVE0 = [
  0, 0, 0, 0, 0, 0, 0, 128, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 96, 128, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 2, 132, 164, 132, 9, 17, 48, 0, 0, 2, 50, 18, 10, 226, 161, 225, 9, 25, 97, 0, 0, 0, 0, 0, 0, 159, 97, 30,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33, 134, 12, 140, 76, 70, 41, 20, 0, 0, 0, 0, 16, 14, 1, 0, 0,
  0, 128, 0, 0, 32, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 24, 0, 0, 0,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 46, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 46, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameWave0(ox, oy) {
  korg.display.bitmap(P_WAVE0, ox + 5, oy + 4, 39);
}

const P_WAVE1 = [
  0, 0, 0, 0, 0, 0, 0, 128, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 224, 224,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 2, 132, 164, 132, 9, 17, 48, 0, 0, 2, 50, 18, 10, 226, 161, 225, 9, 25, 97, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 223, 33, 31, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33, 134, 12, 140, 76, 70, 41, 20, 0, 0, 0, 0, 0, 32, 16, 12, 2, 1, 0, 0, 0, 0,
  0, 128, 0, 0, 32, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 24, 0, 0, 0, 0, 0, 0, 0, 0,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 46, 49, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 49, 46, 48, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameWave1(ox, oy) {
  korg.display.bitmap(P_WAVE1, ox + 5, oy + 4, 44);
}

const P_WALK = [
  0, 0, 128, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 4, 2, 132, 164, 132, 9, 17, 48, 0, 0, 2, 50, 18, 10, 226, 161, 225, 9, 25, 97, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33, 134, 12, 140, 76, 70, 41, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 8, 8, 8, 16, 16,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 192, 32, 24, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 32, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 48, 48, 48, 48, 60, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 51, 44, 48, 48, 48, 0, 0, 0, 0, 0, 0
];

function frameWalk(ox, oy) {
  korg.display.bitmap(P_WALK, ox + 9, oy + 4, 37);
}

const P_FLAIL_BASE = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 48, 128, 96, 16, 0, 8, 4, 194, 2, 134, 122, 115, 139, 51, 79, 71, 6, 7, 52, 0, 0, 0, 128, 0, 0, 0, 0, 0, 0,
  128, 0, 3, 0, 0, 6, 9, 17, 8, 4, 6, 118, 234, 255, 255, 254, 106, 96, 0, 0, 4, 0, 8, 0, 0, 1, 0, 0, 0, 0, 192,
  7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3,
  0, 0, 1, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6, 1, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 8, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlailBase(ox, oy) {
  korg.display.bitmap(P_FLAIL_BASE, ox + 10, oy + 5, 31);
}

function frameFlailCore(ox, oy) {
  korg.display.bitmap(P_FLAIL_BASE, ox + 10, oy + 5, 31);
}

const P_FLAIL0 = [
  0, 0, 0, 0, 0, 0, 0, 128, 96, 32, 16, 8, 8, 4, 4, 4, 8, 8, 16, 16, 224, 0, 0, 0, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  8, 48, 192, 0, 0, 128, 30, 129, 48, 216, 12, 226, 245, 11, 136, 144, 3, 1, 137, 153, 97, 113, 115, 145, 151, 223, 223, 255, 192, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 64, 32,
  0, 0, 0, 3, 132, 104, 17, 0, 15, 19, 8, 12, 45, 36, 33, 2, 0, 1, 0, 3, 43, 60, 83, 119, 212, 88, 72, 111, 46, 21, 12, 24, 32, 64, 0, 96, 24, 4, 0, 1, 0, 0,
  0, 0, 0, 0, 0, 240, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 248, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 1, 16, 96, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 96, 16, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 128, 96, 17, 14, 2, 4, 4, 24, 16, 16, 0, 16, 0, 0, 16, 32, 32, 56, 68, 130, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 12, 12, 12, 12, 14, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 103, 88, 96, 96, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlail0(ox, oy) {
  korg.display.bitmap(P_FLAIL0, ox + 6, oy + 4, 42);
}

const P_FLAIL1 = [
  96, 144, 8, 4, 2, 129, 65, 193, 65, 97, 98, 162, 164, 40, 160, 128, 128, 0, 0, 0, 24, 24, 56, 248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 32, 12, 2,
  62, 193, 48, 252, 128, 204, 179, 33, 67, 66, 126, 4, 35, 47, 176, 17, 0, 40, 6, 208, 216, 216, 89, 231, 127, 144, 0, 0, 64, 64, 128, 128, 96, 12, 1, 0, 0, 0, 0,
  0, 0, 15, 1, 7, 7, 6, 11, 22, 21, 22, 27, 62, 17, 2, 0, 0, 0, 0, 2, 2, 2, 1, 2, 0, 0, 0, 0, 0, 0, 1, 6, 128, 0, 0, 0, 0, 0, 0,
  0, 192, 63, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 20, 11, 0, 0, 0, 0, 0, 0, 0,
  1, 0, 0, 0, 0, 0, 1, 6, 8, 16, 32, 64, 128, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 128, 96, 24, 6, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 12, 112, 129, 1, 129, 186, 135, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 2, 3, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlail1(ox, oy) {
  korg.display.bitmap(P_FLAIL1, ox + 8, oy + 8, 39);
}

const P_FLAIL2 = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 64, 32, 16, 16, 16, 16, 16, 32, 32, 192, 0, 0, 0, 0, 0, 0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  4, 24, 32, 64, 128, 0, 0, 0, 0, 224, 30, 1, 0, 96, 0, 128, 116, 20, 36, 230, 196, 36, 22, 51, 211, 49, 1, 163, 199, 195, 47, 192, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 1, 2, 12, 0, 16, 103, 200, 63, 19, 124, 122, 35, 210, 50, 86, 108, 163, 36, 86, 2, 1, 0, 86, 38, 236, 216, 200, 127, 7, 1, 0, 0, 8, 16, 32, 64, 128, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 1, 0, 0, 0, 0, 0, 1, 1, 1, 3, 2, 0, 0, 0, 0, 2, 0, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 32, 16, 32, 64,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 96, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 224, 0, 3, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 4, 200, 48, 8, 16, 16, 0, 32, 0, 0, 32, 32, 32, 32, 32, 32, 60, 194, 129, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 64, 192, 192, 160, 104, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 33, 54, 40, 48, 48, 0, 0, 0, 0
];

function frameFlail2(ox, oy) {
  korg.display.bitmap(P_FLAIL2, ox, oy + 3, 44);
}

const P_FLAIL3 = [
  0, 48, 200, 48, 16, 8, 4, 4, 132, 2, 2, 130, 130, 132, 136, 184, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 76, 3, 24, 236, 198, 50, 121, 4, 197, 64, 4, 8, 0, 204, 176, 184, 153, 224, 194, 30, 26, 27, 123, 231, 254, 2, 0, 0, 0, 0, 0, 0, 0, 128, 96, 0, 24, 4, 2,
  112, 12, 0, 2, 1, 6, 6, 39, 42, 40, 8, 1, 0, 0, 1, 149, 159, 239, 108, 185, 187, 115, 95, 61, 14, 5, 12, 16, 32, 0, 32, 24, 0, 6, 1, 0, 0, 0, 0, 0,
  120, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 124, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 24, 32, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 96, 16, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 1, 13, 246, 4, 8, 8, 8, 0, 8, 0, 192, 48, 16, 8, 4, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 12, 12, 12, 10, 13, 0, 0, 0, 0, 24, 24, 22, 43, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
];

function frameFlail3(ox, oy) {
  korg.display.bitmap(P_FLAIL3, ox + 11, oy + 5, 40);
}

const DX_MAX = 127 - WALK_RIGHT;
const DX_MID = 24;
const WALK_MS = 120;
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
    korg.display.text("kein Mund,", x, 14);
    korg.display.text("kein Problem", x, 26);
  } else if (kind == 6) {
    korg.display.text("bisschen", x, 14);
    korg.display.text("mehr Bass?", x, 26);
  } else if (kind == 7) {
    korg.display.text("nicht so", x, 14);
    korg.display.text("doll tippen", x, 26);
  } else {
    korg.display.text("Schranz", x, 14);
    korg.display.text("ist Liebe", x, 26);
  }
}

function drawFrame(f, last, ox, oy) {
  if (f == 0 || f == 1 || f == 2 || f == 3 || f == 8 || f == 9 || f == 10) {
    if (last == 0 || last == 1 || last == 2 || last == 3 || last == 8 || last == 9 || last == 10) {
      korg.display.clearRect(ox + 5, oy + 9, 44, 49);
      frameStandCore(ox, oy);
    } else {
      korg.display.clear();
      frameStandBase(ox, oy);
    }
    if (f == 0) frameIdle(ox, oy);
    else if (f == 1) frameTwitch(ox, oy);
    else if (f == 2) frameAngry(ox, oy);
    else if (f == 3) frameHappy(ox, oy);
    else if (f == 8) frameWave0(ox, oy);
    else if (f == 9) frameWave1(ox, oy);
    else if (f == 10) frameWalk(ox, oy);
  } else if (f == 4 || f == 5 || f == 6 || f == 7) {
    if (last == 4 || last == 5 || last == 6 || last == 7) {
      korg.display.clearRect(ox, oy + 6, 51, 53);
      frameFlailCore(ox, oy);
    } else {
      korg.display.clear();
      frameFlailBase(ox, oy);
    }
    if (f == 4) frameFlail0(ox, oy);
    else if (f == 5) frameFlail1(ox, oy);
    else if (f == 6) frameFlail2(ox, oy);
    else if (f == 7) frameFlail3(ox, oy);
  }
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
  talkNo = talkNo % 8 + 1;
  talkKind = talkNo;
  holdUntil = now + TALK_MS;
  nextTalk = holdUntil + TALK_GAP + rnd() % TALK_SPREAD;
}

function walking() {
  return F_WALK;
}

// Which picture belongs to the moment, and where he is: a reaction first, then the play states (to the middle,
// listening, dancing), then the wave (once per landing, WAVE_DELAY_MS after it, the hand swings every WAVE_STEP_MS),
// then the walk with its stops at the edges, the twitch, standing.
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
    posY = (posX >> 1) & 1;
    return walking();
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
  posY = (posX >> 1) & 1;
  return walking();
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
